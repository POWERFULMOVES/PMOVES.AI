# PMOVES-supabase Comprehensive Exploration

**Date:** 2026-02-07

**Purpose:** Complete exploration of PMOVES-supabase fork to understand configuration options and integration points for PMOVES.AI

---

## PMOVES-supabase Fork Overview

**Location:** `/home/pmoves/PMOVES.AI/PMOVES-supabase`

**Branch:** main (aligned with Supabase self-hosted)

**Purpose:** Custom fork of Supabase for PMOVES.AI integration with:
- Standard Supabase variable naming
- Complete service stack (11 services)
- Production-ready configuration
- Docker Compose based deployment

---

## Service Inventory (PMOVES-supabase)

### Complete Service List

| # | Service | Container Name | Image | Purpose | Ports |
|---|---------|----------------|-------|---------|-------|
| 1 | studio | supabase-studio | supabase/studio:2026.01.27-sha-6aa59ff | Dashboard | 3000 |
| 2 | kong | supabase-kong | kong:2.8.1 | API Gateway | 8000, 8443 |
| 3 | auth | supabase-auth | supabase/gotrue:v2.185.0 | Authentication | 9999 |
| 4 | rest | supabase-rest | postgrest/postgrest:v14.3 | REST API | 3000 |
| 5 | realtime | realtime-dev.supabase-realtime | supabase/realtime:v2.72.0 | Websockets | 4000 |
| 6 | storage | supabase-storage | supabase/storage-api:v1.37.1 | File storage | 5000 |
| 7 | imgproxy | supabase-imgproxy | darthsim/imgproxy:v3.30.1 | Image processing | 5001 |
| 8 | meta | supabase-meta | supabase/postgres-meta:v0.95.2 | DB management | 8080 |
| 9 | functions | supabase-edge-functions | supabase/edge-runtime:v1.70.0 | Edge functions | - |
| 10 | analytics | supabase-analytics | supabase/logflare:1.30.3 | Logging | 4000 |
| 11 | db | supabase-db | supabase/postgres:15.8.1.085 | PostgreSQL | 5432 |
| 12 | vector | supabase-vector | timberio/vector:0.28.1-alpine | Log forwarding | 9001 |
| 13 | supavisor | supabase-pooler | supabase/supavisor:2.7.4 | Connection pooler | 6543 |

---

## Environment Variables (From .env.example)

### Secrets (MUST CHANGE FOR PRODUCTION)

```bash
POSTGRES_PASSWORD=your-super-secret-and-long-postgres-password
JWT_SECRET=your-super-secret-jwt-token-with-at-least-32-characters-long
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
DASHBOARD_USERNAME=supabase
DASHBOARD_PASSWORD=this_password_is_insecure_and_should_be_updated
SECRET_KEY_BASE=UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq
VAULT_ENC_KEY=your-32-character-encryption-key
PG_META_CRYPTO_KEY=your-encryption-key-32-chars-min
```

### Database Configuration

```bash
POSTGRES_HOST=db          # Service name in docker-compose
POSTGRES_DB=postgres      # Default database
POSTGRES_PORT=5432        # PostgreSQL port
```

### Auth Configuration (GoTrue)

```bash
SITE_URL=http://localhost:3000
ADDITIONAL_REDIRECT_URLS=
JWT_EXPIRY=3600
DISABLE_SIGNUP=false
API_EXTERNAL_URL=http://localhost:8000

# Email
ENABLE_EMAIL_SIGNUP=true
ENABLE_EMAIL_AUTOCONFIRM=false
ENABLE_ANONYMOUS_USERS=false
SMTP_ADMIN_EMAIL=admin@example.com
SMTP_HOST=supabase-mail
SMTP_PORT=2500
SMTP_USER=fake_mail_user
SMTP_PASS=fake_mail_password
SMTP_SENDER_NAME=fake_sender

# Phone
ENABLE_PHONE_SIGNUP=true
ENABLE_PHONE_AUTOCONFIRM=true

# Mailer URL paths
MAILER_URLPATHS_CONFIRMATION=/auth/v1/verify
MAILER_URLPATHS_INVITE=/auth/v1/verify
MAILER_URLPATHS_RECOVERY=/auth/v1/verify
MAILER_URLPATHS_EMAIL_CHANGE=/auth/v1/verify
```

