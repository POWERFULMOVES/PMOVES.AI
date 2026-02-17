# Model Source of Truth

> Referenced by: `PMOVES_UNIFIED_AGENT_TAXONOMY.md`, `PMOVES_AGENT_CLASS_TAXONOMY.md`

## Principle

PMOVES.AI is **model-agnostic by design**. TensorZero is the single routing point for all LLM calls. Documentation, architecture descriptions, and runtime code must use **role names**, not concrete model IDs.

## TensorZero Role Names

| Role | Purpose | Example Concrete Models (for sizing only) |
|------|---------|------------------------------------------|
| `orchestrator` | Complex reasoning, task planning, architecture | Qwen2.5-14B/32B/72B, Mixtral-8x22B |
| `utility` | Fast simple tasks, safety checks, auditing | Phi-3-Mini, Qwen2.5-3B, Gemma-2-2B |
| `coding` | Code generation and analysis | Qwen2.5-Coder-7B, DeepSeek-Coder-6.7B |
| `reasoning` | Deep multi-hop logical tasks | DeepSeek-V3.1 distilled, Qwen2.5-72B |
| `embed` | Text embedding generation | Qwen3-Embedding-4B/8B, BGE-Large |
| `vl_sentinel` | Vision-language processing | Qwen2-VL-7B, Qwen3-VL-8B |
| `hirag_rerank` | Cross-encoder reranking for RAG | Qwen3-Reranker-4B, Jina-Reranker-v2 |
| `research` | Deep research, coordinator tasks | Qwen2.5-32B/72B |

## Where Concrete Model Names Are Acceptable

| Context | Acceptable? | Reason |
|---------|------------|--------|
| Hardware sizing docs (`HARDWARE_TTS_REQUIREMENTS.md`) | Yes | VRAM calculations need exact parameters |
| Model setup guides (`LOCAL_MODEL_SETUP.md`) | Yes | `ollama pull` commands need exact IDs |
| Config files (`pmoves/config/models.yaml`) | Yes | Canonical model catalog |
| Historical footnotes / Works Cited | Yes | Academic attribution |
| Architecture descriptions | **No** | Use role names |
| Taxonomy definitions | **No** | Use role names |
| API examples in docs | **No** | Use `"model": "orchestrator"` |
| Runtime code | **No** | Use TensorZero role routing |

## Canonical Config Files

- **`pmoves/config/models.yaml`** — Master catalog of local models with HuggingFace mappings, hardware requirements, and role assignments
- **`pmoves/config/models_by_tier.yaml`** — Hardware-tier-specific model recommendations (CPU, consumer GPU, workstation, multi-GPU)

## How Runtime Routing Works

```
Agent Code                    TensorZero Gateway              Model Backend
─────────────                 ──────────────────              ─────────────
POST /v1/chat/completions     Receives role name              Routes to concrete
  model: "orchestrator"   →   Looks up routing table      →   model based on
                              (hardware profile +              current config
                               load balancing)
```

Agents never specify concrete model names at runtime. TensorZero resolves the role to the best available model based on:
1. Hardware profile (CPU, consumer GPU, workstation, multi-GPU)
2. Current load and availability
3. Model capability requirements (context length, multimodal, etc.)

## Model Spotlight

PMOVES routes to strengths, not just availability. Every model has a **strength profile** — a set of dimensional scores that capture what it's good at, what it's done, and how it performs. Users get matched to the right model, and both sides do less work because the fit is better.

### Strength Dimensions

Each model is scored 0.0–1.0 on six dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| `reasoning` | Complex multi-hop logic, task planning, architecture design |
| `speed` | Tokens/sec throughput, time to first token |
| `coding` | Code generation, analysis, debugging, refactoring |
| `multilingual` | Non-English language quality (especially CJK, RTL) |
| `creativity` | Open-ended generation, brainstorming, novel solutions |
| `context_handling` | Effective use of long context windows (RAG, documents) |

Plus a `cost_efficiency_score` (0–10 scale, higher = more tokens per dollar) and a `primary_strength` label for quick identification.

### How Metrics Are Collected

