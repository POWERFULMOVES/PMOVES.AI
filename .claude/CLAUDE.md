# PMOVES.AI Developer Context

**Always-on context for Claude Code CLI when working in the PMOVES.AI repository.**

## Architecture Overview

PMOVES.AI is a **production-ready multi-agent orchestration platform** featuring:
- Autonomous agent coordination via Agent Zero
- Hybrid RAG (Hi-RAG v2) combining vector, graph, and full-text search
- Multimodal holographic deep research (SupaSerch)
- Comprehensive observability (Prometheus, Grafana, Loki)
- Event-driven architecture via NATS message bus
- Media processing pipeline (YouTube, Whisper, YOLO)

## Production Services (DO NOT DUPLICATE - Use via APIs)

### Core Infrastructure

**TensorZero Gateway** [Port 3030] **[PRIMARY MODEL PROVIDER & OBSERVABILITY]**
- Centralized LLM gateway for all model providers (OpenAI, Anthropic, Venice, Ollama)
- ClickHouse-backed observability and metrics collection
- Request/response logging, token tracking, latency metrics
- UI dashboard at port 4000
- API: `http://localhost:3030/v1/chat/completions` or `/v1/embeddings`
- **Use for:** All LLM calls, embeddings, model provider routing, usage analytics
- **See:** `.claude/context/tensorzero.md` for detailed documentation

**TensorZero ClickHouse** [Port 8123]
- Observability metrics storage for TensorZero
- Stores request logs, token usage, latency data
- Query: `curl http://localhost:8123/ping`

**TensorZero UI** [Port 4000]
- Metrics dashboard and admin interface
- Request/response inspection, usage analytics
- Access: `http://localhost:4000`

### Agent Coordination & Orchestration

**Agent Zero** [Port 8080 API, 8081 UI]
- Control-plane orchestrator with embedded agent runtime
- Exposes MCP API at `/mcp/*` for external agent integration
- Subscribes to NATS for task coordination
- Health: `GET http://localhost:8080/healthz`
- **Use for:** Agent orchestration, MCP commands, task delegation

**Mesh Agent** [No HTTP interface]
- Distributed node announcer for multi-host orchestration
- Announces host presence/capabilities on NATS every 15s

**Archon** [Port 8091 API, 3737 UI]
- Supabase-driven agent service with prompt/form management
- Connects to Agent Zero's MCP interface
- Health: `GET http://localhost:8091/healthz`
- **Use for:** Agent form management, Supabase-backed prompts

**Channel Monitor** [Port 8097]
- External content watcher (YouTube channels, etc.)
- Triggers ingestion when new content detected
- Posts to PMOVES.YT `/yt/ingest` endpoint

### Retrieval & Knowledge Services

**Hi-RAG Gateway v2** [Port 8086 CPU, 8087 GPU] **[PREFERRED]**
- Next-gen hybrid RAG with cross-encoder reranking
- Combines: Qdrant (vectors) + Neo4j (graph) + Meilisearch (full-text)
- API: `POST http://localhost:8086/hirag/query`
- Request: `{"query": "...", "top_k": 10, "rerank": true}`
- **Use for:** Knowledge retrieval, semantic search, RAG queries

**Hi-RAG Gateway v1** [Port 8089 CPU, 8110 GPU] **[LEGACY]**
- Original hybrid RAG implementation
- Use v2 instead for new features

**DeepResearch** [Port 8098]
- LLM-based research planner (Alibaba Tongyi DeepResearch)
- NATS worker: publishes to `research.deepresearch.request.v1`
- Auto-publishes results to Open Notebook
- **Use for:** Complex research tasks, multi-step planning

**SupaSerch** [Port 8099]
- Multimodal holographic deep research orchestrator
- Coordinates DeepResearch, Archon/Agent Zero MCP tools
- NATS: `supaserch.request.v1` / `supaserch.result.v1`
- Metrics: `GET http://localhost:8099/metrics`
- **Use for:** Complex multi-source research, search aggregation

**Open Notebook** [External - SurrealDB]
- Knowledge base / note-taking integration
- Access via `OPEN_NOTEBOOK_API_URL` + API token
- Used by DeepResearch for persistent storage

### Voice & Speech Services

