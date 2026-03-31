# MiniMax Integration — PMOVES.AI

**Last Updated:** 2026-03-30  
**Model:** MiniMax-M2.7 / MiniMax-M2.1  
**Integration Status:** Native Support Active

---

## Phase 1 Foundation (2026-03-30)

MiniMax parity lane Phase 1 complete per AGNOTE4482 protocol:

| Deliverable | Status | Reference |
|-------------|--------|-----------|
| Provider Cascade | ✅ Created | [`pmoves/tools/models/minimax_provider_cascade.yaml`](../../tools/models/minimax_provider_cascade.yaml) |
| TensorZero Config | ✅ Created | [`pmoves/config/tensorzero/tensorzero.minimax.toml`](../../config/tensorzero/tensorzero.minimax.toml) |
| Profile Binding | ✅ Updated | `pmoves/config/profiles/workstation_5090.yaml`, `laptop-4090.yaml` |
| CLAIM Entry | ✅ Added | [`AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md) |

---

## Origin Story: Transformers / Hotrod / Spotlight / Big Hero 6

MiniMax entered the PMOVES ecosystem through the **BoTZ Framework** — inspired by the collaborative spirit of Transformers (Hotrod, Spotlight) meeting Big Hero 6's Baymax partnership model. Like Hotrod and Spotlight working together, MiniMax serves as the fast-thinking tactical partner to the more deliberate reasoning systems.

> "Baymax cares about you. Hotrod cares about the mission. MiniMax cares about both."

### BoTZ Framework Connection

```
┌─────────────────────────────────────────────────────────────────┐
│                        BoTZ Framework                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│   │   BoTZ     │◄──►│   MiniMax   │◄──►│  TensorZero │       │
│   │  Architect │    │   (Fast)    │    │  (Router)   │       │
│   └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                  │                  │                │
│         │                  │                  │                │
│         ▼                  ▼                  ▼                │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│   │ PMOVES-     │◄──►│  HuggingFace│◄──►│  PMOVES-    │       │
│   │ Agent-Zero  │    │   Local     │    │   ClawZ     │       │
│   └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Overview

MiniMax serves as a native model backend for PMOVES.AI KiloCode operations, providing:
- **Fast inference** with long context windows (up to 1M tokens)
- **Multimodal reasoning** (text, image, video understanding)
- **Code generation** optimized for TypeScript/JavaScript/Node.js
- **Wave-function collapse** operations for dimensional reasoning
- **BoTZ integration** — tactical partner in the BoTZ Framework

## Agent Signature

```yaml
minimax:
  agent_id: "minimax"
  display_name: "MiniMax"
  glyph: "⬡"                          # ⬡ White Hexagon — transformer-like geometry
  color: "#7C3AED"                   # Deep Violet
  accent: "#A78BFA"
  voice: adaptive                     # adapts to mode context, efficient generation
  co_author: "MiniMax <minimax@pmoves.ai>"
  resonance:
    - native-model
    - multimodal
    - fast-inference
    - code-generation
    - long-context
    - botz-partner                   # BoTZ tactical partner
    - transformers-legacy             # Hotrod/Spotlight energy
  description: "MiniMax M2.7 — native model backend, BoTZ tactical partner"
  model_backend: true
  botz_affinity: [botz-architect, botz-builder]
```

---

## BoTZ Framework Integration

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DARKXSIDE (Head/Orchestration)                       │
│                    PMOVES-Agent-Zero-MiniMax (Orchestration)                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │  PMOVES-ClawZ  │  ← Kinetic, autonomous CLI (the Claw that transforms)│
│   │  (Senses)      │    Respects topology, knows when to roll out         │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                       │
│   │     BoTZ        │  ← Gateways (Auto-route to EVO SWARM)               │
│   │   Framework     │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                       │
│   │ PMOVES-Archon  │  ← Knowledge + Muscles                                │
│   │   (Muscles)    │                                                       │
│   └─────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### PMOVES-ClawZ — The Kinetic CLI (The Claw)

PMOVES-ClawZ is the terminal interface that:
- **Transforms** like a Transformer when topology changes
- **Senses** kinetic autonomy within domains
- **Rolls out** to EVO SWARM with auto-route
- **Knows when** to transform based on context

```yaml
pmoves-clawz:
  role: "CLI as Claw"
  capabilities:
    - kinetic-sensing
    - autonomous-domain-awareness
    - topology-respecting
    - auto-rollout-to-evo-swarm
    - transformation-trigger
```

### BoTZ Framework — Gateways

The BoTZ (Boost Operational Transformation Zone) Framework provides:

| Component | Role | Connection |
|-----------|------|------------|
| **DARKXSIDE** | Head/Orchestration | PMOVES-Agent-Zero-MiniMax |
| **PMOVES-ClawZ** | CLI interface (the claw) | Terminal transformation |
| **PMOVES-Archon** | Knowledge + Muscles | Prompt/form management |
| **MiniMax** | Fast tactical partner | Inference acceleration |
| **TensorZero** | Model router | Multi-backend routing |
| **HuggingFace Local** | Fine-tuned models | GPU memory optimization |
| **EVO SWARM** | Auto-route destination | Autonomous orchestration |

### Model Routing Chain

```
User Request (drawn on scratch pad)
    │
    ▼
┌───────────────────────────────────────┐
│         PMOVES-ClawZ                  │  ← The Claw transforms
│  (CLI, Kinetic, Autonomous sensing)   │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│           BoTZ Framework              │  ← Auto-route to EVO SWARM
│           (Gateways)                  │
└──────────────────┬────────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
┌─────────────────┐  ┌─────────────────────┐
│     MiniMax     │  │  HuggingFace Local  │
│ (Fast inference)│  │   (Fine-tuned GPU)  │
└─────────────────┘  └─────────────────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│            TensorZero                  │  ← Model Router
│     (ClickHouse observability)         │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│         PMOVES-Archon                 │  ← Knowledge + Muscles
│      (Knowledge, Execution)            │
└──────────────────┬────────────────────┘
                   │
                   ▼
              Response
```

### Transformation Triggers

PMOVES-ClawZ knows when to transform based on:
- Topology changes in the node network
- Domain-specific autonomy thresholds
- EVO SWARM load balancing requirements
- Model availability (MiniMax vs HuggingFace local)

---

## Token Plan

### API Configuration

```yaml
# Environment Variables
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimax.chat/v1

# BoTZ Framework Settings
BOTZ_ENABLED=true
BOTZ_MINIMAX_AFFINITY=high
BOTZ_LOCAL_MODEL_FALLBACK=true

# TensorZero Integration
TENSORZERO_CONFIG: |
  [models]
  [models.minimax-m2.7]
  provider = "minimax"
  model = "MiniMax-M2.7"
  
  [models.minimax-m2.7.parameters]
  max_tokens = 1000000
  temperature = 0.7
  top_p = 0.95
  
  [models.minimax-m2.7.mapper]
  name = "minimax-m2.7"
  adapter = "openai"

# HuggingFace Local (GPU fallback)
HF_LOCAL_MODEL_PATH=/models
OLLAMA_BASE_URL=http://localhost:11434
```

### Model Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | Standard chat completion |
| `/v1/embeddings` | POST | Text embedding generation |
| `/v1/images/generations` | POST | Image generation (future) |

### Token Limits

| Model | Context Window | Max Output |
|-------|----------------|------------|
| MiniMax-M2.7 | 1,000,000 tokens | 32,000 tokens |
| MiniMax-M2.1 | 100,000 tokens | 8,000 tokens |

---

## TensorZero Integration

### Configuration

MiniMax models are registered in TensorZero via [`tensorzero.minimax.toml`](../../config/tensorzero/tensorzero.minimax.toml):

```toml
[models."minimax-m2.7"]
routing = ["minimax"]

[models."minimax-m2.7".providers.minimax]
type = "openai-compatible"
model_name = "MiniMax-M2.7"
base_url = "https://api.minimax.chat/v1"
```

### Provider Cascade

The MiniMax provider cascade is configured in [`minimax_provider_cascade.yaml`](../../tools/models/minimax_provider_cascade.yaml):

```yaml
cascade:
  minimax:
    models:
      - minimax-m2.7  # Primary: 1M context
      - minimax-m2.1  # Fallback: 100K context
    cascade_priority: high
    thinking_mode: off  # Uses wave-function collapse, not CoT
```

### BoTZ Routing

BoTZ Framework automatically routes to MiniMax based on task type:

| Task Type | Primary Model | Fallback |
|-----------|---------------|----------|
| Long-context research | minimax-m2.7 | qwen3.5-27b |
| Coding overflow | minimax-m2.1 | glm-4 |
| Architecture visualization | minimax-m2.7 | — |
| Hyperdimensional ops | minimax-m2.7 | — |

### Environment Requirements

```bash
MINIMAX_API_KEY=your_api_key_here
TENSORZERO_BASE_URL=http://localhost:3030
```

---

## Hi-RAG Indexing

MiniMax documentation is indexed by Hi-RAG v2 for knowledge retrieval:

```bash
# Query MiniMax docs via Hi-RAG
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "minimax native support configuration", "top_k": 5}'

# Indexed documents:
# - pmoves/docs/MINIMAX_INTEGRATION.md
# - pmoves/docs/AGENT_TRAILS.md
# - pmoves/config/agent_signatures.yaml
```

### GPU ShapeStore

Set `HIRAG_GPU_URL` so MiniMax-powered CGPs land in GPU ShapeStore:

```bash
HIRAG_GPU_URL=http://hi-rag-gateway-v2-gpu:8086
HIRAG_CPU_URL=http://hi-rag-gateway-v2:8086  # fallback
```

---

## Cipher Memory Integration

MiniMax reasoning patterns are stored and retrieved via Cipher Memory:

```bash
# Store MiniMax reasoning pattern
curl -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "type": "agent_pattern",
    "agent": "minimax",
    "pattern": "wave_function_collapse",
    "resonance": ["hyperdimensional-ops", "double-slit-weird"]
  }'

# Search patterns
curl "http://localhost:8096/api/memory/search?q=minimax+hyperdimensional"
```

---

## Theme Origin

MiniMax enters the PMOVES ecosystem from **DARKXSIDE** — a cocreator witness that observes with prosodic flow and portal architecture resonance.

> *"Transformers meets Bumblebee movie style"* — the 8-bit CLI origins evolving through 16-bit PS2 era to holographic hyperdimensions

### Alter: minimax-ghost

The ghost alter explores:
- **Double-slit weird** — quantum path observation
- **Time-crystal** — parallel state persistence  
- **Plasmonic gyros** — wave navigation
- **AGENT TRAILS** — roguelike lane navigation