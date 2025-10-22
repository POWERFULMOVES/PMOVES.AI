# PMOVES.YT — Video Ingestion Service

Endpoints
- POST `/yt/info`: { url } → returns { id, title, uploader, duration, webpage_url }.
- POST `/yt/download`: { url, bucket?, namespace? } → downloads MP4, uploads to S3 at `yt/<id>/raw.mp4`, optional thumbnail; inserts `studio_board` + `videos`; emits `ingest.file.added.v1`.
- POST `/yt/transcript`: { video_id, bucket?, namespace?, language?, whisper_model?, provider? } → extracts audio + runs the selected transcription backend (`faster-whisper` default, `whisper`, or `qwen2-audio`); inserts `transcripts`; emits `ingest.transcript.ready.v1`.
- POST `/yt/ingest`: convenience: info + download + transcript.
- POST `/yt/playlist`: { url, namespace?, bucket?, max_videos?, … } → iterates playlist, tracks job state in `yt_jobs/yt_items`, downloads + transcribes each video.
- POST `/yt/channel`: { url|channel_id, ... } → same as playlist for a channel.
- POST `/yt/summarize`: { video_id, style, provider?: ollama|hf } → uses Gemma (Ollama or HF) to summarize transcript; stores in `videos.meta.gemma`. `style` must be either `short` or `long`.
- POST `/yt/chapters`: { video_id, provider? } → handles chapter extraction.
- POST `/yt/emit`: { video_id, namespace?, text? } → segments transcript into retrieval chunks (JSONL) and emits CGP to the Geometry Bus; pushes chunks via `hi-rag-v2 /hirag/upsert-batch`.
## Playlist/Channel ingest

### Concurrency & rate limiting

Playlist and channel ingestion runs inside an async worker pool so downloads and transcripts can progress in parallel. `YT_CONCURRENCY` sets the maximum number of in-flight videos (default `2`); setting it to `1` falls back to the legacy sequential flow. Each worker updates its `yt_items` row as it starts and finishes so Supabase job tracking stays accurate even when tasks complete out of order.

`YT_RATE_LIMIT` defines a shared delay (seconds) before new workers start downloading. When the limit is greater than zero, every worker waits on a global timer before beginning the download/transcription step. This means high values can effectively serialize start times even if the pool has multiple slots, but long-running jobs continue in parallel once started. Leave it at `0` to disable throttling.

Example:

```bash
export YT_CONCURRENCY=4
export YT_RATE_LIMIT=1.5
curl -X POST http://localhost:8077/yt/playlist \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.youtube.com/playlist?list=PL..."}'
```

Compose
- `pmoves-yt` (8077) and `ffmpeg-whisper` (8078) included under profiles `workers|orchestration|agents`.

Supabase tables
- `videos` (video_id, namespace, title, source_url, s3_base_prefix, meta)
- `transcripts` (video_id, language, text, s3_uri, meta)
- `yt_jobs` (id, type, args, state, started_at, finished_at, error, created_at)
- `yt_items` (job_id, video_id, status, error, retries, meta, created_at)
- (Next) `detections`, `segments`, `emotions` for video/audio analysis

Flow
1) `/yt/ingest` with URL
2) `/yt/download` → S3 raw.mp4, Studio row, `videos` insert, `ingest.file.added.v1`
3) `/yt/transcript` → audio extract + faster‑whisper (segments + full text), `transcripts` insert, `ingest.transcript.ready.v1`
4) `/yt/emit` → smart boundary segmentation from Whisper segments (gap>1.2s, strong punctuation+, duration caps); upsert chunks to Hi‑RAG v2; emit CGP with timecoded points
5) Downstream: LangExtract → extract-worker → Hi‑RAG + Neo4j; Jellyfin refresh + Discord embeds (pending)

Notes
- `ffmpeg-whisper` auto-detects CUDA GPUs (`WHISPER_DEVICE` / `USE_CUDA` override) and defaults to `faster-whisper`, falling back to CPU INT8 inference when no GPU is available.
- Set `provider` in `/yt/transcript` or `/yt/ingest` to choose `faster-whisper`, `whisper` (WhisperX + optional PyAnnote diarization), or `qwen2-audio` (requires Transformers + Qwen2 Audio weights; GPU strongly recommended for real-time throughput).
- For Jetson, use L4T PyTorch bases and CUDA‑enabled models.
- Downloader hardening:
  - `YT_PLAYER_CLIENT` (default `android`) and `YT_USER_AGENT` (Android Chrome UA) are injected into yt-dlp so player signatures resolve without manual cookies. Override when YouTube blocks the default fingerprint.
  - Set `YT_COOKIES=/path/to/cookies.txt` if you need authenticated fetches; the path is passed straight to yt-dlp.
  - `YT_FORCE_IPV4=true|false` (default true) avoids IPv6-only CDN nodes that intermittently reject API calls; disable if your network only supports IPv6.
  - `YT_EXTRACTOR_RETRIES` controls yt-dlp retry attempts (default `2`). Increase when scraping longer playlists or spotty connections.
- Gemma providers:
  - `YT_SUMMARY_PROVIDER=ollama|hf`, `OLLAMA_URL`, `YT_GEMMA_MODEL` (default gemma2:9b-instruct)
  - `HF_GEMMA_MODEL`, `HF_USE_GPU`, `HF_TOKEN` (requires transformers+torch if using HF locally)
- Segmentation heuristics:
  - Flush when: accumulated duration ≥ 30s, silence gap > 1.2s, strong punctuation with ≥ 600 chars, or hard caps (60s or 1500 chars)
  - Each chunk carries `payload.t_start`/`t_end`; CGP points mirror these for precise jumps
  - Tunables (env): `YT_SEG_TARGET_DUR` (sec), `YT_SEG_GAP_THRESH` (sec), `YT_SEG_MIN_CHARS`, `YT_SEG_MAX_CHARS`, `YT_SEG_MAX_DUR` (sec)
- Indexing:
  - `YT_INDEX_LEXICAL=true|false` (default true). When true, `/yt/emit` asks Hi‑RAG v2 to also index in Meili via `index_lexical`.
- Auto‑tune:
   - `YT_SEG_AUTOTUNE=true|false` (default true). When enabled, thresholds are auto‑tuned per video using Whisper segment stats (avg duration, gap, words/sec, short‑line ratio) to choose profiles: dialogue, talk, or lyrics.

## `/yt/chapters`

- Body: `{ video_id, provider? }`.
- Output: JSON array of chapter objects `[{title, blurb}]`.
- Persistence: results are stored under `videos.meta.gemma.chapters`.
- Providers: uses the same Gemma configuration as `/yt/summarize` (`YT_SUMMARY_PROVIDER`, `OLLAMA_URL`, `YT_GEMMA_MODEL`, `HF_GEMMA_MODEL`, `HF_USE_GPU`, `HF_TOKEN`).
