# Add YouTube Channel

Add a new YouTube channel to the channel monitor configuration.

## Arguments

- `$ARGUMENTS` - YouTube channel URL (e.g., `https://www.youtube.com/@ChannelName`)

## Instructions

1. Parse the channel URL from arguments
2. Extract channel handle (e.g., @ChannelName)
3. Read current channel_monitor.json
4. Create new channel entry with these defaults:
   - `channel_id`: `yt:channel:@{handle}`
   - `platform`: `youtube`
   - `source_type`: `channel`
   - `enabled`: `true`
   - `check_interval_minutes`: `240`
   - `auto_process`: `false` (require manual approval)
   - `priority`: `2`
   - `namespace`: `pmoves.youtube.custom`
   - `tags`: `["custom"]`
   - `filters.min_duration_seconds`: `120`
   - `filters.max_age_days`: `90`
   - `filters.exclude_keywords`: `["#shorts"]`
5. Add to channels array
6. Write updated config
7. Restart channel-monitor service

```bash
<<<<<<< HEAD
# After editing config (uses PMOVES_ROOT env var or defaults to current git repo root)
PMOVES_ROOT="${PMOVES_ROOT:-$(git rev-parse --show-toplevel)}"
docker compose -f "${PMOVES_ROOT}/pmoves/docker-compose.yml" restart channel-monitor
=======
# After editing config
docker compose -f /home/pmoves/PMOVES.AI/pmoves/docker-compose.yml restart channel-monitor
>>>>>>> origin/main
```

Ask user for:
- Channel name (display name)
- Namespace (default: pmoves.youtube.custom)
- Tags (comma-separated)
- Priority (1=high, 2=medium, 3=low)
