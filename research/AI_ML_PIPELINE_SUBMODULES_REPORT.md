# PMOVES.AI AI/ML Pipeline Submodules — Deep Research Report

> **Generated:** 2026-04-17 | **Researcher:** Agent Zero Deep Research (GLM-5)  
> **Scope:** 9 AI/ML pipeline submodules — submodule state, in-tree integration, Docker/NATS/TensorZero/TAC analysis  
> **Classification:** Internal — PMOVES.AI Engineering

---

## Executive Summary

Of the 9 AI/ML pipeline submodules under investigation, **none have initialized content locally** (all submodule directories are empty — not cloned). However, the in-tree codebase reveals a rich integration tapestry:

| Category | Submodules | In-Tree Services | TAC Trees | Docker Compose | NATS Subjects |
|----------|-----------|-----------------|-----------|----------------|---------------|
| Production-Integrated | AgentGym-RL, Deep-Serch, HiRAG | 5 services | 3 trees | 3 compose files | 12+ subjects |
| Dev-Integrated | Creator | 1 compose file | Via Creator report | 1 compose file | 0 defined |
| Pre-Stage (Planned) | Crush, Autoresearch | 0 | 1 tree (autoresearch) | 0 | 3 planned |
| Minimal Integration | AgentGym, llama-throughput-lab, Hyperdimensions | 0 | 0 | 0 | 0 |

**Critical Finding:** The AgentGym-RL + HiRAG v2 + Deep-Serch triad forms the operational core of the AI/ML pipeline. Crush and Autoresearch represent the next integration frontier but remain at Pre-Stage with no containerized deployment path.

---

## 1. PMOVES-Creator

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-Creator/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-Creator.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned (0 files) |
| **Category** | Media Generation |

### What It Is

Hardened fork of ComfyUI v0.3.68 with 685+ files and 57 diffusion model architecture classes. Three workflow families:

- **WAN Animate 2.2** — Video generation
- **Qwen Image Edit+** — Image editing
- **VibeVoice/RVC** — TTS + voice cloning

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | `pmoves/docker-compose.comfyui.yml` — profile `creator`, uses `runpod/comfyui:latest` image, GPU reservation via `nvidia/capabilities: [compute,utility]`, port 8188 |
| **NATS Subjects** | None defined in current codebase (marked as `(future)` in modular-architecture.md) |
| **TensorZero** | No direct integration; connects to TensorZero, MinIO, NATS, n8n per prior research |
| **TAC Tree** | Separate Creator report exists at `research/PMOVES-Creator_Deep_Research_Report.md` |
| **Agent Registry** | Listed under `creator` domain tag in submodule skill registry |
| **Smoke Tests** | `make smoke-creator-pipeline` tests render-webhook → comfy-watcher → MinIO → NATS flow |
| **Volume** | `comfyui-data` persistent volume at `/workspace` |

### Integration Gap

The docker-compose.comfyui.yml uses the upstream `runpod/comfyui:latest` image rather than a PMOVES-hardened build. The hardened fork (PMOVES-Creator) would need its own Dockerfile to replace this. Current compose is labeled `# optional and intended for local/dev convenience`.

---

## 2. PMOVES-AgentGym

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-AgentGym/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-AgentGym.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Legacy Vendor Path** | `pmoves/vendor/agentgym/` (also empty) |
| **Category** | Agent Training |

### What It Is

Fork of THUDM/AgentGym — an agent training framework providing diverse real-world environment scenarios for evaluating and training LLM agents. This is the *base framework* (not the RL variant).

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | None — no dedicated compose file |
| **NATS Subjects** | None |
| **TensorZero** | None |
| **TAC Tree** | None dedicated; referenced in training-pipeline.tac.yaml indirectly |
| **Agent Registry** | Not registered as standalone agent |
| **Config Files** | `pmoves/configs/agentgym/field-runner-4090.yaml` — field runner config for 4090 GPU |

### Relationship to AgentGym-RL

