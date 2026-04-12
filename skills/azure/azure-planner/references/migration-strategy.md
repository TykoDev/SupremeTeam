# Database Migration Strategy

## Migration Execution Order

Migrations execute in a fixed order, not by filesystem sort:

1. Extension enablement (inline SQL, not a file)
2. `src/services/storage/migrations/001_initial_schema.sql` -- Core tables
3. `src/services/cache/migrations/001_postgres_cache.sql` -- Cache table
4. `src/services/storage/migrations/002_mcp_schema.sql` -- MCP schema and tables
5. `src/services/storage/migrations/003_product_sku_matrix.sql` -- Product catalog
6. `src/services/storage/migrations/004_user_tags_and_chatlink_tiers.sql` -- Tier system
7. `src/services/storage/migrations/005_frontend_metrics.sql` -- Metrics tables
8. `src/services/storage/migrations/006_stripe_billing_linkage.sql` -- Billing
9. `src/services/storage/migrations/007_tier_capabilities_and_catalog.sql` -- Capabilities

## Migration Tracking

A tracking table records applied migrations:

```sql
CREATE TABLE IF NOT EXISTS public.schema_migrations (
  version   TEXT PRIMARY KEY,
  checksum  TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Each migration is recorded with its filename and SHA256 checksum of the file content.
Re-running a migration with a changed checksum is an error condition.

## Checksum Validation

Before executing a migration file:
1. Compute SHA256 of the file content
2. Check if `schema_migrations` has an entry for this version
3. If exists and checksum matches: skip (already applied)
4. If exists and checksum differs: ERROR -- migration was modified after application
5. If not exists: execute the migration, then insert the tracking record

## Post-Migration Assertions

After all migrations, run validation queries:

```sql
-- Verify critical table exists
SELECT 1 FROM information_schema.tables
WHERE table_schema = 'mcp' AND table_name = 'tiers';

-- Verify critical column exists
SELECT 1 FROM information_schema.columns
WHERE table_schema = 'mcp' AND table_name = 'tiers' AND column_name = 'capabilities';

-- Verify all migration versions recorded
SELECT version, checksum FROM public.schema_migrations ORDER BY version;
```

## Multi-Schema Support

Migrations may create and operate across multiple PostgreSQL schemas:

- `public` -- Core tables (memories, cache, schema_migrations)
- `mcp` -- MCP-specific tables (tiers, products, subscriptions)

Application user grants must cover all schemas:

```sql
GRANT USAGE ON SCHEMA public TO chatlink_app;
GRANT USAGE ON SCHEMA mcp TO chatlink_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatlink_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mcp TO chatlink_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatlink_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chatlink_app;
```

## psql Execution Strategy

The deployment finds a psql client through this fallback chain:

1. `POSTGRES_PSQL_PATH` env var (explicit path)
2. `PSQL_PATH` env var (legacy)
3. `psql` on system PATH
4. Known Windows install paths (`C:\Program Files\PostgreSQL\{16,15,14}\bin\psql.exe`)
5. Docker container: `docker run --rm postgres:16-alpine psql ...`

All psql invocations use `sslmode=require` and connect to the Flexible Server FQDN.
