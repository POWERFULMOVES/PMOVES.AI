# PMOVES.AI Port Registry

Central registry of all service ports to prevent conflicts and ensure consistency.

**Last Updated:** 2026-01-13

## Port Allocation Ranges

| Range | Purpose | Examples |
|-------|---------|----------|
| 3000-3999 | Web UIs | Grafana 3002, PostgREST 3000 |
| 4000-4999 | Debug/Admin | TensorZero UI 4000 |
| 5000-5999 | Databases | Postgres 5432*, ClickHouse 8123† |
| 6000-6999 | Vector/Search | Qdrant 6333, Neo4j 7474/7687 |
| 7000-7999 | Core Services | Meilisearch 7700, Ollama 11434‡ |
| 8000-8199 | Agent/Worker Services | Agent Zero 8080, Workers 8077-8104 |
| 8200-8999 | Orchestration Services | Tokenism 8103, Evo 8113 |
| 9000-9999 | Infrastructure | Prometheus 9090, NATS 4222‡ |

*Postgres uses standard 5432
†ClickHouse uses non-standard 8123 (outside range)
‡Services with standard ports keep their defaults

## Assigned Ports

### Core Infrastructure (Tier 0)

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| 3002 | 3000 | Grafana | `GRAFANA_HOST_PORT` | Metrics visualization |
| 3030 | 3000 | TensorZero Gateway | `TENSORZERO_PORT` | LLM gateway (3030:3000) |
| 3100 | 3100 | Loki | `LOKI_HOST_PORT` | Log aggregation |
| 4000 | 4000 | TensorZero UI | - | Metrics dashboard |
| 4222 | 4222 | NATS | `NATS_PORT` | Message broker (JetStream) |
| 8123 | 8123 | ClickHouse | - | TensorZero observability |
| 9090 | 9090 | Prometheus | `PROMETHEUS_HOST_PORT` | Metrics scraping |
| 9115 | 9115 | Blackbox Exporter | `BLACKBOX_HOST_PORT` | HTTP probing |
| 9180 | 8080 | cAdvisor | `CADVISOR_HOST_PORT` | Container metrics |

### Data Storage (Tier 1)

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| 5432 | 5432 | PostgreSQL (Supabase) | - | Primary database |
| 54321 | 54321 | Supabase Kong | - | API gateway (CLI) |
| 54322 | 54322 | Supabase DB | - | Database (CLI) |
| 6333 | 6333 | Qdrant | `QDRANT_PORT` | Vector embeddings |
| 7474 | 7474 | Neo4j HTTP | `NEO4J_HTTP_PORT` | Knowledge graph UI |
| 7687 | 7687 | Neo4j Bolt | `NEO4J_BOLT_PORT` | Knowledge graph protocol |
| 7700 | 7700 | Meilisearch | `MEILISEARCH_PORT` | Full-text search |
| 9000 | 9000 | MinIO API | `MINIO_PORT` | S3-compatible storage |
| 9001 | 9001 | MinIO Console | `MINIO_CONSOLE_PORT` | Storage web UI |
| 11434 | 11434 | Ollama | - | Local LLM inference |

### Core Services (Tier 2)

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| 3737 | 3737 | Archon UI | - | Agent framework UI |
| 7861 | 7861 | Ultimate TTS Studio | - | Multi-engine TTS (Gradio) |
| 8054 | 8054 | Flute Gateway (alt) | - | Voice/TTS layer |
| 8055 | 8055 | Flute Gateway HTTP | - | TTS API |
| 8056 | 8056 | Flute Gateway WebSocket | - | Real-time audio |
| 8077 | 8077 | PMOVES.YT | `PMOVES_YT_PORT` | YouTube ingestion |
| 8078 | 8078 | FFmpeg-Whisper | - | Media transcription |
| 8079 | 8079 | Media-Video Analyzer | - | YOLO video analysis |
| 8080 | 8080 | Agent Zero | `AGENT_ZERO_PORT` | Agent orchestrator API |
| 8081 | 8081 | Agent Zero UI | - | Agent orchestrator web UI |
| 8082 | 8082 | Media-Audio Analyzer | - | Audio emotion detection |
| 8083 | 8083 | Extract Worker | - | Text embedding/indexing |
| 8084 | 8084 | LangExtract | - | NLP preprocessing |
| 8085 | 8085 | Render Webhook | - | ComfyUI callback handler |
| 8086 | 8086 | Hi-RAG Gateway v2 (CPU) | `HIRAG_V2_HOST_PORT` | **PREFERRED** |
| 8087 | 8086 | Hi-RAG Gateway v2 (GPU) | `HIRAG_V2_GPU_HOST_PORT` | GPU reranking |
| 8088 | 8088 | Presign | - | MinIO URL presigner |
| 8091 | 8091 | Archon | `ARCHON_PORT` | Supabase agent service |
| 8092 | 8092 | PDF Ingest | - | Document ingestion |
| 8093 | 8093 | Jellyfin Bridge | - | Media metadata sync |
| 8094 | 8094 | Publisher-Discord | - | Discord notification bot |
| 8095 | 8095 | Notebook Sync | - | SurrealDB sync |
| 8097 | 8097 | Channel Monitor | - | External content watcher |
| 8098 | 8098 | DeepResearch | `DEEPRESEARCH_PORT` | Research planner |
| 8099 | 8099 | SupaSerch | `SUPASERCH_PORT` | Multimodal search |
| 8110 | 8110 | Model Registry | `MODEL_REGISTRY_PORT` | Dynamic model configuration |

