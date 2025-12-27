# Pending YouTube Videos

List videos that have been discovered but not yet processed (auto_process=false).

## Instructions

1. Query Supabase for videos with status 'pending' or 'discovered'
2. Show list with:
   - Video title
   - Channel name
   - Duration
   - Discovery date
   - Video URL

```bash
# Check for pending videos in recent logs
docker logs pmoves-channel-monitor-1 --tail 100 2>&1 | grep -E "(discovered|pending|queued)"
```

If videos are pending, ask user which ones to ingest.