AgentGym is the upstream base framework. AgentGym-RL (submodule #3) extends it with reinforcement learning algorithms (PPO, ScalingInter-RL). The vendor mount `pmoves/vendor/agentgym-rl/` contains the RL code, while `pmoves/vendor/agentgym/` would contain the base environments. Both are currently empty locally.

### Integration Gap

Minimal integration — exists primarily as a dependency for AgentGym-RL. The `field-runner-4090.yaml` config suggests planned GPU-based evaluation but no containerized service exists yet.

---

## 3. Pmoves-AgentGym-RL

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `Pmoves-AgentGym-RL/` |
| **Repository** | `https://github.com/POWERFULMOVES/Pmoves-AgentGym-RL.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Legacy Vendor Path** | `pmoves/vendor/agentgym-rl/` (also empty) |
| **Category** | Reinforcement Learning Training |

### What It Is

Fork extending THUDM/AgentGym with reinforcement learning. Implements multi-turn interactive decision-making with 27 task environments, ScalingInter-RL algorithm for progressive interaction scaling, and PPO training. Published paper: [arXiv:2509.08755](https://arxiv.org/abs/2509.08755). Dataset: [AgentGym-RL-Data-ID on HuggingFace](https://huggingface.co/datasets/AgentGym/AgentGym-RL-Data-ID).

### In-Tree Integration — MOST INTEGRATED AI/ML SUBMODULE

#### Docker Compose: `pmoves/docker-compose.agentgym.yml`

Two services with profile `agentgym`:

| Service | Port | Image | Resources |
|---------|------|-------|-----------|
| `agentgym-rl-coordinator` | 8114 | `ghcr.io/powerfulmoves/agentgym-rl-coordinator:latest` | 4 CPU / 8G RAM |
| `agentgym-env-pmoves` | 36000 | `ghcr.io/powerfulmoves/agentgym-env-pmoves:latest` | 2 CPU / 4G RAM |

#### Training Configuration

| Parameter | Default | Notes |
|-----------|---------|-------|
| Base Model | `Qwen2.5-7B-Instruct` | Configurable via `AGENTGYM_BASE_MODEL` |
| Algorithm | PPO | `AGENTGYM_DEFAULT_ALGORITHM` |
| Horizon | 10 turns | `AGENTGYM_DEFAULT_HORIZON` |
| Epochs | 25 | `AGENTGYM_DEFAULT_EPOCHS` |
| Batch Size | 32 | `AGENTGYM_DEFAULT_BATCH_SIZE` |
| Learning Rate | $1 \times 10^{-6}$ | `AGENTGYM_DEFAULT_LR` |
| KL Coefficient | 0.001 | `AGENTGYM_DEFAULT_KL_COEF` |

#### Reward Function (4-component weighted)

| Component | Weight | Description |
|-----------|--------|-------------|
| Task Success | 0.4 | Did the agent complete the task? |
| Retrieval Quality | 0.3 | Quality of HiRAG retrieval results |
| CGP Fitness | 0.2 | Consciousness Geometry Packet fitness |
| Efficiency | 0.1 | Resource efficiency (turns, tokens) |

#### In-Tree Service Code: `pmoves/services/agentgym-rl-coordinator/`

```
app.py               — FastAPI service, NATS subscriber
coordinator/         — Core modules:
  ├── trajectory_accumulator.py
  ├── ppo_training_orchestrator.py
  └── huggingface_publisher.py
Dockerfile
requirements.txt
```

**NATS Subscriptions (from app.py lifespan):**
- `geometry.event.v1` — Accumulate trajectory data from Geometry Bus
- `tokenism.geometry.event.v1` — Tokenism geometry events
- `hf.model.downloaded.v1` — HuggingFace model download tracking
- `agentgym.train.completed.v1` — Auto-publish completed training runs

**NATS Publications:**
- `training.model.published.v1` — When model published to HuggingFace
- Benchmark pipeline events (via training.pipeline.*)

#### PMOVES-HiRAG Environment: `agentgym-env-pmoves`

A custom AgentGym-RL environment that uses HiRAG v2 for knowledge retrieval during RL training:

| Config | Value |
|--------|-------|
| Task Generator Mode | `constellation` (constellation/random/curriculum) |
| Difficulty Distribution | medium:0.5, easy:0.3, hard:0.2 |
| Max Turns | 15 |
| Episode Timeout | 600s |
| Namespace | `pmoves.consciousness` |

#### Dependencies

| Dependency | Service | Purpose |
|------------|---------|---------|
| NATS | `nats:4222` | Event bus for training lifecycle |
| HiRAG v2 | `hi-rag-gateway-v2:8086` | Knowledge retrieval for RL environment |
| EvoSwarm | `evo-controller` | Triggers training on fitness plateau |
| Supabase | `supabase-db` | Trajectory and checkpoint storage |
| MinIO | `minio:9000` | Model file storage |
| TensorZero | `tensorzero-gateway:3000` | Model routing (optional) |
| Weights & Biases | wandb.ai | Training experiment tracking |

#### Volumes

| Volume | Purpose |
|--------|---------|
| `agentgym-models` | Model checkpoints (shared) |
| `agentgym-logs` | Training logs |
| `agentgym-task-cache` | Cached constellation tasks for HiRAG environment |

#### TAC Tree References

- `training-pipeline.tac.yaml` — Phase 2 (Walk): agentic model training for PMOVES tool-use patterns
- `agent-teams-taxonomy.tac.yaml` — Training team with NATS subjects

### Integration Gap

Vendor volume mounts (`./vendor/agentgym-rl:/agentgym-rl:ro`) expect the submodule to be cloned at `pmoves/vendor/agentgym-rl/`. Currently empty — the service would fail to start without `git submodule update --init`.

---

## 4. PMOVES-llama-throughput-lab

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-llama-throughput-lab/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-llama-throughput-lab.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | LLM Benchmarking |

### What It Is

LLM throughput testing laboratory. Listed in submodule tables as `LLM throughput testing` with no assigned port or Docker profile.

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | None |
| **NATS Subjects** | None |
| **TensorZero** | None |
| **TAC Tree** | None |
| **Agent Registry** | Not registered |
| **Config Files** | None found |
| **Code References** | Only appears in summary tables in submodules.md |

### Integration Gap

Zero in-tree integration. This is the least integrated of all 9 submodules. Likely a standalone benchmarking tool (similar to llama.cpp benchmarks) that has not yet been adapted for PMOVES service orchestration. No evidence of planned integration in TAC trees or topology docs.

---

## 5. PMOVES-autoresearch

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-autoresearch/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-autoresearch.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | Autonomous ML Training |
| **Evolution Stage** | Pre-Stage |

### What It Is

Fork of [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — an AI agent-driven experiment runner that modifies, trains, and evaluates LLMs autonomously overnight. The agent modifies only `train.py` based on instructions in `program.md`, with fixed data prep in `prepare.py`. Metric: `val_bpb` (validation bits per byte, lower is better). Time budget: 5 minutes per experiment (~12 experiments/hour).

### Experiment Loop Architecture

```
program.md (human instructions)
    │
    ▼ AI agent reads
train.py (agent-modified model/optimizer/loop)
    │
    ▼ uv run train.py (5-min budget)
prepare.py (fixed data prep + evaluation)
    │
    ▼ val_bpb comparison
    ├── Improved → Keep
    └── Not improved → Discard, new approach
```

### Project Structure (from TAC tree)

```
PMOVES-autoresearch/
├── prepare.py      — Constants, data prep (DO NOT modify)
├── train.py        — Model, optimizer, training loop (agent modifies)
├── program.md      — Agent instructions (human modifies)
├── pyproject.toml   — Dependencies (PyTorch, etc.)
├── nats_reporter.py — NATS result publisher (PMOVES addition)
├── analysis.ipynb   — Experiment analysis notebook
├── progress.png     — Training progress visualization
└── uv.lock          — Locked dependencies
```

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | None — runs directly on GPU host |
| **NATS Subjects** | `research.autoresearch.result.v1` (publishes) — via `nats_reporter.py` |
| **TensorZero** | None |
| **TAC Tree** | `pmoves/docs/TAC/TAC_AUTORESEARCH.md` — full TAC tree exists |
| **Agent Registry** | Not registered as agent |
| **CHIT/CGP** | None — not CHIT-enabled |

### Planned Integration Path (from DEEP_DIVE_ALIGNMENT_2026-03-15.md)

| Planned Connection | Interface | Status |
|-------------------|-----------|--------|
| Agent Zero → autoresearch | NATS task delegation | Planned |
| autoresearch → Supabase | REST API (store results) | Planned |
| autoresearch → AgentGym RL | NATS / shared storage | Planned (E3 bridge) |
| autoresearch → Hi-RAG v2 | Ingest API (index findings) | Planned |

**Proposed NATS subjects (not yet implemented):**
- `research.autoresearch.experiment.v1` — experiment start/trigger
- `research.autoresearch.result.v1` — experiment results (partially implemented via nats_reporter.py)

### Integration Gap

Classified as **Pre-Stage** in alignment docs. No containerization, no Agent Zero orchestration path, no Supabase storage. The `nats_reporter.py` is the only PMOVES-specific addition confirmed. Priority P3 (add NATS publishing) and P4 (AgentGym bridge) in the integration roadmap.

---

## 6. PMOVES-crush

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-crush/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-crush.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | Development Tools |
| **Evolution Stage** | Stage 1 |

### What It Is

"Charm Crush" — a terminal-based AI coding assistant. Multi-model LLM support (OpenAI, Anthropic, local models), session-based context management, LSP-enhanced code intelligence, extensible via MCP (http, stdio, sse), cross-platform terminal support.

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | None — no compose profile defined |
| **NATS Subjects** | Publishes: `crush.graphiti.discovered.v1`, `shape.trace.recorded.v1` / Subscribes: `agent.graphiti.signed.v1` |
| **TensorZero** | Can integrate via TensorZero gateway for model routing (documented, not implemented) |
| **TAC Tree** | None dedicated |
| **Agent Registry** | Registered as agent: class=standard, type=ui+agent, layers=[L0,L2,L4], signature="crush" |
| **Voice Persona** | `pmoves-crush` — uses KittenTTS, <100ms latency, CLI notifications/gateway |

#### Agent Registry Detail

```yaml
crush:
  name: "Crush"
  class: standard
  primary_type: ui
  secondary_type: agent
  port: null
  health: null
  layers: [L0, L2, L4]
  evolution_stage: stage_1
  signature: "crush"
  nats:
    publishes: ["crush.graphiti.discovered.v1", "shape.trace.recorded.v1"]
    subscribes: ["agent.graphiti.signed.v1"]
  chit_toggles:
    delta_sensitive: false
    kappa_sensitive: false
    hz_sensitive: false
    swarm_participant: false
    attribution_gated: true
  resilience:
    context_budget: medium
    checkpoint_frequency: per_wave
  submodule: "PMOVES-crush"
  topology:
    node_affinity: [z890, 5090]
    team: ui
    ci_runner: ubuntu-latest
    compose_profile: null
```

#### Slash Commands

| Command | Description |
|---------|-------------|
| `/crush:setup` | Initialize Crush terminal assistant |
| `/crush:status` | Check Crush status |

### Integration Gap

No containerized deployment (compose_profile: null, port: null, health: null). NATS subjects defined in registry but no service code to publish them. Node affinity suggests z890/5090 desktop deployment. Evolution stage_1 indicates early development.

---

## 7. PMOVES-Deep-Serch

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-Deep-Serch/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | Research — Deep Search |

### What It Is

Deep research service — an LLM-based research planner that breaks down complex queries into research steps and executes them. Maps to the in-tree `deepresearch` service.

### In-Tree Service: `pmoves/services/deepresearch/`

```
app.py           — (entry point)
cookbooks.py     — Research cookbook loader
Dockerfile      — Container build
models.py       — ResearchRequest data model
parser.py       — Response parsing
requirements.txt
runner.py       — DeepResearchRunner (context assembly + provider dispatch)
worker.py       — NATS worker
```

### Docker Compose: `pmoves/docker-compose.workers.yml`

| Config | Value |
|--------|-------|
| **Service Name** | `deepresearch` |
| **Port** | 8098 (bind 127.0.0.1) |
| **Image** | Built from `services/deepresearch/Dockerfile` |
| **Profile** | workers |
| **Resources** | 2 CPU / 2G RAM |
| **Mode** | `tensorzero` (default) — routes through TensorZero gateway |

#### Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPRESEARCH_MODE` | `tensorzero` | tensorzero or openrouter |
| `DEEPRESEARCH_TIMEOUT` | 600s | Max research time |
| `DEEPRESEARCH_TENSORZERO_BASE_URL` | `http://tensorzero-gateway:3000` | TensorZero endpoint |
| `DEEPRESEARCH_OPENROUTER_MODEL` | `tongyi-deepresearch` | OpenRouter model fallback |
| `DEEPRESEARCH_NOTEBOOK_EMBED` | `true` | Auto-embed to Open Notebook |
| `DEEPRESEARCH_NOTEBOOK_ASYNC` | `true` | Async notebook publishing |
| `OPEN_NOTEBOOK_API_URL` | `http://open-notebook:5055` | Open Notebook endpoint |

#### DeepResearchRunner Architecture

The runner assembles context from cookbooks and user payload, then dispatches to either a local TensorZero-backed client or an OpenRouter client. Supports notebook embedding (auto-publishes research to Open Notebook/SurrealDB).

### NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `research.deepresearch.request.v1` | Subscribes | Incoming research requests |
| `research.deepresearch.result.v1` | Publishes | Research results output |

(Subjects defined in Supabase persona seed for Researcher agent — confirmed in `17_persona_seed.sql`)

### TensorZero Integration

DeepResearch is the primary consumer of TensorZero in the research pipeline. Uses `tensorzero` mode by default, routing research planning calls through the TensorZero gateway (port 3000). Falls back to OpenRouter with `tongyi-deepresearch` model.

### Related Services

| Service | Port | Relationship |
|---------|------|-------------|
| SupaSerch | 8099 | Orchestrates DeepResearch + Archon/Agent Zero MCP tools |
| Open Notebook | 5055 | Receives auto-published research results |
| Hi-RAG v2 | 8086 | SupaSerch coordinates HiRAG queries alongside DeepResearch |

### Integration Gap

Submodule not cloned, but in-tree service is fully functional. The submodule likely contains the original research implementation that was adapted into the in-tree service. No TAC tree dedicated to Deep-Serch specifically (covered by agent-teams taxonomy).

---

## 8. PMOVES-HiRAG

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `PMOVES-HiRAG/` |
| **Repository** | `https://github.com/POWERFULMOVES/PMOVES-HiRAG.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | Knowledge Base — Hybrid RAG |
| **Evolution Stage** | Production |

### What It Is

Hybrid Retrieval-Augmented Generation system combining three retrieval backends with cross-encoder reranking. The most mature AI/ML submodule in terms of in-tree integration.

### In-Tree Services

#### HiRAG v1: `pmoves/services/hi-rag-gateway/`

```
gateway.py       — 40KB monolithic gateway (v1)
Dockerfile
README.md
requirements.lock  — 113KB locked deps
requirements.txt
```

#### HiRAG v2: `pmoves/services/hi-rag-gateway-v2/` — PREFERRED

```
app.py            — FastAPI wiring (v2.1.0)
config.py         — 15KB central config
embeddings.py     — 11KB embedding pipeline
geometry_bus.py   — 32KB WebSocket rooms, ShapeStore, NATS swarm
Dockerfile        — CPU build
Dockerfile.gpu    — GPU build (for reranking)
clients/          — Backend clients:
  ├── qdrant/
  ├── neo4j/
  └── openai_compat/
routes/           — API routes:
  ├── health.py
  ├── query.py
  ├── geometry.py
  └── models.py
```

### Hybrid Retrieval Architecture

```
Query
  ├── Qdrant (vectors)     → Dense embedding similarity
  ├── Neo4j (graph)         → Knowledge graph traversal
  ├── Meilisearch (full-text) → BM25 keyword matching
  └── Cross-Encoder Rerank  → FlagReranker / FlagLLMReranker
       └── Optional: BGEM3FlagModel for BGE-M3 embeddings
```

### Optional Dependencies (Graceful Degradation)

The v2 config wraps all heavy dependencies in try/except ImportError:

| Dependency | Purpose | Fallback |
|------------|---------|----------|
| `torch` | GPU inference | CPU mode |
| `qdrant_client` | Vector search | Disabled |
| `sentence_transformers` | Embeddings | Disabled |
| `FlagEmbedding` (FlagReranker) | Cross-encoder rerank | Disabled |
| `FlagEmbedding` (FlagLLMReranker) | LLM-based rerank | Disabled |
| `FlagEmbedding` (BGEM3FlagModel) | BGE-M3 multi-vector | Disabled |
| `rapidfuzz` | Fuzzy matching | Disabled |

### Geometry Bus

The v2 gateway includes a full geometry bus implementation (32KB) providing:
- WebSocket rooms for real-time geometry streaming
- ShapeStore (capacity: 10,000 shapes) for geometry caching
- NATS swarm integration for distributed geometry events
- CHIT codebook integration
- GAN sideloader support
- Direct PostgreSQL connection for geometry persistence

### Docker Compose (from base docker-compose.yml)

| Service | Port | Profile |
|---------|------|---------|
| `hi-rag-gateway` (v1) | 8089 | — |
| `hi-rag-gateway-v2` (CPU) | 8086 | — |
| `hi-rag-gateway-v2-gpu` | 8087 | gpu |

### TAC Tree: `pmoves/configs/tac_trees/hirag-retrieval.tac.yaml`

Full audit tree covering:
- Phase 1: Hi-RAG v2 Gateway (compose definition, healthcheck, port separation v1/v2)
- Phase 2: Vector Store (Qdrant on port 6333, embedding model all-MiniLM-L6-v2)
- Phase 3+: Graph store (Neo4j), full-text (Meilisearch), reranking pipeline

### TensorZero Integration

HiRAG connects to TensorZero for embedding requests. The extract-worker service uses:
```
TENSORZERO_EMBED_MODEL=tensorzero::embedding_model_name::qwen3_embedding_4b_local
```
This routes embedding calls through TensorZero to a local Qwen3-4B embedding model (2560 dimensions).

### Training Pipeline Integration

From `training-pipeline.tac.yaml`:
- Phase 1 (Crawl): Fine-tune Qwen3-4B embeddings on PMOVES content for domain-specific retrieval
- Training data sources: CONCH transcript, CLAUDE.md files, Agent Graphiti trails, CHIT/CGP packets, TAC trees, NATS subject catalog
- Target: 10K+ (query, positive, negative) triplets
- Tool: `pmoves/tools/training/prep_embed_data.py`

### Consumers of HiRAG

| Consumer | How It Uses HiRAG |
|----------|-------------------|
| AgentGym-RL env | Knowledge retrieval during RL training episodes |
| DeepResearch | Via SupaSerch orchestration |
| SupaSerch | Direct `POST /hirag/query` calls |
| Session Context Worker | `HIRAG_INGEST_URL=http://hi-rag-gateway-v2:8086/ingest` |
| Retrieval Eval | `HIRAG_URL=http://hi-rag-gateway-v2:8086` for benchmarking |
| GitHub Issue Triage | `HIRAG_URL` for historical issue context |

### Integration Gap

Submodule not cloned, but in-tree v2 service is comprehensive. The submodule likely contains upstream HiRAG code that was heavily modified for PMOVES (geometry bus, ShapeStore, CHIT integration, NATS swarm). Port conflict between v1/v2 was a known issue (now resolved with separate port variables).

---

## 9. Pmoves-hyperdimensions

### Submodule Status

| Field | Value |
|-------|-------|
| **Path** | `Pmoves-hyperdimensions/` |
| **Repository** | `https://github.com/POWERFULMOVES/Pmoves-hyperdimensions.git` |
| **Branch** | `PMOVES.AI-Edition-Hardened` |
| **Local State** | EMPTY — not cloned |
| **Category** | Specialized — UI + Data |
| **Evolution Stage** | Base |

### What It Is

Holographic visualization system for hyperdimensional computing. Provides Three.js-based rendering of high-dimensional data surfaces.

### In-Tree Integration

| Integration Point | Details |
|------------------|---------|
| **Docker Compose** | None |
| **NATS Subjects** | None (empty publishes array in agent registry) |
| **TensorZero** | None |
| **TAC Tree** | None |
| **Agent Registry** | Registered: class=specialized, type=ui+data, layers=[L0,L2.5], evolution_stage=base |

#### Agent Registry Detail

```yaml
hyperdimensions:
  name: "Hyperdimensions"
  class: specialized
  primary_type: ui
  secondary_type: data
  port: null
  health: null
  layers: [L0, L2.5]
  evolution_stage: base
  nats:
    publishes: []
  submodule: "Pmoves-hyperdimensions"
```

#### Slash Commands

| Command | Description |
|---------|-------------|
| `/hyperdim:render` | Three.js surface rendering |
| `/hyperdim:animate` | Animated visualizations |
| `/hyperdim:export` | Export to 3D formats |

#### Related Skills

| Skill | File | Description |
|-------|------|-------------|
| Three.js render | `pmoves/skills/threejs-render/manifest.yaml` | Three.js rendering capability |
| Remotion render | `pmoves/skills/remotion-render/manifest.yaml` | Video rendering (possibly related) |

### Integration Gap

Earliest evolution stage (base). No containerized deployment, no NATS subjects, no TAC tree. The slash commands suggest a CLI/web-based visualization tool. The L2.5 layer designation is unusual (half-layer) suggesting partial integration. Port and health are null.

---

## Cross-Cutting Analysis

### NATS Subject Map (All 9 Submodules)

```
# AgentGym-RL (implemented)
geometry.event.v1                    ← subscribe (trajectory accumulation)
tokenism.geometry.event.v1           ← subscribe
hf.model.downloaded.v1               ← subscribe
agentgym.train.completed.v1          ← subscribe (auto-publish trigger)
training.model.published.v1           → publish
training.job.started.v1               → publish (from training-pipeline TAC)
training.job.completed.v1             → publish
training.job.failed.v1                → publish
training.eval.result.v1               → publish
training.model.deployed.v1            → publish

# Deep-Serch (implemented via deepresearch service)
research.deepresearch.request.v1      ← subscribe
research.deepresearch.result.v1       → publish

# Autoresearch (partially implemented)
research.autoresearch.result.v1        → publish (via nats_reporter.py)
research.autoresearch.experiment.v1    → publish (planned, not implemented)

# Crush (defined in registry, not implemented)
crush.graphiti.discovered.v1          → publish
shape.trace.recorded.v1               → publish
agent.graphiti.signed.v1              ← subscribe

# HiRAG, AgentGym, llama-throughput-lab, Hyperdimensions
# No dedicated NATS subjects found
```

### TensorZero Integration Map

| Submodule | TensorZero Usage | Model |
|-----------|-----------------|-------|
| HiRAG | Embedding routing | `qwen3_embedding_4b_local` (2560d) |
| Deep-Serch | Research planning dispatch | Via gateway (model-agnostic) |
| AgentGym-RL | Optional model routing | Via `TENSORZERO_BASE_URL` |
| Crush | Planned model routing | Not implemented |
| Others | None | — |

### Evolution Stage Summary

| Stage | Submodules | Meaning |
|-------|-----------|---------|
| Production | HiRAG | Fully containerized, monitored, TAC-audited |
| Stage 1 | Crush | Agent registered, NATS defined, no container |
| Pre-Stage | Autoresearch | TAC tree exists, NATS partially implemented, no container |
| Base | Hyperdimensions | Agent registered, slash commands, no services |
| Unstaged | AgentGym, AgentGym-RL*, llama-throughput-lab | RL has production compose but submodule itself unstaged |
| External | Creator | Upstream image, hardened fork not integrated |

*AgentGym-RL is anomalous: production-grade docker-compose exists but evolution stage not formally assigned.

### Dependency Graph (In-Tree Services Only)

```
                    ┌─────────────┐
                    │  NATS Bus   │
                    │  :4222      │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
    │ AgentGym-RL │ │DeepResearch│ │ Hi-RAG v2   │
    │ Coordinator │ │  :8098     │ │  :8086/8087 │
    │   :8114     │ └─────┬──────┘ └──────┬──────┘
    └──────┬──────┘       │               │
           │               │         ┌─────┴─────┐
    ┌──────▼──────┐       │         │           │
    │ AgentGym    │       │      Qdrant     Neo4j
    │ Env-PMOVES  │       │      :6333      :7687
    │   :36000    │       │         │           │
    └──────┬──────┘       │      Meilisearch
           │               │        :7700
           └───────┬───────┘
                   │
            ┌──────▼──────┐
            │ TensorZero  │
            │ Gateway     │
            │   :3000     │
            └──────┬──────┘
                   │
            ┌──────▼──────┐
            │   Ollama    │
            │  :11434     │
            └─────────────┘

    NOT CONTAINERIZED:
    ┌──────────┐ ┌──────────────┐ ┌─────────────┐
    │  Crush   │ │ Autoresearch │ │Hyperdimensions│
    │ (CLI)    │ │ (GPU CLI)    │ │ (slash cmds) │
    └──────────┘ └──────────────┘ └─────────────┘
    ┌──────────────────┐
    │llama-throughput  │
    │     lab          │
    └──────────────────┘
```

---

## Recommendations

### P0 — Unblock Existing Services

1. **Clone AgentGym-RL submodule** to `pmoves/vendor/agentgym-rl/` — the docker-compose.agentgym.yml mounts this volume read-only. Without it, the coordinator and environment services cannot start.
2. **Clone HiRAG submodule** to `PMOVES-HiRAG/` — verify in-tree v2 service matches or supersedes submodule code. Consider deprecating v1 gateway.

### P1 — Close Integration Gaps

3. **Autoresearch → AgentGym-RL bridge (E3)**: Implement `research.autoresearch.result.v1` → AgentGym RL training data pipeline. Creates closed loop: autoresearch finds better architectures → AgentGym trains with them.
4. **Containerize Autoresearch**: Create Dockerfile + compose profile for GPU-host deployment. Add health endpoint and Prometheus metrics.
5. **Crush containerization**: Define compose profile, assign port, implement NATS publishers defined in agent registry.

### P2 — Bring Staging Up

6. **Hyperdimensions evolution**: Advance from base to stage_1. Add NATS subjects, define compose profile, implement Three.js render service.
7. **llama-throughput-lab assessment**: Determine if this submodule is still relevant. If yes, create integration plan. If no, consider removal from .gitmodules.
8. **Creator hardened Dockerfile**: Replace `runpod/comfyui:latest` with PMOVES-Creator fork build to enable hardened workflow execution.

### P3 — TAC Tree Completion

9. Create TAC trees for: Crush, Deep-Serch, Hyperdimensions, llama-throughput-lab, AgentGym (base)
10. Update `hirag-retrieval.tac.yaml` to cover Neo4j and Meilisearch phases (currently only Phase 1-2 visible in excerpt)

---

## Appendix A: Git Module URLs

| Submodule | GitHub URL | Branch |-----------|-----------|--------|
| PMOVES-Creator | https://github.com/POWERFULMOVES/PMOVES-Creator.git | PMOVES.AI-Edition-Hardened |
| PMOVES-AgentGym | https://github.com/POWERFULMOVES/PMOVES-AgentGym.git | PMOVES.AI-Edition-Hardened |
| Pmoves-AgentGym-RL | https://github.com/POWERFULMOVES/Pmoves-AgentGym-RL.git | PMOVES.AI-Edition-Hardened |
| PMOVES-llama-throughput-lab | https://github.com/POWERFULMOVES/PMOVES-llama-throughput-lab.git | PMOVES.AI-Edition-Hardened |
| PMOVES-autoresearch | https://github.com/POWERFULMOVES/PMOVES-autoresearch.git | PMOVES.AI-Edition-Hardened |
| PMOVES-crush | https://github.com/POWERFULMOVES/PMOVES-crush.git | PMOVES.AI-Edition-Hardened |
| PMOVES-Deep-Serch | https://github.com/POWERFULMOVES/PMOVES-Deep-Serch.git | PMOVES.AI-Edition-Hardened |
| PMOVES-HiRAG | https://github.com/POWERFULMOVES/PMOVES-HiRAG.git | PMOVES.AI-Edition-Hardened |
| Pmoves-hyperdimensions | https://github.com/POWERFULMOVES/Pmoves-hyperdimensions.git | PMOVES.AI-Edition-Hardened |

## Appendix B: Source Files Examined

| File | Information Extracted |
------|----------------------|
| `.gitmodules` | All 9 submodule URLs and branches |
| `pmoves/docker-compose.agentgym.yml` | AgentGym-RL full service definitions |
| `pmoves/docker-compose.comfyui.yml` | Creator ComfyUI service |
| `pmoves/docker-compose.workers.yml` | DeepResearch service + 15 other workers |
| `pmoves/docker-compose.yml` | HiRAG v1/v2 service definitions (base) |
| `pmoves/config/agent_registry.yaml` | Crush + Hyperdimensions agent entries |
| `pmoves/configs/tac_trees/hirag-retrieval.tac.yaml` | HiRAG audit tree |
| `pmoves/configs/tac_trees/training-pipeline.tac.yaml` | 3-phase training pipeline |
| `pmoves/configs/tac_trees/agent-teams-taxonomy.tac.yaml` | 11 teams, 62 agents, NATS subjects |
| `pmoves/docs/TAC/TAC_AUTORESEARCH.md` | Full autoresearch TAC tree |
| `pmoves/docs/TAC/TAC_INTEGRATION_TOPOLOGY.md` | Cross-submodule integration map |
| `pmoves/docs/AGENTS/DEEP_DIVE_ALIGNMENT_2026-03-15.md` | Alignment gaps and priorities |
| `pmoves/services/agentgym-rl-coordinator/app.py` | Coordinator NATS handlers |
| `pmoves/services/hi-rag-gateway-v2/config.py` | HiRAG v2 dependency graph |
| `pmoves/services/hi-rag-gateway-v2/geometry_bus.py` | ShapeStore, WebSocket, NATS swarm |
| `pmoves/services/hi-rag-gateway-v2/app.py` | v2 FastAPI wiring |
| `pmoves/services/deepresearch/runner.py` | Research runner dispatch logic |
| `pmoves/tensorzero/config/tensorzero.toml` | Model routing config |
| `.claude/context/submodules.md` | Submodule documentation index |
| `.claude/context/modular-architecture.md` | Architecture context |
| `.claude/context/voice-personas.md` | Crush voice persona mapping |
| `pmoves/supabase/initdb/17_persona_seed.sql` | Researcher persona with NATS subjects |

---

*End of report.*
