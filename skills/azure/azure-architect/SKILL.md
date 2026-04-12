---
name: azure-architect
description: >-
  This skill should be used when the user or azure-provisioner asks to "design Azure infrastructure",
  "create Bicep templates", "plan Azure resource topology", "define Azure naming
  conventions", "architect an Azure deployment", "design IaC for Azure",
  "create Azure resource modules", "define Azure networking layout",
  "plan App Service architecture", "design PostgreSQL Flexible Server setup",
  "create ACR topology", "plan Key Vault structure", or mentions Bicep modules,
  Azure resource groups, or infrastructure-as-code for Azure.
version: 1.0.0
---

# Azure Infrastructure Architect

## Purpose

Design Azure infrastructure architectures using Bicep IaC templates. Produce
resource topology designs, naming conventions, module decomposition, parameter
strategies, and deployment output contracts suitable for staged PowerShell
deployment pipelines.

---

## Core Workflow

### 1. Requirements Gathering

Collect the following from the user or existing project artifacts:

- **Application type:** Containerized (App Service, Container Apps), serverless
  (Functions), static (Static Web Apps), or hybrid. Containerized Linux App Service
  is the default for Deno/Node backends with Docker images.
- **Compute tier:** App Service Plan SKU determines cost, scaling, and features.
  B2/Basic suits small production; S1/Standard adds deployment slots and auto-scale;
  P1v3/Premium adds VNet integration and higher performance.
- **Data tier:** PostgreSQL Flexible Server for relational data with pgvector
  extension support. Burstable B1ms for light production; General Purpose D2ds_v5
  for steady workloads requiring vector search at scale.
- **Authentication model:** System-assigned managed identity for service-to-service
  auth. Entra ID for PostgreSQL (token-based, no stored passwords). Password auth
  as fallback or for development environments.
- **Caching layer:** PostgreSQL-backed cache eliminates a separate Redis dependency.
  Redis for high-throughput scenarios. Deno KV as local fallback.
- **Secret management:** Key Vault with RBAC authorization (never access policies).
  All API keys, passwords, and tokens stored as KV secrets, referenced from App
  Service via `@Microsoft.KeyVault()` URIs.
- **Container registry:** ACR Basic SKU for small teams (< 5 images, 10 GB storage).
  Admin user disabled; pull via managed identity `AcrPull` role.
- **Storage requirements:** StorageV2 with Standard_LRS for file uploads and
  attachments. Private container access, blob soft delete (7 days), versioning
  enabled, CORS configured for frontend origins.
- **Environment strategy:** Separate resource groups per environment (`prod`,
  `staging`, `dev`). Shared subscription is acceptable; separate subscriptions
  for strict isolation.
- **Budget constraints:** SKU selection is the primary cost lever. Burstable
  PostgreSQL + Basic App Service + Basic ACR minimizes spend for small production.

### 2. Resource Topology Design

Produce a resource map covering all Azure resources and their Bicep module files:

| Concern | Azure Resource | Module File | Key Properties |
|---------|---------------|-------------|----------------|
| Compute | App Service Plan | `app_service_plan.bicep` | Linux, reserved, SKU configurable |
| Backend | Web App (API) | `web_app.bicep` | System MI, container, HTTPS-only |
| Frontend | Web App (SPA) | `web_app.bicep` (reused) | System MI, container, HTTPS-only |
| Database | PostgreSQL Flexible Server | `postgres_flexible_server.bicep` | v16, pgvector, dual auth |
| Secrets | Key Vault | `key_vault.bicep` | RBAC auth, soft delete 90 days |
| Registry | Container Registry | `acr.bicep` | Basic, admin disabled |
| Storage | Storage Account | `storage_account.bicep` | StorageV2, no public blob |
| Identity | Managed Identity | Embedded in `web_app.bicep` | System-assigned per app |

The web_app module is parameterized and instantiated multiple times (backend, frontend,
MCP frontend) with different names, container images, and health check paths.

### 3. Naming Convention

Apply a deterministic naming scheme using Bicep `uniqueString()` to ensure global
uniqueness while keeping names predictable within a subscription/RG pair:

```bicep
var suffix = take(uniqueString(subscription().subscriptionId, resourceGroup().id), 6)
```

| Resource | Pattern | Max Length | Character Rules |
|----------|---------|-----------|-----------------|
| Resource Group | `{base}-{env}-{locAlias}-rg` | 90 | Alphanumeric, `-_.()`  |
| App Service Plan | `{base}-{env}-{locAlias}-asp` | 60 | Alphanumeric, `-` |
| Web App | `{base}-{env}-{locAlias}-{role}-{suffix}` | 60 | Alphanumeric, `-` |
| ACR | `{base}{locAlias}{suffix}acr` | 50 | Alphanumeric only |
| Storage | `{base}{locAlias}{suffix}st` | 24 | Lowercase alphanumeric only |
| Key Vault | `{base}-{locAlias}-{suffix}-kv` | 24 | Alphanumeric, `-` |
| PostgreSQL | `{base}-{env}-{locAlias}-pg-{suffix}` | 63 | Lowercase alphanumeric, `-` |
| Database | `{base}` (lowercase) | 63 | Lowercase alphanumeric, `-_` |

**Validation:** Before deploying, compute the actual name length for each resource
and verify it falls within the maximum. Storage and Key Vault (24-char limit) are
the most likely to overflow with long base names.

### 4. Module Decomposition

Each Azure resource type gets its own Bicep module under `infra/modules/`:

