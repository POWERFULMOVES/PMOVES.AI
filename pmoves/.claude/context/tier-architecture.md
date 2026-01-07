# PMOVES.AI Tier Architecture

**Created**: 2025-12-29
**Purpose**: Document the 6-tier environment security model and 5-tier network segmentation architecture

---

## Overview

PMOVES.AI implements **defense-in-depth** through two complementary tier architectures:

1. **Environment Tiers (6)** - Secrets/privilege segmentation via `env.tier-*` files
2. **Network Tiers (5)** - Container communication segmentation via Docker networks

These serve different purposes:
- **Env tiers** control what secrets/credentials each service receives
- **Network tiers** control which services can communicate with each other

---

## 6-Tier Environment Architecture

The environment tier model implements **principle of least privilege** - each tier only receives the secrets it needs.

### Tier Definitions

| Tier File | Purpose | Services | Secrets Included |
|-----------|---------|----------|------------------|
| **env.tier-data** | Infrastructure | Postgres, Qdrant, Neo4j, Meilisearch, MinIO, NATS | Database passwords, master keys, root credentials |
| **env.tier-api** | Data Access APIs | PostgREST, Presign, Hi-RAG Gateway, GPU Orchestrator | Neo4j, Meilisearch, Qdrant credentials (NO external API keys) |
| **env.tier-worker** | Background Workers | Extract Worker, LangExtract, PDF-ingest, Notebook-sync | TensorZero, Qdrant, Meilisearch, MinIO, Supabase URLs |
| **env.tier-media** | Media Processing | PMOVES.YT, FFmpeg-Whisper, Media-Video/Audio, Channel Monitor | DATABASE_URL, MinIO, NATS URLs |
| **env.tier-agent** | Agent Orchestration | Agent Zero, Archon, SupaSerch, DeepResearch | Supabase, Hi-RAG, TensorZero URLs (NO external API keys) |
| **env.tier-llm** | LLM Gateway | TensorZero Gateway, TensorZero UI | **ALL** external LLM provider API keys (OpenAI, Anthropic, etc.) |

### Critical Security Rules

1. **Only tier-llm has external LLM API keys** - No other service calls OpenAI/Anthropic/etc. directly
2. **All LLM calls go through TensorZero Gateway** - Services use `TENSORZERO_URL=http://tensorzero-gateway:3000`
3. **Data tier credentials isolated** - Only api/worker tiers get direct data store access
4. **External URLs standardized** - Supabase via `supabase_kong_PMOVES.AI:8000`

### Env File Structure

```bash
# Each tier env file sources from env.shared
# env.shared is the single source of truth

env.shared                    # All env vars (for reference, not used directly)
├── env.tier-data            # Infrastructure credentials
├── env.tier-api             # Data access APIs
├── env.tier-worker          # Background workers
├── env.tier-media           # Media processing
├── env.tier-agent           # Agent orchestration
└── env.tier-llm             # LLM gateway (ALL external API keys)
```

### Usage in docker-compose.yml

```yaml
# YAML anchors for tier env files
x-env-tier-data: &env-tier-data
  env_file:
    - path: env.tier-data
      required: false

x-env-tier-api: &env-tier-api
  env_file:
    - path: env.tier-api
      required: false

# Services reference by anchor
postgres:
  <<: *env-tier-data
  # ...

postgrest:
  <<: *env-tier-api
  # ...

tensorzero-gateway:
  <<: *env-tier-llm
  # ...
```

---

## 5-Tier Network Architecture

The network tier model implements **container communication segmentation** via Docker bridge networks.

### Network Definitions

| Network | Name | Type | Subnet | Purpose |
|---------|------|------|--------|---------|
| **api_tier** | `pmoves_api` | bridge | 172.30.1.0/24 | Public-facing services (PostgREST, Gateway Agent) |
| **app_tier** | `pmoves_app` | bridge (internal) | 172.30.2.0/24 | Application services (UIs, dashboards) |
| **bus_tier** | `pmoves_bus` | bridge (internal) | 172.30.3.0/24 | Message bus (NATS) and subscribers |
| **data_tier** | `pmoves_data` | bridge (internal) | 172.30.4.0/24 | Data stores (Postgres, Qdrant, Neo4j, Meilisearch) |
| **monitoring_tier** | `pmoves_monitoring` | bridge | 172.30.5.0/24 | Observability (Prometheus, Grafana, Loki) |

