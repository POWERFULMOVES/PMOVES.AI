# TAC Tree: Supabase (Self-Hosted 13-Service Stack)

> Technology-Architecture-Context tree for the Supabase self-hosted platform integration.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Supabase (Self-Hosted 13-Service Stack) |
| **Ports** | Kong: 8000, PostgREST: 3000, GoTrue: 9999, Studio: 54323, Realtime: 4000, Storage: 5000, DB: 5432, Meta: 8080, Analytics: 4000, Vector: 9001, Pooler: 6543, Edge Functions: 54321, imgproxy: 5001 |
| **Health** | GoTrue: `GET /health`, PostgREST: `GET /`, Realtime: `GET /`, Kong: gateway probe |
| **Metrics** | `supabase_health` blackbox job + `supabase-postgres` exporter |
| **Submodule** | `PMOVES-supabase` |
| **Docker Profile** | `supabase-local` |
| **Tier** | data |
| **Class** | Standard |
| **Evolution** | Stage 2 |
| **Runtime** | CLI (preferred) or compose (fallback), guarded by `supabase_runtime_guard.py` |

## Architecture

Supabase is a **self-hosted 13-service platform** providing the unified data layer for PMOVES.AI. It provides:

1. **PostgreSQL database** — Primary relational store (Postgres 17.6.1) with 42 migrations
2. **Authentication** — GoTrue for JWT-based auth, single `JWT_SECRET` signs `ANON_KEY` + `SERVICE_ROLE_KEY`
3. **REST API** — PostgREST v14.3 auto-generates REST endpoints from database schema
4. **Realtime** — WebSocket channels (v2.72.0) for chat, ingestion queue, geometry bus
5. **Storage** — S3-compatible object storage with presign integration
6. **Edge Functions** — Deno-based serverless functions (youtube_oembed_cache, yt_chapters_ingest)
7. **RLS policies** — 7+ policy sets (geometry bus, channels, service catalog, persona, studio board)
8. **Service catalog** — 100+ entries for PMOVES service discovery
9. **Studio** — Admin dashboard at port 54323

### Sub-Services

| Service | Port | Purpose |
|---------|------|---------|
| Kong Gateway | 8000 | API gateway, consumer URL: `http://supabase-kong:8000/rest/v1` |
| PostgREST | 3000 | Auto-generated REST API |
| GoTrue | 9999 | Auth (JWT issuance, user management) |
| Studio | 54323 | Admin UI |
| Realtime | 4000 | WebSocket channels |
| Storage | 5000 | S3-compatible file storage |
| PostgreSQL DB | 5432 | Primary database |
| pg-meta | 8080 | Database metadata API |
| Analytics (Logflare) | 4000 | Log analytics |
| Vector | 9001 | Log collection agent |
| Supavisor (Pooler) | 6543 | Connection pooling |
| Edge Functions | 54321 | Deno serverless runtime |
| imgproxy | 5001 | Image transformation proxy |

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| Docker Engine | Container runtime | Yes |
| `JWT_SECRET` | Auth signing key | Yes |
| `env.supabase` + `env.tier-supabase` | Configuration | Yes |
| MinIO (9000) | S3-compatible storage (presign bridge) | Optional |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero (8080) | PostgREST API | Agent state persistence, task records |
| Archon (8091) | PostgREST API | Prompt/form management, agent services |
| Hi-RAG v2 (8086) | PostgREST API | Knowledge metadata storage |
| Media analyzers | PostgREST API | Video/audio analysis results |
| Render Webhook (8085) | PostgREST API | ComfyUI render callbacks |
| Jellyfin Bridge (8093) | PostgREST API | Media metadata sync |
| Channel Monitor (8097) | PostgREST API | Content watch state |
| Cipher Memory (8105) | PostgREST API | Memory index metadata |
| Extract Worker (8083) | PostgREST API | Embedding job tracking |
| UI (A2UI, MAI-UI) | PostgREST + Realtime | Frontend data + live updates |
| NATS-connected services | Via Supabase data | Event-driven state coordination |

## NATS Subjects

Supabase itself does not publish directly to NATS, but multiple services bridge Supabase data to NATS:

| Subject | Direction | Bridge Service | Description |
|---------|-----------|----------------|-------------|
| `ingest.file.added.v1` | Via Extract Worker | extract-worker | New file indexed in Supabase |
| `ingest.transcript.ready.v1` | Via PMOVES.YT | pmoves-yt | Transcript stored in Supabase |
| `geometry.cgp.v1` | Via Realtime | tokenism | CGP packets via Realtime channel |
| `ops.service.catalog.updated.v1` | Via Gateway | gateway | Service catalog mutation |

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | **Partial** | Consciousness theory data loaded (`load_supabase_chunks.py`) |
| Delta/Kappa/Hz sensitivity | None | All toggles `false` — data tier, not compute |
| Swarm participant | No | |
| Attribution gated | No | |
| BPM capable | No | Not prosodic-oriented |
| Schema as CGP | **Planned** | Encode migration changes as CGP packets |

