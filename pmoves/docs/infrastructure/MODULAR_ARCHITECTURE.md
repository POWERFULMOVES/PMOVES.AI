# PMOVES.AI Modular Architecture

This document describes the modular architecture of PMOVES.AI, a production-ready multi-agent orchestration platform.

## Overview

PMOVES.AI is built as a collection of modular services that work together to provide:
- Autonomous agent coordination
- Hybrid RAG (vector + graph + full-text search)
- Multimodal holographic deep research
- Media processing pipeline
- Comprehensive observability

**Key Principle**: All services are required in production. The architecture supports different deployment modes (docked/standalone) but does not have "optional" services.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PMOVES.AI Platform                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │  Agents &    │    │  Retrieval   │    │    Media     │        │
│  │ Orchestration│◄──►│   & Search   │◄──►│   Pipeline   │        │
│  │              │    │              │    │              │        │
│  │ • Agent Zero │    │ • Hi-RAG v2  │    │ • PMOVES.YT  │        │
│  │ • Archon     │    │ • Qdrant     │    │ • Whisper    │        │
│  │ • Mesh Agent │    │ • Neo4j      │    │ • Analyzers  │        │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘        │
│         │                    │                    │                  │
│         └────────────────────┴────────────────────┘                  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Core Infrastructure                       │  │
│  │                                                              │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │  │
│  │  │  NATS   │  │ Supabase│  │  MinIO  │  │   TensorZero │   │  │
│  │  │ Message │  │ Database│  │ Storage │  │     Gateway   │   │  │
│  │  │   Bus   │  │         │  │         │  │              │   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────────┘   │  │
│  │                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Observability Stack                        │  │
│  │                                                              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │  │
│  │  │Prometheus│  │ Grafana  │  │   Loki   │                   │  │
│  │  │ Metrics  │  │ Dashboards│  │   Logs   │                   │  │
│  │  └──────────┘  └──────────┘  └──────────┘                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Service Tiers

### Tier: Agent (Orchestration & Control)

Services that coordinate agents and manage task execution.

| Service | Port | Purpose |
|---------|------|---------|
| **Agent Zero** | 8080 API, 8081 UI | Control-plane orchestrator with embedded agent runtime |
| **Archon** | 8091 API, 3737 UI | Supabase-driven agent service with prompt management |
| **Mesh Agent** | N/A | Distributed node announcer for multi-host |

### Tier: API (Core Services)

Central services that provide essential platform capabilities.

| Service | Port | Purpose |
|---------|------|---------|
| **Service Registry** | 8100 | Central service discovery for multi-host |
| **TensorZero Gateway** | 3030 | LLM gateway with observability |
| **TensorZero UI** | 4000 | Metrics dashboard for TensorZero |
| **PostgREST** | 3010 | REST API for Supabase |
| **Presign** | 8088 | MinIO URL presigner |

### Tier: Data (Databases & Storage)

Persistent storage and data services.

| Service | Port | Purpose |
|---------|------|---------|
| **Supabase (Postgres)** | 5432 | Primary database with pgvector |
| **Qdrant** | 6333 | Vector embeddings for semantic search |
| **Neo4j** | 7474 HTTP, 7687 Bolt | Knowledge graph storage |
| **Meilisearch** | 7700 | Full-text keyword search |
| **MinIO** | 9000 API, 9001 Console | S3-compatible object storage |
| **ClickHouse** | 8123 | Observability metrics storage |
| **SurrealDB** | 8000 | Open Notebook database |

### Tier: Worker (Background Processing)

Services that process data asynchronously.

| Service | Port | Purpose |
|---------|------|---------|
| **Extract Worker** | 8083 | Text embedding and indexing |
| **LangExtract** | 8084 | Language detection and NLP preprocessing |
| **Notebook Sync** | 8095 | Open Notebook synchronizer |
| **PDF Ingest** | 8092 | Document ingestion orchestrator |

### Tier: Media (Media Processing)

Services for audio, video, and image processing.

| Service | Port | Purpose |
|---------|------|---------|
| **PMOVES.YT** | 8077 | YouTube ingestion service |
| **FFmpeg Whisper** | 8078 | Media transcription (GPU) |
| **Media Video** | 8079 | Object/frame analysis (YOLO) |
| **Media Audio** | 8082 | Audio analysis (emotion/speaker) |
| **Ultimate TTS Studio** | 7861 | Multi-engine TTS (GPU) |
| **Flute Gateway** | 8055 HTTP, 8056 WebSocket | Prosodic TTS synthesis |

### Tier: Research (Advanced AI)

Services for complex research and knowledge tasks.

| Service | Port | Purpose |
|---------|------|---------|
| **Hi-RAG Gateway v2** | 8086 CPU, 8087 GPU | Hybrid RAG with reranking |
| **DeepResearch** | 8098 | LLM-based research planner |
| **SupaSerch** | 8099 | Multimodal holographic deep research |

### Tier: Integration (Third-Party)

Services for integrating with external platforms.

