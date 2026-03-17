# PMOVES.AI Services Catalog

Comprehensive reference of all production services, ports, APIs, and integration points.

## Agent Coordination & Orchestration

### Agent Zero
- **Ports:** 8080 (API), 8081 (UI)
- **Purpose:** Control-plane agent orchestrator with embedded runtime
- **Key APIs:**
  - `GET /healthz` - Health check (supervisor + runtime + NATS status)
  - `POST /mcp/*` - MCP API for agent commands
- **NATS Topics:** Subscribes to task coordination subjects
- **Dependencies:** NATS (required), Supabase, Hi-RAG, PMOVES.YT
- **Environment:**
  - `ANTHROPIC_API_KEY` - Claude API key
  - `MCP_SERVICE_URL` - MCP endpoint configuration
  - `AGENTZERO_JETSTREAM=true` - Enable reliable delivery
- **Docker Image:** `agent0ai/agent-zero:latest`
- **Compose Profile:** `agents`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Trivy+Cosign+SBOM), `self-hosted-builds` (amd64)

### Archon
- **Ports:** 8091 (API), 3737 (UI), 8051/8052 (internal MCP)
- **Purpose:** Supabase-driven agent service with prompt/form management
- **Key APIs:**
  - `GET /healthz` - Service + Supabase connectivity
- **Dependencies:** Supabase (required), Agent Zero MCP, NATS
- **Environment:**
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Docker Image:** `coleam00/archon-server:latest`, `coleam00/archon-mcp:latest`
- **Compose Profile:** `agents`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign), `self-hosted-builds` (amd64)

### Mesh Agent
- **Ports:** None (no HTTP interface)
- **Purpose:** Distributed node announcer for multi-host orchestration
- **NATS Topics:** Publishes host announcements every 15s
- **Environment:**
  - `ANNOUNCE_SEC=15` - Announcement interval
- **Compose Profile:** `agents`
- **CI Pipeline:** `none` (no Dockerfile — uses agent-zero image or inline build)

### Channel Monitor
- **Ports:** 8097
- **Purpose:** External content watcher (YouTube, RSS feeds)
- **Key APIs:**
  - `GET /healthz` - Service health
- **Integration:** Triggers PMOVES.YT `/yt/ingest` on new content
- **Dependencies:** PMOVES.YT, Supabase
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `self-hosted-builds` (amd64)

### BoTZ MCP Gateway
- **Ports:** 2091
- **Purpose:** Multi-server MCP gateway + A2A task bridge for BoTZ orchestration
- **Key APIs:**
  - `GET /healthz` - Primary health endpoint
  - `GET /health` - Compatibility health endpoint
  - `GET /metrics` - Prometheus metrics
  - `GET /servers`, `GET /tools` - MCP server/tool catalog
  - `POST /call`, `POST /mcp`, `POST /a2a/v1/tasks` - Protected execution/task routes
- **Authentication:** JWT Bearer token validated via `SUPABASE_JWT_SECRET` (fail-closed)
- **NATS Topics:**
  - Publish: `botz.mcp.tool.executed.v1`, `botz.gateway.task.dispatched.v1`, `agent.graphiti.signed.v1`
- **Dependencies:** NATS, Supabase
- **Compose Profile:** `agents` (submodule lane)
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

## Retrieval & Knowledge Services

### Hi-RAG Gateway v2 (PREFERRED)
- **Ports:** 8086 (CPU), 8087 (GPU)
- **Purpose:** Next-gen hybrid RAG with cross-encoder reranking
- **Key APIs:**
  - `POST /hirag/query` - Query endpoint
    - Request: `{"query": "...", "top_k": 10, "rerank": true}`
    - Response: `{"results": [...], "metadata": {...}, "reranked": bool}`
  - `GET /healthz` - Service health
- **Features:**
  - Combines Qdrant (vectors) + Neo4j (graph) + Meilisearch (text)
  - Cross-encoder reranking (BAAI/bge-reranker-base CPU, Qwen GPU)
  - CHIT Geometry Bus integration
  - Supabase realtime event broadcasting
