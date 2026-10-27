import os
from uuid import uuid4

from keycloak_auth import AsyncKeycloakAdmin
from keycloak_auth.exceptions import KeycloakError
from keycloak_auth.models.admin import authz as z
from keycloak_auth.models.admin import client as c
from keycloak_auth.models.admin import user as u


def get_kc_client():
    admin_username = os.getenv("KEYCLOAK_ADMIN_USERNAME")
    admin_password = os.getenv("KEYCLOAK_ADMIN_PASSWORD")
    if not admin_username or not admin_password:
        raise ValueError("Admin username and password must be set")

    client = AsyncKeycloakAdmin(
        server_url=os.getenv("KEYCLOAK_SERVER_URL") or "http://localhost:8080",
        target_realm=os.getenv("KEYCLOAK_REALM") or "master",
        admin_username=admin_username,
        admin_password=admin_password,
    )
    return client


async def test_context_manager():
    async with get_kc_client() as client:
        assert len(await client.get_clients(c.QueryClient(max=1))) == 1

    # the session is logged out and the HTTP clients are closed on exit
    try:
        await client.get_clients(c.QueryClient(max=1))
        assert False, "request after exit should fail"
    except RuntimeError as e:
        assert "closed" in str(e)


async def test_errors():
    async with get_kc_client() as client:
        # the admin API's error message is kept, together with the status code
        try:
            await client.get_client_authz_resources(str(uuid4()))
            assert False, "request for a missing client should fail"
        except KeycloakError as e:
            assert e.status_code == 404
            assert e.error == "status_error"
            assert e.error_description == "404 Not Found: Could not find client"


async def test_users():
    async with get_kc_client() as client:
        # test get users
        users = await client.get_users(u.QueryUser(firstName="John", lastName="Smith"))
        assert len(users) == 1
        assert users[0].firstName == "John"
        assert users[0].lastName == "Smith"

        users = await client.get_users(u.QueryUser(email="john@example.com"))
        assert len(users) == 1
        assert users[0].email == "john@example.com"

        # test brief representation
        users = await client.get_users(u.QueryUser(email="john@example.com", briefRepresentation=True))
        assert len(users) == 1
        assert users[0].email == "john@example.com"

        # test create user
        username = f"test-user-{uuid4().hex[:8]}"
        await client.create_user(u.CreateUser(username=username, email=f"{username}@example.com"))

        try:
            created_user = await client.get_users(u.QueryUser(username=username, exact=True))
            assert len(created_user) == 1
            user_id = created_user[0].id

            # test exact match
            users = await client.get_users(u.QueryUser(username=username[:-1], exact=True))
            assert all(user.id != user_id for user in users)

            # test created date filters (inclusive, epoch milliseconds)
            created_at = created_user[0].createdTimestamp
            users = await client.get_users(u.QueryUser(username=username, exact=True, createdAfter=created_at))
            assert len(users) == 1
            users = await client.get_users(u.QueryUser(username=username, exact=True, createdAfter=created_at + 1))
            assert len(users) == 0
            users = await client.get_users(u.QueryUser(username=username, exact=True, createdBefore=created_at - 1))
            assert len(users) == 0

            # test update user
            await client.update_user(user_id, u.UpdateUser(firstName="Test", lastName="User"))

            updated_user = await client.get_users(u.QueryUser(username=username, exact=True))
            assert len(updated_user) == 1
            assert updated_user[0].firstName == "Test"
            assert updated_user[0].lastName == "User"

            # test update keeps a disabled user disabled
            await client.update_user(user_id, u.UpdateUser(enabled=False))
            await client.update_user(user_id, u.UpdateUser(firstName="Disabled"))

            updated_user = await client.get_users(u.QueryUser(username=username, exact=True))
            assert len(updated_user) == 1
            assert updated_user[0].firstName == "Disabled"
            assert updated_user[0].enabled is False
        finally:
            # test delete user
            for user in await client.get_users(u.QueryUser(username=username, exact=True)):
                await client.delete_user(user.id)

        deleted_user = await client.get_users(u.QueryUser(username=username, exact=True))
        assert len(deleted_user) == 0


async def test_clients():
    async with get_kc_client() as client:
        # test get clients
        clients = await client.get_clients()
        assert len(clients) >= 1

        # test exact client ID match
        clients = await client.get_clients(c.QueryClient(clientId="account"))
        assert len(clients) == 1
        assert clients[0].clientId == "account"

        # test client ID search
        clients = await client.get_clients(c.QueryClient(clientId="account", search=True))
        client_ids = {client.clientId for client in clients}
        assert {"account", "account-console"} <= client_ids

        # test pagination
        clients = await client.get_clients(c.QueryClient(max=1))
        assert len(clients) == 1


