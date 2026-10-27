import os

from keycloak_auth import KeycloakOpenID

client = KeycloakOpenID(
    server_url=os.getenv("KEYCLOAK_SERVER_URL") or "http://localhost:8080",
    realm=os.getenv("KEYCLOAK_REALM") or "master",
    client_id=os.getenv("KEYCLOAK_CLIENT_ID") or "test-client",
    client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET") or "test-secret",
)


def test_openid_flow():
    # test well known
    well_known = client.well_known()
    assert well_known.issuer == f"{client.server_url}/realms/{client.realm}"
