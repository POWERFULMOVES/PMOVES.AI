# GB10 + LLM Inference Research: 5-Search Structured Report
**Date:** 2026-05-08

---

## SEARCH 1: NVIDIA GB10 Blackwell SoC Specifications

### Core Compute
| Parameter | Value |
-----------|-------|
| CUDA Cores | **6,144** |
| Tensor Core Gen | **5th Generation** (exact count not publicly disclosed) |
| FP32 Compute | **31 TFLOPS** |
| NVFP4 (FP4) Compute | **1,000 TOPS** (1 PFLOP) |
| RT Cores | Yes (RTX Ray Tracing cores, DLSS 4 support) |
| Process Node | **TSMC 3nm** |
| Package | 2.5D multi-die (Mediatek Arm CPU + Blackwell GPU over interposer, C2C interconnect) |

### Memory Subsystem
| Parameter | Value |
-----------|-------|
| Memory Type | **LPDDR5X-9400** (mobile-class DRAM) |
| Memory Capacity | **128 GB unified** (confirmed) |
| Interface Width | 256-bit |
| Raw Bandwidth | **301 GB/s** (at 9400 MT/s) |
| Aggregate C2X Bandwidth | **600 GB/s** (GPU access via C2X interface) |
| Memory Model | Unified — GPU accesses LPDDR5X coherently and transparently |

### Power & Thermal
| Parameter | Value |
-----------|-------|
| TDP | **140W** (entire chip, CPU+GPU) |
| Power Efficiency | NVFP4 tuned for competitive inference efficiency vs Hopper (per arXiv 2507.10789) |

### Supported Precision Formats
| Format | Status |
--------|--------|
| NVFP4 (FP4) | **Confirmed** — 1000 TOPS |
| FP32 | **Confirmed** — 31 TFLOPS |
| FP16 | Implicitly supported (CUDA standard) but not explicitly benchmarked in GB10 literature |
| FP8 | Implicitly supported (Blackwell architecture feature) but not explicitly benchmarked for GB10 |
| INT8 | Implicitly supported (Tensor Core native) |
| INT4 | Implicitly supported (Tensor Core native) |

### CPU Complex
| Parameter | Value |
-----------|-------|
| Architecture | Arm v9.2 |
| Core Count | **20 cores** (2 clusters of 10) |
| Performance Cluster | 10x Arm Cortex-X925 |
| Efficiency Cluster | 10x Arm Cortex-A725 |
| CPU Die Source | MediaTek (co-developed with NVIDIA) |

### Comparison to Other NVIDIA Platforms
| Metric | GB10 | RTX 5090 | GH200 Grace Hopper | GB200 NVL72 |
---------|------|-----------|-------------------|-------------|
| Memory | 128GB LPDDR5X | 32GB GDDR7 | 96/144GB HBM3e | 192GB HBM3e per GPU |
| Bandwidth | 301 GB/s | 1,792 GB/s | 4.0/4.5 TB/s | 8.0 TB/s per GPU |
| TDP | 140W | 575W | 700-1000W | N/A (rack-scale) |
| Form Factor | Desktop/Mini | Desktop | Server | Rack (36 GPUs) |
| Package | 2.5D unified SoC | Discrete | 2-chip (CPU+GPU) | 2-chip per GPU |
| NVFP4 | Yes | No (FP8 max) | No | Yes |

### Inference Workload Assessment
- **Strength**: 128GB unified memory enables running models up to ~100GB quantized (70B Q4_K_M at ~40GB, multiple models concurrently)
- **Weakness**: 301 GB/s bandwidth is 6x lower than RTX 5090 GDDR7 and 13x lower than GH200 HBM3e — memory-bound inference (prefill) will be bottlenecked
- **Sweet Spot**: Batch-1 inference for large models that don't fit in consumer GPU VRAM; MoE models with sparse activation; multi-model serving where total model weight exceeds single-GPU VRAM but fits in 128GB
- **Source**: TechPowerUp Hot Chips 2025 coverage, Wccftech, ChipLog analysis, globalnerdy.com HP ZGX Nano specs

---

## SEARCH 2: Unsloth Fine-Tuning Capabilities (2025-2026)

