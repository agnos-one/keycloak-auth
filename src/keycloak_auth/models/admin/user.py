from datetime import date

from pydantic import BaseModel, ConfigDict

from . import QueryPagination


class User(BaseModel):
    """A user returned by the admin API (`UserRepresentation`)."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    access: dict[str, bool]
    """What the calling admin may do with this user, e.g. `{"view": true, "manage": true}`."""

    attributes: dict[str, list[str]] | None = None
    """Custom user attributes. Each key maps to a list of values."""

    createdTimestamp: int
    """Creation time in epoch milliseconds."""

    disableableCredentialTypes: list[str] | None = None
    """Credential types configured for the user that can be disabled, e.g. `otp`. Omitted in brief representations."""

    email: str | None = None
    """Email address."""

    emailVerified: bool
    """Whether the email has been verified."""

    enabled: bool
    """Whether the user is enabled. Disabled users cannot log in."""

    firstName: str | None = None
    """First name."""

    groups: list[str] | None = None
    """Group paths the user belongs to, e.g. `/parent/child`. Not populated when listing users."""

    id: str
    """User ID."""

    lastName: str | None = None
    """Last name."""

    notBefore: int | None = None
    """
    Tokens issued to the user before this time (epoch seconds) are rejected. `0` means not set.
    Omitted in brief representations.
    """

    requiredActions: list[str] | None = None
    """
    Actions the user must complete at next login, e.g. `VERIFY_EMAIL`, `UPDATE_PASSWORD`.
    Omitted in brief representations.
    """

    totp: bool | None = None
    """Whether the user has OTP configured. Omitted in brief representations."""

    username: str
    """Username, unique within the realm."""


class UserConsent(BaseModel):
    """A client the user has granted access to on a consent screen (`UserConsentRepresentation`)."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    clientId: str
    """Client ID of the client the consent was granted to."""

    grantedClientScopes: list[str] | None = None
    """Names of the client scopes the user granted, e.g. `profile`, `email`."""

    createdDate: int | None = None
    """Creation time in epoch milliseconds."""

    lastUpdatedDate: int | None = None
    """Last update time in epoch milliseconds."""


class UserOptional(BaseModel):
    """Fields shared by user create and update requests. Fields left as `None` are not sent."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    attributes: dict[str, list[str]] | None = None
    """Custom user attributes. Each key maps to a list of values."""

    email: str | None = None
    """Email address."""

    emailVerified: bool | None = None
    """Whether the email has been verified."""

    firstName: str | None = None
    """First name."""

    groups: list[str] | None = None
    """Group paths to add the user to, e.g. `/parent/child`."""

    lastName: str | None = None
    """Last name."""

    requiredActions: list[str] | None = None
    """Actions the user must complete at next login, e.g. `VERIFY_EMAIL`, `UPDATE_PASSWORD`."""


class CreateUser(UserOptional):
    """Request body for creating a user."""

    enabled: bool = True
    """Whether the user is enabled. Disabled users cannot log in."""

    username: str
    """Username. Must be unique within the realm."""


class UpdateUser(UserOptional):
    """Request body for updating a user."""

    enabled: bool | None = None
    """Whether the user is enabled. Left unchanged when `None`."""


class QueryUserBase(BaseModel):
    """Base model for querying users."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    createdAfter: date | int | None = None
    """Only return users created on or after this date, or epoch milliseconds."""

    createdBefore: date | int | None = None
    """Only return users created on or before this date, or epoch milliseconds."""

    email: str | None = None
    """A string contained in email, or the complete email if param `exact` is true."""

    emailVerified: bool | None = None
    """Whether the email is verified."""

    enabled: bool | None = None
    """Whether the user is enabled."""

    exact: bool | None = None
    """Whether the params `lastName`, `firstName`, `email`, and `username` must match exactly."""

    firstName: str | None = None
    """A string contained in first name, or the complete first name if param `exact` is true."""

    idpAlias: str | None = None
    """The alias of an Identity Provider linked to the user."""

    idpUserId: str | None = None
    """The userId at an Identity Provider linked to the user."""

    lastName: str | None = None
    """A string contained in last name, or the complete last name if param `exact` is true."""

    q: str | None = None
    """Query to search for custom attributes, in the format 'key1:value1 key2:value2'."""

    search: str | None = None
    """
    String contained in username, first or last name, or email. Default search behavior is prefix-based
    (e.g. `foo` or `foo*`). Use `*foo*` for infix search and `"foo"` for exact search.
    """

    username: str | None = None
    """A string contained in username, or the complete username if param `exact` is true."""


class QueryUserCount(QueryUserBase):
    """Query parameters for counting users (`GET /users/count`)."""


class QueryUser(QueryPagination, QueryUserBase):
    """Query parameters for listing users (`GET /users`)."""

    briefRepresentation: bool | None = None
    """Whether brief representations are returned (default: false)."""