```
TensorZero Gateway ──OTLP──▶ ClickHouse (raw traces)
                                    │
                              hourly queries
                              (cron / n8n)
                                    │
                                    ▼
                            Supabase model_metrics
                            (per-model hourly aggregates)
                                    │
                              refresh_model_strengths()
                                    │
                                    ▼
                            Supabase model_strengths
                            (computed profiles)
                                    │
                                    ▼
                        Grafana "Model Spotlight" dashboard
```

1. **TensorZero** logs every inference to ClickHouse via OTLP (model, tokens, latency, errors)
2. **ClickHouse aggregation queries** (`pmoves/monitoring/clickhouse/model_spotlight_queries.sql`) extract hourly per-model stats
3. A scheduled job writes those aggregates to **`pmoves_core.model_metrics`** in Supabase
4. **`pmoves_core.refresh_model_strengths()`** rolls up all-time stats into `model_strengths`
5. The **Grafana Model Spotlight dashboard** (`pmoves/monitoring/grafana/dashboards/model-spotlight.json`) visualizes everything

### Seeded Profiles

Before production data accumulates, strength profiles are seeded from known model characteristics:

- **Seed file:** `pmoves/config/model_strengths_seed.yaml`
- Covers all local models from `models.yaml` plus cloud models from `tensorzero.toml`
- Each model gets a `notes` field — a tongue-in-cheek personality description that's semantically connected to what the model actually does

### Grafana Dashboard Panels

The Model Spotlight dashboard provides:

| Panel | Shows |
|-------|-------|
| Model Leaderboard | Top models by requests served, sortable table |
| Requests by Model | Per-model request rate over time (Prometheus) |
| Latency by Model | Per-model p95 latency over time |
| Token Throughput | Total tokens served per model (bar chart) |
| Cost Efficiency | Tokens per cost unit by model (bar gauge) |
| Strength Scores | Heat-mapped table of all six dimensions |
| Model Personality | The tongue-in-cheek notes field |
| VRAM Footprint | VRAM usage per model from model registry |
| Models by Type/Provider | Distribution pie charts |

### The Fairness Principle

> PMOVES routes to strengths, not just availability.

Models are not interchangeable commodities. A model that excels at coding should get coding tasks. A model that excels at multilingual work should get multilingual tasks. Fair routing means:

1. **Strength-aware selection** — routing considers dimensional scores, not just "is it online?"
2. **Transparent attribution** — users see which model handled their request and why
3. **Measured improvement** — production data feeds back into strength profiles over time
4. **Every model shines** — small models aren't second-class; they shine where they're strong

### Schema (Supabase)

- **`pmoves_core.model_metrics`** — Hourly aggregated per-model stats (migration: `20260218_model_spotlight.sql`)
- **`pmoves_core.model_strengths`** — Computed strength profiles (one row per model)
- **`pmoves_core.v_model_spotlight`** — Convenience view joining models + providers + strengths

## CHIT-Distilled Models

PMOVES doesn't just consume models — it **builds** them. CHIT (Compressed Hierarchical Information Transfer) is not merely a compression protocol; it's a **distillation signal**. Data encoded through CHIT geometry trains models that reconstruct orthogonal information with arbitrary precision.

### The Distillation Pipeline

```
Raw Data ──▶ CHIT Encoder ──▶ CGP v0.2 Packets ──▶ Training Dataset (HuggingFace)
(text, img,   (multi-lane)    (shaped data)                │
 audio)            ▲                                       ▼
                   │                              Fine-Tune / Distill
            EvoSwarm (8113)                       (AgentGym trainers)
            evolves geometry                               │
            parameters                                     ▼
                                                 PMOVES Model ──▶ HuggingFace Hub
                                                 (CHIT-native)    (DARKXSIDE org)
```

### Multi-Lane Reconstruction

CHIT operates across four modality lanes, all sharing CGP v0.2 format:

| Lane | Input | Output | Key Parameter |
|------|-------|--------|---------------|
| Text | Text → CHIT | → Text | delta (curvature) — semantic density |
| Image | Image → CHIT | → Image | kappa (concentration) — spatial frequency |
| Audio | Audio → CHIT | → Audio | Hz (frequency) — spectral fidelity |
| Mixed | Any → CHIT | → Any | Cross-modal mapping via shared geometry |

