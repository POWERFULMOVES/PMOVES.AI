# PMOVES-Supabase Integration Guide

**Status:** ⚠️ **CRITICAL VARIABLE MISMATCH FOUND**

**Date:** 2026-02-07

---

## Critical Finding

PMOVES-supabase (the fork we should be using) follows standard Supabase naming conventions, but `pmoves/docker-compose.yml` uses custom `SUPABASE_*` prefixed variables that don't match.

This mismatch is causing Supabase service failures.

---

## Variable Name Mapping

| PMOVES-supabase Standard | pmoves/docker-compose.yml (INCORRECT) | Notes |
|--------------------------|----------------------------------------|-------|
| `JWT_SECRET` | `SUPABASE_JWT_SECRET` | ✅ Fixed in env.shared |
| `JWT_EXPIRY` | `SUPABASE_JWT_EXP` | ✅ Fixed in env.shared |
| `ANON_KEY` | `SUPABASE_ANON_KEY` | ❌ Mismatch |
| `SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_ROLE_KEY` | ❌ Mismatch |
| `SITE_URL` | `SUPABASE_SITE_URL` | ❌ Mismatch |
| `API_EXTERNAL_URL` | `SUPABASE_PUBLIC_URL` | ❌ Mismatch |
| `POSTGRES_HOST=db` | `POSTGRES_HOST=supabase-db` | Different service name |
| `POSTGRES_DB=postgres` | `POSTGRES_DB=pmoves` | Different DB name |
| `POSTGRES_PORT=5432` | `POSTGRES_PORT=5432` | ✅ Match |

---

## PMOVES-Supabase Standard Configuration

Based on `PMOVES-supabase/docker/.env.example`, the standard environment variables are:

### Secrets (MUST CHANGE FOR PRODUCTION)
```bash
POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password
JWT_SECRET=your-super-secret-jwt-token-with-at-least-32-characters-long
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Generate new
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Generate new
SECRET_KEY_BASE=UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq
VAULT_ENC_KEY=your-32-character-encryption-key
PG_META_CRYPTO_KEY=your-encryption-key-32-chars-min
```

### Database Connection
```bash
POSTGRES_HOST=db           # Service name in docker-compose
POSTGRES_DB=postgres       # Default database name
POSTGRES_PORT=5432         # Default PostgreSQL port
```

### Auth Configuration
```bash
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8000
JWT_EXPIRY=3600            # JWT token expiration in seconds
DISABLE_SIGNUP=false
ADDITIONAL_REDIRECT_URLS=
```

### Studio Configuration
```bash
STUDIO_DEFAULT_ORGANIZATION=Default Organization
STUDIO_DEFAULT_PROJECT=Default Project
SUPABASE_PUBLIC_URL=http://localhost:8000
```

### API Proxy (Kong)
```bash
KONG_HTTP_PORT=8000
KONG_HTTPS_PORT=8443
```

---

## Required Actions

### 1. Update pmoves/docker-compose.yml Variable References

**Change from:**
```yaml
environment:
  - GOTRUE_JWT_SECRET=${SUPABASE_JWT_SECRET}
  - GOTRUE_JWT_EXP=${SUPABASE_JWT_EXP}
  - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
```

**Change to:**
```yaml
environment:
  - GOTRUE_JWT_SECRET=${JWT_SECRET}
  - GOTRUE_JWT_EXP=${JWT_EXPIRY}
  - SUPABASE_ANON_KEY=${ANON_KEY}
```

### 2. Create Correct env.shared Variables

Add to `pmoves/env.shared`:
```bash
# Standard Supabase variables (matching PMOVES-supabase conventions)
JWT_SECRET=Mk1YWigx/sFJcP/cN1yTreuIa0maXMekfZ46M5Ewq+s=
JWT_EXPIRY=3600
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWRlbW8iLCJpYXQiOjE2NDE3NjkyMDAsImV4cCI6MTc5OTUzNTYwMH0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UtZGVtbyIsImlhdCI6MTY0MTc2OTIwMCwiZXhwIjoxNzk5NTM1NjAwfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q
SITE_URL=http://localhost:3000
API_EXTERNAL_URL=http://localhost:8000
SUPABASE_PUBLIC_URL=http://localhost:8000

# Database connection for PMOVES integration
POSTGRES_HOST=supabase-db
POSTGRES_DB=pmoves
POSTGRES_PORT=5432
POSTGRES_PASSWORD=bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger
```

### 3. Service Name Mapping

PMOVES-supabase uses these service names in its docker-compose:
- `db` (PostgreSQL) → pmoves uses `supabase-db`
- `studio` → pmoves uses `supabase-studio`
- `kong` → pmoves uses `supabase-kong`
- `auth` → pmoves uses `supabase-gotrue`
- `api` (PostgREST) → pmoves uses `supabase-postgrest`
- `realtime` → pmoves uses `supabase-realtime`
- `storage` → pmoves uses `supabase-storage`
- `meta` (postgres-meta) → pmoves may not have this

