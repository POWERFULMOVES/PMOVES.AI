# Observability Integration: Supabase Stack

**Status:** Integrated - Dashboard and probes configured
**Date:** 2026-02-04
**Related:** [SUBMODULE_MIGRATIONS.md](SUBMODULE_MIGRATIONS.md), [PRODUCTION_SUPABASE.md](PRODUCTION_SUPABASE.md)

## Overview

The PMOVES observability stack (Prometheus, Grafana, Loki, cAdvisor) now includes comprehensive monitoring for self-hosted Supabase services. This allows real-time visibility into service health, performance, and resource usage during startup and operation.

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PMOVES Monitoring Stack                   │
├─────────────────────────────────────────────────────────────┤
│  Prometheus (9090)  ← Scrapes metrics from all sources      │
│  Grafana (3002)     ← Dashboards and visualization           │
│  Loki (3100)        ← Log aggregation                        │
│  cAdvisor (8080)    ← Container metrics (CPU, memory, I/O)   │
│  Blackbox (9115)    ← HTTP health check probes               │
└─────────────────────────────────────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    │                │
            ┌───────▼──────┐  ┌─────▼────────────┐
            │   Metrics    │  │   Blackbox       │
            │   Scrape     │  │   HTTP Probes    │
            └───────┬──────┘  └─────┬────────────┘
                    │                │
        ┌───────────┼────────────────┼────────────┐
        │           │                │            │
    ┌───▼───┐ ┌───▼───┐  ┌──────┐ ┌──────┐ ┌─────┐
    │ GoTrue│ │PostgREST│ │Realtime│Storage│Studio│
    │ :9999 │ │ :3000 │ │ :4000│ :5000│ :3K  │
    └───┬───┘ └───┬───┘  └───┬──┘ └───┬──┘ └───┬─┘
        │         │           │        │         │
        └─────────┴───────────┴────────┴─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Supabase DB      │
                    │  PostgreSQL 17    │
                    │  (via cAdvisor)   │
                    └───────────────────┘
```

## Supabase Services Monitored

| Service | Port | Health Endpoint | Metrics |
|---------|------|-----------------|---------|
| GoTrue | 9999 | `/health` | Blackbox probe |
| PostgREST | 3000 | `/` | Blackbox probe |
| Realtime | 4000 | `/health` | Native `/metrics` |
| Storage | 5000 | `/status` | Blackbox probe |
| Studio | 3000 | `/api/profile` | Blackbox probe |
| PostgreSQL | 5432 | `pg_isready` | cAdvisor (container) |

## Dashboard: Supabase Stack Monitoring

**Location:** Grafana → "Supabase Stack Monitoring"
**Dashboard ID:** `supabase-stack`
**Refresh:** 10 seconds

### Panels

1. **Service Health Status** (6 panels)
   - GoTrue /health
   - PostgREST /
   - Realtime /health
   - Storage /status
   - Studio API
   - PostgreSQL (via cAdvisor)

2. **Response Times**
   - HTTP probe duration for all Supabase services

3. **Container Metrics**
   - CPU usage per service
   - Memory usage per service
   - Network I/O

4. **Logs**
   - Real-time log streaming from Loki

5. **Summary**
   - Total services up (out of 6)
   - Service status table

## Configuration Files

### Prometheus Scrape Config

**File:** `monitoring/prometheus/prometheus.yml`

```yaml
# Realtime exposes /metrics endpoint
- job_name: supabase-realtime
  static_configs:
    - targets: ["realtime:4000"]
  metrics_path: /metrics

# Blackbox HTTP probes for Supabase services
- job_name: supabase_health
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - http://realtime:4000/health
        - http://gotrue:9999/health
        - http://storage:5000/status
        - http://postgrest:3000/
        - http://studio:3000/api/profile
```

### Grafana Dashboard

**File:** `monitoring/grafana/dashboards/supabase.json`

Auto-provisioned on Grafana startup. No manual import needed.

## Quick Start

### 1. Start Monitoring Stack (if not running)

```bash
cd pmoves
make up-monitoring
```

Expected output:
```
⛳ Starting monitoring stack (Prometheus, Grafana, Loki, Promtail, blackbox, cAdvisor)...
✔ Prometheus: http://localhost:9090
✔ Grafana: http://localhost:3002 (admin/admin)
✔ Loki: http://localhost:3100
```

### 2. Start Supabase Stack

```bash
# Using tier-based environment
PUBLISHED_AGENTS=1 docker compose --profile supabase up -d
```

### 3. View Dashboard

1. Open Grafana: http://localhost:3002
2. Login: `admin` / `admin`
3. Navigate to: Dashboards → "Supabase Stack Monitoring"

### 4. Verify Prometheus Targets

```bash
curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

