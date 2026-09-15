---
name: pmoves-yt
description: Use when the user wants to check a YouTube channel or playlist, list latest videos, ingest a video or playlist into the PMOVES pipeline (transcript to Open Notebook + Hi-RAG), or diagnose why the channel-monitor is not discovering. Covers the pmoves-yt service (:8077) and channel-monitor (:8097), and the paths verified to work versus the ones that hang on large playlists.
---

# PMOVES.YT

This skill drives the PMOVES YouTube and SoundCloud pipeline: the `pmoves-yt`
yt-dlp worker on `:8077` and the `channel-monitor` on `:8097`.

## When to Use This Skill

Use this skill when the user:

- Asks to check a channel or playlist, or see the latest videos
- Wants to ingest a video or a bounded slice of a playlist (transcript to
  Open Notebook + Hi-RAG)
- Asks why the monitor has not discovered or ingested anything
- Mentions the DARKXSIDE `ai` playlist, channel-monitor, or yt-dlp

## Listing a playlist (the reliable path)

`POST /yt/playlist` and `/yt/info` with flat do NOT scale: a 2,244-item
playlist hangs `/yt/playlist` (HTTP 000) and `/yt/info` returns zero entries.
Use yt-dlp flat inside the container — fast and authoritative:

```bash
docker exec pmoves-pmoves-yt-1 sh -c \
  'yt-dlp --flat-playlist --no-warnings \
     --print "%(title)s|%(id)s|%(url)s" "<playlist-url>" | head -25'
```

A YouTube playlist is oldest-last, so the **head is newest**. `wc -l` for the
count; `head` for latest, `tail` for the originals. `%(upload_date)s` is `NA`
in flat mode — resolve real dates per video with `/yt/info` on the ids kept.

## Reading one video

```bash
curl -s -X POST http://localhost:8077/yt/info       -H 'Content-Type: application/json' -d '{"url":"<video-url>"}'
curl -s -X POST http://localhost:8077/yt/transcript -H 'Content-Type: application/json' -d '{"url":"<video-url>"}'
```

`/yt/info` returns 200 in about four seconds — egress is clean and there is no
bot-gate on this node.

## Ingesting (bounded — never fan out a whole large playlist)

Resolve the latest N ids with the flat print above, then ingest each:

```bash
curl -s -X POST http://localhost:8077/yt/ingest -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=<id>"}'
```

Ingest lands the transcript in Open Notebook and Hi-RAG. Keep the video id and
timestamp on anything derived; nothing publishes past a room's `publish_gate`.

## Registered sources

`pmoves/config/channel_monitor.json` holds 16 sources including the `ai`
playlist `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`. List live:
`curl -s http://localhost:8097/api/monitor/channels`; stats:
`curl -s http://localhost:8097/api/monitor/stats`.

## Gates and known gaps (2026-09-06)

- Check the egress IP first: a KVM exit node presents a datacenter IP and trips
  the YouTube bot gate. Cookies stay funnel-fed via `yt-cookie-writer`, never in
  chat.
- Monitor discovery is OAuth-based (per-user refresh token via
  `POST /api/oauth/google/token`); the `YOUTUBE_API_KEY` env and the
  `youtube_api_key` config field are unused by it. A public-playlist read needs
  no OAuth — use the yt-dlp flat path above.
- SoundCloud ingest fails on an S3 upload FileNotFoundError (`.NA` filename) —
  the monitor's only run (2026-08-04) failed all 10 SoundCloud tracks this way.
- No videos have been ingested yet for the DARKXSIDE `ai` playlist.

## Related

- Handoff: `pmoves/docs/handoffs/darkxside-youtube-analysis-2026-09-05.md`
- Skills: `search:hirag`, `search:ingest-content`, `notebook:query`
- Constellation authoring method: `skills/README.md`