---

## Supabase Services Stack (from PMOVES-supabase)

Based on `PMOVES-supabase/docker/docker-compose.yml`:

| Service | Image | Container Name | Purpose |
|---------|-------|----------------|---------|
| Studio | supabase/studio:2026.01.27-sha-6aa59ff | supabase-studio | Dashboard |
| Kong | kong:2.8.1 | supabase-kong | API Gateway |
| Auth | supabase/gotrue:v2.185.0 | supabase-auth | Authentication |
| PostgREST | postgrest/postgrest:v14.3 | supabase-postgrest | REST API |
| Realtime | supabase/realtime:v2.72.0 | supabase-realtime | Websockets |
| Storage | supabase/storage:v1.37.1 | supabase-storage | File storage |
| imgproxy | darthsim/imgproxy:v3.30.1 | supabase-imgproxy | Image processing |
| meta | supabase/postgres-meta:v0.95.2 | supabase-meta | DB management |
| db | supabase/postgres:15.8.1.085 | supabase-db | PostgreSQL |
| edge-runtime | supabase/edge-runtime:v1.70.0 | supabase-edge | Edge functions |
| analytics | logflare/logflare:1.30.3 | supabase-analytics | Logging |

---

## Correct Startup Procedure for PMOVES.AI

### Option 1: Use PMOVES-supabase Docker Compose Directly

```bash
cd PMOVES-supabase/docker

# Copy and configure env file
cp .env.example .env
# Edit .env with production values

# Start Supabase stack
docker compose up -d

# Services will be available at:
# Studio: http://localhost:3000
# API: http://localhost:8000
# Auth: http://localhost:9999
```

### Option 2: Integrate into pmoves/docker-compose.yml

If integrating into the main PMOVES.AI stack:

1. **Align service names** or use `container_name` aliases
2. **Use standard variable names** from PMOVES-supabase
3. **Match network configuration** (PMOVES-supabase uses network `supabase`)
4. **Include all required services** from PMOVES-supabase stack

---

## Security Notes

⚠️ **The default values in PMOVES-supabase/.env.example are NOT secure for production:**

Before going to production:
1. Generate new `POSTGRES_PASSWORD`
2. Generate new `JWT_SECRET` (32+ characters)
3. Generate new `ANON_KEY` and `SERVICE_ROLE_KEY`
4. Update `SECRET_KEY_BASE`
5. Update `VAULT_ENC_KEY`
6. Update `PG_META_CRYPTO_KEY`

---

## References

- PMOVES-supabase fork: `/PMOVES-supabase`
- Docker configuration: `PMOVES-supabase/docker/docker-compose.yml`
- Environment template: `PMOVES-supabase/docker/.env.example`
- Official docs: https://supabase.com/docs/guides/self-hosting/docker

---

**Status:** ✅ **DOCUMENTATION COMPLETE - READY FOR IMPLEMENTATION**

## Implementation Deliverables Created

1. **pmoves/env.supabase** - Standard Supabase environment variables file
2. **pmoves/docs/SUPABASE_UNIFIED_SETUP.md** - Complete unified setup guide
3. **pmoves/docs/PMOVES_SUPABASE_CURRENT_STATE_ANALYSIS.md** - Detailed state analysis
4. **pmoves/docs/PMOVES_SUPABASE_COMPREHENSIVE_EXPLORATION.md** - PMOVES-supabase fork exploration

## Next Action: Implementation Steps

1. **Update env.shared** with standard variables:
   ```bash
   # Add these standard Supabase variables to env.shared
   JWT_SECRET=Mk1YWigx/sFJcP/cN1yTreuIa0maXMekfZ46M5Ewq+s=
   JWT_EXPIRY=3600
   ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWRlbW8iLCJpYXQiOjE2NDE3NjkyMDAsImV4cCI6MTc5OTUzNTYwMH0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE
   SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UtZGVtbyIsImlhdCI6MTY0MTc2OTIwMCwiZXhwIjoxNzk5NTM1NjAwfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q
   SITE_URL=http://localhost:3000
   API_EXTERNAL_URL=http://localhost:8000
   SUPABASE_PUBLIC_URL=http://localhost:8000
   ```

2. **Update docker-compose.yml** variable references:
   - Change `${SUPABASE_JWT_SECRET}` → `${JWT_SECRET}`
   - Change `${SUPABASE_JWT_EXP}` → `${JWT_EXPIRY}`
   - Change `${SUPABASE_PUBLISHABLE_KEY}` → `${ANON_KEY}`
   - Change `${SUPABASE_SECRET_KEY}` → `${SERVICE_ROLE_KEY}`

3. **Add missing services** from PMOVES-supabase (imgproxy, meta, functions, analytics, vector, supavisor)

4. **Restart services:**
   ```bash
   cd pmoves
   docker compose down supabase-*
   docker compose up -d supabase-db
   # Wait for db to be healthy
   docker compose up -d
   ```

See `SUPABASE_UNIFIED_SETUP.md` for complete implementation guide.
