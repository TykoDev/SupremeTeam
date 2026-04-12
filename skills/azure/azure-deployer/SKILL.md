---
name: azure-deployer
description: >-
  This skill should be used when the user or azure-provisioner asks to "deploy to Azure",
  "build and push Docker images", "deploy containers to App Service",
  "push to ACR", "update the backend deployment", "update the frontend deployment",
  "run the deployment pipeline", "execute deployment stages", "deploy Bicep templates",
  "roll out a new version", "deploy database migrations", "run the full deploy",
  "build Docker images for Azure", or mentions container deployment, ACR push,
  web app restart, or deployment execution on Azure.
version: 1.0.0
---

# Azure Deployer

## Purpose

Execute Azure deployments: run the staged PowerShell pipeline, build and push
Docker images to ACR, deploy Bicep templates, apply database migrations, update
web app containers, and perform post-deployment health checks. Handle both full
deployments and targeted update operations.

---

## Core Workflow

### 1. Full Pipeline Deployment

Execute the master orchestrator that runs all stages in sequence:

```powershell
./deploy/deploy.ps1 -EnvFile .env.prod
```

**Prerequisites check before execution:**
- `az` CLI installed, logged in, and set to the correct subscription
- Docker daemon running and accessible (verify with `docker info`)
- `.env.prod` file populated with all required variables
- `POSTGRES_ADMIN_PASSWORD` and `POSTGRES_APP_PASSWORD` set to non-empty values
- `pwsh` (PowerShell 7+) available
- For PostgreSQL configuration: `psql` available locally or Docker accessible for fallback

**Stage execution order (dependency-safe, not numeric):**

| Order | Stage | Script | Purpose |
|-------|-------|--------|---------|
| 1 | 01 | `bootstrap` | Validate env, Azure login, register 6 resource providers, create RG |
| 2 | 02 | `deploy-core` | Deploy `infra/main.bicep`, capture all outputs to state file |
| 3 | 03 | `deploy-roles` | RBAC: AcrPull, Key Vault Secrets User, Storage Blob Contributor |
| 4 | 04 | `configure-postgres` | Server config, auth mode, extensions, migrations, app user |
| 5 | 07 | `configure-secrets` | Push all secrets to Key Vault, verify read-back |
| 6 | 05 | `configure-appservice` | App settings with KV references, web app config |
| 7 | 06 | `configure-storage-blob` | Blob containers, soft delete, versioning, CORS |
| 8 | 08 | `build-deploy` | Docker build, push to ACR, update web apps, health check |

Stage 07 runs before 05 intentionally -- secrets must exist in Key Vault before
app settings can reference them via `@Microsoft.KeyVault()` URIs.

**WhatIf preview mode:** Add `-WhatIf` to preview all changes without applying.
Creates a temporary state file copy, runs all stages in dry-run mode, then discards
the temporary state:
```powershell
./deploy/deploy.ps1 -EnvFile .env.prod -WhatIf
```

**Skipping the build stage:** Add `-SkipBuildDeploy` to provision infrastructure
without building or deploying container images:
```powershell
./deploy/deploy.ps1 -EnvFile .env.prod -SkipBuildDeploy
```

### 2. Bicep Template Deployment

Stage 02 deploys `infra/main.bicep` with parameters from the env file and state:

```powershell
az deployment group create `
    --resource-group $rgName `
    --template-file infra/main.bicep `
    --parameters baseName=$baseName environment=$env location=$location `
                 locationAlias=$locAlias pgAdminUsername=$pgUser `
                 pgAdminPassword=$pgPass pgEnableEntraAuth=$entraAuth `
                 pgEnablePasswordAuth=$pwdAuth `
                 backendContainerImage=$bootstrapBackend `
                 frontendContainerImage=$bootstrapFrontend
```

All Bicep outputs (18 values) are captured and flattened into the state file.
In WhatIf mode, predictable values are synthesized so downstream stages can
preview their configuration.

**Preview infrastructure changes before applying:**
```powershell
az deployment group what-if `
    --resource-group $rgName `
    --template-file infra/main.bicep `
    --parameters baseName=$baseName environment=$env location=$location ...
```

The what-if output shows create, modify, delete, and no-change operations for
every resource. Review this output before applying changes to production.

### 3. Docker Image Build and Push

Three container images are built from dedicated Dockerfiles:

**Backend image:**
```powershell
docker build -f docker/backend.Dockerfile -t "$acrLoginServer/chatlink-backend:$tag" .
az acr login --name $acrName
docker push "$acrLoginServer/chatlink-backend:$tag"
```

**Frontend image (with build-time API URLs):**
```powershell
docker build -f docker/frontend.Dockerfile `
    --build-arg FRONTEND_API_URL="https://$backendHostname/api" `
    --build-arg FRONTEND_WS_URL="wss://$backendHostname/ws" `
    -t "$acrLoginServer/chatlink-frontend:$tag" .
docker push "$acrLoginServer/chatlink-frontend:$tag"
```

**MCP frontend image:**
```powershell
docker build -f docker/frontend-mcp.Dockerfile `
    --build-arg FRONTEND_MCP_API_URL="https://$backendHostname/api" `
    --build-arg FRONTEND_MCP_ADMIN_EMAIL=$adminEmail `
    -t "$acrLoginServer/chatlink-frontend-mcp:$tag" .
