---
name: kilocode-hyperdims
description: Execute hyperdimensional operations for PMOVES BoTZ tactical partner dynamics on the KiloCode GLM lane. Use when performing high-dimensional computations, tensor operations, or operating in the Transformers/Bumblebee energy framework.
keywords: [hyperdims, tensor, high-dimensional, BoTZ, tactical, spotlight, kilocode, glm]
version: 1.0.0
category: PMOVES/KiloCode
---

# KiloCode Hyperdimensional Operations

Execute hyperdimensional operations for PMOVES BoTZ tactical partner dynamics with KiloCode GLM support.

## Purpose

Perform high-dimensional tensor operations, embeddings, and BoTZ framework computations for PMOVES tactical partner dynamics. Leverages GLM-5-Turbo's 32K effective context for massive hyperdimensional state spaces. Route tensor operations through TensorZero `coding_glm` / `coding_kilocode`.

## Capabilities

- 🧮 High-dimensional vector operations
- 🎯 Tensor embedding generation
- ⚡ BoTZ gateway auto-routing
- 🔮 Spotlight/Hotrod energy dynamics
- 📊 TensorZero observability

## Integration Points

- **GLM-5-Turbo**: 32K effective context for hyperdims via Z.AI
- **TensorZero Functions**: `coding_glm`, `coding_kilocode`
- **BoTZ Gateway**: `PMOVES-BoTZ/` submodule
- **Hi-RAG v2**: GPU embeddings on `:8087`
- **NATS Subject**: `pmoves.hyperdims.ops.v1`

## Resonance Keys

Per `pmoves/docs/KILOCODE_GLM_INTEGRATION.md`:

```
blueprint-first        — GLM coding plan methodology
mode-driven            — KiloCode mode-based routing
hyperdimensional-ops   — high-dimensional tensor operations
time-crystal           — parallel state persistence
agent-trails           — roguelike lane navigation
```

## BoTZ Framework

```
┌────────────────────────────────────────────────────────────────┐
│              DARKXSIDE (Head/Orchestration)                     │
│         PMOVES-Agent-Zero (Orchestration)                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   PMOVES-ClawZ ──── Kinetic CLI (the Claw that transforms)    │
│                     Respects topology, knows when to roll out  │
│                                                                │
│       │                                                         │
│       ▼                                                         │
│   BoTZ Gateway ─── Auto-route to KiloCode GLM                 │
│                                                                │
│       │                                                         │
│       ▼                                                         │
│   PMOVES-Archon ─── Knowledge + Muscles                       │
│                                                                │
│   Model Routing:                                                │
│   BoTZ ◄──► GLM-5-Turbo ◄──► TensorZero                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Workflow

### 1. Initialize Hyperdimensional Space

```bash
# Create embedding space
curl -X POST http://localhost:3030/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm/embedding",
    "input": <context>,
    "dimensions": 1024
  }'
```

### 2. Execute BoTZ Routing

```bash
# Route through BoTZ
curl -X POST http://boTZ-gateway:8050/route \
  -H "Content-Type: application/json" \
  -d '{
    "task": <task_description>,
    "context": <hyperdim_vector>,
    "mode": "tactical"
  }'
```

### 3. TensorZero Observability

```bash
# Query ClickHouse for inference metrics
clickhouse-client --query \
  "SELECT * FROM tensorzero.inference WHERE model='glm' LIMIT 10"
```

## Tensor Shape Reference

| Operation | Shape | Dimensions |
|-----------|-------|------------|
| Embedding | [batch, seq, 1024] | 3D |
| Attention | [batch, heads, seq, seq] | 4D |
| State Space | [batch, 1024, 1024] | 3D |

## Example Usage

```
User: "Execute hyperdimensional search in context space"

Agent:
1. Loads context into GLM-5-Turbo
2. Generates 1024-dim embedding vector via coding_glm
3. Routes through BoTZ gateway
4. Executes tensor operations
5. Captures result with TensorZero observability
```

## Trigger Phrases

- "hyperdimensional operations"
- "BoTZ routing"
- "tensor operations"
- "high-dimensional search"
- "tactical partner dynamics"
- "kilocode hyperdims"
