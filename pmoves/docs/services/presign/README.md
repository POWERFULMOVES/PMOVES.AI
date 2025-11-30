# presign — Service Guide

Status: Implemented (compose)

Overview
- MinIO presign API for ComfyUI uploads and asset ingest.

Compose
- Service: `presign`
- Port: `8088:8080`
- Profiles: `data`, `orchestration`
- Depends on: `minio`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `AWS_DEFAULT_REGION` (default `us-east-1`)
- `ALLOWED_BUCKETS` (default `assets,outputs`)
- `PRESIGN_SHARED_SECRET`

Smoke
```
docker compose up -d minio presign
docker compose ps presign
curl -sS http://localhost:8088/ | head -c 200 || true
docker compose logs -n 50 presign
```
