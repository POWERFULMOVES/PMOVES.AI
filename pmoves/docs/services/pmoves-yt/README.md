# pmoves-yt — Service Guide

Status: Implemented (compose)

> **Operating this service?** See [`RUNBOOK.md`](./RUNBOOK.md) — bring-up, health checks,
> the cookie chain, failure triage, teardown. Start with its §1: there are two deployment
> paths, only one of them actually runs, and §1.1 is how you tell which you are on.

Overview
- YouTube ingest and processing; integrates with MinIO and Supabase.
- Authoritative runtime lives in the `PMOVES.YT` submodule (repo-root sibling of `pmoves/`) under `pmoves_yt_service/`.
- Root `pmoves/services/pmoves-yt` is now a compatibility mirror/shim, not the source of truth.

Compose
- Service: `pmoves-yt`
- Port: `8077:8077`
- Profiles: none (always-on with the core stack; run via `make up-yt` which adds the yt-cookies overlay)
- Depends on: `minio`
- Build context: `../PMOVES.YT`
- Dockerfile: `pmoves_yt_service/Dockerfile`

Environment
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`
- `YT_BUCKET` (default `assets`)
- `INDEXER_NAMESPACE` (default `pmoves`)
- `SUPA_REST_URL` (default `http://supabase-kong:8000/rest/v1`)
- `NATS_URL` (default `nats://nats:pmoves@nats:4222`)
- `HIRAG_URL` (default `http://hi-rag-gateway-v2:8086`)
- `YT_RATE_LIMIT` (seconds; per-item sleep during playlist/channel ingest; read at call time so test overrides via env are honored — set via env_file, not compose defaults)

Smoke (Known Road — raw `docker compose up` is hook-blocked)
```
make -C pmoves up-yt
curl -sS http://localhost:8077/healthz
curl -sS http://localhost:8077/yt/docs/catalog
curl -sS -X POST http://localhost:8077/yt/docs/sync
docker compose logs -n 50 pmoves-yt
```
