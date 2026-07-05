# New User Onboarding: Next Steps

> Perspective: New user wanting to get PMOVES.AI running correctly
> Date: 2026-05-13
> Based on: 8 source documents + verified prior context

---

## 1. Executive Summary

PMOVES.AI is an ambitious distributed AI platform built on a Metal-Organic Framework (MOF) architectural metaphor with ~50 compose services, 71 agent types, and a five-layer stack spanning structure, information, transport, optimization, and economics. The documentation is extensive and philosophically rich, but a new user will hit two unfixed Makefile bugs before anything works. The system is "mostly shipped" per the roadmap (W1-W5 done, W6 partial) but has critical blockers: the bring-up path is broken, Agent Zero is 502 commits behind upstream, cross-session memory has a 3-layer gap, and ~100 unauthenticated NATS references represent a P0 security hole. The highest-leverage action is fixing the two Makefile bugs to unblock `make first-run`, followed by reclaiming 81.7 GB of Docker dust and addressing the NATS authentication gap.

---

## 2. Current System State

### What Works
| Component | Status | Evidence |
-----------|--------|----------|
| GitHub PAT authentication | Verified | GH_PAT_PMOVES: admin+push+pull on POWERFULMOVES/PMOVES.AI |
| Secrets funnel | Passing | `make secrets-funnel`: 0 errors, 16 warnings |
| Environment tier files | Present | All env.tier-* files exist on remote host (dated May 12) |
| CHIT passphrase | Configured | CHIT_PASSPHRASE=dev-local-sidecar-override |
| Signoff checklist | 36/42 pass | AGNOTE4482_SIGNOFF_CHECKLIST.md: 1 fail, 5 warnings |
| bpm_encoder + ToKenism | Shipped | W6-P2, 574-line implementation, tests green |
| Persona selector + voice binding | Shipped | W6-P3, 19 tests passing |
| TTS mesh routing | Shipped | W1, verified 10/14 Flute engines |
| Room catalog + dashboard | Shipped | W2, PRs #1136-1143 merged |
| Discord publisher | Shipped | W3, container running, MCP+REST validated |
| CHIT integration wave | Shipped | Extract Worker, FFmpeg-Whisper, embedding standardization |

### What's Broken
| Component | Status | Impact |
-----------|--------|--------|
| **Makefile check-tools** (line 265-266) | Bug: trailing `;` after `esac` | Bash syntax error blocks `make first-run` |
| **bootstrap_db.sh** (line 87) | Bug: `ALTER USER supabase_admin` | Fails on supabase/postgres:17.6.1.108 (reserved role) |
| Cipher Memory Layer 2-3 | `/api/memory` routes don't exist | Cross-session context persistence broken |
| A2A agent-to-agent | Partially mounted, disabled by default | Cannot verify at runtime |
| NATS heartbeat/presence | Phase D, not yet live | No fleet capability announcement |
| Agent Zero upstream sync | 502 commits behind (pinned March 7) | Missing v1.2+v1.3 features |

### What's Missing
| Gap | Priority | Source |
|-----|----------|--------|
| ~100 unauthenticated NATS references (`nats://nats:4222` without `@`) | P0 | Roadmap W1-W5 |
| 29 CodeQL alerts (2 critical SSRF in Hi-RAG gateway) | P0 | README.md |
| signing-card.v1.schema.json | P1 | AGNOTE4482.md (blocked by damage-control policy) |
| Automated CVE intake | P1 | Signoff checklist §6 |
| Profile-governed suit routing (Agent Zero UI defaults to OpenAI) | P1 | Signoff checklist §4 |
| Discord/site/docs language alignment | P1 | Signoff checklist §7 (explicit FAIL) |
| §1.4 Discord channel descriptions + site updates | P1 | Signoff checklist §1 |
| Operator SSH fingerprint capture | P2 | AGNOTE4482.md |
| Prometheus scrape config wger target | P2 | AGNOTE4482.md |
| 21 files in NATS auth secondary batch | P2 | AGNOTE4482.md |

---

## 3. Documentation Quality Assessment

### Strengths
- **Architectural depth**: AGNOTE4482.md provides a rigorous MOF physics homology mapping — nothing like it exists elsewhere
- **Signoff discipline**: The checklist ledger with multi-agent signoff is a strong accountability mechanism
- **SITREP pattern**: Cold-start orientation file is excellent practice for distributed teams
- **Tiered context map**: CLAUDE.md's "you want X → load Y" table is practical and concise

