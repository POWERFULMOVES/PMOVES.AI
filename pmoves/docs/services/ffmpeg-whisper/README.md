# ffmpeg-whisper — Service Guide

Status: Implemented (compose)

Overview
- GPU-enabled transcription service (faster-whisper).

Compose
- Service: `ffmpeg-whisper`
- Port: `8078:8078`
- Profiles: `workers`, `orchestration`, `agents`
- Depends on: `minio`

Environment
- `MINIO_ENDPOINT` (default `minio:9000`)
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE` (default `false`)
- `USE_CUDA` (default `true`)
- `NVIDIA_VISIBLE_DEVICES` (default `all`)
- `GPU_COUNT` (deploy reservation, default `all`)

Smoke
```
docker compose up -d minio ffmpeg-whisper
docker compose ps ffmpeg-whisper
curl -sS http://localhost:8078/ | head -c 200 || true
docker compose logs -n 50 ffmpeg-whisper
```
Ops Quicklinks
- Smoke: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next Steps: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)