| Service | Port | Purpose |
|---------|------|---------|
| **Jellyfin Bridge** | 8093 | Jellyfin metadata webhook |
| **Publisher Discord** | 8094 | Discord notification bot |
| **Render Webhook** | 8085 | ComfyUI render callback |
| **n8n** | 5678 | Workflow automation |
| **BoTZ Gateway** | 8090 | Geometry BUS integration |

### Tier: Monitoring (Observability)

Services for monitoring and logging.

| Service | Port | Purpose |
|---------|------|---------|
| **NATS** | 4222 | Message bus with JetStream |
| **Prometheus** | 9090 | Metrics scraping |
| **Grafana** | 3000 | Dashboard visualization |
| **Loki** | 3100 | Log aggregation |
| **cAdvisor** | 8080 | Container metrics |

## Deployment Modes

### Docked Mode (Production)

All services run integrated on a single host:

```bash
make up                    # Start all services
make up-agents-ui          # Start agents + UI
make up-workers            # Start worker services
```

**Characteristics:**
- Shared Supabase database
- Shared MinIO storage
- Central NATS message bus
- Full observability stack

### Standalone Mode (Edge)

Selected services run independently:

```bash
SERVICE_MODE=standalone make up
```

**Characteristics:**
- Service registry for discovery
- NATS for cross-host communication
- Local SQLite/database
- Announces to mesh via `mesh.node.announce.v1`

## Communication Patterns

### 1. NATS Message Bus

All services communicate via NATS subjects:

| Subject Pattern | Purpose |
|----------------|---------|
| `mesh.node.announce.v1` | Service announcements |
| `service.registry.*` | Registry events |
| `ingest.file.added.v1` | New file ingestion |
| `ingest.transcript.ready.v1` | Transcript ready |
| `claude.code.tool.executed.v1` | Claude CLI events |
| `research.deepresearch.*` | Research coordination |

### 2. REST APIs

Services expose REST APIs for direct access:

- **TensorZero**: `POST /v1/chat/completions`
- **Service Registry**: `GET /api/services`
- **Hi-RAG v2**: `POST /hirag/query`
- **Agent Zero**: `POST /mcp/command`

### 3. MCP (Model Context Protocol)

Agent Zero exposes MCP API:
- **Endpoint**: `/mcp/*` on port 8080
- **Used by**: Archon, custom agents
- **Purpose**: Agent coordination and tool execution

## Service Dependencies

### Critical Path

```
postgres → postgrest → nats → tensorzero → agent-zero → hirag-v2
```

### Storage Dependencies

```
supabase (postgres) ← All services requiring metadata
minio ← All media services
qdrant ← RAG services
neo4j ← Knowledge services
meilisearch ← Search services
```

### Message Bus Dependencies

```
nats (with jetstream) ← All services for events
service-registry ← Mesh Agent for registration
```

## Data Flow

### 1. Ingestion Pipeline

```
PMOVES.YT → MinIO → FFmpeg Whisper → Media Analyzers → Supabase
                                            ↓
                                         Extract Worker
                                            ↓
                                  Qdrant + Meilisearch
```

### 2. RAG Query Flow

```
Agent Zero → Hi-RAG v2 → Qdrant (vectors)
                         → Neo4j (graph)
                         → Meilisearch (text)
                         → Rerank (cross-encoder)
                         → Response
```

### 3. Agent Coordination

```
User Query → Archon → Agent Zero MCP → Task Execution
                        ↓
                   NATS events
                        ↓
                   Service Registry (discovery)
```

## Service Health

All services expose health endpoints:

| Service | Health Endpoint |
|---------|-----------------|
| Most HTTP services | `/healthz` |
| Gradio (TTS Studio) | `/gradio_api/info` |
| Qdrant | `/readyz` |
| Meilisearch | `/health` |
| Postgres | `pg_isready` |
| NATS | TCP socket check |

## Configuration

### Environment Tiers

Configuration is organized into tiers:

| File | Purpose |
|------|---------|
| `env.shared` | Shared configuration (all tiers) |
| `env.tier-api` | API service configuration |
| `env.tier-agent` | Agent service configuration |
| `env.tier-data` | Database configuration |
| `env.tier-llm` | LLM provider keys |
| `env.tier-media` | Media service configuration |
| `env.tier-ui` | UI configuration |
| `env.tier-worker` | Worker configuration |

### Service Discovery

- **Service Registry**: Central discovery hub
- **Mesh Agent**: Announces presence every 15 seconds
- **Tailscale**: Zero-VPN for multi-host
- **NATS TLS**: Encrypted direct connection

## Scaling

### Horizontal Scaling

Services that can scale horizontally:
- Agent Zero (multiple instances with different IDs)
- Hi-RAG Gateway (multiple instances with load balancing)
- Extract Worker (concurrent processing)
- Media analyzers (GPU distribution)

### Vertical Scaling

Services that benefit from more resources:
- Hi-RAG GPU variant (more GPU memory)
- FFmpeg Whisper (faster with GPU)
- Qdrant (larger index capacity)

## See Also

- `docs/DOCKING_ARCHITECTURE.md` - Docking architecture details
- `docs/MULTI_HOST_DISCOVERY.md` - Multi-host setup guide
- `docs/DYNAMIC_PORTS_GUIDE.md` - Port management
- `pmoves/docker-compose.yml` - Service definitions
