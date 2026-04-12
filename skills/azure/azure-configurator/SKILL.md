---
name: azure-configurator
description: >-
  This skill should be used when the user or azure-provisioner asks to "configure Azure app settings",
  "set up Key Vault secrets", "configure RBAC roles", "set up PostgreSQL auth",
  "configure managed identity", "set up Entra authentication for PostgreSQL",
  "configure storage CORS", "set app service environment variables",
  "configure Key Vault references", "set up database connection string",
  "configure Azure firewall rules", "set up blob storage containers",
  "manage Azure secrets", or mentions app settings, Key Vault references,
  RBAC assignments, or PostgreSQL server configuration on Azure.
version: 1.0.0
---

# Azure Resource Configurator

## Purpose

Configure Azure resources after Bicep provisioning: app settings with Key Vault
references, RBAC role assignments, PostgreSQL server configuration and auth modes,
Key Vault secret management, storage account setup, and App Service container
configuration. Handle the post-IaC configuration layer that deploy scripts execute.

---

## Core Workflow

### 1. RBAC Role Assignment

Configure managed identity access using idempotent role assignments. Each assignment
follows a check-then-create pattern to prevent errors on re-deployment:

```powershell
# Pattern: check for existing assignment before creating
$existing = az role assignment list --assignee $principalId --role $roleName --scope $scope
if (-not $existing -or $existing -eq '[]') {
    az role assignment create --assignee $principalId --role $roleName --scope $scope
}
```

**Standard assignments (4 total):**

| Principal | Role Definition | Scope | Purpose |
|-----------|----------------|-------|---------|
| Backend system-assigned MI | `AcrPull` | ACR resource ID | Pull container images at startup |
| Frontend system-assigned MI | `AcrPull` | ACR resource ID | Pull container images at startup |
| Backend system-assigned MI | `Key Vault Secrets User` | KV resource ID | Resolve KV reference app settings |
| Backend system-assigned MI | `Storage Blob Data Contributor` | Storage resource ID | Read/write blob data for file uploads |

**Scope specificity:** Always scope assignments to the specific resource ID, never to
the resource group or subscription. This follows the principle of least privilege and
ensures a compromised identity cannot access other resources in the same group.

**Timing constraint:** RBAC assignments (Stage 03) must complete before app settings
(Stage 05) because the backend MI needs `Key Vault Secrets User` to resolve
`@Microsoft.KeyVault()` references on web app restart. RBAC propagation takes up to
5 minutes -- if KV references fail immediately after role assignment, wait and retry.

### 2. Key Vault Secret Management

Push secrets from the `.env` file to Key Vault. This is a two-pass process:
identification then upsert.

**Secret identification rules (dual strategy):**
- **Explicit list (28 known secrets):** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_COMPATIBLE_KEY`, `AZURE_OPENAI_KEY`,
  `AZURE_OPENAI_ENDPOINT`, `SESSION_SECRET`, `JWT_SECRET`, `WORKOS_API_KEY`,
  `WORKOS_CLIENT_ID`, `WORKOS_COOKIE_PASSWORD`, `DATABASE_URL`, `BRAVE_API_KEY`,
  `TAVILY_API_KEY`, and others matching the sensitive data pattern
- **Pattern match fallback:** Any variable name ending with `_KEY`, `_SECRET`,
  `_PASSWORD`, or `_TOKEN` is treated as a secret even if not explicitly listed
- **Skip rules:** Empty values are skipped. Deployment-only variables (18 listed)
  are never stored in Key Vault.

**Name conversion rule:** Environment variable names convert to Key Vault secret
names by lowercasing and replacing underscores with hyphens:
`OPENAI_API_KEY` -> `openai-api-key`, `DATABASE_URL` -> `database-url`

**Upsert and verification:**
```powershell
# Write secret
az keyvault secret set --vault-name $kvName --name $secretName --value $value

# Verify read-back
$readBack = az keyvault secret show --vault-name $kvName --name $secretName --query value -o tsv
if ($readBack -ne $value) { throw "Secret verification failed for $secretName" }
```

**Special validation for `database-url`:**
- Must start with `postgresql://`
- Must contain `sslmode=require`
- If the state file contains `databaseUrl` from Stage 04, that value is used
  (overriding any value from the env file)

### 3. App Service Configuration

Configure app settings in two categories, applied via bulk JSON update:

**Non-sensitive settings (set as plain text):**
```json
{
  "PORT": "8000",
  "WEBSITES_PORT": "8000",
  "CACHE_BACKEND": "postgres",
  "CACHE_PREFIX": "chatlink",
  "CACHE_POSTGRES_TABLE": "cache_entries",
  "RLM_ENABLED": "true",
  "POSTGRES_SSL": "true",
  "FRONTEND_ORIGIN": "https://{frontendHostname}",
  "FRONTEND_ORIGINS": "https://{frontendHostname},https://{mcpFrontendHostname}"
}
```

**Sensitive settings (set as Key Vault references):**
```json
{
  "OPENAI_API_KEY": "@Microsoft.KeyVault(SecretUri=https://{kvName}.vault.azure.net/secrets/openai-api-key)",
  "DATABASE_URL": "@Microsoft.KeyVault(SecretUri=https://{kvName}.vault.azure.net/secrets/database-url)",
  "SESSION_SECRET": "@Microsoft.KeyVault(SecretUri=https://{kvName}.vault.azure.net/secrets/session-secret)"
}
```

