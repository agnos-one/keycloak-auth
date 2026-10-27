class KeycloakError(Exception):
    """An error response from Keycloak, with its `error` code and `error_description`."""

    def __init__(self, error: str, error_description: str, status_code: int | None = None):
        super().__init__(error)

        self.error = error
        """OAuth error code, e.g. `invalid_grant`, or `status_error` for other errors."""

        self.error_description = error_description
        """Human-readable description, e.g. `409 Conflict: User exists with same username`."""

        self.status_code = status_code
        """HTTP status code of the response, e.g. 404 or 409."""

    def __str__(self) -> str:
        return f"[{self.error}] {self.error_description}"
