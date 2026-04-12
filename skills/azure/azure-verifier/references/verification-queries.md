# PostgreSQL Verification Queries

## Extension Verification

```sql
-- Check required extensions
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('vector', 'pgcrypto')
ORDER BY extname;

-- Expected: 2 rows (vector, pgcrypto)
```

## Schema Verification

```sql
-- Check schemas exist
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('public', 'mcp')
ORDER BY schema_name;

-- Expected: 2 rows (mcp, public)
```

## Table Verification

```sql
-- Check all expected tables
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('public', 'mcp')
  AND table_type = 'BASE TABLE'
ORDER BY table_schema, table_name;

-- Critical tables that must exist:
-- public.memories
-- public.cache_entries
-- public.schema_migrations
-- mcp.tiers
-- mcp.products
-- mcp.subscriptions
```

## Migration Tracking Verification

```sql
-- Check all migrations applied
SELECT version, checksum, applied_at
FROM public.schema_migrations
ORDER BY version;

-- Expected versions:
-- 001_initial_schema
-- 001_postgres_cache
-- 002_mcp_schema
-- 003_product_sku_matrix
-- 004_user_tags_and_chatlink_tiers
-- 005_frontend_metrics
-- 006_stripe_billing_linkage
-- 007_tier_capabilities_and_catalog
```

## Column Verification

```sql
-- Check critical columns on mcp.tiers
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'mcp' AND table_name = 'tiers'
ORDER BY ordinal_position;

-- Must include: capabilities column
```

## User and Role Verification

```sql
-- Check application user exists
SELECT rolname, rolcanlogin, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname = 'chatlink_app';

-- Expected: rolcanlogin = true
```

## Grant Verification

```sql
-- Check schema grants
SELECT grantee, privilege_type
FROM information_schema.role_usage_grants
WHERE grantee = 'chatlink_app' AND object_type = 'SCHEMA';

-- Check table grants
SELECT grantee, table_schema, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'chatlink_app'
ORDER BY table_schema, table_name, privilege_type;

-- Expected: SELECT, INSERT, UPDATE, DELETE on all tables in public and mcp schemas
```

## Entra Auth Verification (if applicable)

```sql
-- Check security labels for pgaadauth
SELECT objtype, objname, label
FROM pg_seclabels
WHERE provider = 'pgaadauth';

-- Expected: label contains 'aadauth,oid={MI_OID},database=chatlink'
```

## Connection Test

```sql
-- Simple connectivity and version check
SELECT version();
SELECT current_database();
SELECT current_user;
SHOW server_version;
SHOW ssl;
-- Expected: ssl = on
```
