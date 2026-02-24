# PMOVES.AI Service Topology

> **A user-facing guide to the PMOVES.AI platform architecture.**
> Last updated: 2026-02-23

---

## What is PMOVES.AI?

PMOVES.AI is a **multi-agent orchestration platform** that coordinates autonomous AI agents, knowledge retrieval, voice synthesis, media processing, and document intelligence through a unified event-driven architecture. Think of it as a private AI operating system — every capability (search, voice, vision, memory, code execution) is a service that agents can call, and NATS is the nervous system connecting them all.

---

## The 7 Service Tiers

Every service in PMOVES.AI belongs to one of seven tiers. Tiers define the service's role, security posture, and resource profile.

### Tier Map

```
┌─────────────────────────────────────────────────────────────────┐
│                          UI TIER                                │
│  PMOVES-MAI-UI · Pmoves-hyperdimensions · TensorZero UI        │
│  Archon UI · Agent Zero UI · Grafana                           │
├─────────────────────────────────────────────────────────────────┤
│                         AGENT TIER                              │
│  Agent Zero · Archon · Mesh Agent · Cipher Memory              │
│  Channel Monitor · BoTZ MCP Gateway                            │
├─────────────────────────────────────────────────────────────────┤
│                         LLM TIER                                │
│  TensorZero Gateway · ClickHouse · DeepResearch · SupaSerch    │
├─────────────────────────────────────────────────────────────────┤
│                        WORKER TIER                              │
│  Extract Worker · LangExtract · Notebook Sync                  │
│  PDF Ingest · Render Webhook · Publisher-Discord                │
├─────────────────────────────────────────────────────────────────┤
│                        MEDIA TIER                               │
│  PMOVES.YT · FFmpeg-Whisper · Media-Video · Media-Audio        │
│  Flute-Gateway · Pipecat · Ultimate-TTS · Jellyfin Bridge      │
├─────────────────────────────────────────────────────────────────┤
│                         API TIER                                │
│  Hi-RAG v2 · Presign · n8n Workflows                           │
├─────────────────────────────────────────────────────────────────┤
│                        DATA TIER                                │
│  Supabase/Postgres · NATS · Qdrant · Neo4j · Meilisearch       │
│  MinIO · SurrealDB (Open Notebook)                             │
└─────────────────────────────────────────────────────────────────┘
```

| Tier | Purpose | Security Posture |
|------|---------|-----------------|
| **data** | Persistent storage (databases, message bus, object store) | Network-isolated, no public exposure |
| **api** | Stateless request handlers, search gateways | JWT auth, rate limiting |
| **llm** | Model inference, embeddings, research planning | Bearer auth, token tracking |
| **worker** | Background jobs (indexing, sync, webhooks) | Internal-only, shared secrets |
| **media** | Audio/video processing, transcription, TTS | GPU resources, file I/O |
| **agent** | Orchestration, MCP coordination, memory | JWT + MCP token auth |
| **ui** | Dashboards, visualization, user interfaces | Browser-facing, CORS |

---

## Data Flow Narratives

### Flow 1: Knowledge Query (Agent → RAG → LLM → Response)

```
User ──► Agent Zero ──► Hi-RAG v2 ──► TensorZero ──► Response
              │              │              │
              │         ┌────┴────┐         │
              │      Qdrant  Neo4j  Meili   │
              │              │              │
              └──────── NATS events ────────┘
```

1. User submits a query to **Agent Zero** (port 8080)
2. Agent Zero delegates to **Hi-RAG v2** (port 8086) for hybrid retrieval
3. Hi-RAG combines results from Qdrant (vectors), Neo4j (graph), and Meilisearch (full-text)
4. Cross-encoder reranking produces the top-K results
5. Results + query go to **TensorZero** (port 3030) for LLM completion
6. TensorZero routes to the best model provider and logs to ClickHouse
7. Response returns to the user; NATS events record the interaction

### Flow 2: YouTube Ingestion (URL → Transcribe → Index → Searchable)

```
URL ──► PMOVES.YT ──► MinIO ──► FFmpeg-Whisper ──► Extract Worker ──► Hi-RAG
             │                        │                    │
             └──── NATS: ingest.file.added.v1 ────────────┘
                   NATS: ingest.transcript.ready.v1
```

1. YouTube URL submitted to **PMOVES.YT** (port 8077)
2. Video downloaded to **MinIO** object storage
3. **FFmpeg-Whisper** (port 8078) transcribes the audio
4. NATS event `ingest.transcript.ready.v1` triggers **Extract Worker** (port 8083)
5. Extract Worker generates embeddings and indexes into Qdrant + Meilisearch
6. Content is now searchable via **Hi-RAG v2**
7. **Publisher-Discord** (port 8094) announces the new content

