# ToKenism-Multi visibility verify — 2026-10-11

**Lane:** L3 of the operator-approved three-lane batch (CLAIM `THREE-LANE-CLAIM-20261011`).
**Operator intent (stated 2026-10-11):** "tokenism multi was meant pub" — the repo should be publicly visible.

## Measured

| Check | Result |
|---|---|
| `GET api.github.com/repos/POWERFULMOVES/ToKenism-Multi` (unauthenticated) | **404 Not Found** — private (or renamed/deleted) |
| `GET api.github.com/users/POWERFULMOVES` | 200 — org exists and is reachable, so the 404 is repo-specific, not org-level |
| `pmoves/config/fork_registry.json` | **No tokenism entry** — the fork registry carries no intent record for this repo either |
| Chit-tour static data (data.js) | References ToKenism Multi as a simulation-engine source in the tour's tokenomics section — a public tour citing a private repo readers cannot open |

## Interpretation

The tour's ToKenism lab (pillars-lab.js + data.js sources) points readers at a repo that returns 404 for the public. Either the repo is private (flip to public) or it was renamed (update tour links + registry). The fork-registry gap is its own reconcile item: per the 2026-09-20 submodule survey, fork_registry.json and fork-sync.yml disagree fleet-wide; this repo is currently in neither.

## Required action (org-admin only — agents unauthenticated cannot flip)

If the repo exists and should be public:

```bash
gh repo edit POWERFULMOVES/ToKenism-Multi --visibility public --accept-visibility-change-consequences
```

If renamed or deleted: confirm the canonical name, then update the chit-tour sources and this report.

## Post-flip verification (this lane, once flipped)

1. Re-run the repo API → expect `"private": false` and a real description.
2. Decide the fork_registry entry (sync posture per the gate-parity lane) and open that as a follow-up registry PR.
3. Spot-check the chit-tour ToKenism lab links resolve publicly.

**Status:** BLOCKED-ON-OPERATOR (org-admin action). Everything else in this lane is done — the measurement, the intent conflict record, and the post-flip checklist.
