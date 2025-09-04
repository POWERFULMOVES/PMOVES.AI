# PMOVES.YT — Video Ingestion Service

Endpoints
- POST `/yt/info`: { url } → returns { id, title, uploader, duration, webpage_url }.
- POST `/yt/download`: { url, bucket?, namespace? } → downloads MP4, uploads to S3 at `yt/<id>/raw.mp4`, optional thumbnail; inserts `studio_board` + `videos`; emits `ingest.file.added.v1`.
- POST `/yt/transcript`: { video_id, bucket?, namespace?, language?, whisper_model? } → extracts audio + runs Whisper (via ffmpeg‑whisper); inserts `transcripts`; emits `ingest.transcript.ready.v1`.
- POST `/yt/ingest`: convenience: info + download + transcript.

Compose
- `pmoves-yt` (8077) and `ffmpeg-whisper` (8078) included under profiles `workers|orchestration|agents`.

Supabase tables
- `videos` (video_id, namespace, title, source_url, s3_base_prefix, meta)
- `transcripts` (video_id, language, text, s3_uri, meta)
- (Next) `detections`, `segments`, `emotions` for video/audio analysis

Flow
1) `/yt/ingest` with URL
2) `/yt/download` → S3 raw.mp4, Studio row, `videos` insert, `ingest.file.added.v1`
3) `/yt/transcript` → audio extract + Whisper, `transcripts` insert, `ingest.transcript.ready.v1`
4) Downstream: LangExtract → extract-worker → Hi‑RAG + Neo4j; Jellyfin refresh + Discord embeds (pending)

Notes
- ffmpeg‑whisper currently uses OpenAI Whisper; GPU path is to switch to `faster-whisper`.
- For Jetson, use L4T PyTorch bases and CUDA‑enabled models.
