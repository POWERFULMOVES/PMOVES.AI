# DGX Spark Model Deployment Strategy — Next-Gen Intelligence Layer

**Classification**: Deployment Planning
**Hardware Target**: NVIDIA DGX Spark (GB10 Grace-Blackwell SoC, 128GB HBM3e)
**Last Updated**: 2026-05-15
**Status**: Planning — models not yet available on Ollama registry

> **Context**: This document covers the **next-generation model deployment strategy** for DGX Spark,
> complementing the existing deployment doc at `pmoves/docs/SPARK_MODEL_STRATEGY.md` which covers
> current P0/P1 models (Qwen3.5-35B, Qwen2.5-Coder-32B). This document plans for GLM-5.1, Qwen3.6,
> Gemma4, and Nemotron-3 as they become available.

---

## 1. Recommended Models

### 1.1 Primary Models for Multi-Model Deployment

| Model | Parameters | Role | Priority | ETA |
|---|---|---|---|---|
| **GLM-5.1** | ~65B | General reasoning, research, complex analysis | P0 | Available |
| **Qwen3.6** | ~72B | Code generation, multilingual, tool use | P0 | Q3 2026 |
| **Gemma4** | ~27B | Fast inference, embedding, classification | P1 | Q3 2026 |
| **Nemotron-3** | ~49B | Instruction following, safety, alignment | P1 | Available |

### 1.2 Model Selection Rationale

- **GLM-5.1**: Best-in-class reasoning for Chinese + English bilingual tasks. Strong on agent orchestration
  and multi-step planning. Currently available via Z.AI cloud; local GGUF pending.
- **Qwen3.6**: Next evolution of Qwen series with improved code generation, function calling, and
  multilingual capabilities. Expected to supersede Qwen3.5 as primary agent brain.
- **Gemma4**: Google's open model with strong safety alignment and efficient inference. Ideal for
  classification tasks, embedding generation, and fast-turnaround queries.
- **Nemotron-3**: NVIDIA's instruction-tuned model with excellent alignment characteristics.
  Recommended for safety-critical paths and user-facing interactions.

---

## 2. Quantization Strategy

### 2.1 Quantization Selection Matrix

| Quantization | Size Impact (65B model) | Quality | Use Case |
|---|---|---|---|
| **Q8_0** | ~65GB | Near-lossless | Quality-critical tasks: reasoning, code review, research |
| **Q4_K_M** | ~38GB | Good (minor degradation) | Multi-model concurrent: chat + code + background tasks |
| **F16** | ~130GB | Lossless | Fine-tuning base, evaluation benchmarks, LoRA training |

### 2.2 Memory Budget Allocation (128GB HBM3e)

#### Single-Model Q8_0 (Quality Mode)
```
┌──────────────────────────────────────────────────┐
│  Model Q8_0 (~65GB)    ████████████████████  65GB │
│  KV Cache (q8_0)       ██████              20GB  │
│  System + OS           ██                  8GB   │
│  Ollama Runtime        █                   4GB   │
│  ────────────────────────────────────────────── │
│  Free                  ████████████        31GB  │
│  TOTAL                                      128GB │
└──────────────────────────────────────────────────┘
```

#### Multi-Model Q4_K_M (Concurrency Mode)
```
┌──────────────────────────────────────────────────┐
│  Primary (Q4_K_M)      ██████████████  38GB      │
│  Coder (Q4_K_M)        ████████████    34GB      │
│  KV Cache (shared)     ████            12GB      │
│  System + OS           ██              8GB       │
│  Ollama Runtime        █               4GB       │
│  ────────────────────────────────────────────── │
│  Free                  ████████        32GB      │
│  TOTAL                                128GB      │
└──────────────────────────────────────────────────┘
```

#### F16 Fine-Tuning Mode
```
┌──────────────────────────────────────────────────┐
│  Model F16             ████████████████████ 130GB │
│  ────────────────────────────────────────────── │
│  ⚠️ OVER BUDGET — requires offloading or        │
│     single-model-only with minimal context       │
│  Recommended: Use Q8_0 base + LoRA adapter      │
└──────────────────────────────────────────────────┘
```

### 2.3 Quantization Decision Tree

```
Is quality critical (code/reasoning)?
├─ YES → Can only run ONE model at a time?
│         ├─ YES → Q8_0 (near-lossless, ~65GB)
│         └─ NO  → Q4_K_M for all (good quality, fits 2 models)
└─ NO  → Q4_K_M (best throughput-per-GB)

Fine-tuning?
├─ YES → Q8_0 base + LoRA adapter (F16 won't fit)
└─ NO  → See above
```

---

## 3. Ollama Configuration

### 3.1 Recommended Runtime Parameters

```bash
# Optimal for DGX Spark 128GB HBM3e
NGL=999                    # Offload all layers to GPU
num_batch=4096             # Maximum batch size for throughput
ubatch=1024                # Micro-batch for scheduling granularity

# KV cache quantization (critical for long-context)
OLLAMA_KV_CACHE_TYPE=q8_0  # Halves KV memory with minimal quality loss

# Flash attention for memory efficiency
OLLAMA_FLASH_ATTENTION=1
```

### 3.2 Per-Model Ollama Modelfile Templates

#### GLM-5.1 Q8_0
```dockerfile
FROM glm-5.1:65b-q8_0
PARAMETER num_gpu 999
PARAMETER num_batch 4096
PARAMETER num_ctx 32768
PARAMETER temperature 0.7
SYSTEM "You are the PMOVES primary reasoning engine."
```