**Flute-Gateway** [Port 8055 HTTP, 8056 WebSocket]
- Multimodal voice communication layer with Pipecat integration
- Prosodic synthesis with natural pauses and emphasis
- WebSocket streaming for real-time audio
- API: `POST http://localhost:8055/v1/voice/synthesize/prosodic`
- Health: `GET http://localhost:8055/healthz`
- **Use for:** TTS synthesis, real-time voice sessions, audio streaming
- **See:** `.claude/context/flute-gateway.md` for API reference

**Ultimate-TTS-Studio** [Port 7861]
- Multi-engine TTS with 7 engines (Kokoro, F5-TTS, KittenTTS, VoxCPM, etc.)
- Gradio web interface for interactive synthesis
- GPU-accelerated (CUDA 12.4)
- Health: `GET http://localhost:7861/gradio_api/info`
- **Use for:** High-quality TTS, voice cloning, multi-language synthesis

### Media Ingestion & Processing

**PMOVES.YT** [Port 8077]
- YouTube ingestion service
- Downloads videos to MinIO, retrieves transcripts
- API: `POST http://localhost:8077/yt/ingest`
- Publishes NATS events when transcripts ready

**FFmpeg-Whisper** [Port 8078]
- Media transcription (OpenAI Whisper with GPU)
- Uses Faster-Whisper backend, model: small
- Reads/writes to MinIO

**Media-Video Analyzer** [Port 8079]
- Object/frame analysis with YOLOv8
- Frame sampling: every 5th frame, confidence: 0.25
- Outputs to Supabase

**Media-Audio Analyzer** [Port 8082]
- Audio analysis (emotion/speaker detection)
- Model: superb/hubert-large-superb-er

**Extract Worker** [Port 8083]
- Text embedding & indexing service
- Indexes to Qdrant (vectors) + Meilisearch (full-text)
- Model: all-MiniLM-L6-v2
- API: `POST http://localhost:8083/ingest`

**PDF Ingest** [Port 8092]
- Document ingestion orchestrator
- Processes PDFs from MinIO, sends to extract-worker

**LangExtract** [Port 8084]
- Language detection and NLP preprocessing
- Used by notebook sync for text analysis

**Notebook Sync** [Port 8095]
- SurrealDB Open Notebook synchronizer
- Polling interval: 300s
- Calls LangExtract + Extract Worker for indexing

### Utility & Integration Services

**Presign** [Port 8088]
- MinIO URL presigner for short-lived download URLs
- Requires `PRESIGN_SHARED_SECRET` for API access
- Allowed buckets: assets, outputs

**Render Webhook** [Port 8085]
- ComfyUI render callback handler
- Requires `RENDER_WEBHOOK_SHARED_SECRET`
- Writes to Supabase, stores to MinIO

**Publisher-Discord** [Port 8094]
- Discord notification bot
- Listens on NATS subjects:
  - `ingest.file.added.v1`
  - `ingest.transcript.ready.v1`
  - Summary/chapter ready events

**Jellyfin Bridge** [Port 8093]
- Jellyfin metadata webhook & helper
- Syncs Jellyfin events to Supabase

### Monitoring Stack

**Prometheus** [Port 9090]
- Metrics scraping from all services
- All services expose `/metrics` endpoints
- **Use for:** Querying metrics, service monitoring

**Grafana** [Port 3000]
- Dashboard visualization
- Datasources: Prometheus, Loki
- Pre-configured "Services Overview" dashboard

**Loki** [Port 3100] + **Promtail**
- Centralized log aggregation
- All services configured with Loki labels

**cAdvisor** [Port 8080]
- Container metrics for Prometheus

### Data Storage

**NATS Message Bus** [Port 4222]
- JetStream-enabled event broker
- Primary communication bus for all agent coordination
- **Critical subjects:** See `.claude/context/nats-subjects.md`

**Supabase** [PostgREST Port 3010]
- Postgres with pgvector extension
- Schema: `pmoves_core`, Archon prompts
- **Use for:** Metadata storage, content records, agent state

**Qdrant** [Port 6333]
- Vector embeddings for semantic search
- Collection: `pmoves_chunks`

**Neo4j** [Port 7474 HTTP, 7687 Bolt]
- Knowledge graph storage
- Entity relationships, graph traversal

**Meilisearch** [Port 7700]
- Full-text keyword search
- Typo-tolerant, substring search

