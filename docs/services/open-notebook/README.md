# Open Notebook Service

Open Notebook is a SurrealDB-backed knowledge management system for persistent storage of research, notes, and sources.

## Quick Start

```bash
# Start Open Notebook with Docker Compose
docker compose up open-notebook open-notebook-surrealdb -d

# Verify health
curl http://localhost:5055/health
```

## Configuration

### Required Environment Variables

```bash
OPEN_NOTEBOOK_API_URL=http://cataclysm-open-notebook:5055
OPEN_NOTEBOOK_API_TOKEN=<your-token>
```

See `env.shared.example` for all configuration options.

## Integrations

Open Notebook integrates with several PMOVES.AI services:

| Service | Purpose |
|---------|---------|
| **DeepResearch** | Publishes research summaries |
| **notebook-sync** | Syncs content to search indexes |
| **Agent Zero** | MCP `notebook.search` command |
| **UI Dashboard** | Displays recent sources |

For detailed integration documentation, see [INTEGRATION_AUDIT.md](INTEGRATION_AUDIT.md).

## API Reference

```bash
# List notebooks
curl -H "Authorization: Bearer $TOKEN" http://localhost:5055/api/notebooks

# Create source
curl -X POST http://localhost:5055/api/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notebook_id": "notebook:xxx", "content": "..."}'

# Search
curl -X POST http://localhost:5055/api/v1/notebooks/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search", "limit": 10}'
```

## Troubleshooting

### Service won't start

1. Check SurrealDB is running: `docker logs pmoves-open-notebook-surrealdb-1`
2. Verify `SURREAL_ADDRESS` is set to hostname only (not `ws://` URL)
3. Check port 5055 is not in use

### API returns 401

1. Verify `OPEN_NOTEBOOK_API_TOKEN` is set correctly
2. Ensure token matches the one configured in Open Notebook

### DeepResearch not publishing

1. Check `DEEPRESEARCH_NOTEBOOK_ID` is set
2. Verify notebook exists via API
3. Check DeepResearch logs for errors

## Related Documentation

- [INTEGRATION_AUDIT.md](INTEGRATION_AUDIT.md) - Complete integration audit
- [.claude/CLAUDE.md](../../../.claude/CLAUDE.md) - PMOVES.AI developer context
