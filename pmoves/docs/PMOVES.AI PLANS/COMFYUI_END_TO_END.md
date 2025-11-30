# ComfyUI End‑to‑End (Upload + Webhook)
_Last updated: 2025-08-29_

## Setup
- Install custom nodes:
  - `pmoves_minio_nodes` (Upload Image / Upload File Path)
  - `pmoves_webhook` (Completion Webhook → Supabase)
- Env for ComfyUI process:
```
PMOVES_PRESIGN_URL=http://<host>:8088
PMOVES_PRESIGN_TOKEN=<PRESIGN_SHARED_SECRET>
PMOVES_WEBHOOK_URL=http://<host>:8085/comfy/webhook
PMOVES_WEBHOOK_TOKEN=<RENDER_WEBHOOK_SHARED_SECRET>
```

## Minimal Graph
1) Generate image → 2) Upload Image (MinIO) → 3) Completion Webhook

## Tips
- Use deterministic filenames (`key_prefix=comfy/{date}/`, `filename={artist}_{seed}.png`).
- Pass `auto_approve=true` during exploration; disable for review flows.