#### Qwen3.6 Q4_K_M
```dockerfile
FROM qwen3.6:72b-q4_K_M
PARAMETER num_gpu 999
PARAMETER num_batch 4096
PARAMETER num_ctx 32768
PARAMETER temperature 0.3
SYSTEM "You are the PMOVES code generation and tool-use specialist."
```

#### Gemma4 Q4_K_M
```dockerfile
FROM gemma4:27b-q4_K_M
PARAMETER num_gpu 999
PARAMETER num_batch 4096
PARAMETER num_ctx 16384
PARAMETER temperature 0.5
SYSTEM "You are the PMOVES classification and fast-inference agent."
```

#### Nemotron-3 Q4_K_M
```dockerfile
FROM nemotron-3:49b-q4_K_M
PARAMETER num_gpu 999
PARAMETER num_batch 4096
PARAMETER num_ctx 16384
PARAMETER temperature 0.4
SYSTEM "You are the PMOVES safety-aligned instruction follower."
```

### 3.3 Deployment Launch Commands

```bash
# Quality mode: single model, maximum quality
OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1 \
  ollama run glm-5.1:65b-q8_0

# Concurrency mode: dual model
OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1 \
  ollama serve &  # background

ollama run qwen3.6:72b-q4_K_M  &  # primary brain
ollama run qwen2.5-coder:32b-q4_K_M  # code specialist
```

---

## 4. Multi-Model Orchestration

### 4.1 Recommended Service Topology

| Service | Model | Quantization | Memory | Port |
|---|---|---|---|---|
| Primary Brain | Qwen3.6 / GLM-5.1 | Q4_K_M / Q8_0 | ~38-65GB | 11434 |
| Code Specialist | Qwen2.5-Coder | Q4_K_M | ~18GB | 11434 |
| Fast Classifier | Gemma4 | Q4_K_M | ~15GB | 11434 |
| Safety Guard | Nemotron-3 | Q4_K_M | ~28GB | 11434 |

> **Note**: Ollama serves all models on a single port (11434). Memory concurrency
> is managed by Ollama's internal scheduler — models are loaded/unloaded based on
> active requests and available VRAM.

### 4.2 TensorZero Routing (Future)

When the TensorZero compose stack is active, route requests through function variants:

```toml
# tensorzero.toml
[functions.spark_reasoning]
type = "chat"

[functions.spark_reasoning.variants.glm51_local]
type = "ollama_chat"
model = "glm-5.1:65b-q8_0"

[functions.spark_reasoning.variants.qwen36_local]
type = "ollama_chat"
model = "qwen3.6:72b-q4_K_M"

[functions.spark_reasoning.variants.glm51_cloud]
type = "http"
url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
```

---

## 5. Performance Expectations

### 5.1 Estimated Throughput (128GB HBM3e, GB10 Blackwell)

| Model | Quantization | Est. tok/s (generate) | Est. tok/s (prompt) | Context Window |
|---|---|---|---|---|
| GLM-5.1 65B | Q8_0 | 8-14 | 50-80 | 32K |
| Qwen3.6 72B | Q4_K_M | 12-20 | 60-100 | 32K |
| Gemma4 27B | Q4_K_M | 25-40 | 100-150 | 16K |
| Nemotron-3 49B | Q4_K_M | 15-25 | 70-110 | 16K |

### 5.2 Context Length vs Memory Trade-off

```
Context: 4K   → KV cache ~1GB per model (Q8_0)
Context: 8K   → KV cache ~2GB per model (Q8_0)
Context: 16K  → KV cache ~4GB per model (Q8_0)
Context: 32K  → KV cache ~8GB per model (Q8_0)
Context: 64K  → KV cache ~16GB per model (Q8_0) ← near limit for multi-model
Context: 128K → KV cache ~32GB per model (Q8_0) ← single-model only
```

**Recommendation**: Default to 32K context. Use 16K for multi-model concurrency.
Use 64K+ only for single-model deep-analysis tasks.

---

## 6. Migration Path from Current Models

### 6.1 Phase Transition

| Phase | Primary Model | Coder Model | Status |
|---|---|---|---|
| **Current** | Qwen3.5-35B-a3b Q4_K_M | Qwen2.5-Coder-32B Q4_K_M | ✅ Active |
| **Phase 2** | GLM-5.1 65B Q8_0 | Qwen2.5-Coder-32B Q4_K_M | 🔄 Pending GGUF |
| **Phase 3** | Qwen3.6 72B Q4_K_M | Qwen3.6-Coder Q4_K_M | 🔜 Q3 2026 |
| **Phase 4** | GLM-5.1 + Qwen3.6 dual | Gemma4 classifier | 🎯 Target |

### 6.2 Rollback Strategy

Each model change is non-destructive — old models remain in Ollama storage.
Rollback is `ollama run <old-model>` away.

---

## 7. Cross-References

| Document | Relation |
|---|---|
| `pmoves/docs/intelligence/SPARK_MODEL_STRATEGY.md` | Current deployment guide (P0/P1 models, GB10 specs, fine-tuning) |
| `pmoves/config/profiles/dgx-spark-grace-blackwell.yaml` | Hardware profile |
| `scripts/spark_deploy_models.sh` | Model deployment automation |
| `pmoves/docs/AGENTS/AGNOTE-dgx-spark.md` | DGX Spark agent note |
| `pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md` | Agent taxonomy with model bindings |