- **Dependencies:** Qdrant, Neo4j, Meilisearch, Supabase
- **Docker Image:** Custom build from `services/hi-rag-gateway-v2`
- **Compose Profile:** Default
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### Hi-RAG Gateway v1 (LEGACY)
- **Ports:** 8089 (CPU), 8187 (GPU)
- **Purpose:** Original hybrid RAG implementation
- **Status:** Use v2 for new features
- **Compose Profile:** Default
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### DeepResearch
- **Ports:** 8098 (health monitoring)
- **Purpose:** LLM-based research planner (Alibaba Tongyi)
- **NATS Topics:**
  - Subscribe: `research.deepresearch.request.v1`
  - Publish: `research.deepresearch.result.v1`
- **Key APIs:**
  - `GET /healthz` - Service health
- **Modes:**
  - OpenRouter API (default) - Cloud Tongyi model
  - Local mode - Self-hosted DeepResearch
- **Integration:** Auto-publishes results to Open Notebook
- **Environment:**
  - `OPENROUTER_API_KEY` - For cloud mode
  - `DEEPRESEARCH_LOCAL=true` - For local mode
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `integrations-ghcr` (amd64-only, Cosign), `build-images` (manual dispatch)

### SupaSerch
- **Ports:** 8099
- **Purpose:** Multimodal holographic deep research orchestrator
- **Key APIs:**
  - `GET /healthz` - Service health
  - `GET /metrics` - Prometheus metrics
- **NATS Topics:**
  - Subscribe: `supaserch.request.v1`
  - Publish: `supaserch.result.v1`
- **Features:**
  - Orchestrates DeepResearch, Agent Zero MCP tools
  - CHIT Geometry Bus for structured output
  - Queries Supabase/Qdrant/Meilisearch
- **Dependencies:** Agent Zero, DeepResearch, databases
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign+SBOM), `build-images` (manual dispatch)

### Model Registry
- **Ports:** 8111
- **Port Note:** Previously 8110, changed to 8111 to avoid conflict with gateway-agent (PR #845).
- **Purpose:** Dynamic model configuration service — central catalog for LLM/embedding model providers, mappings, and active deployments
- **Key APIs:**
  - `GET /healthz` - Service health
  - `GET /api/models` - List registered models
  - `GET /api/providers` - List model providers
  - `GET /api/deployments` - List active model deployments
- **NATS Topics:**
  - Publish: `model.registry.updated.v1` (catalog mutation notifications)
  - Subscribe: `mesh.gpu.model.loaded.v1`, `mesh.gpu.model.unloaded.v1` (syncs deployment state from GPU Orchestrator)
- **Dependencies:** Supabase (required), NATS
- **Docker Image:** Custom build from `services/model-registry`
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `self-hosted-builds` (amd64), `build-images` (manual dispatch)
- **Lifecycle:** Formerly dormant; activated in PR #787-791

### GPU Orchestrator
- **Ports:** 8200
- **Purpose:** Dynamic GPU resource management and model lifecycle controller
- **Key APIs:**
  - `GET /healthz` - Service health
  - `GET /api/v1/status` - GPU status (VRAM utilization, loaded models, temperature)
  - `GET /api/v1/models` - List models loaded on GPU
  - `GET /metrics` - Prometheus metrics
- **NATS Topics:**
  - Publish: `mesh.gpu.status.v1` (every 5s), `mesh.gpu.model.loaded.v1`, `mesh.gpu.model.unloaded.v1`, `mesh.gpu.vram.warning.v1`, `mesh.gpu.command.result.v1`
  - Subscribe: `mesh.gpu.command.v1` (model load/unload/optimize requests)
- **Features:**
  - Bidirectional NATS wiring with model-registry
  - VRAM warning rate-limited to 1/min
  - Command execution results via fire-and-forget NATS (no request-reply)
- **Dependencies:** NATS (required), NVIDIA GPU runtime
- **Docker Image:** Custom build from `services/gpu-orchestrator`
- **Compose Profile:** `gpu`
- **CI Pipeline:** `self-hosted-builds` (amd64), `build-images` (manual dispatch)
- **Note:** Only started by `make up-model-management` when NVIDIA runtime is detected
- **Lifecycle:** Formerly dormant; activated in PR #787-791

### Open Notebook (External Integration)
- **Ports:** 8503 (UI), 5055 (API)
- **Purpose:** Knowledge base / note-taking workspace
- **Compose File:** `pmoves/docker-compose.open-notebook.yml` (or `pmoves/docker-compose.external.yml` in external profile)
- **Stack:** Next.js UI + FastAPI backend + SurrealDB
- **Key Endpoints:**
  - `GET http://localhost:5055/health` - API health
  - `GET http://localhost:8503/` - UI readiness
  - `GET http://localhost:4482/api/notebook/runtime` - PMOVES Notebook Workbench runtime status
- **Access:** Via `OPEN_NOTEBOOK_API_URL` + bearer token (`OPEN_NOTEBOOK_API_TOKEN`)
- **Branded Defaults:** `OPEN_NOTEBOOK_PASSWORD` and `OPEN_NOTEBOOK_API_TOKEN` are expected to be identical in the PMOVES bundle
- **Used By:** DeepResearch, notebook-sync, PMOVES.YT sync, Agent Zero, Notebook Workbench API routes
- **Status:** External integration (upstream image default, PMOVES image override supported)
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Trivy+Cosign+SBOM), `build-images` (manual dispatch)

