---
name: pmoves-yt
description: Query, list, and ingest YouTube (and SoundCloud) content through the PMOVES.YT service and channel-monitor, using the paths verified to work.
user-invocable: true
owning_persona: cataclysmstudios@gmail.com
minted_at: 2026-09-06
---

# PMOVES.YT

## When to invoke

Use when the operator wants to check a channel or playlist, list latest videos,
ingest a video/playlist into the pipeline (transcript to Open Notebook + Hi-RAG),
or diagnose why the monitor is not discovering. Two services back this:

- **pmoves-yt** `:8077` — yt-dlp worker (info, download, transcript, ingest,
  playlist control). Verified: `GET /healthz` 200, `POST /yt/info` on a single
  video 200 in ~4s (no bot-gate, egress clean).
- **channel-monitor** `:8097` — scheduled discovery + Discord/YT-control review.

## Inputs

- A YouTube video URL, playlist URL/id, or channel handle.
- For ingest: the target (video or bounded playlist slice) and a limit.

## Outputs

- Video/playlist metadata, a latest-N listing, or an ingest job queued to
  `pmoves-yt:8077/yt/ingest` (transcript to Open Notebook + Hi-RAG).

## Implementation

### List a playlist's videos (the reliable path)

`POST /yt/playlist` and `/yt/info` with flat do NOT scale — a 2,244-item
playlist hangs `/yt/playlist` (HTTP 000) and `/yt/info` returns 0 entries. Use
yt-dlp flat inside the container, which is fast and authoritative:

```bash
docker exec pmoves-pmoves-yt-1 sh -c \
  'yt-dlp --flat-playlist --no-warnings \
     --print "%(title)s|%(id)s|%(url)s" "<playlist-url>" | head -25'
```

A YouTube playlist is oldest-last, so the **head is newest**. `wc -l` the full
print for the count; `head` for latest, `tail` for the originals. `%(upload_date)s`
is `NA` in flat mode — resolve real dates per-video with `/yt/info` on the ids
you keep.

### Get one video's metadata / transcript

```bash
curl -s -X POST http://localhost:8077/yt/info       -H 'Content-Type: application/json' -d '{"url":"<video-url>"}'
curl -s -X POST http://localhost:8077/yt/transcript -H 'Content-Type: application/json' -d '{"url":"<video-url>"}'
```

### Ingest (bounded — never fan out a 2,244-item playlist blindly)

Resolve the latest N ids with the flat print above, then ingest each:

```bash
curl -s -X POST http://localhost:8077/yt/ingest -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=<id>"}'
```

Ingest lands the transcript in Open Notebook and Hi-RAG. Provenance: keep the
video id + timestamp on anything derived; nothing publishes past a room's
`publish_gate`.

### Registered sources

`pmoves/config/channel_monitor.json` (16 sources incl. the `ai` playlist
`PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`). List: `curl -s http://localhost:8097/api/monitor/channels`.
Stats: `curl -s http://localhost:8097/api/monitor/stats`.

## Known gaps (2026-09-06)

- **Monitor discovery is OAuth-based, not key-based.** It builds a client only
  when `GOOGLE_CLIENT_ID`/`SECRET` are set and needs a per-user refresh token
  via `POST /api/oauth/google/token`; the `youtube_api_key` config field and the
  `YOUTUBE_API_KEY` env are unused by it. A public-playlist read needs no OAuth —
  use the yt-dlp flat path above, or add a `developerKey` public-read path to
  `youtube_api.py` (follow-up).
- **SoundCloud ingest fails** on an S3 upload FileNotFoundError (`.NA` filename)
  — the monitor's only run (2026-08-04) failed all 10 SoundCloud tracks this way.
- **No videos ingested yet** for the DARKXSIDE `ai` playlist.

## Gates

Check egress IP first (a KVM exit node presents a datacenter IP and trips the
YouTube bot gate). Cookies stay funnel-fed via `yt-cookie-writer` — never in chat.

## Related

- Handoff: `pmoves/docs/handoffs/darkxside-youtube-analysis-2026-09-05.md`
- Skills: `search:hirag`, `search:ingest-content`, `notebook:query`
