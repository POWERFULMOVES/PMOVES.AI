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

## Quick Reference

### All Service Health Endpoints
```bash
# Agent Coordination
http://localhost:8080/healthz  # Agent Zero
http://localhost:8091/healthz  # Archon
http://localhost:8097/healthz  # Channel Monitor

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
