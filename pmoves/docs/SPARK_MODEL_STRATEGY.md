# SPARK Model Strategy

NVIDIA DGX Spark (GB10 Blackwell) — Model Selection, Fine-Tuning, Routing & Migration

**Date:** 2026-05-08 (updated 2026-07-07)
**Hardware:** NVIDIA DGX Spark — GB10 Blackwell SoC, 128GB LPDDR5X unified memory
**Topology:** TOPOLOGY_MODE=docked, Ollama on host.docker.internal:11434, TensorZero gateway active

---

## 0. Deployed Models (2026-07-07)

| Model | Size | Role | Status |
|---|---|---|---|
| `qwen3.5:35b-a3b-q8_0` | 36GB | Primary reasoning engine | ✅ Deployed |
| `nemotron-3-super:120b` | 80GB | Heavy inference, deep analysis | ✅ Deployed |
| `qwen3:30b-a3b-q4_K_M` | 17GB | Code generation, tool use | ✅ Deployed |
| `hermes3:8b` | 4GB | Fast agent tasks | ✅ Deployed |
| `llama3.2:3b` | 1GB | Lightweight classification | ✅ Deployed |
| `nomic-embed-text` | 0.6GB | Embeddings | ✅ Deployed |
| `qwen2.5-coder:32b` | ~19GB | Code specialist | ✅ Deployed |

---

## 1. Overview — SPARK Hardware Summary

### GB10 Blackwell SoC Specifications

| Parameter | Value |
-----------|-------|
| CUDA Cores | 6,144 |
| Tensor Core Gen | 5th Generation |
| FP32 Compute | 31 TFLOPS |
| NVFP4 Compute | 1,000 TOPS (1 PFLOP) |
| Process Node | TSMC 3nm |
| Memory | 128 GB LPDDR5X-9400 unified |
| Raw Bandwidth | 301 GB/s (600 GB/s aggregate C2X) |
| TDP | 140W (entire SoC) |
| CPU | 20-core Arm v9.2 (10x X925 + 10x A725) |
| Price | $4,699 |

### Topology Position

The DGX Spark serves as PMOVES.AI's local-first inference node in standalone sidecar mode.
The sidecar container (Agent Zero) accesses Ollama on the host via `host.docker.internal:11434`.
TensorZero routing profile enables hybrid local+cloud fallback chains.
The researcher agent profile uses GLM-5-turbo via Z.AI for tasks requiring cloud-scale reasoning.

```
Sidecar Container (Agent Zero)
    |
    +-- Ollama (host.docker.internal:11434) -- Local GGUF inference
    +-- TensorZero Gateway (when compose up) -- Routing + observability
    +-- Z.AI GLM-5-turbo (researcher profile) -- Cloud fallback
```

### Bandwidth Reality Check

301 GB/s feeding 6,144 CUDA cores = 51 GB/s per 1024 cores — severely memory-bound.
For 70B Q4_K_M at ~40GB: full prefill = 40GB / 301GB/s = **133ms** theoretical minimum.
Multi-model serving amortizes bandwidth across concurrent requests.
KV cache quantization (q8_0) is critical for long-context workloads on GB10.

### Strength vs Weakness

- **Strength:** 128GB unified memory enables models up to ~100GB quantized.
  70B Q4_K_M at ~40GB means 3+ models concurrently in memory.
  No other desktop device offers this capacity at $4,699.
- **Weakness:** 301 GB/s is 6x lower than RTX 5090 GDDR7 (1,792 GB/s).
  Prefill latency dominates for large models. Batch-1 throughput wins;
  high-concurrency serving should use vLLM with careful gpu-memory-utilization.

### Source

Full hardware analysis: `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` (Search 1)

---

## 2. Model Selection Matrix

### Primary Models for GB10

