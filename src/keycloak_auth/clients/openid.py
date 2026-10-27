import asyncio
from types import TracebackType
from typing import Any, Literal, Self

import httpx2
import jwt
from cachetools import TTLCache
from jwt.types import Options

from .. import urls
from ..exceptions import KeycloakError
from ..models.openid import (
    AuthResult,
    DecodedToken,
    DeviceAuthResponse,
    Introspect,
    IntrospectInactive,
    IntrospectRPT,
    Permission,
    Realm,
    TokenResponse,
    UserInfo,
    WellKnown,
)
from ..utils import check_permission_format, gen_auth_header, raise_error

TOKEN_TYPE_HINT = Literal["access_token", "refresh_token", "requesting_party_token"]
PUBLIC_KEY_TTL = 3600  # Cache the public key for 1 hour
DEVICE_CODE_SLOW_DOWN = 5  # Seconds added to the polling interval on `slow_down` (RFC 8628, section 3.5)


def _scope_param(scope: list[str] | None) -> str:
    # add the openid scope if not present, as required by the OpenID Connect spec
    scope = list(scope or [])
    if "openid" not in scope:
        scope.append("openid")
    return " ".join(scope)


class KeycloakOpenID:
    """
    Keycloak OpenID client.

    Args:
        server_url (str): Keycloak server URL.
        realm (str): Keycloak realm name.
        client_id (str): Keycloak client ID.
        client_secret (str, optional): Keycloak client secret. Defaults to None.
        verify (bool, optional): Verify SSL certificate. Defaults to True.
        timeout (int, optional): Request timeout in seconds. Defaults to 10.
    """

    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str | None = None,
        verify: bool = True,
        timeout: int = 10,
    ):
        self.server_url = server_url
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = httpx2.Client(verify=verify, timeout=timeout, http2=True)

    def well_known(self) -> WellKnown:
        """
        Get the well known configuration.

        Returns:
            WellKnown: Well known configuration.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_WELL_KNOWN.format(realm_name=self.realm)
        resp = self._http.get(self.server_url + path)

        if resp.status_code != 200:
            raise_error(resp)
        return WellKnown.model_validate(resp.json())


class AsyncKeycloakOpenID:
    """
    Asynchronous Keycloak OpenID client.

    Args:
        server_url (str): Keycloak server URL.
        realm (str): Keycloak realm name.
        client_id (str): Keycloak client ID.
        client_secret (str, optional): Keycloak client secret. Defaults to None.
        verify (bool, optional): Verify SSL certificate. Defaults to True.
        timeout (int, optional): Request timeout in seconds. Defaults to 10.
    """

    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str | None = None,
        verify: bool = True,
        timeout: int = 10,
    ):
        self._http = httpx2.AsyncClient(verify=verify, timeout=timeout, http2=True)
        self.cache = TTLCache[str, str, float](maxsize=1, ttl=PUBLIC_KEY_TTL)
        self.cache_lock = asyncio.Lock()
        self.client_id = client_id
        self.client_secret = client_secret
        self.realm = realm
        self.server_url = server_url

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """
        Close the underlying HTTP client. The client cannot be used afterwards.
        """
        await self._http.aclose()

    def _add_client_secret(self, data: dict[str, str]) -> dict[str, str]:
        if self.client_secret:
            data["client_secret"] = self.client_secret
        return data

    async def password_grant(
        self, username: str, password: str, totp: str | None = None, scope: list[str] | None = None
    ) -> TokenResponse:
        """
        Do a password grant request to obtain an access/refresh token.

        Args:
            username (str): User username.
            password (str): User password.
            totp (str, optional): Time-based OTP. Defaults to None.
            scope (list[str], optional): List of scopes to request. `openid` is always added. Defaults to ['openid'].

        Returns:
            TokenResponse: Token model containing access token, refresh token, and other details.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_TOKEN.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": _scope_param(scope),
        }
        if totp:
            data["totp"] = totp
        data = self._add_client_secret(data)
        resp = await self._http.post(self.server_url + path, data=data)

        if resp.status_code != 200:
            raise_error(resp)

        resp_json = resp.json()
        return TokenResponse.model_validate(resp_json)

    async def device_code_grant(self, scope: list[str] | None = None) -> DeviceAuthResponse:
        """
        Get device authorization URL and device code.

        Args:
            scope (list[str], optional): List of scopes to request. `openid` is always added. Defaults to ['openid'].

        Returns:
            DeviceAuthResponse: Device authorization response containing device code, user code, and verification URI.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_AUTH_DEVICE.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "scope": _scope_param(scope),
        }
        data = self._add_client_secret(data)
        auth_resp = await self._http.post(self.server_url + path, data=data)
        if auth_resp.status_code != 200:
            raise_error(auth_resp)

        device_auth = DeviceAuthResponse.model_validate(auth_resp.json())
        return device_auth

    async def device_code_to_token(self, device_code: str, polling_interval: int) -> TokenResponse:
        """
        Exchange the device code for access and refresh tokens.

        Polls the token endpoint until the user approves or denies the request, or the device code expires.
        When Keycloak answers `slow_down`, the interval is increased by 5 seconds.

        Args:
            device_code (str): The device code obtained from the device code grant.
            polling_interval (int): The interval (in seconds) to poll for the token.

        Returns:
            TokenResponse: Token model containing access token, refresh token, and other details.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        data = {
            "client_id": self.client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        }
        data = self._add_client_secret(data)
        path = urls.URL_TOKEN.format(realm_name=self.realm)
        while True:
            await asyncio.sleep(polling_interval)
            token_resp = await self._http.post(self.server_url + path, data=data)
            if token_resp.status_code == 200:
                resp_json = token_resp.json()
                return TokenResponse.model_validate(resp_json)
            elif token_resp.status_code == 400:
                error_data: dict[str, str] = token_resp.json()
                if error_data.get("error") == "authorization_pending":
                    continue
                if error_data.get("error") == "slow_down":
                    polling_interval += DEVICE_CODE_SLOW_DOWN
                    continue
            raise_error(token_resp)

    async def client_credentials_grant(self, scope: list[str] | None = None) -> TokenResponse:
        """
        Obtain an access token using client credentials grant.

        Args:
            scope (list[str], optional): List of scopes to request. `openid` is always added. Defaults to ['openid'].

        Returns:
            TokenResponse: Token model containing the access token and other details.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_TOKEN.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "grant_type": "client_credentials",
            "scope": _scope_param(scope),
        }
        data = self._add_client_secret(data)
        resp = await self._http.post(self.server_url + path, data=data)

        if resp.status_code != 200:
            raise_error(resp)

        resp_json = resp.json()
        return TokenResponse.model_validate(resp_json)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh an access token.

        Args:
            refresh_token (str): Refresh token.

        Returns:
            TokenResponse: Token model.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_TOKEN.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        data = self._add_client_secret(data)
        resp = await self._http.post(self.server_url + path, data=data)

        if resp.status_code != 200:
            raise_error(resp)

        resp_json = resp.json()
        return TokenResponse.model_validate(resp_json)

    async def well_known(self) -> WellKnown:
        """
        Get the well known configuration.

        Returns:
            WellKnown: Well known configuration.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_WELL_KNOWN.format(realm_name=self.realm)
        resp = await self._http.get(self.server_url + path)

        if resp.status_code != 200:
            raise_error(resp)
        return WellKnown.model_validate(resp.json())

    async def introspect(
        self, token: str, token_type: TOKEN_TYPE_HINT = "access_token"
    ) -> Introspect | IntrospectRPT | IntrospectInactive:
        """
        Introspect a token.

        Args:
            token (str): Token to introspect.
            token_type (TOKEN_TYPE_HINT, optional): Token type hint. Defaults to "access_token".

        Returns:
            Introspect | IntrospectRPT | IntrospectInactive: Introspect response model.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_INTROSPECT.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "token": token,
            "token_type_hint": token_type,
        }
        data = self._add_client_secret(data)

        if token_type == "requesting_party_token":
            headers = gen_auth_header(token)
            resp = await self._http.post(self.server_url + path, data=data, headers=headers)
        else:
            resp = await self._http.post(self.server_url + path, data=data)

        if resp.status_code != 200:
            raise_error(resp)

        resp_json: dict[str, Any] = resp.json()
        if resp_json.get("active") is False:
            return IntrospectInactive.model_validate(resp_json)
        if token_type == "requesting_party_token":
            return IntrospectRPT.model_validate(resp_json)
        return Introspect.model_validate(resp_json)

    async def userinfo(self, access_token: str) -> UserInfo:
        """
        Obtain user information from the userinfo endpoint.

        Args:
            access_token (str): Access token.

        Returns:
            UserInfo: User information model.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        path = urls.URL_USERINFO.format(realm_name=self.realm)
        headers = gen_auth_header(access_token)
        resp = await self._http.get(self.server_url + path, headers=headers)

        if resp.status_code != 200:
            raise_error(resp)
        return UserInfo.model_validate(resp.json())

    async def public_key(self) -> str:
        """
        Get the realm public key.

        Returns:
            str: Public key in PEM format.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        if "key" in self.cache:
            return self.cache["key"]

        async with self.cache_lock:
            if "key" in self.cache:
                return self.cache["key"]

            path = urls.URL_REALM.format(realm_name=self.realm)
            resp = await self._http.get(self.server_url + path)

            if resp.status_code != 200:
                raise_error(resp)
            realm = Realm.model_validate(resp.json())
            realm.public_key = "-----BEGIN PUBLIC KEY-----\n" + realm.public_key + "\n-----END PUBLIC KEY-----"
            self.cache["key"] = realm.public_key
            return realm.public_key

    async def decode_token(self, token: str, options: Options | None = None) -> DecodedToken:
        """
        Verify and decode an access or ID token.

        The signature (RS256) is checked against the realm public key, and `aud` must contain `client_id`.
        Refresh tokens cannot be decoded this way; use `introspect()` for them.

        Args:
            token (str): Token to decode.
            options (Options, optional): PyJWT decode options, e.g. `{"verify_aud": False}`. Defaults to None.

        Returns:
            DecodedToken: Decoded token data.

        Raises:
            jwt.PyJWTError: If the token is invalid, expired, or has the wrong audience.
            KeycloakError: If the public key cannot be fetched.
        """
        public_key = await self.public_key()
        decoded_token = jwt.decode(token, public_key, audience=self.client_id, algorithms=["RS256"], options=options)
        return DecodedToken.model_validate(decoded_token)

    async def logout(self, refresh_token: str) -> None:
        """
        Logout the user.

        Args:
            refresh_token (str): Refresh token.

        Raises:
            KeycloakError: If the response status code is not 204.
        """

        path = urls.URL_LOGOUT.format(realm_name=self.realm)
        data = {
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        data = self._add_client_secret(data)
        resp = await self._http.post(self.server_url + path, data=data)
        if resp.status_code != 204:
            raise_error(resp)

    async def uma_permissions(self, access_token: str, permissions: list[str] | None = None) -> list[Permission]:
        """
        Obtain UMA permissions for the access token, optionally requesting specific permissions.

        For more information see:
        https://www.keycloak.org/docs/latest/authorization_services/#_service_obtaining_permissions

        Args:
            access_token (str): Access token to obtain permissions for.
            permissions (list[str], optional): Permissions to request, in the format of resource#scope.
                Defaults to None, which requests all permissions.

        Returns:
            list[Permission]: Granted permissions.

        Raises:
            ValueError: If a permission is not in the format of resource#scope.
            KeycloakError: If the response status code is not 200, e.g. `access_denied`.
        """

        data: dict[str, str | list[str]] = {
            "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
            "response_mode": "permissions",
            "audience": self.client_id,
        }
        if permissions:
            check_permission_format(permissions)
            data["permission"] = permissions
        headers = gen_auth_header(access_token)

        path = urls.URL_TOKEN.format(realm_name=self.realm)
        resp = await self._http.post(self.server_url + path, data=data, headers=headers)

        if resp.status_code != 200:
            raise_error(resp)

        return [Permission.model_validate(p) for p in resp.json()]

    async def has_permissions(self, access_token: str, permissions: list[str]) -> AuthResult:
        """
        Check if the access token has the required permissions.

        Args:
            access_token (str): Access token.
            permissions (list[str]): List of permissions to check, in the format of resource#scope.

        Returns:
            AuthResult: Authorization result model.

        Raises:
            ValueError: If a permission is not in the format of resource#scope.
            KeycloakError: If Keycloak returns an error other than `access_denied` or `invalid_grant`.
        """
        try:
            has_permissions = await self.uma_permissions(access_token, permissions)
        except KeycloakError as e:
            if e.error == "access_denied":
                return AuthResult(is_logged_in=True, is_authorized=False, missing_permissions=permissions)
            if e.error == "invalid_grant":
                return AuthResult(is_logged_in=False, is_authorized=False, missing_permissions=permissions)
            raise

        missing_permissions: list[str] = []
        for permission in permissions:
            resource, scope = permission.split("#")
            for p in has_permissions:
                if p.scopes is None:
                    continue
                if p.rsname == resource and scope in p.scopes:
                    break
            else:
                missing_permissions.append(permission)

        is_authorized = len(missing_permissions) == 0
        return AuthResult(is_logged_in=True, is_authorized=is_authorized, missing_permissions=missing_permissions)
