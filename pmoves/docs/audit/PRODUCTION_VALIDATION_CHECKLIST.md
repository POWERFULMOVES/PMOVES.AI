# Production Validation Checklist
**PMOVES.AI Edition - Hardened Branch**
**Created:** 2026-02-07
**Purpose:** Step-by-step production bring-up and validation

---

## Phase 0: Pre-Flight Validation

### 0.1 Environment File Audit

| File | Status | Empty Variables | Placeholder Variables |
|------|--------|-----------------|----------------------|
| env.shared | ⚠️ Audit | ~40 keys | 5+ placeholders |
| env.tier-agent | ✅ OK | 0 | 0 |
| env.tier-supabase | 🟡 Partial | 2 (S3_BUCKET, URI_ALLOW_LIST) | 0 |
| env.tier-api | ❌ TODO | TBD | TBD |
| env.tier-data | ❌ TODO | TBD | TBD |
| env.tier-llm | ❌ TODO | TBD | TBD |
| env.tier-media | ❌ TODO | TBD | TBD |
| env.tier-ui | ❌ TODO | TBD | TBD |
| env.tier-worker | ❌ TODO | TBD | TBD |

### 0.2 Critical Empty Keys (env.shared)

**LLM Provider Keys (ALL EMPTY):**
- `ANTHROPIC_API_KEY=` - Primary LLM provider
- `OPENAI_API_KEY=` - Fallback LLM provider
- `GROQ_API_KEY=` - Fast inference
- `GEMINI_API_KEY=` - Google LLM
- `COHERE_API_KEY=` - Cohere models
- `DEEPSEEK_API_KEY=` - DeepSeek models
- `FIREWORKS_AI_API_KEY=` - Fireworks AI
- `ELEVENLABS_API_KEY=` - TTS provider
- `FLUTE_API_KEY=` - Voice synthesis

**Placeholder Values:**
- `CHANNEL_MONITOR_GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID_HERE.apps.googleusercontent.com`
- `CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET=GOCSPX-YOUR_CLIENT_SECRET_HERE`
- `DISCORD_AVATAR_URL=https://example.com/avatar.png`
- `CLOUDFLARE_API_TOKEN=placeholder_token_until_configured`

**Security:**
- `CHIT_PASSPHRASE=` - Empty (encryption disabled)
- `CHANNEL_MONITOR_SECRET=` - Empty
- `CHANNEL_MONITOR_STATUS_SECRET=` - Empty

### 0.3 Docker Compose Issues Found

| Issue | Count | Services Affected |
|-------|-------|-------------------|
| NATS_URL without credentials | 17 | Multiple services |
| Missing healthchecks | TBD | TBD |
| host.docker.internal references | TBD | channel-monitor |

---

## Phase 1: Core Infrastructure Startup

### 1.1 Start Data Tier (Networks + Data Stores)

```bash
# Start data tier services
docker compose up -d \
  qdrant \
  neo4j \
  meilisearch \
  minio \
  tensorzero-clickhouse
```

**Validation:**
- [ ] All containers running
- [ ] Qdrant responding on port 6333
- [ ] Neo4j responding on port 7474
- [ ] Meilisearch responding on port 7700
- [ ] MinIO responding on port 9000
- [ ] ClickHouse responding on port 8123

### 1.2 Start Supabase Stack

```bash
# Start Supabase services
docker compose up -d \
  supabase-db \
  supabase-postgrest \
  supabase-kong \
  supabase-gotrue \
  supabase-realtime \
  supabase-storage \
  supabase-studio
```

**Validation:**
- [ ] PostgreSQL healthy (port 5432)
- [ ] PostgREST responding (port 3000)
- [ ] Kong gateway responding (port 8000)
- [ ] Studio accessible (port 54323)

### 1.3 Run Database Migrations

```bash
# Run migrations in order
cd supabase/initdb

# Core schema
docker exec -i pmoves-supabase-db-1 psql -U pmoves -d pmoves < 00_pmoves_schema.sql

# Public schema
docker exec -i pmoves-supabase-db-1 psql -U pmoves -d pmoves < 01_public_init.sql

# Geometry Bus
docker exec -i pmoves-supabase-db-1 psql -U pmoves -d pmoves < 09_geometry_rls.sql

# Seeds
docker exec -i pmoves-supabase-db-1 psql -U pmoves -d pmoves < 10_archon_prompts_seed.sql
```

**Validation:**
- [ ] pmoves_core schema exists
- [ ] pmoves_core.agent table exists
- [ ] pmoves_core.session table exists
- [ ] pmoves_core.message table exists
- [ ] pmoves_core.memory table exists
- [ ] Anchors table exists with RLS
- [ ] Archon prompts seeded

---

## Phase 2: Message Bus and Gateways

### 2.1 Start NATS

```bash
docker compose up -d nats
```

**Validation:**
- [ ] NATS healthy (healthcheck passes)
- [ ] NATS monitoring port 8222 accessible
- [ ] JetStream enabled

### 2.2 Start TensorZero Gateway

```bash
docker compose up -d tensorzero-gateway tensorzero-ui
```

**Validation:**
- [ ] Gateway responding on port 3030
- [ ] UI accessible on port 4000
- [ ] ClickHouse connection working

---

## Phase 3: Agent and API Tier

### 3.1 Start Agent Services

