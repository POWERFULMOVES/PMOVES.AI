# Service Documentation Matrix

**Living Document** | **Last Updated:** 2026-02-19

> Maps every PMOVES.AI service to its documentation, NATS subjects, health endpoints, ports, and audit status. Use this matrix to quickly find all documentation related to a specific service.

---

## Legend

| Column | Description |
|--------|-------------|
| **Service** | Service name as in docker-compose |
| **Port** | HTTP port(s) |
| **CLAUDE.md** | Submodule-level context file |
| **README** | Service-specific README |
| **API Docs** | API reference or endpoint docs |
| **NATS** | Primary NATS subjects |
| **Health** | Health endpoint path |
| **Audit** | Phase C audit status (P1/P2/GREEN) |
| **Layer** | CHIT layer classification |

---

## Agent Coordination & Orchestration

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| Agent Zero | 8080, 8081 | `PMOVES-Agent-Zero/CLAUDE.md` | `PMOVES-Agent-Zero/README.md` | `.claude/context/mcp-api.md` | `agent.*`, `claude.code.*` | `/healthz` | P1 (root, NATS) | L3 |
| Archon | 8091, 3737 | `PMOVES-Archon/CLAUDE.md` | `PMOVES-Archon/README.md` | `pmoves/docs/ARCHON_INTEGRATION.md` | `archon.*` | `/healthz` | -- | L3 |
| Mesh Agent | -- | -- | -- | -- | `mesh.announce.*` | -- | -- | L3 |
| Channel Monitor | 8097 | -- | `pmoves/services/channel-monitor/` | -- | -- | `/healthz` | -- | L3 |
| Cipher Memory | 8105 | `Pmoves-cipher/CLAUDE.md` | `Pmoves-cipher/README.md` | Inline | `cipher.*` | `/health` | -- | L3 |

## Retrieval & Knowledge Services

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| Hi-RAG Gateway v2 | 8086, 8087 | `PMOVES-HiRAG/CLAUDE.md` | `PMOVES-HiRAG/README.md` | Inline | `geometry.packet.*` | `/healthz` | P1 (injection, creds) | L3 |
| Hi-RAG Gateway v1 | 8089, 8090 | -- | -- | -- | -- | `/healthz` | Legacy | L3 |
| DeepResearch | 8098 | `PMOVES-Deep-Serch/CLAUDE.md` | `PMOVES-Deep-Serch/README.md` | -- | `research.deepresearch.*` | `/healthz` | -- | L3 |
| SupaSerch | 8099 | -- | -- | -- | `supaserch.*` | `/healthz` | -- | L3 |
| Open Notebook | -- | `PMOVES-Open-Notebook/CLAUDE.md` | `PMOVES-Open-Notebook/README.md` | -- | -- | -- | P1 (SurrealDB root) | L3 |

## Voice & Speech Services

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| Flute-Gateway | 8055, 8056 | -- | -- | `.claude/context/flute-gateway.md` | `voice.tts.*`, `voice.stt.*` | `/healthz` | -- | L3 |
| Ultimate-TTS-Studio | 7861 | -- | `PMOVES-Ultimate-TTS-Studio/README.md` | Gradio API | -- | `/gradio_api/info` | -- | L3 |
| Pipecat | -- | `PMOVES-Pipecat/CLAUDE.md` | `PMOVES-Pipecat/README.md` | -- | `voice.*` | -- | P2 (no allowlist) | L3 |

## Media Ingestion & Processing

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| PMOVES.YT | 8077 | -- | `PMOVES.YT/README.md` | Inline | `ingest.*` | `/healthz` | P2 (MinIO creds) | L3 |
| FFmpeg-Whisper | 8078 | -- | -- | -- | `ingest.transcript.*` | `/healthz` | -- | L3 |
| Media-Video | 8079 | -- | -- | -- | `ingest.video.*` | `/healthz` | -- | L3 |
| Media-Audio | 8082 | -- | -- | -- | `ingest.audio.*` | `/healthz` | -- | L3 |
| Extract Worker | 8083 | -- | -- | `POST /ingest` | `extract.*` | `/healthz` | -- | L3 |
| PDF Ingest | 8092 | -- | -- | -- | -- | `/healthz` | -- | L3 |
| LangExtract | 8084 | -- | -- | -- | -- | `/healthz` | -- | L3 |
| Notebook Sync | 8095 | -- | -- | -- | -- | `/healthz` | -- | L3 |

