# PMOVES Complete Architecture Map

_Last Updated: 2025-10-20 (Generated from comprehensive codebase + planning docs review)_

## Executive Summary

PMOVES is a **distributed multi-agent orchestration mesh** for autonomous self-improvement, research, and complex software engineering. The system features 35+ microservices across 6 deployment profiles, coordinated by **Agent Zero** as the primary orchestrator. Services communicate via **REST APIs**, **NATS JetStream**, **Supabase Realtime websockets**, **MCP (Model Context Protocol)**, and **webhooks**. Recent integrations add Open Notebook for research capture, Wger and Firefly III for health/finance telemetry, and Jellyfin bridge services for media enrichment.

**Current Milestone**: **M2 - Creator & Publishing** (Supabase → Agent Zero → Discord automation loop)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Complete Service Inventory](#complete-service-inventory)
3. [Docker Compose Profiles](#docker-compose-profiles)
4. [Agent Zero: Primary Orchestrator](#agent-zero-primary-orchestrator)
5. [Event-Driven Architecture (NATS)](#event-driven-architecture-nats)
6. [MCP Ecosystem](#mcp-ecosystem)
7. [Data Layer](#data-layer)
8. [Service Communication Patterns](#service-communication-patterns)
9. [M2 Automation Architecture](#m2-automation-architecture)
10. [PMOVES.yt MCP Integration Strategy](#pmovesyt-mcp-integration-strategy)

---

## System Overview

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: User Interface & Interaction                       │
│  - Crush CLI, Codex VM, Open Notebook UI, domain apps (Firefly, Wger, Jellyfin) │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Orchestration & Decision Making                    │
│  - Agent Zero (Primary), n8n (MCP Hub), Archon (MCP Server)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Processing & Analysis Workers                      │
│  - Hi-RAG gateways, LangExtract, Media Video/Audio, PMOVES.yt│
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Data & Persistence                                 │
│  - Supabase + Realtime, Qdrant, Neo4j, MinIO, MeiliSearch    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Event-Driven**: NATS JetStream for async coordination (40+ topic schemas in `contracts/topics.json`)
2. **MCP-First Integration**: Agent Zero, Archon, and n8n expose MCP tools for AI clients (Crush, Codex)
3. **Unified Database**: Supabase (Postgres + pgvector) as single source of truth
4. **Profile-Based Deployment**: Services grouped into `data`, `workers`, `orchestration`, `agents`, `gateway` profiles
5. **Hierarchical RAG**: Hi-RAG Gateway v2 with rerankers + Qdrant vector store + MeiliSearch full-text

---

## Complete Service Inventory

### Agent Layer (Profile: `agents`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **agent-zero** | 8080 | Primary orchestrator. Creates subordinate agents, makes decisions, persistent memory. Exposes MCP commands via HTTP. | REST, NATS pub/sub, MCP HTTP bridge |
| **archon** | 8091 (API)<br>8051 (MCP)<br>8052 (Workers) | Knowledge & task management backbone. MCP server with 10+ tools for RAG queries, task CRUD, web crawling. | REST, MCP HTTP, NATS (subscribes to `ingest.*`, `archon.crawl.request`) |
| **mesh-agent** | - | Multi-agent coordination (lightweight wrapper for agent mesh logic) | NATS |
| **agents/** | - | Subordinate agent spawning logic (used by Agent Zero) | Internal API |

### Orchestration Layer (Profile: `orchestration`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **n8n** | 5678 | Workflow automation & **MCP Hub**. Hosts approval poller, echo publisher, and future YouTube RAG workflows. | REST webhooks, Supabase PostgREST, Agent Zero HTTP, Discord webhooks |
| **gateway/** | 8086 (v2 default & legacy) / 8087 (v2 GPU) | Entry point for external requests (if used as API gateway) | REST |
| **publisher** | 8092 | Publishes approved content to Jellyfin, emits `content.published.v1` events | REST, NATS pub, Jellyfin API |
| **publisher-discord** | 8094 | Consumes `content.published.v1` events, posts rich embeds to Discord | NATS sub, Discord webhooks |
| **jellyfin-bridge** | 8093 | Links Supabase assets to Jellyfin library items. Exposes `/map-by-title`, `/link`, `/search`, `/playback-url` | REST, Jellyfin API |

### Processing Workers (Profile: `workers`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **extract-worker** | 8083 | Ingests chunks from LangExtract → Qdrant, MeiliSearch, Supabase | REST, Qdrant gRPC, MeiliSearch HTTP, Supabase PostgREST |
| **langextract** | 8084 | LLM-powered structured extraction (text/XML → grounded chunks) using Gemini | REST (FastAPI) |
| **ffmpeg-whisper** | 8078 | Audio transcription via Whisper (migrating to `faster-whisper` GPU) | REST, MinIO S3, Supabase |
| **pmoves-yt** | 8077 | **YouTube ingestion pipeline**: `/yt/ingest`, `/yt/search`, `/yt/emit` (Hi-RAG), `/yt/summarize` (planned Gemma integration) | REST, MinIO S3, Hi-RAG Gateway HTTP, Supabase |
| **media-video** | 8079 | Video analysis (YOLO v11, Sortformer) → detections/segments to Supabase, emits `analysis.entities.v1` | REST, NATS pub, Supabase |
| **media-audio** | 8082 | Audio emotion analysis → `analysis.audio.v1` events | REST, NATS pub, Supabase |
| **render-webhook** | 8085 | ComfyUI completion webhook → Supabase `studio_board` status updates | REST, Supabase PostgREST |
| **presign** | 8088 | MinIO presigned URL generator for ComfyUI uploads | REST, MinIO S3 |

### RAG & Search (Profile: `gateway`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **hi-rag-gateway** (legacy) | 8086 (legacy profile only) | Original RAG gateway | REST, Qdrant, MeiliSearch, Supabase |
| **hi-rag-gateway-v2** | 8086 (default) / 8087 (GPU profile) | Enhanced RAG with rerankers (Flag/Qwen/Cohere/Azure). **Primary RAG endpoint**. Supports geometry cache (CGP). | REST, Qdrant gRPC, MeiliSearch, Supabase, ShapeStore cache |
| **retrieval-eval** | 8090 | RAG testing dashboard. Validates persona publish gates. | REST (FastAPI), Hi-RAG Gateway v2 |

### Integration & Analysis (Profile: `workers`, partial `orchestration`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **comfy-watcher** | - | Monitors ComfyUI job queue, emits `gen.image.result.v1` when jobs complete | WebSocket (ComfyUI), NATS pub |
| **comfyui/** | - | Custom ComfyUI nodes (e.g., MinIO loader) for AI image generation | Internal (ComfyUI API) |
| **graph-linker** | - | Neo4j relationship management. Subscribes to `gen.image.result.v1`, `analysis.extract_topics.result.v1`, `kb.upsert.request.v1` | NATS sub, Neo4j Cypher |
| **analysis-echo/** | - | Analysis service (purpose TBD - likely echoes analysis events for debugging) | NATS |
| **pdf-ingest/** | - | PDF processing pipeline (extracts text → LangExtract) | Internal |
| **notebook-sync** | 8095 | Polls Open Notebook SurrealDB API, normalises entries via LangExtract → Supabase, emits CGPs when research entries are ready. | REST, Supabase PostgREST |

### External Integrations (Profile: `external`, pmoves-net add-ons)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **open-notebook-ext** | 8503 (UI, override `OPEN_NOTEBOOK_UI_PORT`)<br>5055 (API, override `OPEN_NOTEBOOK_API_PORT`) | Research workspace (Streamlit UI + SurrealDB API). Operators capture notes/assets that sync back into Supabase via notebook-sync. | HTTP (UI), REST API |
| **pmoves-health-wger** | 8000 | Self-hosted Wger instance for workout metrics. n8n flows pull workouts → Supabase (`health_workouts`) → hi-rag geometry summaries. | REST, n8n webhooks |
| **pmoves-firefly-iii** | 8081 (mapped to container 8080) | Finance host (Firefly III). n8n flows ingest transactions → Supabase (`finance_transactions`) → geometry summaries. | REST, Supabase service tokens |
| **pmoves-open-notebook (internal)** | - | (See notebook-sync service) Connects pmoves stack to the external Open Notebook API for SurrealDB sync. | REST |
| **jellyfin** (external media server) | 8096 | Upstream Jellyfin server powering media enrichment. `jellyfin-bridge` links library metadata into Supabase. | REST, WebSocket |

### Data Layer (Profile: `data`)

| Service | Port | Purpose | Communication |
|---------|------|---------|---------------|
| **supabase** (CLI or compose) | 5432 (Postgres)<br>3000 (PostgREST)<br>54321 (REST/WS host)<br>54323 (GoTrue)<br>54324 (Storage)<br>8000 (Kong/API) | Unified database (Postgres + pgvector). Includes GoTrue auth, Storage, Studio, and **Realtime** websocket endpoints consumed by hi-rag gateways and n8n flows. Preferred local path: Supabase CLI `start --network-id pmoves-net`. | PostgREST, Realtime WebSocket, S3 API |
| **qdrant** | 6333 | Vector database for embeddings (primary vector store for RAG) | gRPC, REST |
| **neo4j** | 7474 (HTTP)<br>7687 (Bolt) | Knowledge graph (entities, relationships) | Cypher queries |
| **minio** | 9000 (API)<br>9001 (Console) | S3-compatible object storage (videos, audio, images, ComfyUI artifacts) | S3 API |
| **meilisearch** | 7700 | Full-text search engine (complements vector search) | REST |
| **nats** | 4222 (client)<br>8222 (HTTP monitoring) | Message broker (JetStream for durable subscriptions) | NATS protocol |

---

## Docker Compose Profiles

Services are organized into **6 deployment profiles** (defined in `docker-compose.yml`, `docker-compose.*.yml`):

| Profile | Services | Purpose |
|---------|----------|---------|
| **data** | qdrant, neo4j, minio, meilisearch, presign, (optional: nats) | Core data persistence and message broker |
| **workers** | hi-rag-gateway-v2, retrieval-eval, render-webhook, langextract, extract-worker | Processing and RAG workers |
| **orchestration** | n8n, publisher, publisher-discord, jellyfin-bridge | Workflow automation and publishing |
| **agents** | nats, agent-zero, archon, mesh-agent | Agent coordination layer |
| **gateway** | hi-rag-gateway-v2 (overlaps with `workers`) | Public-facing RAG endpoints |
| **gpu** | media-video, media-audio, (optional: faster-whisper GPU) | GPU-accelerated analysis |
| **external** | open-notebook-ext, pmoves-health-wger, pmoves-firefly-iii, pmoves-jellyfin | Domain integrations running on `pmoves-net` |

### Common Deployment Commands

```bash
# Default stack (data + workers + pmoves-yt + jellyfin-bridge)
make up

# Add agents profile (requires NATS)
make up-nats        # Starts NATS + updates .env.local
make up-agents      # Starts agent-zero, archon, mesh-agent, publisher-discord

# GPU analyzers (requires NVIDIA runtime)
make up-media

# n8n workflows only
make up-n8n

# Full Supabase (CLI method - recommended)
make supa-init && make supa-start && make supa-use-local   # supa-start wraps `supabase start --network-id pmoves-net`

# Compose-based Supabase (lightweight alternative)
make up-compose && make supabase-up

# External integrations (Firefly, Wger, Open Notebook, Jellyfin)
make up-external     # starts pmoves-net integrations published to GHCR or local clones
```

---

## Agent Zero: Primary Orchestrator

### Role & Responsibilities

**Agent Zero** is the **brain** of PMOVES. It:

1. **Makes decisions** about which services to invoke for a given task
2. **Creates subordinate agents** to break down complex tasks
3. **Maintains persistent memory** (recall previous solutions, code, instructions)
4. **Publishes events** to NATS for downstream coordination
5. **Exposes MCP commands** via HTTP bridge for AI clients (Crush, Codex)

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Liveness + JetStream controller status |
| `/config/environment` | GET | Resolved config (ports, directories, NATS status) |
| `/mcp/commands` | GET | Lists available MCP commands |
| `/mcp/execute` | POST | Execute MCP command (e.g., `geometry.jump`, `ingest.youtube`) |
| `/events/publish` | POST | Publish NATS envelope (topic + payload + metadata) |

### MCP Commands (from `agent-zero/mcp_server.py`)

- `geometry.publish_cgp` - Publish Constellation Geometry Protocol data
- `geometry.jump` - Navigate to point in knowledge space
- `geometry.decode_text` - Decode geometry-tagged text
- `geometry.calibration.report` - Get calibration status
- **`ingest.youtube`** - Trigger YouTube ingestion (will be enhanced)
- `media.transcribe` - Request audio transcription
- `comfy.render` - Queue ComfyUI render job
- `form.get` / `form.switch` - Manage agent forms (POWERFULMOVES, etc.)

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 8080 | FastAPI listen port |
| `NATS_URL` | `nats://nats:4222` | Event bus connection |
| `AGENTZERO_JETSTREAM` | `true` | Enable JetStream controller (durable subscriptions) |
| `AGENT_FORM` | `POWERFULMOVES` | Default agent persona |
| `AGENT_FORMS_DIR` | `configs/agents/forms` | YAML form definitions |
| `AGENT_KNOWLEDGE_BASE_DIR` | `runtime/knowledge` | Persistent memory artifacts |
| `HIRAG_URL` | `http://localhost:8086` | Hi-RAG Gateway v2 URL |
| `YT_URL` | `http://localhost:8077` | PMOVES.yt service URL |
| `RENDER_WEBHOOK_URL` | `http://localhost:8085` | ComfyUI webhook |

### JetStream Controller

Agent Zero now includes a **JetStream controller** that:

1. Connects to NATS at startup (retries until `NATS_URL` is reachable)
2. Creates **durable consumers** for topics Agent Zero cares about:
   - `content.published.v1` - Published content events
   - `archon.task.update.v1` - Task progress from Archon
   - `analysis.entities.v1` - Entity detection results
   - `analysis.audio.v1` - Audio emotion analysis
3. Reports status via `/healthz` (connected, controller_started, subscription counts)

**Note**: If you see `nats: JetStream.Error cannot create queue subscription...` after rebuilding, restart the container to let the controller recreate consumers cleanly.

---

## Event-Driven Architecture (NATS)

### Message Broker: NATS JetStream

PMOVES uses **NATS JetStream** for:

- **Durable message queues** (survive restarts)
- **Pub/sub coordination** between services
- **Event sourcing** (all events logged to streams)
- **Dead-letter queues** (planned for failed message handling)

### Topic Schema Registry

`pmoves/contracts/topics.json` defines **40+ event schemas**:

#### Agent Zero Events
- `agentzero.event.log.v1` - Agent logs
- `agentzero.memory.update` - Memory updates
- `agentzero.task.v1` / `agentzero.task.status.v1` / `agentzero.task.result.v1` - Task lifecycle

#### Ingest Events
- `ingest.transcript.ready.v1` - Transcription complete
- `ingest.file.added.v1` - New file uploaded
- `ingest.document.ready.v1` - Document processed

#### Analysis Events
- `analysis.extract_topics.request.v1` / `analysis.extract_topics.result.v1` - Topic extraction
- `analysis.entities.v1` - Entity detection (YOLO, Sortformer)
- `analysis.audio.v1` - Audio emotion analysis

#### Generation Events
- `gen.text.request.v1` / `gen.text.result.v1` - Text generation
- `gen.image.request.v1` / `gen.image.result.v1` - Image generation (ComfyUI)

#### Knowledge Base Events
- `kb.upsert.request.v1` / `kb.upsert.result.v1` - Knowledge base updates
- `kb.search.request.v1` / `kb.search.result.v1` - RAG queries

#### Archon Events
- `archon.crawl.request.v1` / `archon.crawl.result.v1` - Web crawling
- `archon.task.update.v1` - Task progress updates

#### Publishing Events (M2 Focus)
- **`content.publish.approved.v1`** - Approval poller → Agent Zero (n8n)
- **`content.publish.failed.v1`** - Publish failures
- **`content.published.v1`** - Publisher → Discord/Agent Zero (enriched with Jellyfin metadata)

#### Geometry Events
- `geometry.cgp.v1` - Constellation Geometry Protocol broadcasts

#### Persona Events
- `persona.publish.request.v1` / `persona.publish.failed.v1` / `persona.published.v1` - Persona lifecycle

### NATS Usage Patterns

#### Publishing (Example: comfy-watcher)
```python
from nats.aio.client import Client as NATS
nc = NATS()
await nc.connect(servers=["nats://nats:4222"])

envelope = {
    "topic": "gen.image.result.v1",
    "payload": {"prompt_id": "abc", "s3_url": "s3://..."},
    "correlation_id": "xyz",
    "source": "comfy-watcher"
}
await nc.publish("gen.image.result.v1", json.dumps(envelope).encode())
```

#### Subscribing (Example: graph-linker)
```python
async def handle_message(msg):
    data = json.loads(msg.data.decode())
    # Process event, update Neo4j

await nc.subscribe("gen.image.result.v1", cb=handle_message)
await nc.subscribe("analysis.extract_topics.result.v1", cb=handle_message)
await nc.subscribe("kb.upsert.request.v1", cb=handle_message)
```

---

## MCP Ecosystem

### What is MCP?

**Model Context Protocol (MCP)** is a standard for exposing tools and context to AI clients (Crush CLI, Codex, Claude Desktop, etc.). It allows agents to:

- **Discover tools** (e.g., "What can PMOVES do?")
- **Execute tools** with structured parameters
- **Receive structured responses** (JSON)

### Existing MCP Implementations

#### 1. Archon (MCP Server)

**Port**: 8051 (HTTP bridge)

**10+ MCP Tools**:
- `archon_search_knowledge` - Semantic search across crawled docs
- `archon_get_projects` - List all projects
- `archon_get_project` - Get project details
- `archon_create_project` - Create new project
- `archon_update_project` - Update project metadata
- `archon_get_tasks` - List tasks in project
- `archon_create_task` - Create task with AI-assisted description
- `archon_update_task` - Update task status/description
- `archon_delete_task` - Delete task
- `archon_crawl_url` - Trigger web crawl (publishes `archon.crawl.request.v1`)

**MCP Config Example** (for Crush/Codex):
```json
{
  "mcpServers": {
    "archon": {
      "endpoint": "http://archon_mcp:8051",
      "protocol": "http"
    }
  }
}
```

#### 2. Agent Zero (MCP Server)

**Port**: 8080 (HTTP bridge via `/mcp/*` endpoints)

**9 MCP Commands** (from `agent-zero/mcp_server.py`):
- `geometry.publish_cgp` - Publish CGP data to Hi-RAG
- `geometry.jump` - Navigate knowledge space
- `geometry.decode_text` - Decode geometry tags
- `geometry.calibration.report` - Get calibration status
- `ingest.youtube` - Trigger YouTube ingestion (calls `YT_URL/yt/ingest`)
- `media.transcribe` - Request transcription (calls `ffmpeg-whisper`)
- `comfy.render` - Queue ComfyUI job (calls `RENDER_WEBHOOK_URL`)
- `form.get` - Get current agent form
- `form.switch` - Switch agent persona

**MCP Config Example**:
```json
{
  "mcpServers": {
    "agent-zero": {
      "endpoint": "http://agent-zero:8080/mcp",
      "protocol": "http"
    }
  }
}
```

#### 3. n8n (MCP Hub)

**Port**: 5678

n8n is labeled as the **"MCP Hub"** in `docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md`. Its role:

- **Workflow orchestration** between Agent Zero, Archon, and other services
- **Webhook-based tool invocation** (HTTP nodes can call MCP servers)
- **Multi-agent task delegation** (n8n workflows can spawn parallel MCP calls)

**Example M2 Workflows**:
1. **Approval Poller** (`n8n/flows/approval_poller.json`)
   - Polls Supabase `studio_board` for `status='approved'`
   - Posts `content.publish.approved.v1` to Agent Zero `/events/publish`
   - Updates row to `status='published'`

2. **Echo Publisher** (`n8n/flows/echo_publisher.json`)
   - Receives webhook from `publisher` service with `content.published.v1` payload
   - Sends Discord embed with title, thumbnail, duration, Jellyfin link
   - Optionally forwards to other MCP servers for logging

3. **PMOVES.yt Workflow** (`docs/PMOVES.yt/n8n_pmoves_yt_workflow.json`)
   - Webhook trigger → `/yt/ingest` → `/yt/emit` → `/yt/summarize` → `/jellyfin/map-by-title`
   - Parallel execution (emit + summarize run simultaneously)
   - Auto-mapping to Jellyfin library items

---

## Data Layer

### Supabase (Unified Database)

**Deployment**: Supabase CLI (recommended) or compose fallback. For CLI parity use `supabase start --network-id pmoves-net` so PostgREST and Realtime share the Docker network with PMOVES.

**Services**:
- **Postgres** (5432) - Primary database with pgvector extension
- **PostgREST** (3000) - REST API auto-generated from schema
- **GoTrue** (auth) - Authentication (not yet used in M2)
- **Realtime** - WebSocket subscriptions to table changes
- **Storage** - S3-compatible file storage (alternative to MinIO)
- **Studio** (54321) - Web UI for data management

**Key Tables** (from `db/v5_12_*.sql` and `supabase/migrations/`):
- `videos` - YouTube videos metadata (duration, channel, tags, s3_base_prefix)
- `transcripts` - Whisper transcriptions (text, timestamps, language)
- `studio_board` - Creator approval queue (status, content_url, meta.publish_event_sent_at)
- `chunks` - Extracted text chunks (from LangExtract)
- `personas` - AI agent personas (embeddings, prompts, packs)
- `packs` - Knowledge packs (manifests, selectors, age/size limits)
- `archon_prompts` - Archon system prompts
- `geometry_cgp_packets` / `constellations` - Constellation Geometry Protocol data
- `health_workouts` / `health_nutrition` - Wger ingests
- `finance_transactions` / `finance_accounts` - Firefly III ingests
- `notebook_entries` (Surreal sync staging) - Open Notebook snapshots forwarded by notebook-sync
- `publisher_metrics_rollup` / `publisher_discord_metrics` - Publishing telemetry

**RLS (Row-Level Security)**:
- See `docs/SUPABASE_RLS_HARDENING_CHECKLIST.md` for production hardening plan
- Current: development mode (permissive policies)
- Future: `authenticated` role for user content, `service_role` for automation

### Qdrant (Vector Database)

**Port**: 6333

**Purpose**: Primary vector store for embeddings (chunks, personas, packs)

**Collections**:
- `pmoves_chunks` - Chunked documents with embeddings
- `pmoves_personas` - Persona embeddings
- (Others TBD)

**Integration**: Hi-RAG Gateway v2 queries Qdrant via gRPC

### Neo4j (Knowledge Graph)

**Ports**: 7474 (HTTP), 7687 (Bolt)

**Purpose**: Entity relationships, brand aliases, fact-based reasoning

**M3 Roadmap**:
- Load brand alias dictionary (DARKXSIDE, POWERFULMOVES) via Cypher scripts
- Relation extraction from captions/notes → candidate graph edges
- Graph-enhanced RAG queries (Hi-RAG + Neo4j)

**Scripts**: `pmoves/neo4j/cypher/002_load_person_aliases.cypher` (pending)

### MinIO (Object Storage)

**Ports**: 9000 (API), 9001 (Console)

**Buckets**:
- `pmoves-yt` - YouTube videos, audio, thumbnails
- `pmoves-transcripts` - Whisper outputs
- `pmoves-comfyui` - Generated images/videos from ComfyUI
- `pmoves-studio` - Studio assets (approved content)

**Presign Service**: `presign` (port 8088) generates signed URLs for ComfyUI uploads

### MeiliSearch (Full-Text Search)

**Port**: 7700

**Purpose**: Complements vector search with keyword/phrase matching

**Indexes**:
- `pmoves_chunks` - Full-text index on extracted text
- (Others TBD)

---

## Service Communication Patterns

### 1. REST APIs (Synchronous)

Most services expose FastAPI endpoints:

- **Agent Zero**: `/mcp/execute`, `/events/publish`
- **Archon**: `/api/v1/projects`, `/api/v1/tasks`, `/api/v1/knowledge`
- **Hi-RAG Gateway v2**: `/search`, `/retrieve`, `/rerank`
- **PMOVES.yt**: `/yt/ingest`, `/yt/search`, `/yt/emit`, `/yt/summarize`
- **Jellyfin Bridge**: `/link`, `/map-by-title`, `/search`, `/playback-url`
- **Publisher**: `/publish`, `/metrics`

### 2. NATS Pub/Sub (Asynchronous)

Event-driven coordination:

- **Publishers**: comfy-watcher, publisher, media-video, media-audio, graph-linker
- **Subscribers**: Agent Zero, Archon, graph-linker, publisher-discord

### 3. Supabase Realtime (WebSocket)

- **Hi-RAG Gateway v2 / v2-gpu**: Subscribes to `realtime:geometry.cgp.v1` for constellation updates and warms ShapeStore caches on startup.
- **n8n**: Uses service-role keys to push finance/health payloads, triggering realtime events for downstream analytics.
- **Archon** (planned): listens for knowledge pack changes to refresh MCP prompts.

**Example Flow** (M2 Publishing):
```
n8n approval poller → Agent Zero /events/publish
  → NATS: content.publish.approved.v1
    → publisher service subscribes
      → Publishes to Jellyfin, enriches metadata
        → NATS: content.published.v1
          → publisher-discord subscribes
            → Discord webhook (rich embed)
```

### 3. MCP (AI Client ↔ Tool Server)

MCP clients (Crush, Codex, Agent Zero) discover and invoke tools:

```
Crush CLI → MCP client
  → HTTP: archon_mcp:8051/tools
    → Response: [archon_search_knowledge, archon_create_task, ...]
  → HTTP: archon_mcp:8051/execute
    → Body: {"tool": "archon_search_knowledge", "args": {"query": "PMOVES architecture"}}
    → Response: {"results": [...]}
```

### 4. Webhooks (External → PMOVES)

- **n8n webhooks**: `/webhook/pmoves/content-published` (echo publisher)
- **Discord webhooks**: External Discord servers receive embeds
- **Jellyfin webhooks** (planned): Library updates → trigger backfill

### 5. Database Access Patterns

- **Supabase PostgREST**: Most services use REST API (auth via `apikey` header)
- **Direct Postgres**: Some services (extract-worker, publisher) use `psycopg2` for transactions
- **Qdrant gRPC**: Hi-RAG Gateway v2 uses gRPC for vector queries
- **Neo4j Bolt**: graph-linker uses `neo4j-driver` for Cypher queries

---

## M2 Automation Architecture

### Goal: Supabase → Agent Zero → Discord Loop

**Status**: Active (validation logs in `SESSION_IMPLEMENTATION_PLAN.md` dated October 2025)

### Components

1. **Supabase `studio_board` Table**
   - Rows represent content awaiting approval/publishing
   - Columns: `status` (pending/approved/published), `content_url` (S3 path), `meta` (JSONB with `publish_event_sent_at`)

2. **n8n Approval Poller Workflow**
   - Cron: Every 5 minutes (configurable)
   - Query: `SELECT * FROM studio_board WHERE status='approved' AND meta->>'publish_event_sent_at' IS NULL`
   - For each row:
     - POST to Agent Zero `/events/publish` with `content.publish.approved.v1` event
     - PATCH row to `status='published'`, set `meta.publish_event_sent_at=<timestamp>`

3. **Agent Zero Event Republisher**
   - Subscribes to `content.publish.approved.v1` (via JetStream controller)
   - Forwards to `publisher` service (or directly to NATS for fanout)

4. **Publisher Service** (port 8092)
   - Subscribes to `content.publish.approved.v1`
   - Uploads asset to Jellyfin library
   - Enriches with metadata: `jellyfin_item_id`, `jellyfin_public_url`, `thumbnail_url`, `duration`, tags
   - Publishes `content.published.v1` event (enriched)

5. **Jellyfin Bridge** (port 8093)
   - Provides `/map-by-title` endpoint for auto-linking assets by fuzzy title match
   - Used by n8n workflows and publisher service

6. **Publisher-Discord Service** (port 8094)
   - Subscribes to `content.published.v1`
   - POSTs rich embed to Discord webhook with:
     - Title, description, thumbnail (from `thumbnail_url`)
     - Duration, Jellyfin deep link (from `jellyfin_public_url`)
     - Artifact path (S3 URL or MinIO presigned URL)

7. **n8n Echo Publisher Workflow**
   - Webhook trigger: `/webhook/pmoves/content-published`
   - Receives `content.published.v1` payload from `publisher` service (optional alternative to NATS)
   - Sends Discord embed (duplicate of publisher-discord logic, kept for flexibility)

### Validation Evidence (from `SESSION_IMPLEMENTATION_PLAN.md`)

```
2025-10-17T15:29:23Z - Agent Zero health OK (JetStream controller connected)
2025-10-17T15:21:05Z - Discord webhook ping successful
2025-10-12 - PMOVES.yt updates completed (CUDA 12.6, yt-dlp hardening, smoke tests passed 12/12)
2025-10-14 - Agent Zero realtime listener captured enriched payload (thumbnail_url, duration, jellyfin_item_id)
2025-10-14 - publisher-discord delivered Jellyfin-enriched embed to mock webhook
```

### Outstanding M2 Tasks (from `NEXT_STEPS.md`)

- [ ] Activate n8n approval poller in production (currently manual trigger)
- [ ] Confirm Jellyfin credentials allow library enumeration (`make jellyfin-verify`)
- [ ] Backfill historic `studio_board` rows with enriched metadata
- [ ] Automate evidence capture (timestamps, log snapshots) via script
- [ ] Hit `/metrics` endpoints on publisher/publisher-discord to capture turnaround/latency

---

## PMOVES.yt MCP Integration Strategy

### Current State (as of session)

**PMOVES.yt** (port 8077) is a FastAPI service providing:

- **`/yt/ingest`** - Download YouTube video, extract audio, store in MinIO, insert metadata to Supabase
- **`/yt/search`** - Semantic search across YouTube corpus (Hi-RAG Gateway v2 backend)
- **`/yt/emit`** - Emit video chunks to Hi-RAG for indexing
- **`/yt/summarize`** - (Planned) Generate summary using Gemma/Ollama

**Current Integration**:
- Agent Zero MCP command: `ingest.youtube` (calls `/yt/ingest`)
- n8n workflow: Orchestrates full pipeline (ingest → extract → emit → summarize → Jellyfin mapping)

**Problem**: PMOVES.yt is **not yet a full MCP server** — it only has REST endpoints. To enable:
1. **Tool discovery** by Crush/Codex/Archon
2. **Structured parameter validation** (JSON schema)
3. **Automatic API docs generation** (OpenAPI via MCP introspection)
4. **Integration with n8n MCP Hub** for orchestrated workflows

...it should expose MCP tools natively.

### Proposed MCP Tools for PMOVES.yt

#### 1. `youtube_ingest`
**Description**: Download and ingest a YouTube video (video file, audio, thumbnail, metadata)

**Parameters**:
```json
{
  "url": "https://youtube.com/watch?v=...",
  "extract_audio": true,
  "store_video": true,
  "emit_to_hirag": true
}
```

**Response**:
```json
{
  "video_id": "abc123",
  "s3_base_prefix": "s3://pmoves-yt/abc123/",
  "duration": 245.6,
  "title": "Rick Astley - Never Gonna Give You Up",
  "hirag_indexed": true
}
```

**Implementation Notes**:
- Reuses existing `/yt/ingest` logic
- Add parameter validation (URL format, boolean flags)
- Return structured response (not just HTTP 200)

#### 2. `youtube_search`
**Description**: Semantic search across indexed YouTube videos

**Parameters**:
```json
{
  "query": "never gonna give you up",
  "top_k": 5,
  "min_similarity": 0.5
}
```

**Response**:
```json
{
  "results": [
    {
      "video_id": "abc123",
      "title": "Rick Astley - Never Gonna Give You Up",
      "snippet": "We're no strangers to love...",
      "similarity": 0.6028,
      "jellyfin_url": "http://jellyfin:8096/web/index.html#!/item?id=xyz",
      "thumbnail_url": "http://jellyfin:8096/Items/xyz/Images/Primary"
    }
  ]
}
```

**Implementation Notes**:
- Reuses existing `/yt/search` logic
- Add Jellyfin enrichment (query `jellyfin-bridge` for item IDs)
- Return structured results with metadata

#### 3. `youtube_emit`
**Description**: Emit video chunks to Hi-RAG Gateway for indexing

**Parameters**:
```json
{
  "video_id": "abc123",
  "force_reindex": false
}
```

**Response**:
```json
{
  "video_id": "abc123",
  "chunks_indexed": 42,
  "hirag_collection": "pmoves_chunks"
}
```

**Implementation Notes**:
- Reuses existing `/yt/emit` logic
- Add `force_reindex` flag to override existing chunks
- Return indexing stats

#### 4. `youtube_summarize` (Planned)
**Description**: Generate summary using Gemma/Ollama

**Parameters**:
```json
{
  "video_id": "abc123",
  "model": "gemma2:9b-instruct",
  "style": "concise"
}
```

**Response**:
```json
{
  "video_id": "abc123",
  "summary": "A classic 1987 pop song by Rick Astley...",
  "model_used": "gemma2:9b-instruct",
  "generation_time_ms": 1234
}
```

**Implementation Notes**:
- Integrate Ollama API or HF Transformers
- Use transcript + metadata as input
- Store summaries in Supabase `videos.meta` JSONB column

#### 5. `youtube_transcribe` (Future)
**Description**: Request transcription for a video

**Parameters**:
```json
{
  "video_id": "abc123",
  "language": "auto",
  "diarization": false
}
```

**Response**:
```json
{
  "video_id": "abc123",
  "transcript_id": "def456",
  "status": "pending",
  "estimated_completion": "2025-01-15T12:34:56Z"
}
```

**Implementation Notes**:
- Publishes `ingest.transcript.ready.v1` event to NATS
- `ffmpeg-whisper` service handles transcription
- PMOVES.yt polls Supabase for completion

#### 6. `youtube_list_videos`
**Description**: List videos in the corpus (with filters)

**Parameters**:
```json
{
  "channel": "UC...",
  "min_duration": 60,
  "max_duration": 600,
  "has_transcript": true,
  "limit": 20
}
```

**Response**:
```json
{
  "videos": [
    {
      "video_id": "abc123",
      "title": "Rick Astley - Never Gonna Give You Up",
      "duration": 245.6,
      "channel": "RickAstleyVEVO",
      "ingested_at": "2025-10-12T10:30:00Z"
    }
  ],
  "total": 120
}
```

**Implementation Notes**:
- Query Supabase `videos` table with filters
- Return paginated results

### MCP Server Implementation Plan

#### Step 1: Add MCP HTTP Bridge to PMOVES.yt

Create `pmoves/services/pmoves-yt/mcp_server.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/mcp", tags=["MCP"])

class MCPCommand(BaseModel):
    cmd: str
    arguments: dict

class MCPTool(BaseModel):
    name: str
    description: str
    parameters: dict

@router.get("/commands")
async def list_commands() -> List[MCPTool]:
    return [
        MCPTool(
            name="youtube_ingest",
            description="Download and ingest a YouTube video",
            parameters={
                "url": {"type": "string", "required": True},
                "extract_audio": {"type": "boolean", "default": True},
                "store_video": {"type": "boolean", "default": True},
                "emit_to_hirag": {"type": "boolean", "default": True}
            }
        ),
        MCPTool(
            name="youtube_search",
            description="Semantic search across indexed YouTube videos",
            parameters={
                "query": {"type": "string", "required": True},
                "top_k": {"type": "integer", "default": 5},
                "min_similarity": {"type": "number", "default": 0.5}
            }
        ),
        # ... other tools
    ]

@router.post("/execute")
async def execute_command(cmd: MCPCommand):
    if cmd.cmd == "youtube_ingest":
        # Call existing ingest logic
        result = await ingest_video(**cmd.arguments)
        return result
    elif cmd.cmd == "youtube_search":
        # Call existing search logic
        results = await search_videos(**cmd.arguments)
        return results
    # ... other commands
```

Mount router in `pmoves/services/pmoves-yt/main.py`:

```python
from mcp_server import router as mcp_router
app.include_router(mcp_router)
```

#### Step 2: Update Agent Zero to Call PMOVES.yt MCP

Update `agent-zero/mcp_server.py`:

```python
@app.post("/mcp/execute")
async def execute_mcp_command(cmd: MCPCommand):
    if cmd.cmd.startswith("youtube_"):
        # Forward to PMOVES.yt MCP server
        yt_mcp_url = os.getenv("YT_URL", "http://pmoves-yt:8077")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{yt_mcp_url}/mcp/execute",
                json={"cmd": cmd.cmd, "arguments": cmd.arguments}
            )
            return response.json()
    # ... existing commands
```

#### Step 3: Register PMOVES.yt in MCP Hub (n8n)

Create n8n workflow node:

1. **HTTP Request Node**: `GET {{YT_URL}}/mcp/commands`
   - Store tool list in workflow variable
2. **Function Node**: Parse tools, expose as n8n functions
3. **HTTP Request Node**: `POST {{YT_URL}}/mcp/execute`
   - Dynamic body based on selected tool

#### Step 4: Add OpenAPI Documentation

Update `pmoves/services/pmoves-yt/main.py`:

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="PMOVES.yt MCP Server",
        version="1.0.0",
        description="YouTube ingestion pipeline with MCP tools",
        routes=app.routes,
    )
    # Add MCP-specific metadata
    openapi_schema["x-mcp-protocol"] = "http"
    openapi_schema["x-mcp-endpoint"] = "/mcp"
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

#### Step 5: Update Docker Compose

Expose MCP metadata in `docker-compose.yml`:

```yaml
pmoves-yt:
  # ...
  labels:
    - "pmoves.mcp.enabled=true"
    - "pmoves.mcp.endpoint=http://pmoves-yt:8077/mcp"
    - "pmoves.mcp.tools=youtube_ingest,youtube_search,youtube_emit,youtube_summarize"
```

### Integration with Agent Zero Orchestration

**Scenario**: User asks Crush CLI to "download Rick Astley Never Gonna Give You Up and add to knowledge base"

**Flow**:
```
1. Crush CLI → MCP client discovers tools from Agent Zero
2. Crush calls `agent-zero:8080/mcp/execute`
   - Command: `youtube_ingest`
   - Args: {"url": "https://...", "emit_to_hirag": true}
3. Agent Zero forwards to `pmoves-yt:8077/mcp/execute`
4. PMOVES.yt executes:
   - Downloads video (yt-dlp)
   - Extracts audio (FFmpeg)
   - Uploads to MinIO
   - Inserts metadata to Supabase
   - Calls `/yt/emit` to index chunks in Hi-RAG
5. PMOVES.yt publishes `ingest.document.ready.v1` event to NATS
6. Archon subscribes, adds to knowledge base
7. Response bubbles back to Crush: "✅ Video ingested, 42 chunks indexed"
```

### Integration with n8n MCP Hub

**Scenario**: n8n workflow "YouTube Weekly Digest"

**Flow**:
```
1. Cron trigger: Every Monday 9am
2. n8n HTTP node: `GET pmoves-yt:8077/mcp/execute`
   - Command: `youtube_list_videos`
   - Args: {"channel": "UCXXX", "has_transcript": true, "limit": 10}
3. For each video:
   a. Call `youtube_summarize` (MCP)
   b. Store summary in Supabase
   c. Call `/jellyfin/map-by-title` to link Jellyfin item
4. Aggregate summaries into Discord embed
5. Post to Discord webhook
```

### Testing Plan

1. **Unit Tests**: `tests/test_mcp_server.py`
   - Test `/mcp/commands` returns correct tool list
   - Test `/mcp/execute` validates parameters
   - Test error handling (invalid URL, network failure)

2. **Integration Tests**: `tests/test_pmoves_yt_mcp_integration.py`
   - Test Agent Zero → PMOVES.yt MCP forwarding
   - Test n8n workflow calling PMOVES.yt MCP
   - Test Jellyfin enrichment in search results

3. **Smoke Tests**: `make yt-mcp-smoke`
   - Target: Rick Astley test video
   - Steps:
     1. Call `youtube_ingest` MCP command
     2. Verify S3 upload, Supabase row, Hi-RAG indexing
     3. Call `youtube_search` MCP command
     4. Verify results include Jellyfin URL
     5. Call `youtube_emit` with `force_reindex=true`
     6. Verify chunk count increments

4. **Manual Testing**: Crush CLI session
   ```bash
   crush
   > Use the youtube_ingest tool to download https://www.youtube.com/watch?v=dQw4w9WgXcQ
   > Search for "never gonna give you up" using youtube_search
   > Summarize the video using youtube_summarize
   ```

### Documentation Updates

1. **`pmoves/services/pmoves-yt/README.md`**:
   - Add MCP section with tool list
   - Add configuration (`MCP_ENABLED`, `MCP_PORT`)
   - Add Crush/Codex config examples

2. **`pmoves/docs/PMOVES.yt/MCP_INTEGRATION.md`** (new):
   - Architecture diagram (Crush ↔ Agent Zero ↔ PMOVES.yt)
   - Tool schemas with examples
   - n8n workflow templates
   - Troubleshooting guide

3. **Update `pmoves/docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md`**:
   - Add PMOVES.yt to MCP server list
   - Document YouTube-specific MCP tools
   - Add workflow examples

### Alignment with M2 Goals

**M2 Focus**: Creator & Publishing (Supabase → Agent Zero → Discord)

**How PMOVES.yt MCP Fits**:
1. **YouTube content ingestion** → Enriched metadata in Supabase
2. **Jellyfin auto-mapping** → Publisher service can link videos
3. **Agent Zero orchestration** → Seamless "find and publish" workflows
4. **n8n automation** → "Weekly YouTube digest" workflow publishes to Discord

**Example M2 Workflow**:
```
User approves YouTube video in Supabase studio_board
  → n8n approval poller publishes content.publish.approved.v1
    → Agent Zero receives event
      → Calls youtube_search MCP to find Jellyfin item
        → Publisher enriches with thumbnail_url, duration, jellyfin_public_url
          → Publishes content.published.v1
            → Publisher-Discord sends rich embed to Discord ✅
```

---

## Next Steps

### Immediate (Before MCP Implementation)

1. ✅ **Review Complete**: All 31 services documented, orchestration patterns understood
2. ✅ **NATS Patterns**: Pub/sub flows mapped (40+ topics in contracts)
3. ✅ **Existing MCP**: Archon (10 tools), Agent Zero (9 commands), n8n (MCP Hub)
4. ✅ **M2 Context**: Automation loop validated (October 2025 logs)

### Phase 1: PMOVES.yt MCP Server (1-2 days)

- [ ] Create `pmoves/services/pmoves-yt/mcp_server.py` with 6 tools
- [ ] Add `/mcp/commands` and `/mcp/execute` endpoints
- [ ] Update `main.py` to include MCP router
- [ ] Add OpenAPI metadata (x-mcp-protocol, x-mcp-endpoint)
- [ ] Test locally: `curl http://localhost:8077/mcp/commands`

### Phase 2: Agent Zero Integration (1 day)

- [ ] Update `agent-zero/mcp_server.py` to forward `youtube_*` commands
- [ ] Add `YT_MCP_URL` config to `.env.local`
- [ ] Test: Crush CLI → Agent Zero → PMOVES.yt MCP chain
- [ ] Document in `agent-zero/README.md`

### Phase 3: n8n Workflows (1 day)

- [ ] Create "YouTube Weekly Digest" workflow template
- [ ] Add PMOVES.yt MCP nodes (HTTP requests to `/mcp/execute`)
- [ ] Test: Cron trigger → list videos → summarize → Discord embed
- [ ] Export workflow to `pmoves/n8n/flows/youtube_digest.json`

### Phase 4: Documentation & Testing (1 day)

- [ ] Create `pmoves/docs/PMOVES.yt/MCP_INTEGRATION.md`
- [ ] Add smoke tests (`make yt-mcp-smoke`)
- [ ] Update `PMOVES_COMPLETE_ARCHITECTURE.md` with PMOVES.yt MCP details
- [ ] Record demo video: Crush CLI → YouTube ingest → Discord publish

### Phase 5: M2 Validation (1 day)

- [ ] Run full automation loop with PMOVES.yt MCP:
  - Ingest YouTube video via Agent Zero MCP
  - Auto-map to Jellyfin
  - Approve in Supabase `studio_board`
  - Verify Discord embed includes YouTube metadata
- [ ] Capture validation evidence in `SESSION_IMPLEMENTATION_PLAN.md`
- [ ] Mark M2 YouTube lane as complete in `ROADMAP.md`

---

## Appendix: Service Dependency Matrix

| Service | Depends On | Consumes From | Publishes To |
|---------|------------|---------------|--------------|
| agent-zero | NATS, Supabase | content.published.v1, archon.task.update.v1 | agentzero.task.v1, agentzero.memory.update |
| archon | Supabase, NATS | ingest.*, archon.crawl.request | archon.crawl.result.v1, archon.task.update.v1 |
| n8n | Supabase PostgREST, Agent Zero, Discord webhooks | - | content.publish.approved.v1 (via Agent Zero) |
| publisher | Supabase, Jellyfin API, NATS | content.publish.approved.v1 | content.published.v1 |
| publisher-discord | NATS, Discord webhooks | content.published.v1 | - |
| jellyfin-bridge | Jellyfin API, Supabase | - | - |
| pmoves-yt | MinIO, Hi-RAG Gateway, Supabase | - | ingest.document.ready.v1 (planned) |
| extract-worker | LangExtract, Qdrant, MeiliSearch, Supabase | - | - |
| langextract | Gemini API, Supabase | - | - |
| ffmpeg-whisper | MinIO, Supabase | - | ingest.transcript.ready.v1 |
| media-video | MinIO, Supabase, NATS | - | analysis.entities.v1 |
| media-audio | MinIO, Supabase, NATS | - | analysis.audio.v1 |
| comfy-watcher | ComfyUI WebSocket, NATS | - | gen.image.result.v1 |
| graph-linker | Neo4j, NATS | gen.image.result.v1, analysis.extract_topics.result.v1, kb.upsert.request.v1 | - |
| hi-rag-gateway-v2 | Qdrant, MeiliSearch, Supabase | - | - |
| retrieval-eval | Hi-RAG Gateway v2, Supabase | - | - |
| render-webhook | Supabase PostgREST | - | - |
| presign | MinIO | - | - |

---

## References

### Core Documents
- `pmoves/README.md` - Quickstart, profiles, Supabase modes
- `pmoves/docs/ROADMAP.md` - M1-M5 milestones
- `pmoves/docs/NEXT_STEPS.md` - Immediate tasks, M2 focus
- `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` - M2 automation validation logs

### Agent Architecture
- `docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md` - Agent Zero, Archon, Crush roles
- `pmoves/services/agent-zero/README.md` - Agent Zero endpoints, MCP commands, JetStream controller
- `pmoves/services/archon/README.md` - Archon MCP server, 10 tools, NATS subscriptions

### MCP Ecosystem
- `docs/PMOVES_ARC.md` - MCP server paths, n8n MCP Hub role
- `docs/PMOVES_Enhanced_Visual_Architecture_Diagrams.md` - Architecture diagrams with MCP flows

### M2 Automation
- `pmoves/docs/JELLYFIN_BRIDGE_INTEGRATION.md` - Jellyfin integration, auto-mapping
- `pmoves/docs/SUPABASE_DISCORD_AUTOMATION.md` - Automation loop activation checklist
- `pmoves/n8n/flows/approval_poller.json` - n8n approval workflow
- `pmoves/n8n/flows/echo_publisher.json` - n8n Discord webhook workflow

### Contracts
- `pmoves/contracts/topics.json` - NATS topic schemas (40+ events)
- `pmoves/contracts/schemas/` - JSON schemas for event validation

### PMOVES.yt
- `pmoves/services/pmoves-yt/README.md` - Existing REST endpoints
- `pmoves/docs/PMOVES.yt/n8n_pmoves_yt_workflow.json` - n8n workflow
- `pmoves/docs/PMOVES.yt/WORKFLOW_SUMMARY.md` - Workflow documentation

---

**Document Status**: ✅ Complete architecture map generated from codebase + planning docs

**Next Action**: Review with user, then proceed with PMOVES.yt MCP integration (Phase 1-5 plan above)
