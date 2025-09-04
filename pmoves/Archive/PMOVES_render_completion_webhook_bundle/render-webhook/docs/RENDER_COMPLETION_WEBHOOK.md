# Render Completion Webhook
Connect **ComfyUI** outputs to **Supabase Studio Board** via a small FastAPI service.

## Flow
ComfyUI uploads output to MinIO via presign → posts completion to `/comfy/webhook` →
this service inserts a `studio_board` row (`status=submitted` by default). Your n8n
notifications fire; after approval the Indexer + Publisher complete the pipeline.

## Service
- Env:
```
SUPA_REST_URL=http://postgrest:3000
DEFAULT_NAMESPACE=pmoves
RENDER_WEBHOOK_SHARED_SECRET=change_me
RENDER_AUTO_APPROVE=false
```
- Compose: see `compose-render-webhook-snippet.yml`

## ComfyUI node
Copy `comfyui/custom_nodes/pmoves_webhook/pmoves_completion_webhook.py` to ComfyUI.
Env:
```
PMOVES_WEBHOOK_URL=http://<host>:8085/comfy/webhook
PMOVES_WEBHOOK_TOKEN=change_me
```
Node: **PMOVES • Completion Webhook → Supabase**.
