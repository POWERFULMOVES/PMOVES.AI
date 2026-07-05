# Weekend Plan — 2026-05-01

## Two Lanes

---
### LANE 1 — SYNC (SPARK / 5090)

**Node**: SPARK (DGX Spark, ARM64, 128GB, GH_PAT, self-hosted runner)
**Goal**: Submodules cloned, branches verified, SPARK-claimable issues closed.

#### SPARK-Claimable Issues
| # | Title | Why SPARK | Status |
|---|-------|------------|--------|
| 1411 | bpm_encoder NATS publish gap + env.shared fix | Explicitly tagged [5090] | **CLOSED** — already implemented, just not closed |
| 1414 | rdna4 hostname normalization | Config fix, any node | **PR #1416** — ready to merge |

#### SPARK-Claimable PRs
| # | Branch | Status |
|---|--------|--------|
| 1415 | feature/launch-readiness-stage-0 | SPARK provenance pipeline — review & merge |
| 1416 | fix/rdna4-hostname-normalization | Ready — 5 files, 10 replacements, closes #1414 |
| 1408 | fix/meilisearch-env-var-mismatch | Ready — 2 lines, merge |
| 1409 | docs/cnc-circuit-breaker-architecture | Ready — companion to #1408, merge |

#### Not SPARK's Lane
| # | Title | Lane |
|---|-------|------|
| 1410 | Health Phase 4 + Wealth Phase 1+2 | z890 |

#### Submodule Sprint
- 45 registered, 2 cloned (Archon, BotZ-gateway), 43 gitlink-only
- 128GB handles full init
- Steps: init → checkout PMOVES.AI-Edition-Hardened → check behind → sync → document

#### Branch Hygiene
- Naming audit — flag non-convention branches
- Orphan sweep — >7 days, no PR, no CHIT trail

---
### LANE 2 — P7

**Goal**: Launch readiness progressing toward signoff.

#### PR #1415 Review
- SPARK provenance pipeline + space-agent NATS + A2UI Pretext
- Assess merge readiness

#### AGNOTE4482 Signoff — P7 Items
- [ ] P7/Discord/site language point at same frame
- [ ] P7 framed as room-aware stage manager (docs verified, needs Discord+site)
- [ ] Remaining: room-aware entry alignment, Agent Zero suit baseline

#### Pinokio Checks
- P7 SKILL.md files current?
- TAC tree phase completion?

---

## Parked (Separate Concerns)

| Topic | Status | When to Revisit |
|-------|--------|-----------------|
| ArcOns tutorial app | Not found — need clarification | When user provides direction |
| YouTube playlist | Frozen since 04-24, zero signal | Next curation batch |
| Collaboration constellation (GoMobii × CS × PMOVES) | Signal captured (memory x0igpMCXwI) | When user says discuss |
| Outreach package | Intent captured | When direction clarifies |
| Protections (enforce_admins, CHIT flip) | Branch protection active, gaps noted | After sync lane complete |

## Carried Forward

- CnC P7 Accord — gate shape defined, not implemented
- Circuit-breaker principle — promptinclude, carries every conversation
- Trace #0 — meilisearch pipeline (fix merged, docs merged)
