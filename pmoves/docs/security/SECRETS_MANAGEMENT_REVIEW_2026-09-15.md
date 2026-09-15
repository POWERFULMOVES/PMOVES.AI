# Secrets management review — TS-key lifecycle, funnel map, and the OAuth mint fix

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** secrets-management review (operator-directed)
**Trigger:** "re ts key we have composio and tailscale cli and you are able to run secrets
funnels — please review secrets management and update your cipher."

## The pipeline, as it actually runs (measured this session)

```
operator values ──▶ GitHub Actions secrets (repo + prod scopes)
                        │  sync-secrets-local.yml (env map, ~120 labels)
                        ▼
                 secrets_local_hydrate.py ──▶ pmoves/data/chit/env.cgp.json  (canonical CHIT, 401 points)
                        │  chit-bundle artifact (per run)
                        ▼
        node pull: PMOVES_NODE=<n> make secrets-pull  ──▶ ~/.config/pmoves/chit/env.cgp.json (bundle, 108 points)
                        │  secrets-funnel-sync-from-bundle
                        ▼
        env.shared + env.tier-* (node materialization)  ──▶ compose interpolation ──▶ containers
                        ▲
        reverse path: make chit-export (env.shared → CHIT; guarded against
        un-exported bundle-delivered secrets) — the sanctioned input direction
        for values a node legitimately originates.
```

Guards that worked this week: the export refusal (un-exported bundle secrets), the
E2B `e2b_` prefix shape check, `secret_shape.inspect_value` charset withholding, the
funnel's alias resolution (`TAILSCALE_APIKEY` ↔ `TAILSCALE_API_KEY`).

## The Tailscale key: what actually happened

1. The vault's `TAILSCALE_API_KEY` (60 chars, `tskey-api-…`) was delivered FRESH to
   this node at 09:42 today — the pipeline is healthy end-to-end.
2. The value **401s against the API**: revoked upstream, shape-valid downstream.
   The funnel validates shape, not liveness — the exact failure class as the E2B
   `e2b_`/42-char delivery defect. Nothing in the chain could notice.
3. The OAuth client credentials (#3054: `TAILSCALE_OAUTH_CLIENT_ID/SECRET`) were
   plumbed into the sync workflow's env — and **consumed by nothing**. No mint
   step existed anywhere in the repo.

## Findings

| # | Finding | Severity | Disposition |
|---|---|---|---|
| F1 | Static TS key revoked-but-shape-valid; funnel cannot detect liveness | P2 ops | structural: any long-lived static key has this failure mode |
| F2 | OAuth creds routed (#3054) but never consumed | P2 | **fixed this lane**: mint-on-sync |
| F3 | Label drift `TAILSCALE_APIKEY` vs `TAILSCALE_API_KEY` across manifest/aliases/vault | P3 | aliases cover it; single-name consolidation is a hygiene PR |
| F4 | CHIT parser shape: points[] envelope means naive label greps see "4 labels" — tooling must parse `points[].label` (bit me twice today) | P3 | documented here + in cipher |
| F5 | Composio key: funnel-registered and delivered, no consumer yet — healthy opt-in state | info | none |

## The fix (this lane)

- `pmoves/scripts/ts_oauth_mint.sh` — mints an API access token from the OAuth client
  (official contract: POST `/api/v2/oauth/token`, form body, `Authorization: Bearer`;
  https://tailscale.com/kb/1215/oauth-clients, accessed 2026-09-15). Prints the token;
  callers mask.
- `sync-secrets-local.yml` — before hydrate: if the OAuth client is present, mint and
  **override** `TAILSCALE_API_KEY` with the fresh token; warning-with-fallback (never
  hard-fail the whole sync on a vendor hiccup). Long-lived static keys become the
  fallback, not the primary — every sync delivers a freshly minted token.

After this lands: dispatch the sync, `secrets-pull` + `secrets-funnel-sync-from-bundle`
on nodes, and the API probe should go green without any operator key-handling.

## Notes for the fleet

- The tailscale CLI on a node speaks for the NODE (tailscaled), not the API — it cannot
  mint API tokens; the OAuth client is the only programmatic mint path. This is why the
  mint lives in the sync workflow, where the client credentials are available.
- Composio remains the external-app action surface; nothing in this lane required it.
- Cipher updated with the full map + failure classes (see memory `crush-spark`).
