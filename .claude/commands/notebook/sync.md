# Notebook Sync

Trigger a manual sync between Open Notebook (SurrealDB) and the indexing pipeline.

## Instructions

Trigger a sync that will:
1. Pull new notes from Open Notebook via SurrealDB
2. Send them through LangExtract for language detection
3. Index them via Extract Worker to Qdrant + Meilisearch

```bash
# Check Notebook Sync health
curl -s http://localhost:8095/healthz
```

```bash
# Trigger manual sync (if endpoint available)
curl -s -X POST http://localhost:8095/sync \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

```bash
# Check sync logs
docker logs notebook-sync --tail 20 2>&1
```

Report:
- Sync initiated/completed status
- Notes discovered and indexed
- Any processing errors