### Flow 3: Voice Interaction (Speech → Pipeline → TTS → Audio)

```
Voice ──► Flute-Gateway ──► Pipecat Pipeline ──► Ultimate-TTS ──► Audio
               │                    │                   │
           WebSocket            Frames              Synthesis
           (port 8056)        Processing           (port 7861)
```

1. Voice input arrives at **Flute-Gateway** via WebSocket (port 8056)
2. **Pipecat** frame pipeline processes the audio stream
3. STT produces text, which routes through the agent pipeline
4. Agent response text goes to **Ultimate-TTS-Studio** (port 7861)
5. Prosodic synthesis produces natural-sounding audio
6. Audio streams back to the user via WebSocket
7. NATS events on `voice.agent.*` subjects track the session

### Flow 4: Document Intelligence (PDF → Extract → Graph → Visualize)

```
PDF ──► DoX (PDF Ingest lane) ──► Extract Worker ──► Qdrant + Meilisearch
                                     │
                              Neo4j (entities)
                                     │
                         Hyperdimensions (visualize)
```

1. Document uploaded or discovered by **DoX** document intelligence
2. **DoX Document Intelligence (PDF Ingest lane)** (port 8092) orchestrates processing from MinIO
3. **Extract Worker** generates embeddings and entity extractions
4. Vectors go to Qdrant, full-text to Meilisearch, entities to Neo4j
5. **Hyperdimensions** visualizes the knowledge graph on a Poincare disk
6. CHIT geometry state vector drives the visualization surface

---

## Service Connection Map

This table shows which services communicate with which, and via what protocol.

| Source | Target | Protocol | Subject/Endpoint |
|--------|--------|----------|-----------------|
| Agent Zero | Hi-RAG v2 | HTTP | `POST /hirag/query` |
| Agent Zero | TensorZero | HTTP | `POST /v1/chat/completions` |
| Agent Zero | NATS | NATS | Task coordination subjects |
| Agent Zero | Supabase | HTTP | State storage |
| Archon | Agent Zero | HTTP/MCP | `POST /mcp/*` |
| Archon | Supabase | HTTP | Prompt/form storage |
| BoTZ Gateway | MCP Servers | stdio/HTTP/SSE | Tool routing |
| Channel Monitor | PMOVES.YT | HTTP | `POST /yt/ingest` |
| DeepResearch | NATS | NATS | `research.deepresearch.*` |
| DeepResearch | TensorZero | HTTP | LLM calls |
| DeepResearch | Open Notebook | HTTP | Result storage |
| Extract Worker | Qdrant | HTTP | Vector indexing |
| Extract Worker | Meilisearch | HTTP | Full-text indexing |
| Extract Worker | TensorZero | HTTP | Embeddings |
| FFmpeg-Whisper | MinIO | S3 | Read/write media |
| Flute-Gateway | Ultimate-TTS | HTTP | TTS synthesis |
| Flute-Gateway | NATS | NATS | Voice events |
| Hi-RAG v2 | Qdrant | HTTP | Vector search |
| Hi-RAG v2 | Neo4j | Bolt | Graph traversal |
| Hi-RAG v2 | Meilisearch | HTTP | Full-text search |
| Notebook Sync | Open Notebook | HTTP | SurrealDB polling |
| Notebook Sync | Extract Worker | HTTP | Re-indexing |
| DoX Document Intelligence (PDF Ingest lane) | MinIO | S3 | Document storage |
| DoX Document Intelligence (PDF Ingest lane) | Extract Worker | HTTP | Indexing |
| PMOVES.YT | MinIO | S3 | Video storage |
| PMOVES.YT | NATS | NATS | `ingest.file.added.v1` |
| Publisher-Discord | NATS | NATS | `ingest.*.v1` subjects |
| SupaSerch | DeepResearch | NATS | Research orchestration |
| SupaSerch | NATS | NATS | `supaserch.*` |

---

## Submodule Purpose Directory

All submodules grouped by function with a one-line description.

### Agent Coordination

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-Agent-Zero** | Control-plane orchestrator with embedded agent runtime and MCP API |
| **PMOVES-Archon** | Supabase-driven agent service with prompt/form management |
| **PMOVES-BoTZ** | Unified multi-agent MCP tools ecosystem (Docling, Cipher, E2B, VL Sentinel) |
| **Pmoves-cipher** | Knowledge-graph persistent memory for agents (Neo4j backend) |

