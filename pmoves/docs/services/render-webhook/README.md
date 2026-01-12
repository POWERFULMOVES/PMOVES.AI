# render-webhook — Service Guide

Status: Implemented (compose)

Overview
- ComfyUI completion webhook that writes to Supabase.

Compose
- Service: `render-webhook`
- Port: `8085:8085`
- Profiles: `workers`, `orchestration`
- Depends on: (none explicit) — expects `postgrest` reachable

Environment
- `SUPA_REST_URL` (default `http://postgrest:3000`)
- `DEFAULT_NAMESPACE` (default `pmoves`)
- `RENDER_WEBHOOK_SHARED_SECRET`
- `RENDER_AUTO_APPROVE` (default `false`)

Smoke
```
docker compose up -d postgrest render-webhook
docker compose ps render-webhook
curl -sS http://localhost:8085/ | head -c 200 || true
docker compose logs -n 50 render-webhook
```
