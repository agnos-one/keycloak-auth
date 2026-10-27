from pydantic import BaseModel, ConfigDict

from . import QueryPagination


class ProtocolMapper(BaseModel):
    """A protocol mapper attached to a client (`ProtocolMapperRepresentation`)."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    id: str | None = None
    """Protocol mapper ID."""

    name: str
    """Display name of the mapper."""

    protocol: str
    """Protocol the mapper applies to, e.g. `openid-connect` or `saml`."""

    protocolMapper: str
    """Mapper type, e.g. `oidc-usermodel-attribute-mapper`."""

    config: dict[str, str] | None = None
    """Mapper configuration."""


class Client(BaseModel):
    """
    A client returned by the admin API (`ClientRepresentation`).

    Only `id` and `clientId` are always present. Other fields are omitted when unset, depending on the client's
    protocol and settings.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    id: str
    """Client UUID, used in admin API paths."""

    clientId: str
    """Client ID used in OpenID Connect and SAML requests."""

    name: str | None = None
    """Display name."""

    description: str | None = None
    """Description."""

    type: str | None = None
    """Client type."""

    rootUrl: str | None = None
    """Root URL prepended to relative URLs."""

    adminUrl: str | None = None
    """URL of the client's admin interface, used for backchannel requests."""

    baseUrl: str | None = None
    """Default URL to use when the auth server needs to redirect or link back to the client."""

    surrogateAuthRequired: bool | None = None
    """Whether surrogate authentication is required."""

    enabled: bool | None = None
    """Whether the client is enabled. Disabled clients cannot request tokens."""

    alwaysDisplayInConsole: bool | None = None
    """Whether to always list the client in the Account Console, even without an active session."""

    clientAuthenticatorType: str | None = None
    """How a confidential client authenticates, e.g. `client-secret` or `client-jwt`."""

    secret: str | None = None
    """Client secret. Only returned for confidential clients the caller can manage."""

    registrationAccessToken: str | None = None
    """Registration access token for the client registration service."""

    redirectUris: list[str] | None = None
    """Valid redirect URIs. May contain wildcards."""

    webOrigins: list[str] | None = None
    """Allowed CORS origins. `+` allows the origins of the redirect URIs."""

    notBefore: int | None = None
    """Tokens issued for the client before this time (epoch seconds) are rejected. `0` means not set."""

    bearerOnly: bool | None = None
    """Whether the client only accepts bearer tokens and never initiates logins."""

    consentRequired: bool | None = None
    """Whether users must grant consent to the client."""

    standardFlowEnabled: bool | None = None
    """Whether the authorization code flow is enabled."""

    implicitFlowEnabled: bool | None = None
    """Whether the implicit flow is enabled."""

    directAccessGrantsEnabled: bool | None = None
    """Whether the resource owner password grant is enabled."""

    serviceAccountsEnabled: bool | None = None
    """Whether the client credentials grant (service account) is enabled."""

    authorizationServicesEnabled: bool | None = None
    """Whether fine-grained authorization services are enabled."""

    publicClient: bool | None = None
    """Whether the client is public, i.e. does not authenticate with a secret."""

    frontchannelLogout: bool | None = None
    """Whether logout requests are sent to the client through the browser."""

    protocol: str | None = None
    """Protocol of the client, `openid-connect` or `saml`."""

    attributes: dict[str, str] | None = None
    """Protocol-specific client settings."""

    authenticationFlowBindingOverrides: dict[str, str] | None = None
    """Authentication flows that override the realm's flows for this client, keyed by flow binding."""

    fullScopeAllowed: bool | None = None
    """Whether all realm and client roles are allowed in the client's tokens."""

    nodeReRegistrationTimeout: int | None = None
    """Maximum interval in seconds for cluster nodes to re-register. `-1` means no limit."""

    registeredNodes: dict[str, int] | None = None
    """Registered cluster nodes, mapped to their last registration time."""

    protocolMappers: list[ProtocolMapper] | None = None
    """Protocol mappers defined directly on the client."""

    defaultClientScopes: list[str] | None = None
    """Names of client scopes always applied to the client's tokens."""

    optionalClientScopes: list[str] | None = None
    """Names of client scopes applied when requested with the `scope` parameter."""

    access: dict[str, bool] | None = None
    """What the calling admin may do with this client, e.g. `{"view": true, "manage": true}`."""

    origin: str | None = None
    """ID of the component the client was imported from, if any."""


class QueryClient(QueryPagination):
    """Query parameters for listing clients (`GET /clients`)."""

    clientId: str | None = None
    """Filter by client ID. Matches exactly unless `search` is true."""

    q: str | None = None
    """
    Query to search for client attributes, in the format 'key1:value1 key2:value2'.
    Only attributes the server allows for search can be used; others return 400.
    """

    search: bool | None = None
    """Whether `clientId` matches as a substring instead of exactly (default: false)."""

    viewableOnly: bool | None = None
    """
    Whether to return only clients the caller can view in full (default: false).
    Has no effect on current Keycloak versions, which always leave out clients the caller cannot view.
    """
