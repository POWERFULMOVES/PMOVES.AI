# Model Registry

Supabase-backed model configuration service for PMOVES.AI. Provides dynamic model discovery, TensorZero TOML generation, and GPU orchestrator integration.

## Overview

The Model Registry replaces hardcoded TensorZero configuration with a database-driven approach. It enables:
- **Dynamic model routing** - Switch models without code changes
- **Service discovery** - GPU nodes announce available models via NATS
- **TensorZero integration** - Auto-generate TOML config from database
- **Deployment tracking** - Monitor which models are loaded on which nodes

## Service & Ports
- Compose service: `model-registry`
- Port: `:8110` (HTTP API)

## Health
- Healthz: `GET /healthz` returns 200 when service is healthy
- Metrics: `GET /metrics` returns Prometheus-compatible metrics

## Quick Start

```bash
# Start with orchestration profile
docker compose --profile orchestration up -d model-registry

# Verify health
curl http://localhost:8110/healthz

# List all models
curl http://localhost:8110/api/models

# Get TensorZero TOML config
curl http://localhost:8110/api/tensorzero/config
```

## API Endpoints

### Models
- `GET /api/models` - List all models with provider details
- `GET /api/models/{id}` - Get specific model
- `POST /api/models` - Create new model (authenticated)
- `PUT /api/models/{id}` - Update model (authenticated)
- `DELETE /api/models/{id}` - Delete model (authenticated)

### Providers
- `GET /api/providers` - List all providers
- `GET /api/providers/{id}` - Get specific provider
- `POST /api/providers` - Create new provider (authenticated)

### Service Mappings
- `GET /api/mappings` - List all service-to-model mappings
- `GET /api/mappings/{service_name}` - Get mappings for a service
- `POST /api/mappings` - Create new mapping (authenticated)

### TensorZero Integration
- `GET /api/tensorzero/config` - Generate TensorZero TOML from database
- `GET /api/tensorzero/functions` - Get function definitions

### Deployments
- `GET /api/deployments` - List active model deployments
- `POST /api/deployments/register` - Register model deployment (GPU orchestrator)
- `PUT /api/deployments/{id}/status` - Update deployment status

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | `http://host.docker.internal:54321` | Supabase API URL |
| `SUPABASE_SERVICE_KEY` | - | Supabase service role key (required) |
| `MODEL_REGISTRY_PORT` | `8110` | Service port |
| `DOCKED_MODE` | `true` | Enable Docker-specific features |

## Database Schema

See `/pmoves/supabase/migrations/20260115_model_registry.sql` for full schema.

### Tables
- `model_providers` - LLM/API provider configurations
- `models` - Individual model definitions
- `model_aliases` - UI-friendly naming
- `service_model_mappings` - Service-to-model routing
- `model_deployments` - Live deployment tracking

### Views
- `v_active_models` - Active models with providers
- `v_service_models` - Service mappings with full details
- `v_active_deployments` - Deployments grouped by node

## TensorZero Migration

Import existing TensorZero configuration:

```bash
# Dry run to preview
python pmoves/services/model-registry/migrate_tensorzero.py \
  --config-path pmoves/tensorzero/config/tensorzero.toml \
  --dry-run

# Run migration
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_KEY=your-service-key

python pmoves/services/model-registry/migrate_tensorzero.py
```

## GPU Orchestrator Integration

GPU nodes publish deployment status via NATS:

```
Subject: mesh.gpu.model.loaded.v1
{
  "node_id": "gpu-node-1",
  "provider_type": "ollama",
  "model_id": "qwen3:8b",
  "vram_allocated_mb": 8000,
  "status": "loaded"
}
```

The registry updates `model_deployments` table automatically.

## Docker Compose Profile

Model Registry is included in the `orchestration` profile:

```bash
# Start orchestration profile
docker compose --profile orchestration up -d

# View logs
docker compose logs -f model-registry

# Restart
docker compose restart model-registry
```

## Dependencies

- **Supabase** (PostgREST) - Required for all operations
- **NATS** - Optional, for GPU orchestrator events

## Troubleshooting

### Service won't start
- Verify Supabase is running: `curl http://localhost:54321/rest/v1/`
- Check `SUPABASE_SERVICE_KEY` is set correctly
- Review logs: `docker compose logs model-registry`

### Empty models list
- Run seed script: `psql -f pmoves/supabase/initdb/12_model_registry_seed.sql`
- Or run migration: `python migrate_tensorzero.py`

### TensorZero config errors
- Verify all models have valid providers
- Check required fields: `name`, `model_id`, `model_type`
- Ensure `api_base` is set for external providers

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  GPU Orchestrator│────▶│ Model Registry│────▶│   Supabase  │
│  (NATS publish) │     │   (FastAPI)  │     │  PostgreSQL │
└─────────────────┘     └──────────────┘     └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  TensorZero  │
                        │ (TOML gen)   │
                        └──────────────┘
```

## See Also

- Migration: `/pmoves/supabase/migrations/20260115_model_registry.sql`
- Seed data: `/pmoves/supabase/initdb/12_model_registry_seed.sql`
- Architecture docs: `/pmoves/docs/MODEL_REGISTRY.md`
