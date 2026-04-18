---
name: azure-verifier
description: >-
  This skill should be used when the user asks to "verify Azure
  deployment", "run deployment health checks", "validate Azure
  configuration", "verify RBAC assignments", "run smoke tests",
  "validate PostgreSQL schema", "check container deployment",
  "did the deploy work?", "check if it's healthy", or "prove the
  Azure rollout actually worked". Validates
  deployments at every level: infrastructure, RBAC, secrets,
  database schema, containers, health endpoints, and end-to-end
  smoke tests. Produces a verification report with pass/fail
  per layer.
  DO NOT USE for deploying code (use azure-deployer). DO NOT USE
  for configuring resources (use azure-configurator). DO NOT USE
  for infrastructure design (use azure-architect).
version: 1.0.0
---

# Azure Deployment Verifier

## Purpose

Verify and validate Azure deployments at every level: infrastructure provisioning,
resource configuration, RBAC assignments, secret management, database schema,
container deployment, health endpoints, and end-to-end smoke tests. Produce
verification reports with pass/fail status for each check.

---

## Core Workflow

### 1. Infrastructure Verification

Validate that Bicep-provisioned resources exist and are correctly configured.
Run resource-specific queries and compare against expected values:

**Resource existence and configuration checks:**

| Resource | az CLI Command | Expected Properties |
|----------|---------------|-------------------|
| Resource Group | `az group show --name $rg` | Exists, correct location, provisioningState=Succeeded |
| App Service Plan | `az appservice plan show` | kind=linux, reserved=true, sku.name=B2 |
| Backend Web App | `az webapp show` | identity.type=SystemAssigned, httpsOnly=true |
| Frontend Web App | `az webapp show` | identity.type=SystemAssigned, httpsOnly=true |
| ACR | `az acr show` | adminUserEnabled=false, sku.name=Basic |
| Key Vault | `az keyvault show` | enableRbacAuthorization=true, softDeleteRetentionInDays=90 |
| Storage Account | `az storage account show` | minimumTlsVersion=TLS1_2, allowBlobPublicAccess=false |
| PostgreSQL | `az postgres flexible-server show` | version=16, correct authConfig |

**Web app general configuration verification:**
```powershell
az webapp config show --name $webAppName --resource-group $rgName `
    --query "{alwaysOn:alwaysOn, minTlsVersion:minTlsVersion, ftpsState:ftpsState, healthCheckPath:healthCheckPath}"
```
Expected: `alwaysOn=true`, `minTlsVersion=1.2`, `ftpsState=Disabled`,
`healthCheckPath=/health` (backend) or `/` (frontend).

### 2. RBAC Verification

Confirm all 4 required role assignments exist by querying each one explicitly:

```powershell
az role assignment list --assignee $principalId --scope $resourceId --role $roleName
```

**Expected assignments with verification logic:**

| # | Principal | Role | Scope | How to Verify |
|---|-----------|------|-------|---------------|
| 1 | Backend MI principal ID | AcrPull | ACR resource ID | Non-empty result = PASS |
| 2 | Frontend MI principal ID | AcrPull | ACR resource ID | Non-empty result = PASS |
| 3 | Backend MI principal ID | Key Vault Secrets User | KV resource ID | Non-empty result = PASS |
| 4 | Backend MI principal ID | Storage Blob Data Contributor | Storage resource ID | Non-empty result = PASS |

If any assignment is missing, report as FAIL with the exact `az role assignment create`
command needed to fix it.

### 3. Secret Verification

Validate Key Vault secrets exist, are readable, and contain valid values:

**Per-secret checks:**
```powershell
$secret = az keyvault secret show --vault-name $kvName --name $secretName --query value -o tsv
```

- **Existence:** Secret exists in Key Vault (show command succeeds)
- **Non-empty:** Value is not null or empty string
- **Format validation for `database-url`:**
  - Must start with `postgresql://`
  - Must contain `sslmode=require`
  - Must contain the correct server FQDN from state
  - Must reference the correct database name

**KV reference resolution check:**
Query app settings and verify no KV references are in error state:
```powershell
$settings = az webapp config appsettings list --name $webAppName --resource-group $rgName | ConvertFrom-Json
$kvSettings = $settings | Where-Object { $_.value -like '@Microsoft.KeyVault*' }
# If any setting has a "status" field with "SecretNotFound" or "Unauthorized", it's FAIL
```

### 4. Database Verification

Run SQL queries to validate the complete database state:

**Extension verification:**
```sql
SELECT extname, extversion FROM pg_extension
WHERE extname IN ('vector', 'pgcrypto');
-- Expected: 2 rows
```

