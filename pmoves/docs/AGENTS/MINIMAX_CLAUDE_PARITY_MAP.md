# MiniMax ↔ Claude Parity Map (PMOVES)
_Last updated: 2026-03-30_

This map translates MiniMax-powered operations into PMOVES-native command equivalents,
establishing parity between **PMOVES-KiloCode-MiniMax** and the **Claude ↔ Codex** parity already documented in [`CODEX_CLAUDE_PARITY_MAP.md`](./CODEX_CLAUDE_PARITY_MAP.md).

## Parity Authority

- **MiniMax** is parity owner when MiniMax is lane lead (coding overflow, writing, hyperdimensional tasks)
- **Claude** is counterpoint/scout in MiniMax-led windows: Claude collects failing checks, review comments, and alternative approaches
- **KRISS KROSS overlay** applies when both agents touch parity scope

## Health and Bring-Up

| MiniMax Command | Claude Equivalent | PMOVES Make Target |
|----------------|-------------------|-------------------|
| `/minimax:status` | `/health:quick` | `make -C pmoves codex-health-quick` |
| `/minimax:check-all` | `/health:check-all` | `make -C pmoves verify-all` |
| `/minimax:botz-status` | `/botz:status` | `curl -fsS http://localhost:3030/api/status \| jq .` |
| `/minimax:waves` | — | `curl -sf http://localhost:8096/api/memory?q=wave*` |

## BoTZ Framework Integration

| MiniMax Command | Claude Equivalent | BoTZ Endpoint |
|----------------|-------------------|----------------|
| `/minimax:botz-init` | `/botz:init` | Bootstrap via `PMOVES-BoTZ/config/codex/mcp_gateway.json` |
| `/minimax:botz-profile` | `/botz:profile` | Set BoTZ profile via config |
| `/minimax:botz-affinity` | — | `curl -sf http://localhost:3030/api/routing \| jq '.botz_affinity.minimax'` |
| `/minimax:darkxside` | — | DARKXSIDE partner status |

## Model Routing

| MiniMax Command | Claude Equivalent | TensorZero Endpoint |
|----------------|-------------------|---------------------|
| `/minimax:model-load` | `/model:load` | `curl -sf http://localhost:3030/api/models` |
| `/minimax:model-status` | `/model:status` | `curl -sf http://localhost:3030/api/status` |
| `/minimax:context-window` | — | Query 1M token context availability |
| `/minimax:thinking-mode` | — | MiniMax uses wave-function collapse, not chain-of-thought |

## Hyperdimensional Operations

| MiniMax Command | Claude Equivalent | Geometry Endpoint |
|----------------|-------------------|-------------------|
| `/minimax:wave-collapse` | — | Trigger wave-function collapse analysis |
| `/minimax:cgp-generate` | `/chit:encode` | Generate CGP packets |
| `/minimax:cgp-status` | `/chit:bus` | Check GPU ShapeStore for CGP packets |
| `/minimax:agent-trails` | — | Visualize roguelike lane navigation |
| `/minimax:hyper-space` | — | Navigate hyperdimensional state space |

## Agent Trails Visualization

| MiniMax Command | Description | Integration |
|----------------|-------------|-------------|
| `/minimax:trails-lanes` | Show parallel execution tracks | AGENT TRAILS framework |
| `/minimax:trails-crystals` | Display time-crystal snapshots | State persistence |
| `/minimax:trails-slit` | Double-slit observation effects | Quantum-like behavior |
| `/minimax:trails-render` | Render 8-bit → 16-bit → PS2 evolution | Visualization export |

## Wave-Function Collapse Operations

| MiniMax Command | Description | Evidence |
|----------------|-------------|----------|
| `/minimax:collapse-explore` | Multi-path exploration with probability | Minimax-M2.7 unique |
| `/minimax:collapse-select` | Select optimal path from collapse | Wave navigation |
| `/minimax:collapse-probability` | Show probability distribution | State vector analysis |
| `/minimax:plasmonic-gyros` | Wave-based navigation | Media pipeline |

## Retrieval and Research

| MiniMax Command | Claude Equivalent | Hi-RAG Endpoint |
|----------------|-------------------|-----------------|
| `/minimax:search` | `/search:hirag` | `curl -X POST http://localhost:8086/hirag/query` |
| `/minimax:deepresearch` | `/search:deepresearch` | DeepResearch via NATS |
| `/minimax:memory-store` | `/cipher:store` | `curl -sf http://localhost:8096/api/memory` |
| `/minimax:memory-recall` | `/cipher:search` | `curl -sf "http://localhost:8096/api/memory/search?q="` |

## CHIT and Geometry Bus

