# firefly-iii — Integration Guide

Status: In progress (external stack; compose bundle available)

Overview
- Firefly III is a self-hosted personal finance manager with a REST API and personal access tokens.
- In PMOVES, treat Firefly as a finance telemetry source for budgeting insights, spend summaries, and goal tracking.

## Geometry Bus (CHIT) Integration
- Current: No direct CHIT endpoints.
- Planned: generate category/time-bucket constellations from normalized transactions to visualize spending clusters and trend anchors in the geometry UI.
- Design references:
  - UI: `../../../docs/Unified and Modular PMOVES UI Design.md`
  - CHIT decoder/specs: `../../PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md`

Deployment
- Local compose: use `make integrations-up-firefly` for Firefly only or `make integrations-up-all` for Firefly + Wger + watcher.
- Flows live under `pmoves/integrations/firefly-iii/n8n/flows/`; drop exported JSON there for auto-imports when the watcher is running.

Networking/Ports
- Default Firefly web: `8080` (as defined in the compose bundle)

Environment
- `FIREFLY_BASE_URL` (e.g., `http://cataclysm-firefly:8080` on the compose network)
- `FIREFLY_ACCESS_TOKEN` (personal access token)

API/Contracts
- Endpoints of interest: `/api/v1/transactions`, `/api/v1/accounts`, `/api/v1/budgets`.
- Auth via `Authorization: Bearer <token>` header.

- Store `FIREFLY_ACCESS_TOKEN` in PMOVES secrets.
- n8n flows in `pmoves/integrations/firefly-iii/n8n/flows/` poll Firefly transactions, normalize categories, and write to Supabase.

Smoke
```
curl -sS -H "Authorization: Bearer $FIREFLY_ACCESS_TOKEN" "$FIREFLY_BASE_URL/api/v1/transactions?limit=1" | jq '.data[0] | {journal_id: .id, description: .attributes.description}'
```

Supabase quick checks
- Upsert a synthetic transaction (dev only):
```
curl -sS -X POST "$SUPA_REST_URL/finance_transactions" \
  -H "content-type: application/json" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Prefer: resolution=merge-duplicates" \
  -d '{"namespace":"pmoves","source":"firefly","external_id":"demo-1","occurred_at":"2025-10-18T00:00:00Z","amount":12.34,"currency":"USD","description":"demo"}' | jq
```
- Verify insert:
```
curl -sS "$SUPA_REST_URL/finance_transactions?external_id=eq.demo-1" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | jq '.[0]'
```

Workflow activation (n8n)
- Set env in compose or n8n credentials: `FIREFLY_BASE_URL`, `FIREFLY_ACCESS_TOKEN`, `SUPA_REST_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Import and activate `Finance Firefly Sync (stub)` and run a manual execution. Expect rows in `finance_*` and an event on `finance.transactions.ingested.v1`.
 - Demo flow JSON: `pmoves/n8n/flows/finance_monthly_to_cgp.json` (manual trigger builds a monthly summary → maps to CGP → POSTs to gateway).

Integration Review (PMOVES)
- Storage: `finance.transactions`, `finance.accounts`, `finance.budgets` in Supabase.
- Events: `finance.transactions.ingested.v1` emitted on new data to trigger analytics.
- Agents: Budget coach persona or dashboard generator consuming normalized tables.

Related Plans/Docs
- Compose profiles and automation scripts now live directly under `pmoves/compose/` and `pmoves/scripts/` (see `docker-compose.firefly.yml`, `docker-compose.flows-watcher.yml`, and `scripts/n8n-*.sh`).

Next Steps — CHIT
- Define `finance.monthly.summary.v1` events and a mapper to CGPs (anchors: categories; spectrum: budget variance; points: transactions or buckets). Render summaries in geometry UI and surface anomalies to agents.
- Leverage Creator tutorials for artwork/voiceovers in generated artifacts (see `pmoves/creator/tutorials/*_tutorial.md`).

Next Steps
- Define Supabase schemas + RLS for finance domains.
- Add reconciliation job to dedupe/merge recurring transactions.
