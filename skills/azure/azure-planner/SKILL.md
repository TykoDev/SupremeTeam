---
name: azure-planner
description: >-
  This skill should be used when the user or azure-provisioner asks to "plan an Azure deployment",
  "create a deployment strategy", "design deployment stages", "plan environment
  configuration", "define deployment pipeline", "create deployment runbook",
  "plan database migrations", "design secret management strategy",
  "plan RBAC assignments", "create deployment checklist", "organize env vars
  for Azure", "plan staged rollout", or mentions deployment sequencing,
  state management, or deployment dependencies for Azure.
version: 1.0.0
---

# Azure Deployment Planner

## Purpose

Plan complete Azure deployment strategies including stage sequencing, environment
variable organization, secret management, database migration planning, RBAC
assignment mapping, and state management. Produce actionable deployment runbooks
that PowerShell pipelines can execute.

---

## Core Workflow

### 1. Deployment Stage Design

Design a numbered, dependency-ordered stage pipeline. Each stage is a self-contained
PowerShell script that reads shared state and writes its results back. Stages are
numbered for clarity but may execute out of numeric order when dependencies require it.

**Standard stage sequence:**

| Stage | Script | Purpose | Depends On |
|-------|--------|---------|------------|
| 01 | `bootstrap` | Validate env, Azure login, register providers, create RG | `.env` file |
| 02 | `deploy-core` | Deploy Bicep templates, capture resource outputs | Stage 01 state |
| 03 | `deploy-roles` | Assign RBAC roles (ACR pull, KV secrets, storage) | Stage 02 outputs (principal IDs) |
| 04 | `configure-postgres` | Server config, auth, extensions, migrations, app user | Stage 02 outputs (PG FQDN) |
| 07 | `configure-secrets` | Push secrets to Key Vault | Stage 02 outputs (KV name) + Stage 04 (DB URL) |
| 05 | `configure-appservice` | App settings with KV references | Stages 02, 04, 07 |
| 06 | `configure-storage` | Blob containers, CORS, soft delete | Stage 02 outputs |
| 08 | `build-deploy` | Docker build, push to ACR, update web apps | All prior stages |
| 09 | `custom-domains` | DNS, hostname binding, managed certificate | Stage 08 (separate run) |

**Critical ordering constraint:** Stage 07 (secrets) runs before Stage 05 (app settings)
because Key Vault secrets must exist before app settings can reference them via
`@Microsoft.KeyVault()` URIs. If this order is reversed, all KV reference app settings
will fail to resolve.

**Stage design principles:**
- Each stage is independently re-runnable (idempotent)
- Each stage validates its prerequisites from the state file before executing
- Each stage writes its results to the shared state file
- Each stage respects a `-WhatIf` switch for dry-run mode
- Failure in any stage halts the pipeline cleanly without corrupting state

### 2. State Management Design

Plan a JSON-based state file (`deploy/.state/context.json`) as the coupling
mechanism between stages. The state file acts as a contract -- each stage
declares what it reads and what it writes.

**State accumulation by stage:**

```
Stage 01 writes: subscriptionId, tenantId, location, locationAlias, environment,
                 baseName, resourceGroupName, envFile
Stage 02 writes: acrName, acrId, acrLoginServer, backendWebAppName, backendWebAppId,
                 backendWebAppHostname, backendPrincipalId, frontendWebAppName,
                 frontendWebAppHostname, frontendPrincipalId, keyVaultName,
                 keyVaultId, storageAccountName, storageAccountId,
                 postgresServerName, postgresServerFqdn, postgresDatabaseName
Stage 03 writes: role assignment confirmations
Stage 04 writes: databaseUrl, postgresAuthMode, postgresEntraAdminOid
Stage 07 writes: list of secret names stored in Key Vault
Stage 05 writes: app settings confirmation
```

