# PMOVES.YT — Video Ingestion Service

Endpoints
- POST `/yt/info`: { url } → returns { id, title, uploader, duration, webpage_url }.
- POST `/yt/download`: { url, bucket?, namespace? } → downloads MP4, uploads to S3 at `yt/<id>/raw.mp4`, optional thumbnail; inserts `studio_board` + `videos`; emits `ingest.file.added.v1`.
- POST `/yt/transcript`: { video_id, bucket?, namespace?, language?, whisper_model? } → extracts audio + runs Whisper (via ffmpeg‑whisper); inserts `transcripts`; emits `ingest.transcript.ready.v1`.
- POST `/yt/ingest`: convenience: info + download + transcript.
- POST `/yt/playlist`: { url, namespace?, bucket?, max_videos?, … } → iterates playlist, tracks job state in `yt_jobs/yt_items`, downloads + transcribes each video.
- POST `/yt/channel`: { url|channel_id, ... } → same as playlist for a channel.
- POST `/yt/summarize`: { video_id, style: short|long, provider?: ollama|hf } → uses Gemma (Ollama or HF) to summarize transcript; stores in `videos.meta.gemma`.
- POST `/yt/chapters`: { video_id, provider? } → handles chapter extraction, returns JSON array [{title, blurb}], stores in `videos.meta.gemma.chapters`.
- POST `/yt/emit`: { video_id, namespace?, text? } → segments transcript into retrieval chunks (JSONL) and emits CGP to the Geometry Bus; pushes chunks via `hi-rag-v2 /hirag/upsert-batch`.
## Playlist/Channel ingest

### Concurrent processing

Playlists and channels can be processed in parallel. `YT_CONCURRENCY` controls how many videos are handled at once (default `2`). `YT_RATE_LIMIT` adds a delay in seconds between starting each video to avoid quota issues (default `0`, meaning no delay).

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
- ffmpeg‑whisper currently uses OpenAI Whisper; GPU path is to switch to `faster-whisper`.
- For Jetson, use L4T PyTorch bases and CUDA‑enabled models.
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
