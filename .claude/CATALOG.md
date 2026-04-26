# PMOVES.AI Service Catalog

**Ports, URLs, health endpoints. Load this on demand when you need a specific service address.**

All services expose `/healthz` for liveness and `/metrics` for Prometheus.

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

**Archon** `:8091` API, `:3737` UI — Supabase-driven agent service, prompt/form management. Connects to Agent Zero MCP. Health: `GET http://localhost:8091/healthz`.

**Channel Monitor** `:8097` — External content watcher (YouTube channels). Posts to PMOVES.YT `/yt/ingest`.

**Cipher Memory** `:8105` — Knowledge-graph memory (Neo4j backend). MCP bridge at `pmoves-cipher-mcp/` (stdio). API: `POST /api/memory`, `GET /api/memory/search?q=...`. Health: `GET /health`. MCP tools: `pmoves_cipher_store`, `pmoves_cipher_search`, `pmoves_cipher_store_reasoning`, `pmoves_cipher_reasoning_patterns`.

## Retrieval & Knowledge Services

**Hi-RAG Gateway v2** `:8086` CPU, `:8087` GPU **[PREFERRED]** — Hybrid RAG with cross-encoder reranking. Combines Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text). API: `POST /hirag/query` with `{"query": "...", "top_k": 10, "rerank": true}`.

**Hi-RAG Gateway v1** `:8089` CPU, `:8187` GPU **[LEGACY]** — Use v2 for new features.

**DeepResearch** `:8098` — LLM-based research planner (Alibaba Tongyi). NATS worker on `research.deepresearch.request.v1`. Auto-publishes results to Open Notebook.

**SupaSerch** `:8099` — Multimodal holographic deep research orchestrator. Coordinates DeepResearch + Archon/Agent Zero MCP. NATS: `supaserch.request.v1` / `supaserch.result.v1`. Metrics: `GET /metrics`.

**Open Notebook** (external, SurrealDB) — Accessed via `$OPEN_NOTEBOOK_API_URL` + token.

## Voice & Speech

**Flute-Gateway** `:8055` HTTP, `:8056` WebSocket — Multimodal voice communication with Pipecat. Prosodic TTS. API: `POST /v1/voice/synthesize/prosodic`. Health: `GET /healthz`. Detail: `.claude/context/flute-gateway.md`.

**Ultimate-TTS-Studio** `:7860` native, `:7861` Docker — 14-engine TTS (KittenTTS, Kokoro, F5, IndexTTS/2, Fish Speech S1/S2 Pro, VoxCPM, Higgs Audio, Chatterbox variants, Qwen Voice Design, VibeVoice). Gradio UI. **GPU-accelerated, runs natively via Pinokio (NOT Docker).** Health: `GET /gradio_api/info`.

## Media Ingestion & Processing

**PMOVES.YT** `:8077` — YouTube ingestion. Downloads to MinIO, retrieves transcripts. API: `POST /yt/ingest`.

**FFmpeg-Whisper** `:8078` — Media transcription with Faster-Whisper (small model). GPU. Reads/writes MinIO.

**Media-Video Analyzer** `:8079` — YOLOv8 frame analysis. Every 5th frame, conf 0.25. Outputs to Supabase.

**Media-Audio Analyzer** `:8082` — Emotion/speaker detection. Model: `superb/hubert-large-superb-er`.

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

**NATS** `:4222`, `:9222` WS (standalone DoX), `:9223` WS (docked via compose) — JetStream event broker. **Always authenticated:** `nats://nats:pmoves@nats:4222`. Subject catalog: `.claude/context/nats-subjects.md`.

**Supabase** — 13-service self-hosted stack (profile `supabase-local`). Kong `:8000`, PostgREST `:3000`, Studio `:54323`. Canonical consumer URL: `http://supabase-kong:8000/rest/v1`. Standard vars: `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY` (`SUPABASE_*` aliases for compat). Services: DB (Postgres 17.6.1), GoTrue, PostgREST v14.3, Kong 3.7.1, Realtime v2.72.0, Storage v1.37.1, Studio, imgproxy, pg-meta, Edge Functions, Analytics (Logflare), Vector, Supavisor.

**Neo4j** `:7474` HTTP, `:7687` Bolt — Graph DB for CHIT consciousness taxonomy, agent memory. Profile: `make -C pmoves neo4j-local-up`. API: `POST http://localhost:7474/db/neo4j/tx/commit`. Submodule: `PMOVES-Neo4j`.

**Qdrant** `:6333` — Vector embeddings. Primary collection: `pmoves_chunks_qwen3` (2560d, Qwen3-Embedding-4B). Legacy: `pmoves_chunks` (384d, MiniLM — do not use). **CRITICAL:** `QDRANT_RECREATE_ON_DIM_MISMATCH` defaults to true; **will delete all data** if dims change — always `false` in production. Hi-RAG v2 requires `EMBEDDING_BACKEND=tensorzero` in compose env.

**Meilisearch** `:7700` — Full-text keyword search, typo-tolerant.

**MinIO** `:9000` API, `:9001` Console — S3-compatible. Buckets: `assets`, `outputs`.

## Integration Rule — Leverage, Don't Duplicate

- **DO** use Hi-RAG v2 for knowledge retrieval
- **DO** publish to NATS for event coordination
- **DO** store artifacts in MinIO via Presign
- **DO** call Agent Zero MCP API for orchestration
- **DON'T** build new RAG, search, or monitoring systems
- **DON'T** create new event buses or message brokers
- **DON'T** duplicate existing embeddings or indexing