Expected output includes:
```json
{"job": "supabase-realtime", "health": "up"}
{"job": "supabase_health", "health": "up"}
```

## Service Startup Metrics

### Observability During Bring-Up

The monitoring stack starts **before** data services in the PMOVES bring-up sequence:

```
Phase 1: Monitoring (FIRST)
  └─ Prometheus, Grafana, Loki, cAdvisor

Phase 2: Data Tier
  └─ Supabase (db, postgrest, gotrue, realtime, storage, studio)

Phase 3: Core Services
  └─ TensorZero, Hi-RAG, Agent Zero, etc.
```

This means you can watch services come online in real-time via the Grafana dashboard.

### Startup Order Visualization

As services start, you'll see:
1. **Container appear** in cAdvisor metrics
2. **Health probe succeed** in blackbox metrics
3. **Status turn GREEN** on dashboard

### Typical Startup Sequence

| Service | Startup Time | Health Check |
|---------|--------------|--------------|
| PostgreSQL | ~30s | pg_isready |
| PostgREST | ~5s after DB | HTTP 200 on `/` |
| GoTrue | ~5s after DB | HTTP 200 on `/health` |
| Realtime | ~10s after DB | HTTP 200 on `/health` |
| Storage | ~5s after PostgREST | HTTP 200 on `/status` |
| Studio | ~5s after PostgREST | HTTP 200 on `/api/profile` |

Total: ~45-60 seconds for full Supabase stack

## Alerts

### Configured Alerts

The dashboard includes Grafana alerts for critical services:

| Alert | Condition | Duration |
|-------|-----------|----------|
| GoTrue Auth Down | `probe_success < 0.5` | 2m |
| PostgREST Down | `probe_success < 0.5` | 2m |

### Viewing Alert Rules

1. Grafana → Alerting → Alert Rules
2. Filter by: "Supabase"

## Optional: PostgreSQL Metrics Exporter

For deeper database metrics (connections, locks, queries), add the postgres_exporter:

### 1. Add to docker-compose.monitoring.yml

```yaml
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    restart: unless-stopped
    environment:
      - DATA_SOURCE_NAME=postgresql://pmoves:password@supabase-db:5432/pmoves?sslmode=disable
    ports:
      - "9187:9187"
    networks: [pmoves_monitoring]
    profiles: ["postgres-metrics"]
```

### 2. Enable postgres_exporter scrape in prometheus.yml

Already configured in `monitoring/prometheus/prometheus.yml`:

```yaml
  - job_name: supabase-postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]
```

### 3. Start with profile

```bash
docker compose -f monitoring/docker-compose.monitoring.yml --profile postgres-metrics up -d
```

### Available Metrics (with exporter)

- `pg_stat_database_*`: Database stats
- `pg_stat_bgwriter_`: Background writer metrics
- `pg_replication_*`: Replication status
- `pg_locks_*`: Lock contention
- `pg_stat_statements_*`: Query performance (if pg_stat_statements enabled)

## Troubleshooting

### Dashboard Shows "No Data"

1. **Check Prometheus targets:**
   ```bash
   curl -s "http://localhost:9090/api/v1/targets" | jq '.data.activeTargets[] | select(.labels.job | contains("supabase"))'
   ```

2. **Verify blackbox exporter:**
   ```bash
   curl -f "http://localhost:9115/probe?module=http_2xx&target=http://gotrue:9999/health"
   ```

3. **Check service DNS:**
   ```bash
   docker exec prometheus ping -c 1 gotrue
   ```

### Services Show Red

1. **Check service is running:**
   ```bash
   docker ps | grep -E "(gotrue|postgrest|realtime|storage|studio)"
   ```

2. **Check service health directly:**
   ```bash
   curl http://localhost:9999/health  # GoTrue
   curl http://localhost:3000/       # PostgREST
   curl http://localhost:4000/health # Realtime
   curl http://localhost:5000/status # Storage
   ```

3. **View service logs:**
   ```bash
   docker logs gotrue --tail 50
   ```

### cAdvisor Shows No Containers

1. **Check cAdvisor is running:**
   ```bash
   curl http://localhost:9180/metrics | grep container
   ```

2. **Verify permissions:**
   ```bash
   docker inspect cadvisor | grep -A5 "Mounts"
   ```

## Integration with PMOVES Bring-Up

### Monitoring-First Philosophy

The PMOVES bring-up sequence ensures observability is available **before** services start:

```bash
# Full bring-up with monitoring
make bringup-with-ui
```

This executes:
1. `make up-monitoring` - Start observability stack
2. `make up-supabase` - Start data tier (now observable!)
3. `make up-core` - Start core services (observable)
4. `make up-ui` - Start UI layer

### Real-Time Service Visualization

