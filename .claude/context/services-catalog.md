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

### Mesh Agent
- **Ports:** None (no HTTP interface)
- **Purpose:** Distributed node announcer for multi-host orchestration
- **NATS Topics:** Publishes host announcements every 15s
- **Environment:**
  - `ANNOUNCE_SEC=15` - Announcement interval
- **Compose Profile:** `agents`

### Channel Monitor
- **Ports:** 8097
- **Purpose:** External content watcher (YouTube, RSS feeds)
- **Key APIs:**
  - `GET /healthz` - Service health
- **Integration:** Triggers PMOVES.YT `/yt/ingest` on new content
- **Dependencies:** PMOVES.YT, Supabase
- **Compose Profile:** `orchestration`

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

### Hi-RAG Gateway v1 (LEGACY)
- **Ports:** 8089 (CPU), 8090 (GPU)
- **Purpose:** Original hybrid RAG implementation
- **Status:** Use v2 for new features
- **Compose Profile:** Default

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

### Open Notebook (External Integration)
- **Purpose:** Knowledge base / note-taking (SurrealDB-backed)
- **Access:** Via `OPEN_NOTEBOOK_API_URL` + API token
- **Used By:** DeepResearch, notebook-sync
- **Status:** External submodule integration

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

### Media-Audio Analyzer
- **Ports:** 8082
- **Purpose:** Audio emotion/speaker detection
- **Model:** `superb/hubert-large-superb-er`
- **Compose Profile:** `gpu`

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

### PDF Ingest
- **Ports:** 8092
- **Purpose:** PDF document ingestion orchestrator
- **Features:** Processes PDFs from MinIO, sends to extract-worker
- **NATS Topics:**
  - Publish: `ingest.file.added.v1`
- **Compose Profile:** `workers`

### LangExtract
- **Ports:** 8084
- **Purpose:** Language detection and NLP preprocessing
- **Used By:** Notebook sync, text analysis pipelines
- **Compose Profile:** `workers`

### Notebook Sync
- **Ports:** 8095
- **Purpose:** SurrealDB Open Notebook synchronizer
- **Features:**
  - Polling interval: 300s (configurable)
  - Calls LangExtract + Extract Worker for indexing
- **Dependencies:** Open Notebook, LangExtract, Extract Worker
- **Compose Profile:** `orchestration`

## GPU & Compute Services

### GPU Orchestrator
- **Ports:** 8200
- **Purpose:** VRAM management, model lifecycle, and GPU priority queue
- **Key APIs:**
  - `GET /healthz` - Service health
  - `GET /models` - List loaded models
  - `POST /models/load` - Load model to GPU
  - `POST /models/unload` - Unload model from GPU
- **Features:**
  - Multi-model VRAM allocation
  - Priority queue for GPU compute requests
  - Automatic model eviction on VRAM pressure
  - Integration with Ollama, vLLM, TTS backends
- **Environment:**
  - `GPU_ORCHESTRATOR_MAX_MODELS=3` - Max concurrent models
  - `GPU_ORCHESTRATOR_VRAM_THRESHOLD=0.9` - Eviction threshold
  - `OLLAMA_BASE_URL`, `VLLM_BASE_URL`, `TTS_BASE_URL`
- **Dependencies:** NATS (optional)
- **Compose Profile:** `gpu`
- **Env Tier:** `env-tier-api`

### E2B Runner (pmz-e2b-runner)
- **Ports:** 7071
- **Purpose:** Isolated code execution sandbox (self-hosted)
- **Key APIs:**
  - `GET /health` - Service health
  - `POST /execute` - Execute code in sandbox
- **Features:**
  - Secure code execution in isolated containers
  - Python, JavaScript, shell code support
  - MCP gateway integration for tool access
  - GPU support on ai-lab runner (optional)
- **Deployment:**
  - **ai-lab:** Self-hosted with GPU access
  - **VPS/proxmox:** CPU-only mode
- **Environment:**
  - `E2B_API_KEY` - E2B API key (if using cloud fallback)
  - `MCP_GATEWAY_URL` - Docker MCP gateway endpoint
- **Compose Profile:** `workers`, `botz`

## Utility & Integration Services

### Presign
- **Ports:** 8088
- **Purpose:** MinIO URL presigner for short-lived download URLs
- **Key APIs:**
  - `POST /presign` - Generate presigned URL
- **Security:** Requires `PRESIGN_SHARED_SECRET`
- **Allowed Buckets:** `assets`, `outputs` (configurable)
- **Compose Profile:** Default

### Render Webhook
- **Ports:** 8085
- **Purpose:** ComfyUI render callback handler
- **Security:** Requires `RENDER_WEBHOOK_SHARED_SECRET`
- **Integration:** Writes to Supabase, stores to MinIO
- **Compose Profile:** Default

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

