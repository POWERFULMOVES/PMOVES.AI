# Wealth Tri-Integration Recon (Wealth × Tokenism-Multi × DoX)

> **Date:** 2026-09-09 · **Node:** elder-melchor (overwatch seat) · **Lane:** wealth-tri-refresh (CLAIM 2026-09-09T17:10Z, TTL 2026-09-12)
> **Method:** live verification from the agent's own end (HTTP probes over tailnet), repo contract reads. No SSH to spark (tailnet ACL blocks user `elder`) — findings below are external observations, flagged as such.

## What the tri-integration IS (contracts)

- **Room manifest** `pmoves/config/rooms/tokenism.room.exchange.json` — public room "ToKenism Exchange", rehearsal stage:
  - app `tokenism-simulator` (route /dashboard/tokenism, capabilities simulate/scenario/calibrate/chit-sign) + app `wealth-ledger` (provider `firefly-iii`, route /demo/wealth, capabilities accounts/transactions/budgets/export-csv).
  - skill bindings `tokenism-run-scenario` (pmoves/tokenism-scenario-runner) and `tokenism-export-to-wealth` (pmoves/tokenism-wealth-export, approval-gated, dry-run-default) — both emit to `tokenism.export.result.v1`.
  - service_refs: tokenism-simulator, firefly, open-notebook, nats.
- **Code seam** `PMOVES-ToKenism-Multi/integrations/firefly/` — FireflyClient / DataTransformer / CalibrationEngine / settlement-executor + publisher, with .spec.ts. Latest: 79d5771 "token-gated HTTP trigger for sim → PMOVES-Wealth dry-run export (spec G1)".
- **DoX consumption** `PMOVES-DoX/backend/app/utils/integration_health.py` — checks Tokenism (+Wealth) as sibling integration ("Tokenism hosts economic simulation and PMOVES-Wealth integration", integration_health.py:171,241); DoX backend main.py:289 runs it at startup.
- **Superproject compose** `docker-compose.ui.yml` — tokenism-simulator (host :8103) + tokenism-ui; `TOKENISM_URL` default `http://pmoves-tokenism-simulator-1:8100` (container port).

## Live fleet state (2026-09-09, probed from elder-melchor over tailnet)

| Surface | Host | State | Evidence |
|---|---|---|---|
| Firefly III web/API | spark :8075 | **UP** | 302 → /login (live UI) |
| wealth-mcp | spark :8092 | **UP** (auth-gated) | /mcp → Unauthorized without Bearer |
| mcp-toolkit gateway | spark :8100 | UP, **degraded** | /healthz: status "degraded", "Integration health check failed: attempted relative import with no known parent package", 23 tools |
| **Tokenism simulator** | spark :8103 | **DOWN** | connection refused |
| fleet-sentinel | spark :8116/:8099 | **NOT DEPLOYED** | both closed |
| fleet-sentinel | elder-melchor :8116 | **NOT DEPLOYED** | closed |
| Fleet NATS | kvm4-2 :4222 | UP | INFO handshake, JetStream, auth |
| cipher shim | elder-melchor :8105 | UP | /health healthy (bootstrap agent) |

## Findings (ranked)

1. **Simulator down = the export loop is broken end-to-end.** Room binding `tokenism-export-to-wealth` targets the simulator; :8103 refused. G1 export (79d5771) cannot run while the simulator is down.
2. **Port identity confusion is systemic.** :8100 is the mcp-toolkit gateway (hirag/nats/tensorzero/supabase/cast tools), NOT the simulator — compose default `TOKENISM_URL=http://…:8100` (docker-compose.ui.yml:84) points at the wrong service on spark. Anyone debugging "tokenism down" via that URL sees a *different* service's health.
3. **mcp-toolkit gateway degraded** with a Python import-context bug ("relative import with no known parent package") — likely a script executed directly instead of `python -m` package context. Its error string exists in NEITHER superproject nor Tokenism-Multi pinned trees — spark-local deployment drift; needs spark-side fix (crush/kimi lane) or the mcp-toolkit repo.
4. **No overwatch visibility.** fleet-sentinel (PR #2934, merged) is deployed NOWHERE — not spark, not elder-melchor. The MOF-steward/overwatch role has no registry to watch. This is the structural gap behind findings 1–3 going unnoticed.
5. **Submodule pins stale.** ToKenism-Multi pin d17ea07 is 1 behind Hardened tip 04285b8 (UI theme). Wealth pin 5f11f8d (21 behind upstream at recon start → sync PR #57 closes it).
6. **DoX pin fresh** (78dc457 = dependabot bumps; 0 behind).

## Actions from this recon

- **This PR** (superproject): ToKenism-Multi submodule pin bump d17ea07 → 04285b8 (Hardened tip; picks up the Cataclysm armor dark theme for the simulator UI).
- **Filed for spark/crush lane** (not this lane): simulator restart on :8103, mcp-toolkit relative-import fix, fleet-sentinel deployment.
- **Wealth PRs:** #56 (fork readme/tri context) + #57 (upstream sync) — pre-steps, already open.
- **Structural (next in lane):** deploy fleet-sentinel on elder-melchor as the overwatch registry (make up-sentinel) — makes tri-state continuously visible instead of port-scans.