## Voice & Speech Services

### Flute-Gateway
- **Ports:** 8055 (HTTP), 8056 (WebSocket)
- **Purpose:** Multimodal voice communication layer with Pipecat integration
- **Key APIs:**
  - `GET /healthz` - Service health
  - `POST /v1/voice/synthesize/prosodic` - Prosodic TTS synthesis
  - `POST /v1/voice/analyze/prosodic` - Text analysis for TTS
  - `POST /v1/sessions` - Create voice session
- **Features:**
  - Pipecat pipeline for real-time audio
  - Prosodic synthesis with natural pauses/emphasis
  - WebSocket streaming for duplex communication
  - Multiple TTS backend support (VibeVoice, Ultimate-TTS)
- **Metrics:** `GET http://localhost:8055/metrics` (Prometheus)
- **Dependencies:** NATS, Ultimate-TTS-Studio (optional), FFmpeg-Whisper
- **Environment:**
  - `FLUTE_API_KEY` - API authentication
  - `ULTIMATE_TTS_URL` - Backend TTS service
  - `VIBEVOICE_URL` - Alternative TTS backend
- **Docker Image:** Custom build from `services/flute-gateway`
- **Compose Profile:** `workers`, `orchestration`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### Ultimate-TTS-Studio
- **Ports:** 7861
- **Purpose:** Multi-engine TTS with 7 engines pre-installed
- **Key APIs:**
  - `GET /gradio_api/info` - Service info and health
  - Gradio Python client for synthesis
- **Engines:**
  - KittenTTS - Fast neural TTS
  - Kokoro - High-quality Japanese/English
  - F5-TTS - Natural prosody
  - VoxCPM - Voice cloning
  - Whisper - Speech-to-text input
  - espeak-ng - Phoneme generation
  - pynini - G2P and phonetic rules
- **Features:**
  - CUDA GPU acceleration
  - Gradio web interface
  - Multiple voice styles
- **Security:** Non-root user (UID 65532)
- **Metrics:** Gradio-based (no native Prometheus /metrics endpoint)
- **Docker Image:** Custom build from `docker/ultimate-tts-studio`
- **Compose Profile:** `gpu`, `tts`
- **CI Pipeline:** `build-images` (amd64, manual dispatch only — GPU-heavy)

### Voice Relay
- **Ports:** 8121
- **Purpose:** NATS bridge relaying `agentzero.task.result.v1` → `voice.agent.response.v1` for voice-tagged tasks
- **Key APIs:**
  - `GET /healthz` - Service health (includes NATS connection status)
  - `GET /metrics` - Prometheus metrics
