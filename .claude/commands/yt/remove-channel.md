# Remove YouTube Channel

Remove a YouTube channel or playlist from the channel monitor configuration.

## Arguments

- `$ARGUMENTS` - Channel name or channel_id to remove

## Instructions

1. Read current channel_monitor.json
2. Find matching channel by:
   - `channel_name` (partial match, case-insensitive)
   - `channel_id` (exact match)
3. If multiple matches found, list them and ask user to be more specific
4. If single match found, show details and confirm removal
5. Remove from channels array
6. Write updated config
7. Restart channel-monitor service

```bash
# After editing config (uses PMOVES_ROOT env var or defaults to current git repo root)
PMOVES_ROOT="${PMOVES_ROOT:-$(git rev-parse --show-toplevel)}"
docker compose -f "${PMOVES_ROOT}/pmoves/docker-compose.yml" restart channel-monitor
```

Always confirm before removing.
