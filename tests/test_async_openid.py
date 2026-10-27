import os

from keycloak_auth import AsyncKeycloakOpenID
from keycloak_auth.exceptions import KeycloakError


def get_client():
    return AsyncKeycloakOpenID(
        server_url=os.getenv("KEYCLOAK_SERVER_URL") or "http://localhost:8080",
        realm=os.getenv("KEYCLOAK_REALM") or "master",
        client_id=os.getenv("KEYCLOAK_CLIENT_ID") or "test-client",
        client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET") or "test-secret",
    )


async def test_public_key_caching():
    async with get_client() as client:
        client.cache.clear()

        public_key_1 = await client.public_key()
        assert public_key_1

        public_key_2 = await client.public_key()
        assert public_key_2 == public_key_1


async def test_context_manager():
    async with get_client() as client:
        assert await client.public_key()

    # the HTTP client is closed on exit
    try:
        await client.well_known()
        assert False, "request after exit should fail"
    except RuntimeError as e:
        assert "closed" in str(e)


async def test_openid_flow():
    username = os.getenv("KEYCLOAK_USERNAME") or "test-user"
    password = os.getenv("KEYCLOAK_PASSWORD") or "test-password"

    async with get_client() as client:
        token = await client.password_grant(username, password)

        try:
            assert token.access_token

            # test well known
            well_known = await client.well_known()
            assert well_known.issuer == f"{client.server_url}/realms/{client.realm}"

            # test userinfo
            user_info = await client.userinfo(token.access_token)
            assert user_info.preferred_username == username

            # test decode token
            decoded_token = await client.decode_token(token.access_token)
            assert decoded_token.exp is not None

            # test introspect
            checked_token = await client.introspect(token.access_token)
            assert checked_token.active is True
            assert checked_token.typ == "Bearer"

            assert token.refresh_token
            checked_token = await client.introspect(token.refresh_token, token_type="refresh_token")
            assert checked_token.active is True
            assert checked_token.typ == "Refresh"

            # test uma permissions
            permissions = await client.uma_permissions(token.access_token)
            assert len(permissions) == 2
            auth_result = await client.has_permissions(
                token.access_token,
                ["resource-1#read-resource", "resource-2#write-resource", "resource-3#read-resource"],
            )
            assert auth_result.is_logged_in
            assert auth_result.is_authorized is False
            assert len(auth_result.missing_permissions) == 1
            assert "resource-3#read-resource" in auth_result.missing_permissions

            # test refresh token
            token = await client.refresh_token(token.refresh_token)
            assert token.access_token
        finally:
            # test logout
            assert token.refresh_token
            await client.logout(token.refresh_token)

        checked_token = await client.introspect(token.refresh_token, token_type="refresh_token")
        assert checked_token.active is False

        # test invalid token
        try:
            await client.userinfo("fake_token")
            assert False, "userinfo with a fake token should fail"
        except KeycloakError as e:
            assert e.error == "invalid_token"


async def test_client_credentials_flow():
    async with get_client() as client:
        token = await client.client_credentials_grant()

        try:
            assert token.access_token

            # the token belongs to the client's service account user
            decoded_token = await client.decode_token(token.access_token)
            assert decoded_token.azp == client.client_id
            assert decoded_token.preferred_username == f"service-account-{client.client_id}"

            checked_token = await client.introspect(token.access_token)
            assert checked_token.active is True
        finally:
            # Keycloak only issues a refresh token here when "Use refresh tokens for client credentials grant" is on
            if token.refresh_token:
                await client.logout(token.refresh_token)
