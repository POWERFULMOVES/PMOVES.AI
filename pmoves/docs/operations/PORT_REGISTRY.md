# PMOVES.AI Port Registry

Central registry of all service ports to prevent conflicts and ensure consistency.

## Port Allocation Ranges

| Range | Purpose | Examples |
|-------|---------|----------|
| 3000-3999 | Web UIs | Grafana 3002 |
| 4000-4999 | Debug/Admin | TensorZero UI 4000 |
| 5000-5999 | Databases | Postgres 5432* |
| 6000-6999 | Vector/Search | Qdrant 6333, Meilisearch 7700† |
| 7000-7999 | Core Services | Agent Zero 8080‡ |
| 8000-8199 | Agent/Worker Services | session-context-worker 8100, gateway-agent 8100, github-runner-ctl 8104 |
| 8200-8999 | Orchestration Services | Archon 8181 |
| 9000-9999 | Infrastructure | Prometheus 9090, NATS 4222‡ |

*Postgres uses standard 5432
†Meilisearch uses standard 7700 (in 7000-7999 range)
‡Services with standard ports (NATS 4222, Agent Zero 8080) keep their defaults

## Assigned Ports

### Core Infrastructure (Tier 0)

| Port | Service | Description |
|------|---------|-------------|
| 3000 | Grafana | Metrics visualization |
| 3030 | TensorZero Gateway | LLM gateway |
| 3100 | Loki | Log aggregation |
| 4000 | TensorZero UI | Metrics dashboard |
| 4222 | NATS | Message broker (JetStream) |
| 9090 | Prometheus | Metrics scraping |

### Data Storage (Tier 1)

| Port | Service | Description |
|------|---------|-------------|
| 5432 | PostgreSQL (Supabase) | Primary database |
| 6333 | Qdrant | Vector embeddings |
| 7474 | Neo4j HTTP | Knowledge graph UI |
| 7687 | Neo4j Bolt | Knowledge graph protocol |
| 7700 | Meilisearch | Full-text search |
| 9000 | MinIO API | S3-compatible storage |
| 9001 | MinIO Console | Storage web UI |

### Core Services (Tier 2)

| Port | Service | Description |
|------|---------|-------------|
| 8055 | Flute Gateway | Voice/TTS layer |
| 8056 | Flute Gateway WebSocket | Real-time audio |
| 8077 | PMOVES.YT | YouTube ingestion |
| 8078 | FFmpeg-Whisper | Media transcription |
| 8079 | Media-Video Analyzer | YOLO video analysis |
| 8080 | Agent Zero | Agent orchestrator API |
| 8081 | Agent Zero UI | Agent orchestrator web UI |
| 8082 | Media-Audio Analyzer | Audio emotion detection |
| 8083 | Extract Worker | Text embedding/indexing |
| 8084 | LangExtract | NLP preprocessing |
| 8085 | Render Webhook | ComfyUI callback handler |
| 8086 | Hi-RAG Gateway v2 (CPU) | Hybrid RAG (CPU) |
| 8087 | Hi-RAG Gateway v2 (GPU) | Hybrid RAG (GPU) |
| 8088 | Presign | MinIO URL presigner |
| 8091 | Archon | Supabase agent service |
| 8092 | PDF Ingest | Document ingestion |
| 8093 | Jellyfin Bridge | Media metadata sync |
| 8094 | Publisher-Discord | Discord notification bot |
| 8095 | Notebook Sync | SurrealDB sync |
| 8097 | Channel Monitor | External content watcher |
| 8098 | DeepResearch | Research planner |
| 8099 | SupaSerch | Multimodal search orchestrator |
| 8110 | Model Registry | Dynamic model configuration service |

### Agent/Worker Services (Tier 3)

| Port | Service | Description |
|------|---------|-------------|
| 8100 | Gateway Agent / Session Context Worker | ⚠️ Shared port (different profiles) |
| 8101 | Messaging Gateway | NATS message relay |
| 8102 | Chat Relay | Agent chat relay |
| 8103 | Tokenism UI API | Tokenism simulator API |
| 8104 | GitHub Runner Controller | CI/CD runner orchestration |
| 8181 | Archon | Alternative Archon port |

