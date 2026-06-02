# PMOVES.AI Launch: Plight & Plan

**Authoritative plan:** `C:/Users/DARKXSIDE/.claude/plans/we-need-work-and-partitioned-hearth.md`
**TAC tree:** `pmoves/configs/tac_trees/pmoves-launch-readiness.tac.yaml`
**PR backlog:** `pmoves/docs/launch/PR_BACKLOG_CLASSIFICATION.md`
**Layout validator:** `scripts/validate_launch_layout.py`

---

## Plight

PMOVES.AI is a moving Metroplex preparing for first ship. The data-services audit surfaced ten junction/dead-node gaps, an unformalized Archon (1) ↔ Agent-Zero (0) polarity, an absent PMOVES-Longbow submodule, P7PLAYGROUND privacy primitives still on paper, and 76+ registered agents waiting for pilots with no work-attestation pipeline yet.

The intent is harm-reduction and uplift: helping colleagues trapped by entropy ("Robotnik, the ever-creep") find rooms where they can be free, learn, grow, leave, and return. Tokens are the bridge between rooms and the outside economy. The lifeline is what the operator throws to themselves and to anyone in the mesh when entropy creeps in. *In the rooms we become free learn grow leave return.*

## Plan

Twelve stages (0 through 11). Stages 0, 1, 2, 3, 7, 8, 9, 10, 11 are launch-blocking. Stages 4 (Longbow), 5 (visualization), 6 (retrace lifeline) are v1.1 — target milestone M6.

**Cross-cutting principle:** every gate junction in the data plane emits both syntactic (schema) and semantic (meaning) measure. Drift is captured to `gate_drift_dynamo` Qdrant collection — drift is dynamo, not noise.

**Defense-in-stance:** Stage 8 ships parallel tokenization tracks (work-attestation stub + TradFi+Web3 hybrid). The diff between them is the leverage under pressure.

## Milestones

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

A daily-updated status doc lives at `pmoves/docs/launch/STATUS.md` once Stage 0 closes.

## Design Frame

PMOVES.AI ships as a moving city. The plan doesn't fix services so they hold still — it makes them rearrangeable, instrumented, lifelined. Every junction measures shape *and* meaning. The retrace path is a feature **and** an admission that the operator is also Ron sometimes — the system has to throw the line back. Cranked to 11 with no internal bottleneck means semantic sampling is configurable and async, and `gate.drift.detected.v1` exists as a *signal*, not a *brake*.

The 76+ registered agents are real and waiting. NFC tap is the moment of becoming. Money-agents bend the system toward intent. Rooms are sanctuary; tokens are the bridge; the lifeline is what carries anyone through.

This plan ships the city in a state where any new arrival — agent, operator, MC at the P7 playground — can find a junction, read its measure, follow the thread, and never be lost in it.
