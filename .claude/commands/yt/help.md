# YouTube Management Help

List all available YouTube management commands.

## Available Commands

### Channel/Playlist Management
- `/yt:list-channels` - List all configured channels and playlists
- `/yt:add-channel <url>` - Add a new YouTube channel
- `/yt:add-playlist <url>` - Add a new YouTube playlist
- `/yt:remove-channel <name>` - Remove a channel/playlist
- `/yt:toggle-channel <name>` - Enable/disable a channel

### Video Operations
- `/yt:check-now [channel]` - Trigger immediate channel check
- `/yt:ingest-video <url>` - Manually ingest a specific video
- `/yt:pending` - List discovered videos awaiting approval

### Status & Monitoring
- `/yt:status` - Check all YouTube service health
- `/yt:help` - Show this help message

## Quick Start

1. Check current channels: `/yt:list-channels`
2. Add a new channel: `/yt:add-channel https://www.youtube.com/@ChannelName`
3. Check for new videos: `/yt:check-now`
4. Review pending videos: `/yt:pending`
5. Ingest specific video: `/yt:ingest-video https://youtu.be/xxxxx`

## Configuration

All channel configurations are stored in:
`/home/pmoves/PMOVES.AI/pmoves/config/channel_monitor.json`

Key settings:
- `auto_process: false` - Videos require manual approval (default)
- `auto_process: true` - Videos are automatically processed
- `check_interval_minutes` - How often to check for new videos
- `filters` - Duration, age, keyword filters
