# TODO — lane `validation-matches-shape`

Owner: B850-CLAUDE (Knuckles) · Delivery body · TTL 2026-09-08T15:57Z
Branch: `feat/validation-matches-shape`

## Thesis

Validation for a service must be based on **functionality and usage** — that is what
turns the light green, not a switch. And validation should **match shape**: a service
that stores is validated by writing and reading back; one that publishes by publishing
and consuming; one that authenticates by presenting a credential and being accepted.

## Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 0 | Todo doc + scaffolding commit | DONE |
| A | Archon compose diff (produce, do NOT apply) — attach archon to the tier carrying Supabase, root + overlay | TODO |
| A1 | Re-verify network-membership root cause (positive control included) | TODO |
| B | Wire the light to the function — Archon healthcheck parses `ready`, not just HTTP status | TODO |
| C | Shape-matched validation pattern doc + switch-vs-shape inventory of the 66 targets + ranked backlog | TODO |
| C1 | First tranche: prove the pattern on a small number of services | TODO |
| D | Provenance table (source URL/path, version/commit/date, what was taken) | TODO |
| E | Cipher ingest — VERIFY write path or report COULD-NOT-MEASURE | TODO |

## Constraints in force

- The compose files under `pmoves/` are READ-ONLY on this node. Diffs + runbook only.
- Never print/log/echo/commit a credential value. Names, lengths, shapes only.
- Do NOT mint/rotate/revoke/set any live credential. Do NOT restart production services.
- Tier environment files and the secrets manifests are zero-access, hook-blocked.
- Do NOT inspect container environment blocks. Network/healthcheck inspection is fine.
- Exit codes: 0 clean / 1 findings / 3 could-not-measure. Could-not-measure is NOT a pass.
- Every zero/empty result needs a positive control attached.

## Resume notes for a successor

(appended as work proceeds)