**MinIO** [Port 9000 API, 9001 Console]
- S3-compatible object storage
- Buckets: `assets`, `outputs`
- Stores: videos, audio, images, analysis results

## NATS Event Subjects (Event-Driven Architecture)

**Research & Search:**
- `research.deepresearch.request.v1` / `research.deepresearch.result.v1`
- `supaserch.request.v1` / `supaserch.result.v1`

**Media Ingestion:**
- `ingest.file.added.v1` - New file ingested
- `ingest.transcript.ready.v1` - Transcript completed
- `ingest.summary.ready.v1` - Summary generated
- `ingest.chapters.ready.v1` - Chapter markers created

**Agent Observability (for Claude Code CLI hooks):**
- `claude.code.tool.executed.v1` - Claude CLI tool execution events

## Common Development Tasks

### Call LLMs via TensorZero
```bash
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Generate Embeddings via TensorZero
```bash
curl -X POST http://localhost:3030/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma_embed_local", "input": "Text to embed"}'
```

### Query TensorZero Metrics (ClickHouse)
```bash
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero \
  --query "SELECT model, COUNT(*) FROM requests GROUP BY model"
```

### Query Knowledge Base
```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "your question", "top_k": 10, "rerank": true}'
```

### Check Service Health
```bash
# Single service
curl http://localhost:8080/healthz  # Agent Zero

