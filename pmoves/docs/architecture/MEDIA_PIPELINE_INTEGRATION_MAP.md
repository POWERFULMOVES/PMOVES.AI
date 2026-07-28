# Media Pipeline Service Integration Map

**Created:** 2026-07-28
**Status:** Research synthesis — how existing services leverage each other

## Service Inventory

### PMOVES.YT (port 8077) — Universal Media Access
The primary ingestion engine. Already has far more capability than we were using:

| Endpoint | Purpose | Batch? |
|----------|---------|--------|
| `/yt/info` | Metadata (Data API first, yt-dlp fallback) | Single |
| `/yt/download` | Download to S3/MinIO + NATS event | Single |
| `/yt/transcript` | Transcribe via ffmpeg-whisper + store | Single |
| `/yt/ingest` | Full pipeline: download + transcribe + store + NATS | Single |
| `/yt/playlist` | **Batch concurrent playlist ingest** | **Yes** |
| `/yt/channel` | **Batch channel ingest** (delegates to playlist) | **Yes** |
| `/yt/summarize` | AI summary via Gemma (Ollama) | Single |
| `/yt/chapters` | Chapter markers via Gemma | Single |
| `/yt/emit` | Segment transcript → Hi-RAG v2 + Geometry Bus | Single |
| `/yt/search` | Search ingested content / Jellyfin backfill | Query |

**Key discovery:** `/yt/playlist` already has everything we need for batch processing:
- `asyncio.Semaphore(YT_CONCURRENCY)` — parallel download control (default 2)
- `tenacity.AsyncRetrying` with exponential backoff — retries
- `yt_jobs` + `yt_items` Supabase tables — job tracking (queued → running → completed/failed)
- `YT_PLAYLIST_MAX` (default 50) — configurable batch size
- Rate limiting via `asyncio.Lock` + `YT_RATE_LIMIT`
- Multi-platform support via `_infer_platform()` — works with any yt-dlp site

### PMOVES-transcribe-and-fetch (port 8074) — Transcription Specialist
Powerful transcription pipeline but **no batch API** and **no NATS consumer** (despite declared subjects).

**Strengths to leverage:**
- Three transcription backends: Faster-Whisper (local GPU), Groq (cloud), LLM Registry (LiteLLM proxy)
- Rich output: Markdown tables with clickable timestamps, CSV, Excel, PDF
- Dual-write to workspace + Obsidian vault
- SSE real-time progress streaming
- pgvector search over transcripts

**Gap:** The declared NATS subjects (`transcribe.fetch.request.v1` / `.result.v1`) are **forward-looking contracts only** — no subscriber exists in the backend. Batch processing would require either:
- Option A: Sequential API scripting via `/process-video/` loop
- Option B: Wire a NATS consumer to the declared subjects (contract-ready)
- Option C: Add `/process-batch/` endpoint

### DeepResearch (port 8098) — Research Worker
NATS-driven LLM research worker that:
- Subscribes to `research.deepresearch.request.v1`
- Runs queries through TensorZero (local Ollama) or OpenRouter (Tongyi)
- Mirrors results to Open Notebook
- Publishes CGP geometry packets to `tokenism.cgp.ready.v1`
- Does NOT call Hi-RAG directly — CGP flows downstream

### SupaSearch (port 8099) — Multimodal Research Orchestrator
The higher-level orchestrator that:
- Subscribes to `supaserch.request.v1`
- Fans out across DeepResearch + Archon + Hi-RAG + MCP tools
- Publishes `supaserch.result.v1` + CGP
- Calls Hi-RAG directly for retrieval
- Calls Supabase for persistence

## Pipeline Architecture: How They Connect

```
                    ┌─────────────────────────────────┐
                    │     CONTENT DISCOVERY            │
                    │  Data API v3 crawl (2028 videos) │
                    │  Supabase: youtube_videos        │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     BATCH INGESTION              │
                    │  PMOVES.YT /yt/playlist          │
                    │  ┌─────────────────────────────┐ │
                    │  │ Per-video (concurrent ×2):  │ │
                    │  │ 1. Download → S3/MinIO      │ │
                    │  │ 2. NATS: ingest.file.added  │ │
                    │  │ 3. Transcribe (ffmpeg-W)    │ │
                    │  │ 4. NATS: ingest.transcript  │ │
                    │  │ 5. Store in Supabase        │ │
                    │  └─────────────────────────────┘ │
                    │  Job tracking: yt_jobs/yt_items  │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     ENRICHMENT (NATS-driven)     │
                    │                                  │
                    │  PMOVES.YT /yt/emit ──────────►  │  Hi-RAG v2 (index)
                    │  (segment transcript)            │  + Geometry Bus (CGP)
                    │                                  │
                    │  PMOVES.YT /yt/summarize ─────►  │  Gemma summary
                    │  PMOVES.YT /yt/chapters ──────►  │  Chapter markers
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     RESEARCH & ANALYSIS          │
                    │                                  │
                    │  SupaSearch ◄── supaserch.req    │
                    │  ├──► DeepResearch (NATS)        │
                    │  ├──► Archon (MCP)               │
                    │  ├──► Hi-RAG (retrieval)         │
                    │  └──► Supabase (persist)         │
                    │                                  │
                    │  Output: research.deepresearch   │
                    │  .result.v1 + Open Notebook      │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     DISTRIBUTION                 │
                    │                                  │
                    │  Publisher → Jellyfin (S3→FS)    │
                    │  n8n → Discord/notify            │
                    │  Activepieces Cloud → LinkedIn   │
                    │  Tailscale Serve → mesh access   │
                    └─────────────────────────────────┘
```

