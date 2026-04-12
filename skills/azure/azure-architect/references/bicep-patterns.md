# Bicep Design Patterns

## Module Interface Contract

Every Bicep module follows this interface pattern:

```bicep
// Parameters: only what this module needs
@description('Base name for resource naming')
param baseName string

@description('Deployment environment')
param environment string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

// Resource definition
resource myResource 'Microsoft.X/y@2024-01-01' = {
  name: computedName
  location: location
  tags: tags
  properties: { ... }
}

// Outputs: everything downstream needs
output id string = myResource.id
output name string = myResource.name
```

## Conditional Deployment

Use `@allowed` and ternary operators for feature toggles:

```bicep
@allowed(['true', 'false'])
param enableFeature string = 'false'

resource conditionalResource '...' = if (enableFeature == 'true') {
  ...
}
```

## Cross-Module Dependencies

Pass outputs from one module as parameters to another in `main.bicep`:

```bicep
module acr 'modules/acr.bicep' = { ... }
module webApp 'modules/web_app.bicep' = {
  params: {
    acrLoginServer: acr.outputs.loginServer
  }
}
```

## Secure Parameter Handling

```bicep
@secure()
@description('Database admin password')
param pgAdminPassword string

// Never output secure values
// Never use secure values in resource names
// Pass secure values only to properties that accept them
```

## Tag Propagation

Compute tags once in main.bicep, pass to every module:

```bicep
var baseTags = {
  app: baseName
  environment: environment
  managedBy: 'bicep'
}
var allTags = union(baseTags, tags)
```

## UniqueString for Global Uniqueness

```bicep
var suffix = take(uniqueString(subscription().subscriptionId, resourceGroup().id), 6)
var acrName = take('${baseName}${locationAlias}${suffix}acr', 50)
var storageName = take(toLower('${baseName}${locationAlias}${suffix}st'), 24)
```

## App Service with Managed Identity

```bicep
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  kind: 'app,linux,container'
  identity: { type: 'SystemAssigned' }
  properties: {
    httpsOnly: true
    siteConfig: {
      alwaysOn: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      acrUseManagedIdentityCreds: true
    }
  }
}
```

## PostgreSQL Flexible Server with Dual Auth

```bicep
resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  properties: {
    authConfig: {
      activeDirectoryAuth: pgEnableEntraAuth ? 'Enabled' : 'Disabled'
      passwordAuth: pgEnablePasswordAuth ? 'Enabled' : 'Disabled'
    }
    storage: { storageSizeGB: 128 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
  }
}
```

## Output Flattening Pattern

In main.bicep, re-export module outputs so deploy scripts get a flat namespace:

```bicep
output acrName string = acr.outputs.name
output acrId string = acr.outputs.id
output acrLoginServer string = acr.outputs.loginServer
output backendWebAppName string = backendWebApp.outputs.name
output backendWebAppHostname string = backendWebApp.outputs.defaultHostname
output backendPrincipalId string = backendWebApp.outputs.principalId
```
