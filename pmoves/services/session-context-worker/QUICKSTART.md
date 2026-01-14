# Session Context Worker - Quick Start

## What is it?

Transforms Claude Code session snapshots into searchable Hi-RAG knowledge base entries.

## Event Flow

```
Claude Code → NATS (session.context.v1) → Worker → NATS (kb.upsert.request.v1) → Hi-RAG
```

## Deploy

```bash
# Start the service
docker compose --profile workers up -d session-context-worker

# Check health
curl http://localhost:8100/healthz

# View logs
docker compose logs -f session-context-worker
```

## Test

```bash
# Run transformation test
cd /home/pmoves/PMOVES.AI/pmoves/services/session-context-worker
python3 test_transform.py

# Publish test event
nats pub claude.code.session.context.v1 '{
  "session_id": "test-123",
  "context_type": "autocompact",
  "timestamp": "2025-12-07T23:00:00Z",
  "summary": "Testing session context worker",
  "repository": "PMOVES.AI",
  "branch": "main"
}'

# Query Hi-RAG
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "session context", "top_k": 5}'
```

## Endpoints

- **Health**: `http://localhost:8100/healthz`
- **Metrics**: `http://localhost:8100/metrics`

## Files

- `main.py` - Service implementation
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container build
- `README.md` - Full documentation
- `test_transform.py` - Standalone test
- `IMPLEMENTATION_SUMMARY.md` - Detailed summary

## Configuration

Environment variables:
- `NATS_URL` - NATS server URL (default: `nats://nats:4222`)
- `HEALTH_PORT` - Health endpoint port (default: `8100`)

## Monitoring

Metrics exposed at `/metrics`:
- `messages_received` - Total NATS messages
- `messages_processed` - Successfully transformed
- `messages_failed` - Parse/processing errors
- `kb_upserts_published` - Published to KB upsert queue

## Common Issues

### Worker not receiving messages
- Check NATS connection: `docker compose logs nats`
- Verify subscription: `nats sub claude.code.session.context.v1`
- Check health endpoint: `curl localhost:8100/healthz`

### KB upserts not being ingested
- Verify Hi-RAG is running: `docker compose ps hi-rag-gateway-v2`
- Check kb.upsert.request.v1 subscribers: `nats sub kb.upsert.request.v1`

## Integration with Claude Code CLI

When Claude Code triggers autocompact or checkpoint, it publishes session context to NATS. This worker:
1. Receives the event
2. Extracts searchable content (summary, tasks, decisions, files)
3. Enriches with metadata (session_id, repo, branch, metrics)
4. Publishes to `kb.upsert.request.v1` for Hi-RAG ingestion

Result: Session context becomes searchable via Hi-RAG semantic + full-text search.

## Next Phase

This completes Phase 3. Next:
- Phase 4: Claude Code CLI hooks integration
- Phase 5: Session recovery UI
- Phase 6: Cross-session analytics
