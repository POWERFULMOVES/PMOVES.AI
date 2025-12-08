# Session Context Worker

Phase 3 service for PMOVES Claude Awareness infrastructure.

## Purpose

Transforms Claude Code session context snapshots into searchable knowledge base entries via Hi-RAG ingestion.

## Architecture

### Input
- **Subject**: `claude.code.session.context.v1`
- **Schema**: `/pmoves/contracts/schemas/claude/session.context.v1.schema.json`
- **Source**: Claude Code CLI session hooks (autocompact, checkpoint, etc.)

### Output
- **Subject**: `kb.upsert.request.v1`
- **Schema**: `/pmoves/contracts/schemas/kb/upsert.request.v1.schema.json`
- **Destination**: Hi-RAG knowledge base ingestion pipeline

## Features

### Searchable Content Extraction
Extracts and combines:
- Session summaries
- Pending/completed tasks from TodoWrite
- User decisions from AskUserQuestion
- Active file paths and actions
- Tool execution summaries
- Agent spawn information

### Metadata Enrichment
Tags each entry with:
- `source`: "claude-code"
- `session_id`: Unique session identifier
- `context_type`: autocompact, checkpoint, tool, decision, summary
- `repository`, `branch`, `worktree`: Git context
- `working_directory`: CWD at time of capture
- `task_count`, `completed_task_count`: Task metrics
- `active_file_count`: File activity metrics
- `decision_count`: Decision tracking

### Knowledge Base Organization
- **Namespace**: `claude-code-sessions`
- **ID Format**: `claude-session-{session_id}-{context_type}-{timestamp}`

## Deployment

### Environment Variables
```bash
NATS_URL=nats://nats:4222           # NATS server URL
HEALTH_PORT=8100                     # Health check HTTP port
```

### Docker Compose
```yaml
session-context-worker:
  build: ./services/session-context-worker
  restart: unless-stopped
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:4222}
    - HEALTH_PORT=8100
  depends_on: [nats]
  profiles: ["workers"]
  networks: [bus_tier, monitoring_tier]
  ports: ["8100:8100"]
```

### Health Check
```bash
curl http://localhost:8100/healthz
```

Response:
```json
{
  "ok": true,
  "nats_connected": true,
  "metrics": {
    "messages_received": 42,
    "messages_processed": 41,
    "messages_failed": 1,
    "kb_upserts_published": 41
  }
}
```

### Metrics
```bash
curl http://localhost:8100/metrics
```

## Integration with Hi-RAG

Entries published to `kb.upsert.request.v1` are consumed by the Hi-RAG ingestion pipeline, which:
1. Generates embeddings via TensorZero
2. Indexes to Qdrant (vectors)
3. Indexes to Meilisearch (full-text)
4. Optionally links entities in Neo4j

## Use Cases

### Session Recovery
Query Hi-RAG for previous session context:
```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was I working on in the auth refactor?",
    "top_k": 5,
    "rerank": true,
    "filters": {
      "source": "claude-code",
      "repository": "PMOVES.AI"
    }
  }'
```

### Cross-Session Learning
Agent Zero can query Claude Code session history to:
- Understand team development patterns
- Retrieve past architectural decisions
- Learn from previous task breakdowns

### Autocompact Awareness
When Claude Code autocompacts, session context is preserved in Hi-RAG, enabling:
- Seamless session continuity
- Context recovery after autocompact
- Long-term development history

## Event Flow

```
Claude Code CLI
     |
     | (autocompact trigger)
     v
NATS: claude.code.session.context.v1
     |
     v
Session Context Worker
     |
     | (transform + enrich)
     v
NATS: kb.upsert.request.v1
     |
     v
Hi-RAG Ingestion Pipeline
     |
     +---> TensorZero (embeddings)
     +---> Qdrant (vectors)
     +---> Meilisearch (full-text)
     +---> Neo4j (entities)
```

## Monitoring

- **Logs**: JSON-structured via `logging` module
- **Metrics**: Exposed at `/metrics` endpoint
- **Health**: `/healthz` endpoint returns connection status
- **Grafana**: Integrate via Prometheus scraper (future)

## Development

### Local Testing
```bash
# Start NATS
docker compose --profile data up -d nats

# Install dependencies
pip install -r requirements.txt

# Run worker
python main.py
```

### Manual Event Publishing
```bash
# Publish test session context
nats pub claude.code.session.context.v1 '{
  "session_id": "test-123",
  "context_type": "autocompact",
  "timestamp": "2025-12-07T00:00:00Z",
  "summary": "Working on session context worker",
  "repository": "PMOVES.AI",
  "branch": "main"
}'
```

## Future Enhancements

- [ ] CGP geometry extraction for structured knowledge
- [ ] Deduplication for similar session contexts
- [ ] Automatic session linking based on parent_session_id
- [ ] Cross-repository session correlation
- [ ] Prometheus metrics export