```bash
docker compose up -d \
  agent-zero \
  archon \
  mesh-agent \
  deepresearch \
  supaserch
```

**Validation:**
- [ ] Agent Zero healthy (port 8080)
- [ ] Archon healthy (port 8091)
- [ ] Archon UI accessible (port 3737)
- [ ] Mesh agent announcing on NATS
- [ ] DeepResearch ready
- [ ] SupaSerch ready

### 3.2 Start Hi-RAG Gateway

```bash
docker compose up -d hi-rag-gateway-v2
```

**GPU version:**
```bash
docker compose up -d hi-rag-gateway-v2-gpu
```

**Validation:**
- [ ] Hi-RAG responding on port 8086
- [ ] Vector search working (Qdrant)
- [ ] Graph search working (Neo4j)
- [ ] Full-text search working (Meilisearch)

---

## Phase 4: Worker and Media Services

### 4.1 Start Workers

```bash
docker compose up -d \
  extract-worker \
  langextract \
  notebook-sync
```

**Validation:**
- [ ] Extract worker healthy
- [ ] LangExtract processing
- [ ] Notebook sync polling

### 4.2 Start Media Services (Optional)

```bash
docker compose up -d \
  ffmpeg-whisper \
  media-video \
  media-audio \
  pmoves-yt
```

**Validation:**
- [ ] Whisper transcribing
- [ ] Video analyzer processing
- [ ] YouTube ingestion ready

---

## Phase 5: Monitoring Stack

### 5.1 Start Monitoring

```bash
docker compose up -d \
  prometheus \
  grafana \
  loki \
  promtail \
  cadvisor
```

**Validation:**
- [ ] Prometheus collecting metrics (port 9090)
- [ ] Grafana accessible (port 3000)
- [ ] Loki aggregating logs (port 3100)
- [ ] All services being scraped

---

## Phase 6: Health Check Validation

### 6.1 Run Full Health Check

```bash
# Check all services
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check specific endpoints
curl -s http://localhost:8080/healthz | jq .  # Agent Zero
curl -s http://localhost:8091/healthz | jq .  # Archon
curl -s http://localhost:8086/hirag/health | jq .  # Hi-RAG
```

### 6.2 Expected Service Count

| Tier | Expected Services |
|------|-------------------|
| Data | 5 (qdrant, neo4j, meilisearch, minio, clickhouse) |
| Supabase | 7 |
| Bus | 1 (nats) |
| Gateway | 2 (tensorzero, tensorzero-ui) |
| Agent | 5 (agent-zero, archon, mesh-agent, deepresearch, supaserch) |
| RAG | 1-2 (hi-rag v2 + optional gpu) |
| Worker | 3 (extract, langextract, notebook-sync) |
| Monitoring | 5 (prometheus, grafana, loki, promtail, cadvisor) |
| **Total** | **~34 core services** |

---

## Known Issues Requiring Fix

### Issue 1: NATS Authorization (FIXED for archon, 16 remaining)
**Services with incorrect NATS_URL default:**
- Lines 725, 876, 927, 1266, 1294, 1331, 1365, 1386, 1403, 1420, 1556, 1601, 1654, 1676, 1779, 1858

**Fix:** Remove `NATS_URL=${NATS_URL:-nats://nats:4222}` from environment sections
The env.tier-agent already provides: `NATS_URL=nats://nats:pmoves@nats:4222`

### Issue 2: channel-monitor PostgreSQL URL
**Current:** `postgresql://postgres:postgres@host.docker.internal:65432/postgres`
**Should be:** `postgresql://pmoves:bZ9VZ0UoKcTD4aTOJASMrm2vSVd94Ger@supabase-db:5432/pmoves`

### Issue 3: ultimate-tts-studio Missing Dependency
**Error:** `gradio[mcp]` not installed
**Fix:** Add to Dockerfile

### Issue 4: comfy-watcher MinIO Credentials
**Error:** `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` not set
**Fix:** Add to env.tier-media

### Issue 5: Missing LLM API Keys
**Impact:** All agent services will fail LLM calls
**Required:** At least one of ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY

---

## Production Security Requirements

### Before Going Live:

- [ ] Generate and set `CHIT_PASSPHRASE` (32+ chars)
- [ ] Set `CHIT_REQUIRE_SIGNATURE=true`
- [ ] Set `CHIT_DECRYPT_ANCHORS=true`
- [ ] Rotate `SUPABASE_JWT_SECRET` (currently using default)
- [ ] Rotate `SUPABASE_ANON_KEY`
- [ ] Rotate `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Configure `PGRST_JWT_SECRET` (currently `super-secret-jwt-token...`)
- [ ] Set at least one LLM provider API key
- [ ] Configure Google OAuth or disable channel-monitor
- [ ] Set `CLOUDFLARE_TUNNEL_TOKEN` for remote access OR configure Tailscale
- [ ] Set `MINIO_SECRET_KEY` (currently empty)

---

## Bring-Up Commands (Full Stack)

```bash
# Full production bring-up
docker compose up -d \
  $(docker compose config --services)

# Or by profile
docker compose --profile data --profile supabase --profile agents \
              --profile workers --profile monitoring up -d
```

---

## Rollback Procedure

```bash
# Stop all services
docker compose down

# Remove volumes (WARNING: data loss)
docker compose down -v

# Restart from clean state
docker compose up -d
```

---

**Next Step:** Begin Phase 1 after environment variables are configured.
