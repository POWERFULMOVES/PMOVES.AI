# Evolution Fabric Wave 0 — SPARK Review

**Reviewer:** Crush-GLM52 (SPARK)
**Date:** 2026-08-04
**Branch:** `agent/evolution-fabric-rfc`
**Verdict:** ✅ **GO for Wave 1** (conditional — see blockers below)

---

## Scorecard

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| Reuse of existing PMOVES components | 0.25 | 0.95 | 0.2375 |
| Contract compatibility | 0.20 | 0.90 | 0.1800 |
| Security and memory separation | 0.15 | 0.95 | 0.1425 |
| SPARK operational feasibility | 0.15 | 0.80 | 0.1200 |
| AgentGym compatibility | 0.10 | 0.75 | 0.0750 |
| Human review/promotion safety | 0.10 | 0.95 | 0.0950 |
| Documentation clarity | 0.05 | 0.90 | 0.0450 |
| **Total** | **1.00** | | **0.895** |

**Threshold: 0.85 — PASS (0.895 > 0.85)**

---

## 1. Duplicate-service risks

**Verdict: NO DUPLICATES FOUND.**

The RFC explicitly rejects creating:
- A `spark-controller` (uses P7/Agent Zero instead)
- Separate `crush-bridge`/`hermes-bridge` products (extends existing runtimes)
- A duplicate AgentGym service (extends the existing RL coordinator)

All new `evolution.*` NATS subjects are additive facts, not replacement control subjects. The RFC reuses:
- `claw.task.assign.v1` for cross-node task delegation
- PMOVES-Crush bootstrap + Graphiti trail for provenance
- AgentGym-RL coordinator for training
- Archon for review/teacher role

**No hard-gate failure.**

---

## 2. NATS contract conflicts

**Verdict: NO CONFLICTS — 7 new additive subjects.**

Proposed new subjects (all `evolution.*` namespace):
- `evolution.task.created.v1`
- `evolution.attempt.started.v1`
- `evolution.attempt.completed.v1`
- `evolution.evaluation.completed.v1`
- `evolution.review.completed.v1`
- `evolution.candidate.proposed.v1`
- `evolution.candidate.promoted.v1`

**Verified:** No `evolution.*` subjects exist in `pmoves/contracts/topics.json` or `.claude/context/nats-subjects.md`. All 7 are genuinely new, additive, and use the canonical `.v1` suffix.

The subjects reuse existing surfaces (`claw.task.assign.v1`, `agentgym.train.*`, `geometry.*`) as runtime-native events, normalizing them into the `evolution.*` fact namespace only after acceptance. This is the correct pattern — facts are durable, runtime events are transient.

**No hard-gate failure.**

---

## 3. AgentGym storage compatibility

**Verdict: COMPATIBLE — but schema must be confirmed live before Wave 1.**

The RFC proposes referencing existing AgentGym trajectories and training runs. Verified the coordinator code:
- `coordinator/storage.py:61` — `create_trajectory()` exists
- `coordinator/storage.py:180` — `create_training_run()` exists
- `coordinator/storage.py:365` — `agentgym_events` table referenced
- `coordinator/training.py:77` — `create_training_run()` RPC call to Supabase

**Finding:** The actual Supabase table DDL is NOT in `pmoves/supabase/migrations/` — it's managed by the AgentGym-RL coordinator at runtime via RPC calls. The RFC's schema proposal (`EVOLUTION_FABRIC_SUPABASE_SCHEMA.md`) must be validated against the live table structure before Wave 1 implementation.

**Recommendation:** Wave 1 must start with a live schema dump from the running coordinator.

**No hard-gate failure** (schema confirmation is a Wave 1 prerequisite, not a Wave 0 blocker).

---

## 4. Hermes integration gaps

**Verdict: COVERED by existing TAC tree.**

`pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` has 36 references to NATS, bridge, MCP, and private-memory separation. The RFC correctly extends this existing plan rather than creating a parallel Hermes configuration.

