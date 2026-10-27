import logging
import time
from types import TracebackType
from typing import Self

import httpx2

from .. import urls
from ..exceptions import KeycloakError
from ..models.admin.authz import (
    AuthZPermission,
    AuthZPermissionResource,
    AuthZPolicy,
    AuthZPolicyUser,
    AuthZResource,
    CreateAuthZPermissionResource,
    CreateAuthZPolicyUser,
    CreateAuthZResource,
    QueryAuthZPermission,
    QueryAuthZPolicy,
    QueryAuthZResource,
    UpdateAuthZResource,
)
from ..models.admin.client import Client, QueryClient
from ..models.admin.user import CreateUser, QueryUser, UpdateUser, User, UserConsent
from ..models.openid import DecodedToken, TokenResponse
from ..utils import gen_auth_header, raise_error
from .openid import AsyncKeycloakOpenID

logger = logging.getLogger(__name__)


class AsyncKeycloakAdmin:
    """
    Keycloak Admin client with async httpx2.

    Args:
        server_url: Keycloak server URL
        target_realm: Name of the realm to be operated on
        admin_username: Keycloak admin username
        admin_password: Keycloak admin password
        totp: Time-based OTP for admin login. Defaults to None
        admin_realm: Realm the admin user logs in to. Defaults to "master"
        client_id: Client ID for admin login. Defaults to "admin-cli"
        client_secret: Client secret for admin login. Defaults to None
        verify: Whether to verify SSL certificate. Defaults to True
        timeout: Request timeout in seconds. Defaults to 10 seconds
    """

    TOKEN_REFRESH_THRESHOLD = 0.8

    def __init__(
        self,
        server_url: str,
        target_realm: str,
        admin_username: str,
        admin_password: str,
        totp: str | None = None,
        admin_realm: str = "master",
        client_id: str = "admin-cli",
        client_secret: str | None = None,
        verify: bool = True,
        timeout: int = 10,
    ):
        self.server_url = server_url
        self.target_realm = target_realm
        self.admin_realm = admin_realm
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.totp = totp
        self.client_id = client_id
        self.client_secret = client_secret

        self._http = httpx2.AsyncClient(verify=verify, timeout=timeout, http2=True)
        self._openid = AsyncKeycloakOpenID(
            server_url=server_url,
            realm=admin_realm,
            client_id=client_id,
            client_secret=client_secret,
            verify=verify,
            timeout=timeout,
        )  # underlying OpenID client for admin login
        self._token: TokenResponse | None = None
        self._decoded_access_token: DecodedToken | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._token:
                await self.logout()
        except (KeycloakError, httpx2.HTTPError) as e:
            # don't let a failed logout replace the exception raised in the `async with` body
            logger.warning("Failed to logout admin on exit: %r", e)
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        """
        Close the underlying HTTP clients. The client cannot be used afterwards.
        """
        try:
            await self._http.aclose()
        finally:
            await self._openid.aclose()

    async def _get_token(self) -> TokenResponse:
        """
        Login as admin and get the token.

        Returns:
            TokenResponse: Token model.

        Raises:
            KeycloakError: If the response status code is not 200.
        """
        token = await self._openid.password_grant(
            self.admin_username,
            self.admin_password,
            self.totp,
            scope=["openid", "offline_access"],
        )
        return token

    async def _refresh_if_needed(self) -> str:
        """
        Log in, or refresh the token once `TOKEN_REFRESH_THRESHOLD` of its lifetime has passed,
        and return the access token.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            str: Access token.
        """
        if not self._token:
            token = await self._get_token()
            self._token = token
        else:
            token = self._token

        if token.refresh_token is None:
            logger.warning("No refresh token available, skipping refresh check.")
            return token.access_token

        if not self._decoded_access_token:
            decoded_access_token = await self._openid.decode_token(token.access_token, {"verify_aud": False})
            self._decoded_access_token = decoded_access_token
        else:
            decoded_access_token = self._decoded_access_token

        if not decoded_access_token.exp:
            logger.warning("Access token does not have an expiration time, skipping refresh check.")
            return token.access_token

        token_lifetime = decoded_access_token.exp - decoded_access_token.iat
        refresh_time = decoded_access_token.iat + int(token_lifetime * self.TOKEN_REFRESH_THRESHOLD)

        if time.time() > refresh_time:
            try:
                token = await self._openid.refresh_token(token.refresh_token)
            except KeycloakError as e:
                if e.error == "invalid_grant":
                    # if the refresh token is invalid, login again
                    token = await self._get_token()
                else:
                    raise
            self._token = token
            self._decoded_access_token = None

        return token.access_token

    async def logout(self) -> None:
        """
        Logout admin and revoke the token.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        if self._token and self._token.refresh_token:
            await self._openid.logout(self._token.refresh_token)
            self._token = None
            self._decoded_access_token = None

    async def get_users(self, query: QueryUser | None = None) -> list[User]:
        """
        Get all users in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmusers

        Args:
            query (QueryUser | None): Query parameters. Defaults to None.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[User]: List of User models.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USERS.format(realm_name=self.target_realm)
        params = query.model_dump(exclude_none=True) if query else None
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, params=params, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [User.model_validate(user) for user in resp.json()]

    async def create_user(self, user_new: CreateUser) -> None:
        """
        Create a new user in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_post_adminrealmsrealmusers

        Args:
            user_new (CreateUser): Data model representing the new user.

        Raises:
            KeycloakError: If the response status code is not 201.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USERS.format(realm_name=self.target_realm)
        data = user_new.model_dump(exclude_none=True)
        headers = gen_auth_header(access_token)

        resp = await self._http.post(self.server_url + path, json=data, headers=headers)
        if resp.status_code != 201:
            raise_error(resp)

    async def update_user(self, user_id: str, user_mod: UpdateUser) -> None:
        """
        Update an existing user in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_put_adminrealmsrealmusersuser_id

        Args:
            user_id (str): User ID to be updated.
            user_mod (UpdateUser): Data model representing the updates.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USER.format(realm_name=self.target_realm, user_id=user_id)
        data = user_mod.model_dump(exclude_none=True)
        headers = gen_auth_header(access_token)

        resp = await self._http.put(self.server_url + path, json=data, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)

    async def delete_user(self, user_id: str) -> None:
        """
        Delete a user in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_delete_adminrealmsrealmusersuser_id

        Args:
            user_id (str): User ID to be deleted.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USER.format(realm_name=self.target_realm, user_id=user_id)
        headers = gen_auth_header(access_token)

        resp = await self._http.delete(self.server_url + path, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)

    async def get_user_consents(self, user_id: str) -> list[UserConsent]:
        """
        Get the consents a user has granted to clients in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmusersuser_idconsents

        Args:
            user_id (str): User ID.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[UserConsent]: List of UserConsent models.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USER_CONSENTS.format(realm_name=self.target_realm, user_id=user_id)
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [UserConsent.model_validate(consent) for consent in resp.json()]

    async def revoke_user_consent(self, user_id: str, client_id: str) -> None:
        """
        Revoke a user's consent to a client, together with the user's offline tokens for that client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_delete_adminrealmsrealmusersuser_idconsentsclient

        Args:
            user_id (str): User ID.
            client_id (str): Client ID (not the client UUID) to revoke the consent for.

        Raises:
            KeycloakError: If the response status code is not 204, e.g. 404 when there is no such consent.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_USER_CONSENT.format(realm_name=self.target_realm, user_id=user_id, client_id=client_id)
        headers = gen_auth_header(access_token)

        resp = await self._http.delete(self.server_url + path, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)

    async def get_clients(self, query: QueryClient | None = None) -> list[Client]:
        """
        Get all clients in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmclients

        Args:
            query (QueryClient | None): Query parameters. Defaults to None.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[Client]: List of Client models.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENTS.format(realm_name=self.target_realm)
        params = query.model_dump(exclude_none=True) if query else None
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, params=params, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [Client.model_validate(client) for client in resp.json()]

    async def get_client_authz_resources(
        self, client_uuid: str, query: QueryAuthZResource | None = None
    ) -> list[AuthZResource]:
        """
        Get all authorization resources from a client in the target realm.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmclientsclient_uuidauthzresource_serverresource

        Args:
            client_uuid (str): Client UUID.
            query (QueryAuthZResource | None): Query parameters. Defaults to None.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[AuthZResource]: List of AuthZResource models representing the resources.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_RESOURCES.format(realm_name=self.target_realm, client_uuid=client_uuid)
        params = query.model_dump(exclude_none=True) if query else None
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, params=params, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [AuthZResource.model_validate(resource) for resource in resp.json()]

    async def create_client_authz_resource(self, client_uuid: str, resource_new: CreateAuthZResource) -> AuthZResource:
        """
        Create a new authorization resource for a client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_post_adminrealmsrealmclientsclient_uuidauthzresource_serverresource

        Args:
            client_uuid (str): Client UUID.
            resource_new (CreateAuthZResource): Data model representing the new resource.

        Raises:
            KeycloakError: If the response status code is not 201.

        Returns:
            AuthZResource: Data model for the created resource.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_RESOURCES.format(realm_name=self.target_realm, client_uuid=client_uuid)
        headers = gen_auth_header(access_token)

        resp = await self._http.post(
            self.server_url + path, json=resource_new.model_dump(exclude_none=True), headers=headers
        )
        if resp.status_code != 201:
            raise_error(resp)

        return AuthZResource.model_validate(resp.json())

    async def update_client_authz_resource(
        self, client_uuid: str, resource_id: str, resource_mod: UpdateAuthZResource
    ) -> None:
        """
        Update an authorization resource in a client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_put_adminrealmsrealmclientsclient_uuidauthzresource_serverresourceresource_id

        Args:
            client_uuid (str): Client UUID.
            resource_id (str): Resource ID to be updated.
            resource_mod (UpdateAuthZResource): Data model representing the updates.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_RESOURCE.format(
            realm_name=self.target_realm, client_uuid=client_uuid, resource_id=resource_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.put(
            self.server_url + path, json=resource_mod.model_dump(exclude_none=True), headers=headers
        )
        if resp.status_code != 204:
            raise_error(resp)

    async def delete_client_authz_resource(self, client_uuid: str, resource_id: str) -> None:
        """
        Delete an authorization resource from a client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_delete_adminrealmsrealmclientsclient_uuidauthzresource_serverresourceresource_id

        Args:
            client_uuid (str): Client UUID.
            resource_id (str): Resource ID to be deleted.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_RESOURCE.format(
            realm_name=self.target_realm, client_uuid=client_uuid, resource_id=resource_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.delete(self.server_url + path, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)

    async def get_client_authz_policies(
        self, client_uuid: str, query: QueryAuthZPolicy | None = None
    ) -> list[AuthZPolicy]:
        """
        Get all authorization policies from a client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmclientsclient_uuidauthzresource_serverpolicy

        Args:
            client_uuid (str): Client UUID.
            query (QueryAuthZPolicy | None): Query parameters. Defaults to None.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[AuthZPolicy]: List of AuthZPolicy models.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_POLICIES.format(realm_name=self.target_realm, client_uuid=client_uuid)
        params = {"permission": "false"}  # Only get policies, without it permissions will also returned
        if query:
            params.update(query.model_dump(exclude_none=True))
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, params=params, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [AuthZPolicy.model_validate(policy) for policy in resp.json()]

    async def get_client_authz_policy_user(self, client_uuid: str, policy_id: str) -> AuthZPolicyUser:
        """
        Get a user policy from a client.

        Args:
            client_uuid (str): Client UUID.
            policy_id (str): Policy ID to be retrieved.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            AuthZPolicyUser: Data model for the policy.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_POLICY_USER.format(
            realm_name=self.target_realm, client_uuid=client_uuid, policy_id=policy_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return AuthZPolicyUser.model_validate(resp.json())

    async def create_client_authz_policy_user(
        self, client_uuid: str, policy_new: CreateAuthZPolicyUser
    ) -> AuthZPolicyUser:
        """
        Create a new user policy for a client.

        Args:
            client_uuid (str): Client UUID.
            policy_new (CreateAuthZPolicyUser): Data model representing the new user policy.

        Raises:
            KeycloakError: If the response status code is not 201.

        Returns:
            AuthZPolicyUser: Data model for the policy.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_POLICIES_USER.format(realm_name=self.target_realm, client_uuid=client_uuid)
        headers = gen_auth_header(access_token)

        resp = await self._http.post(
            self.server_url + path, json=policy_new.model_dump(exclude_none=True), headers=headers
        )
        if resp.status_code != 201:
            raise_error(resp)

        return AuthZPolicyUser.model_validate(resp.json())

    async def update_client_authz_policy_user(
        self, client_uuid: str, policy_id: str, policy_mod: AuthZPolicyUser
    ) -> None:
        """
        Update a user policy for a client.

        Args:
            client_uuid (str): Client UUID.
            policy_id (str): Policy ID to be updated.
            policy_mod (AuthZPolicyUser): The full policy with the updates applied, e.g. from
                `get_client_authz_policy_user()`.

        Raises:
            KeycloakError: If the response status code is not 201 (Keycloak answers 201 to this PUT).
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_POLICY_USER.format(
            realm_name=self.target_realm, client_uuid=client_uuid, policy_id=policy_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.put(
            self.server_url + path, json=policy_mod.model_dump(exclude_none=True), headers=headers
        )
        if resp.status_code != 201:
            raise_error(resp)

    async def delete_client_authz_policy_user(self, client_uuid: str, policy_id: str) -> None:
        """
        Delete a user policy from a client.

        Args:
            client_uuid (str): Client UUID.
            policy_id (str): Policy ID to be deleted.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_POLICY_USER.format(
            realm_name=self.target_realm, client_uuid=client_uuid, policy_id=policy_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.delete(self.server_url + path, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)

    async def get_client_authz_permissions(
        self, client_uuid: str, query: QueryAuthZPermission | None = None
    ) -> list[AuthZPermission]:
        """
        Get all permissions from a client.

        For more information, visit:
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_get_adminrealmsrealmclientsclient_uuidauthzresource_serverpermission

        Args:
            client_uuid (str): Client UUID.
            query (QueryAuthZPermission | None): Query parameters. Defaults to None.

        Raises:
            KeycloakError: If the response status code is not 200.

        Returns:
            list[AuthZPermission]: List of AuthZPermission models.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS.format(realm_name=self.target_realm, client_uuid=client_uuid)
        params = query.model_dump(exclude_none=True) if query else None
        headers = gen_auth_header(access_token)

        resp = await self._http.get(self.server_url + path, params=params, headers=headers)
        if resp.status_code != 200:
            raise_error(resp)

        return [AuthZPermission.model_validate(permission) for permission in resp.json()]

    async def create_client_authz_permission_resource(
        self, client_uuid: str, permission_new: CreateAuthZPermissionResource
    ) -> AuthZPermissionResource:
        """
        Create a new resource based permission for a client.

        Args:
            client_uuid (str): Client UUID.
            permission_new (CreateAuthZPermissionResource): Data model representing the new permission.

        Raises:
            KeycloakError: If the response status code is not 201.

        Returns:
            AuthZPermissionResource: Data model for the permission.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS_RESOURCE.format(
            realm_name=self.target_realm, client_uuid=client_uuid
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.post(
            self.server_url + path, json=permission_new.model_dump(exclude_none=True), headers=headers
        )
        if resp.status_code != 201:
            raise_error(resp)

        return AuthZPermissionResource.model_validate(resp.json())

    async def delete_client_authz_permission_resource(self, client_uuid: str, permission_id: str) -> None:
        """
        Delete a resource based permission from a client.

        Args:
            client_uuid (str): Client UUID.
            permission_id (str): Permission ID to be deleted.

        Raises:
            KeycloakError: If the response status code is not 204.
        """
        access_token = await self._refresh_if_needed()

        path = urls.URL_ADMIN_CLIENT_AUTHZ_PERMISSION_RESOURCE.format(
            realm_name=self.target_realm, client_uuid=client_uuid, permission_id=permission_id
        )
        headers = gen_auth_header(access_token)

        resp = await self._http.delete(self.server_url + path, headers=headers)
        if resp.status_code != 204:
            raise_error(resp)