### Supabase Stack (Self-Hosted)

| Port | Service | Description | Network |
|------|---------|-------------|---------|
| 5432 | Supabase DB | PostgreSQL 17 (internal only) | pmoves_data |
| 3010 | PostgREST | Supabase REST API | pmoves_api, pmoves_data |
| 9999 | GoTrue | JWT authentication service | pmoves_api, pmoves_data |
| 4000 | Realtime | WebSocket for real-time subscriptions | pmoves_api, pmoves_data |
| 5000 | Storage | S3-compatible file storage | pmoves_api, pmoves_data |
| 8000 | Kong Gateway | API Gateway (proxy/routing) | pmoves_api |
| 8001 | Kong Admin | Kong administration interface | pmoves_api |
| 54323 | Studio | Admin UI dashboard | pmoves_api |
| 65421 | Kong (external) | External API access (VPS) | pmoves_api |

**Notes:**
- **PostgreSQL (5432):** Internal-only, accessible via pmoves_data network
- **PostgREST (3010):** NOT 3000 (avoids Grafana conflict on port 3000)
- **Kong (8000):** Primary external access point for all Supabase APIs
- **Services on pmoves_api + pmoves_data:** Need database access for queries

**Environment Variables:**
```bash
# env.tier-supabase
SUPABASE_POSTGREST_PORT=3010    # NOT 3000 (Grafana conflict)
SUPABASE_GOTRUE_PORT=9999
SUPABASE_REALTIME_PORT=4000     # Conflicts with TensorZero UI (use profile separation)
SUPABASE_STORAGE_PORT=5000
SUPABASE_KONG_PROXY_PORT=8000
SUPABASE_KONG_ADMIN_PORT=8001
SUPABASE_STUDIO_PORT=54323
SUPABASE_DB_PORT=54322           # External access (if needed)
```

**See Also:** [PRODUCTION_SUPABASE.md](PRODUCTION_SUPABASE.md) for complete Supabase documentation.

### External Integrations

| Port | Service | Description |
|------|---------|-------------|
| *See Supabase Stack section above* | Supabase services | Full self-hosted Supabase |

## Port Assignment Guidelines

1. **Check the registry first** - Always search this file before assigning a new port
2. **Use range allocation** - Stay within the appropriate range for the service tier
3. **Document conflicts** - If a port must be shared, document the profile separation
4. **Update Prometheus** - When changing ports, update `monitoring/prometheus/prometheus.yml`
5. **Update healthchecks** - Health check URLs must match the assigned port

## Conflict Resolution

### Port 4000 Conflict (Identified 2026-02-04)

- **TensorZero UI:** Uses 4000 (always runs)
- **Supabase Realtime:** Uses 4000 (optional, profile: `supabase`)

**Resolution:** Realtime should be configured to use a different port or run in a separate profile when TensorZero UI is active.

### Port 8100 Conflict (Resolved 2025-12-30)

- **session-context-worker**: Uses 8100 (profile: `workers,orchestration`)
- **gateway-agent**: Uses 8100 (profile: `tier-agent`)
- **github-runner-ctl**: Was 8100 → **Changed to 8104**

Services using the same port must run in different Docker Compose profiles to avoid conflicts.

## Adding a New Service

When adding a new service:

1. Choose an available port from the appropriate range
2. Add entry to this registry
3. Add Prometheus scrape config (if applicable)
4. Add healthcheck configuration
5. Update environment variable in appropriate `env.tier-*` file

Example:
```yaml
my-service:
  environment:
    - PORT=${MY_SERVICE_PORT:-8110}
  ports: ["8110:8110"]
```

## See Also

- [Tier Architecture](tier-architecture.md) - Network tier organization
- [Services Catalog](services-catalog.md) - Complete service listing
- [NATS Subjects](nats-subjects.md) - Message bus topics
