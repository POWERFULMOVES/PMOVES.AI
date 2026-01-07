# PMOVES.AI Hardened Makefile Refactor & Alignment Plan

**Date:** 2026-01-06
**Branch:** `PMOVES.AI-Edition-Hardened`
**Worktree:** `/home/pmoves/tac-merge-ops`
**Status:** ⏸️ Planning Phase

---

## Executive Summary

The current Makefile (3000+ lines) has accumulated technical debt from multiple development streams:
1. Duplicate target definitions causing "overriding recipe" warnings
2. References to non-existent docker-compose files
3. Targets that don't align with hardened branch requirements
4. Missing documentation for hardened-specific workflows

This plan documents the issues, provides hardened requirements, and outlines a refactor strategy.

---

## Part 1: Critical Issues Identified

### 1.1 Duplicate Target Definitions

| Target | Lines | Issue | Resolution |
|--------|-------|-------|------------|
| `up-workers` | 148, 706 | Duplicate definitions | Keep line 706 (hardened version) |
| `up-tensorzero` | 162, 738 | Duplicate definitions | Keep line 738 (hardened version) |
| `down-tensorzero` | 243, 741 | Duplicate definitions | Keep line 741 (hardened version) |
| `up-agents` | 154, 1078 | Duplicate definitions | Keep line 1078 (enhanced with explicit services) |

### 1.2 Missing Docker Compose Files

| File | Referenced By | Status | Action |
|------|---------------|--------|--------|
| `docker-compose.voice.yml` | `up-data-tier` target | ❌ Missing | Remove reference or create file |
| `docker-compose.n8n.postgres.yml` | N8N targets | ❌ Missing | Remove reference (use `docker-compose.n8n.yml`) |
| `pmoves/docker-compose.monitoring.yml` | Some targets | ❌ Wrong path | Use `monitoring/docker-compose.monitoring.yml` |
| `docker-compose.jellyfin-ai.yml` | Jellyfin targets | ❌ Missing | Use submodule or external compose |
| `docker-compose.supabase.yml` | Supabase targets | ❌ Missing | Services are in main docker-compose.yml |

### 1.3 Makefile Target Issues

The `up-data-tier` target fails because:
```makefile
up-data-tier: ## Start data tier (Qdrant, Neo4j, Meilisearch, MinIO)
    @echo "💾 Starting data tier..."
    @$(DC) -f docker-compose.voice.yml config > /dev/null 2>&1 || true  # ❌ File doesn't exist!
    @$(DC) up -d qdrant neo4j meilisearch minio
```

---

## Part 2: Hardened Branch Requirements

### 2.1 6-Tier Environment Architecture

The hardened branch implements tier-based environment segmentation:

| Tier File | Purpose | Services | Security Boundaries |
|-----------|---------|----------|-------------------|
| `env.tier-data` | Infrastructure | Postgres, Qdrant, Neo4j, Meilisearch, MinIO, NATS | DB passwords, master keys, root credentials only |
| `env.tier-api` | Data Access APIs | PostgREST, Presign, Hi-RAG Gateway | Neo4j/Meili/Qdrant credentials, NO external API keys |
| `env.tier-llm` | LLM Gateway | TensorZero Gateway, TensorZero UI | **ALL** external LLM provider API keys |
| `env.tier-worker` | Background Workers | Extract, LangExtract, PDF-ingest, Notebook-sync | Internal URLs only |
| `env.tier-media` | Media Processing | PMOVES.YT, FFmpeg-Whisper, Media-Video/Audio | DATABASE_URL, MinIO, NATS URLs |
| `env.tier-agent` | Agent Orchestration | Agent Zero, Archon, SupaSerch, DeepResearch | Supabase/Hi-RAG URLs, NO external API keys |

**Critical Security Rule:** External API keys (OpenAI, Anthropic, etc.) MUST only be in `env.tier-llm`. All LLM calls go through TensorZero Gateway.

### 2.2 5-Tier Network Architecture