### Blackwell/GB10 Native Support
| Aspect | Detail |
--------|--------|
| Blackwell Optimization | **Yes — confirmed** | 
| GB10/DGX Spark Specifically | **Yes — NVIDIA blog explicitly names "GB10-based developer workstations (such as NVIDIA DGX Spark)" |
| Supported Blackwell GPUs | RTX 50 Series, RTX PRO 6000 Blackwell, HGX B200, GB200 NVL72, **GB10 (DGX Spark)** |
| Primary Precision | **NVFP4** (Blackwell-specific optimization) |
| Secondary Precision | QLoRA 4-bit on all linear layers |

### Performance Claims (Blackwell-specific)
| Metric | Value |
--------|-------|
| Training Speed | **2x faster** than baseline |
| VRAM Reduction | **70% less** than HuggingFace + Flash Attention 2 |
| Context Window | **12x longer** than FA2 baseline |
| Max Fine-Tunable Size | **Up to 40B parameters on single Blackwell GPU** |
| 70B+ Models | VRAM reduction applies but requires multi-GPU or 128GB+ unified memory |

### Context Length Benchmarks (RTX 5090 32GB, Alpaca, bs=2, ga=4, rank=32)
| VRAM | Unsloth Context | HF+FA2 Context | Improvement |
|------|----------------|----------------|-------------|
| 8GB | 2,972 tokens | OOM | Infinite |
| 12GB | 21,848 tokens | 932 tokens | 23.4x |
| 16GB | 40,724 tokens | 2,551 tokens | 16.0x |
| 24GB | 78,475 tokens | 5,789 tokens | 13.6x |
| 32GB | 122,181 tokens | 9,711 tokens | 12.6x |

### GB10 Fine-Tuning Implications (128GB Unified)
- With 128GB and 70% VRAM reduction, QLoRA fine-tuning of **70B+ models becomes feasible on single GB10**
- Estimated: Llama-3.1-70B QLoRA needs ~35-40GB for weights + optimizer states = fits comfortably
- 40B models at 4-bit QLoRA: ~20-25GB weights + overhead = very comfortable
- Context length at 128GB: potentially 300K+ tokens (extrapolating from 32GB→122K curve)

### Supported Model Families
| Family | Models | Notes |
--------|--------|-------|
| Llama | 3.1, 3.3, 4 (Scout, Maverick) | Full SFT + RL support |
| Qwen | 2.5, 3, 3.5, 3.6 | Including MoE variants (30B-A3B, 235B-A22B) |
| DeepSeek | V3, R1 | Full support |
| gpt-oss | Multiple sizes | Listed as supported |

### Qwen3.5 Fine-Tuning Specifics (from Unsloth docs)
- Supported sizes: **0.8B, 2B, 4B, 9B, 27B, 35B-A3B, 122B-A10B**
- Includes vision, text, and RL fine-tuning
- Qwen3.5-35B-A3B (MoE): active params only ~35B, fits in 128GB easily

### Qwen3 MoE Fine-Tuning Notes
- Qwen3-30B-A3B: **17.5GB VRAM** for inference with Unsloth
- Router layer fine-tuning **disabled by default** (not recommended for MoE)
- 2026 "Faster MOE update" applied

### Ollama GGUF Integration
- Unsloth publishes **Dynamic GGUF** variants on HuggingFace (unsloth org)
- GGUF + 4-bit and 16-bit instruct variants available
- GGUF models can be loaded into Ollama via `ollama create` with Modelfile
- No native "fine-tune directly on Ollama GGUF" — workflow is: Unsloth fine-tunes → export to GGUF → load into Ollama

### Llama 3.1 Fine-Tuning Example (QLoRA params)
```python
from unsloth import is_bfloat16_supported
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./outputs_qlora",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    max_steps=60,
    learning_rate=2e-4,
    warmup_steps=10,
    lr_scheduler_type="linear",
    fp16=not is_bfloat16_supported(),
    bf16=is_bfloat16_supported(),
    optim="adamw_8bit",
    weight_decay=0.01,
    logging_steps=10,
    seed=3407,
)
```

---

## SEARCH 3: TensorZero Routing with Local Ollama Backends

### Ollama Provider Configuration (tensorzero.toml)
```toml
[models.llama3_3_70b_instruct]
routing = ["ollama"]

[models.llama3_3_70b_instruct.providers.ollama]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "llama3.1"
api_key_location = "none"
```

### Fallback Chain (Ollama → Cloud)
```toml
[models.hybrid_model]
routing = ["ollama", "openai-cloud"]

[models.hybrid_model.providers.ollama]
type = "openai"
api_base = "http://host.docker.internal:11434/v1"
model_name = "qwen2.5:32b"
api_key_location = "none"

[models.hybrid_model.providers.openai-cloud]
type = "openai"
model_name = "gpt-4o-mini"
api_key_location = "env::OPENAI_API_KEY"
```

