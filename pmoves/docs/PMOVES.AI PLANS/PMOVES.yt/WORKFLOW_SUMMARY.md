# PMOVES.yt • Workflow Summary

This summarizes the end‑to‑end path from a YouTube URL to playback and geometry in PMOVES.

## Overview
- Ingest: `/yt/ingest { url, namespace, bucket }`
- Info: `/yt/info { url }` → `video_id`
- Transcript: `/yt/transcript { video_id }` (captions) or offline Whisper fallback
- Emit: `/yt/emit { video_id, namespace }` → chunks + `geometry.cgp.v1`
- ShapeStore: hi‑rag v2 warms constellations from Supabase + realtime
- Jellyfin: bridge maps by title or links newest item; playback URL returned

## REST and Env
- Preferred REST: `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
- Keys: `SUPABASE_SERVICE_ROLE_KEY` for server‑side writes; `SUPABASE_ANON_KEY` for UI
- Single‑env mode: `pmoves/env.shared` is source of truth (optional `.env.local` overrides)

## SABR / Transcript Handling
- If captions are missing or `/yt/emit` returns 404, enable Invidious (`make -C pmoves up-invidious`).
- Offline path: fetch audio and run Whisper (service `ffmpeg-whisper`) to persist a transcript, then retry `/yt/emit`.

## Hi‑RAG v2 Notes
- GPU rerank model is Qwen3‑Reranker‑4B (batch=1). The smoke harness runs rerank queries inside the container.
- On RTX 50xx (SM_120), current torch wheels may run CPU fallback; functionally OK but slower.

## Smoketests
- `make -C pmoves yt-smoke` → health + ingest + summarize
- `make -C pmoves yt-emit-smoke URL=<youtube_url>` → chunks + CGP + geometry jump
- `make -C pmoves yt-jellyfin-smoke` → emit + playback URL via Jellyfin bridge

## Troubleshooting
- 404 on `/yt/emit`: run `/yt/transcript` first; if still 404, use Invidious or Whisper fallback.
- Geometry 404: gateway containers may have the point while host port misses; the harness retries GPU → CPU and executes jump tests inside the container.
- Playback missing: ensure `JELLYFIN_API_KEY`, `JELLYFIN_URL` are set and at least one library item exists (seeding or host mounts).

