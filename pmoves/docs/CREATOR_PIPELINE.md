# PMOVES v5 • Creator Pipeline (ComfyUI → MinIO → Webhook → Supabase → Indexer → Publisher)
_Last updated: 2025-08-29_

This doc shows the end‑to‑end creative flow from **ComfyUI** render to **Discord/Jellyfin** publish.

## Overview
1. **ComfyUI** renders an image/video.
2. **Presign microservice** issues PUT/GET URLs for MinIO/S3.
3. **ComfyUI nodes** upload the asset to MinIO (`s3://outputs/comfy/...`).
4. **Render Webhook** posts a completion to `/comfy/webhook`.
5. **Supabase** gets a new `studio_board` row (`submitted` or `approved`).
6. **n8n** notifies reviewers; on approval, **Indexer** ingests → Qdrant/Meili/Neo4j.
7. **Publisher** emits `content.published.v1`, posts **Discord embed**, and refreshes **Jellyfin** (optional).

## Services
- Presign: `pmoves-v5/services/presign` (port 8088)
- Render Webhook: `pmoves-v5/services/render-webhook` (port 8085)
- Supabase CE + PostgREST: profiles `data`
- Indexer: profile `workers`
- Publisher: profile `workers`
- n8n: profile `orchestration`

## .env (excerpt)
```
# Presign
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
ALLOWED_BUCKETS=assets,outputs
PRESIGN_SHARED_SECRET=change_me

# Render Webhook
RENDER_WEBHOOK_SHARED_SECRET=change_me
RENDER_AUTO_APPROVE=false

# Publisher enrichments
PUBLISHER_NOTIFY_DISCORD_WEBHOOK=...
PUBLISHER_REFRESH_ON_PUBLISH=true
PUBLISHER_EMBED_COVER=true
```

## Compose snippets
- `compose-presign-snippet.yml`
- `compose-render-webhook-snippet.yml`

```
docker compose --profile data up -d presign
docker compose --profile orchestration up -d render-webhook
```

## ComfyUI graph (minimal)
```
[Generate Image] → [PMOVES • Upload Image (MinIO)] → [PMOVES • Completion Webhook → Supabase]
```

Node inputs:
- Upload Image: `bucket=outputs`, `key_prefix=comfy/`, `filename=<your-name>.png`
- Completion Webhook: `s3_uri`, `presigned_get` (from Upload node), `title`, `namespace=pmoves`, `author=DARKXSIDE`, `tags`

## Approve → Publish
- In Supabase Studio, set `status=approved` (or use `RENDER_AUTO_APPROVE=true`).
- Indexer will ingest; Publisher will post to Discord and link/refresh Jellyfin.
- Audit breadcrumbs are stored in `publisher_audit`.