| Network | Name | Subnet | Purpose | Internet Access |
|---------|------|--------|---------|-----------------|
| API Tier | `pmoves_api` | 172.30.1.0/24 | Public-facing services | ✅ Yes |
| App Tier | `pmoves_app` | 172.30.2.0/24 | Application services | ❌ No |
| Bus Tier | `pmoves_bus` | 172.30.3.0/24 | NATS message bus | ❌ No |
| Data Tier | `pmoves_data` | 172.30.4.0/24 | Data stores | ❌ No |
| Monitoring | `pmoves_monitoring` | 172.30.5.0/24 | Observability | ✅ Yes (Grafana) |

### 2.3 Security Hardening Features

1. **Non-Root Execution:** All services run as user `65532:65532` or `pmoves:pmoves`
2. **Read-Only Root:** `read_only: true` with tmpfs for `/tmp` and cache
3. **Capability Dropping:** `cap_drop: ["ALL"]` - remove all Linux capabilities
4. **Privilege Prevention:** `no-new-privileges:true`
5. **CHIT Secret Management:** Multi-target secret output (tier files, GitHub, Docker)

### 2.4 Hardened Docker Compose Files

| File | Purpose | Status |
|------|---------|--------|
| `docker-compose.yml` | Main compose with tier anchors | ✅ Core |
| `docker-compose.hardened.yml` | Security hardening overrides | ✅ Core |
| `docker-compose.agents.images.yml` | Agent services (published images) | ✅ Core |
| `docker-compose.agents.integrations.yml` | Agent services (submodule builds) | ✅ Core |
| `monitoring/docker-compose.monitoring.yml` | Prometheus, Grafana, Loki | ✅ Core |
| `docker-compose.n8n.yml` | N8N workflow automation | ✅ Integration |
| `docker-compose.external.yml` | Wger, Firefly, Open Notebook | ✅ Integration |

---

## Part 3: Existing Docker Compose Files Inventory

### 3.1 All Compose Files

| File | Status | Purpose | Services |
|------|--------|---------|----------|
| `docker-compose.yml` | ✅ EXISTS | Main compose file | All core services |
| `docker-compose.hardened.yml` | ✅ EXISTS | Security overrides | 20+ services |
| `docker-compose.agents.images.yml` | ✅ EXISTS | Agent images | agent-zero, archon, deepresearch, supaserch |
| `docker-compose.agents.integrations.yml` | ✅ EXISTS | Agent submodules | agent-zero, archon |
| `docker-compose.external.yml` | ✅ EXISTS | External integrations | wger, firefly, open-notebook, jellyfin-ext |
| `docker-compose.gpu-image.yml` | ✅ EXISTS | GPU services | hi-rag-gateway-v2-gpu |
| `docker-compose.n8n.yml` | ✅ EXISTS | N8N automation | n8n, n8n-runners |
| `docker-compose.open-notebook.yml` | ✅ EXISTS | Standalone Notebook | open-notebook |
| `docker-compose.vps.override.yml` | ✅ EXISTS | VPS deployment | CPU-only override |
| `monitoring/docker-compose.monitoring.yml` | ✅ EXISTS | Monitoring stack | prometheus, grafana, loki, promtail |
| `compose/docker-compose.firefly.yml` | ✅ EXISTS | Firefly III | firefly-db, firefly |
| `compose/docker-compose.wger.yml` | ✅ EXISTS | Wger health | wger-db, wger |

### 3.2 Missing Compose Files (Referenced but Don't Exist)

- ❌ `docker-compose.voice.yml` - Referenced by `up-data-tier`
- ❌ `docker-compose.n8n.postgres.yml` - N8N with PostgreSQL (not needed, using SQLite)
- ❌ `docker-compose.supabase.yml` - Supabase is in main compose
- ❌ `docker-compose.jellyfin-ai.yml` - Use submodule or external

---

## Part 4: Refactor Strategy

### 4.1 Immediate Fixes (Priority: CRITICAL)

1. **Fix `up-data-tier` target:**
   ```makefile
   up-data-tier: ## Start data tier (Qdrant, Neo4j, Meilisearch, MinIO)
       @echo "💾 Starting data tier..."
       @$(DC) up -d qdrant neo4j meilisearch minio
       @echo "✅ Data tier ready"
   ```

2. **Remove duplicate target definitions:**
   - Remove early definitions of `up-workers`, `up-tensorzero`, `down-tensorzero`, `up-agents`
   - Keep later (hardened) versions

