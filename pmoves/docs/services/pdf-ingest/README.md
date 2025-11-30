# pdf-ingest — Service Guide

Status: Implemented (compose)

Overview
- Watches PDFs, uploads to MinIO, triggers extract-worker via webhook.

Compose
- Service: `pdf-ingest`
- Port: `8092:8092`
- Profiles: `workers`, `orchestration`
- Depends on: `minio`, `extract-worker`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `PDF_DEFAULT_BUCKET` (default `assets`)
- `PDF_DEFAULT_NAMESPACE` (default `pmoves`)
- `PDF_MAX_PAGES` (default `0`)
- `PDF_INGEST_EXTRACT_URL` (default `http://extract-worker:8083/ingest`)
- `NATS_URL` (default `nats://nats:4222`)

Smoke
```
docker compose up -d minio extract-worker pdf-ingest
docker compose ps pdf-ingest
curl -sS http://localhost:8092/ | head -c 200 || true
docker compose logs -n 50 pdf-ingest
```
