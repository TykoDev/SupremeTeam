# az CLI Verification Commands

## Resource Group

```powershell
az group show --name $rgName --query "{name:name, location:location, provisioningState:properties.provisioningState}"
# Expected: provisioningState = Succeeded
```

## App Service Plan

```powershell
az appservice plan show --name $aspName --resource-group $rgName --query "{sku:sku, kind:kind, reserved:properties.reserved}"
# Expected: kind contains "linux", reserved = true, sku.name = "B2"
```

## Web App

```powershell
# General config
az webapp config show --name $webAppName --resource-group $rgName --query "{alwaysOn:alwaysOn, minTlsVersion:minTlsVersion, ftpsState:ftpsState, healthCheckPath:healthCheckPath}"
# Expected: alwaysOn=true, minTlsVersion="1.2", ftpsState="Disabled"

# Identity
az webapp identity show --name $webAppName --resource-group $rgName --query "{principalId:principalId, type:type}"
# Expected: type = "SystemAssigned", principalId not null

# Container config
az webapp config container show --name $webAppName --resource-group $rgName
# Verify DOCKER_CUSTOM_IMAGE_NAME matches expected image:tag

# App settings
az webapp config appsettings list --name $webAppName --resource-group $rgName
# Verify all expected settings present, KV references resolve
```

## Container Registry

```powershell
az acr show --name $acrName --query "{adminUserEnabled:adminUserEnabled, sku:sku.name, loginServer:loginServer}"
# Expected: adminUserEnabled = false, sku = "Basic"

# List repositories
az acr repository list --name $acrName
# Expected: chatlink-backend, chatlink-frontend, chatlink-frontend-mcp

# List tags for a repo
az acr repository show-tags --name $acrName --repository chatlink-backend --orderby time_desc --top 5
```

## Key Vault

```powershell
az keyvault show --name $kvName --query "{enableRbacAuthorization:properties.enableRbacAuthorization, softDeleteRetention:properties.softDeleteRetentionInDays, sku:properties.sku.name}"
# Expected: enableRbacAuthorization=true, softDeleteRetention=90, sku="standard"

# List secrets
az keyvault secret list --vault-name $kvName --query "[].{name:name}" --output table

# Read specific secret
az keyvault secret show --vault-name $kvName --name "database-url" --query value
# Verify starts with "postgresql://" and contains "sslmode=require"
```

## Storage Account

```powershell
az storage account show --name $storageName --resource-group $rgName --query "{minimumTlsVersion:minimumTlsVersion, supportsHttpsTrafficOnly:enableHttpsTrafficOnly, allowBlobPublicAccess:allowBlobPublicAccess}"
# Expected: TLS1_2, httpsOnly=true, allowBlobPublicAccess=false

# Blob service properties
az storage blob service-properties show --account-name $storageName --auth-mode login --query "{softDelete:deleteRetentionPolicy, versioning:isVersioningEnabled}"
# Expected: softDelete.enabled=true, softDelete.days=7, versioning=true

# List containers
az storage container list --account-name $storageName --auth-mode login --query "[].name"
# Expected: files, attachments

# CORS rules
az storage cors list --account-name $storageName --services b
# Expected: allowed origins match frontend hostname(s)
```

## PostgreSQL Flexible Server

```powershell
az postgres flexible-server show --name $pgServer --resource-group $rgName --query "{version:version, sku:sku, authConfig:authConfig, storage:storage.storageSizeGB}"
# Expected: version="16", auth matches target mode

# Firewall rules
az postgres flexible-server firewall-rule list --name $pgServer --resource-group $rgName
# Expected: AllowAzureServices (0.0.0.0-0.0.0.0)

# Database exists
az postgres flexible-server db show --server-name $pgServer --resource-group $rgName --database-name $dbName
```

## RBAC Role Assignments

```powershell
# Check specific assignment
az role assignment list --assignee $principalId --role "AcrPull" --scope $acrId --query "[].{role:roleDefinitionName, principal:principalId}"
# Expected: 1 result

az role assignment list --assignee $principalId --role "Key Vault Secrets User" --scope $kvId
# Expected: 1 result

az role assignment list --assignee $principalId --role "Storage Blob Data Contributor" --scope $storageId
# Expected: 1 result
```

## DNS and Custom Domain

```powershell
# List hostname bindings
az webapp config hostname list --webapp-name $webAppName --resource-group $rgName

# List SSL bindings
az webapp config ssl list --resource-group $rgName
```
