# Production Readiness Report - 2026-02-07

**Status:** ⚠️ **NOT READY** - Critical security configuration required

---

## Executive Summary

| Category | Status | Issues |
|----------|--------|--------|
| **API Keys** | 🔴 Critical | All LLM provider keys are empty |
| **Supabase** | 🟡 Partial | InitDB files restored, migrations run, some env issues |
| **CHIT Security** | 🔴 Critical | Encryption disabled, signatures disabled |
| **Service Health** | 🟡 Partial | 45 services running, 5 unhealthy/restarting |

---

## Service Health Status (2026-02-07 23:28 UTC)

### Healthy Services ✅
- nats, archon, agent-zero, tensorzero-gateway, tensorzero-clickhouse, tensorzero-ui
- supabase-db, supabase-postgrest, supabase-kong, supabase-gotrue, supabase-studio, supabase-storage, supabase-realtime
- neo4j, qdrant, meilisearch, minio
- hi-rag-gateway-v2, hi-rag-gateway-v2-gpu, deepresearch, supaserch
- prometheus, grafana, loki, promtail, blackbox
- gpu-orchestrator, github-runner-ctl, botz-gateway

### Unhealthy/Restarting Services ⚠️
| Service | Status | Issue |
|---------|--------|-------|
| **channel-monitor** | Restarting | PostgreSQL connection to `host.docker.internal:65432` - needs internal service name |
| **ultimate-tts-studio** | Restarting | Missing `gradio[mcp]` dependency |
| **model-registry** | Unhealthy | Running but healthcheck failing |
| **retrieval-eval** | Restarting | Missing `/app/server.py` entrypoint |
| **comfy-watcher** | Restarting | Missing `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` |

---

## Fixes Applied (2026-02-07)

### 1. Database Schema Files Restored ✅
**Issue:** Missing initdb SQL files caused migration failures
- **Fixed:** Restored from git history (commit 0498c3bf):
  - `00_pmoves_schema.sql` - Creates pmoves_core schema
  - `01_public_init.sql` through `15_user_personalization.sql`

### 2. NATS Healthcheck Added ✅
**Issue:** NATS container had no healthcheck, causing dependency failures
- **Fixed:** Added healthcheck to `docker-compose.yml` for NATS service

### 3. Archon NATS Authorization Fixed ✅
**Issue:** Archon couldn't connect to NATS due to missing credentials
- **Root cause:** `NATS_URL=${NATS_URL:-nats://nats:4222}` default in docker-compose.yml overrode env_file
- **Fixed:** Removed hardcoded NATS_URL from archon environment section
- **Result:** NATS_URL now comes from `env.tier-agent` with credentials: `nats://nats:pmoves@nats:4222`

---

## Remaining Issues Requiring Attention

### 5. Service Configuration Issues 🔴

#### channel-monitor - PostgreSQL Connection
**Error:** `ConnectionRefusedError: postgresql://postgres:postgres@host.docker.internal:65432/postgres`

**Fix Required:** Update `CHANNEL_MONITOR_DATABASE_URL` in env.shared to use internal service:
```bash
# Change from:
CHANNEL_MONITOR_DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:65432/postgres
# To:
CHANNEL_MONITOR_DATABASE_URL=postgresql://pmoves:bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger@supabase-db:5432/pmoves
```

#### ultimate-tts-studio - Missing Dependency
**Error:** `ImportError: gradio[mcp] not installed`

**Fix Required:** Update Dockerfile to include:
```dockerfile
RUN pip install gradio[mcp]
```

#### model-registry - Healthcheck Failing
**Status:** Service running but healthcheck failing
**Action:** Investigate healthcheck endpoint configuration

#### retrieval-eval - Missing Entrypoint
**Error:** `python: can't open file '/app/server.py'`

**Fix Required:** Check Dockerfile CMD/ENTRYPOINT or add missing server.py

#### comfy-watcher - MinIO Credentials
**Error:** `MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set`

**Fix Required:** Add to env.shared or env.tier-media:
```bash
MINIO_ACCESS_KEY=cataclysm_pmoves  # From env.shared
MINIO_SECRET_KEY=<actual_secret>   # Currently empty in env.shared
```

---

### 1. LLM Provider API Keys 🔴