**State file design rules:**
- Each stage reads only the keys it needs -- never the entire file
- Each stage appends its outputs without overwriting prior entries
- WhatIf mode creates a temporary state copy and discards it after preview
- State file lives in `deploy/.state/` which is `.gitignore`-protected
- State contains resource names, IDs, and hostnames but never secret values
- A helper function (`Read-StateFile`/`Write-StateFile`/`Get-StateValue`) provides
  typed access to state values

### 3. Environment Variable Classification

Classify every env var into exactly one of four categories. This classification
determines where the variable is stored and how it reaches the application:

| Category | Example | Destination | Security |
|----------|---------|-------------|----------|
| **Deployment-only** | `AZ_SUBSCRIPTION_ID`, `DEPLOY_WHATIF`, `IMAGE_TAG`, `AZ_TENANT_ID` | Deploy scripts only | Not sensitive |
| **Provisioning** | `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_APP_PASSWORD` | Deploy scripts + Bicep params | Sensitive but not in KV |
| **Runtime non-sensitive** | `PORT`, `CACHE_BACKEND`, `RLM_ENABLED`, `ADMIN_EMAIL` | Plain text app settings | Not sensitive |
| **Runtime secrets** | `OPENAI_API_KEY`, `DATABASE_URL`, `SESSION_SECRET` | KV secrets + KV ref app settings | Sensitive |

**Secret detection strategy (dual approach):**

1. **Explicit allow-list:** Enumerate all known secrets by name -- `OPENAI_API_KEY`,
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_COMPATIBLE_KEY`,
   `AZURE_OPENAI_KEY`, `SESSION_SECRET`, `JWT_SECRET`, `WORKOS_API_KEY`, `WORKOS_CLIENT_ID`,
   `WORKOS_COOKIE_PASSWORD`, `DATABASE_URL`, `BRAVE_API_KEY`, `TAVILY_API_KEY`

2. **Pattern match fallback:** Any variable name ending with `_KEY`, `_SECRET`,
   `_PASSWORD`, or `_TOKEN` is treated as a secret even if not on the explicit list.
   This catches new secrets added to the env file without updating the detection logic.

**Exclusion list (deployment-only, never in app settings or KV):**
`AZ_SUBSCRIPTION_ID`, `AZ_TENANT_ID`, `AZ_LOCATION`, `AZ_LOCATION_ALIAS`, `AZ_ENV`,
`AZ_RESOURCE_GROUP`, `BASE_NAME`, `DEPLOY_WHATIF`, `IMAGE_TAG`, `BACKEND_IMAGE_TAG`,
`FRONTEND_IMAGE_TAG`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD`,
`POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD`, `POSTGRES_PSQL_PATH`,
`POSTGRES_PSQL_DOCKER_IMAGE`, `BACKEND_BOOTSTRAP_IMAGE`, `FRONTEND_BOOTSTRAP_IMAGE`

### 4. RBAC Assignment Planning

Map every managed identity role assignment needed for the deployment. Assignments
use the principle of least privilege -- each identity gets only the roles it needs.

| Principal | Role | Scope | Purpose | Verification |
|-----------|------|-------|---------|-------------|
| Backend MI | `AcrPull` | ACR resource ID | Pull container images at startup | `az role assignment list` |
| Frontend MI | `AcrPull` | ACR resource ID | Pull container images at startup | `az role assignment list` |
| Backend MI | `Key Vault Secrets User` | KV resource ID | Read secrets via KV references | `az role assignment list` |
| Backend MI | `Storage Blob Data Contributor` | Storage resource ID | Read/write blob data for file uploads | `az role assignment list` |

**Idempotent assignment pattern:** Before creating a role assignment, query for an
existing assignment with the same principal, role, and scope. Only create if no
match exists. This prevents errors on re-deployment and avoids duplicate assignments.

**Role assignment timing:** RBAC assignments (Stage 03) must complete before
app settings (Stage 05) because the backend web app needs `Key Vault Secrets User`
to resolve KV reference app settings on restart.

### 5. Database Migration Planning

