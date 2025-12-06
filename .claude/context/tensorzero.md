# TensorZero - Primary Model Provider & Observability Gateway

**TensorZero is PMOVES.AI's centralized LLM gateway and observability platform.** It provides unified access to multiple model providers (OpenAI, Anthropic, Venice, Ollama) with comprehensive metrics collection via ClickHouse.

## Purpose

TensorZero serves three critical functions in PMOVES:

1. **Model Gateway** - Unified API for multiple LLM providers
2. **Observability** - ClickHouse-backed metrics collection and tracing
3. **Model Management** - Configuration-driven model selection and routing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 TensorZero Stack                            │
│                                                             │
│  tensorzero-gateway (Port 3030) ◄─── PMOVES Services       │
│         │                                                   │
│         ├──► Model Providers (OpenAI, Anthropic, etc.)     │
│         └──► tensorzero-clickhouse (Port 8123)             │
│                     │                                       │
│              tensorzero-ui (Port 4000)                      │
│              Metrics Dashboard & Admin                      │
└─────────────────────────────────────────────────────────────┘
```

## Services

### TensorZero Gateway [Port 3030]

**Image:** `tensorzero/gateway:latest`
**Purpose:** LLM gateway with observability
**Profiles:** `tensorzero`

**Configuration:**
- Config file: `pmoves/tensorzero/config/tensorzero.toml`
- Environment: `env.shared.generated`, `env.shared`, `.env.generated`, `.env.local`

**Key Features:**
- Multi-provider routing (OpenAI, Anthropic, Venice, Ollama)
- Request/response logging to ClickHouse
- Token usage tracking
- Latency metrics
- Error rate monitoring

**API Endpoint:**
```bash
TENSORZERO_BASE_URL=http://localhost:3030
```

### TensorZero ClickHouse [Port 8123]

**Image:** `clickhouse/clickhouse-server:24.12-alpine`
**Purpose:** Observability metrics storage
**Profiles:** `tensorzero`

**Configuration:**
```bash
TENSORZERO_CLICKHOUSE_USER=tensorzero
TENSORZERO_CLICKHOUSE_PASSWORD=tensorzero
TENSORZERO_CLICKHOUSE_URL=http://tensorzero:tensorzero@tensorzero-clickhouse:8123/default
```

**Health Check:**
```bash
curl http://localhost:8123/ping
```

**Data Storage:**
- Volume: `tensorzero-clickhouse-data`
- Tables: Request logs, token usage, latency metrics, error traces

### TensorZero UI [Port 4000]

**Image:** `tensorzero/ui:latest`
**Purpose:** Metrics dashboard and admin interface
**Profiles:** `tensorzero`

**Access:** `http://localhost:4000`

**Features:**
- Request/response inspection
- Token usage analytics
- Latency distribution graphs
- Error rate monitoring
- Model performance comparison

## Integration in PMOVES Services

TensorZero is integrated across PMOVES services:

### Hi-RAG v2 (CPU & GPU)

Uses TensorZero for embeddings:

```bash
# Environment variables in docker-compose.yml
TENSORZERO_BASE_URL=http://tensorzero-gateway:3000
TENSORZERO_API_KEY=
TENSORZERO_EMBED_MODEL=tensorzero::embedding_model_name::gemma_embed_local
```

**Usage:** Hi-RAG can optionally use TensorZero for embedding generation instead of local sentence-transformers.

### Archon

Uses TensorZero for LLM calls in agent workflows.

### Agent Zero

Can route LLM requests through TensorZero gateway.

### Extract Worker

Optional TensorZero integration for embedding generation.

## Configuration

### tensorzero.toml

**Location:** `pmoves/tensorzero/config/tensorzero.toml`

**Structure:**
```toml
[gateway]
observability.enabled = true

[gateway.observability.clickhouse]
url = "env::TENSORZERO_OBS_CLICKHOUSE_URL"
database = "env::TENSORZERO_OBS_CLICKHOUSE_DB"
username = "env::TENSORZERO_OBS_CLICKHOUSE_USER"
password = "env::TENSORZERO_OBS_CLICKHOUSE_PASSWORD"

# Model definitions
[models.gemma_embed_local]
provider = "ollama"
model = "gemma:2b"
type = "embedding"

[models.claude_sonnet]
provider = "anthropic"
model = "claude-sonnet-4-5"
type = "chat"

# ... additional models
```