Private-memory separation is preserved: the RFC states "Private user/domain memory is excluded from training by default" and treats it as a protected store.

**No hard-gate failure.**

---

## 5. Crush hook/export feasibility

**Verdict: FEASIBLE via existing hooks.**

Verified the following Crush hook/export surfaces exist:
- `.claude/hooks/post-tool-sign-trail.sh` — PostToolUse Graphiti trail signing
- `.claude/hooks/shift-crew-trail.sh` — NATS branch trail emit
- `.claude/hooks/a2ui-crew-trail.sh` — A2UI lane trail emit
- `pmoves/scripts/crush-pmoves` — bootstrap wrapper
- CRUSH.md — documents the trail signing flow + CHIT awareness

The RFC's "Crush attempt export" can use these existing hook surfaces to capture attempt metadata without creating a new Crush runtime.

**No hard-gate failure.**

---

## 6. SPARK sandbox + persistent inbox

**Verdict: OPERATIONALLY REALISTIC — 2 concerns.**

**What works:**
- `make -C pmoves nats-agent-inbox` target exists (Makefile:1138) — persistent inbox subscriber
- NATS broker running with 6 JetStream streams
- Pinokio path exists at `~/pinokio`
- `make -C pmoves crush-bootstrap` + `hermes doctor` paths documented

**Concerns:**
1. **Disk space:** 86GB free (91% used). Wave 1 training datasets + model checkpoints could fill this. Recommend setting up JuiceFS off-C storage (already merged #2337/#2341) before Wave 1 training begins.
2. **`nats-agent-inbox` target** creates a subscriber but does not create a durable JetStream stream for the inbox. Wave 1 should add an `EVOLUTION_INBOX` stream to the 6 existing streams.

**No hard-gate failure** (both are Wave 1 prerequisites, not blockers).

---

## 7. Experience Layer skin-manifest benchmark

**Verdict: SUFFICIENTLY BOUNDED.**

The first benchmark (Wave 6) adds a skin-manifest validator compatible with existing PMOVES UI/A2UI. It does NOT replace the Next.js/Supabase UI or the A2UI bridge — it's an additive validation contract. The scope is well-bounded: validate a manifest, emit a pass/fail, no UI changes.

**No hard-gate failure.**

---

## Hard-gate summary

| Gate | Status |
|---|---|
| No duplicate controller/service | ✅ PASS |
| No direct-main mutation path | ✅ PASS (human-reviewed PR required) |
| No private-memory training path | ✅ PASS (excluded by default) |
| Independent reviewer preserved | ✅ PASS (Archon as teacher, not self-review) |
| Reliable SPARK inbox confirmed | ⚠️ CONDITIONAL (stream needs creation in Wave 1) |
| Existing event subjects reused | ✅ PASS |

---

## Proposed Wave 1 lane owners

| Lane | Owner | Rationale |
|---|---|---|
| NATS schemas + persistence | SPARK (Crush) | Has the live NATS + Supabase + model-registry |
| AgentGym schema inspection | 5090 or B850 | Has the RL coordinator running |
| Hermes NATS bridge | SPARK | Has Hermes profile + crush integration |
| Crush attempt export | SPARK | Owns the hook surfaces |
| Archon review integration | B850 | Has Archon 0.6.0 running |

---

## Go/No-Go decision

**GO for Wave 1**, conditional on:
1. Live AgentGym schema dump before schema implementation
2. `EVOLUTION_INBOX` JetStream stream created on SPARK
3. JuiceFS off-C storage configured for training datasets
4. Human owner authorizes Wave 1 implementation start

---

## NATS/DB implementation order (recommended)

1. Create `EVOLUTION_INBOX` JetStream stream
2. Add `evolution.*` subjects to `pmoves/contracts/topics.json` with schemas
3. Dump live AgentGym table structure → validate schema proposal
4. Implement Crush attempt export hook → `evolution.attempt.started.v1` / `.completed.v1`
5. Wire model-fitness-bridge to consume `evolution.attempt.completed.v1`
6. Archon review gate → `evolution.review.completed.v1`