### Retry Configuration (Exponential Backoff with Jitter)
```toml
[functions.my_function.variants.my_variant]
type = "chat_completion"
model = "hybrid_model"
retries = { num_retries = 3, max_delay_s = 10 }
```

### Timeout Configuration (Multi-Level)
```toml
# Variant level
[functions.my_function.variants.my_variant]
timeouts = { non_streaming.total_ms = 15000, streaming.ttft_ms = 3000, streaming.total_ms = 60000 }

# Provider level (simple)
[models.hybrid_model.providers.ollama]
timeout_ms = 3000

# Provider level (granular)
[models.hybrid_model.providers.openai-cloud]
timeouts = { non_streaming.total_ms = 15000, streaming.ttft_ms = 3000, streaming.total_ms = 60000 }

# Global level
[gateway]
global_outbound_http_timeout_ms = 900000  # 15 min default
```

### A/B Testing Configuration
```toml
[functions.my_function]
type = "chat"

[functions.my_function.experimentation]
# Default: uniform random sampling across variants

[functions.my_function.variants.local_variant]
type = "chat_completion"
model = "ollama-qwen"

[functions.my_function.variants.cloud_variant]
type = "chat_completion"
model = "gpt-4o-mini"
```

### Metrics for Optimization
```toml
[metrics.task_success]
type = "boolean"
optimize = "max"
level = "episode"

[metrics.latency_p95]
type = "float"
optimize = "min"
level = "episode"
```

### Routing Limitations Found
- **Latency-based routing**: Not natively supported in TOML config — would require custom variant selection logic
- **Cost optimization**: No built-in cost-aware routing in config — TensorZero tracks cost but routing is provider-order-based
- **Weighted A/B**: Not explicitly configurable — defaults to uniform random
- **Supported providers**: Anthropic, AWS Bedrock/SageMaker, Azure, DeepSeek, Fireworks, GCP Vertex, Google AI Studio, Groq, Hyperbolic, Mistral, OpenAI, OpenRouter, SGLang, TGI, Together AI, vLLM, xAI, **Ollama (via openai-compatible)**

### Production Deployment (from PMOVES-tensorzero example)
```toml
[models."gpt-4o-mini-2024-07-18"]
routing = ["openai"]

[models."gpt-4o-mini-2024-07-18".providers.openai]
type = "openai"
model_name = "gpt-4o-mini-2024-07-18"

[functions.simple_llm_call]
type = "chat"

[functions.simple_llm_call.variants.baseline]
type = "chat_completion"
model = "gpt-4o-mini-2024-07-18"

[metrics.task_success]
type = "boolean"
optimize = "max"
level = "episode"
```

---

## SEARCH 4: HuggingFace Hub + Pinokio Integration Patterns

### Pinokio Architecture
- **Type**: Browser-based automation platform (not just an installer)
- **Script Format**: JSON descriptor + JavaScript execution files
- **Cross-Platform**: Windows, Mac, Linux
- **Core Mechanism**: JSON file describes dependencies and execution flow; JS files implement install/start/stop/update/reset logic

### Pinokio Script Structure (from PMOVES-Pinokio-Ultimate-TTS-Studio)
```
pinokio_meta.json    # Metadata (name, description, icon, requirements)
install.js           # Installation logic
start.js             # Launch logic
stop.js              # Shutdown logic
update.js            # Update logic
reset.js             # Reset/cleanup logic
torch.js             # PyTorch installation helper
link.js              # Symlink/shortcut creation
pinokio.js           # Main entry point
```

### HuggingFace Model Download Pattern (Real Example)
```javascript
// From PMOVES-Pinokio-Ultimate-TTS-Studio/install.js
module.exports = {
  requires: {
    bundle: "ai",
  },
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "hf download cocktailpeanut/oa --local-dir ./checkpoints/openaudio-s1-mini",
      }
    },
    // ... more steps
  ]
};
```

### Key Pinokio API Methods
| Method | Purpose |
--------|---------|
| `shell.run` | Execute shell commands (supports `conda`, `path`, `sudo`, `message` params) |
| `script.start` | Invoke another Pinokio script (for modular installs) |
| `when` | Conditional execution (OS detection: `which('brew')`, `which('apt')`, `which('yum')`, `which('winget')`) |
| `next` | Flow control (`'end'` to skip remaining steps) |

