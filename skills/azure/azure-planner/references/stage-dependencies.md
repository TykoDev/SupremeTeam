# Stage Dependencies and State Flow

## Dependency Graph

```
01-bootstrap
    |
    v
02-deploy-core
    |
    +---> 03-deploy-roles
    |         |
    +---> 04-configure-postgres ---+
    |                              |
    +---> 07-configure-secrets <---+
              |
              v
         05-configure-appservice
              |
         06-configure-storage-blob
              |
         08-build-deploy
              |
         09-configure-custom-domains (separate run)
```

## State File Schema

The state file (`deploy/.state/context.json`) accumulates values across stages:

### After Stage 01 (bootstrap)
```json
{
  "stage": "01-bootstrap",
  "envFile": ".env.prod",
  "subscriptionId": "...",
  "tenantId": "...",
  "location": "swedencentral",
  "locationAlias": "swc",
  "environment": "prod",
  "baseName": "chatlink",
  "resourceGroupName": "chatlink-prod-swc-rg"
}
```

### After Stage 02 (deploy-core)
Adds all Bicep outputs:
```json
{
  "acrName": "chatlinkswcXXXXXXacr",
  "acrId": "/subscriptions/.../Microsoft.ContainerRegistry/registries/...",
  "acrLoginServer": "chatlinkswcXXXXXX.azurecr.io",
  "backendWebAppName": "chatlink-prod-swc-api-XXXXXX",
  "backendWebAppId": "/subscriptions/.../Microsoft.Web/sites/...",
  "backendWebAppHostname": "chatlink-prod-swc-api-XXXXXX.azurewebsites.net",
  "backendPrincipalId": "...",
  "frontendWebAppName": "chatlink-prod-swc-web-XXXXXX",
  "frontendWebAppHostname": "chatlink-prod-swc-web-XXXXXX.azurewebsites.net",
  "frontendPrincipalId": "...",
  "keyVaultName": "chatlink-swc-XXXXXX-kv",
  "keyVaultId": "/subscriptions/.../Microsoft.KeyVault/vaults/...",
  "storageAccountName": "chatlinkswcXXXXXXst",
  "storageAccountId": "/subscriptions/.../Microsoft.Storage/storageAccounts/...",
  "postgresServerName": "chatlink-prod-swc-pg-XXXXXX",
  "postgresServerFqdn": "chatlink-prod-swc-pg-XXXXXX.postgres.database.azure.com",
  "postgresDatabaseName": "chatlink"
}
```

### After Stage 04 (configure-postgres)
```json
{
  "databaseUrl": "postgresql://chatlink_app:...@...postgres.database.azure.com:5432/chatlink?sslmode=require",
  "postgresAuthMode": "password",
  "postgresEntraAdminOid": "..." // if Entra mode
}
```

## Inter-Stage Data Flow

| Producer | Consumer | Data |
|----------|----------|------|
| 01 | 02 | baseName, environment, location, locationAlias |
| 02 | 03 | acrId, keyVaultId, storageAccountId, principalIds |
| 02 | 04 | postgresServerName, postgresDatabaseName |
| 04 | 07 | databaseUrl (stored in KV) |
| 02, 07 | 05 | keyVaultName (for KV reference URIs), all resource hostnames |
| 02 | 06 | storageAccountName, backend hostnames (for CORS) |
| 02 | 08 | acrLoginServer, webAppNames |

## WhatIf Mode

When `-WhatIf:$true`:
- Stage 01: Logs actions, skips provider registration
- Stage 02: Runs `az deployment group what-if`, synthesizes predictable outputs
- Stage 03: Logs role assignments without creating them
- Stage 04: Logs all SQL operations without executing
- Stage 05-07: Logs all configurations without applying
- Stage 08: Skips Docker build/push entirely
