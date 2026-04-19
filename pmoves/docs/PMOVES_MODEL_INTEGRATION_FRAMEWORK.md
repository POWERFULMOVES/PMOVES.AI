# PMOVES Model Integration Framework

**Version:** 1.0.0  
**Date:** 2026-04-19  
**Status:** Canonical Reference  
**Supersedes:** `Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md` (historical baseline, 2025-era)

---

## 1. Purpose

This framework maps the **PMOVESCHIT Distillation pipeline** to the model configuration lifecycle. Every model that enters the PMOVES ecosystem gets a **Model Suit** — a YAML profile ensuring it "fits like a glove" across all agents and deployment contexts.

The Distillation pipeline ([THREE_BODY_DOCTRINE.md §7](pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md)) defines four stages:

| Stage | What It Produces | Suit Field |
|-------|-----------------|------------|
| `config_tuning` | Provider-recommended temperature, context, SDK settings | `model_config` |
| `context_priming` | Per-model prompt style, format preferences, system templates | `prompt_style` |
| `model_fine_tune` | LoRA/adapter weights trained on accumulated traces | `fine_tuning` |
| `full_distillation` | Complete config + model + context strategy for cross-agent deployment | All fields populated |

Each suit profile lives in `/a0/usr/projects/pmoves_ai/pmoves/configs/model-suits/` and is **layered above** agent profiles in `/a0/usr/projects/pmoves_ai/pmoves/configs/agent-profiles/`. Agent profiles define *where* a claw runs (node affinity, NATS subjects, exec permissions). Model suits define *how* a model behaves (temperature, prompt format, fallback chain, cross-agent compatibility).

**Key principle:** Agent profiles are hardware/topology concerns. Model suits are capability/behavior concerns. They compose — a `spark_claw` agent profile can load any model suit that targets `ollama_spark`.

---

## 2. Model Suit Anatomy

Every suit YAML follows this structure. Fields map directly to Distillation stages.

### Top-Level Metadata

```yaml
name:              # Unique suit identifier (filename sans .yaml)
provider:          # ollama_local | ollama_spark | zai | openrouter
provider_display:  # Human-readable provider name
distillation_stage: # config_tuning | context_priming | model_fine_tune | full_distillation
```

`distillation_stage` indicates the **highest completed stage**. A cloud-only model with no local weights caps at `config_tuning`. A local model with LoRA path reaches `model_fine_tune`. `full_distillation` means all stages are complete — the suit is production-ready for cross-agent deployment.

### `model_config` — Maps to `config_tuning`

```yaml
model_config:
  model_name:          # Provider-specific model identifier
  endpoint:             # API base URL (null for Ollama local)
  api_key_env:          # Environment variable name for API key
  context_window:       # Maximum context tokens
  max_output_tokens:    # Maximum generation tokens
  temperature:          # Provider-recommended default
  top_p:                # Provider-recommended default
  ollama_config:        # Ollama-specific (local models only)
    num_gpu: 999        # NGL — offload all layers to GPU
    num_batch: 4096     # Batch size for prompt processing
    ubatch: 1024        # Micro-batch for GPU compute
    quantization: Q4_K_M
```

These are **not cookie-cutter values** — each is sourced from provider documentation or benchmark validation. See §9 for Ollama config rationale.

### `prompt_style` — Maps to `context_priming`

```yaml
prompt_style:
  format:              # xml | markdown | json | structured
  system_prompt_template: null  # Model-specific template (if known)
  preferred_language:  en
  notes: "..."         # Provider-specific prompt guidance
```

This is critical. Claude models require XML tags. GLM models prefer clean markdown. Nemotron uses structured JSON patterns. Sending the wrong format to a model degrades output quality — this field prevents that.

### `agent_zero` — Agent Zero Wiring

```yaml
agent_zero:
  role:                # chat | utility | embedding
  a0_set_prefix:       # Environment variable prefix (A0_SET_chat_model, etc.)
  subordinate_profile:  # Which agent profile to use
  strengths: [...]      # Model capability tags
  limitations: [...]    # Known constraints
```

See §5 for full wiring details.

### `pinokio_p7` — Pinokio P7 Integration

