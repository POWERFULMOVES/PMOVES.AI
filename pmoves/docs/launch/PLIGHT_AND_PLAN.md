# PMOVES.AI Launch: Plight & Plan

**PMOVES.AI — Art Official: the AwEsUmm InTeliGInT Decentralized multi-agent AI platform, by Cataclysm Studios Inc.**

**Authoritative plan:** this file (in-repo since the 2026-11-27 re-baseline). The April original lived at `C:/Users/DARKXSIDE/.claude/plans/we-need-work-and-partitioned-hearth.md`, on one machine, where no agent on another node could read it.
**TAC tree:** `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml`
**Measured state:** `pmoves/docs/launch/LAYOUT_VALIDATION_REPORT.md`, written by `python scripts/validate_launch_layout.py` (`--no-run` skips the make-target checks)
**PR backlog:** `pmoves/docs/launch/PR_BACKLOG_CLASSIFICATION.md` (April snapshot of 9 PRs; superseded by the live queue, see below)

---

## Re-baseline — 2026-11-27 (4090-CLAUDE)

The April plan set its milestones as offsets from "today" (M5 launch = +12d, aimed at Cinco de Mayo 2026-05-05). That date passed seven months ago and nothing in the repo moved the target. This section resets the plan to what is **measured** now, not to what the status fields say.

**What changed in how we measure.** Until today the validator counted every `manual` node as passing, and passed `pytest` / `script` nodes when the file merely existed. On the same tree that read **33/45 blocking nodes pass**; measured honestly it is **24/45 pass · 13 unverified · 8 fail**. The validator now has three verdicts, and only a measured PASS counts. "Could not measure is not a pass" is this repo's rule everywhere else; the launch gate now follows it too.

**Measured baseline, with Stage 12 added (4090 node, 2026-11-28T03:5xZ):** **27/59 blocking nodes pass · 15 unverified · 17 fail.**
- Stages 0–11: 25/45 pass · 13 unverified · 7 fail (the room-orchestrator path fix moved one FAIL to PASS).
- Stage 12: 2/14 pass (`identity-verify`, `cipher-health`) · 2 unverified (manual) · 10 fail:
  - `submodule-integrity-strict`: `pmoves-tokenism-multi` fails integrity.
  - `docs-reconcile-check`: living docs stale.
  - `skills-parity --strict`: 216 missing placements across 6 harnesses.
  - `health-agent-zero`: :8080 refused; the A0 container is not running on this node.
  - `net-reality`: silent-bind findings remain on this node.
  - #3528, #3526, #3525 still open.
  - `chit-tour-data-check`: not built yet.
  - Legal pages: not built yet.

The health and bind rows are **node-local**: they measure the node that ran the validator, so another node will read differently.