| Model | Params | Quant | Size on Disk | Use Case | Est. GB10 Perf | Priority |
-------|--------|-------|-------------|----------|----------------|----------|
| Qwen3.5-35B-A3B | 35B (MoE, 3B active) | Q4_K_M | ~20GB | Agent Zero brain, coding, reasoning | 15-25 tok/s | P0 |
| Qwen2.5-Coder-32B | 32B | Q4_K_M | ~18GB | MCP forms, tool routing, code gen | 12-20 tok/s | P0 |
| Llama 3.3-70B | 70B | Q4_K_M | ~40GB | Quality-critical orchestration | 8-15 tok/s | P1 |
| Qwen2.5-32B | 32B | Q8_0 | ~32GB | Near-lossless quality tasks | 10-18 tok/s | P1 |
| Llama 4 Scout | 17B (MoE) | Q4_K_M | ~10GB | Fast general tasks, latest arch | 20-35 tok/s | P1 |
| Qwen2.5-7B | 7B | Q4_K_M | ~4.1GB | LangExtract, edge fallback | 40-60 tok/s | P2 |
| Qwen3-30B-A3B | 30B (MoE, 3B active) | Q4_K_M | ~17.5GB | MoE efficiency benchmark | 20-30 tok/s | P2 |
| Phi-3-Mini 3.8B | 3.8B | Q4_K_M | ~2.5GB | Autonomy loop, Jetson parity | 60-80 tok/s | P2 |

### Embedding & RAG Models

| Model | Params | Format | Use Case | Source |
-------|--------|--------|----------|--------|
| Qwen3-Embedding 4B | 4B | GGUF | Primary embeddings (Archon/Hi-RAG) | Ollama `qwen3-embedding:4b` |
| nomic-embed-text | 137M | GGUF | Fast semantic search | Ollama `nomic-embed-text` |
| BGE-Large (Gemma2) | 1.5B | FP16 | High-quality retrieval | HF `BAAI/bge-large-en-v1.5` |

### Multi-Model Memory Budget (128GB)

| Configuration | Models Loaded | Total RAM | Headroom |
|--------------|---------------|-----------|----------|
| Lean | Qwen3.5-35B-A3B (20GB) + Qwen2.5-7B (4GB) + embedders (5GB) | ~29GB | 99GB free |
| Standard | + Qwen2.5-Coder-32B (18GB) | ~47GB | 81GB free |
| Full | + Llama 3.3-70B (40GB) | ~87GB | 41GB free |

> Models are memory-mapped from disk by Ollama/llama.cpp — not all loaded at once.
> Only actively serving models consume full RAM. See Ollama `OLLAMA_MAX_LOADED_MODELS`.

### Cross-Reference

Per-service model rationale: `../../Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md`
Agent registry structure: `../config/agent_registry.yaml` (agent_zero topology.node_affinity)

---

## 3. Unsloth Local Fine-Tuning Path

### GB10 Native Support

Unsloth explicitly supports GB10-based developer workstations (NVIDIA blog confirmation).
Primary optimization leverages NVFP4 (Blackwell-specific, 1000 TOPS on GB10).
QLoRA 4-bit on all linear layers with 70% VRAM reduction vs HuggingFace + Flash Attention 2.

### Feasibility on 128GB Unified Memory

| Model | QLoRA VRAM Est. | Fits GB10? | Context (est.) |
-------|----------------|------------|----------------|
| Qwen2.5-7B | ~8GB | Yes (trivially) | 100K+ tokens |
| Qwen2.5-32B | ~18GB | Yes (comfortable) | 60K+ tokens |
| Qwen3.5-35B-A3B (MoE) | ~15GB | Yes (comfortable) | 80K+ tokens |
| Llama 3.3-70B | ~35-40GB | Yes (fits with headroom) | 30K+ tokens |
| Llama 4 Scout 17B | ~12GB | Yes | 80K+ tokens |

### Training Arguments (GB10-Optimized)