During bring-up, watch the Grafana dashboard to see:
- Containers appearing in cAdvisor
- Services passing health checks
- Resource usage stabilizing

## Advanced: Custom Metrics

### Adding Application Metrics

Services can expose custom metrics on `/metrics`:

```python
from prometheus_client import Counter, start_http_server

request_counter = Counter('app_requests_total', 'Total requests')
start_http_server(8081)  # Metrics on :8081/metrics
```

### Adding to Prometheus

```yaml
# In prometheus.yml
- job_name: my_custom_service
  static_configs:
    - targets: ["my-service:8081"]
```

## Bring-Up Troubleshooting (2026-02-06)

### Common Issues and Fixes

#### 1. PostgreSQL Peer Authentication Errors

**Error:** `FATAL: peer authentication failed for user "pmoves"`

**Cause:** Docker exec without `-h localhost` uses Unix socket peer auth instead of password auth.

**Fix:** Makefile migration commands updated to use `-h localhost`:
```bash
docker exec -i pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves
```

#### 2. Missing Schemas and Roles

**Error:** `ERROR: schema "auth" does not exist` or `role "postgres" does not exist`

**Cause:** Fresh database volume doesn't have Supabase-specific schemas.

**Fix:** Run schema creation before first bring-up:
```bash
docker exec -i pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves <<'SQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS graphql_public;
CREATE SCHEMA IF NOT EXISTS pmoves_core;
CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';
ALTER ROLE postgres WITH PASSWORD 'postgres';
SQL
```

#### 3. Kong Migration Bootstrap

**Error:** Kong fails with database errors.

**Fix:** Bootstrap Kong migrations before starting Kong:
```bash
docker run --rm --network pmoves_data \
  -e KONG_DATABASE=postgres \
  -e KONG_PG_HOST=supabase-db \
  -e KONG_PG_DATABASE=pmoves \
  -e KONG_PG_USER=pmoves \
  -e KONG_PG_PASSWORD=<your_password> \
  kong:3.7.1 kong migrations bootstrap --yes
```

#### 4. Neo4j 5.x Config Validation

**Error:** `Failed to read config: Unrecognized setting. No declared setting with name: PASSWORD`

**Cause:** Neo4j 5.x has stricter config validation.

**Fix:** Add to docker-compose.yml environment:
```yaml
environment:
- NEO4J_server_config_strict__validation_enabled=false
```

#### 5. Storage Service Region

**Error:** `Error: Region is missing`

**Fix:** Set in `env.tier-supabase`:
```bash
SUPABASE_STORAGE_REGION=us-east-1
```

### Complete Bring-Up Sequence

For fresh Supabase bring-up on PMOVES.AI-Edition-Hardened:

```bash
# 1. Start Supabase DB only
make up-supabase  # Starts DB first

# 2. Create schemas and roles (manual first-time setup)
docker exec -i pmoves-supabase-db-1 psql -h localhost -U pmoves -d pmoves <<'SQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS storage;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS graphql_public;
CREATE SCHEMA IF NOT EXISTS pmoves_core;
CREATE SCHEMA IF NOT EXISTS pmoves;
CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';
ALTER ROLE postgres WITH PASSWORD 'postgres';
GRANT ALL ON SCHEMA auth, storage, extensions, graphql_public, pmoves_core, pmoves TO postgres;
GRANT ALL ON SCHEMA pmoves_core, pmoves TO pmoves;
GRANT USAGE ON SCHEMA pmoves_core, pmoves TO anon, authenticated, service_role;
SQL

# 3. Bootstrap Kong migrations
docker run --rm --network pmoves_data \
  -e KONG_DATABASE=postgres \
  -e KONG_PG_HOST=supabase-db \
  -e KONG_PG_DATABASE=pmoves \
  -e KONG_PG_USER=pmoves \
  -e KONG_PG_PASSWORD=${POSTGRES_PASSWORD} \
  kong:3.7.1 kong migrations bootstrap --yes

# 4. Run Supabase migrations and seeds
make supabase-bootstrap

# 5. Start remaining data tier
make up-data-tier

# 6. Seed Neo4j
make neo4j-bootstrap

# 7. Seed Qdrant/Meili
make seed-data
```

### Migration File Notes

Some migration files in `pmoves/supabase/migrations/` use deprecated `uuid_generate_v4()` which requires `uuid-ossp` extension. For PostgreSQL 17+, these should be updated to use `gen_random_uuid()`.

**Files affected (as of 2026-02-06):**
- `20250204000000_channel_monitor_tables.sql`
- `20251230000000_tokenism_simulator.sql`

