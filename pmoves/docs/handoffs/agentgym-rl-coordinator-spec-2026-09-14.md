# AgentGym-RL Coordinator — Service Spec (2026-09-14)

> **Status:** dead code → specs land today; code + compose wiring is
> operator-only on the SPARK node.
> **Lane:** `wave-4-evo-spark-watch-list` (TTL 24h, filed 2026-09-14T20:42:32Z,
> expires 2026-09-15T20:42:32Z).
> **Source of truth:** `pmoves/services/evo-controller/agentgym_integration.py`
> on main. The integration file is the contract; this handoff is the
> docs surface.

## Why this exists

`pmoves/services/evo-controller/agentgym_integration.py` (on main, since
2026) declares the integration with an AgentGym-RL coordinator that
**does not exist in this repo**:

- The class `AgentGymIntegration` is mixed into the EvoSwarm controller.
- It calls `POST {AGENTGYM_COORDINATOR_URL}/agentgym/train/start`
  with a `training_request` body.
- The default URL is `http://agentgym-rl-coordinator:8114` — a
  compose-network DNS name that resolves to nothing today.
- It publishes `agentgym.train.started.v1` and `agentgym.train.completed.v1`
  events to the Agent Zero `/events/publish` endpoint.
- It assumes a return shape of `{training_run_id, environment, population_id, ...}`.

The result: the EvoSwarm controller is wired to call a service that
doesn't ship. Any time the integration's training trigger fires
(fitness plateau, new constellation, periodic, fitness degradation),
the HTTP POST fails and the controller logs a warning, but no RL
training actually happens. **The RL half of evo is dead code today.**

## Service contract (verbatim from the integration)

### HTTP API

```
POST {AGENTGYM_COORDINATOR_URL}/agentgym/train/start
Content-Type: application/json

{
  "environment": "pmoves-hirag",
  "base_model": "<AGENTGYM_BASE_MODEL, default Qwen/Qwen3-8B>",
  "population_id": "pop-{generation}",
  "training_config": {
    "algorithm": "ppo" | "grpo",
    "horizon": 5 | 10 | 15,
    "num_epochs": <int, default 25>,
    "batch_size": <int, default 32>,
    "learning_rate": <float, default 1e-6>,
    "kl_coef": <float, default 0.001>,
    "focus_namespace": "<optional>"
  },
  "geometry_config": {
    "cgp_fitness_weight": <float, default 0.2>,
    "retrieval_quality_weight": <float, default 0.3>,
    "task_success_weight": <float, default 0.4>,
    "efficiency_weight": <float, default 0.1>,
    "parameter_pack_id": "<optional>",
    "namespace": "<env_namespace or focus_namespace>"
  }
}
```

Response (success): `{training_run_id: str, environment: str, population_id: str, ...}`

Response (failure): HTTP 4xx/5xx, body irrelevant; controller logs the
status and continues.

### Port and DNS

