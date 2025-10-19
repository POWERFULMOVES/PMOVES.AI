# media-audio — Service Guide

Status: Implemented (compose)

Overview
- GPU audio analysis (emotion, features) with MinIO integration.

Compose
- Service: `media-audio`
- Port: `8082:8082`
- Profiles: `workers`, `orchestration`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `NVIDIA_VISIBLE_DEVICES` (default `all`)
- `EMOTION_MODEL` (default `superb/hubert-large-superb-er`)
- `GPU_COUNT` (deploy reservation)

Smoke
```
docker compose up -d minio media-audio
docker compose ps media-audio
curl -sS http://localhost:8082/ | head -c 200 || true
docker compose logs -n 50 media-audio
```