### External Networks

| Network | Name | Purpose |
|---------|------|---------|
| **supabase_net** | `supabase_network_PMOVES.AI` | Bridge to Supabase CLI stack for direct container-to-container communication |
| **cataclysm** | `cataclysim-net` | Legacy external network (jellyfin-bridge only) |

### Network Security Rules

1. **Internal networks cannot reach internet** - `app_tier`, `bus_tier`, `data_tier` marked `internal: true`
2. **Services span multiple networks** - A service like Agent Zero connects to `api_tier` + `bus_tier` + `monitoring_tier`
3. **Data stores isolated to data_tier** - Only api/worker services can directly connect
4. **Monitoring via dedicated tier** - All services expose `/metrics` to `monitoring_tier`

### Service Network Placement

```yaml
# Example: Multi-network service
agent-zero:
  networks:
    - api_tier      # For HTTP API access
    - bus_tier      # For NATS message bus
    - monitoring_tier  # For /metrics

# Example: Data store (single network)
postgres:
  networks:
    - api_tier      # For PostgREST access
    - data_tier     # For internal data access
    - monitoring_tier  # For exporter
```

---

## Bring-Up Order

Services must be started in dependency order:

### Phase 1: Data Tier
```bash
docker compose --profile data up -d
# Services: postgres, qdrant, neo4j, meilisearch, minio, nats
```

### Phase 2: API Tier
```bash
docker compose --profile orchestration up -d
# Services: postgrest, hi-rag-gateway-v2, tensorzero-gateway
```

### Phase 3: Worker Tier
```bash
docker compose --profile workers up -d
# Services: extract-worker, langextract, pdf-ingest, notebook-sync
```

### Phase 4: Media Tier
```bash
docker compose --profile yt up -d
# Services: pmoves-yt, ffmpeg-whisper, media-video, media-audio, channel-monitor
```

### Phase 5: Agent Tier
```bash
docker compose --profile agents up -d
# Services: agent-zero, archon, supaserch, deepresearch
```

### Phase 6: Monitoring
```bash
docker compose --profile monitoring up -d
# Services: prometheus, grafana, loki, promtail, cadvisor
```

### All Tiers (Combined)
```bash
docker compose --profile data --profile orchestration --profile workers \
  --profile agents --profile monitoring --profile yt up -d
```

---

## Troubleshooting

### Service Cannot Connect to Database

**Symptom**: `Connection refused` to Postgres/Qdrant/Neo4j

**Check**:
```bash
# Is service on correct network?
docker inspect <service> | grep Networks

# Is data store running?
docker ps | grep -E "postgres|qdrant|neo4j"

# Is tier env file populated?
cat env.tier-<tier> | grep -E "URL|PASSWORD"
```

**Fix**: Ensure service has `<<: *env-tier-<tier>` and networks include `data_tier`

### Service Cannot Resolve Supabase

**Symptom**: `Could not resolve host: supabase_kong_PMOVES.AI`

**Check**:
```bash
# Is service on supabase_net network?
docker inspect <service> | grep -A 10 Networks

# Is supabase stack running?
docker ps | grep supabase
```

**Fix**: Ensure service has `supabase_net` in its `networks:` list

### LLM API Keys Not Working

**Symptom**: `OPENAI_API_KEY not found` in non-TensorZero service

**Check**:
```bash
# Does service have tier-llm env?
grep -A 5 "<service>:" docker-compose.yml | grep "env-tier"
```

**Fix**: Service should call TensorZero Gateway, not OpenAI directly. Remove LLM API keys from service env.

---

## Makefile Commands

```bash
# Start all tiers
make up

# Start specific tier
make up-data      # Data tier
make up-api       # API tier
make up-workers   # Worker tier
make up-agents    # Agent tier
make up-media     # Media tier

# Stop all tiers
make down

# Verify health (all tiers)
make verify-all
```

---

## Related Documentation

- `services-catalog.md` - Complete service listing with ports and health endpoints
- `nats-subjects.md` - NATS message bus subjects
- `tensorzero.md` - TensorZero Gateway integration
- `testing-strategy.md` - Testing workflow per tier

---

## Changes Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-29 | Initial documentation of 6-tier env + 5-tier network architecture | Claude Code |
