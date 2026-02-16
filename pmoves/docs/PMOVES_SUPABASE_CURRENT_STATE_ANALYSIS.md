# PMOVES Supabase Integration - Current State Analysis

**Date:** 2026-02-07

**Status:** ⚠️ **CRITICAL CONFIGURATION MISMATCH IDENTIFIED**

---

## Executive Summary

The current `pmoves/docker-compose.yml` Supabase configuration uses **non-standard variable naming** that conflicts with the PMOVES-supabase fork (which follows standard Supabase conventions). This mismatch is causing service startup failures.

---

## Current Supabase Services in pmoves/docker-compose.yml

### Services Present (7)

| Service | Container Name | Image | Status |
|---------|---------------|-------|--------|
| db | supabase-db | supabase/postgres:17.6.1.079 | ✅ Running |
| auth | supabase-gotrue | supabase/gotrue:v2.186.0 | ⚠️ Failing (JWT config) |
| rest | supabase-postgrest | postgrest/postgrest:v14.3 | ⚠️ Failing (JWT config) |
| kong | supabase-kong | kong:2.8.1 | ⚠️ Failing (DB connection) |
| realtime | supabase-realtime | supabase/realtime:v2.72.0 | ❓ Unknown |
| storage | supabase-storage | supabase/storage-api:v1.36.2 | ⚠️ Failing (missing keys) |
| studio | supabase-studio | supabase/studio:2026.02.04-sha-fba1944 | ❓ Unknown |

### Services Missing from pmoves (but present in PMOVES-supabase)

| Service | Purpose | Impact |
|---------|---------|--------|
| imgproxy | Image transformation | No image processing in storage |
| meta (postgres-meta) | Database management UI | Studio missing features |
| functions (edge-runtime) | Edge functions | No serverless functions |
| analytics (logflare) | Log aggregation | No centralized logging |
| vector | Log forwarding to analytics | Analytics won't receive logs |
| supavisor (pooler) | Connection pooling | No connection pooling |

---

## Variable Mapping Analysis

### Current pmoves/docker-compose.yml Variable Usage

```yaml
# auth (supabase-gotrue)
environment:
  - GOTRUE_JWT_SECRET=${SUPABASE_JWT_SECRET}
  - GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP}
  - GOTRUE_JWT_ALGORITHM=${SUPABASE_JWT_ALGORITHM}

# storage (supabase-storage)
environment:
  - ANON_KEY=${SUPABASE_PUBLISHABLE_KEY}
  - SERVICE_KEY=${SUPABASE_SECRET_KEY}
  - PGRST_JWT_SECRET=${SUPABASE_JWT_SECRET}

# postgrest (supabase-postgrest)
environment:
  - PGRST_JWT_SECRET=${PGRST_JWT_SECRET}
```

### PMOVES-supabase Standard Variable Usage

```yaml
# auth (supabase-auth)
environment:
  - GOTRUE_JWT_SECRET=${JWT_SECRET}
  - GOTRUE_JWT_EXP=${JWT_EXPIRY}

# storage (supabase-storage)
environment:
  - ANON_KEY=${ANON_KEY}
  - SERVICE_KEY=${SERVICE_ROLE_KEY}
  - PGRST_JWT_SECRET=${JWT_SECRET}

# rest (supabase-rest)
environment:
  - PGRST_JWT_SECRET=${JWT_SECRET}
  - PGRST_APP_SETTINGS_JWT_SECRET=${JWT_SECRET}
  - PGRST_APP_SETTINGS_JWT_EXP=${JWT_EXPIRY}
```

---

## Variable Name Mapping Table