3. **Fix `VOICE_STACK_FILE` references:**
   - Remove `$(VOICE_STACK_FILE)` from targets that reference non-existent file
   - Or conditional check: `test -f docker-compose.voice.yml && $(DC) -f docker-compose.voice.yml || true`

### 4.2 Target Consolidation (Priority: HIGH)

**Current Multiple Variants:**
- `up-agents` (2 definitions)
- `up-agents-hardened`
- `up-agents-published`
- `up-agents-ui`
- `up-agents-integrations`

**Proposed Consolidation:**
```makefile
# Base agent services
.PHONY: up-agents
up-agents: ## Start core agent services (NATS, Agent Zero, Archon, Mesh Agent, DeepResearch)
    @echo "🤖 Starting agents..."
    @$(DC) up -d nats agent-zero archon mesh-agent deepresearch publisher-discord

# Hardened variant with security options
.PHONY: up-agents-hardened
up-agents-hardened: ## Start hardened agent services (with security hardening)
    @echo "🔒 Starting hardened agents..."
    @$(DC) -f docker-compose.yml -f docker-compose.hardened.yml up -d agent-zero archon deepresearch

# UI variant
.PHONY: up-agents-ui
up-agents-ui: up-agents ## Start agents + their UIs
    @$(DC) up -d archon-ui agent-zero-ui

# Published images variant
.PHONY: up-agents-published
up-agents-published: ## Start agents using published images
    @$(DC) -f docker-compose.agents.images.yml up -d agent-zero archon deepresearch supaserch

# Integrations variant
.PHONY: up-agents-integrations
up-agents-integrations: ## Start agents from integration workspace
    @$(DC) -f docker-compose.agents.integrations.yml up -d agent-zero archon
```

### 4.3 Profile-Based Organization (Priority: MEDIUM)

Align Makefile targets with Docker Compose profiles:

| Makefile Target | Compose Profiles | Services |
|----------------|------------------|----------|
| `up-data-tier` | `data` | qdrant, neo4j, meilisearch, minio |
| `up-bus` | (no profile, nats always starts) | nats |
| `up-workers` | `workers` | extract-worker, langextract, pdf-ingest, notebook-sync |
| `up-agents` | `agents` | agent-zero, archon, mesh-agent, deepresearch, supaserch |
| `up-tensorzero` | `tensorzero` | tensorzero-gateway, tensorzero-clickhouse |
| `up-media` | `media, yt` | ffmpeg-whisper, media-video, media-audio, pmoves-yt |
| `up-gpu` | `gpu` | hi-rag-gateway-v2-gpu |

### 4.4 New Standardized Targets

```makefile
# === Core Infrastructure ===
.PHONY: up-infra
up-infra: up-obs up-data-tier up-bus ## Start all infrastructure (monitoring + data + bus)

# === Tier-by-Tier Bringup ===
.PHONY: up-api-tier
up-api-tier: ## Start API tier (PostgREST, Hi-RAG Gateway, Presign)
    @$(DC) up -d postgrest hi-rag-gateway-v2 presign render-webhook

.PHONY: up-llm-tier
up-llm-tier: ## Start LLM tier (TensorZero Gateway + ClickHouse)
    @$(DC) up -d tensorzero-gateway tensorzero-clickhouse

.PHONY: up-media-tier
up-media-tier: ## Start media tier (FFmpeg-Whisper, Media analyzers, PMOVES.YT)
    @$(DC) --profile media --profile yt up -d

# === Hardened-Specific ===
.PHONY: up-hardened
up-hardened: ## Start all hardened services (with security hardening)
    @$(DC) -f docker-compose.yml -f docker-compose.hardened.yml \
        --profile data --profile workers --profile agents --profile monitoring up -d

# === Verification ===
.PHONY: verify-tiers
verify-tiers: ## Verify all tier env files are properly configured
    @python3 tools/verify_tier_config.py
```

---

## Part 5: Implementation Phases

### Phase 1: Critical Fixes (Immediate - Before Bringup Completes)

1. Fix `up-data-tier` target (remove voice.yml reference)
2. Fix any other broken targets blocking current bringup
3. Document current working commands in bringup plan

### Phase 2: Duplicate Removal (After Bringup Stabilizes)

1. Remove duplicate target definitions
2. Consolidate `up-agents` variants
3. Clean up legacy targets (`up-bots`, `up-legacy-both`)

