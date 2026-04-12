# Environment Variable Catalog

## Deployment-Only Variables

These variables are consumed exclusively by deploy scripts. They never appear in
app settings or Key Vault.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AZ_SUBSCRIPTION_ID` | (required) | Azure subscription target |
| `AZ_TENANT_ID` | (required) | Azure AD tenant for login |
| `AZ_LOCATION` | `westeurope` | Azure region for resources |
| `AZ_LOCATION_ALIAS` | `weu` | Short location code for naming |
| `AZ_ENV` | `prod` | Environment name (prod/staging/dev) |
| `AZ_RESOURCE_GROUP` | `{base}-{env}-{loc}-rg` | Resource group name |
| `BASE_NAME` | `chatlink` | Base name for all resources |
| `DEPLOY_WHATIF` | `false` | Enable dry-run mode |
| `IMAGE_TAG` | (auto UTC timestamp) | Container image tag |
| `BACKEND_IMAGE_TAG` | (falls back to IMAGE_TAG) | Backend-specific tag |
| `FRONTEND_IMAGE_TAG` | (falls back to IMAGE_TAG) | Frontend-specific tag |
| `FRONTEND_MCP_IMAGE_TAG` | (falls back to IMAGE_TAG) | MCP frontend tag |

## Provisioning Variables

Used during deployment to configure Azure resources. Not set as app settings.

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_ADMIN_USER` | `chatlink_admin` | PostgreSQL admin username |
| `POSTGRES_ADMIN_PASSWORD` | (required) | PostgreSQL admin password |
| `POSTGRES_APP_USER` | `chatlink_app` | Application database user |
| `POSTGRES_APP_PASSWORD` | (required) | Application user password |
| `POSTGRES_AUTH_MODE` | `password` | Auth mode: password/hybrid/entra_only |
| `POSTGRES_PSQL_PATH` | (auto-detect) | Local psql binary path |
| `POSTGRES_PSQL_DOCKER_IMAGE` | `postgres:16-alpine` | Docker fallback for psql |
| `BACKEND_BOOTSTRAP_IMAGE` | `mcr.microsoft.com/azuredocs/nodejsapp:latest` | Initial backend container |
| `FRONTEND_BOOTSTRAP_IMAGE` | `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest` | Initial frontend container |
| `POSTGRES_ENABLE_ENTRA_AUTH` | `false` | Enable Entra ID auth on PG |
| `POSTGRES_ENABLE_PASSWORD_AUTH` | `true` | Enable password auth on PG |

## Runtime Non-Sensitive Variables

Set as plain-text app settings on the backend web app.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8000` | Backend listen port |
| `CACHE_BACKEND` | `postgres` | Cache implementation |
| `CACHE_TTL` | `300` | Cache entry TTL (seconds) |
| `CACHE_PREFIX` | `chatlink` | Cache key prefix |
| `CACHE_POSTGRES_TABLE` | `cache_entries` | Cache table name |
| `CACHE_POSTGRES_SCHEMA` | `public` | Cache table schema |
| `CACHE_POSTGRES_POOL_SIZE` | `10` | Connection pool size |
| `CACHE_POSTGRES_CLEANUP_INTERVAL_SECONDS` | `300` | Expired entry cleanup interval |
| `RLM_ENABLED` | `true` | Enable RLM memory system |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `RLM_LLM_MODEL` | `gpt-4.1-mini` | Query decomposition model |
| `AUTH_ENABLED` | `false` | Enable authentication |
| `ADMIN_EMAIL` | `dev@localhost` | Admin notification email |
| `PYTHON_ENABLED` | `false` | Enable Python bridge |
| `DOCKER_ENABLED` | `false` | Enable Docker sandbox |
| `STRIPE_TEST_MODE` | `true` | Stripe test/live mode |
| `DEFAULT_MODEL` | `gpt-5-mini` | Default chat model |
| `MEMORY_MODEL` | `gpt-5-nano` | Model for memory operations |
| `MEMORY_UPLOAD_MAX_FILES` | `50` | Max upload file count |
| `MEMORY_UPLOAD_MAX_FILE_SIZE_MB` | `20` | Max upload file size |
| `POSTGRES_SSL` | `true` | Force SSL on PG connections |

## Runtime Secrets

Stored in Key Vault, referenced via `@Microsoft.KeyVault(SecretUri=...)` in app settings.

| Variable | KV Secret Name | Purpose |
|----------|---------------|---------|
| `OPENAI_API_KEY` | `openai-api-key` | OpenAI API access |
| `ANTHROPIC_API_KEY` | `anthropic-api-key` | Anthropic API access |
| `GEMINI_API_KEY` | `gemini-api-key` | Google Gemini access |
| `OPENROUTER_API_KEY` | `openrouter-api-key` | OpenRouter proxy access |
| `OPENAI_COMPATIBLE_KEY` | `openai-compatible-key` | Custom endpoint key |
| `AZURE_OPENAI_KEY` | `azure-openai-key` | Azure OpenAI access |
| `SESSION_SECRET` | `session-secret` | Session signing key |
| `JWT_SECRET` | `jwt-secret` | JWT signing key |
| `WORKOS_API_KEY` | `workos-api-key` | WorkOS authentication |
| `WORKOS_CLIENT_ID` | `workos-client-id` | WorkOS client identifier |
| `WORKOS_COOKIE_PASSWORD` | `workos-cookie-password` | WorkOS cookie encryption |
| `DATABASE_URL` | `database-url` | PostgreSQL connection string |
| `BRAVE_API_KEY` | `brave-api-key` | Brave Search API |
| `TAVILY_API_KEY` | `tavily-api-key` | Tavily Search API |

### Secret Name Conversion Rule

Environment variable names are converted to Key Vault secret names by:
1. Converting to lowercase
2. Replacing underscores with hyphens

Example: `OPENAI_API_KEY` becomes `openai-api-key`