| Current (pmoves) | Standard (PMOVES-supabase) | Location |
|------------------|----------------------------|----------|
| `SUPABASE_JWT_SECRET` | `JWT_SECRET` | env.shared |
| `SUPABASE_JWT_EXP` | `JWT_EXPIRY` | env.shared |
| `SUPABASE_JWT_ALGORITHM` | *not used, defaults to HS256* | - |
| `SUPABASE_PUBLISHABLE_KEY` | `ANON_KEY` | env.shared |
| `SUPABASE_SECRET_KEY` | `SERVICE_ROLE_KEY` | env.shared |
| `SUPABASE_SITE_URL` | `SITE_URL` | env.shared |
| `SUPABASE_PUBLIC_URL` | `SUPABASE_PUBLIC_URL` | env.shared |
| `SUPABASE_DB_USER` | `POSTGRES_USER` | env.shared |
| `SUPABASE_DB_PASSWORD` | `POSTGRES_PASSWORD` | env.shared |
| `SUPABASE_DB_NAME` | `POSTGRES_DB` | env.shared |
| `SUPABASE_SERVICE_ROLE_KEY` | `SERVICE_ROLE_KEY` | env.shared |
| `SUPABASE_ANON_KEY` | `ANON_KEY` | env.shared |

---

## Environment File Architecture Issue

### Problem

Docker Compose evaluates `${VAR}` substitution at **config parse time**, but `env_file` values are loaded at **container runtime**.

```
Timeline:
1. docker compose up
2. Parse docker-compose.yml → ${VAR} substitution happens HERE
3. Create containers
4. Start containers → env_file values loaded HERE (too late!)
```

### Impact

Variables in `env.tier-supabase` are **NOT visible** for `${VAR}` substitution in docker-compose.yml.

### Example

```yaml
# This DOESN'T WORK if SUPABASE_JWT_EXP is in env.tier-supabase
environment:
  - GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP}  # Empty string!
```

### Solutions

1. **Move variables to env.shared** (first file loaded)
2. **Add defaults in docker-compose.yml**: `${VAR:-default}`
3. **Remove environment overrides** - rely on env_file

---

## Service Name Mapping

| PMOVES-supabase | pmoves/docker-compose.yml | Notes |
|-----------------|---------------------------|-------|
| `db` | `supabase-db` | Different name |
| `auth` | `supabase-gotrue` | Different name |
| `rest` | `supabase-postgrest` | Different name |
| `kong` | `supabase-kong` | ✅ Same |
| `realtime` | `supabase-realtime` | ✅ Same |
| `storage` | `supabase-storage` | ✅ Same |
| `studio` | `supabase-studio` | ✅ Same |
| `imgproxy` | *missing* | ❌ Not in pmoves |
| `meta` | *missing* | ❌ Not in pmoves |
| `functions` | *missing* | ❌ Not in pmoves |
| `analytics` | *missing* | ❌ Not in pmoves |
| `vector` | *missing* | ❌ Not in pmoves |
| `supavisor` | *missing* | ❌ Not in pmoves |

---

## Network Configuration

### PMOVES-supabase
```yaml
networks:
  default:
    name: supabase
```

### pmoves/docker-compose.yml
```yaml
networks:
  pmoves_data:  # Database tier
  pmoves_api:   # API tier
  pmoves_app:   # Application tier
  pmoves_bus:   # Message bus (NATS)
```

### Service Network Assignments

| Service | pmoves Network |
|---------|----------------|
| supabase-db | pmoves_data |
| supabase-postgrest | pmoves_api, pmoves_data |
| supabase-gotrue | pmoves_api, pmoves_data |
| supabase-kong | pmoves_api |
| supabase-realtime | pmoves_api, pmoves_data |
| supabase-storage | pmoves_api, pmoves_data |
| supabase-studio | pmoves_app |

---

## Current Service Dependencies

```
supabase-db (healthcheck)
  ↓
supabase-postgrest (depends_on: db)
supabase-gotrue (depends_on: db)
supabase-realtime (depends_on: db)
supabase-storage (depends_on: db, postgrest)

supabase-kong (independent, but proxies to all)
supabase-studio (depends_on: postgrest, gotrue)
```

### Missing Dependencies

Current pmoves configuration is **missing these dependencies** from PMOVES-supabase:
- `vector` (log aggregation) → should depend on all services
- `analytics` → should be dependency for studio, kong, auth, rest, realtime
- `meta` → should be dependency for studio
- `imgproxy` → should be dependency for storage

---

## Integration Gaps

### 1. Kong Configuration

