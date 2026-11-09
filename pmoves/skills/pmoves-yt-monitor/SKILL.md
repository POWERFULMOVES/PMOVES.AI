---
name: pmoves-yt-monitor
description: "YouTube and SoundCloud channel monitoring with transcript extraction, batch processing, and routing to Hi-RAG or notebooks."
version: 0.1.0
author: PMOVES-HERMES-Z890
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [youtube, monitor, transcripts, soundcloud, hi-rag, research, channel-monitor]
    related_skills: [pmoves-folder-monitor, hermes-agent, youtube-content]
---

# PMOVES YouTube Monitor

Operates the existing `pmoves/config/channel_monitor.json` configuration to poll YouTube/SoundCloud channels, download transcripts/media, and route content to the PMOVES knowledge graph or Hi-RAG.

## What it does

- Loads `pmoves/config/channel_monitor.json`.
- Polls each channel at its configured interval.
- Downloads new videos/audio using `yt-dlp`.
- Extracts transcripts (Whisper if no captions).
- Generates summary, tags, and key quotes.
- Routes to:
  - `pmoves/datasets/personas/` style ingestion
  - Hi-RAG v2 gateway
  - Notebook page `pages/yt-monitor/{channel_id}`
  - NATS subject `media.transcript.ready.v1`

## Configuration

Primary config: `pmoves/config/channel_monitor.json`

Key settings:

```json
{
  "global_settings": {
    "max_videos_per_check": 10,
    "use_rss_feed": true,
    "use_youtube_api": true,
    "youtube_api_key": "",
    "check_on_startup": false,
    "notification_webhook": "",
    "batch_processing": true,
    "batch_size": 5
  },
  "monitoring_schedule": {
    "enabled": true,
    "interval_minutes": 60
  }
}
```

## Autonomous scope

Allowed autonomously:
- Poll channels and download new content.
- Extract transcripts and metadata.
- Summarize and route to notebook/RAG.

Not allowed autonomously:
- Publish content externally without approval.
- Delete downloaded archives.
- Exceed `max_videos_per_check` or rate limits.

## Command examples

```bash
# Run the existing monitor once
python pmoves/tools/channel_monitor.py --config pmoves/config/channel_monitor.json --once

# Run continuously
python pmoves/tools/channel_monitor.py --config pmoves/config/channel_monitor.json --daemon
```

## Cron job

```bash
hermes cron create "0 * * * *" --prompt "Run the PMOVES YouTube/SoundCloud channel monitor using pmoves/config/channel_monitor.json. Extract transcripts, summarize, and route results to Hi-RAG and the notebook workspace." --skills pmoves-yt-monitor
```

## Zero-retention note

Media files are stored in the configured download directory. To enforce zero retention, configure a lifecycle rule or use the E2B sandbox path in `pmoves/tools/channel_monitor.py`.

## Next implementation steps

1. Verify `pmoves/tools/channel_monitor.py` exists and reads the JSON config.
2. Add transcript routing to Hi-RAG v2 gateway.
3. Add NATS emit on `media.transcript.ready.v1`.
4. Wire to the z890 room manifest as `yt-monitor` skill binding.
