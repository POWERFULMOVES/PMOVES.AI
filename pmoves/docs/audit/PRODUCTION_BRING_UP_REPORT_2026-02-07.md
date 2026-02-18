# Production Bring-Up Report - 2026-02-07

## Phase 1 Progress

### ✅ Completed
1. **Phase 0: Pre-Flight**
   - Docker compose config validation: PASSED
   - Backup created: docker-compose.yml.backup-20260207_185526

2. **NATS Authorization Fixes** (16 services)
   - All NATS_URL lines fixed to use env.tier-agent credentials
   - Verified: 0 remaining bad patterns

3. **Data Tier Started**
   - qdrant: Running
   - neo4j: Running
   - meilisearch: Running
   - minio: Running
   - tensorzero-clickhouse: Running

### ⚠️ Issues Found During Bring-Up

#### Issue 1: SUPABASE_JWT_EXP Missing from env.shared
**Impact:** supabase-gotrue failing to start
**Error:** `converting '' to type int: strconv.ParseInt: parsing "": invalid syntax`
**Fix Applied:** Added `SUPABASE_JWT_EXP=3600` to env.shared
**Status:** Still failing - needs further investigation

#### Issue 2: Supabase Service Dependencies
**Failing Services:**
- pmoves-supabase-gotrue-1: Restarting (JWT_EXP still empty despite env.shared addition)
- pmoves-supabase-storage-1: Restarting (missing config)
- pmoves-supabase-kong-1: Restarting (database connection issue)

**Root Cause:** The `environment:` section in docker-compose.yml overrides env_file settings. When a variable is referenced like `${SUPABASE_JWT_EXP}`, it must exist in env.shared (first file) or the host environment, NOT in later env_file files.

#### Issue 3: Environment Variable Loading Order
**Problem:** Docker Compose env_file loading order:
1. env.shared (first) - variables available for ${VAR} substitution
2. env.tier-* (second) - NOT available for ${VAR} substitution in docker-compose.yml

**Impact:** Variables in tier files cannot be used in docker-compose.yml environment overrides

## Findings Summary

### Environment Architecture Issue
The current architecture uses tier-specific env files, but docker-compose.yml's `environment:` sections use `${VAR}` substitution which only sees env.shared.

**Example:**
```yaml
# This doesn't work because SUPABASE_JWT_EXP is in env.tier-supabase, not env.shared:
- GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP}
```

**Solutions:**
1. Move all ${VAR} referenced variables to env.shared
2. Remove environment overrides and rely solely on env_file
3. Use defaults in docker-compose.yml: `- GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP:-3600}`

### Missing Variables in env.shared
The following variables need to be added to env.shared (moved from tier files):

**From env.tier-supabase:**
- SUPABASE_JWT_EXP=3600
- SUPABASE_JWT_SECRET=Mk1YWigx/sFJcP/cN1yTreuIa0maXMekfZ46M5Ewq+s=
- SUPABASE_JWT_ALGORITHM=HS256
- SUPABASE_DB_USER=pmoves
- SUPABASE_DB_PASSWORD=bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger
- SUPABASE_DB_NAME=pmoves
- SUPABASE_SITE_URL=http://localhost:3000
- SUPABASE_PUBLIC_URL=http://localhost:54323
- SUPABASE_ANON_KEY=LBLAfet+bMtLNakx/XEoNXYETnOMaBvfJQTC9CKP3mY=
- SUPABASE_SECRET_KEY=ETYYumaXw2neFofxVAYwb0RVP+E5ohp4+GJcgRjPa/Q=
- SUPABASE_PUBLISHABLE_KEY=4X+HudWhF0/U/2xByr+d1ARSPrFE7kQEM1TURjaH4yY=

**From env.shared (POSTGRES_* for supabase-db):**
- POSTGRES_DB=pmoves
- POSTGRES_USER=pmoves
- POSTGRES_PASSWORD=bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger

## Next Steps

### Option 1: Consolidate Variables (Recommended)
Move all ${VAR} referenced variables to env.shared to ensure docker-compose.yml can see them.

### Option 2: Add Defaults to docker-compose.yml
Add default values to all ${VAR:-default} references in docker-compose.yml.

### Option 3: Remove Environment Overrides
Remove `environment:` sections that override env_file values, letting tier files handle all configuration.

## Recommendation

**Immediate Action:** Add missing SUPABASE_* and POSTGRES_* variables to env.shared so Supabase stack can start.

**Long-term:** Refactor docker-compose.yml to remove environment overrides and rely solely on env_file, OR move all shared variables to env.shared.

---

**Status:** ⏸️ **PAUSED** - Environment variable architecture issue needs resolution
**Phase:** 1 (Supabase Stack)
**Blockers:** env.shared missing variables for Supabase services