### Problems

**P1: No Linear Getting-Started Path**
README.md says `make first-run` — that's broken. The actual working path (run steps individually, bypassing the two bugs) is documented nowhere. A new user must discover the bugs by hitting them.

*Source: README.md §Quick Start vs. Known Context (Makefile bugs)*

**P2: Doc Scatter / Circular References**
A new user is told to read 4 files "always" (CLAUDE.md → LIVING_DOCS_INDEX.md → BOOTSTRAP.md → AGENTS.md → SITREP.md), each of which points to 3-5 more files. There is no "read these 2 files and you can start" path. The SITREP itself says "this file is pointers, not content."

*Source: CLAUDE.md §Read first, SITREP §Orientation*

**P3: AGNOTE4482.md is Not an Onboarding Document**
At ~200 pages of MOF physics, Dirichlet distributions, and acoustic impedance matching metaphors, AGNOTE4482.md is a design thesis, not a runbook. Yet it's positioned as "the gateway" document. A new user needs a 2-page "System Overview + How to Start" before being exposed to the full architecture.

*Source: AGNOTE4482.md (full content), CLAUDE.md tiered context map*

**P4: Version Confusion**
Multiple docs say "Agent Zero v1.3" but the gap report clarifies this is upstream-only — PMOVES is pinned to a March 7 pre-v1.2 commit. A new user checking `agent-zero --version` will not see v1.3.

*Source: AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md*

**P5: Stale References**
- SITREP references `LIVING_DOCS_INDEX.md` and `.claude/BOOTSTRAP.md` as mandatory reads — neither was in the 8 docs requested for this review
- Roadmap references open PRs #1135-1138 dated 2026-03-27 — these may be stale or merged by now (May 13)
- Pinokio launcher section in CLAUDE.md references `D:\pinokio\` — Windows-specific path irrelevant to Linux/Docker deployment

*Source: SITREP, Roadmap W1-W5, CLAUDE.md §Pinokio launcher*

**P6: Contradictions**
- README says `make first-run` orchestrates full onboarding; SITREP says run individual health checks (`docker ps`, `make health-quick`, `git status`). These are different entry points with no reconciliation.
- Signoff checklist says §9 (branch hygiene) fully passed, but roadmap notes `feature/launch-readiness-stage-0` violates `feat/` naming convention.

*Source: README.md, SITREP, Signoff checklist §9, Roadmap*

---

## 4. Proposed Next Steps

### P0 — Unblock the System (Do These First)

**Step 1: Fix Makefile check-tools bug**
- File: `Makefile`, line 265-266
- Action: Remove trailing `;` after `esac` in the `check-tools` target
- Verification: `make check-tools` completes without bash error
- Informed by: Known context (prior bug discovery)

**Step 2: Fix bootstrap_db.sh ALTER USER bug**
- File: `pmoves/scripts/bootstrap_db.sh` (or equivalent path), line 87
- Action: Replace `ALTER USER supabase_admin` with the correct Supabase-local role name or skip the ALTER entirely for the Supabase Docker image
- Verification: `make bootstrap-data` completes successfully
- Informed by: Known context (prior bug discovery)

**Step 3: Verify `make first-run` end-to-end**
- Action: After Steps 1-2, run `make first-run` on remote host and document any remaining failures
- If it passes: this becomes the canonical new-user path
- If it fails: document each failure with fix
- Informed by: README.md §Quick Start

### P1 — Stabilize and Secure

**Step 4: Reclaim Docker disk space**
- Action: `docker system prune -a --volumes` (with appropriate safety checks) or targeted cleanup of the 81.7 GB reclaimable dust
- Verification: `docker system df` shows significant reduction
- Informed by: Known context

**Step 5: Address NATS unauthenticated references (P0 security gap)**
- Action: Grep for `nats://(nats|localhost):4222` excluding lines with `@`, add credentials to all ~100 references
- Verification: `make naming-drift-strict` or custom grep passes with 0 hits
- Informed by: Roadmap W1-W5 §Known Gaps

