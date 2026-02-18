# PMOVES.AI Unified Supabase Configuration Guide

**Status:** ✅ **Ready for Implementation**

**Date:** 2026-02-07

---

## Overview

This guide describes the unified Supabase configuration for PMOVES.AI that leverages the PMOVES-supabase fork with standard variable naming conventions.

## Critical Changes

### Variable Naming Standardization

The previous `pmoves/docker-compose.yml` used custom `SUPABASE_*` prefixed variables. The new configuration uses **standard Supabase variable names** from the PMOVES-supabase fork.

| Old (Custom) | New (Standard) | Service |
|--------------|----------------|---------|
| `SUPABASE_JWT_SECRET` | `JWT_SECRET` | All services |
| `SUPABASE_JWT_EXP` | `JWT_EXPIRY` | auth, rest |
| `SUPABASE_ANON_KEY` | `ANON_KEY` | All services |
| `SUPABASE_SERVICE_ROLE_KEY` | `SERVICE_ROLE_KEY` | All services |
| `SUPABASE_SITE_URL` | `SITE_URL` | auth |
| `SUPABASE_PUBLIC_URL` | `SUPABASE_PUBLIC_URL` | studio |
| `SUPABASE_DB_*` | `POSTGRES_*` | db, all services |

### New Services Added

The following services from PMOVES-supabase are now integrated:

| Service | Purpose | Container Name |
|---------|---------|----------------|
| imgproxy | Image transformation | supabase-imgproxy |
| meta (postgres-meta) | Database management UI | supabase-meta |
| functions (edge-runtime) | Edge functions | supabase-edge-functions |
| analytics (logflare) | Log aggregation | supabase-analytics |
| vector | Log forwarding | supabase-vector |
| supavisor | Connection pooler | supabase-pooler |

---

## Implementation Options

### Option 1: Replace Existing Supabase Services (Recommended)

Replace the current Supabase services in `pmoves/docker-compose.yml` with the unified configuration.

**Pros:**
- Single docker-compose file
- Consistent networking with PMOVES services
- Simpler management

**Cons:**
- Larger docker-compose file
- Requires careful migration

### Option 2: Separate Compose File

Create `pmoves/docker-compose.supabase.yml` for Supabase services.

**Pros:**
- Separation of concerns
- Can be updated independently
- Easier to test

**Cons:**
- Two files to manage
- Network bridging required

---

## Environment Variable Architecture

### Understanding Docker Compose env_file Loading Order

```
1. docker-compose.yml is parsed
   → ${VAR} substitution happens HERE
   → Only sees host environment and FIRST env_file

2. Containers are created
   → env_file values are loaded HERE
   → Too late for ${VAR} substitution in docker-compose.yml
```

### Solution: Use Standard Names with Defaults

```yaml
# GOOD: Uses defaults if env variable not set
environment:
  - GOTRUE_JWT_SECRET=${JWT_SECRET:-default-secret}
  - GOTRUE_JWT_EXP=${JWT_EXPIRY:-3600}
  - ANON_KEY=${ANON_KEY:-default-key}

# BAD: Variables must be in env.shared or host environment
environment:
  - GOTRUE_JWT_SECRET=${SUPABASE_JWT_SECRET}  # SUPABASE_JWT_SECRET not visible
```

---

## Configuration Files

### env.supabase

Standard Supabase environment variables for PMOVES.AI:

```bash
# Secrets (CHANGE FOR PRODUCTION)
POSTGRES_PASSWORD=bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger
JWT_SECRET=Mk1YWigx/sFJcP/cN1yTreuIa0maXMekfZ46M5Ewq+s=
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Database
POSTGRES_HOST=supabase-db
POSTGRES_DB=pmoves
POSTGRES_PORT=5432

# Auth
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8000
JWT_EXPIRY=3600

# Kong
KONG_HTTP_PORT=8000
KONG_HTTPS_PORT=8443
```

---

## Service Changes

### auth (GoTrue)

**Before:**
```yaml
environment:
  - GOTRUE_JWT_SECRET=${SUPABASE_JWT_SECRET}
  - GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP}
```

**After:**
```yaml
environment:
  - GOTRUE_JWT_SECRET=${JWT_SECRET}
  - GOTRUE_JWT_EXP=${JWT_EXPIRY}
```

### storage

**Before:**
```yaml
environment:
  - ANON_KEY=${SUPABASE_PUBLISHABLE_KEY}
  - SERVICE_KEY=${SUPABASE_SECRET_KEY}
```

