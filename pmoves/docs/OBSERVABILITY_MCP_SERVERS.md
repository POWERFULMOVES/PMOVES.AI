# Observability MCP Servers - Implementation Complete

**Status:** ✅ Complete - All 5 MCP Servers Implemented
**Date:** 2026-04-21
**Task:** #28 - Create Observability MCP Server Infrastructure

---

## Overview

Implemented 5 MCP (Model Context Protocol) servers to expose observability tools to Agent Zero and other AI agents. These servers convert our existing observability specialist agents into MCP-compliant servers that can be called via stdio transport.

## MCP Servers Created

### 1. Prometheus Metrics MCP Server
**File:** `tools/observability/mcp_prometheus.py`
**Server Name:** `prometheus-metrics`

**Tools:**
- `query_metrics` - Execute PromQL queries
- `detect_anomalies` - Detect error rate, latency, CPU anomalies
- `trend_analysis` - Analyze metric trends over time
- `list_service_metrics` - List available metrics for a service

**Environment Variables:**
- `PROMETHEUS_URL` (default: `http://localhost:9090`)

### 2. Loki Logs MCP Server
**File:** `tools/observability/mcp_loki.py`
**Server Name:** `loki-logs`

**Tools:**
- `query_logs` - Execute LogQL queries
- `extract_errors` - Extract error logs for a service
- `correlate_logs` - Correlate logs by trace/request ID
- `detect_patterns` - Detect regex patterns in logs

**Environment Variables:**
- `LOKI_URL` (default: `http://localhost:3100`)

### 3. Jaeger Tracing MCP Server
**File:** `tools/observability/mcp_jaeger.py`
**Server Name:** `jaeger-tracing`

**Tools:**
- `query_traces` - Query traces for a service
- `get_trace` - Get detailed trace information
- `analyze_bottlenecks` - Identify performance bottlenecks
- `compare_traces` - Compare two traces

**Environment Variables:**
- `JAEGER_URL` (default: `http://localhost:16686`)

### 4. Grafana Dashboard MCP Server
**File:** `tools/observability/mcp_grafana.py`
**Server Name:** `grafana-dashboard`

**Tools:**
- `list_dashboards` - List all Grafana dashboards
- `get_dashboard` - Get dashboard details
- `create_dashboard` - Create new dashboard (templates)
- `configure_alert` - Configure alert on panel

**Environment Variables:**
- `GRAFANA_URL` (default: `http://localhost:3000`)
- `GRAFANA_API_KEY` (optional, for authenticated requests)

### 5. TensorZero LLM Observability MCP Server
**File:** `tools/observability/mcp_tensorzero.py`
**Server Name:** `tensorzero-llm-observability`

**Tools:**
- `query_clickhouse` - Execute SQL queries on ClickHouse
- `get_model_performance` - Get LLM performance metrics
- `get_cost_analysis` - Analyze LLM costs by model/provider
- `compare_models` - Compare performance between two models

**Environment Variables:**
- `TENSORZERO_CLICKHOUSE_URL` (default: `http://localhost:8123`)
- `TENSORZERO_CLICKHOUSE_USER` (default: `tensorzero`)
- `TENSORZERO_CLICKHOUSE_PASSWORD` (default: `tensorzero`)

## Architecture Pattern

All MCP servers follow the same architecture pattern:

```
┌─────────────────────────────────────┐
│     MCP Server (stdio transport)    │
│  - mcp.Server()                      │
│  - stdio_server() for stdio transport │
│  - @list_tools() decorator            │
│  - @call_tool() decorator             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     Service Client Class             │
│  - PrometheusClient                 │
│  - LokiClient                       │
│  - JaegerClient                     │
│  - GrafanaClient                    │
│  - TensorZeroClient                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     Service API                      │
│  - Prometheus HTTP API              │
│  - Loki HTTP API                    │
│  - Jaeger HTTP API                  │
│  - Grafana HTTP API                 │
│  - ClickHouse HTTP API              │
└─────────────────────────────────────┘
```

## Usage

### Standalone Execution (for testing)
```bash
# Run each MCP server directly
python tools/observability/mcp_prometheus.py
python tools/observability/mcp_loki.py
python tools/observability/mcp_jaeger.py
python tools/observability/mcp_grafana.py
python tools/observability/mcp_tensorzero.py
```

### Integration via Agent Zero MCP API
Agents can call these tools via Agent Zero's MCP endpoint:

```bash
curl -X POST http://localhost:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{
    "server": "prometheus-metrics",
    "tool": "detect_anomalies",
    "arguments": {
      "service": "pmoves-yt",
      "hours": 1
    }
  }'
```

## Tool Registration

To make these MCP servers available to Agent Zero, register them in the MCP configuration:

**Option 1: Via docker-compose (stdio transport)**
```yaml
services:
  agent-zero:
    # ... existing config ...
    command:
      - /app/agent_zero
      - --mcp-server=prometheus-metrics:python3 /app/tools/observability/mcp_prometheus.py
      - --mcp-server=loki-logs:python3 /app/tools/observability/mcp_loki.py
      - --mcp-server=jaeger-tracing:python3 /app/tools/observability/mcp_jaeger.py
      - --mcp-server=grafana-dashboard:python3 /app/tools/observability/mcp_grafana.py
      - --mcp-server=tensorzero-llm-observability:python3 /app/tools/observability/mcp_tensorzero.py
```

**Option 2: Via PMOVES-Archon MCP Gateway**
Add MCP server registrations to Archon's MCP bridge configuration.

## Testing

Each MCP server can be tested independently:

```bash
# Test Prometheus MCP
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  python tools/observability/mcp_prometheus.py

# Test Loki MCP
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"query_logs","arguments":{"logql":"{service=\"pmoves-yt\"}","limit":10}},"id":2}' | \
  python tools/observability/mcp_loki.py
```

## Dependencies

All MCP servers require:
- `mcp` Python package (Model Context Protocol SDK)
- `requests` for HTTP client calls
- Existing observability infrastructure (Prometheus, Loki, Jaeger, Grafana, ClickHouse)

## Next Steps

1. **Register MCP Servers** - Add to Agent Zero MCP configuration
2. **Test Integration** - Verify Agent Zero can call tools successfully
3. **Create Agent Workflows** - Build agent workflows that use observability tools
4. **Publish to NATS** - Emit observability insights on NATS subjects

## Security Considerations

- All MCP servers use environment variables for service URLs
- Grafana MCP supports optional API key authentication
- TensorZero ClickHouse uses default credentials (should be secured in production)
- No hardcoded secrets or credentials in code

## Troubleshooting

**MCP server fails to start:**
- Check service URL environment variables
- Verify service is running and accessible
- Check port conflicts

**Tools return empty results:**
- Verify service has data (check logs, traces, metrics)
- Check time range (lookback period)
- Validate query syntax (PromQL, LogQL, SQL)

**Agent Zero cannot call tools:**
- Verify MCP server registration in Agent Zero config
- Check stdio transport configuration
- Review Agent Zero logs for connection errors

## Related Documentation

- `docs/META_AGENT_PHASE_1_COMPLETE.md` - Phase 1 architecture
- `tools/observability/metrics_specialist.py` - Original CLI agent
- `tools/observability/logs_specialist.py` - Original CLI agent
- `tools/observability/tracing_specialist.py` - Original CLI agent
- `tools/observability/dashboard_specialist.py` - Original CLI agent
- `tools/observability/llm_observability_specialist.py` - Original CLI agent

---

**Implementation Complete:** Task #28 ✅
**All 5 observability MCP servers are ready for integration.**
