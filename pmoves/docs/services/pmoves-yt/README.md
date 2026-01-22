# pmoves-yt — Service Guide

Status: Implemented (compose)

Overview
- YouTube ingest and processing; integrates with MinIO and Supabase.

Compose
- Service: `pmoves-yt`
- Port: `8077:8077`
- Profiles: `orchestration`, `workers`, `agents`
- Depends on: `minio`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `YT_BUCKET` (default `assets`)
- `INDEXER_NAMESPACE` (default `pmoves`)
- `SUPA_REST_URL` (default `http://postgrest:3000`)
- `NATS_URL` (default `nats://nats:4222`)
- `HIRAG_URL` (default `http://hi-rag-gateway:8086`)
- `YT_RATE_LIMIT` (seconds; per-item sleep during playlist/channel ingest; read at call time so test overrides via env are honored)

Smoke
```
docker compose up -d minio pmoves-yt
docker compose ps pmoves-yt
curl -sS http://localhost:8077/ | head -c 200 || true
docker compose logs -n 50 pmoves-yt
```