- **NATS Topics:**
  - Subscribe: `agentzero.task.result.v1` (configurable via `VOICE_RELAY_INPUT_SUBJECT`)
  - Publish: `voice.agent.response.v1` (configurable via `VOICE_RELAY_OUTPUT_SUBJECT`)
- **Filter:** Only relays messages where `meta.voice_mode` is truthy
- **Metrics:**
  - `voice_relay_messages_relayed_total` - Successfully relayed messages
  - `voice_relay_messages_filtered_total` - Messages filtered (no voice_mode)
  - `voice_relay_errors_total` - Processing errors
- **Security:** Non-root user (UID 65532), read-only filesystem, tmpfs /tmp
- **Dependencies:** NATS (required)
- **Docker Image:** Custom build from `services/voice-relay`
- **Compose Profile:** `cast`, `media`

## Media Ingestion & Processing

### PMOVES.YT
- **Ports:** 8077
- **Purpose:** YouTube ingestion and transcription service
- **Key APIs:**
  - `POST /yt/ingest` - Trigger ingestion
    - Request: `{"url": "youtube.com/watch?v=...", "options": {}}`
  - `GET /healthz` - Service health
- **Features:**
  - Downloads videos to MinIO (`assets` bucket)
  - Retrieves transcripts via bgutil/YouTube API
  - Publishes NATS events when complete
- **NATS Topics:**
  - Publish: `ingest.transcript.ready.v1`
- **Dependencies:** MinIO, Supabase, NATS
- **Compose Profile:** `yt`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign+SBOM), `self-hosted-builds` (amd64)

### FFmpeg-Whisper
- **Ports:** 8078
- **Purpose:** Media transcription (OpenAI Whisper)
- **Key APIs:**
  - `GET /healthz` - Service health
- **Features:**
  - Faster-Whisper backend
  - GPU acceleration (CUDA)
  - Model: `small` (configurable)
- **Storage:** Reads/writes MinIO
- **Compose Profile:** `gpu`
- **CI Pipeline:** `self-hosted-builds` (amd64)

### Media-Video Analyzer
- **Ports:** 8079
- **Purpose:** Object/frame analysis with YOLOv8
- **Key APIs:**
  - `GET /healthz` - Service health
- **Features:**
  - YOLOv8 object detection (yolov8n.pt)
  - Frame sampling: every 5th frame
  - Confidence threshold: 0.25
- **Output:** Supabase
- **Compose Profile:** `gpu`
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Media-Audio Analyzer
- **Ports:** 8082
- **Purpose:** Audio emotion/speaker detection
- **Model:** `superb/hubert-large-superb-er`
- **Compose Profile:** `gpu`
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Extract Worker
- **Ports:** 8083
- **Purpose:** Text embedding and indexing service
- **Key APIs:**
  - `POST /ingest` - Index text content
  - `GET /healthz` - Service health
- **Features:**
  - Indexes to Qdrant (vectors) + Meilisearch (full-text)
  - Model: `all-MiniLM-L6-v2` (sentence-transformers)
  - Stores metadata in Supabase
- **Dependencies:** Qdrant, Meilisearch, Supabase
- **Compose Profile:** `workers`
- **CI Pipeline:** `self-hosted-builds` (amd64)

### PDF Ingest
- **Ports:** 8092
- **Purpose:** PDF document ingestion orchestrator
- **Features:** Processes PDFs from MinIO, sends to extract-worker
- **NATS Topics:**
  - Publish: `ingest.file.added.v1`
- **Compose Profile:** `workers`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### LangExtract
- **Ports:** 8084
- **Purpose:** Language detection and NLP preprocessing
- **Used By:** Notebook sync, text analysis pipelines
- **Compose Profile:** `workers`
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Notebook Sync
- **Ports:** 8095
- **Purpose:** SurrealDB Open Notebook synchronizer
- **Features:**
  - Polling interval: 300s (configurable)
  - Calls LangExtract + Extract Worker for indexing
- **Dependencies:** Open Notebook, LangExtract, Extract Worker
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Transcribe Backend
- **Ports:** 8074
- **Purpose:** Text transcription service (PMOVES-transcribe-and-fetch submodule)
- **Key APIs:**
  - `GET /healthz` - Service health