### Environment Variables

**ClickHouse Connection:**
```bash
TENSORZERO_OBS_CLICKHOUSE_URL=http://tensorzero-clickhouse:8123
TENSORZERO_OBS_CLICKHOUSE_DB=tensorzero
TENSORZERO_OBS_CLICKHOUSE_USER=tensorzero
TENSORZERO_OBS_CLICKHOUSE_PASSWORD=tensorzero
```

**Gateway Configuration:**
```bash
TENSORZERO_BASE_URL=http://tensorzero-gateway:3000
TENSORZERO_API_KEY=  # Optional API key for gateway access
TENSORZERO_GATEWAY_URL=http://tensorzero-gateway:3000  # For UI
```

**Model Provider Keys:**
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
# ... other provider keys
```

## Starting TensorZero Stack

### Bring Up TensorZero

```bash
cd pmoves && make up-tensorzero
```

This starts:
- `tensorzero-clickhouse` - Metrics database
- `tensorzero-gateway` - Model gateway
- `tensorzero-ui` - Dashboard
- `pmoves-ollama` - Local Ollama for local models

### Verify Health

```bash
# ClickHouse
curl http://localhost:8123/ping

# Gateway
curl http://localhost:3030/health

# UI
curl http://localhost:4000
```

### Enable Observability

1. **Update config:** `pmoves/tensorzero/config/tensorzero.toml`
   ```toml
   [gateway]
   observability.enabled = true
   ```

2. **Restart gateway:**
   ```bash
   cd pmoves && docker compose restart tensorzero-gateway
   ```

3. **Verify observability:**
   Check gateway logs for: `observability exporter configured`

## Using TensorZero Gateway

### From PMOVES Services

Services use TensorZero via environment variables:

```python
import os
import requests

tensorzero_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3030")
api_key = os.getenv("TENSORZERO_API_KEY", "")

# Call via TensorZero gateway
response = requests.post(
    f"{tensorzero_url}/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
```

### From Command Line

```bash
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "Hello from TensorZero!"}]
  }'
```

### Embedding Generation

```bash
curl -X POST http://localhost:3030/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma_embed_local",
    "input": "Text to embed"
  }'
```

## Monitoring & Observability

### Query ClickHouse Metrics

```bash
# Connect to ClickHouse
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero \
  --password tensorzero

# Sample queries
SELECT COUNT(*) FROM requests;
SELECT model, COUNT(*) as count FROM requests GROUP BY model;
SELECT AVG(latency_ms) FROM requests WHERE model = 'claude-sonnet-4-5';
```

### View Metrics in UI

1. **Access dashboard:** `http://localhost:4000`
2. **Browse requests** - See all LLM requests/responses
3. **Analyze usage** - Token counts by model, time period
4. **Monitor latency** - P50, P95, P99 latencies
5. **Track errors** - Error rates and failure patterns

### Prometheus Integration

TensorZero metrics can be exposed to Prometheus:

```yaml
# In prometheus.yml
scrape_configs:
  - job_name: 'tensorzero'
    static_configs:
      - targets: ['tensorzero-gateway:3000']
    metrics_path: '/metrics'
```

## Model Configuration

### Adding New Models

Edit `pmoves/tensorzero/config/tensorzero.toml`:

```toml
[models.my_new_model]
provider = "openai"  # or "anthropic", "ollama", "venice"
model = "gpt-4"
type = "chat"  # or "embedding"

# Optional parameters
temperature = 0.7
max_tokens = 1000
```

### Provider Configuration

**OpenAI:**
```toml
[providers.openai]
api_key = "env::OPENAI_API_KEY"
```

**Anthropic:**
```toml
[providers.anthropic]
api_key = "env::ANTHROPIC_API_KEY"
```

**Ollama (Local):**
```toml
[providers.ollama]
base_url = "http://pmoves-ollama:11434"
```

