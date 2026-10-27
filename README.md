# keycloak-auth

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Typed, async-first Python client for Keycloak's OpenID Connect and Admin REST APIs, maintained by Agnos.

- OpenID Connect flows: password, device code, client credentials, refresh, logout
- Token checks: JWT decoding against the realm public key (cached for one hour), introspection, userinfo
- Authorization: UMA permissions and `resource#scope` permission checks
- Admin API: users, clients, and client authorization resources, policies and permissions
- Every response is validated into a Pydantic v2 model, and the package is fully typed (pyright strict)

Requires Python 3.13 or later. Uses `httpx2` with HTTP/2.

> **Status:** beta. The API may still change in minor releases before 1.0. Breaking changes are listed in the [changelog](CHANGELOG.md).

## Installation

The package is published to the Agnos package index at `https://pkgs.agnos.one/simple/`, not to PyPI.

With uv, add the index to your `pyproject.toml` and pin the package to it:

```toml
[[tool.uv.index]]
name = "agnos"
url = "https://pkgs.agnos.one/simple/"
explicit = true

[tool.uv.sources]
keycloak-auth = { index = "agnos" }
```

```bash
uv add keycloak-auth
```

Because the index is `explicit`, uv uses it only for `keycloak-auth`, and installs everything else from PyPI.

We don't recommend pip. It can't limit a package to one index, so with `--extra-index-url https://pkgs.agnos.one/simple/` a package of the same name on PyPI could be installed instead (dependency confusion).

If you need pip, install the wheel by its URL. Replace `<version>` with a release listed at https://pkgs.agnos.one/simple/keycloak-auth/. The dependencies come from PyPI:

```bash
pip install "https://pkgs.agnos.one/simple/keycloak-auth/keycloak_auth-<version>-py3-none-any.whl"
```

## Quick start

### OpenID Connect

```python
import asyncio

from keycloak_auth import AsyncKeycloakOpenID


async def main() -> None:
    async with AsyncKeycloakOpenID(
        server_url="https://auth.example.com",
        realm="my-realm",
        client_id="my-client",
        client_secret="...",  # omit for public clients
    ) as openid:
        token = await openid.password_grant("alice", "secret")

        # verify the signature and claims locally
        claims = await openid.decode_token(token.access_token)
        print(claims.sub, claims.preferred_username)

        # ask Keycloak whether the token is still active
        result = await openid.introspect(token.access_token)
        print(result.active)

        # check permissions in the form "resource#scope"
        auth = await openid.has_permissions(token.access_token, ["orders#read", "orders#write"])
        if not auth.is_authorized:
            print("missing:", auth.missing_permissions)

        if token.refresh_token:
            token = await openid.refresh_token(token.refresh_token)

        if token.refresh_token:
            await openid.logout(token.refresh_token)


asyncio.run(main())
```

Other flows:

- `device_code_grant()` then `device_code_to_token(device_code, polling_interval)`, which polls until the user approves
- `client_credentials_grant()` for service accounts
- `userinfo(access_token)`, `well_known()`, `public_key()`, `uma_permissions(access_token)`

`KeycloakOpenID` is a minimal synchronous client and currently only implements `well_known()`.

### Admin API

```python
from keycloak_auth import AsyncKeycloakAdmin
from keycloak_auth.models.admin.client import QueryClient
from keycloak_auth.models.admin.user import CreateUser, QueryUser, UpdateUser


async def main() -> None:
    async with AsyncKeycloakAdmin(
        server_url="https://auth.example.com",
        target_realm="my-realm",
        admin_username="admin",
        admin_password="...",
    ) as admin:
        await admin.create_user(CreateUser(username="bob", email="bob@example.com"))

        users = await admin.get_users(QueryUser(username="bob", exact=True))
        await admin.update_user(users[0].id, UpdateUser(firstName="Bob"))

        clients = await admin.get_clients(QueryClient(clientId="my-client"))
        resources = await admin.get_client_authz_resources(clients[0].id)
        print([r.name for r in resources])

        await admin.delete_user(users[0].id)
```

The admin client logs in on its first request (by default as a user of the `master` realm through `admin-cli`) and refreshes its token once 80% of the token's lifetime has passed. Leaving `async with` logs out and closes the HTTP connections. Without `async with`, call `logout()` and `aclose()` yourself.

`UpdateUser` only sends the fields you set, so fields left as `None` keep their current value in Keycloak.

## Errors

Error responses from Keycloak raise `keycloak_auth.exceptions.KeycloakError`, with these attributes:

- `error`: the OAuth error code, e.g. `invalid_grant`, or `status_error` for other errors, such as those from the Admin API
- `error_description`: Keycloak's description, e.g. `409 Conflict: User exists with same username`
- `status_code`: the HTTP status code

```python
from keycloak_auth.exceptions import KeycloakError

try:
    await admin.create_user(CreateUser(username="bob"))
except KeycloakError as e:
    if e.status_code == 409:
        print("already exists:", e.error_description)
    else:
        raise
```

## Keycloak setup notes

Recent Keycloak versions report an access token as active to `introspect()` only when the introspecting client is in the token's `aud` claim. `decode_token()` also checks that `aud` contains `client_id`. Keycloak doesn't add the client you log in through to the access token's `aud`, unless the user holds roles on that client. To add it for every user, give the client an Audience mapper: Clients → your client → Client scopes → `<client>-dedicated` → Add mapper → By configuration → Audience, set "Included Client Audience" to the client, and enable "Add to access token".

## Development

```bash
uv sync --frozen     # install dependencies
uv run pytest        # run tests (with coverage)
uv run ruff format   # format
uv run ruff check    # lint
uv run pyright       # type check (strict)
uv build             # build sdist and wheel
```

The tests are integration tests that run against a real Keycloak server and create, update and delete data in the realm. Each test removes what it creates, even when an assertion fails. Use a dedicated test realm, never a production one. You can run Keycloak locally with Docker:

```bash
docker run -p 8080:8080 -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak start-dev
```

Then create the test realm described below, and set `KEYCLOAK_SERVER_URL=http://localhost:8080`.

Connection settings are read from `.env`:

```
KEYCLOAK_SERVER_URL=
KEYCLOAK_REALM=
KEYCLOAK_CLIENT_ID=
KEYCLOAK_CLIENT_SECRET=
KEYCLOAK_USERNAME=
KEYCLOAK_PASSWORD=
KEYCLOAK_ADMIN_USERNAME=
KEYCLOAK_ADMIN_PASSWORD=
```

The test realm needs:

- A confidential client `test-client` with direct access grants, service accounts, the OAuth 2.0 Device Authorization Grant and authorization enabled, and the Audience mapper described above, containing resources `resource-1` and `resource-2` (scopes `read-resource`, `write-resource`), a policy `policy-1` and a permission `permission-1`
- A test user (`KEYCLOAK_USERNAME`) granted `resource-1#read-resource` and `resource-2#write-resource`, and no other permissions, with no OTP or pending required actions, because the device flow test signs in through the login page. The test accepts the consent screen and revokes the consent afterwards
- A user named John Smith with email `john@example.com`
- At least two users in total

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, and [CHANGELOG.md](CHANGELOG.md) for release notes.

## Security

Please report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md). Do not open public issues for them.

## License

[MIT](LICENSE) © 2026 Agnos, Inc.
