# Jellyfin Sync

Trigger a sync between Jellyfin and Supabase metadata.

## Instructions

Initiate a metadata sync from Jellyfin to Supabase via the Jellyfin Bridge service.

```bash
# Check Jellyfin Bridge health first
curl -s http://localhost:8093/healthz
```

```bash
# Trigger sync (if endpoint available)
curl -s -X POST http://localhost:8093/sync \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

```bash
# Check recent sync logs
docker logs jellyfin-bridge --tail 20 2>&1
```

Report:
- Sync status (started/completed/failed)
- Number of items synced
- Any sync errors
