# Model Registry Architecture

Supabase-backed dynamic model configuration for PMOVES.AI. Replaces hardcoded TensorZero TOML with database-driven model routing, service discovery, and GPU deployment tracking.

## Overview

The Model Registry enables PMOVES.AI to dynamically route LLM requests to appropriate models without code changes. It integrates with TensorZero, GPU Orchestrator, and NATS for complete model lifecycle management.

### Key Benefits

- **Zero-downtime model changes** - Update routing via database
- **GPU discovery** - Automatic model availability tracking
- **Multi-region support** - Route to closest/available models
- **A/B testing** - Weighted routing between models
- **Fallback handling** - Automatic failover configuration

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PMOVES.AI Model Layer                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────────────┐  │
│  │   Services   │─────▶│ Model        │─────▶│    Supabase              │  │
│  │              │      │ Registry     │      │  ┌─────────────────────┐  │  │
│  │ • Agent Zero │      │ (FastAPI)    │      │  │ model_providers     │  │  │
│  │ • Archon     │      │ Port: 8110   │      │  │ models              │  │  │
│  │ • DeepResearch│     │              │      │  │ service_model_      │  │  │
│  │ • TensorZero │      │              │      │  │   mappings          │  │  │
│  └──────────────┘      └──────┬───────┘      │  │ model_deployments   │  │  │
│                               │              │  └─────────────────────┘  │  │
│                               │              └───────────────────────────┘  │
│                               ▼                                              │
│                      ┌──────────────┐                                       │
│                      │ TensorZero   │                                       │
│                      │ TOML Generator│                                       │
│                      └──────────────┘                                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                              GPU Orchestrator                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   GPU Nodes ──NATS──▶ mesh.gpu.model.loaded.v1 ──▶ Model Registry           │
│   GPU Nodes ──NATS──▶ mesh.gpu.model.unloaded.v1 ──▶ Model Registry         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Database Schema

### model_providers

LLM/API provider configurations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | TEXT | Unique provider name |
| `type` | TEXT | ollama, openai_compatible, anthropic, vllm, custom |
| `api_base` | TEXT | Base URL for API requests |
| `api_key_env_var` | TEXT | Environment variable containing API key |
| `description` | TEXT | Human-readable description |
| `metadata` | JSONB | Additional provider settings |
| `active` | BOOLEAN | Enable/disable provider |

### models

Individual model definitions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `provider_id` | UUID | FK to model_providers |
| `name` | TEXT | Display name |
| `model_id` | TEXT | Provider-specific model identifier |
| `model_type` | TEXT | chat, embedding, reranker, vl, tts, audio, image |
| `capabilities` | JSONB | Array of capabilities (function_calling, vision, etc.) |
| `vram_mb` | INTEGER | VRAM required for local models |
| `context_length` | INTEGER | Maximum context window |
| `description` | TEXT | Human-readable description |
| `active` | BOOLEAN | Enable/disable model |

### service_model_mappings

Service-to-model routing configuration (replaces TensorZero variants).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `service_name` | TEXT | agent_zero, langextract, deepresearch, etc. |
| `function_name` | TEXT | chat, nlp, planning, embeddings, etc. |
| `model_id` | UUID | FK to models |
| `variant_name` | TEXT | local, cloud, fast, accurate, etc. |
| `priority` | INTEGER | Lower = higher priority |
| `weight` | DECIMAL | For weighted A/B routing (0.0-1.0) |
| `fallback_model_id` | UUID | FK to models for failover |

### model_deployments

Live tracking of model deployments on GPU nodes.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `model_id` | UUID | FK to models |
| `node_id` | TEXT | GPU node hostname/identifier |
| `provider_type` | TEXT | ollama, vllm, tts, custom |
| `status` | TEXT | loading, loaded, unloaded, error |
| `vram_allocated_mb` | INTEGER | Actual VRAM usage |
| `loaded_at` | TIMESTAMPTZ | When model was loaded |
| `last_used_at` | TIMESTAMPTZ | Last inference request |
| `error_message` | TEXT | Error details if status=error |

### model_aliases

UI-friendly naming and context-specific references.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `model_id` | UUID | FK to models |
| `alias` | TEXT | Display alias |
| `context` | TEXT | agent_zero, default, tensorzero, etc. |

## Service Discovery Pattern

GPU nodes announce available models via NATS:

```
Subject: mesh.gpu.model.loaded.v1
{
  "node_id": "gpu-node-1",
  "provider_type": "ollama",
  "model_id": "qwen3:8b",
  "model_name": "qwen3_8b_local",
  "vram_allocated_mb": 8000,
  "status": "loaded",
  "timestamp": "2025-01-15T12:00:00Z"
}
```

Model Registry subscribes and updates `model_deployments` table.

## TensorZero Integration

### TOML Generation

The registry generates TensorZero-compatible TOML:

```
GET /api/tensorzero/config
```

Response:
```toml
[gateway]

[models.agent_zero_qwen8b]
routing = ["ollama_local"]

[models.agent_zero_qwen8b.providers.ollama_local]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "qwen3:8b"
api_key_location = "none"

[functions.agent_zero]
type = "chat"

[functions.agent_zero.variants.local_qwen8b]
type = "chat_completion"
model = "agent_zero_qwen8b"
weight = 1.0
```

### Variant Mapping

Database mappings translate to TensorZero variants:

| Database | TensorZero |
|----------|------------|
| `service_name` | `[functions.{service_name}]` |
| `function_name` | N/A (chat functions use service) |
| `variant_name` | `[functions.{service}.variants.{variant}]` |
| `model_id` | `model = {model.name}` |
| `weight` | `weight = {weight}` |

## API Endpoints

### Models

```
GET    /api/models              # List all models
GET    /api/models/{id}         # Get specific model
POST   /api/models              # Create model (auth)
PUT    /api/models/{id}         # Update model (auth)
DELETE /api/models/{id}         # Delete model (auth)
```

### Providers

```
GET    /api/providers           # List all providers
GET    /api/providers/{id}      # Get specific provider
POST   /api/providers           # Create provider (auth)
```

### Mappings

```
GET    /api/mappings            # List all mappings
GET    /api/mappings/{service}  # Get service mappings
POST   /api/mappings            # Create mapping (auth)
```

### TensorZero

```
GET    /api/tensorzero/config   # Generate TOML
GET    /api/tensorzero/functions # Get functions only
```

### Deployments

```
GET    /api/deployments         # List active deployments
POST   /api/deployments/register # Register deployment
PUT    /api/deployments/{id}/status # Update status
```

## Routing Algorithm

1. **Query mappings** for service/function
2. **Filter** by active models and providers
3. **Sort** by priority (ASC), then weight (DESC)
4. **Check deployment status** if provider_type = ollama/vllm
5. **Select** first available model
6. **Fallback** to fallback_model_id on error

## Port Assignment

| Port | Service | Description |
|------|---------|-------------|
| 8110 | Model Registry | HTTP API |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes | - | Supabase API URL |
| `SUPABASE_SERVICE_KEY` | Yes | - | Service role key |
| `MODEL_REGISTRY_PORT` | No | 8110 | Service port |
| `DOCKED_MODE` | No | true | Docker mode flag |

## Migration from TensorZero TOML

```bash
# Install dependencies
pip install tomli httpx

# Run migration
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_KEY=your-key

python pmoves/services/model-registry/migrate_tensorzero.py \
  --config-path pmoves/tensorzero/config/tensorzero.toml
```

The parser extracts:
- Providers from `[models.*.providers.*]` sections
- Models with capabilities inferred from names
- Functions and variants from `[functions.*.variants.*]`

## Troubleshooting

### Empty models list
1. Check migration ran: `SELECT COUNT(*) FROM pmoves_core.models`
2. Verify seed data: `psql -f pmoves/supabase/initdb/12_model_registry_seed.sql`
3. Confirm RLS policies allow access

### TOML generation errors
1. Verify all models have valid providers
2. Check required fields: `name`, `model_id`, `model_type`, `provider_id`
3. Ensure `api_base` is set for external providers

### Deployment tracking not working
1. Verify NATS connectivity: `nats pub mesh.gpu.model.loaded.v1 '{"test": true}'`
2. Check service subscribes: `docker compose logs model-registry | grep NATS`
3. Confirm table has records: `SELECT * FROM pmoves_core.model_deployments`

## References

- Migration: `pmoves/supabase/migrations/20260115_model_registry.sql`
- Seed: `pmoves/supabase/initdb/12_model_registry_seed.sql`
- Service: `pmoves/services/model-registry/`
- Docker: `pmoves/docker-compose.yml` (model-registry service)