async def test_authz_resources():
    async with get_kc_client() as client:
        realm_clients = await client.get_clients(c.QueryClient(clientId="test-client"))
        assert len(realm_clients) == 1
        client_uuid = realm_clients[0].id

        # test get authz resources
        resources = await client.get_client_authz_resources(client_uuid)
        assert len(resources) >= 1
        resources = await client.get_client_authz_resources(
            client_uuid=client_uuid,
            query=z.QueryAuthZResource(name="resource-1"),
        )
        assert len(resources) == 1

        # test create authz resource
        name = f"resource-test-{uuid4().hex[:8]}"
        resource_new = z.CreateAuthZResource(
            name=name,
            type="urn:authz:test",
            uris=["/test/1", "/test/2"],
            scopes=[z.AuthZScope(name="read-resource")],
        )
        resource = await client.create_client_authz_resource(client_uuid, resource_new)

        try:
            assert resource.name == name
            assert resource.type == "urn:authz:test"

            # test update authz resource
            resource_mod = z.UpdateAuthZResource(
                name=f"{name}-mod",
                type="urn:authz:test-mod",
                uris=["/test/1", "/test/2", "/test/3"],
                scopes=[],
            )
            await client.update_client_authz_resource(client_uuid, resource.id, resource_mod)

            resources = await client.get_client_authz_resources(
                client_uuid, query=z.QueryAuthZResource(name=f"{name}-mod")
            )
            assert len(resources) == 1
            assert resources[0].name == f"{name}-mod"
            assert resources[0].type == "urn:authz:test-mod"
            assert len(resources[0].uris) == 3
            assert resources[0].scopes is None
        finally:
            # test delete authz resource
            await client.delete_client_authz_resource(client_uuid, resource.id)

        resources = await client.get_client_authz_resources(client_uuid, query=z.QueryAuthZResource(name=name))
        assert len(resources) == 0


async def test_authz_policy():
    async with get_kc_client() as client:
        realm_clients = await client.get_clients(c.QueryClient(clientId="test-client"))
        assert len(realm_clients) == 1
        client_uuid = realm_clients[0].id

        realm_users = await client.get_users()
        assert len(realm_users) >= 2
        user_1_uuid = realm_users[0].id
        user_2_uuid = realm_users[1].id

        # test get authz resources
        policies = await client.get_client_authz_policies(client_uuid)
        assert len(policies) >= 1
        policies = await client.get_client_authz_policies(
            client_uuid=client_uuid,
            query=z.QueryAuthZPolicy(name="policy-1"),
        )
        assert len(policies) == 1

        # test create user policy
        name = f"policy-test-{uuid4().hex[:8]}"
        policy_new = z.CreateAuthZPolicyUser(
            description="Test User Policy",
            logic="POSITIVE",
            name=name,
            users=[user_1_uuid, user_2_uuid],
        )

        policy = await client.create_client_authz_policy_user(client_uuid, policy_new)
        policy_id = policy.id

        try:
            assert policy.name == name
            assert policy.type == "user"

            policy = await client.get_client_authz_policy_user(client_uuid, policy_id)

            # test update user policy
            policy.users = [user_1_uuid]
            policy.name = f"{name}-mod"
            await client.update_client_authz_policy_user(client_uuid, policy_id, policy)

            policies = await client.get_client_authz_policies(client_uuid, query=z.QueryAuthZPolicy(name=f"{name}-mod"))
            assert len(policies) == 1
            assert policies[0].name == f"{name}-mod"
        finally:
            # test delete user policy
            await client.delete_client_authz_policy_user(client_uuid, policy_id)

        policies = await client.get_client_authz_policies(client_uuid, query=z.QueryAuthZPolicy(name=name))
        assert len(policies) == 0


async def test_authz_permission():
    async with get_kc_client() as client:
        realm_clients = await client.get_clients(c.QueryClient(clientId="test-client"))
        assert len(realm_clients) == 1
        client_uuid = realm_clients[0].id

        realm_policies = await client.get_client_authz_policies(client_uuid, z.QueryAuthZPolicy(name="policy-1"))
        assert len(realm_policies) == 1
        policy_1_uuid = realm_policies[0].id

        realm_resources = await client.get_client_authz_resources(client_uuid, z.QueryAuthZResource(name="resource-1"))
        assert len(realm_resources) == 1
        resource_1_uuid = realm_resources[0].id

        # test get authz permissions
        permissions = await client.get_client_authz_permissions(client_uuid)
        assert len(permissions) >= 1
        permissions = await client.get_client_authz_permissions(
            client_uuid=client_uuid,
            query=z.QueryAuthZPermission(name="permission-1"),
        )
        assert len(permissions) == 1

        # test create resource-based permission
        name = f"permission-test-{uuid4().hex[:8]}"
        permission_new = z.CreateAuthZPermissionResource(
            decisionStrategy="UNANIMOUS",
            description="Test Permission",
            name=name,
            policies=[
                policy_1_uuid,
            ],
            resources=[resource_1_uuid],
        )
        permission = await client.create_client_authz_permission_resource(client_uuid, permission_new)

        try:
            assert permission.name == name
        finally:
            # test delete resource-based permission
            await client.delete_client_authz_permission_resource(client_uuid, permission.id)

        permissions = await client.get_client_authz_permissions(client_uuid, query=z.QueryAuthZPermission(name=name))
        assert len(permissions) == 0