## Utility & Integration Services

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| Presign | 8088 | -- | -- | Inline | -- | `/healthz` | -- | L3 |
| Render Webhook | 8085 | -- | -- | -- | -- | `/healthz` | -- | L3 |
| Publisher-Discord | 8094 | -- | -- | -- | `ingest.file.*`, `ingest.transcript.*` | `/healthz` | -- | L3 |
| Jellyfin Bridge | 8093 | `PMOVES-Jellyfin/CLAUDE.md` | `PMOVES-Jellyfin/README.md` | -- | -- | `/healthz` | -- | L3 |
| BoTZ Gateway | -- | `PMOVES-BoTZ/CLAUDE.md` | `PMOVES-BoTZ/README.md` | -- | `botz.*` | -- | P1 (JWT fail-open) | L3 |
| DoX | -- | `PMOVES-DoX/CLAUDE.md` | `PMOVES-DoX/README.md` | -- | -- | -- | P1 (NATS unauth) | L3 |

## Infrastructure & Data

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| TensorZero Gateway | 3030 | `PMOVES-tensorzero/CLAUDE.md` | `PMOVES-tensorzero/README.md` | `.claude/context/tensorzero.md` | -- | `/healthz` | P1 (root, ClickHouse creds) | L1 |
| TensorZero ClickHouse | 8123 | -- | -- | -- | -- | `/ping` | -- | L1 |
| TensorZero UI | 4000 | -- | -- | -- | -- | -- | -- | L1 |
| NATS | 4222 | -- | -- | `.claude/context/nats-subjects.md` | all | `/varz` (8222) | -- | L1 |
| Supabase | 3010 | `PMOVES-supabase/CLAUDE.md` | -- | PostgREST | -- | -- | -- | L1 |
| Qdrant | 6333 | -- | -- | REST API | -- | `/healthz` | -- | L1 |
| Neo4j | 7474, 7687 | -- | -- | Bolt/HTTP | -- | -- | -- | L1 |
| Meilisearch | 7700 | -- | -- | REST API | -- | `/health` | -- | L1 |
| MinIO | 9000, 9001 | -- | -- | S3 API | -- | `/minio/health/live` | -- | L1 |

## Monitoring Stack

| Service | Port | CLAUDE.md | README | API Docs | NATS Subjects | Health | Audit | Layer |
|---------|------|-----------|--------|----------|---------------|--------|-------|-------|
| Prometheus | 9090 | -- | -- | PromQL | -- | `/-/healthy` | -- | L5 |
| Grafana | 3000 | -- | -- | -- | -- | `/api/health` | -- | L5 |
| Loki | 3100 | -- | -- | LogQL | -- | `/ready` | -- | L5 |
| cAdvisor | 8080 | -- | -- | -- | -- | `/healthz` | -- | L5 |

---

## Submodule Documentation Status

| Submodule | README | CLAUDE.md | CHANGELOG | Audit Status | Branch |
|-----------|--------|-----------|-----------|-------------|--------|
| PMOVES-Agent-Zero | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-Archon | Yes | Yes | -- | -- | Hardened |
| PMOVES-BoTZ | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-DoX | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-HiRAG | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-Open-Notebook | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-Pipecat | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-tensorzero | Yes | Yes | -- | Phase C complete | Hardened |
| PMOVES-ToKenism-Multi | Yes | Yes | -- | -- | Hardened |
| PMOVES.YT | Yes | -- | -- | Phase C complete | Hardened |
| PMOVES-Deep-Serch | Yes | Yes | -- | -- | Hardened |
| PMOVES-Jellyfin | Yes | Yes | -- | -- | Hardened |
| PMOVES-Wealth | Yes | -- | -- | -- | Hardened |
| Pmoves-cipher | Yes | Yes | -- | -- | main |
| PMOVES-crush | Yes | -- | -- | -- | Hardened |
| PMOVES-llama-throughput-lab | Yes | -- | -- | -- | Hardened |
| PMOVES-supabase | Yes | Yes | -- | -- | Hardened |
| PMOVES-surf | Yes | -- | -- | -- | Hardened |
| PMOVES-A2UI | Yes | -- | -- | -- | Hardened |
| Pmoves-hyperdimensions | Yes | -- | -- | -- | Hardened |

---

## Gap Analysis

### Services Missing Documentation
- Mesh Agent: No dedicated docs (inline in compose only)
- FFmpeg-Whisper: No README or API docs
- Media-Video / Media-Audio: No README or API docs
- LangExtract: No README or API docs
- Notebook Sync: No README or API docs
- Presign / Render Webhook: No README, API docs inline in code

### Submodules Missing CLAUDE.md
- PMOVES.YT, PMOVES-Wealth, PMOVES-crush, PMOVES-llama-throughput-lab
- PMOVES-surf, PMOVES-A2UI, Pmoves-hyperdimensions

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
*See also: [DOCUMENTATION_MAP.md](DOCUMENTATION_MAP.md) for layer taxonomy.*
