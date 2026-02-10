# Docker Compose Environment Variable Loading

## Problem Description

Docker Compose variable substitution using `${VARIABLE}` syntax was not working as expected, causing environment variables to expand to empty strings in some services.

### Root Cause

Docker Compose has two separate mechanisms for environment variables:

1. **`env_file`**: Loads variables directly into the container's runtime environment
2. **`environment` section with `${VAR}`**: References the **shell environment** where `docker compose` executes, NOT variables defined in `env_file`

When you use:
```yaml
env_file:
  - env.shared
  - env.tier-supabase
environment:
  - DB_USER=${POSTGRES_USER}  # References shell env, NOT env_file!
```

The `${POSTGRES_USER}` is looked up in the shell environment where `docker compose` runs, not in env.shared or env.tier-supabase. If POSTGRES_USER is not set in the shell, it expands to an empty string.

## Solution: Shell Environment Sourcing

PMOVES.AI uses a wrapper script (`with-env.sh`) that sources environment variables from `env.shared` before invoking `docker compose`. This makes all variables available in the shell environment for Docker Compose's variable substitution.

**Correct usage:**
```yaml
services:
  supabase-gotrue:
    environment:
      # Variables reference shell environment (loaded via with-env.sh)
      - GOTRUE_DB_DATABASE_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@supabase-db:5432/${POSTGRES_DB}?sslmode=disable
      - GOTRUE_JWT_SECRET=${SUPABASE_JWT_SECRET}
      - GOTRUE_JWT_ALGORITHM=${SUPABASE_JWT_ALGORITHM}
```

**Always invoke docker compose via Makefile:**
```bash
make dc-up        # Uses with-env.sh to source env.shared
make dc-restart    # Uses with-env.sh to source env.shared
```

Direct `docker compose` commands will NOT have environment variables loaded:
```bash
# WRONG - variables will be empty
docker compose up -d

# CORRECT - uses Makefile wrapper
make dc-up supabase-gotrue
```

## Services Fixed

All Supabase services now properly use environment variable substitution:

- ✅ **supabase-db** - Database (healthy)
- ✅ **supabase-realtime** - Fixed env vars (healthy)
- ✅ **supabase-kong** - Fixed env vars + bootstrap (healthy)
- ✅ **supabase-gotrue** - Fixed env vars + migration cleanup (healthy)
- ✅ **supabase-postgrest** - Fixed env vars (running)
- ✅ **supabase-storage** - Fixed env vars (healthy)
- ✅ **supabase-studio** - Fixed env vars (healthy)

## GoTrue Migration Issue Resolution

The GoTrue service had migration conflicts due to:
1. Schema already had constraints from previous migrations
2. Migration tracking table (`auth.schema_migrations`) had inconsistent entries
3. Embedded migration scripts don't use `IF NOT EXISTS` for constraints

**Resolution:**
1. Dropped all length check constraints from auth tables
2. Cleared migration tracking to base state
3. Let GoTrue run all migrations from scratch
4. Result: All migrations applied successfully

## Kong Bootstrap Resolution

Kong required database bootstrapping:
```bash
docker run --rm --network pmoves_data \
  -e KONG_DATABASE=postgres \
  -e KONG_PG_HOST=supabase-db \
  -e KONG_PG_PORT=5432 \
  -e KONG_PG_DATABASE=${POSTGRES_DB} \
  -e KONG_PG_USER=postgres \
  -e KONG_PG_PASSWORD=${POSTGRES_PASSWORD} \
  -e KONG_PG_SCHEMA=kong \
  kong:3.7.1 kong migrations bootstrap
```

Result: 66 migrations applied successfully

## Connectivity Validation

All Supabase services are accessible:

| Service | Port | Status | Endpoint |
|---------|------|--------|----------|
| PostgREST | 3010 | Running (401 auth required) | http://localhost:3010/ |
| GoTrue | 9999 | Healthy | http://localhost:9999/auth/v1/ |
| Kong Gateway | 8000 | Running (no routes) | http://localhost:8000/ |
| Realtime | 4000 | Healthy | Internal |
| Storage | 5000 | Healthy | http://localhost:5000/status |
| Studio | 54323 | Healthy | http://localhost:54323/ |

## Important Notes

1. **NEVER hardcode credentials** in docker-compose.yml - always use `${VARIABLE}` references
2. **ALWAYS use Makefile targets** for docker compose commands (loads env.shared via with-env.sh)
3. **CREDENTIALS belong in env.shared** which should be gitignored for production deployments
4. **For production**: Use proper secret management (external vault, encrypted secrets, etc.)

## Files Modified

1. `/home/pmoves/PMOVES.AI/pmoves/docker-compose.yml`:
   - Reverted hardcoded credentials to `${VARIABLE}` references
   - All Supabase services now use proper environment variable substitution

2. Database schema changes:
   - Dropped and recreated constraint for migrations
   - Cleaned up migration tracking table
   - Bootstrapped Kong schema