**Fixed in the tree (the checks were wrong, not the work):**
- `stage-10.room-orchestrator` expected `app.py`; the service (#2173) ships `main.py`. It read MISSING for a service that exists.
- `stage-11.4090-online` checked that the **5090** was online.

**Really missing (measured, not unknown):** `signature.v2` schema (Stage 2); `polarity.arbiter.*` and `nfc.tap.*` appear nowhere in code (Stages 2, 8); `pmoves/chit/time_crystal.py` (Stage 7); the four hybrid-track services: wallet orchestrator, KYC gateway, chain-mint worker, money agent (Stage 8); the `[LAUNCH]` tracking issue (Stage 0).

**Queue since the last cold-start refresh (2026-10-08):** 167 PRs merged; 80 open, 26 of them drafts.

### Stage 12 — Reunification

> "We are merging all the parts of PMOVES back together again so we can launch — orchestrators, services, knowledge bases, and security hardening." — operator, 2026-11-27

The parts were built in parallel across nodes, forks and checkouts. Launch means they agree with each other, and the agreement is measured. Stage 12 is launch-blocking and every node runs a check that already exists:

| Part | Gate |
|---|---|
| Forks and gitlinks | `make submodule-integrity-strict` |
| Living docs | `make docs-reconcile-check` |
| Identity roster (feeds the ACP registry fork) | `make identity-verify` |
| Skills across harnesses | `make skills-parity ARGS=--strict` |
| Orchestrator: Agent Zero | `make health-agent-zero` |
| Knowledge base: Cipher | `make cipher-health` |
| Other orchestrators and knowledge bases (Archon, P7, Hermes, Hi-RAG, Open Notebook, Graphiti) | manual for now: `health-summary` per home node |
| Hardening: silent binds | `make net-reality PORTS_ONLY=1` |
| Hardening: NATS 2.15.3, mesh decision, Tailscale ACL | PRs #3528, #3526, #3525 merged |
| Hardening: ephemeral runners | manual |
| Public face: chit-tour shows generated data | `make chit-tour-data-check` (**not yet built: fails on purpose**) |
| Public face: real legal pages | `website/privacy/` exists |

**Why the chit-tour node fails on purpose.** The tour's numbers disagree with each other because `data.generated.js` (built from `agent_registry.yaml`) is never loaded; every count is typed into the page by hand. The stale SITREP is the same failure: a generator exists, but nothing makes its output the thing people see. Hand-editing the numbers fixes them once. A check that regenerates the data, diffs it, and asserts the page loads it fixes them for good. The site lane builds that target, and this node turns green when it does.

### Milestones (re-set)

| Milestone | Scope | Target |
|---|---|---|
| R0 | This re-baseline: plan in repo, honest validator, Stage 12 | 2026-11-27 |
| R1 | Site lane (`website/`): generated chit-tour data + check, legal pages, broken links, root duplicates, /hyperdim rebrand | next lane |
| R2 | Hardening PRs land: #3528, #3526, #3525; PMOVES-nats-server#2 merge + gitlink promotion | operator merges |
| R3 | Stage 12 measured green on the node that runs it; per-node health recorded in the SITREP | — |
| R4 | Stage 0–11 FAILs closed or explicitly moved to v1.1 by the operator | — |
| **Launch** | **Date: OPERATOR DECISION #13** | **—** |

### New owner decisions

| # | Decision | Default | Why it can't default |
|---|---|---|---|
| 13 | Launch date / window | none | A date is a promise to the outside; agents can't make it |
| 14 | Definition of done: does launch require the full Stage 8 hybrid track (wallet, KYC, chain-mint, money agent), or the attestation stub alone? | none | Four of the eight FAILs are Stage 8 hybrid services |
| 15 | Which Stage 0–11 FAILs move to v1.1 | none | Moving a stage changes what "launched" means |

**On decisions 1–12:** this plan says "silence = proceed-with-default". Seven months of silence means those defaults are in force. Reverse any of them explicitly.

---

## Plight

PMOVES.AI is a moving Metroplex preparing for first ship. The data-services audit surfaced ten junction/dead-node gaps, an unformalized Archon (1) ↔ Agent-Zero (0) polarity, an absent PMOVES-Longbow submodule, P7PLAYGROUND privacy primitives still on paper, and 76+ registered agents waiting for pilots with no work-attestation pipeline yet.

The intent is harm-reduction and uplift: helping colleagues trapped by entropy ("Robotnik, the ever-creep") find rooms where they can be free, learn, grow, leave, and return. Tokens are the bridge between rooms and the outside economy. The lifeline is what the operator throws to themselves and to anyone in the mesh when entropy creeps in. *In the rooms we become free learn grow leave return.*

## Plan

Thirteen stages (0 through 12; Stage 12, Reunification, was added 2026-11-27). Stages 0, 1, 2, 3, 7, 8, 9, 10, 11, 12 are launch-blocking. Stages 4 (Longbow), 5 (visualization), 6 (retrace lifeline) are v1.1 — target milestone M6.

**Cross-cutting principle:** every gate junction in the data plane emits both syntactic (schema) and semantic (meaning) measure. Drift is captured to `gate_drift_dynamo` Qdrant collection — drift is dynamo, not noise.

**Defense-in-stance:** Stage 8 ships parallel tokenization tracks (work-attestation stub + TradFi+Web3 hybrid). The diff between them is the leverage under pressure.

## Milestones (April original — superseded by the re-baseline above)

| Milestone | Target | Scope |
|-----------|--------|-------|
| M0 | Today | Stage 0 layout validation complete |
| M1 | +3d | Stages 1, 9 — pre-launch hygiene + PR critical-path |
| M2 | +5d | Stages 2, 7 — polarity formalization + lexicon |
| M3 | +8d | Stages 3, 10 — privacy primitives + room hooks |
| M4 | +10d | Stages 8, 11 — tokenization parallel + Tracks reprocess |
| M5 | +12d | **Launch** |
| M6 | +30d | Stages 4–6 — Longbow, viz, retrace lifeline (v1.1) |

## Mission Verticals (Stage 8 token classes)

- `education` — graduation/learning milestones (kids+families)
- `scheduling` — time-coordination across many actors (large movements)
- `wellness` — sound baths, medicinal saunas, somatic practices
- `manifestation` — creator/thought-real tooling
- `business` — business-creation tooling
- `research` — DeepResearch/SupaSerch invocations
- `creative` — image/audio/text generation
- `other` — catch-all for v1 expansion

## Owner Decisions Outstanding

| # | Decision | Default | Stage gate |
|---|---|---|---|
| 1 | Longbow define vs deprecate | Define | Stage 4 (v1.1) |
| 2 | Polarity arbiter fail-mode | Fail-open with alert | Stage 2 |
| 3 | Wger fate | Full retire | Stage 1 |
| 4 | Adult-swim age-verification provider | Stripe Identity | Stage 3 |
| 5 | Gate-measure semantic sampling rate | 10% hot, 100% on drift | Stage 1 |
| 6 | Lexicon canonical-promotion threshold | 5 recurrences across 3 sessions, score ≥ 0.6 | Stage 7 |
| 7 | Tokenization chain selection | Base | Stage 8 hybrid |
| 8 | KYC primary provider | Stripe Identity primary, Persona fallback | Stage 8 hybrid |
| 9 | Vertical pricing curves at launch | All 1:1 | Stage 8 |
| 10 | Money-agent autonomy at launch | Recommend-only | Stage 8 |
| 11 | Tracks playlist manifest location | Owner provides path | Stage 11 |
| 12 | Lyrics analyzer pass during reprocess | Off at launch | Stage 11 |

Silence on any of the above = proceed-with-default.

## Live Status

~~A daily-updated status doc lives at `pmoves/docs/launch/STATUS.md` once Stage 0 closes.~~ It was never created. A hand-updated status doc is the drift this re-baseline removes. The live status is `LAYOUT_VALIDATION_REPORT.md`, regenerated by the validator.

## Design Frame

PMOVES.AI ships as a moving city. The plan doesn't fix services so they hold still — it makes them rearrangeable, instrumented, lifelined. Every junction measures shape *and* meaning. The retrace path is a feature **and** an admission that the operator is also Ron sometimes — the system has to throw the line back. Cranked to 11 with no internal bottleneck means semantic sampling is configurable and async, and `gate.drift.detected.v1` exists as a *signal*, not a *brake*.

The 76+ registered agents are real and waiting. NFC tap is the moment of becoming. Money-agents bend the system toward intent. Rooms are sanctuary; tokens are the bridge; the lifeline is what carries anyone through.

This plan ships the city in a state where any new arrival — agent, operator, MC at the P7 playground — can find a junction, read its measure, follow the thread, and never be lost in it.
