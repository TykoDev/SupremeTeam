# Azure Resource Naming Rules

## Character and Length Constraints

| Resource | Min | Max | Allowed Characters | Case |
|----------|-----|-----|-------------------|------|
| Resource Group | 1 | 90 | Alphanumeric, `-`, `_`, `.`, `(`, `)` | Case-insensitive |
| App Service Plan | 1 | 60 | Alphanumeric, `-` | Case-insensitive |
| Web App | 2 | 60 | Alphanumeric, `-` | Case-insensitive |
| Container Registry | 5 | 50 | Alphanumeric only | Case-insensitive |
| Storage Account | 3 | 24 | Lowercase alphanumeric only | Lowercase |
| Key Vault | 3 | 24 | Alphanumeric, `-` | Case-insensitive |
| PostgreSQL Server | 3 | 63 | Lowercase alphanumeric, `-` | Lowercase |
| PostgreSQL Database | 1 | 63 | Lowercase alphanumeric, `-`, `_` | Case-sensitive |

## Global Uniqueness Requirements

These resources require globally unique names:
- Web App (resolves to `{name}.azurewebsites.net`)
- Container Registry (resolves to `{name}.azurecr.io`)
- Storage Account (resolves to `{name}.blob.core.windows.net`)
- Key Vault (resolves to `{name}.vault.azure.net`)
- PostgreSQL Server (resolves to `{name}.postgres.database.azure.com`)

## uniqueString() Behavior

`uniqueString()` generates a deterministic 13-character base-64 hash from input strings.
Common pattern: `take(uniqueString(subscription().subscriptionId, resourceGroup().id), 6)`

- Same inputs always produce the same output
- Different subscriptions or resource groups produce different outputs
- Safe for idempotent redeployment
- Trim to 6 characters for readability while maintaining practical uniqueness

## Naming Convention Pattern

```
{baseName}-{environment}-{locationAlias}-{role}-{suffix}
```

Where:
- `baseName`: Project name (e.g., `chatlink`)
- `environment`: `prod`, `staging`, `dev`
- `locationAlias`: Short region code (`weu`, `swc`, `eus2`)
- `role`: Resource purpose (`api`, `web`, `pg`, `asp`)
- `suffix`: 6-char uniqueString hash

## Location Alias Map

| Azure Region | Alias |
|-------------|-------|
| westeurope | weu |
| swedencentral | swc |
| eastus2 | eus2 |
| northeurope | neu |
| westus2 | wus2 |

Define the alias in `.env` as `AZ_LOCATION_ALIAS` -- it is not derived automatically.