docker push "$acrLoginServer/chatlink-frontend-mcp:$tag"
```

**Image tag strategy:**
- Use `IMAGE_TAG` env var if explicitly set
- Otherwise auto-generate a UTC timestamp tag: `yyyyMMddHHmmss` (e.g., `20260410143022`)
- Override per-service with `BACKEND_IMAGE_TAG`, `FRONTEND_IMAGE_TAG`, `FRONTEND_MCP_IMAGE_TAG`
- Production deployments must use immutable tags -- never `latest`
- Timestamp tags are sortable, human-readable, and collision-free

**Frontend build args are baked into the static build.** Changing API endpoints
requires a frontend rebuild and redeployment -- they cannot be changed at runtime.

### 4. Web App Container Update

After pushing images, update each web app's container configuration and restart:

```powershell
az webapp config container set `
    --name $webAppName `
    --resource-group $rgName `
    --container-image-name "$acrLoginServer/$imageName:$tag" `
    --container-registry-url "https://$acrLoginServer"

az webapp restart --name $webAppName --resource-group $rgName
```

The web app pulls the new image from ACR using its system-assigned managed identity
(via the `AcrPull` role assignment). No ACR credentials are stored in app settings.

### 5. Targeted Service Updates

For day-2 operations, update individual services without re-provisioning infrastructure.
Each update script loads the existing state file, builds a single image, pushes to
ACR, updates the web app container config, restarts, and runs a health check.

**Backend only:**
```powershell
./deploy/update-backend.ps1 -EnvFile .env.prod
# Uses BACKEND_IMAGE_TAG or auto-generates timestamp
```

**Frontend only:**
```powershell
./deploy/update-frontend.ps1 -EnvFile .env.prod
# Passes FRONTEND_API_URL and FRONTEND_WS_URL as build args
```

**MCP frontend only:**
```powershell
./deploy/update-frontend-mcp.ps1 -EnvFile .env.prod
# Passes FRONTEND_MCP_API_URL and FRONTEND_MCP_ADMIN_EMAIL as build args
```

### 6. Delta Deployment

For targeted infrastructure changes with built-in safety guards:

```powershell
# Preview mode (default -- shows what would change)
./deploy/temp-deploy-impl-delta.ps1 -EnvFile .env.prod -Mode full-delta

# Apply mode (executes changes after preview)
./deploy/temp-deploy-impl-delta.ps1 -EnvFile .env.prod -Mode full-delta -Apply
```

**Available modes:**
- `auth-delta`: Full auth migration to Entra-only (stages 02, 03, 04, 07, 05 + all apps)
- `frontend-only`: Update both frontend apps without touching backend or infrastructure
- `full-delta`: Run Bicep what-if, then stages 04, 07, 05, and optionally 08

**Safety guards in delta scripts:**
- Hard-coded resource group and web app name validation prevents accidental execution
  against wrong environments
- Immutable image tag requirement rejects `latest`
- Preview-then-apply pattern: runs all stages with `-WhatIf:$true` first, then with
  `-WhatIf:$false` only if `-Apply` is provided
- Post-apply smoke checks verify all public URLs, MCP transport, schema, and auth

### 7. Post-Deployment Health Checks

After container updates, verify deployment succeeded:

**Immediate checks (after 15-second startup wait):**
1. HTTP GET to `/health` endpoint (backend) -- expect 200 OK
2. HTTP GET to `/` endpoint (frontends) -- expect 200 OK with HTML content
3. Fallback to `.azurewebsites.net` hostname if custom domain returns error

**Extended smoke tests (delta deploy):**
- HTTP checks for all public URLs (e.g., `chat.tykotech.eu`, `tykotech.eu`)
- MCP transport mode verification (expects `streamable-http`)
- PostgreSQL auth configuration verification
- Schema validation (critical tables and columns exist)
- Public API endpoint validation (`/api/public/tiers`)
- OAuth authorize flow redirect chain verification
- Admin API bearer token smoke checks
- Deployed image tag verification against target tag

**Rollback procedure:** If health checks fail, roll back to the previous image tag:
```powershell
az acr repository show-tags --name $acrName --repository chatlink-backend --orderby time_desc
az webapp config container set --name $webAppName --resource-group $rgName `
    --container-image-name "$acrLoginServer/chatlink-backend:$previousTag"
az webapp restart --name $webAppName --resource-group $rgName
```

---

## Deployment Checklist

- [ ] `.env.prod` file complete with all required variables
- [ ] Docker daemon running and accessible
- [ ] `az` CLI logged in to correct subscription and tenant
- [ ] Previous state file available (or starting fresh with full deploy)
- [ ] Image tags set (or auto-generated from UTC timestamp)
- [ ] WhatIf preview reviewed before applying to production
- [ ] Health checks pass after deployment
- [ ] Image tag verified on deployed web apps
- [ ] Deploy runner firewall rule removed from PostgreSQL (if applicable)

---

## Additional Resources

### Reference Files

- **`references/docker-patterns.md`** -- Dockerfile best practices, multi-stage builds,
  build arg patterns, ACR login methods, and image tag strategies
- **`references/troubleshooting.md`** -- Common deployment failures, health check
  debugging, container startup issues, and rollback procedures

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: azure
   phase: 4
   skill: azure-deployer
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
