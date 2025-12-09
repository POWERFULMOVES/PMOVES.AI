# YouTube Pipeline Status

Check the status of all YouTube-related services.

## Instructions

Check health of:
1. **Channel Monitor** (port 8097) - Discovers new videos
2. **PMOVES.YT** (port 8077) - Downloads and processes videos
3. **bgutil-pot-provider** - YouTube PO token generation
4. **Invidious** (port 3000) - Privacy-focused YouTube API
5. **Invidious Companion** - Token companion service

```bash
# Service health checks
echo "=== Channel Monitor ===" && curl -s http://localhost:8097/healthz
echo "=== PMOVES.YT ===" && curl -s http://localhost:8077/healthz
echo "=== Invidious ===" && curl -s http://localhost:3000/ >/dev/null && echo '{"status":"ok"}' || echo '{"status":"error"}'
```

```bash
# Container status
docker ps --filter "name=channel-monitor" --filter "name=pmoves-yt" --filter "name=bgutil" --filter "name=invidious" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Service health (healthy/unhealthy)
- Recent activity (videos discovered, processed)
- Any errors in logs