**Module interface contract:**
- Accept only the parameters the module needs (principle of least privilege)
- Use `@description()` decorator on every parameter for self-documenting templates
- Use `@secure()` decorator on all password, key, and token parameters
- Output `id`, `name`, and any values consumed by downstream stages or other modules
- Apply consistent tagging via a `tags` object parameter

**Root template orchestration (`infra/main.bicep`):**
- Declare all shared parameters (baseName, environment, location, credentials)
- Compute all naming variables and the suffix from `uniqueString()`
- Merge base tags with user-supplied tags via `union()`
- Instantiate each module, passing computed names and cross-module outputs
- Re-export all module outputs as flat top-level outputs for the deploy pipeline

**Cross-module dependencies:**
- ACR outputs its login server -> passed to web app modules for container config
- Web app outputs its principal ID -> consumed by deploy scripts for RBAC
- PostgreSQL outputs its FQDN -> consumed by deploy scripts for connection strings
- Key Vault outputs its name -> consumed by deploy scripts for secret URIs

### 5. Parameter Strategy

Separate parameters into three tiers to prevent leaking deployment-only values
into runtime configuration:

1. **Bicep parameters** (passed inline by deploy scripts via `--parameters key=value`):
   `baseName`, `environment`, `location`, `locationAlias`, `pgAdminUsername`,
   `pgAdminPassword` (secure), `pgEnableEntraAuth`, `pgEnablePasswordAuth`,
   `backendContainerImage`, `frontendContainerImage`. These drive resource creation
   and initial configuration.

2. **Parameter files** (`infra/parameters/{env}.bicepparam`): Serve as reference
   documentation and enable direct `az deployment group create --parameters @file`
   usage outside the pipeline. Not consumed by the deploy scripts (which pass
   parameters inline).

3. **Environment variables** (`.env.{env}`): All runtime config and secrets.
   Consumed by deploy scripts for Key Vault population and app settings. Never
   passed to Bicep. Classified as deployment-only, provisioning, runtime non-sensitive,
   or runtime secrets.

### 6. Output Contract

Define Bicep outputs that the deployment pipeline state file consumes. Every output
must be explicitly declared -- undeclared values are invisible to the deploy scripts:

```bicep
// Resource identifiers (for RBAC scope)
output acrId string = acr.outputs.id
output keyVaultId string = keyVault.outputs.id
output storageAccountId string = storageAccount.outputs.id

// Resource names (for az CLI commands)
output acrName string = acr.outputs.name
output backendWebAppName string = backendWebApp.outputs.name
output keyVaultName string = keyVault.outputs.name

// Hostnames (for app settings and DNS)
output backendWebAppHostname string = backendWebApp.outputs.defaultHostname
output frontendWebAppHostname string = frontendWebApp.outputs.defaultHostname

// Identity (for RBAC assignments)
output backendPrincipalId string = backendWebApp.outputs.principalId
output frontendPrincipalId string = frontendWebApp.outputs.principalId

// Registry (for docker push)
output acrLoginServer string = acr.outputs.loginServer

// Database (for connection string)
output postgresDatabaseName string = postgresDatabase.outputs.name
output postgresServerFqdn string = postgresServer.outputs.fqdn
```

### 7. Security Baseline

Apply these security defaults to every architecture:

- **HTTPS only** on all web apps with minimum TLS 1.2
- **FTPS disabled** on all web apps (no FTP access)
- **Managed identity** for all service-to-service authentication
- **ACR admin disabled** -- pull via MI role assignment only
- **Key Vault RBAC** -- never access policies
- **PostgreSQL SSL required** with minimum TLS 1.2
- **Storage HTTPS only** with no public blob access
- **Soft delete** on Key Vault (90 days) and blob storage (7 days)
- **No secrets in Bicep outputs** -- sensitive values flow through Key Vault only

---

## Design Checklist

- [ ] Every module is idempotent and redeployable
- [ ] Managed identity is system-assigned on compute resources
- [ ] ACR admin user is disabled; pull via managed identity
- [ ] Key Vault uses RBAC authorization, not access policies
- [ ] Soft delete and purge protection on Key Vault (90-day retention)
- [ ] Storage account: no public blob access, HTTPS-only, TLS 1.2+
- [ ] PostgreSQL: require_secure_transport ON, min TLS 1.2
- [ ] Blob soft delete (7 days) and versioning enabled
- [ ] All names respect Azure length and character constraints
- [ ] Tags propagated to every resource
- [ ] All Bicep outputs declared for downstream pipeline consumption
- [ ] No secure values leaked in Bicep outputs
- [ ] Cross-module dependencies satisfied through parameter passing

---

## Anti-Patterns to Avoid

- Hardcoding resource names instead of computing from `uniqueString()`
- Using Key Vault access policies instead of RBAC
- Enabling ACR admin user in production
- Omitting `@secure()` on password parameters
- Creating resources without output declarations (blocks downstream automation)
- Mixing deployment-only env vars into Bicep parameters
- Leaking secure values (passwords, keys) in Bicep outputs
- Using `latest` as default container image tag
- Skipping tag propagation on child resources

---

## Additional Resources

### Reference Files

- **`references/bicep-patterns.md`** -- Module design patterns, conditional deployments,
  cross-module dependencies, and advanced Bicep techniques
- **`references/azure-skus.md`** -- SKU selection guide for App Service, PostgreSQL,
  ACR, Storage, and Key Vault with cost/performance tradeoffs
- **`references/naming-rules.md`** -- Complete Azure resource naming constraints,
  character limits, and uniqueString() usage patterns

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: azure
   phase: 2
   skill: azure-architect
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