PMOVES-supabase uses:
```yaml
volumes:
  - ./volumes/api/kong.yml:/home/kong/temp.yml:ro,z
```

pmoves uses inline configuration which may be outdated.

### 2. Database Initialization

PMOVES-supabase has extensive init scripts:
- `volumes/db/realtime.sql` - Realtime setup
- `volumes/db/webhooks.sql` - Webhooks setup
- `volumes/db/roles.sql` - Database roles
- `volumes/db/jwt.sql` - JWT configuration
- `volumes/db/_supabase.sql` - Internal Supabase schema
- `volumes/db/logs.sql` - Analytics schema
- `volumes/db/pooler.sql` - Connection pooler setup

pmoves has:
- `supabase/initdb/` directory with PMOVES-specific migrations

These may conflict or be incomplete.

### 3. Storage Backend

PMOVES-supabase supports:
- File storage (default)
- S3 storage (via docker-compose.s3.yml)

pmoves storage references MinIO:
```yaml
- GLOBAL_S3_ENDPOINT=${MINIO_ENDPOINT}
```

This is a hybrid approach that may need validation.

---

## Health Check Status

### Current Health Check Results

From production bring-up attempt:

| Service | Status | Error |
|---------|--------|-------|
| supabase-db | ✅ Running | - |
| supabase-gotrue | ⚠️ Restarting | JWT_EXP empty/invalid |
| supabase-postgrest | ⚠️ Restarting | JWT_SECRET invalid |
| supabase-kong | ⚠️ Restarting | Database connection |
| supabase-storage | ⚠️ Restarting | Missing ANON_KEY |
| supabase-realtime | ❓ Unknown | Not checked |
| supabase-studio | ❓ Unknown | Not checked |

---

## Recommendations

### Immediate Actions

1. **Add missing variables to env.shared**:
   - `JWT_SECRET` (standard name, not SUPABASE_JWT_SECRET)
   - `JWT_EXPIRY` (standard name, not SUPABASE_JWT_EXP)
   - `ANON_KEY` (standard name, not SUPABASE_PUBLISHABLE_KEY)
   - `SERVICE_ROLE_KEY` (standard name, not SUPABASE_SECRET_KEY)
   - `SITE_URL`
   - `API_EXTERNAL_URL`
   - `SUPABASE_PUBLIC_URL`

2. **Update docker-compose.yml variable references**:
   - Change `${SUPABASE_JWT_SECRET}` → `${JWT_SECRET}`
   - Change `${SUPABASE_JWT_EXP}` → `${JWT_EXPIRY}`
   - Change `${SUPABASE_PUBLISHABLE_KEY}` → `${ANON_KEY}`
   - Change `${SUPABASE_SECRET_KEY}` → `${SERVICE_ROLE_KEY}`

3. **Add missing services**:
   - imgproxy (for storage image transformation)
   - meta (for Studio database management)
   - functions (for edge functions)
   - analytics (for log aggregation)
   - vector (for log forwarding)
   - supavisor (for connection pooling)

### Long-term Actions

1. **Adopt PMOVES-supabase docker-compose structure** for consistency
2. **Use env.supabase** for Supabase-specific variables
3. **Add proper healthchecks** for all services
4. **Implement proper service dependencies**
5. **Copy PMOVES-supabase database init scripts** for complete setup

---

## Files Created

1. **pmoves/env.supabase** - Standard Supabase environment variables
2. **pmoves/docs/SUPABASE_UNIFIED_SETUP.md** - Unified configuration guide
3. **pmoves/docs/PMOVES_SUPABASE_CURRENT_STATE_ANALYSIS.md** - This document

---

## Next Steps

1. Review and approve the unified configuration approach
2. Apply variable name changes to docker-compose.yml
3. Add missing services from PMOVES-supabase
4. Test Supabase stack startup
5. Verify all healthchecks pass
6. Proceed with production bring-up

---

**Related Documentation:**
- PMOVES_SUPABASE_SETUP_GUIDE.md - Original variable mismatch documentation
- SUPABASE_UNIFIED_SETUP.md - Unified configuration guide
- PMOVES-supabase/docker/docker-compose.yml - Reference configuration