- **Dependencies:** Supabase, NATS
- **Submodule:** `PMOVES-transcribe-and-fetch`
- **Compose Profile:** `workers`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)
- **Lifecycle:** Formerly dormant; activated in PR #787-791

## Utility & Integration Services

### Presign
- **Ports:** 8088
- **Purpose:** MinIO URL presigner for short-lived download URLs
- **Key APIs:**
  - `POST /presign` - Generate presigned URL
- **Security:** Requires `PRESIGN_SHARED_SECRET`
- **Allowed Buckets:** `assets`, `outputs` (configurable)
- **Compose Profile:** Default
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Render Webhook
- **Ports:** 8085
- **Purpose:** ComfyUI render callback handler
- **Security:** Requires `RENDER_WEBHOOK_SHARED_SECRET`
- **Integration:** Writes to Supabase, stores to MinIO
- **Compose Profile:** Default
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

### Publisher-Discord
- **Ports:** 8094
- **Purpose:** Discord notification bot
- **NATS Topics (Subscribe):**
  - `ingest.file.added.v1`
  - `ingest.transcript.ready.v1`
  - `ingest.summary.ready.v1`
  - `ingest.chapters.ready.v1`
- **Environment:**
  - `DISCORD_WEBHOOK_URL` - Webhook for notifications
- **Compose Profile:** Default
- **CI Pipeline:** `self-hosted-builds` (amd64)

### Jellyfin Bridge
- **Ports:** 8093
- **Purpose:** Jellyfin metadata webhook and helper
- **Features:** Syncs Jellyfin events to Supabase
- **Compose Profile:** `health` (optional)
- **CI Pipeline:** `local-build-only` (compose `build:` directive)

## Health & Wellness Services

### Health (wger)
- **Ports:** 8000 (`WGER_PORT`, compose: main + external)
- **Purpose:** Fitness tracking and body metrics (wger self-hosted)
- **Framework:** Django / wger
- **Key APIs:**
  - `GET /api/v2/workout/` - List workouts
  - `GET /api/v2/weightentry/` - Body weight entries
  - `POST /api/v2/workoutsession/` - Log workout session
- **NATS Topics (Publish, subjects defined):**
  - `health.metrics.updated.v1`
  - `health.workout.completed.v1`
  - `health.weekly.summary.v1`
- **Health Endpoint:** `GET /healthz/` (3-tier: healthy/degraded/unhealthy)
- **Metrics:** `GET /metrics/` (Prometheus, gated by `EXPOSE_PROMETHEUS_METRICS`)
- **Maturity:** Stage 1 — healthz, metrics, NATS wiring, and Docker hardening complete; CHIT integration pending
- **TAC Tree:** `pmoves/docs/TAC/TAC_HEALTH.md`
- **Submodule:** `Pmoves-Health-wger`
- **Compose Profile:** `health`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign+SBOM), `build-images` (manual dispatch)

### Wealth (Firefly III)
- **Ports:** TBD (default Laravel 8080)
- **Purpose:** Personal finance management (Firefly III self-hosted)
- **Framework:** Laravel / Firefly III
- **Key APIs (planned):**
  - `GET /api/v1/transactions` - List transactions
  - `GET /api/v1/budgets` - Budget tracking
  - `POST /api/v1/transactions` - Create transaction
- **NATS Topics (Publish, planned):**
  - `finance.transactions.ingested.v1`
  - `finance.budget.alert.v1`
  - `finance.monthly.summary.v1`
- **Health Endpoint:** Planned (`/healthz`)
- **Metrics:** Planned (`/metrics`)
- **Maturity:** Pre-stage — no healthz, metrics, NATS, CHIT, or Docker hardening yet
- **TAC Tree:** `pmoves/docs/TAC/TAC_WEALTH.md`
- **Submodule:** `PMOVES-Wealth`
- **Compose Profile:** `wealth`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

## Remote Access Services