```python
from unsloth import FastLanguageModel
from unsloth import is_bfloat16_supported
from transformers import TrainingArguments

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3.5-35B-A3B",
    max_seq_length=4096,       # Scale up with available VRAM
    dtype=None,                 # Auto-detect (BF16 on Blackwell)
    load_in_4bit=True,          # QLoRA 4-bit quantization
)

model = FastLanguageModel.get_peft_model(
    model,
    r=32,                       # LoRA rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

training_args = TrainingArguments(
    output_dir="./outputs_spark_qlora",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    max_steps=200,
    learning_rate=2e-4,
    warmup_steps=20,
    lr_scheduler_type="linear",
    fp16=not is_bfloat16_supported(),
    bf16=is_bfloat16_supported(),   # BF16 preferred on Blackwell GB10
    optim="adamw_8bit",
    weight_decay=0.01,
    logging_steps=10,
    seed=3407,
    save_strategy="steps",
    save_steps=50,
)
```

### Export to Ollama GGUF Pipeline

```bash
# 1. Save LoRA adapter
# (in Python after training)
model.save_pretrained_merged("./qwen35_spark_merged", tokenizer)

# 2. Export to GGUF via Unsloth
model.save_pretrained_gguf(
    "qwen35_spark_merged",
    quantization_method="q4_k_m",
)

# 3. Load into Ollama
cat > Modelfile.spark << 'EOF'
FROM ./qwen35_spark_merged/q4_k_m.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
EOF

ollama create qwen35-spark-ft -f Modelfile.spark
```

### Integration with Agent Registry

Fine-tuned models register in `pmoves/config/agent_registry.yaml` under the target agent's
topology section. The agent_zero entry already supports `node_affinity: [kvm4-1, z890, 5090]` —
add `spark` to enable GB10-specific routing:

```yaml
# In agent_registry.yaml, under agents.agent_zero.topology
node_affinity: [kvm4-1, z890, 5090, spark]
```

### Existing TensorZero Recipe Reference

The PMOVES TensorZero repo includes an Unsloth SFT recipe at:
`../../PMOVES-tensorzero/recipes/supervised_fine_tuning/unsloth/unsloth.ipynb`

This recipe demonstrates the full fine-tune-to-TensorZero-evaluation pipeline.
Adapt it for GB10 by setting `dtype=None` (auto BF16) and increasing `max_seq_length`
to exploit the 128GB memory headroom.

### Source

Unsloth Blackwell details: `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` (Search 2)

---

## 4. TensorZero Routing Strategy

### Architecture: Ollama Local + Z.AI Cloud Fallback

```
PMOVES Service
    |
    v
TensorZero Gateway (port 3030)
    |
    +--[routing order]--> Ollama (host.docker.internal:11434/v1)
    |                        |
    |                        +-- qwen3.5:35b-a3b     (Agent Zero brain)
    |                        +-- qwen2.5-coder:32b   (MCP/tool routing)
    |                        +-- llama3.3:70b        (Quality ceiling)
    |
    +--[fallback]-------> Z.AI GLM-5-turbo (researcher profile)
    |
    +--[observability]--> ClickHouse (port 8123)
```

### tensorzero.toml Configuration

```toml
# === Local Ollama Models ===

[models.spark_brain]
routing = ["ollama_local"]

[models.spark_brain.providers.ollama_local]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "qwen3.5:35b-a3b"
api_key_location = "none"
timeout_ms = 30000

[models.spark_coder]
routing = ["ollama_local"]

[models.spark_coder.providers.ollama_local]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "qwen2.5-coder:32b"
api_key_location = "none"
timeout_ms = 30000

[models.spark_quality]
routing = ["ollama_local"]

[models.spark_quality.providers.ollama_local]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "llama3.3:70b"
api_key_location = "none"
timeout_ms = 60000

# === Hybrid: Local Primary + Cloud Fallback ===

[models.spark_hybrid]
routing = ["ollama_local", "zai_cloud"]

[models.spark_hybrid.providers.ollama_local]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "qwen3.5:35b-a3b"
api_key_location = "none"
timeout_ms = 15000

[models.spark_hybrid.providers.zai_cloud]
type = "openai"
model_name = "glm-5-turbo"
api_key_location = "env::ZAI_API_KEY"
timeouts = { non_streaming.total_ms = 30000, streaming.ttft_ms = 5000 }

# === Research Profile (Cloud-First) ===

[models.spark_researcher]
routing = ["zai_cloud"]

[models.spark_researcher.providers.zai_cloud]
type = "openai"
model_name = "glm-5-turbo"
api_key_location = "env::ZAI_API_KEY"
```