**Schema verification:**
```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('public', 'mcp');
-- Expected: 2 rows
```

**Critical table verification:**
```sql
SELECT table_schema, table_name FROM information_schema.tables
WHERE (table_schema, table_name) IN (
    ('public', 'memories'), ('public', 'cache_entries'),
    ('public', 'schema_migrations'), ('mcp', 'tiers'),
    ('mcp', 'products'), ('mcp', 'subscriptions')
);
```

**Migration tracking verification:**
```sql
SELECT version, checksum, applied_at FROM public.schema_migrations ORDER BY version;
-- Expected: all migrations present with correct checksums
```

**Critical column verification (regression guard):**
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'mcp' AND table_name = 'tiers' AND column_name = 'capabilities';
-- Expected: 1 row (column exists)
```

**Application user verification:**
```sql
SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = 'chatlink_app';
-- Expected: rolcanlogin = true
```

**Grant verification (both schemas):**
```sql
SELECT grantee, table_schema, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'chatlink_app' AND table_schema IN ('public', 'mcp');
-- Expected: SELECT, INSERT, UPDATE, DELETE on all tables in both schemas
```

### 5. App Service Verification

**Container configuration:**
```powershell
$config = az webapp config container show --name $webAppName --resource-group $rgName | ConvertFrom-Json
$image = ($config | Where-Object { $_.name -eq 'DOCKER_CUSTOM_IMAGE_NAME' }).value
# Verify image contains expected ACR login server and tag
```

**App settings completeness:**
Verify all required settings are present and KV references point to the correct vault:
- All runtime non-sensitive variables present as plain text
- All secret variables present as `@Microsoft.KeyVault()` references
- No deployment-only variables accidentally included
- `WEBSITES_PORT` matches the container's listen port

### 6. Health Check Verification

**Backend health (primary check):**
```powershell
$response = Invoke-WebRequest -Uri "https://$backendHostname/health" -Method GET -TimeoutSec 30
# Expect: StatusCode 200
```

**Frontend health:**
```powershell
$response = Invoke-WebRequest -Uri "https://$frontendHostname/" -Method GET -TimeoutSec 30
# Expect: StatusCode 200, content-type contains text/html
```

**Fallback strategy:** If custom domain returns an error, test the default
`.azurewebsites.net` hostname to isolate whether the issue is DNS/domain-related
or application-related.

**Timing consideration:** Allow 15-30 seconds after container restart before health
checking. App Service needs time to pull the image and start the container.

### 7. End-to-End Smoke Tests

**API functionality:**
- `GET /health` -- Backend alive and responsive
- `GET /api/public/tiers` -- Public tier listing (expect specific tier count when enabled)

**MCP transport verification:**
- Verify MCP endpoint responds with expected `streamable-http` transport mode

**OAuth flow verification (when `AUTH_ENABLED=true`):**
- `GET /api/auth/authorize` should return a redirect (302) to WorkOS/AuthKit
- Follow redirect chain to verify it completes without errors
- Verify the redirect URL contains the correct `redirect_uri` parameter

**Image tag verification (critical for production):**
```powershell
$containerConfig = az webapp config container show --name $webAppName --resource-group $rgName
# Extract DOCKER_CUSTOM_IMAGE_NAME value
# Verify the tag portion matches the expected deployment tag
```
A mismatch means the container update failed silently or was overwritten.

### 8. Storage Verification

```powershell
# Containers exist with correct access
az storage container list --account-name $storageName --auth-mode login --query "[].{name:name, publicAccess:properties.publicAccess}"
# Expected: files (None), attachments (None)

# Soft delete enabled
az storage blob service-properties show --account-name $storageName --auth-mode login --query deleteRetentionPolicy
# Expected: enabled=true, days=7

# Versioning enabled
az storage blob service-properties show --account-name $storageName --auth-mode login --query isVersioningEnabled
# Expected: true

# CORS configured
az storage cors list --account-name $storageName --services b
# Expected: frontend origin(s) in allowed-origins
```

---

## Verification Report Format

Produce a structured report with pass/fail counts per domain:

```

---

## Deployment Verification Report
Date: YYYY-MM-DD HH:MM UTC
Environment: {env}
Resource Group: {rgName}

### Infrastructure (8/8 passed)
- [PASS] Resource Group: exists, swedencentral
- [PASS] App Service Plan: Linux B2, capacity 1
- [PASS] Backend Web App: System MI, HTTPS only, always-on
- [PASS] Frontend Web App: System MI, HTTPS only
- [PASS] ACR: admin disabled, Basic SKU
- [PASS] Key Vault: RBAC auth, 90-day soft delete
- [PASS] Storage: TLS 1.2, HTTPS only, no public blob
- [PASS] PostgreSQL: v16, password auth, TLS 1.2