### Headscale (Self-hosted Tailscale Control Server)
- **Ports:** 8096 (API), 9091 (metrics)
- **Purpose:** Self-hosted Tailscale control server for VPN mesh networking
- **Features:**
  - VPN node management
  - Authentication key creation
  - Route advertisement
  - ACL policy enforcement
- **Key APIs:**
  - `GET /healthz` - Service health
  - `GET /metrics` - Prometheus metrics
  - `POST /api/v1/apikey` - Create auth keys
  - `GET /api/v1/machines` - List connected nodes
- **Configuration:** `pmoves/config/headscale/config.yaml`, `acl.yaml`
- **Compose Profile:** `remote`
- **CI Pipeline:** `vendor` (upstream headscale image)

### RustDesk Relay (Self-hosted Remote Desktop)
- **Ports:** 21115-21119 (various protocols)
- **Purpose:** Self-hosted remote desktop relay server
- **Components:**
  - `hbbs` (ports 21115, 21116, 21118) - ID/Rendezvous server
  - `hbbr` (ports 21117, 21119) - Relay server
- **Features:** P2P direct connections, relay fallback, WebRTC support
- **Compose Profile:** `remote`
- **CI Pipeline:** `vendor` (upstream rustdesk image)

### BoTZ VPN MCP Server
- **Port:** 8110
- **Port Note:** No longer collides with Model Registry (moved to 8111 in PR #845). Port 8110 is now exclusive to BoTZ VPN MCP.
- **Purpose:** MCP server exposing VPN and remote desktop tools
- **Transport:** SSE
- **MCP Tools:**
  - `vpn_list_nodes` - List connected VPN nodes
  - `vpn_create_auth_key` - Create VPN authentication keys
  - `vpn_advertise_route` - Advertise VPN routes
  - `remote_start_session` - Start remote desktop session
  - `remote_end_session` - End remote desktop session
  - `remote_list_sessions` - List active sessions
- **Integration:**
  - Headscale API for VPN management
  - Supabase for session logging
  - NATS for event coordination
- **Compose Profile:** `vpn`, `remote` (in PMOVES-BoTZ)
- **Health:** `GET http://localhost:8110/health`
- **CI Pipeline:** `build-images` (amd64, manual dispatch — via PMOVES-BoTZ submodule)

### Cipher Memory API (cipher-api)
- **Port:** 8096 (remapped from internal 3000 to avoid Grafana conflict)
- **Purpose:** Knowledge-graph memory service for Claude Code and agents
- **Backend:** Node.js + Neo4j
- **API Endpoints:**
  - `POST /api/memory` - Store memory with embeddings
  - `GET /api/memory/search?q=...` - Semantic memory search
  - `GET /api/memory/:id` - Retrieve specific memory
  - `DELETE /api/memory/:id` - Delete memory
  - `GET /health` - Health check
- **MCP Bridge:** `pmoves-cipher-mcp/` (stdio transport via `.claude/mcp.json`)
- **MCP Tools:**
  - `pmoves_cipher_store` - Store knowledge with category/tags
  - `pmoves_cipher_search` - Semantic search over memories
  - `pmoves_cipher_store_reasoning` - Store reasoning traces
  - `pmoves_cipher_reasoning_patterns` - Search past reasoning
- **Resilience Role:** Stores `agent_plan`, `agent_checkpoint`, and `agent_completion` snapshots for all agents. See `pmoves/docs/AGENTS/AGENT_RESILIENCE_PATTERNS.md` for checkpoint protocol.
- **Dependencies:** Neo4j (shared), NATS
- **Compose Profile:** `agents`
- **CI Pipeline:** `local-build-only` (compose `build:` directive)
- **Health:** `GET http://localhost:8096/health`

## CHIT & Geometry Services

### Tokenism Simulator
- **Ports:** 8103 (host) → 8100 (internal)
- **Purpose:** Economic simulation with geometric attribution (CGP v0.2)
- **Key APIs:**
  - `GET /healthz` - Service health
- **NATS Topics:**
  - Publish: `tokenism.cgp.ready.v1`, `tokenism.simulation.result.v1`, `tokenism.calibration.result.v1`
- **Features:**
  - CHIT-enabled (`CHIT_ENABLED=true`)
  - Geometry Bus integration via NATS
  - TensorZero LLM routing
  - Agent Zero MCP integration
- **CHIT Level:** Full
- **Dependencies:** NATS (required), TensorZero, Supabase, Agent Zero
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-tokenism:pmoves-latest`
- **Compose Profile:** `agents`, `orchestration`, `botz`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### Evo Controller
- **Ports:** 8113
- **Purpose:** EvoSwarm evolutionary optimization controller
- **Key APIs:**
  - Polling-based optimization (no HTTP health endpoint defined)
- **NATS Topics:** `evoswarm.*`
- **Features:**
  - CHIT signature verification (`CHIT_REQUIRE_SIGNATURE=true`)
  - CHIT anchor decryption (`CHIT_DECRYPT_ANCHORS=true`)
  - Configurable poll interval (`EVOSWARM_POLL_SECONDS=300`)
- **CHIT Level:** Full
- **Dependencies:** Supabase, NATS
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-evo-controller:latest`
- **Compose Profile:** `orchestration`
- **CI Pipeline:** `build-images` (amd64, manual dispatch)

### A2UI NATS Bridge
- **Ports:** 9224
- **Purpose:** WebSocket bridge for A2UI frontend ↔ NATS
- **Key APIs:**
  - `GET /healthz` - Service health
- **NATS Topics:**
  - Subscribe: `a2ui.render.v1`, `geometry.>`
- **Features:**
  - WebSocket relay for real-time UI updates
  - Geometry Bus wildcard subscription
- **CHIT Level:** Partial (relay only)
- **Dependencies:** NATS (required, service_healthy + nats-init)
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-a2ui-nats-bridge:pmoves-latest`
- **Compose Profile:** `agents`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign), `build-images` (manual dispatch)

### Session Context Worker
- **Ports:** 8102 (host) → 8100 (internal)
- **Purpose:** Session-scoped context management worker
- **Features:**
  - Manages session context for agent interactions
  - Forwards to Hi-RAG v2 for ingestion
- **Dependencies:** Hi-RAG v2 (required), NATS
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-session-context-worker:latest`
- **Compose Profile:** `workers`
- **CI Pipeline:** `integrations-ghcr` (multi-arch, Cosign), `build-images` (manual dispatch)

## Monitoring Stack

### Prometheus
- **Ports:** 9090
- **Purpose:** Metrics collection and alerting
- **Features:**
  - Scrapes `/metrics` from all services
  - Health endpoint monitoring via blackbox exporter
- **Query API:** `GET http://localhost:9090/api/v1/query?query=<promql>`
- **Compose Profile:** `monitoring`
- **CI Pipeline:** `vendor` (upstream prom/prometheus image)

### Grafana
- **Ports:** 3000
- **Purpose:** Dashboard visualization
- **Datasources:** Prometheus, Loki
- **Dashboards:** "Services Overview" (pre-configured)
- **Compose Profile:** `monitoring`
- **CI Pipeline:** `vendor` (upstream grafana/grafana image)
- **⚠ Port 3000 Conflict Note:** Several services default to port 3000 via env vars:
  `supabase-postgrest` (`SUPABASE_POSTGREST_PORT`), Invidious (`INVIDIOUS_PORT`),
  VibeVoice (`VIBEVOICE_HOST_PORT`). When Grafana is active, these services **must**
  override their port env vars to avoid binding conflicts. Grafana is the canonical
  owner of host port 3000.

### Loki
- **Ports:** 3100
- **Purpose:** Log aggregation
- **Used With:** Promtail (log collector)
- **All services:** Configured with Loki labels for centralized logging
- **Compose Profile:** `monitoring`
- **CI Pipeline:** `vendor` (upstream grafana/loki image)

### cAdvisor
- **Ports:** 8080 (conflicts with Agent Zero, use different port)
- **Purpose:** Container metrics for Prometheus
- **Compose Profile:** `monitoring`
- **CI Pipeline:** `vendor` (upstream gcr.io/cadvisor image)

## Data Storage

### NATS
- **Ports:** 4222 (TCP), 9222 (WebSocket standalone/DoX), 9223 (WebSocket docked)
- **Purpose:** Message bus for agent coordination
- **Version:** 2.10-alpine
- **Features:** JetStream enabled for persistence
- **Auth:** `nats://nats:pmoves@nats:4222` (always use authenticated URL)
- **WebSocket:** DoX standalone uses 9222, docker-compose docked mode uses 9223
- **Key Subjects:** See `.claude/context/nats-subjects.md`
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream nats:2.10-alpine image)