### GGUF Model Distribution via HuggingFace
- **Pattern**: HF repo contains .gguf files → Pinokio script runs `hf download <org>/<repo> --local-dir ./models/` → Ollama/llama.cpp loads from local dir
- **Example repos**: `unsloth/Qwen3.5-35B-A3B-GGUF`, `tensorblock/Pinokio_v1.0-GGUF`
- **Ollama integration**: Downloaded GGUF files loaded via `ollama create` with Modelfile pointing to local .gguf path

### One-Click Install Flow for Non-Technical Users
1. User installs Pinokio browser
2. User clicks "Install" on a Pinokio script URL
3. Pinokio reads `pinokio_meta.json` → checks `requires.bundle`
4. Executes `install.js` sequentially: git clone → conda env → pip install → `hf download` models → system deps
5. User clicks "Start" → executes `start.js` → launches Gradio/web UI
6. No terminal interaction required

### PMOVES Pattern
- PMOVES-Pinokio-Ultimate-TTS-Studio is a real example: clones GitHub repo, creates conda env `tts_env`, installs PyTorch with Triton, downloads HF model (`cocktailpeanut/oa`), installs OS-level deps (espeak-ng) with OS-conditional logic
- Pattern reusable for any HF-hosted model: replace git clone URL, pip requirements, and `hf download` target

---

## SEARCH 5: Ollama Pull Strategy for GB10-Optimized Quantized Models

### Quantization Quality Comparison

#### Perplexity & Task Benchmarks (Llama 4 Scout 17B)
| Format | HumanEval | vs FP16 Delta | Quality Retention |
--------|-----------|---------------|-------------------|
| F16 (BF16) | 72.6% | baseline | 100% |
| Q8_0 | 72.4% | -0.2% | ~100-103% |
| Q4_K_M | 70.9% | -1.7% | 92-98% |

#### General Quality Deltas
| Comparison | Perplexity Delta | Task Benchmark Delta |
------------|-----------------|---------------------|
| Q8_0 vs Q4_K_M | ~2% better (Q8_0) | <1.5% |
| Q4_K_M vs F16 | ~0.05-0.2 points (WikiText-2) | 1-2% |
| Q8_0 vs F16 | Negligible | <0.5% |

#### VRAM Requirements by Model Size
| Model Size | Q4_K_M | Q8_0 | F16 |
------------|--------|------|-----|
| 7B | ~5GB (4.1GB file) | ~8GB (6.7GB file) | ~15GB (13.5GB file) |
| 13B | ~9GB | ~15GB | ~28GB |
| 32B | ~18GB | ~32GB | ~64GB |
| 70B | ~40GB | ~72GB | ~140GB |
| 70B MoE (active) | ~20-25GB | ~40GB | ~80GB |

#### Inference Speed (RTX 3080 10GB, Llama 4 Scout 17B)
| Format | Speed | VRAM Used | Fits? |
--------|-------|-----------|-------|
| Q4_K_M | ~35 tok/s | 9.8GB | Yes |
| Q8_0 | N/A | >10GB | **OOM** |

### GB10-Specific Recommendations (128GB Unified)

#### Quantization Selection for GB10
| Scenario | Recommended Format | Rationale |
----------|-------------------|-----------|
| Max quality, model fits | **Q8_0** | Near-lossless, 301 GB/s bandwidth sufficient |
| Large models (70B+), multi-model | **Q4_K_M** | Fits 3+ 70B models in 128GB simultaneously |
| Fine-tuning base | **F16** ( Unsloth handles quant internally) | Let Unsloth's QLoRA handle 4-bit during training |
| MoE models (Qwen3-30B-A3B) | **Q4_K_M** | Only active params matter, 4-bit sufficient |

#### No GB10/Blackwell-Specific Ollama Builds Found
- Ollama does not publish architecture-specific GGUF builds
- Optimization is at the llama.cpp level (CUDA kernels auto-detect GPU capabilities)
- Blackwell CUDA kernels in llama.cpp: expected to leverage FP8/FP4 when available
- As of search date: no "gb10-optimized" tag exists on Ollama library

### Ollama Pull Commands