### Function Variants with Retry

```toml
[functions.agent_zero_chat]
type = "chat"

[functions.agent_zero_chat.variants.local_primary]
type = "chat_completion"
model = "spark_hybrid"
retries = { num_retries = 2, max_delay_s = 10 }
timeouts = { non_streaming.total_ms = 30000, streaming.ttft_ms = 5000, streaming.total_ms = 120000 }

[functions.agent_zero_chat.variants.cloud_fallback]
type = "chat_completion"
model = "spark_researcher"
weight = 0.1  # 10% traffic for A/B comparison

[functions.mcp_tool_routing]
type = "chat"

[functions.mcp_tool_routing.variants.coder_local]
type = "chat_completion"
model = "spark_coder"
timeouts = { non_streaming.total_ms = 15000 }

[functions.deep_research]
type = "chat"

[functions.deep_research.variants.researcher_cloud]
type = "chat_completion"
model = "spark_researcher"
```

### Metrics

```toml
[metrics.task_success]
type = "boolean"
optimize = "max"
level = "episode"

[metrics.latency_p95]
type = "float"
optimize = "min"
level = "episode"

[metrics.local_hit_rate]
type = "float"
optimize = "max"
level = "episode"
```

### Routing Limitations

- Latency-based routing: not natively supported — use provider order + timeouts.
- Cost optimization: TensorZero tracks cost but routing is provider-order-based.
- Weighted A/B: not explicitly configurable — defaults to uniform random.
- Circuit breaker: implement via timeout_ms on Ollama provider;
  when Ollama fails, TensorZero falls through to next provider in routing list.

### Source

TensorZero Ollama patterns: `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` (Search 3)
Existing TensorZero config: `../tensorzero/config/tensorzero.toml`

---

## 5. HuggingFace + Pinokio Integration

### Reference Pattern: PMOVES-Pinokio-Ultimate-TTS-Studio

The existing TTS Studio Pinokio integration (`../../PMOVES-Pinokio-Ultimate-TTS-Studio/`)
demonstrates the one-click install pattern:

```
PMOVES-Pinokio-Ultimate-TTS-Studio/
    pinokio_meta.json    # Metadata (name, icon, requirements)
    install.js           # git clone, conda env, hf download, OS deps
    start.js             # Launch Gradio UI
    stop.js              # Shutdown
    update.js            # Pull latest
    reset.js             # Clean slate
```

### Pinokio Script for GB10 Model Distribution

**pinokio_meta.json:**

```json
{
  "name": "PMOVES Spark Models",
  "description": "One-click install of PMOVES-optimized GGUF models for NVIDIA DGX Spark",
  "icon": "https://raw.githubusercontent.com/POWERFULMOVES/PMOVES.AI/main/assets/spark-icon.png",
  "requires": {
    "bundle": "ai"
  }
}
```

**install.js (key excerpt):**

