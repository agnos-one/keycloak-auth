# Contributing

Thanks for your interest in improving keycloak-auth. Bug reports, fixes and new Keycloak endpoints are all welcome.

## Reporting bugs and requesting features

Open an issue on [GitHub](https://github.com/agnos-one/keycloak-auth/issues). For bugs, include the library version, your Keycloak version, a minimal code sample and the full error. Never include real tokens, client secrets or passwords.

Security vulnerabilities should be reported privately, as described in [SECURITY.md](SECURITY.md).

## Development setup

You need Python 3.13 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
```

## Before opening a pull request

Run all of these and make sure they pass:

```bash
uv run ruff format   # format
uv run ruff check    # lint
uv run pyright       # type check (strict mode)
uv run pytest        # tests
```

Guidelines:

- Keep the code fully typed. Prefer real types over `Any`, casts or `# type: ignore`.
- Validate every Keycloak response with a Pydantic model in `src/keycloak_auth/models/`, and add endpoint URLs to `src/keycloak_auth/urls.py`.
- Document model fields with attribute docstrings, following the existing models.
- Add or update tests for the behaviour you change.
- Add an entry under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).

## Tests

The tests are integration tests against a real Keycloak server, and they create and delete data in the realm. Use a dedicated test realm, never a production one. The [README](README.md#development) lists the settings and the realm setup the tests expect. Tests that create data must remove it in a `finally` block, so a failing test leaves nothing behind.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
