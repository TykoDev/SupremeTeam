# Docker Deployment Patterns

## ACR Authentication

### Managed Identity Pull (Production)

Web apps pull images using system-assigned managed identity:
```bicep
siteConfig: {
  acrUseManagedIdentityCreds: true
}
```
Requires `AcrPull` role assignment on the ACR for the web app's principal ID.

### az acr login (Deploy Time)

For pushing images during deployment:
```powershell
az acr login --name $acrName
docker push "$acrLoginServer/$imageName:$tag"
```

## Image Tag Strategies

### Timestamp Tags (Recommended)
```powershell
$tag = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
# Result: 20260410143022
```
- Immutable, sortable, human-readable
- No collision risk
- Easy to identify deployment time

### Git SHA Tags
```powershell
$tag = git rev-parse --short HEAD
# Result: a1b2c3d
```
- Ties image to source code version
- Useful for traceability

### Never Use `latest` in Production
- Not immutable -- can be overwritten
- No rollback capability
- Delta deploy scripts reject `latest` tags

## Multi-Stage Dockerfile Pattern

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

# Stage 2: Runtime
FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 8000
CMD ["node", "dist/server.js"]
```

## Build Args for Frontend

Frontend images embed API URLs at build time:
```powershell
docker build `
    --build-arg FRONTEND_API_URL="https://chatlink-prod-swc-api-XXXXXX.azurewebsites.net/api" `
    --build-arg FRONTEND_WS_URL="wss://chatlink-prod-swc-api-XXXXXX.azurewebsites.net/ws" `
    -f docker/frontend.Dockerfile `
    -t "$acrLoginServer/chatlink-frontend:$tag" .
```

These are baked into the static frontend build and cannot be changed at runtime.
Rebuild and redeploy the frontend to change API endpoints.

## Container Restart Behavior

After updating container config, a restart is needed:
```powershell
az webapp restart --name $webAppName --resource-group $rgName
```

App Service pulls the new image on restart. Container startup time depends on
image size and the app's boot time. Health check becomes available after startup.

## Rollback Procedure

Roll back to a previous image tag:
```powershell
# Find previous tag
az acr repository show-tags --name $acrName --repository chatlink-backend --orderby time_desc

# Set previous image
az webapp config container set `
    --name $webAppName `
    --resource-group $rgName `
    --container-image-name "$acrLoginServer/chatlink-backend:$previousTag"

az webapp restart --name $webAppName --resource-group $rgName
```