## Production Audit Checklist

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Docker hardening | **GREEN** | All 13 services in compose with `env.tier-supabase` |
| Health checks | **GREEN** | GoTrue `/health`, PostgREST `/`, Realtime `/`, Kong gateway probe |
| Prometheus scrape | **GREEN** | `supabase_health` blackbox job + `supabase-postgres` exporter |
| Auth (JWT) | **GREEN** | Single `JWT_SECRET` signs `ANON_KEY` + `SERVICE_ROLE_KEY` via `generate-keys.sh` |
| RLS policies | **GREEN** | 7+ policy sets: geometry bus, channels, service catalog, persona, studio board |
| Database migrations | **GREEN** | 42 files (23 initdb + 19 incremental), managed via `supa-migrate` |
| Edge Functions | **Partial** | 2 functions deployed; JWT verification disabled |
| Realtime channels | **GREEN** | WebSocket channels for chat, ingestion queue, geometry bus |
| Storage integration | **GREEN** | S3-compatible via presign service, bucket: `pmoves-storage` |
| Cron/Scheduled queries | **Partial** | `model_spotlight` uses n8n-triggered queries (not pg_cron) |
| NATS integration | **GREEN** | Multiple services publish/subscribe via Supabase data |
| `env.shared` format | **GREEN** | `env.supabase` + `env.tier-supabase` with runtime bridge |
| Dual-runtime guard | **GREEN** | `supabase_runtime_guard.py` prevents CLI/compose conflicts |
| Service catalog | **GREEN** | 100+ entries with discovery endpoints |

## Hardening Roadmap

### Phase 1: Health & Observability — **DONE**

1. ~~Healthchecks~~ — All 13 services monitored (GoTrue `/health`, PostgREST `/`, Realtime `/`)
2. ~~Prometheus scrape~~ — Blackbox probes + postgres exporter registered
3. ~~Dual-runtime guard~~ — `supabase_runtime_guard.py` prevents CLI/compose stack conflicts

### Phase 2: Auth & Security — **DONE**

1. ~~JWT from single secret~~ — `generate-keys.sh` creates `JWT_SECRET`, signs `ANON_KEY` + `SERVICE_ROLE_KEY`
2. ~~RLS policies~~ — 7+ policy sets across public and internal schemas
3. ~~Service catalog~~ — 100+ entries with discovery API

### Phase 3: Edge Functions — **PARTIAL**

1. ~~2 functions deployed~~ — `youtube_oembed_cache`, `yt_chapters_ingest`
2. **TODO:** Enable JWT verification on Edge Functions
3. **TODO:** Add presign proxy function for unified storage access
4. **TODO:** Add webhook handler functions

### Phase 4: Scheduled Jobs — **PARTIAL**

1. ~~`model_spotlight` uses n8n-triggered queries~~
2. **TODO:** Evaluate `pg_cron` for in-database scheduling
3. **TODO:** Document n8n ↔ Supabase scheduled workflow patterns

### Phase 5: Realtime — **DONE**

1. ~~Chat channels~~ — Real-time message sync
2. ~~Ingestion queue~~ — Job status updates via WebSocket
3. ~~Geometry bus~~ — CGP live updates via Realtime

### Phase 6: Storage Distribution — **TODO**

1. Replace local junctions with presigned URL distribution for Pinokio launchers
2. Upload large assets to MinIO bucket via presign service
3. Create presign-aware launcher bootstrap

### Phase 7: CHIT Integration — **TODO**

1. Encode Supabase schema changes as CGP packets
2. Migration audit trail via Graphiti signing
3. Consciousness theory data already loaded (`load_supabase_chunks.py`)

## Key Files Reference

| Category | Path |
|----------|------|
| Compose | `pmoves/docker-compose.yml` (`supabase-local` profile) |
| DoX Compose | `PMOVES-DoX/docker-compose.supabase.yml` |
| Env | `pmoves/env.supabase`, `pmoves/env.tier-supabase.example` |
| Config | `pmoves/supabase/config.toml` |
| Migrations | `pmoves/supabase/migrations/` (42 files) |
| InitDB | `pmoves/supabase/initdb/` (23 files) |
| Scripts | `pmoves/scripts/supabase/` (7 scripts) |
| Tools | `pmoves/tools/supabase_runtime_guard.py` |
| Client | `pmoves/services/common/supabase.py` |
| Gateway | `pmoves/services/gateway/gateway/integrations/supabase.py` |
| UI | `pmoves/ui/config/supabaseProviders.ts` |
| Tests | `pmoves/tests/smoke/test_supabase_*.py` (3 files) |
| Docs | `pmoves/docs/services/supabase/` (13 files) |

## Cross-Links

- **Submodule:** `PMOVES-supabase/`
- **Credential Flow:** `.claude/context/credentials-workflow.md`
- **CHIT Integration Status:** `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `supabase`
- **Agent Topology:** `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` → Data Infrastructure
- **DoX Fork:** `PMOVES-DoX/docker-compose.supabase.yml`

## Open Items

- Enable JWT verification on Edge Functions (Phase 3)
- Evaluate pg_cron for in-database scheduling (Phase 4)
- Replace local junctions with presigned URL distribution (Phase 6)
- Encode schema changes as CGP packets (Phase 7)
- Document n8n ↔ Supabase scheduled workflow patterns

<!-- GRAPHITI_MARK: Z890-CLAUDE::TAC-SUPABASE-CREATION::2026-03-17 -->
