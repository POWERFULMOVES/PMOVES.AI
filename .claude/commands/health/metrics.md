Query Prometheus for service metrics and observability data.

Prometheus collects metrics from all PMOVES services (exposed via `/metrics` endpoints) and provides a powerful query API for monitoring service health, performance, and resource usage.

## Usage

Run this command to:
- Check service status and uptime
- Query request rates and latencies
- Monitor resource usage (CPU, memory, network)
- Analyze service-specific metrics (task counts, queue depths, etc.)
- Debug performance issues
- Validate system health before deployments

## Implementation

Execute the following steps:

1. **Verify Prometheus is running:**
   ```bash
   curl http://localhost:9090/-/healthy
   ```

   Should return "Prometheus is Healthy."

2. **Query service status (up/down):**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=up'
   ```

   Returns all services with `up=1` (healthy) or `up=0` (down).

3. **Parse and present results:**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=up' | \
     jq -r '.data.result[] | "\(.metric.job): \(.value[1])"'
   ```

   Shows human-readable service status list.

4. **Query additional metrics based on user request:**

   **Request rate (last 5 minutes):**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=rate(http_requests_total[5m])'
   ```

   **Memory usage:**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=container_memory_usage_bytes'
   ```

   **Service-specific metrics (example - Agent Zero tasks):**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=mcp_tasks_active'
   ```

   **CPU usage:**
   ```bash
   curl -G http://localhost:9090/api/v1/query \
     --data-urlencode 'query=rate(container_cpu_usage_seconds_total[5m])'
   ```

5. **Report results to user:**
   - Service status summary (up/down counts)
   - Requested metrics with values and labels
   - Trends or anomalies detected
   - Grafana dashboard link for visualization

## Common Metrics Queries

### Service Health
```bash
# All services status
query=up

# Specific service
query=up{job="agent-zero"}

# Services down
query=up == 0
```

### Performance
```bash
# Request rate per service
query=rate(http_requests_total[5m])

# Request latency (p95)
query=histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
query=rate(http_requests_total{status=~"5.."}[5m])
```

### Resource Usage
```bash
# Container memory
query=container_memory_usage_bytes{name=~".*"}

# Container CPU
query=rate(container_cpu_usage_seconds_total{name=~".*"}[5m])

# Network IO
query=rate(container_network_receive_bytes_total[5m])
```

### Service-Specific
```bash
# Agent Zero MCP requests
query=mcp_requests_total

# Hi-RAG query count
query=hirag_queries_total

# NATS message rate
query=rate(nats_messages_total[5m])

# TensorZero token usage
query=tensorzero_tokens_total
```

## PromQL Query Tips

- **Rate functions:** Use `rate()` for counter metrics
- **Time ranges:** `[5m]`, `[1h]`, `[1d]` for different windows
- **Aggregation:** `sum()`, `avg()`, `max()`, `min()`
- **Filtering:** `{job="service-name", status="200"}`
- **Regex:** `{name=~"agent.*"}` for pattern matching

## Alternative: Range Queries

For time-series data over a range:

```bash
curl -G http://localhost:9090/api/v1/query_range \
  --data-urlencode 'query=rate(http_requests_total[5m])' \
  --data-urlencode 'start=2025-12-06T12:00:00Z' \
  --data-urlencode 'end=2025-12-06T13:00:00Z' \
  --data-urlencode 'step=60s'
```

Returns data points at 60-second intervals.

## Grafana Dashboard

For visual exploration of metrics:
- **URL:** `http://localhost:3000`
- **Dashboard:** "Services Overview" (pre-configured)
- **Datasource:** Prometheus (already configured)

Use Grafana for:
- Interactive metric exploration
- Historical trend analysis
- Alert configuration
- Custom dashboard creation

## Response Format

Prometheus API returns JSON:

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "job": "agent-zero",
          "instance": "localhost:8080"
        },
        "value": [1733572800, "1"]
      }
    ]
  }
}
```

- `metric` - Labels identifying the time series
- `value` - `[timestamp, value]` tuple

## Notes

- Prometheus scrapes all `/metrics` endpoints every 15s (default)
- Metrics are retained for 15 days (configurable)
- Port 9090 for Prometheus API
- All PMOVES services expose Prometheus metrics
- Use `jq` for JSON parsing and formatting
- Check Prometheus targets: `http://localhost:9090/targets`
- Prometheus UI: `http://localhost:9090/graph`
- cAdvisor provides container metrics (port 8080)
- Loki integration for log correlation (port 3100)