### Supabase
- **Ports:** 3010 (PostgREST), 5432 (Postgres)
- **Purpose:** Primary database with pgvector
- **Schema:** `pmoves_core`, Archon prompts
- **Features:** Postgres + PostgREST + pgvector + realtime
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream supabase/postgres image)

### Qdrant
- **Ports:** 6333
- **Purpose:** Vector embeddings for semantic search
- **Version:** v1.10.0
- **Collection:** `pmoves_chunks`
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream qdrant/qdrant image)

### Neo4j
- **Ports:** 7474 (HTTP), 7687 (Bolt)
- **Purpose:** Knowledge graph storage
- **Version:** 5.22
- **Features:** Entity relationships, graph traversal
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream neo4j image)

### Meilisearch
- **Ports:** 7700
- **Purpose:** Full-text keyword search
- **Version:** v1.8
- **Features:** Typo-tolerant, substring search
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream getmeili/meilisearch image)

### MinIO
- **Ports:** 9000 (API), 9001 (Console)
- **Purpose:** S3-compatible object storage
- **Buckets:** `assets`, `outputs`
- **Stores:** Videos, audio, images, analysis results
- **Compose Profile:** Default (always required)
- **CI Pipeline:** `vendor` (upstream minio/minio image)

## Quick Reference

