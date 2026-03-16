# TAC_EVOSWARM
_Last updated: 2026-03-15_

## Mission

Manage population-based evolutionary optimization with CHIT attribution. The EvoSwarm Controller coordinates evolutionary cycles — initializing populations, evaluating fitness, selecting survivors, mutating candidates, and attributing results through the Geometry Bus.

## Current State

- **Port:** 8113
- **Team:** Evolution (agent-teams.yaml)
- **Dependencies:** TensorZero (3030), NATS (4222), Tokenism Simulator (8103), GPU Orchestrator
- **CHIT Integration:** Partial — swarm metadata on Geometry Bus

## Architecture

```
        EvoSwarm Controller (8113)
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
 Fitness    Selection   Mutation
  Eval      Operator    Engine
    │          │          │
    │          │          ▼
    │          │    TensorZero (LLM-guided mutation)
    │          │
    ▼          ▼
  geometry.swarm.meta.v1
  geometry.event.v1
         │
         ▼
  Tokenism Simulator (8103)
  → tokenism.simulation.result.v1
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `geometry.swarm.meta.v1` | Publish | Swarm population metadata |
| `geometry.event.v1` | Publish | Evolutionary lifecycle events |
| `tokenism.simulation.result.v1` | Subscribe | Attribution results from Tokenism |
| `model.registry.updated.v1` | Subscribe | Model catalog changes |

## Phases

1. **Initialize** — Seed population from model registry or random generation
2. **Evaluate** — Score fitness using LLM-based evaluation (TensorZero)
3. **Select** — Tournament/elitist selection of survivors
4. **Mutate** — LLM-guided mutation of selected candidates
5. **Attribute** — Publish swarm metadata to Geometry Bus for CHIT encoding
6. **Iterate** — Loop until convergence or generation limit

## Related Services

| Service | Role |
|---------|------|
| Tokenism Simulator (8103) | CGP encoding of evolutionary trajectories |
| Swarm Attribution | Shape attribution for CHIT geometry |
| GPU Orchestrator | Model loading for fitness evaluation |
| AgentGym RL | Training pipeline consuming evolution results |

## Production Readiness

| Check | Status |
|-------|--------|
| NATS integration | Active (geometry bus) |
| CHIT toggles | Partial (swarm meta, event) |
| Auth | Network isolation |
| Docker Compose | Profile: `gpu` |
| Observability | `/metrics` TBD |

## Verification

```bash
curl -s http://localhost:8113/healthz
nats sub "geometry.swarm.>" --count=1
```
