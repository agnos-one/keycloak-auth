# Realm URLS
URL_REALM = "/realms/{realm_name}"
URL_WELL_KNOWN = URL_REALM + "/.well-known/openid-configuration"
URL_TOKEN = URL_REALM + "/protocol/openid-connect/token"
URL_AUTH_DEVICE = URL_REALM + "/protocol/openid-connect/auth/device"
URL_USERINFO = URL_REALM + "/protocol/openid-connect/userinfo"
URL_LOGOUT = URL_REALM + "/protocol/openid-connect/logout"
URL_INTROSPECT = URL_REALM + "/protocol/openid-connect/token/introspect"

# Admin URLS
URL_ADMIN_API = "/admin/realms/{realm_name}"
# Admin Users
URL_ADMIN_USERS = URL_ADMIN_API + "/users"
URL_ADMIN_USER = URL_ADMIN_USERS + "/{user_id}"
URL_ADMIN_USER_CONSENTS = URL_ADMIN_USER + "/consents"
URL_ADMIN_USER_CONSENT = URL_ADMIN_USER_CONSENTS + "/{client_id}"
# Admin Clients
URL_ADMIN_CLIENTS = URL_ADMIN_API + "/clients"
URL_ADMIN_CLIENT = URL_ADMIN_CLIENTS + "/{client_uuid}"
# Admin Client AuthZ
URL_ADMIN_CLIENT_AUTHZ = URL_ADMIN_CLIENT + "/authz/resource-server"
# Admin Client AuthZ Resources
URL_ADMIN_CLIENT_AUTHZ_RESOURCES = URL_ADMIN_CLIENT_AUTHZ + "/resource"
URL_ADMIN_CLIENT_AUTHZ_RESOURCE = URL_ADMIN_CLIENT_AUTHZ_RESOURCES + "/{resource_id}"
# Admin Client AuthZ Policies
URL_ADMIN_CLIENT_AUTHZ_POLICIES = URL_ADMIN_CLIENT_AUTHZ + "/policy"
URL_ADMIN_CLIENT_AUTHZ_POLICIES_USER = URL_ADMIN_CLIENT_AUTHZ_POLICIES + "/user"
URL_ADMIN_CLIENT_AUTHZ_POLICY_USER = URL_ADMIN_CLIENT_AUTHZ_POLICIES_USER + "/{policy_id}"
# Admin Client AuthZ Permissions
URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS = URL_ADMIN_CLIENT_AUTHZ + "/permission"
URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS_RESOURCE = URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS + "/resource"
URL_ADMIN_CLIENT_AUTHZ_PERMISSION_RESOURCE = URL_ADMIN_CLIENT_AUTHZ_PERMISSIONS_RESOURCE + "/{permission_id}"
