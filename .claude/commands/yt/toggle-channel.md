# Toggle YouTube Channel

Enable or disable a YouTube channel/playlist in the channel monitor.

## Arguments

- `$ARGUMENTS` - Channel name or channel_id to toggle

## Instructions

1. Read current channel_monitor.json
2. Find matching channel by:
   - `channel_name` (partial match, case-insensitive)
   - `channel_id` (exact match)
3. Toggle the `enabled` field
4. Write updated config
5. Restart channel-monitor service

```bash
# After editing config (uses PMOVES_ROOT env var or defaults to current git repo root)
PMOVES_ROOT="${PMOVES_ROOT:-$(git rev-parse --show-toplevel)}"
docker compose -f "${PMOVES_ROOT}/pmoves/docker-compose.yml" restart channel-monitor
```

Show the new state after toggling.
