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

## Publisher Audit Trail & Incident Playback

Every approval event that reaches the Publisher now lands in the Supabase table `publisher_audit`. The row is keyed by the incoming `content.publish.approved.v1` event ID and captures reviewer context, where the artifact ended up, and whether processing succeeded or failed.

| Column | Notes |
| --- | --- |
| `publish_event_id` | UUID of the inbound approval envelope (`content.publish.approved.v1`). Primary key for the audit row. |
| `approval_event_ts` | Timestamp from the approval envelope. Useful for ordering alongside Supabase row history. |
| `correlation_id` | Correlation chain identifier so you can pivot back to upstream renders or review bots. |
| `artifact_uri` | Original MinIO/S3 URI received from the approval event (may be `NULL` on malformed events). |
| `artifact_path` | Absolute path where the Publisher wrote the file. Set even on download failures so you know the intended target. |
| `namespace` | Logical namespace used for slug + directory derivation. |
| `reviewer` / `reviewed_at` | Reviewer identity (pulled from payload/meta) and when they approved. Falls back to the envelope timestamp if no explicit approval time is present. |
| `status` | `published` or `failed`. Failures include `failure_reason` with the exception string from the publisher. |
| `published_event_id` / `published_at` | Envelope data for the downstream `content.published.v1` emission when it succeeds. |
| `public_url` | Publicly accessible URL recorded for Discord/Jellyfin consumption. |
| `processed_at` / `updated_at` | When the publisher handled the event. These auto-update on retries/upserts. |
| `meta` | JSON payload containing the source `meta`, resolved slug/namespace, Jellyfin refresh notes, etc. |

### Playback workflow when something goes wrong

1. **Identify the event** – grab the `publish_event_id` (from logs or n8n) or filter by `artifact_path`/`namespace`:
   ```sql
   select *
   from publisher_audit
   where publish_event_id = '...';
   ```
2. **Check status & failure_reason** – if the row is `failed`, the text explains which stage (validation, download, Jellyfin, etc.) blew up. The `meta` JSON also records the stage for faster triage.
3. **Rehydrate the artifact** – use `artifact_uri` to pull from MinIO/S3 (e.g., `mc cp`) or inspect the partially written file at `artifact_path` if the download finished.
4. **Follow the correlation chain** – `correlation_id` lets you query upstream services (render webhook, indexer) for matching entries or envelopes.
5. **Replay downstream effects** – on successful publishes, the `published_event_id`/`published_at` pair helps confirm what Discord/Jellyfin saw. Use the ID to search the NATS event log or your monitoring sink for the emitted envelope.
6. **Document the resolution** – once fixed, upsert a new audit row (same `publish_event_id`) with status `published`. The trigger keeps `updated_at` current so auditors can see when the replay happened.

Because the audit table is append-friendly (via upsert on `publish_event_id`), replays are straightforward: re-run the publisher with the same approval payload and it will overwrite the row with the latest status while preserving the original timestamps for comparison.
