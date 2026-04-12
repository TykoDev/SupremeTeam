# App Service Settings Reference

## Bulk Update Pattern

Write settings to a temp JSON file and apply:

```powershell
$settings = @{
    PORT = "8000"
    CACHE_BACKEND = "postgres"
    OPENAI_API_KEY = "@Microsoft.KeyVault(SecretUri=https://$kvName.vault.azure.net/secrets/openai-api-key)"
}

$tempFile = [System.IO.Path]::GetTempFileName()
try {
    $settings | ConvertTo-Json | Set-Content $tempFile
    az webapp config appsettings set `
        --name $webAppName `
        --resource-group $rgName `
        --settings "@$tempFile"
} finally {
    Remove-Item $tempFile -ErrorAction SilentlyContinue
}
```

## Forced Settings

These settings are always set regardless of .env content:

| Setting | Value | Reason |
|---------|-------|--------|
| `WEBSITES_PORT` | `8000` | Container listen port |
| `PORT` | `8000` | Application listen port |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `false` | Container uses own filesystem |
| `DOCKER_ENABLE_CI` | `false` | No continuous deployment from ACR |
| `POSTGRES_SSL` | `true` | Force SSL on DB connections |

## Frontend App Settings

Frontend web apps need minimal settings:

| Setting | Value |
|---------|-------|
| `WEBSITES_PORT` | `80` |
| `API_BASE_URL` | `https://{backendHostname}/api` |
| `WS_BASE_URL` | `wss://{backendHostname}/ws` |
| `BACKEND_BASE_URL` | `https://{backendHostname}` |

## Build-Time Frontend Settings

Passed as Docker build args during `08-build-deploy`:

| Build Arg | Source | Purpose |
|-----------|--------|---------|
| `FRONTEND_API_URL` | Env or computed from backend hostname | API endpoint for frontend build |
| `FRONTEND_WS_URL` | Env or computed from backend hostname | WebSocket endpoint for frontend build |
| `FRONTEND_MCP_API_URL` | Env or computed | MCP frontend API endpoint |
| `FRONTEND_MCP_ADMIN_EMAIL` | `ADMIN_EMAIL` env var | Admin email for MCP frontend |

## Container Configuration

```powershell
az webapp config container set `
    --name $webAppName `
    --resource-group $rgName `
    --container-image-name "$acrLoginServer/$imageName:$tag" `
    --container-registry-url "https://$acrLoginServer"
```

## Health Check Configuration

```powershell
az webapp config set `
    --name $webAppName `
    --resource-group $rgName `
    --health-check-path "/health" `  # backend
    --always-on true `
    --min-tls-version "1.2" `
    --ftps-state Disabled
```

## Deployment Slot Settings (Sticky)

For settings that should NOT swap between deployment slots, mark them as slot settings:

```powershell
az webapp config appsettings set `
    --name $webAppName `
    --resource-group $rgName `
    --slot-settings "AZ_ENV=prod"
```

Common slot-sticky settings: `AZ_ENV`, `DATABASE_URL`, `FRONTEND_ORIGIN`
