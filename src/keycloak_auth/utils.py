import re
from typing import NoReturn

import httpx2
from pydantic import BaseModel

from .exceptions import KeycloakError


class _ErrorBody(BaseModel):
    error: str | None = None
    """OAuth error code, or the message on admin API errors, e.g. 404 `User not found`."""

    error_description: str | None = None

    errorMessage: str | None = None
    """Message on admin API errors, e.g. 409 `User exists with same username`."""


def raise_error(response: httpx2.Response) -> NoReturn:
    status_code = response.status_code
    status = f"{status_code} {response.reason_phrase}"
    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("application/json"):
        try:
            body = _ErrorBody.model_validate(response.json())
        except ValueError:  # invalid JSON, or not a JSON object (pydantic's ValidationError is a ValueError)
            body = _ErrorBody()
        if body.error and body.error_description:
            raise KeycloakError(body.error, body.error_description, status_code)
        message = body.errorMessage or body.error
        # skip generic messages like "HTTP 401 Unauthorized", which only repeat the status
        if message and not message.startswith("HTTP "):
            raise KeycloakError("status_error", f"{status}: {message}", status_code)
    elif content_type.startswith("text/plain"):
        try:
            msg = response.headers["WWW-Authenticate"]
            match_error = re.search(r'error="(.+?)"', msg)
            match_description = re.search(r'error_description="(.+?)"', msg)
            error: str | None = match_error.group(1) if match_error else None
            description: str | None = match_description.group(1) if match_description else None
            if error and description:
                raise KeycloakError(error, description, status_code)
        except (KeyError, AttributeError):
            pass
    raise KeycloakError("status_error", status, status_code)


def check_permission_format(permissions: list[str]) -> None:
    for permission in permissions:
        if "#" not in permission or permission.count("#") > 1:
            raise ValueError("Permission must be in the format of resource#scope")


def gen_auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}