```yaml
pinokio_p7:
  discoverable:        # Can P7 Agent Interpreter find this model?
  pbnj_launch:          # Does PBNJ app manage this model's lifecycle?
  tac_node:             # TAC tree node for tracking
  nats_subject:         # NATS subject for model load/unload events
```

See §4 for full P7 integration details.

### `local_fallback` — Offline Resilience

```yaml
local_fallback:
  available:           # Can this model run without network?
  reason: "..."        # Why or why not
  fallback_model_suit:  # Which suit to use when this one fails
```

Cloud models always point to a local suit. Local models MAY reference a smaller local fallback (e.g., `gemma4-dense` → `qwen3.6` when DGX Spark isn't available) or set `fallback_model_suit: null` if they are the smallest option.

### `fine_tuning` — Maps to `model_fine_tune`

```yaml
fine_tuning:
  possible:            # Open weights available?
  method: lora          # lora | qlora | full
  target_platform:      # dgx-spark | cloud
  notes: "..."          # Training considerations
```

Only models with open weights can be fine-tuned. See §7 for the full pipeline.

### `cross_agent` — Ecosystem Compatibility

```yaml
cross_agent:
  agent_zero: full     # full | limited | none
  clawz: limited
  typer: untested
  pinokio: full
```

- **full**: Model works natively in this agent
- **limited**: Works with adaptation layer (e.g., GLM in ClaWZ needs Claude Code wrapper)
- **none**: Cannot function in this agent (e.g., local Ollama model in cloud-only P7)
- **untested**: Not yet validated — assume `limited`

### `metadata` — Provenance

```yaml
metadata:
  source:              # Where this data came from
  last_verified:       # Date of last validation
  benchmark_data:      # Array of benchmark sources and notes
```

All data is traceable. No fabricated benchmarks.

---

## 3. DGX Spark Model Stack

The **DGX Spark** (GB10 Grace-Blackwell, 128GB unified LPDDR5X, 1 petaFLOP FP4) runs a 5-model stack: 3 local + 2 cloud.

### Stack Composition

| Slot | Model | Suit File | VRAM | Role |
|------|-------|-----------|------|------|
| Local Heavyweight | Gemma4 Dense Q4 | `gemma4-dense.yaml` | ~20-24GB | General chat, throughput champion |
| Local Specialist | Nemotron-3 Super Q4 | `nemotron-3-super.yaml` | ~100GB | Single-purpose agents, tool calling |
| Local Utility | Qwen3.6 Q4_K_M | `qwen3.6.yaml` | ~16GB | Fast utility tasks, tool calling |
| Cloud Chat | GLM-5-Turbo | `glm-5-turbo.yaml` | 0 (remote) | Primary chat via Z.AI MAX |
| Cloud Utility | GLM-5.1 | `glm-5.1.yaml` | 0 (remote) | Coding tasks via Z.AI MAX |

### Memory Math

```text
DGX Spark Total:           128 GB unified LPDDR5X
─────────────────────────────────────────────────
Nemotron-3 Super Q4:       ~100 GB  (leaves 20-28GB KV cache)
Gemma4 Dense Q4:           ~24 GB   (fits comfortably)
Qwen3.6 Q4_K_M:           ~16 GB   (fits comfortably)
─────────────────────────────────────────────────
Simultaneous fit check:
  Nemotron alone:          100 + 28 KV = 128 ✓ (maxed out)
  Gemma4 + Qwen3.6:        24 + 16 = 40 GB  ✓ (88GB free for KV)
  Gemma4 alone (hot):      24 + 104 KV = 128 ✓ (massive context)
  Qwen3.6 alone (hot):     16 + 112 KV = 128 ✓ (enormous context)
```

**Operational rule:** Only one heavyweight model loaded at a time. Nemotron and Gemma4 are mutually exclusive in memory. Qwen3.6 can coexist with either due to its small footprint. Cloud models consume zero local memory.

### Why This Stack

- **Gemma4 Dense** over MoE: Benchmark data shows dense is 12x faster (10,000 vs 830 tok/s) when VRAM is available. DGX Spark has 128GB — VRAM is not constrained.
- **Nemotron** for specialists: NVIDIA's NIM Cloud optimization means it's the most efficient model on Spark hardware for focused tasks.
- **Qwen3.6** for speed: At 3,262 tok/s generation, it handles subordinate agent utility calls faster than waiting for cloud round-trips.
- **GLM-5-turbo/5.1** for capability: Cloud models provide 128K context and broader reasoning than local 32K models.

### Agent Profile Mapping

| Agent Profile | Default Model Suit | Fallback |
|---------------|-------------------|----------|
| `spark_claw` | `gemma4-dense` | `qwen3.6` |
| `sidecar` | `glm-5-turbo` (cloud) | `qwen3.6` (local) |

---

## 4. Pinokio P7 Integration

Model suits connect to the Pinokio 7 ecosystem through three mechanisms:

### 4.1 Agent Interpreter Discovery

P7's Agent Interpreter can auto-discover models running on local Ollama endpoints. The `pinokio_p7.discoverable` field indicates whether P7 can find and use the model:

- **Cloud models** (`glm-5-turbo`, `glm-5.1`, `claude-sonnet`): `discoverable: false` — no local Ollama endpoint
- **Local models** (`qwen3.6`, `gemma4-dense`, `nemotron-3-super`): `discoverable: true` — exposed via Ollama API

P7 discovers models through the built-in `pinokio` skill, which auto-launches installed apps and waits for readiness. For Ollama-served models, this means P7 can route requests to `http://localhost:11434` or through Tailscale to `http://pmoves-dgx-spark:11434`.

Reference: [AGNOTE_P7_PLAYGROUND.md](pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md) §P7 Gates

### 4.2 PBNJ Launcher

The `pinokio_p7.pbnj_launch` field indicates whether the PBNJ Pinokio app manages the model's lifecycle. Currently all models are `false` — PBNJ manages service stacks (Agent Zero, NATS, Supabase) but not individual model pull/load cycles. This may change as PBNJ evolves to include GPU mesh management.

Reference: `/a0/usr/projects/pmoves_ai/pbnj/pinokio/api/pmoves-services/pinokio.json`

### 4.3 TAC Node Tracking

Model load/unload events flow through the TAC tree at `p7.nats.model-discovery`. The `pinokio_p7.tac_node` field maps each suit to its tracking node:

| Suit | TAC Node | NATS Subject | Status |
|------|----------|-------------|--------|
| `qwen3.6` | `p7.nats.model-discovery` | `mesh.gpu.model.loaded.v1` | DECLARED |
| `gemma4-dense` | `p7.nats.model-discovery` | `mesh.gpu.model.loaded.v1` | DECLARED |
| `nemotron-3-super` | `p7.nats.model-discovery` | `mesh.gpu.model.loaded.v1` | DECLARED |
> **Note:** DECLARED = suit files define NATS subjects but no runtime wiring exists yet. Requires publisher/subscriber code in `provider_cascade.py` or a model-registry service. No evidence of runtime NATS wiring for model-suits in the current codebase.

Reference: [pinokio-p7.tac.yaml](pmoves/configs/tac_trees/pinokio-p7.tac.yaml) §Phase 2

---

## 5. Agent Zero Wiring

### A0_SET_ Variable Mapping

Agent Zero uses environment variables prefixed with `A0_SET_` to configure model endpoints. Each suit's `agent_zero.a0_set_prefix` maps to these variables:

| A0_SET_ Variable | Purpose | Current Suit |
|-----------------|---------|-------------|
| `A0_SET_chat_model` | Primary chat model endpoint | `glm-5-turbo` (cloud) / `gemma4-dense` (Spark) |
| `A0_SET_utility_model` | Utility/coding model endpoint | `glm-5.1` (cloud) / `qwen3.6` (local) |
| `A0_SET_embedding_model` | Embedding model endpoint | Not in current suits (future) |

### Profile Switching

The `agent_zero.subordinate_profile` field determines which agent profile loads when a subordinate uses this model:

- `sidecar`: Default profile for cloud models. Runs on any device with Docker. Uses `host.docker.internal:11434` for Ollama.
- `spark_claw`: DGX Spark profile for local heavyweights. Runs on `pmoves-dgx-spark` hostname. Full GPU access, NATS mesh participation.

Switching example:
```bash
# Sidecar mode (cloud-first, any device)
A0_SET_chat_model=https://integrate.api.nvidia.com/v1/glm-5-turbo
subordinate_profile=sidecar

# Spark mode (local-first, DGX Spark)
A0_SET_chat_model=http://pmoves-dgx-spark:11434/v1/gemma4:31b-q4
subordinate_profile=spark_claw
```

Reference: [spark_claw.yaml](pmoves/configs/agent-profiles/spark_claw.yaml), [PMOVES_AI_CONFIG.promptinclude.md](PMOVES_AI_CONFIG.promptinclude.md)

---

## 6. ClaWZ/Typer Compatibility

### ClaWZ (Discord Agent)

ClaWZ uses Claude as its native model, making `claude-sonnet` the only suit with `cross_agent.clawz: full`. Other models are `limited` because ClaWZ's Claude Code architecture expects Anthropic-specific features (extended thinking, XML prompts).

| Suit | ClaWZ Compatibility | Notes |
|------|---------------------|-------|
| `claude-sonnet` | **full** | Native model — XML prompts, extended thinking |
| `glm-5-turbo` | limited | Would need adapter layer for Claude Code API |
| `glm-5.1` | limited | Same adapter requirement |
| `qwen3.6` | limited | Ollama local — ClaWZ would need Ollama bridge |
| `gemma4-dense` | limited | Ollama on Spark — network bridge required |
| `nemotron-3-super` | limited | Same as Gemma4 — Ollama bridge needed |

**NemoClaw consideration:** NVIDIA's NemoClaw framework (reference architecture for DGX Spark) uses Nemotron-3 Super as its default model. If ClaWZ modernizes to a harness pattern (per YouTube Signals §2.3), Nemotron could become a native option.

### Typer Agents

All suits are `untested` for Typer. Typer agents are CLI-focused and likely work with any OpenAI-compatible endpoint, but validation is pending.

---

## 7. Fine-Tuning Pipeline

### Eligible Models

Only models with open weights can be fine-tuned on DGX Spark:

| Model | Weights Available | LoRA Viable | Notes |
|-------|-------------------|-------------|-------|
| Qwen3.6 | ✓ (HuggingFace) | ✓ | Best candidate — small, fast to train |
| Gemma4 Dense | ✓ (Google) | ✓ | Dense architecture makes LoRA more effective than MoE |
| Nemotron-3 Super | ✓ (NVIDIA) | ✓ | KV cache constraint limits batch size |
| GLM-5-turbo | ✗ | ✗ | No open weights |
| GLM-5.1 | ✗ | ✗ | No open weights |
| Claude Sonnet | ✗ | ✗ | Anthropic does not publish weights |

### Pipeline Stages

```text
1. Data Collection
   └── Accumulate trace trajectories from Agent Zero sessions
   └── PMOVESCHIT Cipher Memory stores interaction patterns
   └── Filter for high-quality examples (orbit_stability > 0.6)

2. Data Preparation
   └── Format traces as instruction-response pairs
   └── Apply prompt_style.format from suit profile
   └── Split: 80% train / 10% validation / 10% test

3. LoRA Training (on DGX Spark)
   └── Framework: Unsloth (efficient LoRA for Qwen, Gemma)
   └── Rank: r=16 (default), alpha=32
   └── Target modules: q_proj, v_proj, k_proj, o_proj
   └── Learning rate: 2e-4 with cosine decay
   └── Epochs: 3 (PMOVES-specific data is high-quality, low-quantity)
   └── Batch size: 1-4 (constrained by Nemotron KV cache if applicable)

4. Evaluation
   └── Benchmark against base model on PMOVES task suite
   └── Check for capability regression on general benchmarks
   └── Validate prompt_style compatibility still holds

5. Deployment
   └── Export LoRA adapter weights
   └── Update suit: distillation_stage → full_distillation
   └── Add adapter path to suit's fine_tuning.notes
   └── Publish mesh.gpu.model.loaded.v1 with adapter metadata
```

### Distillation Pipeline Connection

Per [THREE_BODY_DOCTRINE.md §7](pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md), fine-tuning connects to EvoSwarm:

```text
distillation.requested.v1 → EvoSwarm Controller
                        → fitness evaluation against trace trajectories
                        → genome evolution (learning rate, chit weight, etc.)
                        → deployed configuration / model weights
                        → agent.rl.model.deployed.v1
```

---

## 8. Cloud Fallback Strategy

### Fallback Chain

```text
Primary (cloud)           → Fallback (local)         → Last Resort
──────────────────────────────────────────────────────────────────
glm-5-turbo (chat)       → qwen3.6 (utility)         → gemma4-dense (if on Spark)
glm-5.1 (utility)        → qwen3.6 (utility)         → gemma4-dense (if on Spark)
claude-sonnet (coding)    → gemma4-dense (if on Spark)→ qwen3.6 (any device)
```

### Trigger Conditions

1. **Network unreachable**: API endpoint returns connection error
2. **Rate limited**: HTTP 429 from provider
3. **API key missing**: Environment variable not set
4. **Latency threshold**: Response time exceeds 10 seconds
5. **User override**: Manual switch via A0_SET_ variable change

### Implementation

Each suit's `local_fallback.fallback_model_suit` defines the next model in the chain. Agent Zero's runtime should:

1. Attempt primary model (from `A0_SET_*` variable)
2. On failure, read the primary suit's `local_fallback.fallback_model_suit`
3. Load fallback suit's `model_config` as the new endpoint
4. Log fallback event to NATS: `mesh.gpu.fallback.v1`
5. Notify user via `notify_user` tool

---

## 9. Ollama Proven Config

### The Magic Three Numbers

```yaml
num_gpu: 999       # NGL — offload ALL layers to GPU
num_batch: 4096    # Prompt processing batch size
ubatch: 1024       # GPU micro-batch size
```

These values come from the Digital Spaceport benchmark ([YouTube Signals §2.4](research/YOUTUBE_SIGNALS_ANALYSIS.md)) and are proven optimal across Qwen3.6, Gemma4, and other models.

### Rationale

**`NGL=999` (num_gpu: 999):**
- Offloads every transformer layer to GPU
- Eliminates CPU↔GPU memory copies during inference
- On unified memory architectures (DGX Spark), this is essentially free — no VRAM penalty
- On discrete GPUs (3060, 4090), this means the entire model must fit in VRAM
- This is why VRAM math matters — if the model doesn't fit, NGL=999 fails silently or falls back to CPU layers

**`num_batch=4096`:**
- Controls how many tokens are processed in parallel during prompt ingestion
- 4096 is the sweet spot for modern GPU memory bandwidth
- Too low: underutilizes GPU, slower prompt processing
- Too high: exceeds GPU memory, causes OOM or auto-reduction
- Benchmark showed 2,279 tok/s (Qwen3.6 at 8K) and 10,000 tok/s (Gemma4 at 8K) with this setting

**`ubatch=1024`:**
- Micro-batch size for actual GPU compute within the larger batch
- 1024 balances GPU occupancy against memory per-batch
- Works with num_batch=4096 as a 4:1 ratio (4 micro-batches per batch)
- Compatible with both small GPUs (3060) and large GPUs (4090, DGX Spark)

### When NOT to Use These Values

- **CPU-only inference**: Set NGL=0 (no GPU offload)
- **Shared GPU**: Lower num_batch to avoid starving other processes
- **MoE models with VRAM pressure**: MoE variants may need lower NGL (partial offload) — but per benchmark data, dense models are preferred when VRAM allows

---

## 10. Migration from OpenClaw

### The OpenClaw Problem

Per [YouTube Signals §2.1](research/YOUTUBE_SIGNALS_ANALYSIS.md), ClaWZ is **1,092 commits behind upstream** OpenClaw. This is an industry-wide pattern — forks diverge from their parent projects. The PMOVES ecosystem needs an evaluation framework for potential replacements.

### Evaluation Criteria

| Criterion | NemoClaw (NVIDIA) | Hermes Agent (Nouse) | Current ClaWZ |
|-----------|-------------------|----------------------|---------------|
| DGX Spark native | ✓ (reference arch) | ✗ (local-first) | ✗ (Claude Code fork) |
| Default model | Nemotron-3 Super | GLM-5.1 (cloud) | Claude (cloud) |
| Config format | JSON | Home-folder YAML | Claude Code format |
| MCP support | Via Ollama | Built-in (`mcp` extra) | Inherited from Claude Code |
| Skills system | ✗ | ✓ (reusable procedures) | ✗ |
| Multi-agent | ✓ (multiple claws on Spark) | ✗ (single agent) | ✗ |
| PMOVESCHIT integration | Potential (guardrail gap) | Low (no geometry) | Current (ClaWZ-specific) |
| Commit freshness | Active (NVIDIA maintained) | Active (Nouse Research) | 1,092 behind |

### Suit-Relevant Decision Points

1. **If adopting NemoClaw**: `nemotron-3-super` suit becomes first-class. `claude-sonnet` suit demotes to fallback only. Agent profiles need `nemoclaw` variant alongside `spark_claw`.

2. **If adopting Hermes**: `glm-5.1` suit becomes primary (already Hermes' recommended model). `qwen3.6` suit gains importance as Hermes' recommended local fallback. Skills folder pattern maps to PMOVES `skills/` directory.

3. **If staying with ClaWZ**: `claude-sonnet` suit remains primary for Discord. Modernization path is ClaWZ-as-harness (per YouTube Signals §2.3) wrapping Claude Code with PMOVESCHIT scaffolding.

### Recommendation

**Hybrid approach**: Keep ClaWZ for Discord (where Claude is native), evaluate NemoClaw for DGX Spark single-purpose agents (where Nemotron excels), and adopt Hermes patterns (home-folder config, skills system) for the sidecar agent experience. Each path maps cleanly to existing suit profiles — no suit changes needed, only agent profile additions.

---

## Cross-References

| Document | Relevance |
|----------|-----------|
| [THREE_BODY_DOCTRINE.md](pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md) | Distillation pipeline §7, orbital resonance, tabula rasa |
| [00_GLOSSARY.md](pmoves/docs/PMOVESCHIT/00_GLOSSARY.md) | Distillation, CGP, Geometry Bus definitions |
| [AGNOTE_P7_PLAYGROUND.md](pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md) | P7 gates, TAC node status, fleet validation |
| [pinokio-p7.tac.yaml](pmoves/configs/tac_trees/pinokio-p7.tac.yaml) | P7 integration TAC tree, Agent Interpreter tracking |
| [spark_claw.yaml](pmoves/configs/agent-profiles/spark_claw.yaml) | DGX Spark agent profile format reference |
| [YOUTUBE_SIGNALS_ANALYSIS.md](research/YOUTUBE_SIGNALS_ANALYSIS.md) | Benchmark data, model specs, harness patterns |
| [PMOVES_AI_CONFIG.promptinclude.md](PMOVES_AI_CONFIG.promptinclude.md) | Sidecar config, LLM providers, topology modes |
| [AGNOTE4482.md](pmoves/docs/AGENTS/AGNOTE4482.md) | Phi-4482 phase context, submodule sync status |
| Open-Source Model Recommendations (root) | Historical baseline (2025-era) — superseded by this document |

## Suit Files

| File | Provider | Stage | DGX Spark |
|------|----------|-------|-----------|
| [glm-5-turbo.yaml](pmoves/configs/model-suits/glm-5-turbo.yaml) | Z.AI MAX | config_tuning | No (cloud) |
| [glm-5.1.yaml](pmoves/configs/model-suits/glm-5.1.yaml) | Z.AI MAX | config_tuning | No (cloud) |
| [claude-sonnet.yaml](pmoves/configs/model-suits/claude-sonnet.yaml) | OpenRouter | context_priming | No (cloud) |
| [qwen3.6.yaml](pmoves/configs/model-suits/qwen3.6.yaml) | Ollama Local | model_fine_tune | Optional |
| [gemma4-dense.yaml](pmoves/configs/model-suits/gemma4-dense.yaml) | Ollama Spark | model_fine_tune | Primary |
| [nemotron-3-super.yaml](pmoves/configs/model-suits/nemotron-3-super.yaml) | Ollama Spark | model_fine_tune | Specialist |
