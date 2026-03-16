# TAC_PMOVES_YT
_Last updated: 2026-03-15_

## Mission

Download, transcribe, and index YouTube content through an event-driven pipeline. PMOVES.YT is the entry point for media ingestion — it downloads videos to MinIO, retrieves/generates transcripts, and publishes NATS events that trigger downstream processing (embedding, indexing, notification).

## Current State

- **Port:** 8077
- **Submodule:** `PMOVES.YT`
- **API:** `POST http://localhost:8077/yt/ingest`
- **Dependencies:** MinIO (9000), FFmpeg-Whisper (8078), NATS (4222), Supabase
- **Downstream:** Extract Worker (8083), Hi-RAG v2 (8086), Publisher-Discord (8094), Notebook Sync (8095)

## Architecture

```
Channel Monitor (8097)          Manual API Call
       │                              │
       └──────────┬───────────────────┘
                  │
                  ▼
          PMOVES.YT (8077)
                  │
       ┌──────────┼──────────┐
       │          │          │
       ▼          ▼          ▼
    MinIO     Supabase    NATS
   (video)   (metadata)  (events)
       │                     │
       ▼                     ├── ingest.file.added.v1
  FFmpeg-Whisper             ├── ingest.transcript.ready.v1
   (8078)                    ├── ingest.summary.ready.v1
       │                     └── ingest.chapters.ready.v1
       ▼
  Extract Worker ──► Qdrant + Meilisearch
   (8083)                    │
                             ▼
                     Publisher-Discord (8094)
                     Notebook Sync (8095)
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `ingest.file.added.v1` | Publish | New file stored in MinIO |
| `ingest.transcript.ready.v1` | Publish | Transcript completed |
| `ingest.summary.ready.v1` | Publish | Summary generated |
| `ingest.chapters.ready.v1` | Publish | Chapter markers created |

## Related Services

| Service | Port | Role |
|---------|------|------|
| Channel Monitor | 8097 | Detects new content, triggers ingestion |
| FFmpeg-Whisper | 8078 | GPU-accelerated transcription (Faster-Whisper) |
| Extract Worker | 8083 | Text embedding + Qdrant/Meilisearch indexing |
| Media-Video | 8079 | YOLOv8 object/frame analysis |
| Media-Audio | 8082 | Emotion/speaker detection |
| Notebook Sync | 8095 | SurrealDB Open Notebook sync |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHANNEL_MONITOR_QUEUE_URL` | `http://pmoves-yt:8077/yt/ingest` | Ingest endpoint |
| `WHISPER_MODEL` | `small` | Whisper model size |
| `MINIO_ROOT_USER` | `minioadmin` | MinIO credentials |

## Phases

1. **Detect** — Channel Monitor polls for new content (300s interval)
2. **Download** — PMOVES.YT fetches video to MinIO `assets` bucket
3. **Transcribe** — FFmpeg-Whisper generates transcript (GPU-accelerated)
4. **Index** — Extract Worker embeds transcript to Qdrant + Meilisearch
5. **Analyze** — Media-Video (YOLOv8) + Media-Audio (speaker/emotion)
6. **Notify** — Publisher-Discord sends notification, Notebook Sync persists

## Production Readiness

| Check | Status |
|-------|--------|
| NATS integration | Active (4 subjects) |
| MinIO storage | Persistent volumes |
| Auth | Network isolation |
| Docker Compose | Profile: `yt` |
| SoundCloud | Partial (PR #955 adds initial support) |

## Verification

```bash
curl -X POST http://localhost:8077/yt/ingest -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=dQw4w9WgXcQ"}'
nats sub "ingest.>" --count=3
```
