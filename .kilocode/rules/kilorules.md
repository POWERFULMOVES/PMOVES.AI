# KiloCode Rules for PMOVES.AI

## Context Sources

Use the `.claude` folder as primary reference:
- `.claude/README.md` — context loading guide
- `.claude/CLAUDE.md` — full architecture overview, service catalog, development patterns
- `.claude/context/` — detailed documentation (services, NATS subjects, MCP API, testing)
- `.claude/commands/` — skill definitions for CLI operations

## Model Backend Support

PMOVES.AI supports multiple model backends through the **BoTZ Framework**:

### MiniMax (Native Cloud)
- **MiniMax-M2.7:** 1M token context, fast inference
- **MiniMax-M2.1:** 100K token context, efficient
- **Origin:** Transformers/Hotrod/Spotlight inspiration (Big Hero 6 partnership model)
- **Documentation:** `pmoves/docs/MINIMAX_INTEGRATION.md`

### HuggingFace Local (GPU)
- **Fine-tuned models** via Ollama or native HuggingFace
- **GPU acceleration** on 5090/4090 nodes
- **Configuration:** `OLLAMA_BASE_URL=http://localhost:11434`

### TensorZero (Router)
- Centralized model routing to all backends
- ClickHouse observability for all inference
- Config: `pmoves/config/tensorzero/`

### BoTZ Framework Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DARKXSIDE (Head/Orchestration)                       │
│                    PMOVES-Agent-Zero-MiniMax (Orchestration)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │  PMOVES-ClawZ  │  ← Kinetic, autonomous CLI (the Claw that transforms) │
│   │  (Senses)      │    Respects topology, knows when to roll out          │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                       │
│   │     BoTZ        │  ← Gateways (Auto-route to EVO SWARM)                 │
│   │   Framework     │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                       │
│   │ PMOVES-Archon  │  ← Knowledge + Muscles                                 │
│   │   (Muscles)    │                                                       │
│   └─────────────────┘                                                       │
│                                                                             │
│   Model Routing:                                                            │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│   │   BoTZ     │◄──►│   MiniMax   │◄──►│  TensorZero │                   │
│   │  Gateway   │    │   (Fast)    │    │  (Router)   │                   │
│   └─────────────┘    └─────────────┘    └─────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Component Roles:**
- **DARKXSIDE** — Head/orchestration, strategic planning
- **PMOVES-ClawZ** — Kinetic CLI (the Claw), autonomous sensing, transformation triggers
- **PMOVES-Archon** — Knowledge base + execution muscles
- **BoTZ Gateway** — Auto-route to EVO SWARM
- **MiniMax** — Fast tactical partner inference
- **TensorZero** — Model routing with observability

## Hi-RAG Indexing for Cipher

Important context documents are indexed by Hi-RAG v2 for Cipher access:
- `pmoves/docs/MINIMAX_INTEGRATION.md` — MiniMax model configuration + BoTZ framework
- `pmoves/docs/AGENT_TRAILS.md` — Roguelike agent visualization framework
- `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` — Agent type system
- `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md` — Integration architecture

Query via Cipher: `POST http://localhost:8105/api/memory/search?q=...`

## Agent Taxonomy

PMOVES.AI uses a structured agent classification system:
- **Registry:** `pmoves/config/agent_registry.yaml` — canonical definitions (91 agents per latest validation)
- **Taxonomy:** `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` — 4 classes, 7 types, evolution paths
- **Signatures:** `pmoves/config/agent_signatures.yaml` — agent identity and capability signatures

## Mode-Type Mapping

KiloCode modes map to PMOVES service tiers and agent types. See `.kilocodemodes` at repo root for the 11 configured modes:

| Mode | Agent Types | Service Tiers |
|------|------------|---------------|
| `pmoves-code` | Worker + LLM | 3-4 |
| `pmoves-architect` | Agent + LLM | 6 + 3 |
| `pmoves-ask` | API + Data | 1-2 |
| `pmoves-debug` | Worker + Data | 4 + 1 |
| `pmoves-review` | Agent | 6 |
| `pmoves-frontend` | UI | 7 |
| `pmoves-portal` | Agent + Geometry | 6 + L2.5 |
| `pmoves-crush` | UI + Agent | 7 + 6 |
| `pmoves-glm` | Worker + LLM | 3-4 |
| `pmoves-cocreate` | Agent + Creative | 6 + L2.5 |
| `pmoves-minimax` | Agent + Fast Inference | 6 + 3 |

## Integration Plan

Full integration architecture: `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`

## AGENT TRAILS Theme

AGENT TRAILS is a roguelike visualization framework (Transformers meets Bumblebee):
- **CLI as Claw:** Terminal transforms like a Transformer
- **Lanes:** Parallel execution tracks with signal switching
- **Time Crystals:** Context snapshots for rewind/shift
- **Double Slit:** Quantum-like observation affecting behavior
- **8-bit → 16-bit → PS2:** Visual evolution generations
- **Hotrod/Spotlight energy:** BoTZ tactical partner dynamics

Full theme documentation: `pmoves/docs/AGENT_TRAILS.md`

## MiniMax Native Model Support

PMOVES.AI supports MiniMax as a native model backend for KiloCode operations.

### Model Configuration

| Model | Context Window | Provider |
|-------|---------------|----------|
| MiniMax-M2.7 | 1M tokens | MiniMax Global |
| MiniMax-M2.1 | 100K tokens | MiniMax Global/CN |

### MiniMax Integration Points

- **Agent Signature:** `pmoves/config/agent_signatures.yaml` — includes `minimax` with `dimensional` voice and `minimax-ghost` alter
- **Documentation:** `pmoves/docs/MINIMAX_INTEGRATION.md` — full integration guide
- **AGENT TRAILS:** `pmoves/docs/AGENT_TRAILS.md` — hyperdimensional navigation concept
- **Hi-RAG Indexing:** MiniMax docs indexed by Hi-RAG v2 for Cipher access
- **TensorZero:** Configure via `tensorzero.config.toml` with `provider = "minimax"`

### Key Resonances

- `native-model` — MiniMax as primary model backend
- `hyperdimensional-ops` — wave-function collapse operations
- `double-slit-weird` — quantum-inspired pathfinding
- `time-crystal` — parallel state persistence
- `agent-trails` — roguelike lane navigation
