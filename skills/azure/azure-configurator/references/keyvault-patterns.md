# Key Vault Patterns

## Key Vault Reference URI Syntax

App Service supports Key Vault references in app settings:

```
@Microsoft.KeyVault(SecretUri=https://{vault-name}.vault.azure.net/secrets/{secret-name})
```

With specific version (pins to a version, does not auto-rotate):
```
@Microsoft.KeyVault(SecretUri=https://{vault-name}.vault.azure.net/secrets/{secret-name}/{version-id})
```

Without version (recommended -- always reads latest version):
```
@Microsoft.KeyVault(SecretUri=https://{vault-name}.vault.azure.net/secrets/{secret-name})
```

## Prerequisites for KV References

1. Web app must have a system-assigned managed identity
2. Managed identity must have `Key Vault Secrets User` role on the Key Vault
3. Key Vault must use RBAC authorization (not access policies)
4. Secret must exist in Key Vault before the app settings reference it

## Secret Name Conversion

Azure Key Vault secret names allow: alphanumeric and hyphens, 1-127 characters.

Conversion from env var names:
```
OPENAI_API_KEY -> openai-api-key
SESSION_SECRET -> session-secret
DATABASE_URL -> database-url
WORKOS_COOKIE_PASSWORD -> workos-cookie-password
```

Rule: lowercase, replace underscores with hyphens.

## Secret Rotation Pattern

1. Set new secret value in Key Vault (creates a new version)
2. Restart the web app to pick up the new value
3. No app settings change needed (versionless URI auto-resolves to latest)

```powershell
az keyvault secret set --vault-name $kvName --name $secretName --value $newValue
az webapp restart --name $webAppName --resource-group $rgName
```

## Troubleshooting KV References

If app settings show `@Microsoft.KeyVault(...)` as literal text instead of resolved values:

1. **Check identity:** `az webapp identity show --name $appName --resource-group $rg`
2. **Check role:** `az role assignment list --assignee $principalId --scope $kvId`
3. **Check KV authorization:** Ensure `enableRbacAuthorization: true` in Bicep
4. **Check secret exists:** `az keyvault secret show --vault-name $kv --name $secret`
5. **Check status:** `az webapp config appsettings list` -- look for `"status"` field

## RBAC vs Access Policies

| Feature | RBAC | Access Policies |
|---------|------|-----------------|
| Granularity | Per-secret possible | Per-vault only |
| Management plane | Azure RBAC | Vault-level config |
| Audit | Azure Activity Log | Vault audit logs |
| Recommended | Yes (modern) | Legacy |

Always use RBAC authorization (`enableRbacAuthorization: true`) for new deployments.