**Migration fix pattern:**
```sql
-- OLD (requires uuid-ossp extension)
id UUID PRIMARY KEY DEFAULT uuid_generate_v4()

-- NEW (PostgreSQL 13+ built-in)
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

## CI/CD Update Strategy (2026-02-06)

### Supabase Submodule Alignment

The PMOVES-supabase submodule tracks the official Supabase self-hosted stack
and must stay synchronized with upstream releases.

**Current Configuration:**
- Submodule: `PMOVES-supabase`
- Branch: `PMOVES.AI-Edition-Hardened`
- Remote: `https://github.com/POWERFULMOVES/PMOVES-supabase.git`
- Status: Proper gitlink (fixed 2026-02-06)

### Update Procedure

To update Supabase to a new version:

```bash
# 1. Fetch latest from upstream
cd PMOVES-supabase
git fetch origin

# 2. Checkout the target version tag or commit
git checkout <version_tag>  # e.g., v1.50.0

# OR update to latest commit on Hardened branch:
git checkout origin/PMOVES.AI-Edition-Hardened

# 3. Update the main repo's submodule reference
cd ..
git add PMOVES-supabase
git commit -m "chore(supabase): Update to latest Hardened"
```

### Environment Loading Fix (Critical)

**Issue**: Docker Compose variable expansion (`${VAR}`) requires variables
to be in the shell environment at compose-time. The `env_file` directive
only sets variables inside containers, not for compose expansion.

**Solution**: Always use `scripts/with-env.sh` to load environment files
before running Docker Compose commands.

```bash
# From repo root (/home/pmoves/PMOVES.AI):
# CORRECT - Sources environment files first
source pmoves/scripts/with-env.sh
docker compose -p pmoves -f pmoves/docker-compose.yml up -d

# INCORRECT - Variables won't be expanded
docker compose -p pmoves -f pmoves/docker-compose.yml up -d

# From pmoves/ directory:
source scripts/with-env.sh
docker compose -p pmoves -f docker-compose.yml up -d
```

**Makefile Integration**: All make targets properly source the environment:
```bash
make up-supabase      # Sources with-env.sh automatically
make up-data-tier     # Sources with-env.sh automatically
```

### Realtime Service Requirements

Supabase Realtime has specific environment requirements:

1. **SECRET_KEY_BASE**: Must be at least 64 bytes
   ```bash
   # SUPABASE_REALTIME_SECRET maps to SECRET_KEY_BASE in Realtime
   # Must be at least 64 bytes
   SUPABASE_REALTIME_SECRET=$(openssl rand -base64 64)
   ```

2. **Database Credentials**: Must use TCP connection (`-h localhost`)
   - Peer authentication fails for Docker exec connections

3. **Environment File**: Create from example if needed
   ```bash
   cp pmoves/env.tier-supabase.example pmoves/env.tier-supabase
   # Then edit pmoves/env.tier-supabase with real values
   ```

4. **Required Variables** (in `pmoves/env.tier-supabase`):
   - `POSTGRES_USER=pmoves`
   - `POSTGRES_PASSWORD=<set strong password>`
   - `POSTGRES_DB=pmoves`
   - `SUPABASE_JWT_SECRET=<generate with openssl rand -base64 32>`
   - `SUPABASE_REALTIME_SECRET=<generate with openssl rand -base64 64>`

### Key Submodules Branch Alignment (2026-02-06)

Most PMOVES submodules are aligned to `PMOVES.AI-Edition-Hardened`. See `.gitmodules`
for complete list (60+ submodules).

| Submodule | Branch | Notes |
|-----------|--------|-------|
| PMOVES-Archon | PMOVES.AI-Edition-Hardened | Fixed from feat/personas-clean-rebase |
| PMOVES-BoTZ | PMOVES.AI-Edition-Hardened | Standalone submodule |
| PMOVES-DoX | PMOVES.AI-Edition-Hardened | External submodule (switched 2026-02-06) |
| PMOVES-ToKenism-Multi | PMOVES.AI-Edition-Hardened | Reset to origin |
| PMOVES-supabase | PMOVES.AI-Edition-Hardened | Re-registered as gitlink |
| PMOVES-Headscale | PMOVES.AI-Edition-Hardened | Branch created 2026-02-06 |

**Verify alignment:**
```bash
# Check submodule status (no prefix = clean, + = modified, - = uninitialized)
git submodule status

# Verify all submodules match recorded branch
git submodule status | grep -v "^ "
```

## Related Documentation

- [PRODUCTION_SUPABASE.md](PRODUCTION_SUPABASE.md) - Supabase setup and architecture
- [PORT_REGISTRY.md](PORT_REGISTRY.md) - Complete port assignments
- [SUBMODULE_MIGRATIONS.md](SUBMODULE_MIGRATIONS.md) - Database migration procedures
- [PRODUCTION_SINGLE_HOST.md](PRODUCTION_SINGLE_HOST.md) - Full deployment guide
