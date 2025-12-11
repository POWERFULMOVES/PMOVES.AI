# Add YouTube Playlist

Add a new YouTube playlist to the channel monitor configuration.

## Arguments

- `$ARGUMENTS` - YouTube playlist URL or ID (e.g., https://www.youtube.com/playlist?list=PLxxxx or just PLxxxx)

## Instructions

1. Parse playlist ID from arguments
   - If URL: extract `list=` parameter
   - If ID: use directly (starts with PL)
2. Read current channel_monitor.json
3. Create new playlist entry with these defaults:
   - `channel_id`: `yt:playlist:{playlist_id}`
   - `platform`: `youtube`
   - `source_type`: `playlist`
   - `source_url`: `https://www.youtube.com/playlist?list={playlist_id}`
   - `enabled`: `true`
   - `check_interval_minutes`: `120`
   - `auto_process`: `false` (require manual approval)
   - `priority`: `1`
   - `namespace`: `pmoves.youtube.playlist`
   - `tags`: `["playlist"]`
   - `filters.min_duration_seconds`: `60`
   - `filters.max_age_days`: `365`
   - `filters.exclude_keywords`: `["#shorts"]`
4. Add to channels array
5. Write updated config
6. Restart channel-monitor service

Ask user for:
- Playlist name (display name)
- Namespace (default: pmoves.youtube.playlist)
- Tags (comma-separated)
- Priority (1=high, 2=medium, 3=low)
