# Check YouTube Channels Now

Trigger an immediate check for new videos on configured channels.

## Arguments

- `$ARGUMENTS` - Optional: specific channel name to check (or "all" for all channels)

## Instructions

1. If specific channel provided:
   - Find channel in config
   - Call channel monitor API to check that channel
2. If "all" or no argument:
   - Trigger full channel check cycle

```bash
# Check channel monitor health
curl -s http://localhost:8097/healthz

# View recent logs for discovered videos
docker logs pmoves-channel-monitor-1 --tail 50 2>&1 | grep -E "(discovered|new video|checking)"
```

Report:
- Number of videos discovered
- Video titles and durations
- Whether videos are queued for processing or waiting for approval
