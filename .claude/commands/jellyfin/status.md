# Jellyfin Status

Check the status of Jellyfin Bridge and related media services.

## Instructions

Check health of:
1. **Jellyfin Bridge** (port 8093) - Metadata webhook and helper
2. **Jellyfin server** - Media server accessibility

```bash
# Jellyfin Bridge health
curl -s http://localhost:8093/healthz && echo "Jellyfin Bridge: healthy" || echo "Jellyfin Bridge: unhealthy"
```

```bash
# Container status
docker ps --filter "name=jellyfin" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Jellyfin Bridge health (healthy/unhealthy)
- Supabase sync status
- Recent webhook activity
- Any errors in logs