Plan ordered, tracked, checksummed migrations across multiple schemas and source
directories:

**Migration registry (execution order):**

| Order | Source | Migration | Schema |
|-------|--------|-----------|--------|
| 1 | (inline) | Extension enablement | public |
| 2 | `src/services/storage/migrations/` | `001_initial_schema.sql` | public |
| 3 | `src/services/cache/migrations/` | `001_postgres_cache.sql` | public |
| 4 | `src/services/storage/migrations/` | `002_mcp_schema.sql` | mcp |
| 5 | `src/services/storage/migrations/` | `003_product_sku_matrix.sql` | mcp |
| 6 | `src/services/storage/migrations/` | `004_user_tags_and_chatlink_tiers.sql` | mcp |
| 7 | `src/services/storage/migrations/` | `005_frontend_metrics.sql` | public |
| 8 | `src/services/storage/migrations/` | `006_stripe_billing_linkage.sql` | mcp |
| 9 | `src/services/storage/migrations/` | `007_tier_capabilities_and_catalog.sql` | mcp |

**Tracking mechanism:**
- `public.schema_migrations` table records version name, SHA256 checksum, and timestamp
- Before executing: compute checksum, check if already applied
- If applied with matching checksum: skip (idempotent)
- If applied with different checksum: ERROR (file modified after application)
- If not applied: execute, then record

**Post-migration assertions:** Run validation queries that confirm critical tables,
columns, and relationships exist. Assertions catch partial application or silent failures.

### 6. Rollout Strategy Planning

Plan multiple deployment modes for different operational scenarios:

- **Full deploy** (`deploy.ps1`): All stages in sequence for fresh environments.
  Complete infrastructure provisioning through to container deployment.
- **Update scripts** (`update-backend.ps1`, `update-frontend.ps1`,
  `update-frontend-mcp.ps1`): Build, push, and restart a single service without
  re-provisioning infrastructure. For day-2 code deployments.
- **Delta deploy** (`temp-deploy-impl-delta.ps1`): Targeted infrastructure changes
  with preview-then-apply pattern. Safety guards prevent accidental execution
  against wrong environments. Supports modes: `auth-delta`, `frontend-only`, `full-delta`.
- **WhatIf preview**: Every stage supports `-WhatIf` for dry-run. The full pipeline
  can preview all changes without touching any Azure resources.

### 7. Deployment Runbook Output

Produce a runbook document containing:

- **Prerequisites:** Required tools (`az`, `docker`, `psql`/Docker fallback, `pwsh 7+`)
- **Environment file template:** All required variables with descriptions and defaults
- **Stage execution order:** Numbered stages with dependency notes and expected duration
- **Per-stage verification:** What to check after each stage succeeds
- **Rollback procedures:** How to reverse each stage's changes if needed
- **Post-deployment smoke tests:** Health check URLs, expected responses, timeout values
- **Day-2 operations:** Update scripts for routine code deployments

---

## Planning Checklist

- [ ] All stages numbered and dependency-ordered
- [ ] State file schema documented with per-stage contributions
- [ ] Every env var classified into exactly one category
- [ ] Secret detection covers both explicit list and pattern matching
- [ ] RBAC assignments are minimal and idempotent
- [ ] Migration order verified with dependency analysis
- [ ] WhatIf mode planned for every stage
- [ ] Update scripts planned for day-2 operations
- [ ] Rollback strategy documented per stage
- [ ] Health check endpoints defined for post-deploy verification

---

## Additional Resources

### Reference Files

- **`references/env-var-catalog.md`** -- Complete catalog of environment variables
  with classification, default values, and destination mapping
- **`references/stage-dependencies.md`** -- Detailed stage dependency graph,
  state file schema, and inter-stage data flow documentation
- **`references/migration-strategy.md`** -- Database migration patterns, checksum
  tracking, multi-schema support, and assertion design

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: azure
   phase: 1
   skill: azure-planner
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