**Status:** All keys are empty - services will fail to make LLM calls

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
```

**Action Required:**
- Configure at least ONE LLM provider API key
- Recommended: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- For OpenRouter (DeepResearch): Configure `OPENROUTER_API_KEY`

**Provider Dashboards:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- Groq: https://console.groq.com/keys
- OpenRouter: https://openrouter.ai/keys

---

### 2. Supabase Credentials 🔴

**Status:** Using example/development values

```bash
# Current (INSECURE):
PGRST_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
SUPABASE_ANON_KEY=UuQ9zTauaWJ3gzbdsPPhE1QII_ktmprMycJVWhWNY7yiubFyo7ezTCjQZ7NX_e-9
SUPABASE_SERVICE_ROLE_KEY=yrO-em969bWU9n2-kohK2hewi1BkzzAwvXKR3LrY52cBVlKRSZA46onMeTkrotZ8
```

**Action Required:**
1. Generate secure `PGRST_JWT_SECRET`:
   ```bash
   openssl rand -base64 32
   ```

2. Rotate Supabase keys via:
   ```bash
   cd pmoves && make supa-start
   make supa-status
   ```

3. Update `env.shared` with new values from `make supa-status`

---

### 3. CHIT Security Configuration 🔴

**Status:** Geometry encryption and signature verification disabled

```bash
# Current (INSECURE):
CHIT_PASSPHRASE=
CHIT_REQUIRE_SIGNATURE=false
CHIT_DECRYPT_ANCHORS=false
```

**Action Required:**
1. Generate CHIT passphrase:
   ```bash
   openssl rand -base64 32 | tr -d '/+=' | head -c 32
   ```

2. Update `env.shared`:
   ```bash
   CHIT_PASSPHRASE=<generated_passphrase>
   CHIT_REQUIRE_SIGNATURE=true
   CHIT_DECRYPT_ANCHORS=true
   ```

---

### 4. Placeholder Credentials 🔴

**Status:** Google OAuth credentials are placeholders

```bash
CHANNEL_MONITOR_GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com
CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET=GOCSPX-YOUR_CLIENT_SECRET_HERE
```

**Action Required:**
- Configure actual Google OAuth credentials if using YouTube monitoring
- Or disable channel monitor if not needed

---

## Pre-Production Checklist

### Step 1: Configure API Keys
- [ ] Set `OPENAI_API_KEY` or alternative LLM provider
- [ ] Set `OPENROUTER_API_KEY` for DeepResearch
- [ ] Verify embedding provider is accessible

### Step 2: Secure Supabase
- [ ] Generate new `PGRST_JWT_SECRET` (32+ chars)
- [ ] Rotate `SUPABASE_ANON_KEY`
- [ ] Rotate `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Verify `SUPABASE_URL` points to production instance

### Step 3: Enable CHIT Security
- [ ] Generate and set `CHIT_PASSPHRASE`
- [ ] Set `CHIT_REQUIRE_SIGNATURE=true`
- [ ] Set `CHIT_DECRYPT_ANCHORS=true`
- [ ] Verify `CHIT_CODEBOOK_PATH` exists

### Step 4: Service Health Validation
- [ ] Run `cd pmoves && make verify-all`
- [ ] Run `/health:check-all`
- [ ] Verify all critical services are healthy
- [ ] Check Prometheus metrics are collecting

### Step 5: Network Configuration
- [ ] Configure `CLOUDFLARE_TUNNEL_TOKEN` if using remote access
- [ ] Or configure `TAILSCALE_AUTHKEY` if using Tailscale VPN
- [ ] Verify firewall rules allow required ports

---

## Required Ports for Production

| Service | Port | External |
|---------|------|----------|
| Supabase/PostgREST | 3010 | No (internal) |
| TensorZero Gateway | 3030 | No (internal) |
| TensorZero UI | 4000 | Optional |
| Agent Zero | 8080 | No (internal) |
| Agent Zero UI | 8081 | Yes (via proxy) |
| Qdrant | 6333 | No (internal) |
| NATS | 4222 | No (internal) |
| Prometheus | 9090 | Optional |
| Grafana | 3000 | Yes |
| MinIO | 9000 | No (internal) |
| MinIO Console | 9001 | Optional |

---

## Next Steps

1. **Immediate:** Configure LLM provider API keys
2. **Immediate:** Rotate Supabase credentials
3. **Immediate:** Enable CHIT security
4. **Then:** Run service health checks
5. **Then:** Configure network/tunnel access
6. **Finally:** Run smoke tests with `/deploy:smoke-test`

---

**Generated:** 2026-02-07
**Validate with:** `pmoves/scripts/check_env_keys.sh` (create if needed)