**Step 6: Fix Cipher Memory Layer 2-3 gap**
- Action: Implement `/api/memory` CRUD routes in `pmoves-cipher-mcp/` submodule (the Pmoves-cipher submodule per SITREP)
- This unblocks cross-session context persistence for all agents
- Verification: Layer 2 MCP client can successfully call `/api/memory` endpoints
- Informed by: SITREP §Cipher Memory 3-layer gap

**Step 7: Create a 2-page "New User Quick Start" document**
- Action: Write `docs/QUICKSTART.md` containing: prerequisites, `make first-run`, what to expect, common failure modes (and fixes for the two bugs once fixed), health check commands, and where to go next
- This is the single highest-leverage documentation improvement
- Informed by: Documentation assessment §P1-P3

**Step 8: Plan Agent Zero v1.3 sync lane**
- Action: Open dedicated sync lane per gap report Option 2 — do NOT fast-forward. Preserve PMOVES hardening overlays, then re-apply on top of v1.3
- Verification: Submodule at v1.3 with all PMOVES overlays intact, tests passing
- Informed by: AGNOTE4482_AGENT_ZERO_V1_3_GAP_REPORT.md §Recommended Path

### P2 — Complete Signoff and Production Readiness

**Step 9: Resolve signoff §7 FAIL (Discord/site/docs alignment)**
- Action: Update Discord channel descriptions and site docs to share the same framing language
- Verification: Re-run signoff checklist §7
- Informed by: Signoff checklist §7

**Step 10: Complete §1.4 Discord/site external updates**
- Action: Same work as Step 9 — these are the same blocker affecting two checklist sections
- Informed by: Signoff checklist §1

**Step 11: Address 2 critical CodeQL SSRF alerts**
- Action: Add URL allowlisting to Hi-RAG gateway services per README.md triage
- Verification: CodeQL scan shows 0 critical alerts
- Informed by: README.md §Known Gaps

**Step 12: Implement signing-card.v1.schema.json**
- Action: Unblock the damage-control policy on `pmoves/contracts/schemas/`
- Verification: Schema file exists and passes validation
- Informed by: AGNOTE4482.md §Deferred Critical Gaps

**Step 13: Audit and close stale open PRs**
- Action: Review PRs #1135-1138 (dated March 27), merge/rebase/close as appropriate
- Verification: `gh pr list --state open` shows no stale PRs
- Informed by: Roadmap W1-W5 §Open PRs

---

## 5. Open Questions

These are things the documentation does NOT answer that a new user would need:

1. **What are the actual hardware minimums?** Docs mention 4090/5090/GB10 Blackwell but never state "you need at least X GB VRAM and Y GB RAM to run the core stack without GPU services."

2. **Which of the ~50 compose services are required vs. optional?** A new user doesn't know which services must run for a minimal viable system vs. which need GPU or are lower priority.

3. **What does `make first-run` actually do step-by-step?** It "orchestrates the full onboarding sequence" but there's no breakdown of what that sequence is, how long it takes, or what it produces.

4. **How do you run PMOVES.AI without the full GPU fleet?** The Island mode (standalone NATS sidecar) is mentioned but never documented as a setup path. Can a laptop user run anything useful?

5. **What is the current branch a new user should be on?** SITREP says check `git branch` but doesn't say which branch is canonical. The signoff was done on `feature/launch-readiness-stage-0` which violates naming conventions.

6. **How do you verify the system is healthy after bring-up?** SITREP lists individual commands (`docker ps`, `make health-quick`, `git status`) but there's no single health check that says "the system is ready for work."

7. **What happens when a make target fails?** No error recovery documentation. The two known bugs were discovered by hitting them — there's no troubleshooting guide.

8. **Is `make secrets-funnel` required before `make first-run`?** The ordering of bootstrap steps is unclear. README shows `make bootstrap` → `make up` → `make bootstrap-data` but SITREP shows a different sequence.

9. **What credentials does a new user actually need to provide?** `make bootstrap` "captures credentials" but which ones? GitHub PAT? Supabase access token? API keys for LLM providers? The list is never enumerated.

10. **How do the 6 agent types map to actual execution?** SITREP defines delivery-agent, control-agent, memory-agent, researcher, test-runner, pr-trimmer — but a new user doesn't know which agent they ARE or how to invoke a specific type.

---

*Report generated by Agent Zero Deep Research from 8 source documents + verified prior context.*