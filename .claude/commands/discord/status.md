# Discord Status

Check the status of the Publisher-Discord notification bot.

## Instructions

Check health of:
1. **Publisher-Discord** (port 8094) - Discord notification service
2. **NATS subscriptions** - Verify event listeners are active

```bash
# Publisher-Discord health
curl -s http://localhost:8094/healthz && echo "Publisher-Discord: healthy" || echo "Publisher-Discord: unhealthy"
```

```bash
# Container status
docker ps --filter "name=publisher-discord" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Service health (healthy/unhealthy)
- NATS subscription status (listening for ingest events)
- Recent notification activity
- Any errors in logs
