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

---

## 7. Audio Model Architecture Extension

### 7.1 Overview

**Status:** ⚠️ **IN PROGRESS** - Architecture defined, implementation pending

All audio/speech models should route through TensorZero Gateway with GPU Orchestrator managing local providers:

```
Services → TensorZero Gateway → GPU Orchestrator → Local Providers (Ollama, Whisper, TTS)
                                      ↓
                              Legacy Fallback (Cloud APIs)
```

### 7.2 Current State

| Component | Status | Notes |
|-----------|--------|-------|
| GPU Orchestrator | ✅ Running (port 8200) | Providers: ollama, vllm, tts |
| TensorZero Gateway | ✅ Running (port 3030) | Chat + Embedding configured |
| Whisper Support | ❌ Missing | Need whisper_client.py + TensorZero config |
| TTS Support | ⚠️ Partial | GPU Orchestrator has tts_client.py, no TensorZero config |

### 7.3 Implementation Tasks

**Priority 1: Add Whisper to GPU Orchestrator**
- Create `services/whisper_client.py` (pattern after `tts_client.py`)
- Add to `model_lifecycle.py` provider list
- Add Whisper models to `config/gpu-models.yaml`

**Priority 2: Configure Audio Models in TensorZero**
```toml
# Whisper transcription
[models.whisper_small]
routing = ["ollama"]  # or gpu_orchestrator when implemented
[models.whisper_small.providers.ollama]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "whisper-small"
api_key_location = "none"

# TTS synthesis
[models.tts_kokoro]
routing = ["gpu_orchestrator"]
[models.tts_kokoro.providers.gpu_orchestrator]
type = "openai"
api_base = "http://pmoves-gpu-orchestrator:8200/tts"
model_name = "kokoro"
```

**Priority 3: Service Migration**
- `ffmpeg-whisper` → Call TensorZero instead of direct model execution
- `pmoves-yt` → Use TensorZero transcription function
- `flute-gateway` → Use TensorZero TTS routing

### 7.4 Model Collections by Service

| Service | Function | Models | Fallback |
|---------|----------|--------|----------|
| PMOVES.YT | `pmoves_yt_transcription` | whisper_small, whisper_medium | OpenAI Whisper |
| Flute-Gateway | `flute_tts_synthesis` | kokoro, f5-tts, kitten-tts | ElevenLabs |
| Hi-RAG V2 | `hirag_vl_analysis` | qwen2_vl_7b | GPT-4V, Gemini Vision |

### 7.5 References

- Main doc: `docs/tz.md` (Section 11: Audio Model Architecture)
- GPU Orchestrator: `pmoves/services/gpu-orchestrator/`
- TensorZero Config: `pmoves/tensorzero/config/tensorzero.toml`
