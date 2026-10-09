# Release Notes — AgentGym-RL Coordinator Spec (2026-09-14)

**PR:** wave-4 spec · **Suit concern:** `pmoves/configs/tac_trees/` (§6.4)

## What changed

A new TAC tree ships to declare the AgentGym-RL Coordinator service
surface. The service body itself remains upstream (AgentGym-RL) and
not in this repo; what lands here is the **integration contract** the
EvoSwarm controller has been calling into a black hole since 2026:

- **TAC tree**: `pmoves/configs/tac_trees/agentgym-rl-coordinator.tac.yaml`
  — declares port `8114`, env contract, NATS subjects
  (`agentgym.train.started.v1`, `agentgym.train.completed.v1`), and
  the SPARK placement decision.
- **Spec handoff**: `pmoves/docs/handoffs/agentgym-rl-coordinator-spec-2026-09-14.md`
  — the full contract, verbatim from
  `pmoves/services/evo-controller/agentgym_integration.py`, with the
  placement rationale and operator follow-up.

## Why it matters

`pmoves/services/evo-controller/agentgym_integration.py` has been
wired to call `POST http://agentgym-rl-coordinator:8114/agentgym/train/start`
since 2026. The compose-network DNS name resolves to nothing in this
repo; the controller's HTTP POST fails every time the training
triggers fire (fitness plateau, new constellation, periodic,
fitness degradation). The result: **the RL half of EvoSwarm is dead
code today** — every trigger fires, every call fails, the controller
logs a warning, and no RL training actually happens.

This PR declares the missing service so the loop can be closed.

## What this does NOT do

- It does not ship the coordinator service body. The upstream
  AgentGym-RL contract lives outside this repo; the operator sources
  the image.
- It does not wire the compose stack. SPARK-side compose wiring is
  operator-side and not in scope of this docs PR. The ratchet would
  block landing compose on 5090 / 4090 anyway (it gates cross-node
  fleet wiring).
- It does not register the new submodule in the fork registry. That
  is the Class-B item flagged in wave-3 (4 PMOVES submodules
  uninit). Land that wave first or include this one there.
- It does not verify the integration end-to-end. The controller's
  trigger paths will fire on the first fitness plateau after SPARK
  brings up the coordinator; that is the verification surface.

## Operator follow-up

1. **File the submodule** `PMOVES-agentgym-rl-coordinator` under
   the POWERFULMOVES org and add a fork-registry entry
   (`sync: true, reason: "RL coordinator for evo loop; SPARK-only;
   AgentGym-RL upstream"`).
2. **Land the compose wiring on SPARK** — `agentgym-rl-coordinator`
   service, port 8114, `pmoves-net`, depends on `evo-controller`.
3. **Bring up** with `make -C pmoves up-agentgym-rl-coordinator` on
   SPARK.
4. **Verify**: observe the controller's existing training triggers
   stop failing — they fire on the first fitness plateau after SPARK
   brings up the coordinator.