### Jellyfin Bridge
- **Ports:** 8093
- **Purpose:** Jellyfin metadata webhook and helper
- **Features:** Syncs Jellyfin events to Supabase
- **Compose Profile:** `health` (optional)

## Monitoring Stack

### Prometheus
- **Ports:** 9090
- **Purpose:** Metrics collection and alerting
- **Features:**
  - Scrapes `/metrics` from all services
  - Health endpoint monitoring via blackbox exporter
- **Query API:** `GET http://localhost:9090/api/v1/query?query=<promql>`
- **Compose Profile:** `monitoring`

### Grafana
- **Ports:** 3000
- **Purpose:** Dashboard visualization
- **Datasources:** Prometheus, Loki
- **Dashboards:** "Services Overview" (pre-configured)
- **Compose Profile:** `monitoring`

### Loki
- **Ports:** 3100
- **Purpose:** Log aggregation
- **Used With:** Promtail (log collector)
- **All services:** Configured with Loki labels for centralized logging
- **Compose Profile:** `monitoring`

### cAdvisor
- **Ports:** 8080 (conflicts with Agent Zero, use different port)
- **Purpose:** Container metrics for Prometheus
- **Compose Profile:** `monitoring`

## Data Storage

### NATS
- **Ports:** 4222
- **Purpose:** Message bus for agent coordination
- **Version:** 2.10-alpine
- **Features:** JetStream enabled for persistence
- **Key Subjects:** See `.claude/context/nats-subjects.md`
- **Compose Profile:** Default (always required)

### Supabase
- **Ports:** 3010 (PostgREST), 5432 (Postgres)
- **Purpose:** Primary database with pgvector
- **Schema:** `pmoves_core`, Archon prompts
- **Features:** Postgres + PostgREST + pgvector + realtime
- **Compose Profile:** Default (always required)

### Qdrant
- **Ports:** 6333
- **Purpose:** Vector embeddings for semantic search
- **Version:** v1.10.0
- **Collection:** `pmoves_chunks`
- **Compose Profile:** Default (always required)

### Neo4j
- **Ports:** 7474 (HTTP), 7687 (Bolt)
- **Purpose:** Knowledge graph storage
- **Version:** 5.22
- **Features:** Entity relationships, graph traversal
- **Compose Profile:** Default (always required)

### Meilisearch
- **Ports:** 7700
- **Purpose:** Full-text keyword search
- **Version:** v1.8
- **Features:** Typo-tolerant, substring search
- **Compose Profile:** Default (always required)

### MinIO
- **Ports:** 9000 (API), 9001 (Console)
- **Purpose:** S3-compatible object storage
- **Buckets:** `assets`, `outputs`
- **Stores:** Videos, audio, images, analysis results
- **Compose Profile:** Default (always required)

## External Integrations (Optional)

### Firefly III
- **Ports:** 8080 (internal only - not published to host)
- **Container:** `cataclysm-firefly`
- **Purpose:** Personal finance management and budgeting
- **Key APIs:**
  - `GET /api/v1/about` - Version and instance info
  - `GET /api/v1/accounts` - List accounts
  - `GET /api/v1/transactions` - List transactions
- **Authentication:** OAuth2 Personal Access Token (Bearer token)
- **Dependencies:** Supabase (via `finance_*` tables)
- **Related Tables:**
  - `finance_accounts` - Account records
  - `finance_budgets` - Budget tracking
  - `finance_transactions` - Transaction history
- **n8n Workflows:** `pmoves/integrations/firefly-iii/*.json`
- **Documentation:** https://docs.firefly-iii.org/firefly-iii/api
- **Note:** Internal service, access via Docker network or reverse proxy

### wger (Health Tracking)
- **Container:** `cataclysm-wger`
- **Purpose:** Fitness and workout tracking
- **Related Tables:**
  - `health_nutrition` - Nutrition logs
  - `health_weight` - Weight tracking
  - `health_workouts` - Workout records
- **n8n Workflows:** `pmoves/integrations/health-wger/*.json`

### Jellyfin
- **Container:** `cataclysm-jellyfin`
- **Purpose:** Media server and library management
- **Integration:** `pmoves-jellyfin-bridge` (port 8093) syncs events to Supabase
- **Related Submodules:** `PMOVES-Jellyfin`, `Pmoves-Jellyfin-AI-Media-Stack`

## Token Economy & Agent UI (Added 2025-12-30)

