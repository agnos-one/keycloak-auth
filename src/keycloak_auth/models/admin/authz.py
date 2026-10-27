from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import QueryPagination


class AuthZScope(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    displayName: str | None = None
    iconUri: str | None = None
    id: str | None = None
    """Optional so the scope can be passed when creating a resource, before Keycloak assigns an id."""
    name: str


class AuthZResourceOwner(BaseModel):
    id: str
    name: str


class AuthZResourceOptional(BaseModel):
    attributes: dict[str, list[str]] | None = None
    displayName: str | None = None
    icon_uri: str | None = None
    scopes: list[AuthZScope] | None = None
    type: str | None = None


class AuthZResource(AuthZResourceOptional):
    id: str = Field(alias="_id")
    name: str
    owner: AuthZResourceOwner
    ownerManagedAccess: bool
    uris: list[str]


class CreateAuthZResource(AuthZResourceOptional):
    name: str
    ownerManagedAccess: bool = False
    uris: list[str]


class UpdateAuthZResource(AuthZResourceOptional):
    name: str
    ownerManagedAccess: bool | None = None
    uris: list[str] | None = None


class QueryAuthZResource(QueryPagination):
    deep: bool | None = None
    name: str | None = None
    owner: str | None = None
    type: str | None = None
    uri: str | None = None


DecisionStrategy = Literal["UNANIMOUS", "AFFIRMATIVE", "CONSENSUS"]
Logic = Literal["POSITIVE", "NEGATIVE"]
PolicyType = Literal["aggregate", "client", "client-scope", "group", "js", "regex", "role", "time", "user"]


class QueryAuthZPolicy(QueryPagination):
    name: str | None = None
    type: str | None = None


class AuthZPolicyBase(BaseModel):
    decisionStrategy: DecisionStrategy
    description: str | None = None
    id: str
    logic: Logic
    name: str
    type: PolicyType


class AuthZPolicy(AuthZPolicyBase):
    config: dict[str, str]


class AuthZPolicyUser(AuthZPolicyBase):
    users: list[str]


class CreateAuthZPolicyUser(BaseModel):
    description: str
    logic: Logic
    name: str
    users: list[str]


PermissionType = Literal["resource", "scope"]


class AuthZPermissionBase(BaseModel):
    decisionStrategy: DecisionStrategy
    description: str | None = None
    id: str
    logic: Logic
    name: str
    type: PermissionType


class AuthZPermission(AuthZPermissionBase):
    resourceType: str | None = None


class QueryAuthZPermission(QueryPagination):
    name: str | None = None
    type: PermissionType | None = None
    resource: str | None = None
    scope: str | None = None


class AuthZPermissionResource(AuthZPermissionBase):
    policies: list[str]
    resources: list[str]


class CreateAuthZPermissionResource(BaseModel):
    decisionStrategy: DecisionStrategy
    description: str
    name: str
    policies: list[str]
    resources: list[str]