Each lane's geometry parameters are **evolved by EvoSwarm** (port 8113). The controller publishes evolved parameter packs on `evoswarm.training.genome.v1` and receives fitness scores on `evoswarm.training.fitness.v1`.

### Published Datasets

Defined in `pmoves/config/datasets.yaml`, published via `pmoves/scripts/publish_dataset.py`:

| Dataset | HuggingFace ID | Contents |
|---------|---------------|----------|
| CHIT Text | `DARKXSIDE/pmoves-chit-text` | Text → CGP packets with reconstruction targets |
| CHIT Multimodal | `DARKXSIDE/pmoves-chit-multimodal` | Multi-lane (text, image, audio) CGP packets |
| Agent Traces | `DARKXSIDE/pmoves-agent-traces` | DPO pairs from production agent execution |

### PMOVES-Built Model Templates

Three initial model templates (seeded in `model_strengths_seed.yaml`):

| Model | Strength | Training Signal |
|-------|----------|----------------|
| `pmoves-chit-text-7b` | context_handling (0.92) | CHIT text reconstruction |
| `pmoves-chit-multi-7b` | creativity (0.88) | Cross-lane multimodal mapping |
| `pmoves-agent-dpo-7b` | reasoning (0.82) | Agent trace DPO pairs |

### EvoSwarm Training Genome

EvoSwarm evolves training hyperparameters alongside geometry parameters:

- **learning_rate**: [1e-5, 1e-3] — base LR for fine-tuning
- **chit_weight**: [0.1, 0.9] — CHIT reconstruction loss contribution
- **reconstruction_target**: text | image | audio | cross
- **lane_mixing_ratio**: [0.0, 1.0] — single-lane vs cross-lane mix
- **distillation_temperature**: [0.5, 5.0] — softmax temperature for KD

Fitness = `reconstruction_fidelity × cost_efficiency`

### Cross-References (Phase G)

- Multi-lane module: `pmoves/services/common/chit_lanes.py`
- Dataset catalog: `pmoves/config/datasets.yaml`
- Publishing script: `pmoves/scripts/publish_dataset.py`
- EvoSwarm controller: `pmoves/services/evo-controller/app.py`
- Agent registry entry: `pmoves/config/agent_registry.yaml` → `evoswarm_controller`

### Future

- Automated training loop: EvoSwarm evolves → CHIT encodes → AgentGym trains → HF publishes → Spotlight tracks
- Image lane implementation (Pillow/torchvision → CHIT → reconstruction)
- Audio lane implementation (torchaudio → CHIT → spectral reconstruction)
- MACA consensus for CHIT reconstruction quality validation
- Model seasons: periodic retraining with evolved EvoSwarm parameters
- Soulbound tokens: shape attribution + geometry proofs for published models
- Automated n8n workflow running ClickHouse queries hourly
- NATS events (`model.milestone.reached.v1`) when models hit request/token milestones
- Hyperdimensions visualization of strength profiles as geometric shapes
- User preference learning feeding back into routing weights

## Cross-References

- CHIT multi-lane module: `pmoves/services/common/chit_lanes.py`
- Dataset catalog: `pmoves/config/datasets.yaml`
- Dataset publisher: `pmoves/scripts/publish_dataset.py`
- Agent registry: `pmoves/config/agent_registry.yaml`
- Agent taxonomy: `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`
- Unified taxonomy: `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`
- Hardware sizing: `pmoves/docs/AGENTS/HARDWARE_TTS_REQUIREMENTS.md`
- Local setup: `pmoves/docs/PMOVESCHIT/LOCAL_MODEL_SETUP.md`
- Model Spotlight dashboard: `pmoves/monitoring/grafana/dashboards/model-spotlight.json`
- Strength seed profiles: `pmoves/config/model_strengths_seed.yaml`
- ClickHouse queries: `pmoves/monitoring/clickhouse/model_spotlight_queries.sql`
- Spotlight migration: `pmoves/supabase/migrations/20260218_model_spotlight.sql`
