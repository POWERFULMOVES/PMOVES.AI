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
# After editing config
docker compose -f /home/pmoves/PMOVES.AI/pmoves/docker-compose.yml restart channel-monitor
```

Show the new state after toggling.
