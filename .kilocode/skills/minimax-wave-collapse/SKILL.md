---
name: minimax-wave-collapse
description: Execute wave-function collapse operations for hyperdimensional state space navigation in PMOVES. This skill should be used when performing quantum-inspired pathfinding, state collapse operations, or wave-function navigation.
keywords: [wave-collapse, hyperdimensional, quantum, state-space, collapse-ops]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Wave Collapse

Execute wave-function collapse operations for hyperdimensional state space navigation with MiniMax native support.

## Purpose

Perform wave-function collapse operations on hyperdimensional state spaces for PMOVES agent navigation. Leverages MiniMax's native model capabilities for fast tactical inference on quantum-inspired pathfinding.

## Capabilities

- 🌊 Execute wave-function collapse on state vectors
- 🎯 Collapse superpositions to concrete states
- 🧭 Navigate hyperdimensional state spaces
- ⚡ Fast collapse via MiniMax inference
- 🔮 Probabilistic path selection

## Integration Points

- **MiniMax Model**: M2.7 (1M context) or M2.1 (100K context)
- **TensorZero**: Routes collapse ops through `localhost:3030`
- **BoTZ Gateway**: `PMOVES-BoTZ/` submodule
- **Agent Trails**: `pmoves/docs/AGENT_TRAILS.md`
- **NATS Subject**: `pmoves.hyperdims.collapse.v1`

## Resonance Key

Per `pmoves/docs/MINIMAX_INTEGRATION.md`:

```
Key: hyperdimensional-ops
Description: wave-function collapse operations
```

## Workflow

### 1. Define State Superposition

```yaml
# State superposition
superposition:
  dimension: 1024
  states:
    - weight: 0.4
      vector: <embeddings>
    - weight: 0.35
      vector: <embeddings>
    - weight: 0.25
      vector: <embeddings>
```

### 2. Execute Collapse

```bash
# Via MiniMax inference
curl -X POST http://localhost:3030/v1/collapse \
  -H "Content-Type: application/json" \
  -d '{
    "superposition": <state_vector>,
    "temperature": 0.7,
    "context": <agent_context>
  }'
```

### 3. Extract Collapsed State

```json
{
  "collapsed_state": <concrete_vector>,
  "probability": 0.42,
  "entropy": 1.23
}
```

## Double Slit Dynamics

Per `pmoves/docs/AGENT_TRAILS.md`:

- **Observation Effect**: Measurement collapses the wave function
- **Interference Patterns**: Parallel execution tracks
- **Time Crystals**: Context snapshots for rewind/shift

## Example Usage

```
User: "Navigate agent to next best action using wave collapse"

Agent:
1. Loads agent context (position, goals, constraints)
2. Generates superposition of possible actions
3. Executes collapse via MiniMax
4. Extracts collapsed action vector
5. Validates against constraints
6. Returns executable action
```

## Trigger Phrases

- "wave function collapse"
- "execute collapse"
- "hyperdimensional navigation"
- "quantum pathfinding"
- "collapse state vector"
