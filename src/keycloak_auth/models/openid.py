from typing import Literal

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """
    Token model for access token or RPT token
    """

    access_token: str
    expires_in: int
    refresh_expires_in: int
    refresh_token: str | None = None
    token_type: Literal["Bearer"]
    id_token: str | None = None
    session_state: str | None = None
    scope: str | None = None
    upgraded: bool | None = None


class WellKnown(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    introspection_endpoint: str
    userinfo_endpoint: str
    end_session_endpoint: str
    frontchannel_logout_session_supported: bool
    frontchannel_logout_supported: bool
    jwks_uri: str
    check_session_iframe: str
    grant_types_supported: list[str]
    acr_values_supported: list[str]
    response_types_supported: list[str]
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    id_token_encryption_alg_values_supported: list[str]
    id_token_encryption_enc_values_supported: list[str]
    userinfo_signing_alg_values_supported: list[str]
    userinfo_encryption_alg_values_supported: list[str]
    userinfo_encryption_enc_values_supported: list[str]
    request_object_signing_alg_values_supported: list[str]
    request_object_encryption_alg_values_supported: list[str]
    request_object_encryption_enc_values_supported: list[str]
    response_modes_supported: list[str]
    registration_endpoint: str
    token_endpoint_auth_methods_supported: list[str]
    token_endpoint_auth_signing_alg_values_supported: list[str]
    introspection_endpoint_auth_methods_supported: list[str]
    introspection_endpoint_auth_signing_alg_values_supported: list[str]
    authorization_signing_alg_values_supported: list[str]
    authorization_encryption_alg_values_supported: list[str]
    authorization_encryption_enc_values_supported: list[str]
    claims_supported: list[str]
    claim_types_supported: list[str]
    claims_parameter_supported: bool
    scopes_supported: list[str]
    request_parameter_supported: bool
    request_uri_parameter_supported: bool
    require_request_uri_registration: bool
    code_challenge_methods_supported: list[str]
    tls_client_certificate_bound_access_tokens: bool
    revocation_endpoint: str
    revocation_endpoint_auth_methods_supported: list[str]
    revocation_endpoint_auth_signing_alg_values_supported: list[str]
    backchannel_logout_supported: bool
    backchannel_logout_session_supported: bool
    device_authorization_endpoint: str
    backchannel_token_delivery_modes_supported: list[str]
    backchannel_authentication_endpoint: str
    backchannel_authentication_request_signing_alg_values_supported: list[str]
    require_pushed_authorization_requests: bool
    pushed_authorization_request_endpoint: str
    mtls_endpoint_aliases: dict[str, str]
    authorization_response_iss_parameter_supported: bool


class UserInfo(BaseModel):
    sub: str
    email: str | None = None
    email_verified: bool | None = None
    name: str | None = None
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    locale: str | None = None


class Realm(BaseModel):
    realm: str
    public_key: str


class DecodedTokenAccess(BaseModel):
    roles: list[str]


class DecodedToken(BaseModel):
    exp: int | None = None
    iat: int
    jti: str
    iss: str
    aud: list[str] | str | None = None
    sub: str | None = None
    typ: str
    azp: str
    session_state: str | None = None
    acr: str | None = None
    allowed_origins: list[str] | None = Field(None, alias="allowed-origins")
    realm_access: DecodedTokenAccess | None = None
    resource_access: dict[str, DecodedTokenAccess] | None = None
    scope: str | None = None
    sid: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    client_host: str | None = Field(None, alias="clientHost")
    preferred_username: str | None = None
    client_address: str | None = Field(None, alias="clientAddress")
    given_name: str | None = None
    family_name: str | None = None
    locale: str | None = None


class Introspect(DecodedToken):
    client_id: str
    username: str
    token_type: str
    active: Literal[True]


class Permission(BaseModel):
    rsid: str
    rsname: str
    scopes: list[str] | None = None


class IntrospectRPT(BaseModel):
    exp: int
    nbf: int
    iat: int
    jti: str
    aud: list[str]
    typ: Literal["Bearer"]
    acr: str
    permissions: list[Permission]
    active: Literal[True]


class IntrospectInactive(BaseModel):
    active: Literal[False]


class AuthResult(BaseModel):
    is_logged_in: bool
    is_authorized: bool
    missing_permissions: list[str]


class DeviceAuthResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int