### API Proxy (Kong)

```bash
KONG_HTTP_PORT=8000
KONG_HTTPS_PORT=8443
```

### PostgREST

```bash
PGRST_DB_SCHEMAS=public,storage,graphql_public
```

### Studio

```bash
STUDIO_DEFAULT_ORGANIZATION=Default Organization
STUDIO_DEFAULT_PROJECT=Default Project
SUPABASE_PUBLIC_URL=http://localhost:8000
IMGPROXY_ENABLE_WEBP_DETECTION=true
OPENAI_API_KEY=  # For SQL Editor Assistant
```

### Functions

```bash
FUNCTIONS_VERIFY_JWT=false
```

### Analytics (Logflare)

```bash
LOGFLARE_PUBLIC_ACCESS_TOKEN=your-super-secret-and-long-logflare-key-public
LOGFLARE_PRIVATE_ACCESS_TOKEN=your-super-secret-and-long-logflare-key-private
DOCKER_SOCKET_LOCATION=/var/run/docker.sock
```

### Supavisor (Connection Pooler)

```bash
POOLER_PROXY_PORT_TRANSACTION=6543
POOLER_DEFAULT_POOL_SIZE=20
POOLER_MAX_CLIENT_CONN=100
POOLER_TENANT_ID=your-tenant-id
POOLER_DB_POOL_SIZE=5
```

---

## Service Dependencies

```
vector (log forwarder)
  ↓ (healthy)
db (PostgreSQL)
  ↓ (healthy)
  ├─→ analytics (Logflare)
  │     ↓ (healthy)
  │     ├─→ studio
  │     ├─→ kong
  │     ├─→ auth
  │     ├─→ rest
  │     └─→ realtime
  ├─→ meta
  ├─→ rest (PostgREST)
  ├─→ auth (GoTrue)
  ├─→ realtime
  ├─→ storage → imgproxy
  ├─→ functions
  └─→ supavisor (pooler)

kong (API Gateway)
  ↓ (proxies to)
  ├─→ auth (:/auth/v1/*)
  ├─→ rest (:/rest/v1/*)
  ├─→ storage (:/storage/v1/*)
  ├─→ realtime (:/realtime/v1/*)
  └─→ functions (:/functions/v1/*)
```

---

## Network Configuration

```yaml
networks:
  default:
    name: supabase
```

All services communicate on the `supabase` network.

---

## Volume Mounts

### Studio
```yaml
volumes:
  - ./volumes/snippets:/app/snippets:Z           # SQL snippets
  - ./volumes/functions:/app/edge-functions:Z    # Edge functions
```

### Kong
```yaml
volumes:
  - ./volumes/api/kong.yml:/home/kong/temp.yml:ro,z
```

### Storage
```yaml
volumes:
  - ./volumes/storage:/var/lib/storage:z
```

### imgproxy
```yaml
volumes:
  - ./volumes/storage:/var/lib/storage:z
```

### Functions
```yaml
volumes:
  - ./volumes/functions:/home/deno/functions:Z
```

### Database (db)
```yaml
volumes:
  - ./volumes/db/realtime.sql:/docker-entrypoint-initdb.d/migrations/99-realtime.sql:Z
  - ./volumes/db/webhooks.sql:/docker-entrypoint-initdb.d/init-scripts/98-webhooks.sql:Z
  - ./volumes/db/roles.sql:/docker-entrypoint-initdb.d/init-scripts/99-roles.sql:Z
  - ./volumes/db/jwt.sql:/docker-entrypoint-initdb.d/init-scripts/99-jwt.sql:Z
  - ./volumes/db/data:/var/lib/postgresql/data:Z
  - ./volumes/db/_supabase.sql:/docker-entrypoint-initdb.d/migrations/97-_supabase.sql:Z
  - ./volumes/db/logs.sql:/docker-entrypoint-initdb.d/migrations/99-logs.sql:Z
  - ./volumes/db/pooler.sql:/docker-entrypoint-initdb.d/migrations/99-pooler.sql:Z
  - db-config:/etc/postgresql-custom
```

