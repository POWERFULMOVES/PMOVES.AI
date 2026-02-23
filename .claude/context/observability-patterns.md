# Observability Patterns Reference

Practical observability reference for monitoring, debugging, and diagnosing PMOVES.AI services.

## Prometheus (Port 9090)

### Scrape Configuration

Located in `pmoves/monitoring/prometheus/prometheus.yml`. All services are scraped at `/metrics`.

### Standard Metric Names

Services SHOULD expose these metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests by method/path/status |
| `http_request_duration_seconds` | Histogram | Request latency |
| `nats_messages_published_total` | Counter | NATS messages published |
| `nats_messages_received_total` | Counter | NATS messages consumed |
| `process_resident_memory_bytes` | Gauge | Memory usage |

### Useful PromQL Queries

```promql
# Service availability (which services are up?)
up

# Request rate per service (5m window)
rate(http_requests_total[5m])

# P95 request latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate (5xx responses)
rate(http_requests_total{status=~"5.."}[5m])

# Memory usage by container
container_memory_usage_bytes{name=~"pmoves.*"}

# NATS message throughput
rate(nats_messages_published_total[5m])
```

### Access

```bash
# Query API
curl 'http://localhost:9090/api/v1/query?query=up'

# Range query (last hour)
curl 'http://localhost:9090/api/v1/query_range?query=up&start=2026-01-01T00:00:00Z&end=2026-01-01T01:00:00Z&step=60s'
```

## Grafana (Port 3002)

### Datasources

| Name | Type | URL |
|------|------|-----|
| Prometheus | prometheus | `http://prometheus:9090` |
| Loki | loki | `http://loki:3100` |

### Dashboards

- **Services Overview** — Pre-configured dashboard showing all service health, latency, and throughput
- Custom dashboards can be provisioned via `pmoves/monitoring/grafana/dashboards/`

### Access

```bash
# Default credentials (change for production)
open http://localhost:3002
# admin / admin (first login)
```

## Loki (Port 3100) + Promtail

### Label Scheme

All services are labeled by Promtail with:

| Label | Description | Example |
|-------|-------------|---------|
| `job` | Service name | `agent-zero` |
| `container` | Docker container name | `pmoves-agent-zero` |
| `compose_service` | Compose service name | `agent-zero` |

### LogQL Query Examples

```logql
# All logs from a service
{job="agent-zero"}

# Error logs only
{job="agent-zero"} |= "ERROR"

# Filter by pattern
{job="hirag-gateway"} |~ "query.*timeout"

# JSON log parsing
{job="channel-monitor"} | json | level="error"

# Rate of errors (for alerting)
rate({job=~"pmoves.*"} |= "ERROR" [5m])
```

### Access

```bash
# Query API
curl -G 'http://localhost:3100/loki/api/v1/query' \
  --data-urlencode 'query={job="agent-zero"} |= "ERROR"'

# Via Grafana Explore
open http://localhost:3002/explore
```

## TensorZero Metrics (ClickHouse)

### ClickHouse (Port 8123)

Stores all LLM request/response data for TensorZero Gateway.

```bash
# Ping
curl http://localhost:8123/ping

# Query via CLI
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero

# Request count by model
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero \
  --query "SELECT model, COUNT(*) as cnt FROM requests GROUP BY model ORDER BY cnt DESC"

# Token usage summary
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero \
  --query "SELECT model, SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion FROM requests GROUP BY model"
```

### TensorZero UI (Port 4000)

Web dashboard for request inspection, usage analytics, and model performance comparison.

```bash
open http://localhost:4000
```

## Health Check Convention

### Standard Format

All PMOVES.AI services expose `GET /healthz` returning:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "dependencies": {
    "nats": "connected",
    "supabase": "connected"
  }
}
```

### Docker HEALTHCHECK

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Quick Health Check (All Services)

```bash
# Via make target
cd pmoves && make verify-all

# Via skill
/health:check-all

# Manual spot check
for port in 8080 8086 8077 8091 8097; do
  echo "Port $port: $(curl -sf http://localhost:$port/healthz | jq -r .status 2>/dev/null || echo 'DOWN')"
done
```

## Service Ports Quick Reference

| Port | Service | Health | Metrics |
|------|---------|--------|---------|
| 8080 | Agent Zero API | /healthz | /metrics |
| 8081 | Agent Zero UI | - | - |
| 8086 | Hi-RAG v2 (CPU) | /healthz | /metrics |
| 8087 | Hi-RAG v2 (GPU) | /healthz | /metrics |
| 8077 | PMOVES.YT | /healthz | /metrics |
| 8091 | Archon API | /healthz | /metrics |
| 8097 | Channel Monitor | /healthz | /metrics |
| 8099 | SupaSerch | /healthz | /metrics |
| 3030 | TensorZero Gateway | /health | /metrics |
| 9090 | Prometheus | /-/healthy | - |
| 3002 | Grafana | /api/health | - |
| 3100 | Loki | /ready | /metrics |