**Venice.ai:**
```toml
[providers.venice]
api_key = "env::VENICE_API_KEY"
base_url = "https://api.venice.ai/v1"
```

## Common Tasks

### Switch Model Provider

Update service environment or TensorZero config:

```bash
# Use TensorZero for embeddings
USE_OLLAMA_EMBED=false
TENSORZERO_EMBED_MODEL=tensorzero::embedding_model_name::gemma_embed_local

# Use Ollama directly
USE_OLLAMA_EMBED=true
OLLAMA_EMBED_MODEL=embeddinggemma:300m
```

### View Request Logs

```bash
# Via ClickHouse
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero \
  --password tensorzero \
  --query "SELECT timestamp, model, request_tokens, response_tokens, latency_ms FROM requests ORDER BY timestamp DESC LIMIT 10;"
```

### Export Metrics

```bash
# Export to JSON
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero \
  --password tensorzero \
  --query "SELECT * FROM requests FORMAT JSONEachRow" > tensorzero-metrics.json
```

### Backup ClickHouse Data

```bash
# Create backup
docker exec tensorzero-clickhouse clickhouse-client \
  --user tensorzero \
  --password tensorzero \
  --query "BACKUP DATABASE tensorzero TO Disk('backups', 'tensorzero_backup.zip')"
```

## Troubleshooting

### Gateway Won't Start

**Check ClickHouse:**
```bash
docker compose logs tensorzero-clickhouse
curl http://localhost:8123/ping
```

**Check config syntax:**
```bash
docker compose logs tensorzero-gateway | grep "error\|unknown field"
```

**Common issue:** `clickhouse: unknown field` means config uses legacy format. Update to `gateway.observability.clickhouse.*` structure.

### Observability Not Working

1. **Enable in config:**
   ```toml
   [gateway]
   observability.enabled = true
   ```

2. **Check credentials:**
   ```bash
   docker compose exec tensorzero-gateway env | grep TENSORZERO
   ```

3. **Verify ClickHouse tables:**
   ```bash
   docker exec -it tensorzero-clickhouse clickhouse-client \
     --user tensorzero \
     --password tensorzero \
     --query "SHOW TABLES"
   ```

### High Latency

**Check Prometheus metrics:**
```promql
histogram_quantile(0.95, rate(tensorzero_request_duration_seconds_bucket[5m]))
```

**Query ClickHouse for slow requests:**
```sql
SELECT model, AVG(latency_ms), MAX(latency_ms)
FROM requests
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY model
ORDER BY AVG(latency_ms) DESC;
```

## Best Practices

1. **Use TensorZero for production** - Centralized observability
2. **Enable ClickHouse observability** - Track all LLM usage
3. **Monitor token costs** - Query ClickHouse for usage analytics
4. **Configure model fallbacks** - TensorZero can route on failure
5. **Rotate logs periodically** - ClickHouse data can grow large
6. **Use UI for debugging** - Inspect individual request/response
7. **Export metrics to Prometheus** - Integrate with existing monitoring

## Integration with PMOVES Monitoring

TensorZero integrates with PMOVES observability stack:

- **Prometheus** - Scrape TensorZero metrics at `/metrics`
- **Grafana** - Dashboard for TensorZero latency, usage, errors
- **Loki** - Aggregate TensorZero gateway logs
- **ClickHouse** - Long-term metrics storage and analytics

## References

- TensorZero GitHub: https://github.com/tensorzero/tensorzero
- Config: `pmoves/tensorzero/config/tensorzero.toml`
- Observability notes: `pmoves/docs/services/open-notebook/TENSORZERO_OBSERVABILITY_NOTES.md`
- Venice integration: `pmoves/docs/venice-tensorzero-integration/`
- Model management: `pmoves/model-management/README.md`

## Developer Notes

**For Claude Code CLI users:**
- TensorZero provides unified LLM access across PMOVES
- All model calls should route through TensorZero for observability
- Check ClickHouse for usage analytics and debugging
- UI at `localhost:4000` for request inspection
- Configuration changes require gateway restart
- Observability is disabled by default - enable in production
