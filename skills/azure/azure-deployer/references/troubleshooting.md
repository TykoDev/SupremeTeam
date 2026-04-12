# Deployment Troubleshooting

## Common Failures and Fixes

### Bicep Deployment Fails

**Symptom:** `az deployment group create` returns error
**Check:**
```powershell
az deployment group show --name $deploymentName --resource-group $rgName --query properties.error
```
**Common causes:**
- Resource name conflicts (globally unique names already taken)
- SKU not available in selected region
- Quota exceeded (e.g., too many App Service Plans)
- Parameter type mismatch

**Fix:** Review the error, adjust parameters, and redeploy. Bicep deployments are idempotent.

### ACR Push Fails: Unauthorized

**Symptom:** `docker push` returns 401
**Fix:**
```powershell
az acr login --name $acrName  # Re-authenticate
docker push ...
```

### Web App Returns 502 After Deploy

**Symptom:** Health check fails with 502 Bad Gateway
**Check:**
```powershell
# View container logs
az webapp log tail --name $webAppName --resource-group $rgName

# Check container settings
az webapp config container show --name $webAppName --resource-group $rgName
```
**Common causes:**
- Container fails to start (crash loop)
- Wrong `WEBSITES_PORT` value
- Missing required environment variable
- App settings KV reference resolution failure

### Key Vault Reference Shows Literal Text

**Symptom:** App setting shows `@Microsoft.KeyVault(...)` instead of resolved value
**Check:**
```powershell
# Verify managed identity exists
az webapp identity show --name $webAppName --resource-group $rgName

# Verify KV role assignment
az role assignment list --assignee $principalId --scope $kvId

# Verify secret exists
az keyvault secret show --vault-name $kvName --name $secretName
```

### PostgreSQL Connection Refused

**Symptom:** Backend can't connect to PostgreSQL
**Check:**
- Firewall rules include `AllowAzureServices` (0.0.0.0)
- `require_secure_transport` is ON and connection uses `sslmode=require`
- Application user exists and has correct grants
- If Entra mode: managed identity OID matches security label

```powershell
# Check firewall rules
az postgres flexible-server firewall-rule list --name $pgServer --resource-group $rgName

# Check auth config
az postgres flexible-server show --name $pgServer --resource-group $rgName --query authConfig
```

### Docker Daemon Not Accessible

**Symptom:** `docker build` fails with connection error
**Fix:**
- Start Docker Desktop (Windows/Mac)
- Verify: `docker info`
- If using WSL2: ensure Docker Desktop WSL integration is enabled

### State File Missing or Corrupt

**Symptom:** Stage fails reading state values
**Fix:**
- Re-run from stage 01 to rebuild state
- Or manually reconstruct state from Azure resource queries:
```powershell
az resource list --resource-group $rgName --output json
```

## Health Check Debugging

### Backend Health Check

```powershell
# Direct HTTP check
Invoke-WebRequest -Uri "https://$backendHostname/health" -Method GET

# Check via Azure default hostname
Invoke-WebRequest -Uri "https://$webAppName.azurewebsites.net/health"
```

### Container Log Analysis

```powershell
# Real-time logs
az webapp log tail --name $webAppName --resource-group $rgName

# Download log files
az webapp log download --name $webAppName --resource-group $rgName --log-file logs.zip
```

### Image Tag Verification

Confirm deployed image matches expected tag:
```powershell
$config = az webapp config container show --name $webAppName --resource-group $rgName | ConvertFrom-Json
$deployedImage = $config | Where-Object { $_.name -eq "DOCKER_CUSTOM_IMAGE_NAME" } | Select-Object -ExpandProperty value
# Compare with expected: "$acrLoginServer/$imageName:$expectedTag"
```

## Proxy Interference

The deploy scripts strip localhost proxy environment variables (pattern `http://127.0.0.1:9`)
before calling `az` CLI, then restore them. If az calls fail with SSL errors while
a proxy is running, verify that `Invoke-AzCli` in `common.ps1` handles the proxy
correctly.