```javascript
module.exports = {
  requires: { bundle: "ai" },
  run: [
    // Ollama installation (if not present)
    {
      method: "shell.run",
      params: {
        message: "curl -fsSL https://ollama.com/install.sh | sh",
      }
    },
    // Primary brain model
    {
      method: "shell.run",
      params: {
        message: "ollama pull qwen3.5:35b-a3b",
      }
    },
    // Coding specialist
    {
      method: "shell.run",
      params: {
        message: "ollama pull qwen2.5-coder:32b",
      }
    },
    // Quality ceiling
    {
      method: "shell.run",
      params: {
        message: "ollama pull llama3.3:70b",
      }
    },
    // Custom fine-tuned model from HuggingFace
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "hf download POWERFULMOVES/qwen35-spark-ft --local-dir ./models/qwen35-spark-ft",
      }
    },
    // Register custom model with Ollama
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "ollama create qwen35-spark-ft -f ./models/qwen35-spark-ft/Modelfile",
      }
    },
    // Embedding model
    {
      method: "shell.run",
      params: {
        message: "ollama pull qwen3-embedding:4b",
      }
    },
    // Verify all models
    {
      method: "shell.run",
      params: {
        message: "ollama list",
      }
    },
  ]
};
```

### HuggingFace Repo Structure

```
POWERFULMOVES/qwen35-spark-ft/
    q4_k_m.gguf              # Quantized weights
    Modelfile                 # Ollama descriptor
    adapter_config.json       # LoRA config (source reference)
    README.md                 # Training details, benchmarks
```

### One-Click Install Flow

1. User installs Pinokio browser
2. User clicks Pinokio script URL from PMOVES docs
3. Pinokio reads `pinokio_meta.json`, checks `requires.bundle`
4. Executes `install.js`: Ollama install -> model pulls -> HF custom model download
5. User clicks "Start" -> launches Ollama serve with GB10-optimized flags
6. Sidecar container connects via `host.docker.internal:11434`

### Source

Pinokio patterns: `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` (Search 4)
TTS Studio reference: `../../PMOVES-Pinokio-Ultimate-TTS-Studio/`

---

## 6. Ollama Pull Strategy

### Recommended Models for GB10

#### Tier 1: Must-Have (Pull Immediately)

```bash
# Fast smoke test — smallest, validates Ollama + GPU offload
ollama pull qwen2.5:7b

# Primary agent brain — MoE efficiency, 3B active params
ollama pull qwen3.5:35b-a3b

# Coding specialist — 92.7% HumanEval on Qwen2.5-Coder
ollama pull qwen2.5-coder:32b
```

#### Tier 2: High Value (Pull After Validation)

```bash
# Quality ceiling — 86.0 MMLU, best overall open model
ollama pull llama3.3:70b

# Latest architecture — Llama 4 Scout MoE
ollama pull llama4:scout-q4_k_m

# Embedding model — Archon/Hi-RAG primary
ollama pull qwen3-embedding:4b
```

#### Tier 3: Extended (Pull as Needed)

```bash
# Near-lossless 32B — Q8_0 for quality-critical tasks
ollama pull qwen2.5:32b

# MoE benchmark — compare against Qwen3.5 MoE
ollama pull qwen3:30b-a3b

# Fast semantic search fallback
ollama pull nomic-embed-text

# Edge parity — same model on Jetson for testing
ollama pull phi3:3.8b-mini-128k-instruct
```

### Quantization Choices for GB10

| Scenario | Format | Rationale |
----------|--------|-----------|
| MoE models (3B active) | Q4_K_M | Active params only ~3B, 4-bit negligible loss |
| 32B models (coding, general) | Q4_K_M | 1-2% task delta vs F16, half the RAM |
| 32B quality-critical | Q8_0 | Near-lossless, 32GB fits easily in 128GB |
| 70B models | Q4_K_M | 40GB each, only format that allows 2+ concurrent |
| Fine-tuning base | F16 | Unsloth handles quant internally via QLoRA |

### Ollama Serve with GB10 Optimizations

```bash
# KV cache quantization — critical for long contexts on 301 GB/s bandwidth
OLLAMA_KV_CACHE_TYPE=q8_0 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_MAX_LOADED_MODELS=3 \
OLLAMA_NUM_PARALLEL=4 \
ollama serve
```

### Custom Quantization from HuggingFace