### Vector
```yaml
volumes:
  - ./volumes/logs/vector.yml:/etc/vector/vector.yml:ro,z
  - ${DOCKER_SOCKET_LOCATION}:/var/run/docker.sock:ro,z
```

### Supavisor
```yaml
volumes:
  - ./volumes/pooler/pooler.exs:/etc/pooler/pooler.exs:ro,z
```

---

## Health Checks

### Studio
```yaml
healthcheck:
  test: ["CMD", "node", "-e", "fetch('http://studio:3000/api/platform/profile').then((r) => {if (r.status !== 200) throw new Error(r.status)})"]
  timeout: 10s
  interval: 5s
  retries: 3
```

### Auth (GoTrue)
```yaml
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:9999/health"]
  timeout: 5s
  interval: 5s
  retries: 3
```

### Realtime
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sSfL --head -o /dev/null -H \"Authorization: Bearer ${ANON_KEY}\" http://localhost:4000/api/tenants/realtime-dev/health"]
  timeout: 5s
  interval: 30s
  retries: 3
  start_period: 10s
```

### Storage
```yaml
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://storage:5000/status"]
  timeout: 5s
  interval: 5s
  retries: 3
```

### imgproxy
```yaml
healthcheck:
  test: ["CMD", "imgproxy", "health"]
  timeout: 5s
  interval: 5s
  retries: 3
```

### Analytics (Logflare)
```yaml
healthcheck:
  test: ["CMD", "curl", "http://localhost:4000/health"]
  timeout: 5s
  interval: 5s
  retries: 10
```

### Database (db)
```yaml
healthcheck:
  test: ["CMD", "pg_isready", "-U", "postgres", "-h", "localhost"]
  interval: 5s
  timeout: 5s
  retries: 10
```

### Vector
```yaml
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://vector:9001/health"]
  timeout: 5s
  interval: 5s
  retries: 3
```

### Supavisor
```yaml
healthcheck:
  test: ["CMD", "curl", "-sSfL", "--head", "-o", "/dev/null", "http://127.0.0.1:4000/api/health"]
  interval: 10s
  timeout: 5s
  retries: 5
