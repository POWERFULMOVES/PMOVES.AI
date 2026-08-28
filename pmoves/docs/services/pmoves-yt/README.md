# pmoves-yt — Service Guide

Status: Implemented (compose)

> **Operating this service?** See [`RUNBOOK.md`](./RUNBOOK.md) — bring-up, health checks,
> the cookie chain, failure triage, teardown. Start with its §1: there are two deployment
> paths, only one of them actually runs, and §1.1 is how you tell which you are on.

Overview
- YouTube ingest and processing; integrates with MinIO and Supabase.
- Authoritative runtime now lives in the [PMOVES.YT submodule](C:/Users/russe/Documents/GitHub/PMOVES.AI/PMOVES.YT) under `pmoves_yt_service/`.
- Root `pmoves/services/pmoves-yt` is now a compatibility mirror/shim, not the source of truth.

Compose
- Service: `pmoves-yt`
- Port: `8077:8077`
- Profiles: `orchestration`, `workers`, `agents`
- Depends on: `minio`
- Build context: `../PMOVES.YT`
- Dockerfile: `pmoves_yt_service/Dockerfile`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `YT_BUCKET` (default `assets`)
- `INDEXER_NAMESPACE` (default `pmoves`)
- `SUPA_REST_URL` (default `http://postgrest:3000`)
- `NATS_URL` (default `nats://nats:pmoves@nats:4222`)
- `HIRAG_URL` (default `http://hi-rag-gateway:8086`)
- `YT_RATE_LIMIT` (seconds; per-item sleep during playlist/channel ingest; read at call time so test overrides via env are honored)

Smoke
```
docker compose up -d minio pmoves-yt
docker compose ps pmoves-yt
curl -sS http://localhost:8077/healthz
curl -sS http://localhost:8077/yt/docs/catalog
curl -sS -X POST http://localhost:8077/yt/docs/sync
docker compose logs -n 50 pmoves-yt
```
