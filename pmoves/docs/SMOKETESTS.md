# Smoke Tests
Last updated: 2025-08-29

## Quick commands
- Start stack: `make up`
- Stop all: `make down`
- Nuke local volumes: `make clean`
- One-shot smoke: `make smoke`

## Health checks
- Presign: http://localhost:8088/healthz
- Render Webhook: http://localhost:8085/healthz
- Hi‑RAG v2 stats: http://localhost:8087/hirag/admin/stats
- Retrieval Eval UI: http://localhost:8090
- PostgREST: http://localhost:3000

## Example queries
Hybrid + rerank query:
```
curl -s localhost:8087/hirag/query \
  -H 'content-type: application/json' \
  -d '{"query":"what is pmoves?","namespace":"pmoves","k":8,"alpha":0.7}' | jq .
```

Webhook insert + verify:
```
curl -s -X POST http://localhost:8085/comfy/webhook \
  -H 'content-type: application/json' \
  -H "Authorization: Bearer ${RENDER_WEBHOOK_SHARED_SECRET:-change_me}" \
  -d '{"bucket":"outputs","key":"demo.png","s3_uri":"s3://outputs/demo.png","title":"Demo","namespace":"pmoves","author":"local","tags":["demo"],"auto_approve":false}'

curl -s "http://localhost:3000/studio_board?order=id.desc&limit=1" | jq .
```

## Individual smoke targets
- `make smoke`: end-to-end presign/webhook/postgrest and a basic Hi-RAG query.
- `make smoke-rerank`: calls Hi-RAG with reranking enabled (requires the model to be available).
- `make smoke-presign-put`: obtains a presigned PUT URL and uploads a small text file to MinIO.

## Publisher Enrichments
- Archive: `PMOVES_publisher_enrich_smoketest.zip`
- Script: `smoketest_publisher_enrich.sh`
- Validates: `published_events` record + `publisher_audit` rows and (optionally) Discord notification.

## Presign
- Use curl examples in `COMFYUI_MINIO_PRESIGN.md` to PUT/GET a text file.