- Default port: **8114** (the controller's `AGENTGYM_COORDINATOR_URL` default).
- Compose network DNS name: `agentgym-rl-coordinator` (the controller
  composes this name; it must resolve inside the `pmoves-net` network).
- Health endpoint contract: not declared in the integration file; a
  `/healthz` returning `{"status":"ok"}` is the conventional shape for
  the rest of the fleet — propose that as the contract.

### Event bus (NATS subjects, validated against `pmoves/docs/AGENTS/`)

| Subject | Publisher | Payload (minimal) |
|---------|-----------|-------------------|
| `agentgym.train.started.v1` | EvoSwarm controller (already wired) | `{training_run_id, environment, trigger_reason, population_id, algorithm, horizon, num_epochs, learning_rate, geometry_config: {…}, timestamp}` |
| `agentgym.train.completed.v1` | EvoSwarm controller (already wired) | `{training_run_id, trajectory_ids, model_id, population_id, fitness_metrics, epoch, generation, timestamp}` |

Both subjects are currently **declared but unbound** — the JetStream
stream `AGENTGYM` (per `pmoves/scripts/nats/init_streams.sh`) exists
with 0 messages, 0 consumers. The coordinator side has to subscribe
to these subjects; that's what makes the loop close.

### Environment contract

```
AGENTGYM_COORDINATOR_URL   default: http://agentgym-rl-coordinator:8114
AGENTGYM_ENABLE            default: true
AGENTGYM_BASE_MODEL        default: Qwen/Qwen3-8B
AGENTGYM_ENV_NAMESPACE     default: pmoves.consciousness
AGENTGYM_DEFAULT_ALGORITHM default: ppo
AGENTGYM_DEFAULT_HORIZON    default: 10
AGENTGYM_DEFAULT_EPOCHS     default: 25
AGENTGYM_DEFAULT_BATCH_SIZE default: 32
AGENTGYM_DEFAULT_LR         default: 1e-6
AGENTGYM_DEFAULT_KL_COEF    default: 0.001
AGENTGYM_TRIGGER_ON_PLATEAU         default: true
AGENTGYM_PLATEAU_WINDOW             default: 5
AGENTGYM_TRIGGER_ON_NEW_CONSTELLATION default: true
AGENTGYM_PERIODIC_TRAINING_INTERVAL   default: 100
AGENTGYM_TASK_SUCCESS_WEIGHT          default: 0.4
AGENTGYM_RETRIEVAL_QUALITY_WEIGHT     default: 0.3
AGENTGYM_CGP_FITNESS_WEIGHT           default: 0.2
AGENTGYM_EFFICIENCY_WEIGHT            default: 0.1
AGENTGYM_HORIZON_SCHEDULE             default: "5,10,15"
AGENTGYM_HORIZON_EPOCH_THRESHOLDS     default: "0,10,20"
```

All read by the controller (already shipped). The coordinator itself
needs the upstream AgentGym-RL contract (AgentGym's POST
`/agentgym/train/start` API, which lives in the upstream AgentGym
repo, not this one). Operator must source the AgentGym image +
the RL training env (pmoves-hirag per the integration) when bringing
up the coordinator.

## Placement: SPARK

The coordinator belongs on **SPARK**, not on the 5090 / 4090 / Z890
nodes:

- It is the training compute for the evo loop. Evo cycles are bursty
  (training fires on plateau / new constellation / periodic, not
  continuously). SPARK's GPU is the natural home for that bursty
  pattern.
- The 5090's enrichment DB `youtube_videos` carries the watch-list
  the SEAP school lane wants transcribed (the parallel lane, not
  this one). The coordinator sits next to whatever consumes the
  transcriptions — and the evo loop is the consumer.
- Putting it on SPARK means **the operator can swap the upstream
  AgentGym-RL image without rebooting any "production" node**. SPARK
  is already the lane's "experiment" host.

SPARK-side requirements (operator-side, not this PR):

1. New submodule `PMOVES-agentgym-rl-coordinator` under the fork —
   operator-only action; not in scope of this docs PR.
2. Compose wiring on SPARK's `pmoves/docker-compose.yml`:
   - `agentgym-rl-coordinator` service, port 8114, env contract above.
   - `pmoves-net` network, depends on `evo-controller` so the
     controller's `http://agentgym-rl-coordinator:8114` resolves.
3. NATS subscriber on `agentgym.train.started.v1` and
   `agentgym.train.completed.v1` — closes the loop the controller
   already opens.

## TAC tree (so the lane is discoverable)

A new TAC tree ships with this PR:
`pmoves/configs/tac_trees/agentgym-rl-coordinator.tac.yaml`. It
references this handoff as its primary source of truth.

## What this PR is NOT

- **Not the code.** The coordinator service body is operator-only;
  upstream AgentGym-RL contract lives outside this repo.
- **Not the compose wiring.** SPARK-side wiring is operator-side;
  the ratchet gate would block this PR from mainlining compose on
  5090 / 4090.
- **Not the fork registration.** A new submodule needs a fork
  registry entry; that's the Class-B issue I flagged in wave-3
  (4 PMOVES submodules already uninit). Land that wave first or
  include this one there.

## Operator follow-up (wave-5 candidate)

- File `PMOVES-agentgym-rl-coordinator` fork (POWERFULMOVES org) and
  register the submodule.
- Add a fork-registry entry: `sync: true, reason: "RL coordinator for
  evo loop; SPARK-only; AgentGym-RL upstream"`.
- Land the compose wiring on SPARK.
- Verify by running `make -C pmoves up-agentgym-rl-coordinator` on
  SPARK and observing the controller's existing training triggers
  stop failing (they'll fire on the first fitness plateau).