### Agent/Worker Services (Tier 3)

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| 8100 | 8100 | Gateway Agent | - | MCP tools (profile: agents) |
| 8100 | 8100 | Session Context Worker | - | Context transformation |
| 8101 | 8101 | Messaging Gateway | - | NATS message relay |
| 8102 | 8102 | Chat Relay | - | Agent chat relay |
| 8103 | 8100 | Tokenism UI API | `TOKENISM_HOST_PORT` | CHIT geometry simulator |
| **8104** | **8104** | **GitHub Runner Controller** | **PORT** | **CI/CD runners** |
| **8111** | **8090** | **Retrieval Eval** | `RETRIEVAL_EVAL_PORT` | RAG evaluation benchmarks |
| 8113 | 8113 | Evo Controller | - | Evolutionary controller |

### Orchestration Services (Tier 4)

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| **8200** | **8200** | **Tokenism Simulator** | - | CHIT geometry engine |
| 8113 | 8113 | Evo Controller | - | Evolutionary controller |

### External Integrations

| Host Port | Container Port | Service | Environment Variable | Notes |
|-----------|---------------|---------|---------------------|-------|
| 5678 | 5678 | n8n | - | Workflow automation |
| 8000 | 80 | WGER | `WGER_HOST_PORT` | Health/fitness tracking |
| 8082 | 8080 | Firefly III | `FIREFLY_PORT` | Finance manager |
| 8096 | 8096 | Jellyfin | - | Media server |
| 8503 | 8502 | Open Notebook UI | `OPEN_NOTEBOOK_UI_PORT` | Note-taking UI |
| 5055 | 5055 | Open Notebook API | `OPEN_NOTEBOOK_API_PORT` | REST API |

## Port Assignment Guidelines

1. **Check the registry first** - Always search this file before assigning a new port
2. **Use range allocation** - Stay within the appropriate range for the service tier
3. **Use environment variables** - Always define `PORT=${SERVICE_PORT:-DEFAULT}` for flexibility
4. **Document conflicts** - If a port must be shared, document the profile separation
5. **Don't hardcode in Dockerfiles** - Use `ENV PORT=${PORT:-default}` pattern
6. **Update Prometheus** - When changing ports, update `monitoring/prometheus/prometheus.yml`
7. **Update healthchecks** - Health check URLs must match the assigned port

## Conflict Resolution

### ✅ Port 8100 → 8104 (Resolved 2026-01-13)

**Issue:** Multiple services used port 8100
- session-context-worker: 8100 (profile: `workers,orchestration`)
- gateway-agent: 8100 (profile: `agents`)
- tokenism: 8100 (profile: `agents`)
- github-runner-ctl: 8100 → **Changed to 8104**

**Root Cause:** Dockerfile had hardcoded `ENV PORT=8100` preventing docker-compose override

**Fix Applied:**
1. Removed `ENV PORT=8100` from `services/github-runner-ctl/Dockerfile`
2. Added comment: `# PORT set at runtime via docker-compose`
3. Services now use different Docker Compose profiles to avoid conflicts

**Dockerfile Pattern (CORRECT):**
```dockerfile
# DON'T hardcode PORT in Dockerfile
# ENV PORT=8100  # ❌ This prevents runtime override

# DO use runtime override pattern
ENV PORT=${PORT:-8100}  # ✅ Allows docker-compose to override
```

## Adding a New Service

When adding a new service:

1. Choose an available port from the appropriate range
2. Add entry to this registry (use table format above)
3. Add Prometheus scrape config (if applicable)
4. Add healthcheck configuration
5. Update environment variable in appropriate `env.tier-*` file
6. **Don't hardcode ports in Dockerfiles**

Example (CORRECT):
```yaml
my-service:
  environment:
    - PORT=${MY_SERVICE_PORT:-8110}
  ports: ["8110:8110"]
```

Dockerfile (CORRECT):
```dockerfile
# DON'T do this:
# ENV PORT=8110

# DO this instead:
ENV PORT=${PORT:-8110}
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
```

## See Also

- [Tier Architecture](tier-architecture.md) - Network tier organization
- [Services Catalog](services-catalog.md) - Complete service listing
- [NATS Subjects](nats-subjects.md) - Message bus topics
- [LOCAL_DEV.md](LOCAL_DEV.md) - Local development port references
