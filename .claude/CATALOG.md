# PMOVES.AI Service Catalog

**Ports, URLs, health endpoints. Load this on demand when you need a specific service address.**

Most HTTP services expose `/healthz` for liveness and `/metrics` for Prometheus, but
treat each entry's listed endpoint as authoritative — exceptions exist (e.g., Mesh
Agent has no HTTP interface; Cipher Memory exposes `/health`, not `/healthz`).

## Core Infrastructure

**TensorZero Gateway** `:3030` — **[PRIMARY MODEL PROVIDER & OBSERVABILITY]**
- Centralized LLM gateway for all providers (OpenAI, Anthropic, Venice, Ollama)
- ClickHouse-backed observability, request/response logging, token tracking
- UI dashboard at `:4000`
- Chat API: `http://localhost:3030/v1/chat/completions`
- Embedding API: `http://localhost:3030/openai/v1/embeddings` (**NOT** `/v1/embeddings` — returns 404)
- Embedding model format: `tensorzero::embedding_model_name::<model_name>` (e.g., `qwen3_embedding_4b_local`)
- Qwen3-Embedding-4B = **2560d** (not 3072); Qwen3-Embedding-8B = 4096d
- **Use for:** all LLM calls, embeddings, provider routing, usage analytics
- Detail: `.claude/context/tensorzero.md`

**TensorZero ClickHouse** `:8123` — Observability metrics storage. `curl http://localhost:8123/ping`.

**TensorZero UI** `:4000` — Metrics dashboard, request inspection.

## Agent Coordination & Orchestration

**Agent Zero** `:8080` API, `:8081` UI — Control-plane orchestrator. MCP API at `/mcp/*`. Subscribes to NATS. Health: `GET http://localhost:8080/healthz`. **Use for:** orchestration, MCP commands, task delegation.

**Mesh Agent** (no HTTP) — Distributed node announcer; publishes host presence/capabilities on NATS every 15s.