## Revised Approach: Use PMOVES.YT /yt/playlist Instead of Custom Tool

The standalone `yt_batch_download.py` was a workaround for the `/yt/download` service endpoint bug. But PMOVES.YT already has `/yt/playlist` which:
- Handles concurrency (Semaphore × 2)
- Has retries (tenacity backoff)
- Tracks jobs in Supabase (`yt_jobs`, `yt_items`)
- Calls `/yt/ingest` per video (download + transcribe + store)
- Emits NATS events
- Supports `YT_PLAYLIST_MAX` (currently 50, increase for full crawl)

**Action:** Fix the `/yt/download` endpoint bug (the `YoutubeDL.__exit__` PermissionError from the root-owned cookie volume), then use `/yt/playlist` for batch processing instead of the custom tool.

## Transcribe-and-Fetch Leverage Points

Rather than building parallel transcription, use transcribe-and-fetch for what it does best:

1. **High-quality local transcription** — Faster-Whisper large-v3 on GPU (better accuracy than ffmpeg-whisper)
2. **Structured output** — Markdown tables with clickable timestamps (useful for agent review)
3. **Obsidian integration** — Dual-write to vault for human-accessible knowledge base
4. **LLM Registry** — Can route to multiple transcription models via LiteLLM proxy

**Integration path:** Wire the declared NATS subjects (`transcribe.fetch.request.v1`) so PMOVES.YT's NATS events trigger transcribe-and-fetch for high-quality transcription as an alternative to the built-in ffmpeg-whisper path.

## DeepResearch + SupaSearch Leverage Points

1. **Content analysis** — After videos are transcribed and indexed in Hi-RAG, DeepResearch can analyze thematic clusters across the 2028-video corpus
2. **Research agent** — SupaSearch orchestrates across DeepResearch + Hi-RAG + Archon to answer questions about the crawled content
3. **Knowledge synthesis** — DeepResearch mirrors to Open Notebook, creating a structured knowledge base from raw video transcripts
4. **CGP geometry** — Research results emit geometry packets that feed shape discovery and persona grounding

**Integration path:** After batch ingestion, publish research requests to `research.deepresearch.request.v1` with topics derived from the keyword clusters (AI/ML: 1815 videos, Energy: 1483, etc.).

## JuiceFS Integration with Pipeline

JuiceFS POSIX mount benefits each service differently:

| Service | Current Storage | JuiceFS Benefit |
|---------|----------------|-----------------|
| PMOVES.YT | S3/MinIO buckets | Direct file write to `/mnt/pmoves/media/video/` (no S3 roundtrip) |
| Transcribe-and-fetch | Local workspace + Obsidian | Shared vault at `/mnt/pmoves/media/transcripts/` visible across nodes |
| DeepResearch | Open Notebook API | Direct read from JuiceFS mount for transcript analysis |
| Publisher | S3 download → local FS | Zero-copy hardlink (Mode B) instead of fget_object download |
| Jellyfin | Local bind mount `/media` | Same mount as content — instant library visibility |
| ComfyUI | S3 `pmoves-comfyui` bucket | Direct write to `/mnt/pmoves/media/images/comfyui/` |
| Flute-Gateway | In-memory streaming | Persist TTS output to `/mnt/pmoves/media/audio/tts-output/` |

## Immediate Actions (Revised)

1. **Fix PMOVES.YT service endpoint bug** — The `/yt/download` and `/yt/ingest` endpoints fail because of the root-owned cookie volume. Fix: ensure the container startup properly copies cookies to a writable path AND that `YT_COOKIES` env var (used by `_with_ytdlp_defaults`) points there. Then `/yt/playlist` can be used for batch processing.

2. **Increase YT_PLAYLIST_MAX** — Set to 2000+ to allow full playlist batch processing.

3. **Implement JuiceFS Phase 1** — PostgreSQL metadata backend, POSIX mount on Knuckles, directory structure.

4. **Wire NATS event consumers** — Connect transcribe-and-fetch to the declared NATS subjects for high-quality transcription alternative.

5. **Test DeepResearch on crawled content** — After first batch of transcripts is indexed in Hi-RAG, publish research requests for thematic analysis.