#### Exact Commands
```bash
# Qwen 2.5 family
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
ollama pull qwen2.5:32b
ollama pull qwen2.5:72b
ollama pull qwen2.5-coder:32b

# Llama 3.1 family
ollama pull llama3.1:8b
ollama pull llama3.1:70b
ollama pull llama3.1:405b

# Llama 3.3
ollama pull llama3.3:70b

# Llama 4 (latest)
ollama pull llama4:scout-q4_k_m
ollama pull llama4:scout-q5_k_m
ollama pull llama4:scout-q8_0
ollama pull llama4:scout-fp16

# Qwen 3 / 3.5 / 3.6
ollama pull qwen3:30b-a3b
ollama pull qwen3.5:35b-a3b

# Verify
ollama show llama4:scout --verbose
ollama list
```

#### Custom Quantization from HuggingFace FP16
```bash
# Create base Modelfile from HF model
cat > Modelfile << 'EOF'
FROM ./models/llama3-8b-instruct-fp16
PARAMETER temperature 0.7
PARAMETER top_p 0.9
EOF

# Generate quantized variants
ollama create llama3-8b-fp16 -f Modelfile
ollama create --quantize q8_0 llama3-8b-q8_0 -f Modelfile
ollama create --quantize q6_k llama3-8b-q6_k -f Modelfile
ollama create --quantize q5_k_m llama3-8b-q5_k_m -f Modelfile
ollama create --quantize q4_k_m llama3-8b-q4_k_m -f Modelfile
```

#### KV Cache & Flash Attention Optimization
```bash
# KV cache quantization (reduces memory for long contexts)
OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve &

# Flash attention enable
OLLAMA_FLASH_ATTENTION=1 ollama serve &
```

#### Unsloth GGUF → Ollama Workflow
```bash
# From Unsloth HuggingFace GGUF exports
llama-server \
  -hf unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M \
  --host 0.0.0.0 \
  -t 10 \
  -ngl 99 \
  --temp 0.6 \
  --min-p 0.0 \
  --top-p 0.95 \
  --top-k 20 \
  --presence-penalty 1.5 \
  --repeat-penalty 1 \
  --jinja \
  --flash-attn on \
  --no-mmap \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -c 64000 \
  --webui-mcp-proxy
```

### Recommended GB10 System Bring-Up Pull Order
1. `ollama pull qwen2.5:7b` — smoke test, fastest download (~4.1GB)
2. `ollama pull qwen2.5:32b` — mid-size quality test (~18GB)
3. `ollama pull qwen2.5-coder:32b` — coding-specific benchmark (~18GB)
4. `ollama pull qwen3.5:35b-a3b` — MoE efficiency test (~20GB active)
5. `ollama pull llama3.3:70b` — large model quality ceiling (~40GB Q4_K_M)
6. `ollama pull llama4:scout-q4_k_m` — latest architecture test (~10GB)
7. `ollama pull qwen2.5:72b` — max single-model test (~40GB Q4_K_M)

Total storage for full stack: ~160GB (exceeds 128GB RAM — models are memory-mapped from disk, not all loaded at once)

### Top Ollama Models (2026 Rankings)
| Model | Best For | MMLU | VRAM (Q4) |
-------|----------|------|-----------|
| Llama 3.3 70B | Overall quality | 86.0 | ~40GB |
| Qwen 2.5 Coder 32B | Coding | 92.7% | ~18GB |
| Llama 4 Scout | Best overall (MoE) | High | ~10GB |
| Qwen 3/3.5/3.6 | Fastest growing, best coding | High | Varies by active params |
| Gemma 4 | Tool use | High | Varies |

---

## CROSS-SEARCH SYNTHESIS: GB10 Deployment Strategy

### Optimal Configuration
- **Primary inference**: Q4_K_M for 70B-class models (40GB each, fits 3 in 128GB with headroom)
- **Quality-critical tasks**: Q8_0 for 32B-class models (32GB, near-lossless)
- **Fine-tuning**: Unsloth with NVFP4 on GB10, QLoRA 4-bit, up to 40B single-GPU or 70B+ with 128GB
- **Routing**: TensorZero with Ollama as primary, cloud (GPT-4o-mini/Glm-5) as fallback
- **Distribution**: Pinokio scripts referencing HF repos for one-click deployment

### Bandwidth Reality Check
- 301 GB/s feeding 6144 CUDA cores = **51 GB/s per 1024 cores** — severely memory-bound
- For 70B Q4_K_M at ~40GB: full prefill = 40GB/301GB/s = **133ms** theoretical minimum
- Multi-model serving amortizes bandwidth cost across concurrent requests
- KV cache quantization (q8_0) critical for long-context workloads on GB10