**After:**
```yaml
environment:
  - ANON_KEY=${ANON_KEY}
  - SERVICE_KEY=${SERVICE_ROLE_KEY}
```

---

## Migration Steps

1. **Backup current configuration**
   ```bash
   cp pmoves/docker-compose.yml pmoves/docker-compose.yml.backup-$(date +%Y%m%d_%H%M%S)
   cp pmoves/env.shared pmoves/env.shared.backup-$(date +%Y%m%d_%H%M%S)
   ```

2. **Stop existing Supabase services**
   ```bash
   cd pmoves
   docker compose stop supabase-db supabase-gotrue supabase-postgrest supabase-kong supabase-realtime supabase-storage supabase-studio
   ```

3. **Update docker-compose.yml**
   - Replace Supabase service definitions with unified versions
   - Update variable references to use standard names
   - Add missing services (imgproxy, meta, functions, analytics, vector, supavisor)

4. **Update env.shared**
   - Add standard Supabase variables (JWT_SECRET, JWT_EXPIRY, ANON_KEY, etc.)
   - Remove old SUPABASE_* prefixed variables after migration

5. **Start services**
   ```bash
   docker compose up -d supabase-db
   # Wait for db to be healthy
   docker compose up -d
   ```

6. **Verify**
   ```bash
   docker compose ps
   curl http://localhost:8000/api/health  # Kong
   curl http://localhost:3000/api/platform/profile  # Studio
   ```

---

## Port Mappings

| Service | Internal Port | External Port |
|---------|---------------|---------------|
| Kong HTTP | 8000 | 8000 |
| Kong HTTPS | 8443 | 8443 |
| Studio | 3000 | 3000 |
| GoTrue Auth | 9999 | - (via Kong) |
| PostgREST | 3000 | - (via Kong) |
| Realtime | 4000 | - |
| Storage API | 5000 | 5000 |
| Analytics | 4000 | - |
| PostgreSQL | 5432 | 54322 |
| Pooler (transaction) | 6543 | 6543 |

---

## Service Dependencies

```
db (PostgreSQL)
  ↓
vector → analytics → studio
  ↓                    ↓
meta ←─────────────────┘
  ↓
  ├─→ rest (PostgREST)
  ├─→ auth (GoTrue)
  ├─→ realtime
  ├─→ storage → imgproxy
  ├─→ functions
  └─→ supavisor (pooler)

kong (API Gateway)
  ↓ (proxies to all services)
```

---

## Security Notes

⚠️ **The following must be changed before production:**

1. `POSTGRES_PASSWORD` - Database password
2. `JWT_SECRET` - JWT signing secret
3. `ANON_KEY` - Public API key
4. `SERVICE_ROLE_KEY` - Service role key
5. `SECRET_KEY_BASE` - Rails secret key base
6. `VAULT_ENC_KEY` - Vault encryption key
7. `PG_META_CRYPTO_KEY` - Postgres meta encryption key
8. `DASHBOARD_PASSWORD` - Dashboard login password

---

## Troubleshooting

### Service won't start

Check logs:
```bash
docker compose logs supabase-auth
docker compose logs supabase-db
```

### Variable not found error

Verify variable exists in env.shared:
```bash
grep JWT_SECRET pmoves/env.shared
```

### Database connection error

Ensure db is healthy:
```bash
docker compose ps supabase-db
```

---

## Production Utilities

PMOVES.AI includes production utilities from PMOVES-supabase:

### Key Generation

Generate all required secrets for a fresh Supabase deployment:

```bash
cd pmoves
./scripts/supabase/generate-keys.sh
```

Generates: `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY`, `POSTGRES_PASSWORD`, etc.

### Password Rotation

Safely rotate all PostgreSQL database passwords:

```bash
cd pmoves
./scripts/supabase/db-passwd.sh
```

Updates all PostgreSQL roles and _analytics configuration.

## Production Patterns

See `PMOVES_SUPABASE_PRODUCTION_PATTERNS.md` for:
- Enterprise partitioning strategies
- Cloudflare Workers integration
- RLS policy best practices
- Edge Functions development patterns
- Realtime integration examples

## References

- PMOVES-supabase fork: `/PMOVES-supabase`
- Docker configuration: `PMOVES-supabase/docker/docker-compose.yml`
- Environment template: `PMOVES-supabase/docker/.env.example`
- Production utilities: `pmoves/scripts/supabase/`
- Production patterns: `pmoves/docs/PMOVES_SUPABASE_PRODUCTION_PATTERNS.md`
- Official docs: https://supabase.com/docs/guides/self-hosting/docker