**Archon** `:3090` API/UI/MCP (unified), `:3737` host alias → 3090 — Archon 0.6.0 (TypeScript/Bun) remote-coding-agent, Postgres-backed (pg_notify), prompt/form management. Connects to Agent Zero MCP. Health: `GET http://localhost:3090/api/health`. _(0.6.0 rewrote the old Python `:8091`/`:8051` service — #2217.)_

**DeepSeek Harness (dsh)** `:3080` web UI — Cordis-based harness where everything is a plugin (profile/bundle/patch composition). Hosts OTHER harnesses via `packages/hooks/hook-protocol` plus per-harness dialects (`hooks-claude-code`, `hooks-codex`); capability seams keyed `ctx.*` with swappable LLM impls (`llm-deepseek`, `llm-pi-ai`, `llm-retry`). The reference the PMOVES harness registry is measured against — see `pmoves/configs/tac_trees/deepseek-harness.tac.yaml`. Port is the boot default (`packages/boot/cmdline`, `ctx.webStartup.port ?? 3080`); verified unclaimed in this catalog and in every compose file. Submodule is **not populated by default** — `git submodule update --init PMOVES-deepseek-harness` before use.

**Channel Monitor** `:8097` — External content watcher (YouTube channels). Posts to PMOVES.YT `/yt/ingest`.

**HF MCP Server** `:8203` (host) / `:8096` (container) — HuggingFace Hub MCP server. Tools: `hf.model.search/info/download/list/convert_gguf`. SSE MCP at `/mcp/sse` (real JSON-RPC over SSE via `mcp.server.MCPServer`; POST messages to `/mcp/messages/`), REST API at `/api/*`, publishes `hf.model.downloaded.v1`. Downloads to `${HF_HOME:-./data/models}`:/models; inference services can mount the same path or import converted GGUF artifacts. Health: `GET /healthz`. Profile: `agents`/`research`.

**Cipher Memory** `:8105` (host) / `:3000` (container) — Agent memory service. Submodule `Pmoves-cipher` forked from `campfirein/byterover-cli` v3.16.1 (formerly Cipher) with PMOVES additive shim (`src/pmoves/`). REST: `/api/memory` CRUD (POST/GET/search/DELETE — PMOVES PR #5 + A1-Shim), `GET /health` (NOT `/healthz`). MCP: SSE at `/mcp/sse` (4 tools: `pmoves_cipher_store`, `pmoves_cipher_search`, `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns`), POST `/mcp/messages`. **Auth:** `Authorization: Bearer ${CIPHER_API_TOKEN}` on all routes except `/health` (dev-skip if unset). NATS: emits `cipher.memory.stored.v1`, `.searched.v1`, `cipher.reasoning.stored.v1` + `services.announce.v1` (discovery mesh). Python bridge (`pmoves-cipher-mcp/`) DISABLED since 2026-05-15 — agents connect direct SSE. See `pmoves/docs/TAC/TAC_CIPHER.md` for architecture decision + A1-Shim workorder. BoTZ variant: separate instance at `:8081`, own `botz.cipher.*` NATS namespace. DoX variant: native Python CipherService at `:8096`.

## Retrieval & Knowledge Services

**Hi-RAG Gateway v2** `:8086` CPU, `:8087` GPU **[PREFERRED]** — Hybrid RAG with cross-encoder reranking. Combines Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text). API: `POST /hirag/query` with `{"query": "...", "top_k": 10, "rerank": true}`.

**Hi-RAG Gateway v1** `:8089` CPU, `:8187` GPU **[LEGACY]** — Use v2 for new features.

**DeepResearch** `:8098` — LLM-based research planner (Alibaba Tongyi). NATS worker on `research.deepresearch.request.v1`. Auto-publishes results to Open Notebook.

**SupaSerch** `:8099` — Multimodal holographic deep research orchestrator. Coordinates DeepResearch + Archon/Agent Zero MCP. NATS: `supaserch.request.v1` / `supaserch.result.v1`. Metrics: `GET /metrics`.

**Open Notebook** (external, SurrealDB) — Accessed via `$OPEN_NOTEBOOK_API_URL` + token.

**clap-embed** `:8108` — Deterministic CLAP audio/text embedder (MOF lattice node, `laion/larger_clap_music`). `POST /embed/audio`, `POST /embed/text`, `GET /healthz`, `GET /metrics`. Optional NATS `audio.embed.request.v1`/`audio.embed.result.v1`. WS-A grounding layer.

**clip-embed** `:8109` — Deterministic CLIP image/text embedder (`openai/clip-vit-large-patch14`, MIT). `POST /embed/image` (multipart), `POST /embed/text`, `GET /healthz`, `GET /metrics`. 768-d, L2-normalised. Used for keyframe embeddings in media pipeline.

**A2UI Renderer** `:8107` — Remotion animation engine for the creator pipeline. Converts A2UI animation JSON specs into MP4/GIF/WebM, uploads to MinIO, publishes NATS events. `POST /render`, `/render/chart`, `/render/provenance` (JWT fail-closed), `GET /healthz`, `GET /metrics`. Skill: `/remotion-render`. **Was 8105 — moved to avoid collision with Cipher Memory's host-published 8105.** Wired into `docker-compose.yml` under the **`creator`** profile (opt-in — heavy Remotion/Chromium image): `make -C pmoves up-a2ui-renderer` (#2228).

## Voice & Speech

**Flute-Gateway** `:8055` (HTTP + WebSocket) — Multimodal voice communication with Pipecat. Prosodic TTS. API: `POST /v1/voice/synthesize/prosodic` (returns `audio/wav`), `GET /v1/voice/config`, `GET /v1/voice/binding`. WS: `/v1/voice/stream/tts`, `/v1/voice/agent`. Auth: `X-API-Key` header (no Bearer/JWT). Health: `GET /healthz`. Detail: `.claude/context/flute-gateway.md`.

**Ultimate-TTS-Studio** `:7860` native, `:7861` Docker — 14-engine TTS (KittenTTS, Kokoro, F5, IndexTTS/2, Fish Speech S1/S2 Pro, VoxCPM, Higgs Audio, Chatterbox variants, Qwen Voice Design, VibeVoice). Gradio UI. **GPU-accelerated, runs natively via Pinokio (NOT Docker).** Health: `GET /gradio_api/info`.

## Media Ingestion & Processing

**PMOVES.YT** `:8077` — YouTube ingestion. Downloads to MinIO, retrieves transcripts. API: `POST /yt/ingest`.

**FFmpeg-Whisper** `:8078` — Media transcription with Faster-Whisper (small model). GPU. Reads/writes MinIO.

**Media-Video Analyzer** `:8079` — object detection over sampled video frames. On `main` this is a FastAPI **stub** (`server.py` with `/healthz`, `/metrics`, GPU detection; analysis pipeline was `TODO`) — it starts and serves health, it does not crash-loop. Full pipeline implemented in PR #2182 (OpenCV frame sampling → **DETR** default, YOLO selectable via `DETECTION_ENGINE`). Wired into `docker-compose.media.yml`. Health: `GET /healthz`.

**Media-Audio Analyzer** `:8082` — audio analysis (STT + diarization + emotion). On `main` this is a FastAPI **stub** (`server.py` with `/healthz`, `/metrics`, GPU detection; analysis pipeline was `TODO`) — it starts and serves health, it does not crash-loop. Full pipeline implemented in PR #2181 (whisper-large-v3-turbo + pyannote-3.1 + `superb/hubert-large-superb-er`). Wired into `docker-compose.media.yml`. Health: `GET /healthz`.

**Extract Worker** `:8083` — Text embedding + indexing. Qdrant (vectors) + Meilisearch (FTS). Model: `all-MiniLM-L6-v2`. API: `POST /ingest`.

**PDF Ingest** `:8092` — Document ingestion orchestrator. Reads PDFs from MinIO, sends to extract-worker.

**LangExtract** `:8084` — Language detection + NLP preprocessing. Used by notebook sync.

**Notebook Sync** `:8095` — SurrealDB Open Notebook synchronizer. Poll interval 300s. Calls LangExtract + Extract Worker.

## Utility & Integration

**Presign** `:8088` — MinIO URL presigner for short-lived downloads. Requires `$PRESIGN_SHARED_SECRET`. Allowed buckets: `assets`, `outputs`.

**Render Webhook** `:8085` — ComfyUI render callback handler. Requires `$RENDER_WEBHOOK_SHARED_SECRET`. Writes to Supabase, stores to MinIO.

**Publisher-Discord** `:8094` — Discord notification bot. Listens on `ingest.file.added.v1`, `ingest.transcript.ready.v1`, summary/chapter events.

**Jellyfin Bridge** `:8093` — Jellyfin metadata webhook + helper. Syncs Jellyfin events to Supabase.

## Monitoring Stack

**Prometheus** `:9090` — Metrics scrape from all services (all expose `/metrics`).
**Grafana** `:3000` — Dashboards, datasources Prometheus + Loki. Pre-configured "Services Overview".
**Loki** `:3100` + **Promtail** — Centralized log aggregation. All services configured with Loki labels.
**cAdvisor** `:8080` — Container metrics for Prometheus.

## Data Storage

**NATS** `:4222`, `:9223` WS (standalone DoX), `:9222` WS (docked via parent compose) — JetStream event broker. **Always authenticated:** `nats://${NATS_USER}:${NATS_PASS}@localhost:4222` (set via `${NATS_URL}` env var in `env.tier-*`). Subject catalog: `.claude/context/nats-subjects.md`.

**Supabase** — 13-service self-hosted stack (profile `supabase-local`). Kong `:8000`, PostgREST `:3000`, Studio `:54323`. Canonical consumer URL: `http://supabase-kong:8000/rest/v1`. Standard vars: `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY` (`SUPABASE_*` aliases for compat). Services: DB (Postgres 17.6.1), GoTrue, PostgREST v14.3, Kong 3.7.1, Realtime v2.72.0, Storage v1.37.1, Studio, imgproxy, pg-meta, Edge Functions, Analytics (Logflare), Vector, Supavisor.

**Neo4j** `:7474` HTTP, `:7687` Bolt — Graph DB for CHIT consciousness taxonomy, agent memory. Profile: `make -C pmoves neo4j-local-up`. API: `POST http://localhost:7474/db/neo4j/tx/commit`. Submodule: `PMOVES-Neo4j`.

**Qdrant** `:6333` — Vector embeddings. Primary collection: `pmoves_chunks_qwen3` (2560d, Qwen3-Embedding-4B). Legacy: `pmoves_chunks` (384d, MiniLM — do not use). **CRITICAL:** `QDRANT_RECREATE_ON_DIM_MISMATCH` defaults to true; **will delete all data** if dims change — always `false` in production. Hi-RAG v2 requires `EMBEDDING_BACKEND=tensorzero` in compose env.

**Meilisearch** `:7700` — Full-text keyword search, typo-tolerant.

**MinIO** `:9000` API, `:9001` Console — S3-compatible. Buckets: `assets`, `outputs`.

## Hostinger KVM Fleet

Three KVMs make up the production VPS substrate (see `pmoves/docs/operations/TOPOLOGY.md` lines 20–22, 135–180, 240–243, 258 for the canonical source):

| Host | Tailscale name | Role | Key services | Hub flag |
|------|---------------|------|--------------|----------|
| `pmoves-kvm4-1` | `pmoves-kvm4-1` | API gateway | TensorZero `:3030`, Agent Zero `:8080`, Hi-RAG v2 `:8086` (⚠ NOT currently deployed — :8086 down / no container, verified 2026-07-04), Archon `:3090`, Mesh Agent, Gateway Agent `:8100`, Extract Worker `:8083` | — |
| `pmoves-kvm4-2` | `pmoves-kvm4-2` | Data hub | **NATS `:4222` (fleet hub, DNS `nats.pmoves.ai`)**, Supabase 13-svc stack, Qdrant `:6333`, Neo4j `:7687`, Meilisearch `:7700`, Prometheus `:9090`, Grafana `:3002`, Loki `:3100`, MinIO `:9000` | NATS-hub |
| `pmoves-kvm2` | `pmoves-kvm2` | Reverse proxy + relay | nginx `:80/443` (SSL termination), RustDesk `hbbs/hbbr` (rendezvous + relay) | — |

**NATS hub addressing**: `nats://${NATS_USER}:${NATS_PASS}@pmoves-kvm4-2:4222` (Tailscale-internal, set via `${NATS_URL}`). All nodes (5090, 4090, SPARK, B850, Z890) connect here for cross-node fan-out. Local-node NATS instances (e.g. `pmoves-nats-1` on 5090) are NOT leafnoded to the hub by default — for fleet signal dispatch use either an MCP that points at the hub URL or SSH to KVM4-2 then `docker exec ... nats pub`.

**SSH addressing (fallback path)**: `${HOSTINGER_KVM4_N_USER:-root}@${HOSTINGER_KVM4_N_IP:-pmoves-kvm4-N}` per `deploy/scripts/deploy-vps.sh:38`. Key at `$PMOVES_SECRETS_DIR/hostinger_vps` (fallback `$LOCALAPPDATA/Temp/hostinger_vps`).

## MCP Servers — declared in `.claude/mcp.json`

| Server | Transport | Required env | Source path | Notes |
|--------|-----------|--------------|-------------|-------|
| `pmoves-cipher` | SSE `localhost:8105/mcp/sse` | none | cipher-api container | Per-host bind broken on Docker Desktop WSL2 (PR #1512 documents the operator-side `CIPHER_BIND` override fix) |
| `pmoves-nats-fleet` | stdio | `NATS_URL` (declared inline) | `pmoves-nats-mcp/nats_mcp/server.py` | Publishes/subscribes to the fleet hub at KVM4-2. No env.shared dependency. |
| `docker` | stdio (image `mcp/docker`) | none | Docker socket | Container inspect/exec on the local Docker daemon |
| `hostinger-mcp` | stdio (GitHub fork `POWERFULMOVES/pmoves-hostinger-api-mcp-server#094e38c`, v1.35.7, 320 tools) | `HOSTINGER_API_KEY` | git fork, commit-pinned | No-op until env populated. VPS list/status/reboot, DNS ops, IP mgmt |
| `tailscale` | stdio (npm pkg `tailscale-mcp@2026.4.10-1`) | `TAILSCALE_API_KEY`, `TAILSCALE_TAILNET` | npm package | No-op until env populated. Tailnet inventory, ACL audit, stale-node sweep |

**Secrets pipeline (canonical)** — never paste API keys in chat. Set in `pmoves/env.tier-api` (or per-tier file), run `make -C pmoves secrets-funnel`, restart the consuming container or Claude Code session. The env.shared multi-line value rule applies: keep secrets single-line escaped or behind `_PATH` references; multi-line bodies break dotenv parsing.

## Integration Rule — Leverage, Don't Duplicate

- **DO** use Hi-RAG v2 for knowledge retrieval
- **DO** publish to NATS for event coordination (via `pmoves-nats-fleet` MCP, `make -C pmoves nats-pub`, or AZ `/mcp/execute`)
- **DO** store artifacts in MinIO via Presign
- **DO** call Agent Zero MCP API for orchestration
- **DON'T** build new RAG, search, or monitoring systems
- **DON'T** create new event buses or message brokers
- **DON'T** duplicate existing embeddings or indexing
- **DON'T** paste API keys / secrets in chat — secrets flow through env.tier-* → `make secrets-funnel`
