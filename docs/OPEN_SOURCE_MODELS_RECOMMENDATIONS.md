# Open-Source Model Recommendations for PMOVES.AI

Comprehensive guide to open-source model selection for PMOVES services, optimized for different deployment contexts.

## Model Selection Philosophy

PMOVES.AI prioritizes:
1. **Local-first**: Run models on-premises when possible
2. **Hardware-aware**: Match models to available resources
3. **Cost-efficient**: Use cloud fallbacks only when necessary
4. **Quality-focused**: Prefer frontier-capable open models

---

## Model Categories by Use Case

### 1. General LLM / Chat Completion

| Model | Parameters | VRAM Required | Best For |
|-------|------------|---------------|----------|
| **Qwen 2.5 32B** | 32B | 24-32GB | General reasoning, coding, analysis |
| **Qwen 2.5 72B** | 72B | 48-80GB | Maximum quality, complex tasks |
| **Llama 3.3 70B** | 70B | 48-80GB | Meta's latest, strong all-around |
| **DeepSeek-R1 671B** | 671B | Cloud/Multi-GPU | Reasoning specialist |
| **Mistral Large 2** | 123B | 80GB+ | Strong reasoning, multilingual |
| **Command R+** | 104B | 64GB+ | Tool use, enterprise |

**PMOVES Default**: Qwen 2.5 32B (fits RTX 3090 Ti/4090)

### 2. Embeddings

| Model | Dimensions | VRAM | Quality Score |
|-------|------------|------|---------------|
| **nomic-embed-text** | 768 | 2GB | Excellent |
| **bge-large-en-v1.5** | 1024 | 2GB | MTEB leader |
| **gemma-embed** | 768 | 2GB | Google quality |
| **all-MiniLM-L6-v2** | 384 | 1GB | Fast, lightweight |
| **e5-large-v2** | 1024 | 2GB | Strong multilingual |

**PMOVES Default**: all-MiniLM-L6-v2 (Extract Worker)
**PMOVES Hi-RAG**: nomic-embed-text or bge-large

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

### RTX 3090 Ti (24GB VRAM)

```yaml
model_bundles:
  llm: qwen2.5-32b-instruct-q4_k_m  # Quantized for 24GB
  embeddings: nomic-embed-text
  reranker: qwen-reranker-4b
  vision: qwen2-vl-7b-instruct
  whisper: faster-whisper-medium
```

### RTX 4090/5090 (24-32GB VRAM)

```yaml
model_bundles:
  llm: qwen2.5-32b-instruct  # Full precision
  embeddings: bge-large-en-v1.5
  reranker: qwen-reranker-4b
  vision: qwen2-vl-7b-instruct
  code: qwen2.5-coder-32b
```

### Dual GPU / 48GB+ VRAM

```yaml
model_bundles:
  llm: llama-3.3-70b-instruct  # Or Qwen 72B
  embeddings: bge-large-en-v1.5
  reranker: qwen-reranker-4b
  vision: llava-1.6-34b
  code: deepseek-coder-v2-instruct
```

### Jetson AGX Orin (32GB unified)

```yaml
model_bundles:
  llm: qwen2.5-7b-instruct  # Smaller for edge
  embeddings: all-MiniLM-L6-v2
  reranker: cross-encoder-ms-marco
  vision: florence-2
  whisper: faster-whisper-small
```

### CPU-Only Deployment

```yaml
model_bundles:
  llm: qwen2.5-7b-instruct-q4_0  # Heavy quantization
  embeddings: all-MiniLM-L6-v2
  reranker: bge-reranker-base
  vision: null  # Cloud fallback
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
variants = ["local_nomic"]

[functions.embed.variants.local_nomic]
provider = "ollama"
model = "nomic-embed-text"
```

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

- **Embeddings**: bge-large-en-v1.5 (quality) or nomic-embed-text (speed)
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
# Core models for 24GB VRAM setup
ollama pull qwen2.5:32b
ollama pull nomic-embed-text
ollama pull qwen2-vl:7b

# For reranking (via API, not Ollama native)
# Use TensorZero routing to local reranker service

# Whisper models
# Pulled by faster-whisper container automatically
```

---

## 2025 Model Landscape Updates

### New Releases to Monitor

| Model | Release | Notes |
|-------|---------|-------|
| **Qwen 3** | Q1 2025 | Next-gen from Alibaba |
| **Llama 4** | TBD 2025 | Meta's next iteration |
| **GPT-5** | TBD 2025 | OpenAI flagship |
| **Claude 4** | TBD 2025 | Anthropic next-gen |
| **Gemini 2.5** | Q1 2025 | Google multimodal |

### Emerging Architectures

- **MoE (Mixture of Experts)**: DeepSeek-V3, Mixtral - efficient at scale
- **Long Context**: Gemini 2M, Claude 200K - extended reasoning
- **Reasoning Models**: DeepSeek-R1, o3 - chain-of-thought specialists

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

- [Qwen 2.5 Technical Report](https://qwenlm.github.io/blog/qwen2.5/)
- [Llama 3 Documentation](https://llama.meta.com/)
- [DeepSeek R1 Paper](https://arxiv.org/abs/2501.12948)
- [TensorZero Documentation](https://www.tensorzero.com/docs)
- [Ollama Model Library](https://ollama.ai/library)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