### Knowledge & Search

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-HiRAG** | Hybrid RAG combining vector, graph, and full-text search with cross-encoder reranking |
| **PMOVES-Deep-Serch** | Deep research service — LLM-based research planner + multimodal search orchestrator |
| **PMOVES-Open-Notebook** | Knowledge base and note-taking integration (SurrealDB) |

### Voice & Media

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-Pipecat** | Real-time voice and multimodal conversational AI framework |
| **PMOVES-Ultimate-TTS-Studio** | Multi-engine TTS with 7 synthesis engines (Kokoro, F5-TTS, etc.) |
| **PMOVES.YT** | YouTube video ingestion, transcript retrieval, and MinIO storage |
| **Pmoves-Jellyfin-AI-Media-Stack** | AI media processing: Whisper, YOLO, audio analysis, embeddings |
| **PMOVES-Jellyfin** | Jellyfin media server bridge — event sync to Supabase |
| **PMOVES-transcribe-and-fetch** | Media transcription and content fetching pipeline |

### Document Intelligence

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-DoX** | Document intelligence platform — extract, analyze, structure data from PDFs, spreadsheets, logs |

### Content Creation

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-Creator** | ComfyUI visual AI engine for Stable Diffusion image generation workflows |

### LLM Infrastructure

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-tensorzero** | Centralized LLM gateway with ClickHouse observability |

### Data & Infrastructure

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-supabase** | Postgres database with pgvector extension |
| **PMOVES-Tailscale** | WireGuard mesh VPN for secure service networking |
| **PMOVES-Remote-View** | Self-hosted RustDesk remote desktop server |
| **PMOVES-Headscale** | Open-source Tailscale coordination server |

### Visualization & CHIT

| Submodule | Purpose |
|-----------|---------|
| **Pmoves-hyperdimensions** | Poincare disk visualization surface driven by CHIT geometry state vectors |
| **PMOVES-ToKenism-Multi** | Token economy simulator with CHIT smart contract integration |

### Personal Tools

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-Wealth** | Firefly III personal finance manager with Supabase sync |
| **Pmoves-Health-wger** | Wger workout and nutrition tracker with CGP reporting |

### Workflow & Automation

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-n8n** | n8n workflow automation — Discord publishing, health/finance reports, content approval |

### Development & Research

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-crush** | Terminal-based AI coding assistant (Charm Crush) |
| **PMOVES-MAI-UI** | Main AI user interface frontend |
| **PMOVES-A2UI** | UI generation research platform |
| **PMOVES-AgentGym** | Agent training framework (THUDM) |
| **Pmoves-AgentGym-RL** | Reinforcement learning for agent training |
| **PMOVES-llama-throughput-lab** | LLM throughput benchmarking |

### E2B Sandbox Ecosystem

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-E2B-Danger-Room** | E2B code sandbox runtime |
| **PMOVES-E2B-Danger-Room-Desktop** | E2B desktop sandbox environment |
| **PMOVES-Danger-infra** | E2B infrastructure tooling |
| **PMOVES-E2b-Spells** | E2B sandbox recipes and fragments |
| **pmoves-e2b-mcp-server** | E2B MCP server for sandboxed code execution |
| **PMOVES-surf / pmoves-surf** | Browser automation in E2B sandbox |

### Pinokio Launchers

| Submodule | Purpose |
|-----------|---------|
| **PMOVES-Pinokio-Ultimate-TTS-Studio** | One-click Pinokio launcher for Ultimate-TTS-Studio |

---

## Docker Compose Profiles

Services are organized into profiles for selective deployment.

| Profile | Services | Use Case |
|---------|----------|----------|
| `agents` | Agent Zero, Archon, Mesh Agent, Cipher | Agent orchestration |
| `workers` | Extract, LangExtract, Media analyzers | Background processing |
| `orchestration` | SupaSerch, DeepResearch | Research planning |
| `yt` | PMOVES.YT, Channel Monitor | YouTube ingestion |
| `gpu` | Ultimate-TTS, FFmpeg-Whisper, Media-Video | GPU-accelerated services |
| `monitoring` | Prometheus, Grafana, Loki, Promtail, cAdvisor | Observability stack |

**Start a profile:**
```bash
docker compose --profile agents --profile workers up -d
```

---

## Cross-References

- **Service Catalog (detailed):** `.claude/context/services-catalog.md`
- **Submodule Catalog:** `.claude/context/submodules.md`
- **NATS Subject Catalog:** `.claude/context/nats-subjects.md`
- **Integration Guide:** `pmoves/docs/integrations/INTEGRATIONS.md`
- **Integration Checklist:** `pmoves/docs/integrations/INTEGRATION_CHECKLIST.md`
- **Security Patterns:** `.claude/context/security-patterns.md`
- **Observability Patterns:** `.claude/context/observability-patterns.md`
