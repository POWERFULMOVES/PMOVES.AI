# TAC_MEDIA_ANALYSIS
_Last updated: 2026-03-15_

## Mission

GPU-accelerated media analysis for video and audio content. Two worker services process files from MinIO, generating structured metadata (object detection, speaker identification, emotion classification) stored in Supabase.

## Services

### Media-Video Analyzer (8079)
- **Role:** Object and frame analysis using YOLOv8
- **Sampling:** Every 5th frame
- **Confidence threshold:** 0.25
- **Output:** Supabase (object annotations, frame metadata)
- **GPU:** Required (NVIDIA CUDA)
- **Docker Profile:** `workers`

### Media-Audio Analyzer (8082)
- **Role:** Emotion detection and speaker identification
- **Model:** `superb/hubert-large-superb-er`
- **Output:** Supabase (speaker segments, emotion labels)
- **GPU:** Required (NVIDIA CUDA)
- **Docker Profile:** `workers`

## Architecture

```
PMOVES.YT / FFmpeg-Whisper
  │ (media files in MinIO)
  │
  ├─────────────────┐
  │                 │
  ▼                 ▼
Media-Video       Media-Audio
 (8079)            (8082)
  │                 │
  ├── YOLOv8        ├── HuBERT
  ├── Frame sample  ├── Speaker ID
  ├── Object detect ├── Emotion class
  │                 │
  └────────┬────────┘
           │
           ▼
       Supabase
    (structured metadata)
           │
           ▼
    Hi-RAG v2 / Dashboard
```

## Triggered By

Both services are triggered by the media ingestion pipeline:
1. PMOVES.YT downloads video to MinIO
2. FFmpeg-Whisper processes audio track
3. Media-Video analyzes video frames
4. Media-Audio analyzes audio segments
5. Results stored in Supabase for Hi-RAG retrieval

## Configuration

| Variable | Service | Description |
|----------|---------|-------------|
| `MINIO_ACCESS_KEY` | Both | MinIO credentials for reading media |
| `MINIO_SECRET_KEY` | Both | MinIO credentials |
| `SUPABASE_URL` | Both | Metadata storage |

## Production Readiness

| Check | Media-Video | Media-Audio |
|-------|-----------|------------|
| GPU | Required (CUDA) | Required (CUDA) |
| `/healthz` | TBD | TBD |
| NATS | N/A (Supabase direct) | N/A (Supabase direct) |
| Auth | Network isolation | Network isolation |
| Docker | `workers` profile | `workers` profile |
| MinIO | Read from `assets` bucket | Read from `assets` bucket |

## Verification

```bash
# Check services running
docker compose --profile workers ps | grep -E "media-video|media-audio"

# Verify GPU access
docker exec pmoves-media-video-1 nvidia-smi
```
