# PostgreSQL Authentication Modes

## Mode Comparison

### Password Mode (`password`)

- Standard username/password authentication
- Simplest to set up and debug
- Connection string: `postgresql://user:pass@host:5432/db?sslmode=require`
- Suitable for development and simple production setups

### Hybrid Mode (`hybrid`)

- Both password and Entra ID authentication enabled
- Migration stepping stone from password to Entra-only
- Allows gradual migration of application connections
- Both auth methods work simultaneously

### Entra-Only Mode (`entra_only`)

- Password authentication disabled
- Only Entra ID (Azure AD) tokens accepted
- Highest security: no stored passwords, token-based, auto-rotating
- Requires managed identity configuration on the application

## Entra Authentication Setup

### 1. Enable Entra Auth on Server

```powershell
az postgres flexible-server update `
  --name $serverName `
  --resource-group $rgName `
  --active-directory-auth Enabled `
  --password-auth Disabled  # for entra_only
```

### 2. Set Entra Admin

```powershell
az postgres flexible-server ad-admin create `
  --server-name $serverName `
  --resource-group $rgName `
  --object-id $adminOid `
  --display-name $adminDisplayName `
  --type ServicePrincipal  # or User
```

### 3. Create Application Role with pgaadauth

Connect as the Entra admin and execute:

```sql
-- Create the role for the managed identity
SELECT * FROM pgaadauth_create_principal_with_oid(
  'chatlink_app',
  '{managed-identity-object-id}',
  'service',
  false,
  false
);
```

Or manually:
```sql
CREATE ROLE "chatlink_app" WITH LOGIN IN ROLE azure_ad_user;
SECURITY LABEL FOR "pgaadauth" ON ROLE "chatlink_app"
  IS 'aadauth,oid={MI_OID},database=chatlink';
```

### 4. Grant Permissions

```sql
GRANT USAGE ON SCHEMA public TO "chatlink_app";
GRANT USAGE ON SCHEMA mcp TO "chatlink_app";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "chatlink_app";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mcp TO "chatlink_app";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "chatlink_app";
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "chatlink_app";
```

## Migration Path: Password -> Entra-Only

1. **Phase 1:** Enable hybrid mode (both auth types active)
2. **Phase 2:** Configure Entra admin and create MI-based roles
3. **Phase 3:** Update application to use MI token-based auth
4. **Phase 4:** Verify application works with Entra tokens
5. **Phase 5:** Disable password auth (switch to entra_only)
6. **Phase 6:** Remove password-based roles and connection strings

## Connection String for Entra Mode

When using managed identity, the application requests an access token from the
Azure Instance Metadata Service (IMDS) and uses it as the password:

```
postgresql://chatlink_app@{server-fqdn}:5432/chatlink?sslmode=require
```

The password is the access token obtained via:
```typescript
const credential = new DefaultAzureCredential();
const token = await credential.getToken("https://ossrdbms-aad.database.windows.net/.default");
// Use token.token as the password
```

## Auth Config Convergence

After changing auth config, the server may take 1-3 minutes to apply. The deploy
script polls the server configuration until the desired state is confirmed:

```powershell
do {
    $config = az postgres flexible-server show --name $server --resource-group $rg
    $authConfig = ($config | ConvertFrom-Json).authConfig
    Start-Sleep -Seconds 10
} while ($authConfig.activeDirectoryAuth -ne 'Enabled')
```