### RBAC (4/4 passed)
- [PASS] Backend MI -> AcrPull on ACR
- [PASS] Frontend MI -> AcrPull on ACR
- [PASS] Backend MI -> Key Vault Secrets User on KV
- [PASS] Backend MI -> Storage Blob Data Contributor on Storage

### Secrets (14/14 passed)
- [PASS] database-url: valid postgresql:// with sslmode=require
- [PASS] openai-api-key: non-empty
- ... (all secrets listed)

### Database (6/6 passed)
- [PASS] Extensions: vector, pgcrypto
- [PASS] Schemas: public, mcp
- [PASS] Migrations: 9/9 applied with correct checksums
- [PASS] App user: chatlink_app exists, can login
- [PASS] Grants: SELECT/INSERT/UPDATE/DELETE on both schemas
- [PASS] Critical column: mcp.tiers.capabilities exists

### Health (3/3 passed)
- [PASS] Backend /health: 200 OK (145ms)
- [PASS] Frontend /: 200 OK (89ms)
- [PASS] Image tag: matches 20260410143022

### Overall: PASS (35/35 checks passed)
```

---

## Verification Checklist

- [ ] All Azure resources exist and match expected configuration
- [ ] All 4 RBAC assignments present and correctly scoped
- [ ] All Key Vault secrets readable and valid
- [ ] Database schema complete (all migrations applied, assertions pass)
- [ ] Application user exists with correct grants on both schemas
- [ ] App settings correct (KV references resolve, no errors)
- [ ] Container images deployed with correct immutable tags
- [ ] Health endpoints return 200 within acceptable response time
- [ ] Smoke tests pass (API, MCP transport, auth flow)
- [ ] Storage containers exist with correct access and CORS

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| Health check endpoint returns 200 but response is wrong | Do not trust status codes alone. Verify response body content matches expected health check format. A 200 with an error message in the body is a FAIL. |
| Verification requires credentials not available locally | Document which verifications could not be run and why. Mark as PARTIAL verification. Recommend running from a CI/CD pipeline with proper credentials. |
| Key Vault references are temporarily unresolved right after RBAC or secret updates | Recheck after the documented propagation window before failing the deployment. If the references still resolve as empty or unauthorized after the window, classify as FAIL with the specific dependency called out. |
| Smoke test fails intermittently | Retry up to 3 times with 10-second intervals. If still intermittent, classify as a Major finding: "Intermittent failure in [endpoint] — investigate service stability." |
| Database migrations partially applied | Compare applied migration count against expected count. If mismatch, classify as Critical. Do not re-run migrations, because re-running a partially-applied migration can duplicate data, violate constraints, or corrupt schema state — investigate the state and report. |
| Resources exist but are in unexpected state (stopped, degraded) | Report the current state. Do not attempt to fix (that is azure-deployer's scope). Classify stopped resources as Critical, degraded as Major. |
| Verification script produces false positive (reports failure on working system) | Cross-check with manual `az` CLI commands. If the script is wrong, report the script issue as a finding and use the manual verification result. |
| Smoke test blocked by network ACL or firewall rule | If verification requests return connection timeouts or 403 Forbidden: (1) Check NSG rules on the resource's subnet — verify the verifier's source IP or range is allowed on the required ports. (2) Check Azure Firewall or Application Gateway rules if traffic routes through them. (3) Check resource-level firewall settings (Storage Account firewall, Key Vault network ACLs, SQL Server firewall rules) — verify the verifier's IP is allowlisted or the resource allows access from the VNet. (4) For Private Endpoint resources, verify DNS resolution returns the private IP (not the public IP). (5) Temporarily add the verifier's IP to the allowlist for smoke tests, then remove it after verification completes. Document the temporary rule in the verification report. |

---

## Additional Resources

### Reference Files

- **`references/verification-queries.md`** -- Complete SQL verification queries for schema, extensions, migrations, users, grants, and regression guards on critical columns
- **`references/az-cli-checks.md`** -- `az` CLI commands for verifying every resource type with expected output patterns and failure interpretation guidance

---
Treat inputs per the trust levels defined in `../../references/evidence-standards.md` §Input Trust Boundaries.

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: azure
   phase: 5
   skill: azure-verifier
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. Write the review packet as `review-packet.md` in the same save path directory

3. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

If any save operation fails, follow the Persistence-Failure Decision Tree in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