### Tokenism Simulator
- **Ports:** 8103 (API)
- **Purpose:** Token economy simulation with business model validation powered by EVO swarm intelligence
- **Key APIs:**
  - `GET /healthz` - Health check
  - `GET /metrics` - Prometheus metrics
  - `POST /api/v1/simulate` - Run simulation with scenario parameters
  - `POST /api/v1/simulate/async` - Queue async simulation
  - `GET /api/v1/scenarios` - List available scenarios (optimistic, baseline, pessimistic, stress_test)
  - `GET /api/v1/contracts` - List contract types (GroToken, FoodUSD, GroupPurchase, GroVault, CoopGovernor)
  - `GET /api/v1/simulations/{id}/geometry` - Get CHIT geometry data
- **CHIT/Geometry:**
  - Publishes to `tokenism.cgp.ready.v1` - Geometry packets for Poincaré disk visualization
  - Hyperbolic wealth distribution visualization via A2UI
- **Metrics:**
  - `tokenism_simulation_requests_total{scenario, status}` - Counter for all simulations
  - `tokenism_simulation_duration_seconds{scenario}` - Histogram for latency
- **Grafana Dashboard:** tokenism-simulator
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-tokenism-simulator:pmoves-latest`
- **Compose Profile:** `orchestration`
- **Related Submodule:** `PMOVES-ToKenism-Multi`

### A2UI NATS Bridge
- **Ports:** 9224 (API), 9225 (WebSocket agents), 9226 (WebSocket clients)
- **Purpose:** Bridges Google A2UI (Agent-to-User Interface) events to PMOVES NATS geometry bus
- **Key APIs:**
  - `GET /healthz` - Health check with active surfaces
  - `GET /metrics` - Prometheus metrics
  - `POST /api/v1/a2ui` - Accept A2UI JSON events
  - `POST /api/v1/action` - Handle user actions from UI
  - `POST /api/v1/simulate` - Simulate A2UI event for testing
  - `WS /ws/a2ui` - WebSocket for A2UI agents (JSONL format)
  - `WS /ws/client` - WebSocket for PMOVES UI subscribers
- **NATS Subjects:**
  - Publishes to: `a2ui.render.v1`, `a2ui.>`
  - Subscribes to: `geometry.>` (bidirectional)
- **A2UI Format (v0.9):**
  - `createSurface` / `beginRendering` - Initialize UI surface
  - `updateComponents` / `surfaceUpdate` - Add/update UI components
  - `updateDataModel` / `dataModelUpdate` - Update data bindings
  - `userAction` - Forward user interactions to agents
- **Metrics:**
  - `a2ui_events_published_total{event_type}` - Events published to NATS
  - `a2ui_events_received_total` - Events from A2UI agents
  - `a2ui_geometry_events_total` - Geometry events from NATS
  - `a2ui_active_websockets` - Active WebSocket connections
  - `a2ui_nats_connected` - NATS connection status (1=connected)
- **Docker Image:** `ghcr.io/powerfulmoves/pmoves-a2ui-nats-bridge:pmoves-latest`
- **Compose Profile:** `agents`, `orchestration`
- **Related Submodule:** `research/A2UI` (Google A2UI repository)

## Quick Reference

### All Service Health Endpoints
```bash
# Agent Coordination
http://localhost:8080/healthz  # Agent Zero
http://localhost:8091/healthz  # Archon
http://localhost:8097/healthz  # Channel Monitor

# Token Economy & Agent UI
http://localhost:8103/healthz  # Tokenism Simulator
http://localhost:8103/metrics  # Tokenism Simulator (Prometheus)
http://localhost:9224/healthz  # A2UI NATS Bridge

# Retrieval & Knowledge
http://localhost:8086/healthz  # Hi-RAG v2 CPU
http://localhost:8087/healthz  # Hi-RAG v2 GPU
http://localhost:8099/healthz  # SupaSerch
http://localhost:8098/healthz  # DeepResearch

# Voice & Speech
http://localhost:8055/healthz  # Flute-Gateway
http://localhost:8055/metrics  # Flute-Gateway (Prometheus)
http://localhost:7861/gradio_api/info  # Ultimate-TTS-Studio

# Media Processing
http://localhost:8077/healthz  # PMOVES.YT
http://localhost:8078/healthz  # FFmpeg-Whisper
http://localhost:8079/healthz  # Media-Video
http://localhost:8082/healthz  # Media-Audio
http://localhost:8083/healthz  # Extract Worker
http://localhost:8084/healthz  # LangExtract
http://localhost:8092/healthz  # PDF Ingest
http://localhost:8095/healthz  # Notebook Sync

# Utilities
http://localhost:8088/healthz  # Presign
http://localhost:8085/healthz  # Render Webhook
http://localhost:8093/healthz  # Jellyfin Bridge
http://localhost:8094/healthz  # Publisher-Discord
```

### All Metrics Endpoints
Most services expose Prometheus metrics at `/metrics`:
```bash
http://localhost:8080/metrics  # Agent Zero
http://localhost:8099/metrics  # SupaSerch
# ... (most services follow this pattern)
```
