# List YouTube Channels

List all configured YouTube channels and playlists in the channel monitor.

## Instructions

Read the channel monitor configuration and display:
1. All configured sources (channels and playlists)
2. Their enabled status
3. Check interval
4. Auto-process setting
5. Priority and namespace

```bash
# Read config
cat /home/pmoves/PMOVES.AI/pmoves/config/channel_monitor.json | jq '.channels[] | {name: .channel_name, id: .channel_id, enabled: .enabled, auto_process: .auto_process, interval_min: .check_interval_minutes, priority: .priority, namespace: .namespace}'
```

Display results in a clean table format showing:
- Channel Name
- Source Type (playlist/channel)
- Enabled (yes/no)
- Auto-Process (yes/no)
- Check Interval
- Priority
