# media-video — Service Guide

Status: Implemented (compose)

Overview
- GPU visual detection/segmentation with MinIO integration.

Compose
- Service: `media-video`
- Port: `8079:8079`
- Profiles: `workers`, `orchestration`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `NVIDIA_VISIBLE_DEVICES` (default `all`)
- `YOLO_MODEL` (default `yolov8n.pt`), `FRAME_EVERY` (default `5`), `SCORE_THRES` (default `0.25`)
- `GPU_COUNT` (deploy reservation)

Smoke
```
docker compose up -d minio media-video
docker compose ps media-video
curl -sS http://localhost:8079/ | head -c 200 || true
docker compose logs -n 50 media-video
```
