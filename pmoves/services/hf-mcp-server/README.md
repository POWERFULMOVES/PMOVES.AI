# Hugging Face MCP Server for PMOVES.AI

Model Context Protocol (MCP) server for Hugging Face Hub integration with PMOVES.AI.

## Features

- **Model Discovery**: Search models by task, size, architecture, and use case
- **Model Download**: Download and cache models from Hugging Face Hub
- **Model Metadata**: Extract model requirements (VRAM, GPU count, quantization)
- **GGUF Conversion**: Support for GGUF format conversion for Ollama
- **vLLM Integration**: Compatibility checking for vLLM backend
- **NATS Events**: Publish download events to NATS bus

## MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `hf.model.search` | Search models by task, size, architecture | `task`, `size`, `architecture`, `use_case` |
| `hf.model.info` | Get model metadata and requirements | `model_id` (required) |
| `hf.model.download` | Download model to local cache | `model_id` (required), `variant`, `quantization` |
| `hf.model.list` | List all cached models | - |
| `hf.model.convert_gguf` | Convert model to GGUF for Ollama | `model_id` (required), `quantize`, `output_dir` |

## Model Catalog

### Small Models (3B-8B) - CPU/Edge
- `phi3-mini`: Microsoft Phi-3 Mini (128K context)
- `gemma-2-2b`: Google Gemma 2 2B

### Medium Models (7B-14B) - Single GPU
- `qwen2.5-7b`: Qwen 2.5 7B Instruct
- `qwen2.5-14b`: Qwen 2.5 14B Instruct
- `llama3.1-8b`: Llama 3.1 8B Instruct (128K context)
- `gemma-2-9b`: Google Gemma 2 9B
- `qwen2.5-coder-7b`: Qwen 2.5 Coder 7B
- `deepseek-coder-6.7b`: DeepSeek Coder 6.7B

### Large Models (30B-70B) - Multi-GPU
- `qwen2.5-32b`: Qwen 2.5 32B Instruct (TP=2)
- `qwen2.5-72b`: Qwen 2.5 72B Instruct (TP=4)

### Vision-Language Models
- `qwen2-vl-7b`: Qwen 2 VL 7B Instruct
- `llava-v1.6-7b`: LLaVA v1.6 7B

### Embedding Models
- `qwen3-embedding-8b`: Qwen 3 Embedding 8B (4096 dim)
- `bge-large-en-v1.5`: BAAI BGE Large (1024 dim)
- `nomic-embed-text`: Nomic Embed Text v1.5 (768 dim)

### Rerankers
- `qwen3-reranker-4b`: Qwen 3 Reranker 4B

## Quick Start

### Docker Compose

```bash
# Standalone (HF MCP server only)
docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d

# Or as part of the full agents profile
docker compose -f pmoves/docker-compose.yml --profile agents --profile research up -d hf-mcp-server
```

### Direct API Usage

```bash
# Health check
curl http://localhost:8096/health

# Search models
curl -X POST http://localhost:8096/api/model/search \
  -H "Content-Type: application/json" \
  -d '{"tier": "medium", "use_case": "coding"}'

# Get model info
curl http://localhost:8096/api/model/qwen2.5-7b

# List cached models
curl http://localhost:8096/api/models

# Download model
curl -X POST http://localhost:8096/api/model/download \
  -H "Content-Type: application/json" \
  -d '{"model_id": "qwen2.5-7b"}'

# Generate TensorZero config
curl http://localhost:8096/api/config/tensorzero
```

### MCP Integration

Add to your MCP client configuration:

```yaml
mcp_servers:
  huggingface:
    url: "http://localhost:8096/sse"
    transport: "sse"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_HOME` | `/models` | Base model storage path |
| `HF_HUB_CACHE` | `/models/hub` | Hugging Face Hub cache |
| `HUGGINGFACE_HUB_TOKEN` | - | HF Hub API token (for gated models) |
| `HF_HUB_ENABLE_HF_TRANSFER` | `1` | Enable HF transfer acceleration |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS server URL |
| `PORT` | `8096` | Server port |

## NATS Events

The server publishes events to:

- `hf.model.downloaded.v1`: When a model download completes

```json
{
  "model_id": "Qwen/Qwen2.5-7B-Instruct",
  "path": "/models/hub/models/Qwen--Qwen2.5-7B-Instruct",
  "timestamp": 1234567890.0
}
```

## TensorZero Integration

Generate TensorZero configuration with:

```bash
curl http://localhost:8096/api/config/tensorzero
```

This generates TOML configuration for all catalog models that can be appended to `tensorzero.toml`.

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python main.py
```

## Testing

```bash
# From repo root — runs against in-memory state, no live HF/NATS needed
pytest pmoves/tests/services/test_hf_services.py -v
```

## License

MIT
