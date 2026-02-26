# PMOVES.AI Service Hardening Inventory
**Date**: 2026-02-26 (v2.0, updated from 2025-12-06 Phase 1 inventory)
**Purpose**: Track security hardening posture across all 66 compose services and 47 PMOVES-native Dockerfiles

## Phase 1 -- COMPLETE (2025-12-06)

| Phase | Scope | Coverage | Status |
|-------|-------|----------|--------|
| 1.1 Non-Root Users | 29 PMOVES services | 29/29 (100%) | COMPLETE |
| 1.2 Read-Only Filesystems | 30 services | 30/30 (100%) | COMPLETE |
| 1.3 Kubernetes SecurityContext | Template | 1/1 (100%) | COMPLETE |

## Current Compose Services (66 total)

### Supabase Stack (7 services) -- Third-Party Managed

| Service | Port | Hardening Anchor | USER | read_only | cap_drop |
|---------|------|------------------|------|-----------|----------|
| supabase-db | 5432 | tier-data-hardened | postgres | No (stateful) | ALL+caps |
| supabase-gotrue | 9999 | tier-supabase-hardened-ro | gotrue | Yes | ALL |
| supabase-postgrest | 3010 | tier-supabase-hardened-ro | postgrest | Yes | ALL |
| supabase-kong | 8000 | tier-supabase-hardened | kong | No (stateful) | ALL+caps |
| supabase-realtime | 4000 | tier-supabase-hardened-ro | supabase | Yes | ALL |
| supabase-storage | 5000 | tier-supabase-hardened | supabase | No (stateful) | ALL+caps |
| supabase-studio | 54323 | tier-ui-hardened | node | Yes | ALL |

### Data Stores (4 services) -- Third-Party Managed

| Service | Port | Notes |
|---------|------|-------|
| qdrant | 6333 | Third-party, own hardening |
| meilisearch | 7700 | Third-party, own hardening |
| neo4j | 7474/7687 | Third-party, own hardening |
| minio | 9000/9001 | Third-party, own hardening |

### NATS Messaging (4 services)

| Service | Port | Hardening | Notes |
|---------|------|-----------|-------|
| nats | 4222/8222 | tier-data-hardened | JetStream enabled, auth block |
| nats-init | - | cap_drop:ALL, read_only, no-new-priv | Init sidecar, hardened 2026-02-26 |
| nats-echo-req | - | hardened-ro | NATS echo utility |
| nats-echo-res | - | hardened-ro | NATS echo utility |

### Agent Services (11 services) -- PMOVES-Native

| Service | Port | Hardening Anchor | Dockerfile HEALTHCHECK | Notes |
|---------|------|------------------|----------------------|-------|
| agent-zero | 8080/8081 | tier-agent-hardened | No | MCP orchestrator |
| archon | 8091/3737 | tier-agent-hardened | No | Supabase-driven agents |
| cipher-api | 8096 | tier-agent-hardened-ro | No | Knowledge-graph memory |
| mesh-agent | - | tier-agent-hardened-ro | No | Node announcer |
| botz-gateway | 8110 | tier-agent-hardened | Yes | Skills marketplace |
| a2ui-nats-bridge | 9224 | tier-agent-hardened-ro | Yes | NATS bridge |
| deepresearch | - | tier-agent-hardened-ro | No | Research planner |
| supaserch | 8099 | tier-agent-hardened-ro | No | Research orchestrator |
| publisher-discord | 8094 | tier-agent-hardened-ro | No | Discord notifications |
| gateway-agent | 8100 | tier-agent-hardened | Yes | MCP tool aggregator |
| github-runner-ctl | 8104 | tier-agent-hardened-rw | Yes | Runner management |

### Hi-RAG Services (4 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| hi-rag-gateway | 8089 | tier-api-hardened | Legacy v1 CPU |
| hi-rag-gateway-v2 | 8086 | tier-api-hardened | Preferred v2 CPU |
| hi-rag-gateway-gpu | 8090 | tier-api-hardened-gpu | v1 GPU |
| hi-rag-gateway-v2-gpu | 8087 | tier-api-hardened-gpu | v2 GPU |

### Workers (6 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| extract-worker | 8083 | tier-worker-hardened | Text embedding/indexing |
| pdf-ingest | 8092 | tier-worker-hardened | Document processing |
| langextract | 8084 | tier-worker-hardened | NLP preprocessing |
| notebook-sync | 8095 | tier-worker-hardened | SurrealDB sync |
| session-context-worker | 8102 | tier-worker-hardened | Session context |
| comfy-watcher | - | tier-worker-hardened | ComfyUI watcher |

