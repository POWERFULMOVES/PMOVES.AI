# MinIO — Object Storage

Status: Compose-managed (data plane)

Overview
- S3-compatible storage for assets, extracts, and notebooks.

Compose
- Service: `minio`
- Ports: `9000:9000` (API), `9001:9001` (console)
- Profile: `data`
- Network: `pmoves-net`

Used by
- `presign` (signed URLs), `ffmpeg-whisper`, `extract-worker`, `pdf-ingest`, `pmoves-yt`

Env (clients)
- `MINIO_ENDPOINT=minio:9000`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE=false`

Make
- `make up` starts minio; smoke tests exercise upload/ingest paths via presign/extract.