```

---

## Configuration Files

### Kong API Routes
**File:** `PMOVES-supabase/docker/volumes/api/kong.yml`

Defines API gateway routes for:
- `/auth/v1/*` → GoTrue (auth)
- `/rest/v1/*` → PostgREST (rest)
- `/storage/v1/*` → Storage
- `/realtime/v1/*` → Realtime
- `/functions/v1/*` → Edge Functions

### Vector Log Configuration
**File:** `PMOVES-supabase/docker/volumes/logs/vector.yml`

Configures log forwarding from Docker containers to Logflare (analytics).

### SQL Snippets
**Directory:** `PMOVES-supabase/docker/volumes/snippets/`

Reusable SQL snippets for Studio's SQL Editor.

### Edge Functions
**Directory:** `PMOVES-supabase/docker/volumes/functions/`

Serverless TypeScript/Deno functions.

---

## PMOVES-Specific Customizations

Based on exploration, PMOVES-supabase appears to follow standard Supabase conventions with minimal customizations.

**Key Points:**
1. Uses standard Supabase variable names (no SUPABASE_* prefixes)
2. Standard image versions from Supabase
3. Standard service configurations
4. No PMOVES-specific code changes detected

---

## Integration Points for PMOVES.AI

### 1. Archon Integration
- **Connection:** Via PostgREST API (port 3000 internally, 8000 via Kong)
- **Authentication:** JWT tokens from GoTrue
- **Environment:** `ARCHON_SUPABASE_BASE_URL=http://postgrest:3000`

### 2. Agent Zero Integration
- **Connection:** Via Supabase client libraries
- **Authentication:** Service role key for backend operations
- **Database:** Direct PostgreSQL connection on port 5432

### 3. NATS Event Publishing
- **Potential:** Supabase webhooks can publish to NATS
- **Implementation:** Custom function or trigger in PostgreSQL
- **Subjects:** `supabase.*`, `ingest.*`, etc.

### 4. Authentication Flow
```
User → Studio → Kong → GoTrue → JWT Token
  ↓
JWT Token → Kong → PostgREST/Storage/etc.
```

### 5. Storage Integration
- **Files:** Stored in `/var/lib/storage` (or S3)
- **Access:** Via Storage API or MinIO
- **Transformation:** imgproxy for image processing

---

## Security Considerations

### Production Requirements

1. **Generate new secrets:**
   ```bash
   openssl rand -base64 32  # JWT_SECRET
   openssl rand -base64 32  # VAULT_ENC_KEY
   openssl rand -base64 32  # PG_META_CRYPTO_KEY
   ```

2. **Generate new API keys:**
   - ANON_KEY (public, limited access)
   - SERVICE_ROLE_KEY (secret, full access)

3. **Configure SMTP:**
   - For email authentication
   - For password recovery

4. **Enable JWT verification:**
   - Set `FUNCTIONS_VERIFY_JWT=true` for production

5. **Network isolation:**
   - Use separate networks for different tiers
   - Restrict access to sensitive services

---

## Differences from Upstream Supabase

Based on comparison with official Supabase self-hosted docs:

1. **Image versions:** PMOVES-supabase tracks specific stable versions
2. **Configuration:** Standard Supabase defaults
3. **Services:** Complete Supabase stack (no services removed)
4. **Network:** Standard single-network configuration

---

## Recommendations for PMOVES.AI Integration

### 1. Adopt Standard Variable Names
Replace custom `SUPABASE_*` prefixes with standard names:
- `SUPABASE_JWT_SECRET` → `JWT_SECRET`
- `SUPABASE_JWT_EXP` → `JWT_EXPIRY`
- `SUPABASE_PUBLISHABLE_KEY` → `ANON_KEY`
- etc.

### 2. Add Missing Services
Include all services from PMOVES-supabase:
- imgproxy (image transformation)
- meta (database management)
- functions (edge functions)
- analytics (log aggregation)
- vector (log forwarding)
- supavisor (connection pooling)

### 3. Use Separate env.supabase File
Creates cleaner separation and follows Supabase conventions.

### 4. Adopt PMOVES Network Configuration
Integrate Supabase services into PMOVES networks:
- `pmoves_data` for database tier
- `pmoves_api` for API tier
- `pmoves_app` for application tier
- `pmoves_bus` for message bus

### 5. Implement Proper Health Checks
All Supabase services should have healthchecks for dependency management.

---

## Files Created During Exploration

1. **pmoves/env.supabase** - Standard Supabase environment variables
2. **pmoves/docs/SUPABASE_UNIFIED_SETUP.md** - Unified configuration guide
3. **pmoves/docs/PMOVES_SUPABASE_CURRENT_STATE_ANALYSIS.md** - Current state analysis
4. **pmoves/docs/PMOVES_SUPABASE_COMPREHENSIVE_EXPLORATION.md** - This document

---

## References

- PMOVES-supabase fork: `/PMOVES-supabase`
- Docker configuration: `PMOVES-supabase/docker/docker-compose.yml`
- Environment template: `PMOVES-supabase/docker/.env.example`
- Official docs: https://supabase.com/docs/guides/self-hosting/docker
- Kong configuration: `PMOVES-supabase/docker/volumes/api/kong.yml`
- Vector configuration: `PMOVES-supabase/docker/volumes/logs/vector.yml`

---

**Status:** ✅ Exploration complete. Ready for implementation.
