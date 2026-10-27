# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

First public release, under the MIT License.

### Added

- `AsyncKeycloakOpenID`: password, device code and client credentials grants, token refresh, logout, introspection, userinfo, `well_known()` and `public_key()`.
- `AsyncKeycloakOpenID.decode_token()`: verifies JWTs against the realm public key, which is cached for one hour.
- UMA permissions and `resource#scope` permission checks with `uma_permissions()` and `has_permissions()`.
- `AsyncKeycloakAdmin`: user CRUD, user consents, client listing, and client authorization resources, policies and permissions. It logs in lazily and refreshes its own token.
- `async with` support and `aclose()` on both async clients.
- `KeycloakError` for every error response, with the error code, Keycloak's message and the HTTP status code.
- `KeycloakOpenID`: a minimal synchronous client with `well_known()`.
- Pydantic v2 models for every response, with field docstrings exposed as field descriptions.
- Full type annotations, checked with pyright in strict mode, and a `py.typed` marker.

[Unreleased]: https://github.com/agnos-one/keycloak-auth/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/agnos-one/keycloak-auth/releases/tag/v0.1.0