```bash
# Download FP16 base from HuggingFace
hf download Qwen/Qwen3.5-35B-A3B --local-dir ./models/qwen35-fp16

# Create Modelfile
cat > Modelfile.qwen35 << 'EOF'
FROM ./models/qwen35-fp16
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
EOF

# Generate quantized variants
ollama create qwen35-fp16 -f Modelfile.qwen35
ollama create --quantize q8_0 qwen35-q8_0 -f Modelfile.qwen35
ollama create --quantize q5_k_m qwen35-q5_k_m -f Modelfile.qwen35
ollama create --quantize q4_k_m qwen35-q4_k_m -f Modelfile.qwen35
```

### Unsloth GGUF -> Ollama Direct Load

```bash
# For Unsloth-exported GGUF (e.g., fine-tuned models)
llama-server \
  -hf unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M \
  --host 0.0.0.0 \
  -t 10 \
  -ngl 99 \
  --temp 0.6 \
  --min-p 0.0 \
  --top-p 0.95 \
  --jinja \
  --flash-attn on \
  --no-mmap \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -c 64000
```

### Bring-Up Order (Validated Sequence)

1. `ollama pull qwen2.5:7b` — smoke test, ~4.1GB, fastest download
2. `ollama run qwen2.5:7b "Hello"` — verify GPU offload works
3. `ollama pull qwen3.5:35b-a3b` — primary brain, ~20GB
4. `ollama pull qwen2.5-coder:32b` — coding specialist, ~18GB
5. `ollama pull qwen3-embedding:4b` — embeddings for Archon
6. `ollama pull llama3.3:70b` — quality ceiling, ~40GB
7. `ollama pull llama4:scout-q4_k_m` — latest arch test, ~10GB

Total Tier 1+2 storage: ~95GB (fits on typical Spark NVMe with room for custom models)

### Source

Ollama strategy: `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` (Search 5)

---

## 7. API-to-Local Migration — Fireworks to Ollama

### Current State

Existing TensorZero recipes target Fireworks API via `firectl`:
`../../PMOVES-tensorzero/recipes/supervised_fine_tuning/fireworks/fireworks.ipynb`

The Fireworks recipe demonstrates SFT with cloud-hosted models.
Migration replaces the Fireworks provider with local Ollama backends.

### Migration Map

| Aspect | Fireworks (Current) | Ollama Local (Target) |
--------|--------------------|-----------------------|
| API endpoint | `https://api.fireworks.ai/inference/v1` | `http://host.docker.internal:11434/v1` |
| Auth | `FIREWORKS_API_KEY` env var | `api_key_location = "none"` |
| Model format | Cloud-hosted, named by slug | Local GGUF, named by Ollama tag |
| Latency | 200-800ms TTFT (network) | 50-200ms TTFT (local) |
| Cost | $0.20-$0.60/1M tokens | $0 (electricity only) |
| Privacy | Data leaves machine | Fully local |
| Rate limits | Fireworks tier-dependent | None (hardware-bound) |

### TensorZero Config Migration

**Before (Fireworks):**

```toml

[models.fireworks_llama]
routing = ["fireworks"]

[models.fireworks_llama.providers.fireworks]
type = "openai"
api_base = "https://api.fireworks.ai/inference/v1"
model_name = "accounts/fireworks/models/llama-v3p1-70b-instruct"
api_key_location = "env::FIREWORKS_API_KEY"
```

**After (Ollama Local):**

```toml
[models.spark_llama70b]
routing = ["ollama_local"]

[models.spark_llama70b.providers.ollama_local]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "llama3.3:70b"
api_key_location = "none"
timeout_ms = 60000
```

### SFT Recipe Migration

The Fireworks SFT recipe (`fireworks.ipynb`) uses the Fireworks API for
dataset generation and model evaluation. Migration path:

1. **Dataset generation:** Replace Fireworks API calls with local Ollama calls.
   Use the same prompt templates but point to `host.docker.internal:11434/v1`.

