# Open-Source Model Recommendations for PMOVES.AI

Comprehensive guide to open-source model selection for PMOVES services, optimized for different deployment contexts.

**Last Updated**: December 14, 2025

## Model Selection Philosophy

PMOVES.AI prioritizes:
1. **Local-first**: Run models on-premises when possible
2. **Hardware-aware**: Match models to available resources
3. **Cost-efficient**: Use cloud fallbacks only when necessary
4. **Quality-focused**: Prefer frontier-capable open models

---

## December 2025 Model Landscape

### Key Model Families Available Now

| Family | Sizes | Context | Notes |
|--------|-------|---------|-------|
| **Qwen3** | 0.6B-235B | 40K-256K | Dense + MoE, thinking modes |
| **Qwen3-Coder** | 30B, 480B | 256K (1M ext) | SWE-Bench SOTA, MoE |
| **Qwen3-Embedding** | 0.6B, 4B, 8B | 32K | MTEB #1 (70.58), 100+ langs |
| **Qwen3-VL** | 2B-235B | 256K (1M ext) | Vision-language, GUI agent |
| **DeepSeek-R1** | 1.5B-671B | 128K-160K | Reasoning distills, MIT license |

### Key Changes from Q1 2025

| Area | Previous | Current (Dec 2025) | Notes |
|------|----------|-------------------|-------|
| **Primary LLM** | Qwen 2.5 32B | **Qwen3 30B** (MoE) | 3.3B active params, 256K ctx |
| **Reasoning** | None | **DeepSeek-R1:32b** | Qwen2.5 distill, MIT license |
| **Embeddings** | qwen3-embedding:4b | **Qwen3-Embedding (default) / Nomic (fallback)** | Qwen3-Embedding is MTEB-leading; PMOVES defaults to local Qwen3 embeddings via Ollama/TensorZero |
| **Code** | Qwen2.5-Coder | **Qwen3-Coder:30b** | 256K ctx, MoE 3.3B active |
| **Edge** | Phi-3 Mini | **Qwen3:4b** | 256K ctx, better quality |
| **Vision** | LLaVA | **Qwen3-VL:8b** | GUI agent, 256K ctx |

### Models to Watch

| Model | Status | Notes |
|-------|--------|-------|
| **Llama 4** | TBD 2025 | Meta's next iteration |
| **DeepSeek-V4** | TBD | Next-gen MoE |
| **Qwen3-235B** | Available | 235B total, 22B active (MoE) |

---

## Model Categories by Use Case

### 1. General LLM / Chat Completion

| Model | Parameters | Active Params | VRAM (Q4) | Context | Best For |
|-------|------------|---------------|-----------|---------|----------|
| **qwen3:30b** | 30B | 3.3B (MoE) | 19GB | 256K | Primary orchestration |
| **qwen3:32b** | 32B | 32B (dense) | 20GB | 128K | Dense alternative |
| **qwen3:14b** | 14B | 14B | 9GB | 40K | Balanced perf/quality |
| **qwen3:8b** | 8B | 8B | 5GB | 40K | Fast inference |
| **qwen3:4b** | 4B | 4B | 2.5GB | 256K | Edge/Jetson |
| **deepseek-r1:32b** | 32B | 32B | 20GB | 128K | Reasoning specialist |
| **deepseek-r1:14b** | 14B | 14B | 9GB | 128K | Lighter reasoning |

**PMOVES Default**: `qwen3:30b` (MoE - only 3.3B active, fits 24GB easily)
**Reasoning Tasks**: `deepseek-r1:32b` (Qwen2.5 distill, MIT license)

### 2. Embeddings

