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

## PMOVES.YT
Info + download + transcript (replace URL):
```
curl -s -X POST http://localhost:8077/yt/info \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=XXXXXXXX"}' | jq .

curl -s -X POST http://localhost:8077/yt/download \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=XXXXXXXX","bucket":"assets","namespace":"pmoves"}' | jq .

# Use the returned video_id from /yt/download
curl -s -X POST http://localhost:8077/yt/transcript \
  -H 'content-type: application/json' \
  -d '{"video_id":"<id>","bucket":"assets"}' | jq .

# Verify rows
curl -s "http://localhost:3000/videos?order=id.desc&limit=1" | jq .
curl -s "http://localhost:3000/transcripts?order=id.desc&limit=1" | jq .
```

## FFmpeg+Whisper
Transcribe directly from raw video:
```
curl -s -X POST http://localhost:8078/transcribe \
  -H 'content-type: application/json' \
  -d '{"bucket":"assets","key":"yt/<id>/raw.mp4","out_audio_key":"yt/<id>/audio.m4a"}' | jq .
```

## Media-Video (YOLO)
Detect objects on frames every N seconds:
```
curl -s -X POST http://localhost:8079/detect \
  -H 'content-type: application/json' \
  -d '{"bucket":"assets","key":"yt/<id>/raw.mp4","video_id":"<id>"}' | jq .
```

## Media-Audio (Emotion)
Classify top emotion per 5s window:
```
curl -s -X POST http://localhost:8082/emotion \
  -H 'content-type: application/json' \
  -d '{"bucket":"assets","key":"yt/<id>/audio.m4a","video_id":"<id>"}' | jq .
```

## Agents Profile
Bring up: `docker compose --profile agents up -d nats agent-zero archon`
Health:
```
curl -s http://localhost:8080/healthz | jq .   # agent-zero
curl -s http://localhost:8091/healthz | jq .   # archon
```
