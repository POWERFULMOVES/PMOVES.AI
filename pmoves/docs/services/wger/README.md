# wger — Integration Guide

Status: In progress (external stack; compose bundle available)

Overview
- Wger is a self-hosted workout/nutrition tracker with a REST API.
- In PMOVES, treat Wger as a data provider for agents and automations (e.g., habit coaching, nutrition summaries, dashboarding).

Deployment
- Reference bundle: `pmoves/docs/PMOVES.AI PLANS/WGER - Firefly iii compose -integrations/`
- Quick start:
```
make -C "pmoves/docs/PMOVES.AI PLANS/WGER - Firefly iii compose -integrations" up-wger
```

Networking/Ports
- Default Wger web: `8000` (exposed via the compose bundle)

Environment
- `WGER_BASE_URL` (e.g., `http://wger:8000` on the compose network)
- `WGER_API_TOKEN` (personal access token)

API/Contracts
- Primary: Wger REST API (v2). Use token auth in `Authorization: Token <token>`.
- Data of interest: workout logs, body weight, nutrition diary entries.

Runbook
- Configure token in PMOVES secret store or `.env.local`.
- Build an n8n flow to periodically fetch logs and write summaries to Supabase.

Smoke
```
curl -sS "$WGER_BASE_URL/api/v2/workoutlog/" -H "Authorization: Token $WGER_API_TOKEN" | jq '.count'
```

Supabase quick checks
- Insert a synthetic row (dev only):
```
curl -sS -X POST "$SUPA_REST_URL/health_workouts" \
  -H "content-type: application/json" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -d '{"namespace":"pmoves","source":"wger","external_id":"smoke-1","observed_at":"2025-10-18T00:00:00Z","metrics":{"demo":true}}' | jq
```
- Verify insert:
```
curl -sS "$SUPA_REST_URL/health_workouts?external_id=eq.smoke-1" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | jq '.[0]'
```

Workflow activation (n8n)
- Set env in compose or n8n credentials: `WGER_BASE_URL`, `WGER_API_TOKEN`, `SUPA_REST_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Import and activate `Health Wger Sync (stub)` and run a manual execution. Expect upserts in `health_*` and an event on `health.metrics.updated.v1`.

Integration Review (PMOVES)
- Storage: Land normalized time series in Supabase (`health.workouts`, `health.nutrition`, `health.metrics_weight`).
- Events: Emit `health.metrics.updated.v1` after each sync for downstream agents.
- Agents: Create a lightweight analyzer to produce weekly summaries and goals.

Related Plans/Docs
- Compose bundle and scripts: `PMOVES.AI PLANS/WGER - Firefly iii compose -integrations/`

Next Steps
- Define Supabase schemas and RLS for per-user health data.
- Add n8n importable flow (JSON) under `pmoves/n8n/flows/` to demonstrate sync.