| Model | Dimensions | VRAM | MTEB Score | Context | Notes |
|-------|------------|------|------------|---------|-------|
| **qwen3-embedding:8b** | 32-4096 | 5-16GB | **70.58 (#1)** | 32K | MTEB leader, 100+ langs |
| **qwen3-embedding:4b** | 32-2560 | 3-4GB | Excellent | 32K | Balanced quality/VRAM |
| **qwen3-embedding:0.6b** | 32-1024 | 0.5GB | Good | 32K | Edge deployment |
| **snowflake-arctic-embed2:568m** | 1024 | 1.2GB | Excellent | 8K | Fast, MRL compression |
| **nomic-embed-text** | 64-768 | 0.5GB | 53.01 | 8K | Speed-optimized |
| **all-minilm:l6-v2** | 384 | 43MB | Moderate | 512 | Ultra-fast, CPU OK |

**PMOVES Default (production, RTX 5090 class)**: `qwen3-embedding:4b` via TensorZero embedding route `tensorzero::embedding_model_name::qwen3_embedding_4b_local`.
**PMOVES Fast local fallback**: `nomic-embed-text` (use a dedicated Qdrant collection; do not mix dims).
**PMOVES Edge (Jetson/low VRAM)**: `qwen3-embedding:0.6b` or `embeddinggemma:300m` (use a dedicated Qdrant collection; do not mix dims).
**PMOVES CPU-only fallback**: `all-minilm:l6-v2` (384-dim; use a dedicated Qdrant collection).

### 3. Reranking

| Model | Parameters | VRAM | Use Case |
|-------|------------|------|----------|
| **Qwen Reranker 4B** | 4B | 4GB | High quality, fast |
| **bge-reranker-v2-m3** | 568M | 1GB | Multilingual |
| **bge-reranker-large** | 560M | 1GB | English focused |
| **cross-encoder/ms-marco** | 110M | 512MB | Ultra-lightweight |

**PMOVES Default**: bge-reranker-base (CPU), Qwen Reranker 4B (GPU)

### 4. Vision / Multimodal

| Model | Parameters | VRAM | Capabilities |
|-------|------------|------|--------------|
| **Qwen2-VL 7B** | 7B | 16GB | OCR, charts, general vision |
| **LLaVA-1.6 34B** | 34B | 48GB | Detailed image analysis |
| **Florence-2** | 0.7B | 2GB | Fast vision tasks |
| **InternVL2** | 8B | 16GB | Strong VQA |

**PMOVES Default**: Qwen2-VL 7B

### 5. Audio / Speech

| Model | Parameters | VRAM | Use Case |
|-------|------------|------|----------|
| **Whisper Large v3** | 1.5B | 6GB | Transcription |
| **Faster-Whisper** | 1.5B | 4GB | Optimized Whisper |
| **HuBERT Large** | 316M | 2GB | Emotion detection |
| **Wav2Vec2** | 317M | 2GB | Speaker ID |

**PMOVES Default**: Faster-Whisper small (FFmpeg-Whisper service)

### 6. Code Generation

| Model | Parameters | VRAM | Specialization |
|-------|------------|------|----------------|
| **Qwen2.5-Coder 32B** | 32B | 24GB | Full-stack coding |
| **DeepSeek-Coder-V2** | 236B | Cloud | Competitive with GPT-4 |
| **CodeLlama 34B** | 34B | 24GB | Meta's code specialist |
| **StarCoder2 15B** | 15B | 16GB | Efficient, multi-language |

**PMOVES Default**: Qwen2.5-Coder 32B

---

## Hardware Profile Mappings

### RTX 5090 (32GB VRAM) - `workstation_5090`

```yaml
# Ollama model names (exact)
model_bundles:
  llm: qwen3:32b              # Dense, 128K ctx, FP16
  llm_moe: qwen3:30b          # MoE 3.3B active, 256K ctx
  reasoning: deepseek-r1:32b  # Qwen2.5 distill
  embeddings: qwen3-embedding:4b  # MTEB #1, 32K ctx
  code: qwen3-coder:30b       # 256K ctx, MoE
  vision: qwen3-vl:8b         # GUI agent capable
  whisper: faster-whisper-large-v3
```

### RTX 4090 (24GB VRAM) / RTX 3090 Ti (24GB) - `desktop_3090ti`

```yaml
model_bundles:
  llm: qwen3:30b              # MoE, only 3.3B active = fast
  llm_fallback: qwen3:14b     # Dense fallback
  reasoning: deepseek-r1:32b  # Fits in 24GB Q4
  embeddings: qwen3-embedding:4b
  code: qwen3-coder:30b       # MoE fits easily
  vision: qwen3-vl:8b
  whisper: faster-whisper-medium
```

### RTX 4090 Laptop (16GB VRAM) - `laptop_4090`

```yaml
model_bundles:
  llm: qwen3:14b              # Dense, good quality
  llm_fast: qwen3:8b          # Quick responses
  reasoning: deepseek-r1:14b  # Lighter reasoning
  embeddings: qwen3-embedding:4b  # 3-4GB
  code: qwen3-coder:30b       # MoE 3.3B active fits
  vision: qwen3-vl:4b
  whisper: faster-whisper-small
```

### Jetson Orin Nano Super (8GB unified) - `jetson_orin`

```yaml
model_bundles:
  llm: qwen3:4b               # 256K ctx, edge optimized
  llm_tiny: qwen3:0.6b        # Ultra-light fallback
  reasoning: deepseek-r1:1.5b # Runs on 8GB RAM
  embeddings: qwen3-embedding:0.6b
  vision: qwen3-vl:2b
  whisper: faster-whisper-tiny
```

### CPU-Only Deployment - `minimal`

```yaml
model_bundles:
  llm: qwen3:1.7b             # Light, 40K ctx
  llm_tiny: qwen3:0.6b        # Minimal
  reasoning: deepseek-r1:1.5b # CPU-capable
  embeddings: all-minilm:l6-v2  # 43MB, instant
  vision: null                # Cloud fallback
  whisper: faster-whisper-tiny
```

---

## TensorZero Model Routing

PMOVES uses TensorZero as the centralized LLM gateway. Configure model routing in `pmoves/tensorzero/config/tensorzero.toml`:

### Provider Configuration

```toml
# Local Ollama models
[providers.ollama]
type = "ollama"
url = "http://localhost:11434"

# Venice.ai for cloud fallback
[providers.venice]
type = "venice"
api_key_env = "VENICE_API_KEY"

# Anthropic for frontier tasks
[providers.anthropic]
type = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
```

### Model Function Mapping

```toml
# Default chat - routes to best available
[functions.chat]
type = "chat"
variants = ["local_qwen", "venice_qwen", "anthropic_claude"]

[functions.chat.variants.local_qwen]
provider = "ollama"
model = "qwen2.5:32b"
weight = 1.0  # Primary

[functions.chat.variants.venice_qwen]
provider = "venice"
model = "qwen/qwen-2.5-72b-instruct"
weight = 0.5  # Fallback

[functions.chat.variants.anthropic_claude]
provider = "anthropic"
model = "claude-sonnet-4-5"
weight = 0.1  # Premium fallback
```

### Embedding Function

```toml
[functions.embed]
type = "embedding"
variants = ["local_qwen3_embedding"]

[functions.embed.variants.local_qwen3_embedding]
provider = "ollama"
model = "qwen3-embedding:4b"
```

Implementation note (this repo): PMOVES uses TensorZero’s `embedding_models.*` routes (see `pmoves/tensorzero/config/tensorzero.toml`) and services point at those via `TENSORZERO_EMBED_MODEL` in `pmoves/env.shared`.

---

## Service-Specific Recommendations

### Agent Zero (Orchestrator)

- **Primary**: Qwen 2.5 32B (reasoning, planning)
- **Fallback**: Claude Sonnet 4.5 (complex orchestration)
- **Context**: 32K tokens sufficient for most tasks

### Archon (Prompt Management)

- **Primary**: Same as Agent Zero
- **For forms**: Lighter model OK (Qwen 7B)

### Hi-RAG v2 (Retrieval)

- **Embeddings**: qwen3-embedding:4b (default) or nomic-embed-text (speed; separate collection)
- **Reranker**: Qwen Reranker 4B (GPU) or bge-reranker-base (CPU)
- **Generator**: Routed through TensorZero

### DeepResearch

- **Primary**: DeepSeek-R1 (reasoning specialist)
- **Fallback**: Qwen 72B or Claude

### SupaSerch (Multimodal)

- **Vision**: Qwen2-VL 7B
- **Text**: Same as Hi-RAG
- **Audio**: Whisper integration

### Extract Worker

- **Embeddings**: all-MiniLM-L6-v2 (fast, lightweight)
- **Purpose**: Document chunking and indexing

### PMOVES.YT (Media)

- **Transcription**: Faster-Whisper (medium or small)
- **Summarization**: Qwen 7B (fast summaries)

---

## Model Pulling with Ollama

```bash
# December 2025 - Core models for 24GB VRAM setup (RTX 3090 Ti / 4090)

# Primary LLM - Qwen3 MoE (30B total, 3.3B active)
ollama pull qwen3:30b

# Reasoning model - DeepSeek-R1 distill
ollama pull deepseek-r1:32b

# Embeddings - MTEB #1 (Qwen3-Embedding)
ollama pull qwen3-embedding:4b

# Code generation - 256K context
ollama pull qwen3-coder:30b

# Vision-language
ollama pull qwen3-vl:8b

# Fast fallback
ollama pull qwen3:8b

# Or use the seed script with profile detection:
PMOVES_PROFILE=workstation_5090 ./pmoves/scripts/seed-local-models.sh
```

### Quick Reference - Ollama Model Names

```bash
# Chat/Reasoning
qwen3:0.6b | qwen3:1.7b | qwen3:4b | qwen3:8b | qwen3:14b | qwen3:30b | qwen3:32b
deepseek-r1:1.5b | deepseek-r1:7b | deepseek-r1:8b | deepseek-r1:14b | deepseek-r1:32b | deepseek-r1:70b

# Embeddings (32K context, flexible dimensions)
qwen3-embedding:0.6b | qwen3-embedding:4b | qwen3-embedding:8b

# Code (256K context, MoE)
qwen3-coder:30b | qwen3-coder:480b

# Vision-Language (256K context)
qwen3-vl:2b | qwen3-vl:4b | qwen3-vl:8b | qwen3-vl:30b | qwen3-vl:32b
```

---

## 2025 Model Landscape Updates

### Released in 2025

| Model | Release | Notes |
|-------|---------|-------|
| **Qwen3** | 2025 | 0.6B-235B, MoE + Dense, 256K ctx |
| **Qwen3-Coder** | 2025 | 30B-480B MoE, SWE-Bench SOTA |
| **Qwen3-Embedding** | 2025 | MTEB #1 (70.58), 32K ctx |
| **Qwen3-VL** | 2025 | GUI agent, 256K-1M ctx |
| **DeepSeek-R1** | Jan 2025 | 1.5B-671B, reasoning distills |
| **DeepSeek-R1-0528** | May 2025 | Improved reasoning, Qwen3 8B base |
| **Llama 3.3** | 2024-25 | 70B, strong all-around |

### Key Architectural Trends (Dec 2025)

- **MoE (Mixture of Experts)**: Qwen3-30B (3.3B active), Qwen3-235B (22B active) - massive quality, small footprint
- **Long Context Native**: Qwen3 256K, expandable to 1M via YaRN
- **Reasoning Distillation**: DeepSeek-R1 distills Qwen2.5/Llama3 with 800K reasoning samples
- **Matryoshka Embeddings**: Qwen3-Embedding, Snowflake Arctic - flexible output dimensions
- **Agentic Coding**: Qwen3-Coder trained with Agent RL on 20K parallel environments

---

## Cost Optimization Strategy

### Tier 1: Local Models (Free after hardware)
- Qwen 2.5 family
- Llama 3.3
- Open embeddings/rerankers

### Tier 2: Affordable Cloud ($0.001-0.01/1K tokens)
- Venice.ai (Qwen 72B, Llama 70B)
- Groq (fast inference)
- Together.ai

### Tier 3: Premium Cloud ($0.01-0.03/1K tokens)
- Claude Sonnet 4.5
- GPT-4o
- Gemini Pro

### TensorZero Routing Strategy

1. **Always try local first** (weight: 1.0)
2. **Fallback to affordable cloud** (weight: 0.5)
3. **Premium only for complex tasks** (weight: 0.1)

---

## TAC Integration

### Model Commands via Claude Code CLI

```bash
# Check TensorZero model status
/health:metrics "tensorzero_model_requests_total"

# Query knowledge base (uses embeddings + reranker)
/search:hirag "What models are configured?"

# Deep research (uses reasoning model)
/search:deepresearch "Compare Qwen vs Llama performance"
```

### Mini CLI Model Management

```bash
# Check hardware profile for model recommendations
python3 -m pmoves.tools.mini_cli profile detect

# Apply profile with model bundles
python3 -m pmoves.tools.mini_cli profile apply rtx-3090-ti
```

---

## References

### Model Documentation
- [Qwen3: Think Deeper, Act Faster](https://qwenlm.github.io/blog/qwen3/)
- [Qwen3-Coder: Agentic Coding](https://qwenlm.github.io/blog/qwen3-coder/)
- [Qwen3-Embedding: Text Embedding & Reranking](https://qwenlm.github.io/blog/qwen3-embedding/)
- [DeepSeek-R1 GitHub](https://github.com/deepseek-ai/DeepSeek-R1)
- [Llama 3.3 Documentation](https://llama.meta.com/)

### Ollama Libraries
- [qwen3](https://ollama.com/library/qwen3) - 14.6M downloads
- [qwen3-embedding](https://ollama.com/library/qwen3-embedding)
- [qwen3-coder](https://ollama.com/library/qwen3-coder)
- [qwen3-vl](https://ollama.com/library/qwen3-vl)
- [deepseek-r1](https://ollama.com/library/deepseek-r1) - 73.7M downloads
- [snowflake-arctic-embed2](https://ollama.com/library/snowflake-arctic-embed2)

### Benchmarks
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [SWE-Bench Verified](https://www.swebench.com/)

### PMOVES Integration
- [TensorZero Documentation](https://www.tensorzero.com/docs)
- [PMOVES seed-local-models.sh](../pmoves/scripts/seed-local-models.sh)
