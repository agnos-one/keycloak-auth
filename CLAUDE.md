# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --frozen

# Run all tests (coverage is on by default via pytest.ini)
uv run pytest

# Run a single test file
uv run pytest tests/test_async_openid.py

# Run a single test
uv run pytest tests/test_async_openid.py::test_function_name

# Build distribution
uv build

# Format code
uv run ruff format

# Lint
uv run ruff check

# Type check (strict mode)
uv run pyright
```

Requires Python >= 3.13 (`.python-version` pins 3.14). Ruff line length is 120.

### Tests

Tests are integration tests against a live Keycloak instance; there are no mocks. `pytest-dotenv` loads `.env` automatically (it is gitignored), with these variables: `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_USERNAME`, `KEYCLOAK_PASSWORD`, `KEYCLOAK_ADMIN_USERNAME`, `KEYCLOAK_ADMIN_PASSWORD`. `asyncio_mode = auto`, so async tests need no `@pytest.mark.asyncio` decorator.

## Architecture

This is a Keycloak API client library exposing three public classes from `src/keycloak_auth/__init__.py`:

- **`AsyncKeycloakOpenID`**: OpenID Connect flows (password grant, device code, client credentials, token refresh, introspection, userinfo, logout, UMA permissions, JWT decode). Holds no tokens itself; `async with` / `aclose()` closes its HTTP client.
- **`KeycloakOpenID`**: a minimal sync client. It currently implements only `well_known()` and is not a full mirror of the async client.
- **`AsyncKeycloakAdmin`**: Admin API for user CRUD, listing and revoking user consents, and client authorization management (resource CRUD, listing all policies plus CRUD for user policies, listing permissions plus create/delete for resource permissions). It logs in lazily, refreshes its own token once 80% of its lifetime has passed (`TOKEN_REFRESH_THRESHOLD`), and supports `async with` (logs out, then closes its HTTP clients on exit; `aclose()` closes them directly).

### Key design points

- Async-first (`httpx2`, the maintained fork of `httpx`, with HTTP/2)
- All API responses are validated through **Pydantic v2** models in `src/keycloak_auth/models/`
- JWT decoding uses **PyJWT** (RS256, audience = `client_id`) with its native `Options` type. The public key comes from the realm endpoint (`URL_REALM`), is wrapped in PEM headers, and is cached in a `cachetools.TTLCache` for 1 hour (`PUBLIC_KEY_TTL`), guarded by an `asyncio.Lock`
- `AsyncKeycloakAdmin` internally holds an `AsyncKeycloakOpenID` instance (against `admin_realm`, default `master`, client `admin-cli`) for its own auth, and operates on `target_realm`
- URL templates for all Keycloak endpoints live in `urls.py`
- HTTP errors are normalized to `KeycloakError` (defined in `exceptions.py`) via `utils.raise_error`, which parses OAuth errors (`error` + `error_description`) and admin API errors (`errorMessage`, or `error` alone) and sets `status_code`
- Pyright runs in strict mode. Keep code fully typed rather than suppressing errors.

### Module layout

```
clients/openid.py   — OpenID clients (AsyncKeycloakOpenID, minimal sync KeycloakOpenID)
clients/admin.py    — Admin client (async only)
models/openid.py    — TokenResponse, UserInfo, DecodedToken, Introspect, Permission, …
models/admin/       — user.py (User, UserConsent, CreateUser, UpdateUser, QueryUser), client.py (Client, QueryClient),
                      authz.py (AuthZ* models);
                      __init__.py defines QueryPagination (first/max), the base of the paginated Query* models
                      (QueryUser, QueryAuthZResource, QueryAuthZPolicy, QueryAuthZPermission; not QueryUserCount)
urls.py             — API endpoint URL templates
utils.py            — raise_error, check_permission_format, gen_auth_header
exceptions.py       — KeycloakError
```

`scripts/build_index.py` and `.github/workflows/release.yml` publish releases to the static PEP 503 index at `https://pkgs.agnos.one/simple/`, not PyPI. Pushing a `vX.Y.Z` tag starts a release.

### Gotchas

- AuthZ resource models: `type` is optional (on `AuthZResourceOptional`), and `AuthZResource.id` maps from Keycloak's `_id` alias.
