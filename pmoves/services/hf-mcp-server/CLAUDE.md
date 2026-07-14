# hf-mcp-server

Hugging Face MCP Server for PMOVES.AI — model discovery, download, caching,
and TensorZero config generation.

## Quick Start

```bash
# Standalone
docker compose -f pmoves/docker-compose/hf-mcp-server.yml up -d

# Full agents profile (includes hf-agent + hf-research-agent)
docker compose -f pmoves/docker-compose.yml --profile research up -d
```

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/healthz` | GET | Health check (PMOVES standard) |
| `/metrics` | GET | Prometheus metrics |
| `/api/model/search` | POST | Search catalog by tier/use_case |
| `/api/model/{id}` | GET | Model metadata from HF Hub |
| `/api/model/download` | POST | Download model to cache |
| `/api/models` | GET | List cached models |
| `/api/config/tensorzero` | GET | Generate TensorZero TOML |
| `/sse` | GET | MCP SSE endpoint |

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| `PORT` | `8096` | Server port |
| `HF_HOME` | `/models` | Model storage root |
| `HF_HUB_CACHE` | `/models/hub` | HF Hub cache |
| `HUGGINGFACE_HUB_TOKEN` | — | HF token (gated models) |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS for download events |

## NATS Events Published

- `hf.model.downloaded.v1` — model snapshot download completed

## Testing

```bash
pytest pmoves/tests/services/test_hf_services.py::TestHFMcpServer -v
```

## Related Services

- **hf-agent** (port 8201) — autonomous HF Hub patrol, publishes `hf.model.discovered.v1`
- **hf-research-agent** (port 8202) — evaluates discovered models, publishes `hf.model.evaluated.v1`