# All services
make verify-all
```

### Publish NATS Event
```bash
nats pub "subject.name.v1" '{"key": "value"}'
```

### Query Prometheus Metrics
```bash
curl http://localhost:9090/api/v1/query?query=up
```

### Call Agent Zero MCP API
```bash
curl -X POST http://localhost:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{"command": "..."}'
```

## Development Patterns

### Integration Pattern: Leverage, Don't Duplicate
- **DO:** Use Hi-RAG v2 for knowledge retrieval
- **DO:** Publish to NATS for event coordination
- **DO:** Store artifacts in MinIO via Presign
- **DO:** Call Agent Zero MCP API for orchestration
- **DON'T:** Build new RAG, search, or monitoring systems
- **DON'T:** Create new event buses or message brokers
- **DON'T:** Duplicate existing embeddings or indexing

### Service Discovery Pattern
All services expose:
- `/healthz` - Health check endpoint
- `/metrics` - Prometheus metrics (most services)

### Error Handling Pattern
Services use NATS for async error reporting:
- Check service logs via Loki at http://localhost:3100
- Monitor health via Prometheus at http://localhost:9090
- View dashboards at Grafana http://localhost:3000

### Docker Compose Profiles
- `agents` - Agent Zero, Archon, Mesh Agent
- `workers` - Extract, LangExtract, media analyzers
- `orchestration` - SupaSerch, DeepResearch
- `yt` - PMOVES.YT ingestion
- `gpu` - GPU-enabled services
- `monitoring` - Prometheus, Grafana, Loki

**Start services:**
```bash
docker compose --profile agents --profile workers up -d
```

## MCP Integration Points

**Agent Zero MCP API** (`/mcp/*` on port 8080)
- External agents can call Agent Zero via MCP protocol
- Used by Archon for agent coordination
- Available for custom integrations

**Configuration:**
- Set `AGENTZERO_JETSTREAM=true` for reliable delivery
- Configure `MCP_SERVICE_URL`, `MCP_CLIENT_ID`, `MCP_CLIENT_SECRET`

## Git & CI Patterns

**Submodules (25 total):**
- Core: `PMOVES-Agent-Zero`, `PMOVES-Archon`, `PMOVES-BoTZ`, `PMOVES.YT`
- RAG/Research: `PMOVES-HiRAG`, `PMOVES-Deep-Serch`, `PMOVES-Open-Notebook`
- Media: `PMOVES-Jellyfin`, `PMOVES-Ultimate-TTS-Studio`, `PMOVES-Pipecat`
- Integration: `PMOVES-tensorzero`, `PMOVES-n8n`, `PMOVES-ToKenism-Multi`
- Plus health/wealth integrations and more
- **See:** `.claude/context/submodules.md` for complete catalog

**Security Posture (as of 2025-12-23):**
- CODEOWNERS: 24/24 (100%) - All submodules have code owners
- Dependabot: 24/24 (100%) - All submodules have automated security updates
- **See:** `.claude/learnings/submodule-security-audit-2025-12.md`

**CI/CD:**
- GitHub Actions for multi-arch builds (amd64, arm64)
- Self-hosted runners: ai-lab (GPU), vps (CPU), cloudstartup (staging), kvm4 (production)
- Published to GHCR + Docker Hub
- Smoke tests via `make verify-all`
- **See:** `.claude/context/ci-runners.md` for runner deployment

**Branch Strategy:**
- Main branch: `main`
- Feature branches: `feature/*`
- Hardened branches: `PMOVES.AI-Edition-Hardened` (in submodules)
- PR target: `main`

## Testing Workflow

### Before PR Submission
1. Run `/test:pr` to execute standard test suite
2. Copy generated Testing section to PR description
3. Ensure docstring coverage ≥80% on new/modified Python code

### Test Commands
| Command | Description |
|---------|-------------|
| `cd pmoves && make verify-all` | Full verification (smoke tests, health checks) |
| `/health:check-all` | Check all service health endpoints |
| `/test:pr` | PR testing workflow with documentation |
| `/deploy:smoke-test` | Deployment smoke tests |
| `pytest pmoves/tests/` | Integration tests |

### CI Requirements
- **CodeQL Analysis** - Security scanning (must pass)
- **CHIT Contract Check** - Schema validation (must pass)
- **SQL Policy Lint** - Migration validation (must pass)
- **CodeRabbit Review** - Docstring coverage ≥80%

See `.claude/context/testing-strategy.md` for detailed testing guidelines.

## UI Development Checklist

Based on CodeRabbit learnings (see `.claude/learnings/ui-error-handling-review-2025.md`):

### Security
- [ ] User identity from JWT only, never from request body/query params
- [ ] Proper base64url decoding for JWT payloads (`-` → `+`, `_` → `/`)
- [ ] No query parameter fallbacks that bypass authentication

### Privacy
- [ ] No PII (userId, email) in error logging interfaces
- [ ] Use `logError()` not raw `console.error` for production
- [ ] Generic user-facing error messages with digest IDs for support

### Accessibility (WCAG 2.1)
- [ ] Skip links as first focusable element (`sr-only focus:not-sr-only` pattern)
- [ ] Skip link target has `tabIndex={-1}` for programmatic focus
- [ ] ARIA live regions: `assertive` (critical errors) / `polite` (normal errors)
- [ ] Tailwind classes statically analyzable (use lookup objects, not interpolation)

### Code Quality
- [ ] Consistent error response shapes: `{ok, error}` or `{items, error}`
- [ ] HTTP status codes: 401 (auth failure), 400 (bad request), 500 (server error)
- [ ] Shared utilities extracted (no duplicate functions like `ownerFromJwt`)
- [ ] Unused imports removed

## Additional References

See `.claude/context/` for detailed documentation:
- `services-catalog.md` - Complete service listing with all details
- `submodules.md` - Complete submodules catalog (25 submodules)
- `ci-runners.md` - Self-hosted runner deployment and configuration
- `nats-subjects.md` - Comprehensive NATS subject catalog
- `geometry-nats-subjects.md` - GEOMETRY BUS NATS subjects (`tokenism.*`, `geometry.*`)
- `mcp-api.md` - Agent Zero MCP API reference
- `testing-strategy.md` - Testing workflow and PR requirements

**GEOMETRY BUS & CHIT Integration:**
- `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` - CGP integration guide
- `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md` - Mathematical foundations
- `pmoves/docs/PMOVESCHIT/Human_side.md` - User-facing CHIT documentation
- `PMOVES-ToKenism-Multi/integrations/contracts/chit/` - CHIT TypeScript modules

## Meta-Instruction for Claude Code CLI

When developing features for PMOVES.AI:
1. **Leverage existing services** - Don't rebuild what exists
2. **Use NATS for coordination** - Event-driven communication
3. **Expose health/metrics** - Follow observability patterns
4. **Check health first** - Always verify service status before use
5. **Consult context docs** - Reference `.claude/context/` for details
6. **Test before PR** - Run `/test:pr` and document results

PMOVES.AI is a sophisticated production system. Your role is to build features that integrate with this ecosystem, not replace it.
