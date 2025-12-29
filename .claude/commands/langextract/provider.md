# LangExtract Provider

Show available providers and current configuration.

## Instructions

1. Query the /provider endpoint to get current configuration
2. List all available providers and their capabilities
3. Show relevant environment variables

```bash
curl -s http://localhost:8084/provider | jq .
```

## Available Providers

| Provider | Description | Env Vars |
|----------|-------------|----------|
| `rule` | Rule-based chunking (default, no LLM) | None |
| `orchestrator` | MCP tools + TensorZero coordination | ORCHESTRATOR_*, MCP_* |
| `tensorzero` | Direct TensorZero LLM chunking | TENSORZERO_* |
| `openai` | OpenAI API for chunking | OPENAI_API_KEY |
| `gemini` | Google Gemini API | GEMINI_API_KEY |
| `cloudflare` | Cloudflare Workers AI | CLOUDFLARE_* |

## Key Environment Variables

```bash
# Provider selection
LANGEXTRACT_PROVIDER=orchestrator

# Orchestrator settings
ORCHESTRATOR_AUTO_INGEST=true
ORCHESTRATOR_USE_DOCLING=true
ORCHESTRATOR_USE_VL=false

# TensorZero (used by orchestrator)
TENSORZERO_BASE_URL=http://tensorzero-gateway:3030
TENSORZERO_MODEL=langextract

# MCP endpoints (used by orchestrator)
MCP_GATEWAY_URL=http://localhost:2091
DOCLING_URL=http://pmz-docling-mcp:3020
EXTRACT_WORKER_URL=http://extract-worker:8083
```

Report:
- Current active provider
- Orchestrator settings if applicable
- Suggestions for switching providers based on use case
