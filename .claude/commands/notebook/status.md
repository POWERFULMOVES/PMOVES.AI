# Notebook Status

Check the status of the Open Notebook (SurrealDB) integration.

## Instructions

Check health of:
1. **Notebook Sync** (port 8095) - SurrealDB synchronizer
2. **Open Notebook API** - External SurrealDB service

```bash
# Notebook Sync health
curl -s http://localhost:8095/healthz && echo "Notebook Sync: healthy" || echo "Notebook Sync: unhealthy"
```

```bash
# Container status
docker ps --filter "name=notebook-sync" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Notebook Sync service health
- Last sync timestamp
- Polling interval (default: 300s)
- Any sync errors or connection issues