### All Service Health Endpoints
```bash
# Agent Coordination
http://localhost:8080/healthz  # Agent Zero
http://localhost:8091/healthz  # Archon
http://localhost:8097/healthz  # Channel Monitor

# Model Management
http://localhost:8111/healthz  # Model Registry
http://localhost:8200/healthz  # GPU Orchestrator (GPU only)

# Retrieval & Knowledge
http://localhost:8086/healthz  # Hi-RAG v2 CPU
http://localhost:8087/healthz  # Hi-RAG v2 GPU
http://localhost:8099/healthz  # SupaSerch
http://localhost:8098/healthz  # DeepResearch

# Voice & Speech
http://localhost:8055/healthz  # Flute-Gateway
http://localhost:8055/metrics  # Flute-Gateway (Prometheus)
http://localhost:7861/gradio_api/info  # Ultimate-TTS-Studio
http://localhost:8121/healthz  # Voice Relay
http://localhost:8121/metrics  # Voice Relay (Prometheus)
http://localhost:8060/healthz  # Cast-TTS-Gateway

# Media Processing
http://localhost:8077/healthz  # PMOVES.YT
http://localhost:8078/healthz  # FFmpeg-Whisper
http://localhost:8079/healthz  # Media-Video
http://localhost:8082/healthz  # Media-Audio
http://localhost:8083/healthz  # Extract Worker
http://localhost:8084/healthz  # LangExtract
http://localhost:8092/healthz  # PDF Ingest
http://localhost:8095/healthz  # Notebook Sync
http://localhost:8074/healthz  # Transcribe Backend

# CHIT & Geometry
http://localhost:8103/healthz  # Tokenism Simulator
http://localhost:9224/healthz  # A2UI NATS Bridge

# Utilities
http://localhost:8088/healthz  # Presign
http://localhost:8085/healthz  # Render Webhook
http://localhost:8093/healthz  # Jellyfin Bridge
http://localhost:8094/healthz  # Publisher-Discord
http://localhost:5055/health   # Open Notebook API
```

### All Metrics Endpoints
Most services expose Prometheus metrics at `/metrics`:
```bash
http://localhost:8080/metrics  # Agent Zero
http://localhost:8099/metrics  # SupaSerch
# ... (most services follow this pattern)
```