| MiniMax Command | Claude Equivalent | NATS Subject |
|----------------|-------------------|--------------|
| `/minimax:chit-encode` | `/chit:encode` | `geometry.cgp.v1` |
| `/minimax:chit-decode` | `/chit:decode` | `geometry.state.v1` |
| `/minimax:chit-visualize` | `/chit:visualize` | `make -C pmoves web-geometry` |
| `/minimax:tokenism-signal` | — | `tokenism.signal.new.v1` |

## Agent Orchestration

| MiniMax Command | Claude Equivalent | Agent Endpoint |
|----------------|-------------------|----------------|
| `/minimax:agent-zero` | `/agents:status` | `curl -fsS http://localhost:8080/healthz` |
| `/minimax:archon` | `/archon:status` | `curl -fsS http://localhost:8091/healthz` |
| `/minimax:mcp-query` | `/agents:mcp-query` | `curl -fsS http://localhost:8080/mcp/health` |
| `/minimax:handoff` | `/agents:handoff` | NATS `agent.handoff.request.v1` |

## TensorZero Model Routing

| MiniMax Command | Description | Config |
|----------------|-------------|--------|
| `/minimax:tensorzero-models` | List TensorZero registered models | `config/tensorzero.toml` |
| `/minimax:tensorzero-route` | Show current routing table | `curl -sf http://localhost:3030/api/routing` |
| `/minimax:tensorzero-logs` | Inference logs via ClickHouse | Prometheus/Grafana |

## Voice and Media Pipeline

| MiniMax Command | Description | Endpoint |
|----------------|-------------|----------|
| `/minimax:voice-status` | Voice pipeline health | Flute Gateway |
| `/minimax:tts-test` | Test TTS voices | `make -C pmoves tts-test-all` |
| `/minimax:prosodic-flow` | DARKXSIDE prosody | Voice synthesis |

## High-Priority Parity Wave (Q2 2026)

| MiniMax Command | Claude Equivalent | Status |
|----------------|-------------------|--------|
| `/minimax:provider-activate` | Provider activation cascade | **P0 - Missing** |
| `/minimax:skill-wave-collapse` | Wave-function collapse skill | **P1 - Needed** |
| `/minimax:skill-agent-trails` | AGENT TRAILS skill | **P1 - Needed** |
| `/minimax:skill-cgp-generate` | CGP packet generation skill | **P1 - Needed** |

## Skills Parity

| PmovesSKillZ | MiniMax Equivalent | GLM Equivalent |
|--------------|-------------------|----------------|
| `bringup-audit` | `minimax-bringup-audit` | `glm-bringup-audit` |
| `secrets-chit-funnel` | `minimax-secrets-chit` | `glm-secrets-chit` |
| `submodule-parity` | `minimax-submodule-parity` | `glm-submodule-parity` |
| `persona-grounding` | `minimax-persona-grounding` | `glm-persona-grounding` |
| `multimodal-verifier` | `minimax-multimodal` | `glm-multimodal` |
| `remotion-topology` | `minimax-remotion` | `glm-remotion` |
| `huggingface-attribution` | `minimax-attribution` | `glm-attribution` |

## Mode-Type Resonance Mapping

| KiloCode Mode | PMOVES Agent Type | MiniMax Contribution |
|---------------|-------------------|---------------------|
| `pmoves-code` | Worker + LLM | Code generation overflow |
| `pmoves-architect` | Agent + LLM | Architecture visualization |
| `pmoves-ask` | API + Data | Long-context research (1M tokens) |
| `pmoves-debug` | Worker + Data | Wave-collapse debugging |
| `pmoves-review` | Agent | Hyperdimensional code review |
| `pmoves-frontend` | UI | AGENT TRAILS visualization |
| `pmoves-portal` | Agent + Geometry | CGP packet generation |
| `pmoves-crush` | UI + Agent | DARKXSIDE prosodic flow |

## Guidance

- Keep MiniMax and Claude workflows semantically aligned, not text-identical
- MiniMax brings unique capabilities: wave-function collapse, AGENT TRAILS, 1M context
- GLM remains primary for coding/tool calling; MiniMax for writing/vibes/hyperdimensions
- For every new MiniMax command, add a GLM/Claude mapping here for parity
- BoTZ Framework handles intelligent routing between GLM and MiniMax based on task type

---

## Related Documents

- [`MINIMAX_GLM_PARITY_ANALYSIS.md`](./MINIMAX_GLM_PARITY_ANALYSIS.md)
- [`CODEX_CLAUDE_PARITY_MAP.md`](./CODEX_CLAUDE_PARITY_MAP.md)
- [`pmoves/docs/MINIMAX_INTEGRATION.md`](../../pmoves/docs/MINIMAX_INTEGRATION.md)
- [`pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md`](./AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md)