### Media Pipeline (6 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| ffmpeg-whisper | 8078 | tier-media-hardened | GPU transcription |
| media-video | 8079 | tier-media-hardened | YOLOv8 analysis |
| media-audio | 8082 | tier-media-hardened | Emotion detection |
| pmoves-yt | 8077 | tier-media-hardened | YouTube ingestion |
| bgutil-pot-provider | - | tier-worker-hardened | Background utility |
| channel-monitor | 8097 | tier-worker-hardened | Content watcher |

### LLM/AI Infrastructure (7 services) -- Mixed

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| tensorzero-gateway | 3030 | Third-party (Rust) | Bearer auth enforced |
| tensorzero-clickhouse | 8123 | Third-party | Metrics storage |
| tensorzero-ui | 4000 | Third-party | Dashboard |
| pmoves-ollama | 11434 | Third-party | Local LLM |
| gpu-orchestrator | - | tier-worker-hardened | Yes (HEALTHCHECK) |
| evo-controller | 8113 | tier-agent-hardened | Evolution controller |
| llama-throughput-lab | - | tier-worker-hardened | Yes (HEALTHCHECK) |

### Voice/TTS (4 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| ultimate-tts-studio | 7861 | tier-media-hardened | Multi-engine TTS (GPU) |
| flute-gateway | 8055/8056 | tier-api-hardened | Yes (HEALTHCHECK) |
| tokenism-simulator | 8103 | tier-agent-hardened | Yes (HEALTHCHECK) |
| tokenism-ui | 8106 | tier-ui-hardened | CHIT interface |

### API/Utility (4 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| retrieval-eval | 8091 | tier-api-hardened | RAG evaluation |
| presign | 8088 | tier-api-hardened | MinIO URL presigner |
| render-webhook | 8085 | tier-api-hardened | ComfyUI callback |
| model-registry | - | tier-api-hardened | Yes (HEALTHCHECK) |

### UI (2 services)

| Service | Port | Hardening Anchor | Notes |
|---------|------|------------------|-------|
| pmoves-ui | 3001 | tier-ui-hardened | Next.js frontend |
| jellyfin-bridge | 8093 | tier-api-hardened | Jellyfin webhook |

### Invidious Stack (6 services) -- Third-Party Managed

| Service | Port | Notes |
|---------|------|-------|
| invidious-db | 5432 | PostgreSQL for Invidious |
| invidious-companion | - | Video proxy |
| invidious | 3000 | Video frontend |
| grayjay-plugin-host | - | Plugin server |
| grayjay-server | - | Grayjay backend |
| invidious-companion-proxy | - | Nginx proxy |

### Infrastructure (1 service)

| Service | Notes |
|---------|-------|
| cloudflared | Cloudflare tunnel |

---

## Hardening Patterns

### Standard Python Services
```dockerfile
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app
USER pmoves:pmoves
```

### GPU Services
```dockerfile
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 pmoves && \
    chown -R pmoves:pmoves /app
USER pmoves:pmoves
```

### Docker Compose Anchor Usage
```yaml
services:
  my-service:
    <<: *tier-agent-hardened-ro  # Inherits: cap_drop, read_only, tmpfs, no-new-privileges
```

---

## Improvement Areas

| Area | Current | Target | Priority |
|------|---------|--------|----------|
| HEALTHCHECK in Dockerfile | 12/47 (25%) | 38/47 (80%) | P3 |
| SHA-Pinned Base Images | 0/60+ | 47/47 native | P3 |
| Multi-Stage Builds | 4/47 | 20/47 (Python slim) | P3 |
| Distroless Migration | 1/47 | 10/47 (stateless) | P3 |

---

## Related Documentation

- Hardening tracker: `docs/hardening/PMOVES-hardening-tracker.md` (v4.0)
- P2 issue tracker: `pmoves/docs/security/P2_SUBMODULE_TRACKER.md`
- Production blockers: `pmoves/docs/audit/PRODUCTION_AUDIT_BLOCKER_STATUS.md`
- Test suite: `pmoves/tests/hardening/test_docker_hardening.py`
- CI validation: `.github/workflows/hardening-validation.yml`