### Phase 3: Documentation & Standards (Ongoing)

1. Create this document in repo (✅ Done)
2. Document hardened requirements locally
3. Create tier-specific usage guides
4. Add target reference documentation

### Phase 4: Refactor Execution (Future Sprint)

1. Split monolithic Makefile into modules (if needed)
2. Implement profile-based organization
3. Add verification targets
4. Update CI/CD to use new targets

---

## Part 6: Hardened Requirements Checklist

### Security Requirements

- [x] Non-root containers (USER pmoves or 65532)
- [x] Read-only root filesystems
- [x] Capability dropping (cap_drop: ["ALL"])
- [x] No-new-privileges flag
- [x] Tier-based environment files
- [x] Network segmentation (5-tier)
- [x] CHIT secret management
- [ ] INVIDIOUS keys added to secrets_manifest_v2.yaml
- [ ] All external API keys isolated to env.tier-llm

### Infrastructure Requirements

- [x] PostgreSQL (pmoves-supabase-db)
- [x] Qdrant (vector DB)
- [x] Neo4j (graph DB)
- [x] Meilisearch (full-text search)
- [x] MinIO (S3 storage)
- [x] NATS (message bus)
- [x] TensorZero (LLM gateway)
- [ ] All services using tier env files
- [ ] All services on correct networks

### Monitoring Requirements

- [x] Prometheus (metrics collection)
- [x] Grafana (dashboards)
- [x] Loki (log aggregation)
- [x] Promtail (log shipping)
- [x] cAdvisor (container metrics)
- [ ] All services exporting metrics
- [ ] All services logging to Loki

---

## Part 7: Quick Reference - Working Commands

### For Current Bringup (Use These)

```bash
cd /home/pmoves/tac-merge-ops/pmoves

# Observability (working)
make up-obs

# Supabase (working)
make up-supabase

# Data tier (FIXED - use docker compose directly)
docker compose up -d qdrant neo4j meilisearch minio

# NATS bus (working)
make up-bus

# TensorZero (working)
make up-tensorzero

# Workers (FIXED - use profile)
docker compose --profile workers up -d

# Agents (FIXED - use explicit services)
docker compose up -d nats agent-zero archon deepresearch
```

### Health Check Commands

```bash
# Data tier
curl -s http://localhost:6333/healthz  # Qdrant
curl -s http://localhost:7474          # Neo4j
curl -s http://localhost:7700/health   # Meilisearch
curl -s http://localhost:9000/minio/health/live  # MinIO

# Bus
nats server info  # NATS

# LLM
curl -s http://localhost:3030/v1/healthz  # TensorZero
curl -s http://localhost:8123/ping         # ClickHouse

# Agents
curl -s http://localhost:8080/healthz  # Agent Zero
curl -s http://localhost:8091/healthz  # Archon
```

---

## Part 8: Files to Create/Modify

### Files to Create

1. `pmoves/docs/HARDENED_REQUIREMENTS.md` - Comprehensive hardened branch docs
2. `pmoves/tools/verify_tier_config.py` - Tier configuration verification
3. `pmoves/docs/MAKEFILE_TARGETS.md` - Makefile target reference

### Files to Modify

1. `pmoves/Makefile` - Remove duplicates, fix broken targets
2. `pmoves/chit/secrets_manifest_v2.yaml` - Add INVIDIOUS key entries
3. `pmoves/docker-compose.yml` - Ensure all services use tier anchors

### Files to Remove (Conditional)

1. Duplicate compose files (consolidate firefly, wger)
2. Legacy target definitions (after confirming no usage)

---

## Part 9: Success Metrics

### Before Refactor
- Makefile: 3000+ lines
- Duplicate targets: 4+
- Broken targets: 2+ (up-data-tier, others)
- Missing documentation: Hardened requirements

### After Refactor (Goals)
- Makefile: ~2000 lines (consolidated)
- Duplicate targets: 0
- Broken targets: 0
- Documentation: Complete

---

## Appendix A: Agent Analysis References

This document was created based on analysis from three Explore agents:
- **Agent a8185ac**: Makefile structure analysis
- **Agent ae6d3fb**: Hardened requirements documentation
- **Agent a9d1b2b**: Docker Compose file structure mapping

Full agent reports available in conversation history.