**Bulk update pattern (prevents temp file leaks):**
```powershell
$tempFile = [System.IO.Path]::GetTempFileName()
try {
    $allSettings | ConvertTo-Json | Set-Content $tempFile
    az webapp config appsettings set --name $webAppName --resource-group $rgName --settings "@$tempFile"
} finally {
    Remove-Item $tempFile -ErrorAction SilentlyContinue
}
```

**Additional web app configuration applied after settings:**
- Managed identity ACR pull: `az webapp config set --acr-use-identity true`
- Always-on: prevents cold starts on idle web apps
- Health check path: `/health` (backend), `/` (frontend)
- FTPS disabled: no FTP access to the container
- Minimum TLS 1.2 on all HTTPS endpoints

**Frontend app settings are minimal:**
| Setting | Value | Purpose |
|---------|-------|---------|
| `WEBSITES_PORT` | `80` | Container listen port |
| `API_BASE_URL` | `https://{backendHostname}/api` | Backend API endpoint |
| `WS_BASE_URL` | `wss://{backendHostname}/ws` | WebSocket endpoint |
| `BACKEND_BASE_URL` | `https://{backendHostname}` | Backend root URL |

### 4. PostgreSQL Server Configuration

**Auth mode configuration (three modes):**

| Mode | Password Auth | Entra Auth | Use Case | Connection Method |
|------|--------------|------------|----------|-------------------|
| `password` | Enabled | Disabled | Development, simple setups | Username + password in DATABASE_URL |
| `hybrid` | Enabled | Enabled | Migration period | Either method works |
| `entra_only` | Disabled | Enabled | Production security | MI token as password |

**Server hardening (applied to all modes):**
- `require_secure_transport = ON` -- reject unencrypted connections
- Minimum TLS: `TLSv1.2` (or `TLSv1.3` where supported)
- Public network access: enabled but firewall-gated

**Firewall rules:**
- `AllowAzureServices`: start IP `0.0.0.0`, end IP `0.0.0.0` -- allows all Azure-internal
  traffic. Required for App Service to reach the database.
- `DeployRunner`: deployer's public IP (auto-detected via ipify.org). Required for
  `psql` commands during migration. Should be removed after deployment for security.

**Extension enablement (required for the application):**
```sql
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector for embedding storage
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- UUID generation via gen_random_uuid()
```

**Application user provisioning (password mode):**
```sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chatlink_app') THEN
    CREATE ROLE chatlink_app WITH LOGIN PASSWORD 'secure_password_here';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO chatlink_app;
GRANT USAGE ON SCHEMA mcp TO chatlink_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatlink_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mcp TO chatlink_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatlink_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatlink_app;
```

**Application user provisioning (Entra mode):**
```sql
CREATE ROLE "chatlink_app" WITH LOGIN IN ROLE azure_ad_user;
SECURITY LABEL FOR "pgaadauth" ON ROLE "chatlink_app" IS 'aadauth,oid={MI_OID},database=chatlink';
-- Same GRANT statements as password mode
```

**Database URL construction and storage:**
```
postgresql://{appUser}:{appPassword}@{serverFqdn}:5432/{dbName}?sslmode=require
```
The constructed URL is stored in Key Vault as secret `database-url` and referenced
from the backend app settings via a KV reference URI.

### 5. Storage Account Configuration

Configure blob storage for application file uploads:

- **Create containers:** `files` and `attachments` with private access level
  (no anonymous read, authentication required for all operations)
- **Enable soft delete:** 7-day retention on deleted blobs (recoverable)
- **Enable versioning:** Track blob modifications (required for audit compliance)
- **Configure CORS:** Allow frontend origin(s) with all HTTP methods (`GET`, `POST`,
  `PUT`, `DELETE`, `OPTIONS`), all headers, 3600-second max-age
- **Verify RBAC:** Confirm backend MI has `Storage Blob Data Contributor` role
  (warning if missing, but do not create -- that is Stage 03's responsibility)

---

## Configuration Checklist

- [ ] All 4 RBAC roles assigned (check for pre-existing before creating)
- [ ] All secrets pushed to Key Vault with verified read-back
- [ ] `database-url` in KV validated (starts with `postgresql://`, contains `sslmode=require`)
- [ ] Backend app settings include KV references for all secret variables
- [ ] Frontend app settings point to correct backend hostname
- [ ] PostgreSQL auth mode matches target configuration
- [ ] PostgreSQL extensions enabled (`vector`, `pgcrypto`)
- [ ] PostgreSQL firewall rules set (Azure services + deploy runner IP)
- [ ] Application database user created with correct grants (both schemas)
- [ ] Storage containers created with private access level
- [ ] CORS configured for frontend origins
- [ ] Temporary settings files cleaned up in `finally` blocks

---

## Additional Resources

### Reference Files

- **`references/keyvault-patterns.md`** -- Key Vault reference URI syntax, secret
  rotation patterns, access troubleshooting, and RBAC vs access policy comparison
- **`references/postgres-auth-modes.md`** -- Detailed PostgreSQL Entra authentication
  setup, hybrid mode migration path, and pgaadauth security label configuration
- **`references/appservice-settings.md`** -- Complete app settings reference,
  bulk update patterns, slot-sticky settings, and container configuration options

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: azure
   phase: 3
   skill: azure-configurator
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. Write the review packet as `review-packet.md` in the same save path directory

3. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
