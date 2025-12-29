# TensorZero Implementation Review & Roadmap

**Date:** 2025-12-21
**Status:** Local-First Architecture Established
**Architecture:** Local First, Cloud Hybrid

## 1. Executive Summary

PMOVES.AI uses a **Local-First, Cloud-Hybrid** architecture for LLM routing:

**Routing Priority:**
1. **Local (Ollama)** - qwen3:8b, qwen2.5:14b/32b for cost-effective local inference on RTX 5090
2. **Anthropic** - claude-sonnet-4-5 for complex reasoning tasks
3. **Gemini Flash** - gemini-2.0-flash-exp as cost-effective cloud backup

We have established a production-ready TensorZero Gateway with:
- 15+ local Ollama models configured
- 10+ cloud provider integrations (Anthropic, Gemini, OpenRouter, Venice, etc.)
- Full observability via ClickHouse
- Supabase Postgres integration for API key management

**Next Phase:** Implement feedback metrics and tool definitions to enable optimization.

## 2. Current State vs. Best Practices

| Feature | Current Implementation | Best Practice | Status |
| :--- | :--- | :--- | :--- |
| **Routing** | Local-first with cloud fallback | Dynamic / Fallback | **DONE:** 15+ Ollama models + 10+ cloud providers |
| **Tools** | `web_search` defined | Explicit `[tools.*]` Schemas | **PARTIAL:** Need hirag_query, file_read |
| **Prompts** | `system.minijinja` templates | Server-Side Templates | **DONE:** Orchestrator function templated |
| **Schema** | Loose (Implicit JSON) | Strict `user_schema` / `output_schema` | **TODO:** Add for structured extraction |
| **Feedback** | None | `[metrics.*]` (Boolean/Float) | **TODO:** Critical for optimization |

## 3. What's Already Implemented

### A. Local-First Model Configuration
15+ Ollama models configured for local inference:
- **Agent Zero:** qwen:14b, mistral:7b, phi3:3.8b
- **LangExtract:** qwen3:8b
- **General:** qwen2.5:14b, qwen2.5:32b, llama3.1
- **Vision:** qwen2-vl:7b
- **Reranking:** qwen3-reranker:4b
- **Embeddings:** qwen3-embedding:4b/8b, nomic-embed-text

### B. Cloud Provider Fallbacks
10+ cloud providers configured as fallback:
- OpenAI, Groq, Moonshot, OpenRouter, Venice, Together AI, Cloudflare

### C. Templated Prompts (DONE)
`functions/orchestrator/system.minijinja` provides dynamic system prompts for Agent Zero.

### D. Tool Definition (PARTIAL)
`web_search` tool defined in `tools/web_search.json`.

## 4. Remaining Gaps

### A. Additional Tool Definitions
**Priority: MEDIUM**
```toml
[tools.hirag_query]
description = "Query the Hi-RAG knowledge base"
parameters = "tools/hirag_query.json"

[tools.file_read]
description = "Read file contents"
parameters = "tools/file_read.json"
```

### B. Feedback Metrics
**Priority: HIGH** - Required for optimization
```toml
[metrics.task_success]
type = "boolean"
optimize = "max"
level = "inference"

[metrics.user_satisfaction]
type = "float"
optimize = "max"
level = "inference"
```

### C. Structured Output Schemas
**Priority: MEDIUM**
Convert `coding` function to use `json_mode = "strict"` for validated code blocks.

## 5. Architecture Principle: TensorZero as Single Source of Truth

**Critical:** All model configuration lives ONLY in `tensorzero.toml`. No hardcoded models in:
- Docker compose files
- Python services
- Environment variables (except API keys)

### Why This Matters
- Change models in ONE place
- Query available models via TensorZero API
- Ollama can proxy cloud models (e.g., `nemotron-3-nano:30b-cloud`, `gemini-3-flash-preview:cloud`)
- Unified observability regardless of provider

### Model Discovery
```bash
# List available models from TensorZero
curl http://localhost:3030/v1/models

# Check model routing
curl http://localhost:3030/status
```

### Cloud-via-Ollama Pattern
Ollama can proxy cloud providers, keeping TensorZero → Ollama as unified path:
```bash
ollama run nemotron-3-nano:30b-cloud    # NVIDIA cloud-backed
ollama run gemini-3-flash-preview:cloud  # Google cloud-backed
```

## 6. Next Steps

1. **Define Metrics** - Add `[metrics.*]` sections for feedback collection
2. **Add Tools** - Define hirag_query, file_read, cipher_memory tools in `tensorzero.toml`
3. **Test Cloud-via-Ollama** - Verify cloud models accessible through Ollama proxy
4. **Document Model List** - Create dynamic model catalog from TensorZero API