2. **Fine-tuning:** Switch to Unsloth recipe (already exists at
   `../../PMOVES-tensorzero/recipes/supervised_fine_tuning/unsloth/unsloth.ipynb`).
   Unsloth runs entirely locally on GB10 — no API needed.

3. **Evaluation:** Use TensorZero evaluation framework with local Ollama models.
   Configure eval variants to use `spark_brain` and `spark_coder` model definitions.

4. **Deployment:** Export Unsloth output to GGUF, load into Ollama,
   update TensorZero config to point to the new local model tag.

### DPO Recipe Migration

The DPO recipe at `../../PMOVES-tensorzero/recipes/dpo/openai/openai_dpo.ipynb`
uses OpenAI API for preference pair generation. On GB10:

1. Generate preference pairs using local Qwen3.5-35B-A3B (Ollama)
2. Run DPO training via Unsloth (local, GPU-accelerated on GB10)
3. Export to GGUF and register with Ollama

### Environment Variable Changes

```bash
# Remove (no longer needed)
unset FIREWORKS_API_KEY

# Add (if using TensorZero observability)
export TENSORZERO_BASE_URL=http://host.docker.internal:3030
export TENSORZERO_EMBED_MODEL=tensorzero::embedding_model_name::qwen3_embedding_4b_local

# Ollama optimization (add to sidecar.env)
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_FLASH_ATTENTION=1
OLLAMA_MAX_LOADED_MODELS=3
```

### Rollback Strategy

Keep the Fireworks provider config commented out in tensorzero.toml.
If a local model underperforms for a specific function, swap the routing
order to try Fireworks first, then fall back to Ollama:

```toml
# Rollback: cloud-first for specific function
[functions.agent_zero_chat.variants.rollback_hybrid]
type = "chat_completion"
model = "spark_rollback"  # routing = ["fireworks", "ollama_local"]
```

### Validation Checklist

- [ ] Ollama serving on host.docker.internal:11434 from sidecar container
- [ ] `ollama list` shows all Tier 1 models loaded
- [ ] TensorZero gateway starts with Ollama provider config
- [ ] Agent Zero chat produces responses via local model
- [ ] Researcher profile still routes to Z.AI GLM-5-turbo
- [ ] Embeddings return vectors via `qwen3-embedding:4b`
- [ ] Latency P95 < 5s for 70B Q4_K_M single-turn
- [ ] Memory usage < 100GB with 3 models loaded
- [ ] Circuit breaker: Ollama timeout triggers Z.AI fallback

---

## Appendix: Quick Reference Commands

```bash
# Full bring-up sequence
ollama pull qwen2.5:7b && \
ollama pull qwen3.5:35b-a3b && \
ollama pull qwen2.5-coder:32b && \
ollama pull qwen3-embedding:4b && \
ollama pull llama3.3:70b && \
ollama pull llama4:scout-q4_k_m && \
ollama list

# Optimized serve
OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_MAX_LOADED_MODELS=3 ollama serve &

# Verify GPU offload
ollama show qwen3.5:35b-a3b --verbose

# Test from sidecar container
curl -s http://host.docker.internal:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5:35b-a3b","messages":[{"role":"user","content":"ping"}],"max_tokens":10}'

# Fine-tune with Unsloth (on GB10 host, not in container)
pip install unsloth
python train_spark.py  # Using training args from Section 3

# Export fine-tuned model to Ollama
ollama create qwen35-spark-ft -f Modelfile.spark
```

---

*Cross-referenced files:*
- `../../research/GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md`
- `../../Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md`
- `../config/agent_registry.yaml`
- `../../PMOVES-tensorzero/recipes/supervised_fine_tuning/unsloth/unsloth.ipynb`
- `../../PMOVES-tensorzero/recipes/supervised_fine_tuning/fireworks/fireworks.ipynb`
- `../../PMOVES-tensorzero/recipes/dpo/openai/openai_dpo.ipynb`
- `../../PMOVES-Pinokio-Ultimate-TTS-Studio/`
- `../tensorzero/config/tensorzero.toml`