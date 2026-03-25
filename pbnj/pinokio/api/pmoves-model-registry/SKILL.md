---
name: PMOVES Model Registry
description: |
  Query, discover, and enrich the PMOVES.AI model catalog. Manages all AI model
  metadata (LLM, embedding, TTS, vision), HuggingFace enrichment, TensorZero
  TOML config export, and GPU deployment tracking across the fleet.
keywords: models, registry, catalog, embedding, llm, tensorzero, huggingface, gpu, deployment, discovery
version: 1.0.0
category: Infrastructure/AI
tier: 1
agent_class: Standard
agent_id: pmoves_model_registry
---

# PMOVES Model Registry

**Agent Class**: `Standard (Pmoves-)`
**Category**: Infrastructure/AI
**Version**: 1.0.0
**Tier**: 1 (Core Infrastructure)
**Status**: Active — Supabase-backed model catalog + HuggingFace enrichment
**Port**: 8110

---

## Capabilities

| Command | What It Does |
|---------|-------------|
| `list-models` | List all active models with optional type/provider filter |
| `get-model` | Get detailed metadata for a single model by ID |
| `enrich-hf` | Fetch dimensions, tags, CUDA support from HuggingFace API |
| `enrich-hf-bulk` | Batch-enrich all models that have hf_id in metadata |
| `export-tensorzero` | Generate TensorZero TOML config from catalog |
| `list-deployments` | Show active GPU model deployments across fleet |
| `register-deployment` | Register/update a model deployment (GPU Orchestrator) |
| `service-models` | List models mapped to a specific service |

---

## Trigger Phrases (Pinokio 7 Interpreter)

| Phrase | Action | Endpoint |
|--------|--------|----------|
| `"list available models"` | Show full model catalog | `GET /api/models` |
| `"show embedding models"` | Filter catalog by type | `GET /api/models?model_type=embedding` |
| `"show LLM models"` | Filter catalog by type | `GET /api/models?model_type=llm` |
| `"get model details for [id]"` | Single model lookup | `GET /api/models/{id}` |
| `"enrich model from huggingface"` | Fetch HF metadata + dimensions | `POST /api/models/{id}/enrich-hf` |
| `"enrich all embedding models"` | Batch HF enrichment | `POST /api/models/enrich-hf-bulk` |
| `"export tensorzero config"` | Download TensorZero TOML | `GET /api/tensorzero/config` |
| `"show GPU deployments"` | List active model deployments | `GET /api/deployments` |
| `"which models are on 5090"` | Filter deployments by node | `GET /api/deployments?node_id=5090` |
| `"what models does hi-rag use"` | Service-specific model lookup | `GET /api/services/hi-rag/models` |

---

## API Reference

### Model Catalog

```bash
# List all models
curl http://localhost:8110/api/models

# Filter by type (embedding, llm, tts, vision, audio)
curl http://localhost:8110/api/models?model_type=embedding

# Filter by provider (ollama, openai, anthropic, venice)
curl http://localhost:8110/api/models?provider=ollama

# Get single model
curl http://localhost:8110/api/models/{model_id}

# Models for a service
curl http://localhost:8110/api/services/hi-rag/models
```

### HuggingFace Enrichment

```bash
# Enrich a single model (requires metadata.hf_id set)
curl -X POST http://localhost:8110/api/models/{model_id}/enrich-hf

# Batch-enrich all embedding models
curl -X POST http://localhost:8110/api/models/enrich-hf-bulk?model_type=embedding
```

### TensorZero Config Export

```bash
# Generate TOML config from catalog
curl http://localhost:8110/api/tensorzero/config -o tensorzero.toml
```

### GPU Deployments

```bash
# List active deployments
curl http://localhost:8110/api/deployments

# Filter by node
curl http://localhost:8110/api/deployments?node_id=5090

# Filter by status
curl http://localhost:8110/api/deployments?status=loaded
```

---

## Health Check

```bash
curl http://localhost:8110/healthz
# → {"status": "healthy", "timestamp": "...", "services": {"supabase": "...", "nats": "..."}}
```

---

## Integration Points

- **Supabase** — `pmoves_core.models`, `pmoves_core.model_service_mapping`, `pmoves_core.v_active_deployments`
- **NATS** — Publishes `model.registry.updated.v1` on catalog mutations (model enriched, deployment registered)
- **GPU Orchestrator** — Calls `POST /api/deployments` when models are loaded/unloaded on GPU nodes
- **TensorZero Gateway** — Consumes exported TOML config for model provider routing
- **HuggingFace API** — Fetches model cards, config.json for embedding dimensions, tags, CUDA support

---

## Prerequisites

- Supabase running with `pmoves_core` schema seeded
- NATS message bus at port 4222 (optional — catalog changes still work without NATS)
- HuggingFace API accessible (no auth required for public models)
