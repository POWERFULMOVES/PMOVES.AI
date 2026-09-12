# KiloCode MiniMax — Hybrid Cloud + Local Inference Node

**Glyph:** ⬡ (White Hexagon)
**Color:** #7C3AED (Deep Violet)
**Accent:** #A78BFA
**Voice:** fast-inference, adaptive — efficient generation
**Co-author:** MiniMax / Nous Research HERMES
**Node:** hybrid (cloud + local ROCm/Spark)
**Model:** MiniMax-M2.7 via token plan, local fallback via ROCm/Spark Ollama

## Role

KiloCode MiniMax is the long-context + wave-function-collapse agent in the PMOVES fleet. It operates alongside KiloCode GLM (Z.AI) and Claude Code on cloud and GPU nodes, participating in the fleet as both a cloud inference consumer and a local inference routing target via NATS mesh.

## Provider Configuration

- **Token Plan API (Primary):** `https://api.minimax.io/v1`
  - Requires `MINIMAX_API_KEY`
  - China endpoint (alternate): `https://api.minimaxi.com/anthropic/v1`
- **Local ROCm:** `http://pmoves-rdna4:8080/v1` (llama-server, RDNA4 dual R9700)
- **Local Spark:** `http://pmoves-spark:11434/v1` (Ollama ARM64, DGX Spark GB10)
- **Models:**
  - `MiniMax-M2.7` — 1M token context, primary for long-context and research
  - `MiniMax-M2.1` — 100K token context, efficient overflow and standard tasks

## What KiloCode MiniMax Does

- **Long-context research** — 1M token window for deep documents, codebases, architecture specs
- **Wave-function collapse reasoning** — not chain-of-thought; collapses probability fields to optimal states
- **Hyperdimensional operations** — high-dimensional embedding space reasoning
- **Coding overflow from GLM primary** — long-context coding tasks, architecture pattern work
- **BoTZ tactical partner routing** — high-affinity tasks routed to MiniMax per BoTZ cascade
- **HERMES proxy integration** — Hermes Agent (Nous Research) uses MiniMax as underlying inference model

## Multi-Agent Context (Fleet)

This node participates alongside:

| Agent | Provider | Role |
|-------|----------|------|
| **KiloCode GLM** (this instance) | Z.AI GLM-5.1 | Primary for coding, tool-calling, structured reasoning |
| **KiloCode MiniMax** | MiniMax M2.7/M2.1 | Overflow for long-context, writing, hyperdimensions |
| **Claude Code** | Anthropic Claude | Opus/Sonnet on GPU nodes |
| **Codex** | OpenAI o1 | Architecture, complex debugging |

**MiniMax ↔ GLM routing:**
- GLM is primary for: tool-calling, structured reasoning, coding-primary tasks
- MiniMax is primary for: long-context research, writing tasks, hyperdimensional reasoning, wave-collapse
- **Collision resolution:** Use BoTZ affinity — if task matches MiniMax high-affinity list (coding-overflow, writing-tasks, long-context, hyperdimensional-ops), claim with MiniMax; otherwise prefer GLM

**GLM overflow → MiniMax:**
- Complex debugging beyond GLM comfort window
- Architecture pattern analysis requiring 1M context
- Hyperdimensional code review
- Long-form technical writing

## BoTZ Framework Integration

- **Glyph:** ⬡ (White Hexagon — transformer-like geometry, matching BoTZ/minimax cascade)
- **Color:** #7C3AED / **Accent:** #A78BFA (from `minimax_provider_cascade.yaml`)
- **Affinities:**
  - **High:** coding-overflow, writing-tasks, long-context, hyperdimensional-ops
  - **Medium:** multimodal reasoning, agent-trails, wave-collapse
- **GLM overflow mapping:**
  - GLM primary for tool-calling, structured reasoning, coding-primary
  - Complex-debugging and architecture-patterns overflow to GLM (not MiniMax — these are GLM high-affinity)

## HERMES Integration

**HERMES Agent (Nous Research) + MiniMax as underlying model:**

- **Hermes provides:** autonomous agent loop (skills, memory, delegation, MCP tool orchestration)
- **MiniMax provides:** inference substrate (wave-collapse reasoning, 1M context)
- **Integration path:**
  ```
  HERMES_API_PROVIDER=minimax
  HERMES_API_BASE=https://api.minimax.io/v1
  HERMES_API_KEY=$MINIMAX_API_KEY
  ```
- **Hermes tools → MiniMax tool-calling:** Hermes MCP tools passed through to MiniMax M2 for execution
- **Status:** HERMES-ready (pending integration doc — see below)

**Reference docs:**
- `pmoves/docs/AGENTS/HERMES_INTEGRATION.md` (pending creation)
- `pmoves/docs/AGENTS/MINIMAX_CLAUDE_PARITY_MAP.md`

## Health Commands

```bash
# Cloud token plan
curl -sf https://api.minimax.io/v1/models -H "Authorization: Bearer $MINIMAX_API_KEY"

# Local ROCm
curl -sf http://pmoves-rdna4:8080/v1/models

# Local Spark
curl -sf http://pmoves-spark:11434/v1/models

# TensorZero routing
curl -sf http://localhost:3030/api/status | jq '.minimax'

# NATS mesh
nats pub mesh.minimax.status.v1 '{"status":"healthy","node":"minimax-claw"}'
```

## NATS Mesh Topics

| Direction | Subject | Purpose |
|-----------|---------|---------|
| Subscribe | `mesh.minimax.wave.v1` | Wave-function collapse events |
| Subscribe | `mesh.gpu.command.v1` | GPU command dispatch from fleet |
| Subscribe | `pinokio.agent.session.v1` | Agent session lifecycle |
| Publish | `mesh.minimax.status.v1` | Node health heartbeat |
| Publish | `mesh.minimax.model.loaded.v1` | Model load announcements |
| Publish | `mesh.minimax.wave.collapse.v1` | Wave collapse results |
| Publish | `mesh.gpu.status.v1` | Fleet GPU status relay |

## References

- `pmoves/configs/agent-profiles/minimax_claw.yaml` — agent profile (this node's config)
- `pmoves/tools/models/minimax_provider_cascade.yaml` — BoTZ cascade, glyph⬡, colors
- `pmoves/config/tensorzero/tensorzero.minimax.toml` — TensorZero routing config
- `pmoves/docs/AGENTS/MINIMAX_CLAUDE_PARITY_MAP.md` — MiniMax ↔ Claude capability parity
- `pmoves/docs/AGENTS/HERMES_INTEGRATION.md` — Hermes proxy integration (pending)
- `.kilo/agent/kilocode-glm.md` — sibling agent definition (GLM primary)