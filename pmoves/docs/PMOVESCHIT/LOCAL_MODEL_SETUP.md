# Local Model Setup Guide for PMOVES.AI

This guide covers setting up and running PMOVES.AI entirely with local models using Hugging Face integration.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Hardware Requirements](#hardware-requirements)
3. [Model Catalog](#model-catalog)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU (recommended) or CPU for small models
- At least 16GB RAM for 7B models

### One-Command Setup

```bash
# 1. Set up environment variables
cp pmoves/env.hf-models.example pmoves/env.hf-models
# Edit pmoves/env.hf-models and add your HF token if needed

# 2. Start HF MCP server
docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d

# 3. Run interactive setup
python pmoves/scripts/hf_model_setup.py

# 4. Start vLLM services (medium tier)
docker compose -f pmoves/docker-compose/vllm-models.yml --profile medium up -d

# 5. Start BoTZ with local models
cd PMOVES-BoTZ-check && ./scripts/pmoves_botz_ctl.sh start
```

## Hardware Requirements

### CPU-Only / Edge (Small Models)

| Model | VRAM | RAM | Use Case |
|-------|------|-----|----------|
| phi3-mini | 0 | 8GB | Utility, edge tasks |
| gemma-2-2b | 0 | 6GB | Simple tasks |

### Single Consumer GPU (8-12GB VRAM)

| Model | VRAM | Parameters | Use Case |
|-------|------|------------|----------|
| qwen2.5-7b | 8GB | 7B | Orchestrator, coding |
| qwen2.5-coder-7b | 8GB | 7B | Coding |
| qwen2-vl-7b | 8GB | 7B | Vision-language |

### Single Mid-Range GPU (16-24GB VRAM)

| Model | VRAM | Parameters | Use Case |
|-------|------|------------|----------|
| qwen2.5-14b | 16GB | 14B | Orchestrator, research |
| qwen2.5-coder-7b (q8) | 16GB | 7B | High-quality coding |
| qwen3-vl-8b | 16GB | 8B | Vision-language |

### AI Workstation (32-48GB VRAM)

| Model | VRAM | Parameters | Use Case |
|-------|------|------------|----------|
| qwen2.5-32b | 48GB (2x24) | 32B | Research, coordinator |
| qwen2.5-14b (fp16) | 24GB | 14B | High-quality tasks |

### Multi-GPU Server (2-4x GPUs)

| Model | VRAM | Parameters | Use Case |
|-------|------|------------|----------|
| qwen2.5-32b (q8) | 2x24GB | 32B | Research, coordinator |
| qwen2.5-72b | 4x24GB | 72B | Advanced research |

## Model Catalog

### Small Models (3B-8B) - CPU/Edge

| Name | HF ID | Context | Backend | Uses |
|------|-------|---------|---------|------|
| phi3-mini | microsoft/Phi-3-mini-128k-instruct | 128K | ollama, vllm | utility, edge |
| gemma-2-2b | google/gemma-2-2b-it | 8K | ollama, vllm | utility |
| qwen2.5-3b | Qwen/Qwen2.5-3B-Instruct | 32K | ollama, vllm | utility |

### Medium Models (7B-14B) - Single GPU

| Name | HF ID | Context | Backend | Uses |
|------|-------|---------|---------|------|
| qwen2.5-7b | Qwen/Qwen2.5-7B-Instruct | 32K | ollama, vllm | orchestrator, coding |
| qwen2.5-14b | Qwen/Qwen2.5-14B-Instruct | 32K | ollama, vllm | orchestrator, coding |
| llama3.1-8b | meta-llama/Llama-3.1-8B-Instruct | 128K | ollama, vllm | orchestrator |
| qwen2.5-coder-7b | Qwen/Qwen2.5-Coder-7B-Instruct | 32K | ollama, vllm | coding |
| deepseek-coder-6.7b | deepseek-ai/deepseek-coder-6.7b-instruct | 16K | ollama, vllm | coding |

### Large Models (30B-70B) - Multi-GPU

| Name | HF ID | Context | TP | Uses |
|------|-------|---------|-----|------|
| qwen2.5-32b | Qwen/Qwen2.5-32B-Instruct | 32K | 2 | orchestrator, research |
| qwen2.5-72b | Qwen/Qwen2.5-72B-Instruct | 128K | 4 | research, coordinator |

### Specialized Models

| Name | Type | HF ID | Dimensions | Uses |
|------|------|-------|------------|------|
| qwen2-vl-7b | VL | Qwen/Qwen2-VL-7B-Instruct | - | vl_sentinel |
| qwen3-vl-8b | VL | Qwen/Qwen3-VL-8B-Instruct | - | vl_sentinel |
| qwen3-embedding-8b | Embedding | Qwen/Qwen3-Embedding-8B | 4096 | embeddings, hirag |
| qwen3-embedding-4b | Embedding | Qwen/Qwen3-Embedding-4B | 3072 | embeddings |
| bge-large-en-v1.5 | Embedding | BAAI/bge-large-en-v1.5 | 1024 | embeddings |
| qwen3-reranker-4b | Reranker | Qwen/Qwen3-Reranker-4B | - | hirag_rerank |

## Installation

### 1. Clone Required Models via Ollama

```bash
# Small models
ollama pull phi3:3.8b-mini-128k-instruct
ollama pull gemma-2:2b

# Medium models
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
ollama pull qwen2.5-coder:7b
ollama pull qwen2-vl:7b

# Embedding models
ollama pull qwen3-embedding:8b
ollama pull qwen3-embedding:4b
```

### 2. Start HF MCP Server

```bash
docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d
```

Verify it's running:
```bash
curl http://localhost:8096/healthz
```

### 3. Start vLLM Services (Optional)

For higher quality inference with full precision models:

```bash
# Medium tier (single GPU)
docker compose -f pmoves/docker-compose/vllm-models.yml --profile medium up -d

# Large tier (multi-GPU)
docker compose -f pmoves/docker-compose/vllm-models.yml --profile large up -d

# Specialized models
docker compose -f pmoves/docker-compose/vllm-models.yml --profile specialized up -d
```

## Configuration

### TensorZero Configuration

Use the generated TensorZero config:

```bash
# Generate config from catalog
python pmoves/scripts/hf_update_tensorzero.py

# Copy to TensorZero config directory
cp pmoves/config/tensorzero/local_models.toml pmoves/tensorzero/config/

# Append to main config
cat pmoves/config/tensorzero/local_models.toml >> pmoves/tensorzero/config/tensorzero.toml
```

### BoTZ Configuration

Update BoTZ component configurations:

```bash
cd PMOVES-BoTZ-check

# Copy local models config
cp config/tensorzero.local.models.toml config/

# Update docker-compose references
# (The local model config will be used automatically)
```

### Environment Variables

Key environment variables:

```bash
# Hugging Face
HF_HOME=/mnt/models/hf
HF_HUB_CACHE=/mnt/models/hf/hub
HUGGINGFACE_HUB_TOKEN=your_token_here

# vLLM
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_GPU_MEMORY_UTILIZATION=0.9

# BoTZ Model Selection
BOTZ_ORCHESTRATOR_MODEL=qwen2.5-14b
BOTZ_CODING_MODEL=qwen2.5-coder-7b
BOTZ_VL_MODEL=qwen2-vl:7b
```

## Usage

### With Ollama (Recommended for Most Users)

1. Start Ollama:
```bash
docker compose -f pmoves/docker-compose.ollama.yml up -d
```

2. Pull models:
```bash
docker exec -it pmoves-ollama ollama pull qwen2.5:7b
docker exec -it pmoves-ollama ollama pull qwen2.5-coder:7b
```

3. Start BoTZ:
```bash
cd PMOVES-BoTZ-check
./scripts/pmoves_botz_ctl.sh start
```

### With vLLM (Higher Quality)

1. Start vLLM services:
```bash
docker compose -f pmoves/docker-compose/vllm-models.yml --profile medium up -d
```

2. Update TensorZero config to use vLLM endpoints

3. Start BoTZ

### Interactive Setup

Use the interactive setup script:
```bash
python pmoves/scripts/hf_model_setup.py
```

This will:
1. Detect your hardware
2. Recommend models
3. Download models
4. Generate TensorZero config
5. Provide next steps

## Troubleshooting

### HF MCP Server Not Responding

```bash
# Check health
curl http://localhost:8096/healthz

# Check logs
docker logs pmoves-hf-mcp-server

# Restart
docker compose -f pmoves/docker-compose/hf-mcp-server.yml restart
```

### vLLM Service Not Starting

```bash
# Check GPU availability
nvidia-smi

# Check logs
docker logs pmoves-vllm-qwen-7b

# Common issues:
# - Out of VRAM: Use smaller model or quantization
# - Model not downloaded: Check HF_HOME path
```

### Model Download Fails

```bash
# Set HF token for gated models
export HUGGINGFACE_HUB_TOKEN=your_token

# Accept terms on Hugging Face first:
# https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
```

### TensorZero Configuration Errors

```bash
# Validate TOML syntax
python -c "import tomllib; tomllib.load('pmoves/tensorzero/config/tensorzero.toml')"

# Check model availability
curl http://localhost:8096/api/models
```

### BoTZ Components Not Using Local Models

1. Check TensorZero config includes local models
2. Check Ollama has models pulled: `ollama list`
3. Check component config references correct function names

## Performance Optimization

### GPU Memory Optimization

- Use quantization (q4_k_m recommended)
- Reduce `max_num_seqs` for limited VRAM
- Adjust `gpu_memory_utilization` (0.7-0.95)

### Throughput Optimization

- Enable `--enable-chunked-prefill` (default)
- Enable `--enable-prefix-caching` for repeated prompts
- Use tensor parallelism for large models

### Model Selection

| Task | Best Value | Best Quality |
|------|------------|--------------|
| Orchestrator | qwen2.5-7b | qwen2.5-32b |
| Coding | qwen2.5-coder-7b | qwen2.5-coder-7b (q8) |
| Utility | qwen2.5-3b | qwen2.5-7b |
| VL | qwen2-vl-7b | qwen3-vl-8b |
| Embeddings | gemma-300m | qwen3-embedding-8b |

## Advanced Topics

### Tensor Parallelism

For models larger than single GPU VRAM:

```bash
# qwen2.5-32b with TP=2
docker compose -f pmoves/docker-compose/vllm-models.yml up vllm-qwen-32b
```

### Custom Model Catalog

Add your own models to `pmoves/config/models.yaml`:

```yaml
models:
  medium:
    - name: my-custom-model
      hf_id: org/cool-model-7b
      params: 7B
      context: 32768
      backends: [ollama, vllm]
      uses: [orchestrator]
      ollama_name: cool-model:7b
```

### GGUF Conversion

Convert HF models to GGUF for Ollama:

```bash
# Use HF MCP server
curl -X POST http://localhost:8096/api/model/convert-gguf \
  -H "Content-Type: application/json" \
  -d '{"model_id": "org/model", "quantize": "q4_k_m"}'
```

## References

- [Hugging Face Hub](https://huggingface.co/models)
- [Ollama Models](https://ollama.com/search)
- [vLLM Documentation](https://docs.vllm.ai/)
- [PMOVES.AI Services](../services-catalog.md)
