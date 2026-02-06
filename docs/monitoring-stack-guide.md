# PMOVES.AI Monitoring Stack Guide

**Comprehensive monitoring, observability, and alerting for PMOVES.AI production infrastructure.**

## Table of Contents

1. [Overview](#overview)
2. [Components](#components)
3. [Configuration](#configuration)
4. [Service Integration](#service-integration)
5. [Common Queries](#common-queries)
6. [Troubleshooting](#troubleshooting)

---

## Overview

PMOVES.AI implements a production-grade observability stack combining metrics, logs, and traces for complete system visibility. The monitoring architecture follows the "three pillars of observability" principle:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PMOVES Observability Stack                       │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Prometheus │───▶│   Grafana    │◀───│     Loki     │              │
│  │   Metrics    │    │  Dashboards  │    │   Logs       │              │
│  │  Port: 9090  │    │  Port: 3000  │    │ Port: 3100   │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                                       │                        │
│         │                                   ┌───┴───┐                   │
│         │                                   │Promtail│                   │
│         │                                   └────────┘                   │
│         │                                   Log Aggregation             │
│         │                                                                │
│         ▼                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    PMOVES Services                                │   │
│  │  /metrics endpoints + /healthz probes + Loki labels               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │               TensorZero + ClickHouse                             │   │
│  │              Model Observability & Usage Analytics                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Single Source of Truth** - Prometheus is the primary metrics store
2. **Service Discovery** - Automatic target detection via Docker labels
3. **Centralized Logging** - Loki aggregates all container logs
4. **Model Observability** - TensorZero + ClickHouse track all LLM usage
5. **Alert-Driven** - Prometheus alerts detect and notify on issues

### Architecture Benefits

- **Horizontal Scalability** - Add services without reconfiguring monitoring
- **Long-Term Retention** - ClickHouse for metrics, Loki for logs
- **Unified Dashboards** - Grafana correlates metrics and logs
- **Production Ready** - Used in production for PMOVES.AI infrastructure

---

## Components

### Prometheus

**Purpose:** Metrics collection, storage, and alerting

**Port:** 9090 (internal), configurable via `PROMETHEUS_HOST_PORT`

**Version:** v2.55.1

**Key Features:**
- Pull-based metrics scraping (15s interval)
- Prometheus query language (PromQL)
- Alerting rule evaluation
- Service discovery via static configs
- Long-term metric storage

**Storage:**
- TSDB (Time Series Database)
- Volume: `prometheus-data`
- Retention: 15 days default (configurable)

**Health Check:**
```bash
curl http://localhost:9090/-/healthy
```

**Configuration:**
- Config file: `pmoves/monitoring/prometheus/prometheus.yml`
- Alert rules: `pmoves/monitoring/prometheus/alert.rules.yml`

---

### Grafana

**Purpose:** Dashboard visualization and alert management

**Port:** 3000 (internal), configurable via `GRAFANA_HOST_PORT` (default: 3002)

**Version:** 11.2.0

**Key Features:**
- Pre-configured dashboards for PMOVES services
- Prometheus and Loki datasources
- Alert provisioning
- Dashboard provisioning from files

**Access:**
- URL: `http://localhost:3002` (or configured port)
- Default credentials: `admin/admin` (set via env vars)

**Dashboards:**
- `services-overview.json` - All service health
- `flute-gateway.json` - Voice service metrics
- `pmoves_services_health.json` - Service uptime tracking
- `github-runners.json` - CI/CD runner monitoring
- `tokenism.json` - Tokenism gateway metrics
- `messaging-gateway.json` - Message throughput

**Datasources:**
- Prometheus (primary)
- Loki (logs)
- TensorZero ClickHouse (model metrics)

**Configuration:**
- Datasources: `pmoves/monitoring/grafana/datasources/datasource.yml`
- Dashboards: `pmoves/monitoring/grafana/provisioning/dashboards.yml`

---

### Loki

**Purpose:** Log aggregation and log query system

**Port:** 3100

**Version:** 3.1.1

**Key Features:**
- Horizontal scalability
- Label-based log indexing
- LogQL (Log Query Language)
- Full-text search on log content
- Split query optimization

**Storage:**
- Filesystem backend (boltdb-shipper)
- Volume: `loki-data`
- Retention: Configurable via limits

**Health Check:**
```bash
curl http://localhost:3100/ready
```

**Configuration:**
- Config file: `pmoves/monitoring/loki/local-config.yaml`
- Single-process mode for WSL2 compatibility

**Loki Labels (Automatic):**
- `service` - Docker compose service name
- `container_name` - Container ID
- `project` - Compose project name
- `stream` - stdout/stderr

---

### Promtail

**Purpose:** Log agent for scraping container logs

**Port:** 9080 (internal)

**Version:** 3.1.1

**Key Features:**
- Docker socket integration
- Journald support (optional)
- Automatic label enrichment
- Positions tracking for resume capability

**Log Sources:**
- Docker container logs via `/var/lib/docker/containers`
- System logs via journald (optional)

**Configuration:**
- Config file: `pmoves/monitoring/promtail/config.yml`
- Positions file: `/tmp/positions.yaml`

**Label Enrichment:**
```yaml
labels:
  service: <compose service>
  project: <compose project>
  container_name: <container id>
  stream: stdout/stderr
```

---

### cAdvisor

**Purpose:** Container metrics collection for Prometheus

**Port:** 8080 (metrics), 9180 (host, configurable via `CADVISOR_HOST_PORT`)

**Version:** v0.49.1

**Key Features:**
- Container CPU, memory, disk I/O metrics
- Network statistics per container
- File system usage
- Auto-discovery of containers

**Metrics Exposed:**
- `container_cpu_usage_seconds_total`
- `container_memory_usage_bytes`
- `container_network_receive_bytes_total`
- `container_fs_usage_bytes`

**Health Check:**
```bash
curl http://localhost:9180/metrics
```

**Special Requirements:**
- Privileged mode for host access
- Volume mounts: `/`, `/var/run`, `/sys`, `/var/lib/docker`
- Profile: `linux` (not enabled on WSL2 by default)

---

### Blackbox Exporter

**Purpose:** External probing of endpoints via HTTP, TCP, ICMP, DNS

**Port:** 9115 (internal), configurable via `BLACKBOX_HOST_PORT`

**Version:** v0.25.0

**Key Features:**
- HTTP/2xx probes for health endpoints
- TCP connect probes
- ICMP ping probes
- DNS query probes

**Probe Modules:**
- `http_2xx` - HTTP GET with 2xx response validation
- `http_post_2xx` - HTTP POST probes
- `tcp_connect` - TCP port reachability
- `icmp` - Ping probes
- `dns_udp` - DNS resolution
- `pmoves_healthz` - Custom PMOVES health checks

**Configuration:**
- Config file: `pmoves/monitoring/blackbox/blackbox.yml`

**Usage in Prometheus:**
```yaml
- job_name: blackbox_http
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - http://host.docker.internal:8080/healthz
```

---

### TensorZero + ClickHouse

**Purpose:** Model observability and usage analytics

**Components:**
- TensorZero Gateway (Port 3030)
- TensorZero ClickHouse (Port 8123)
- TensorZero UI (Port 4000)

**Key Features:**
- Request/response logging for all LLM calls
- Token usage tracking by model
- Latency metrics (P50, P95, P99)
- Error rate monitoring
- Model performance comparison

**Data Stored:**
- Request timestamps
- Model names
- Token counts (input/output)
- Latency in milliseconds
- Error traces

**Query Examples:**
```sql
-- Total requests by model
SELECT model, COUNT(*) as count
FROM requests
GROUP BY model
ORDER BY count DESC;

-- Average latency by model
SELECT model, AVG(latency_ms) as avg_latency
FROM requests
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY model;
```

**Documentation:** See `.claude/context/tensorzero.md`

---

## Configuration

### Prometheus Configuration

**Location:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/prometheus/prometheus.yml`

**Global Settings:**
```yaml
global:
  scrape_interval: 15s    # How often to scrape targets
  evaluation_interval: 15s  # How often to evaluate rules
```

**Scrape Config Patterns:**

#### Direct /metrics Scraping
For services with built-in Prometheus metrics:

```yaml
- job_name: my-service
  static_configs:
    - targets: ["my-service:8080"]
```

#### Blackbox HTTP Probes
For services without /metrics (health check only):

```yaml
- job_name: blackbox_http
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - http://host.docker.internal:8080/healthz
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox:9115
```

**Key Configuration Points:**
1. **Job names** - Must be unique, use lowercase with hyphens
2. **Targets** - Use `service:port` format (Docker DNS)
3. **`host.docker.internal`** - Use for host machine targets from containers
4. **Metrics path** - Default `/metrics`, customize if needed

---

### Prometheus Alert Rules

**Location:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/prometheus/alert.rules.yml`

**Alert Categories:**

#### Service Health
```yaml
- alert: ServiceDown
  expr: up == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Service {{ $labels.job }} is down"
```

#### Error Rates
```yaml
- alert: HighErrorRate
  expr: |
    (
      sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
      /
      sum by (job) (rate(http_requests_total[5m]))
    ) > 0.05
  for: 5m
  labels:
    severity: warning
```

#### Latency
```yaml
- alert: HighP95Latency
  expr: |
    histogram_quantile(0.95,
      sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))
    ) > 2
  for: 5m
  labels:
    severity: warning
```

#### Resource Usage
```yaml
- alert: HighMemoryUsage
  expr: process_resident_memory_bytes > 2e9
  for: 10m
  labels:
    severity: warning
```

**Best Practices:**
1. **`for` duration** - Prevent alert flapping on transient issues
2. **Severity labels** - `critical`, `warning`, `info`
3. **Annotations** - Use `$labels` for context
4. **Thresholds** - Base on SLA requirements

---

### Grafana Provisioning

**Datasources:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/grafana/datasources/datasource.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

**Dashboards:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/grafana/provisioning/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: PMOVES Dashboards
    type: file
    disableDeletion: true
    updateIntervalSeconds: 15
    options:
      path: /etc/grafana/dashboards
```

**Adding New Dashboards:**
1. Create dashboard JSON in `pmoves/monitoring/grafana/dashboards/`
2. Restart Grafana (or wait 15s for auto-reload)
3. Dashboard appears automatically in Grafana

---

### Loki Configuration

**Location:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/loki/local-config.yaml`

**Key Settings:**
```yaml
server:
  http_listen_port: 3100

limits_config:
  split_queries_by_interval: 30m
  max_entries_limit_per_query: 10000
  max_streams_per_user: 0  # Unlimited
  max_global_streams_per_user: 0  # Unlimited
  allow_structured_metadata: false  # Required for boltdb-shipper
```

**Storage Configuration:**
```yaml
common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
```

**Schema Config:**
```yaml
schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v13
      index:
        prefix: loki_index_
        period: 24h
```

---

### Promtail Configuration

**Location:** `/home/pmoves/PMOVES.AI/pmoves/monitoring/promtail/config.yml`

**Docker Log Scraping:**
```yaml
scrape_configs:
  - job_name: docker-containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: container_name
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: service
      - source_labels: ['__meta_docker_container_label_com_docker_compose_project']
        target_label: project
```

**Custom Loki Labels:**

Add to your service's `docker-compose.yml`:
```yaml
labels:
  environment: production
  tier: backend
```

These become queryable labels in Loki.

---

## Service Integration

### Adding /metrics to New Services

#### Python (FastAPI)

**1. Install dependency:**
```bash
pip install prometheus-client
```

**2. Define metrics:**
```python
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response

app = FastAPI()

# Define metrics
REQUEST_COUNT = Counter(
    "my_service_requests_total",
    "Total requests processed",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "my_service_request_latency_seconds",
    "Request latency",
    ["endpoint"]
)

ACTIVE_CONNECTIONS = Gauge(
    "my_service_active_connections",
    "Active connections"
)
```

**3. Instrument endpoints:**
```python
import time

@app.get("/api/data")
async def get_data():
    start = time.time()
    ACTIVE_CONNECTIONS.inc()

    try:
        # Your handler logic
        result = {"data": "..."}
        REQUEST_COUNT.labels(method="GET", endpoint="/api/data", status="200").inc()
        return result
    except Exception as e:
        REQUEST_COUNT.labels(method="GET", endpoint="/api/data", status="500").inc()
        raise
    finally:
        REQUEST_LATENCY.labels(endpoint="/api/data").observe(time.time() - start)
        ACTIVE_CONNECTIONS.dec()
```

**4. Expose /metrics endpoint:**
```python
@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**5. Add to Prometheus:**
```yaml
# pmoves/monitoring/prometheus/prometheus.yml
- job_name: my-service
  static_configs:
    - targets: ["my-service:8000"]
```

#### Python (Flask)

```python
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response

app = Flask(__name__)

REQUEST_COUNT = Counter('flask_requests_total', 'Total requests', ['method', 'endpoint'])

@app.before_request
def before_request():
    REQUEST_COUNT.labels(method=request.method, endpoint=request.endpoint).inc()

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
```

#### Node.js (Express)

```javascript
const promClient = require('prom-client');
const express = require('express');

const app = express();

// Create metrics
const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'code']
});

const httpRequestCounter = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'code']
});

// Middleware to track requests
app.use((req, res, next) => {
  const start = Date.now();

  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestDuration
      .labels(req.method, req.route?.path || req.path, res.statusCode)
      .observe(duration);
    httpRequestCounter
      .labels(req.method, req.route?.path || req.path, res.statusCode)
      .inc();
  });

  next();
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.end(await promClient.register.metrics());
});
```

#### Go

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
    "net/http"
)

var (
    httpRequestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total number of HTTP requests",
        },
        []string{"method", "path", "status"},
    )

    httpDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "http_request_duration_seconds",
            Help: "Duration of HTTP requests in seconds",
        },
        []string{"method", "path"},
    )
)

func init() {
    prometheus.MustRegister(httpRequestsTotal)
    prometheus.MustRegister(httpDuration)
}

func main() {
    http.Handle("/metrics", promhttp.Handler())
    http.ListenAndServe(":8080", nil)
}
```

---

### Adding /healthz Endpoints

**Purpose:** Kubernetes-style readiness/liveness probes

**FastAPI Example:**
```python
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI()

@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    """
    Health check endpoint for orchestrator probes.

    Returns:
        {"status": "ok"} on healthy
        {"status": "degraded"} if partially functional

    HTTP Status Codes:
        200 - Healthy
        503 - Unhealthy
    """
    # Check dependencies
    try:
        # Add your health checks here
        # e.g., database connectivity, external APIs, etc.
        return {"status": "ok", "service": "my-service"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

**Express Example:**
```javascript
app.get('/healthz', (req, res) => {
  try {
    // Add health checks
    res.status(200).json({ status: 'ok', service: 'my-service' });
  } catch (error) {
    res.status(503).json({ status: 'error', message: error.message });
  }
});
```

**Best Practices:**
1. **Return quickly** - Health checks should complete in < 1s
2. **Check dependencies** - Database, cache, external APIs
3. **Use appropriate status codes** - 200 (OK), 503 (Service Unavailable)
4. **Include service name** - Helps identify source in alerts
5. **Don't include secrets** - Avoid exposing config in health responses

---

### Loki Label Conventions

**Structured Logging with Labels:**

Use JSON logging for automatic label extraction:
```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "my-service",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
        }
        return json.dumps(log_obj)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
```

**Recommended Labels:**
- `service` - Service name (required)
- `environment` - production/staging/development
- `tier` - frontend/backend/worker
- `version` - Service version
- `request_id` - Request trace ID
- `user_id` - User ID (if applicable)

**Querying Labels in Loki:**
```logql
{service="my-service", environment="production"} |= "error"
```

---

### Metric Naming Conventions

**Follow Prometheus best practices:**

**Naming Pattern:** `<metric_name>_<unit>`

**Examples:**
```
# Counters
http_requests_total
api_errors_total
jobs_completed_total

# Gauges
active_connections
queue_depth
memory_usage_bytes

# Histograms
http_request_duration_seconds
database_query_latency_seconds
message_processing_time_seconds

# Summary
response_latency_summary
```

**Label Names:**
- Use `snake_case`
- Include relevant dimensions: `method`, `endpoint`, `status`, `service`
- Avoid high-cardinality labels (user_id, request_id)

**Good Examples:**
```
http_requests_total{method="GET", endpoint="/api/users", status="200"}
database_query_duration_seconds{database="postgres", query_type="select"}
```

**Bad Examples (avoid):**
```
# Too specific
http_get_api_users_request_duration_seconds

# High cardinality
http_requests_total{user_id="12345", request_id="abc-def-ghi"}

# Missing unit
http_request_latency  # Should be http_request_latency_seconds
```

---

## Common Queries

### Prometheus Queries (PromQL)

#### Service Health

**All services up:**
```promql
up

# Services currently down
up == 0

# Service uptime percentage
avg_over_time(up[1h]) * 100
```

**Specific service health:**
```promql
up{job="agent-zero"}
up{job="hi-rag-gateway-v2"}
```

#### Error Rates

**HTTP 5xx error rate:**
```promql
sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
```

**Error percentage:**
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100
```

#### Latency

**P95 Latency:**
```promql
histogram_quantile(0.95,
  sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

**Average Latency:**
```promql
sum(rate(http_request_duration_seconds_sum[5m])) /
sum(rate(http_request_duration_seconds_count[5m]))
```

#### Resource Usage

**CPU usage by job:**
```promql
sum by (job) (rate(process_cpu_seconds_total[5m])) * 100
```

**Memory usage:**
```promql
process_resident_memory_bytes / 1024 / 1024  # MB
```

**Container memory percentage:**
```promql
container_memory_usage_bytes{name="my-service"} /
container_spec_memory_limit_bytes{name="my-service"} * 100
```

#### Rate Calculations

**Requests per second:**
```promql
sum(rate(http_requests_total[5m]))
```

**Jobs completed per minute:**
```promql
sum(rate(jobs_completed_total[1m])) * 60
```

#### Aggregation

**Sum by labels:**
```promql
sum by (job) (http_requests_total)
```

**Average across instances:**
```promql
avg by (job) (http_requests_total)
```

**Top 10 by metric:**
```promql
topk(10, sum by (job) (http_requests_total))
```

#### Time-Based

**Compare to yesterday:**
```promql
rate(http_requests_total[5m])
/
rate(http_requests_total[5m] offset 24h)
```

**Week-over-week:**
```promql
rate(http_requests_total[1h])
/
rate(http_requests_total[1h] offset 168h)
```

---

### Loki Queries (LogQL)

#### Basic Queries

**Search by service:**
```logql
{service="agent-zero"}
```

**Full-text search:**
```logql
{service="hi-rag-gateway-v2"} |= "error"
```

**Multiple conditions:**
```logql
{service="archon", environment="production"} |= "timeout"
```

#### Filtering

**Exclude logs:**
```logql
{service="my-service"} != "debug"
```

**Regular expressions:**
```logql
{service="my-service"} |=~ "(?i)error|warning|critical"
```

**Filter by log level:**
```logql
{service="my-service", level="error"}
```

#### Aggregation

**Count errors per service:**
```logql
count_over_time({service=~".+"} |= "error" [1h])
```

**Rate of errors:**
```logql
rate({service="my-service"} |= "error" [5m])
```

**Top logs by frequency:**
```logql
topk(10, count_over_time({service="my-service"} [1h]))
```

#### Time-Based

**Last 5 minutes:**
```logql
{service="my-service"} | line_format "{{.message}}" [5m]
```

**Specific time range:**
```logql
{service="my-service"} | line_format "{{__timestamp__}}" > "2024-01-15T10:00:00Z"
```

---

### ClickHouse Queries (TensorZero)

#### Usage Analytics

**Total requests by model:**
```sql
SELECT
  model,
  COUNT(*) as request_count,
  SUM(request_tokens) as total_input_tokens,
  SUM(response_tokens) as total_output_tokens
FROM requests
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY model
ORDER BY request_count DESC;
```

**Average latency by model:**
```sql
SELECT
  model,
  AVG(latency_ms) as avg_latency,
  quantile(0.95)(latency_ms) as p95_latency,
  quantile(0.99)(latency_ms) as p99_latency
FROM requests
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY model
ORDER BY avg_latency DESC;
```

#### Cost Analysis

**Token usage over time:**
```sql
SELECT
  toStartOfHour(timestamp) as hour,
  model,
  SUM(request_tokens + response_tokens) as total_tokens
FROM requests
WHERE timestamp > now() - INTERVAL 24 HOUR
GROUP BY hour, model
ORDER BY hour DESC, total_tokens DESC;
```

**Error rate by model:**
```sql
SELECT
  model,
  COUNT(*) as total_requests,
  COUNTIF(error_code != '') as error_count,
  error_count / total_requests * 100 as error_percentage
FROM requests
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY model
HAVING error_count > 0
ORDER BY error_percentage DESC;
```

#### Performance Analysis

**Slowest requests:**
```sql
SELECT
  timestamp,
  model,
  latency_ms,
  request_tokens,
  response_tokens
FROM requests
WHERE timestamp > now() - INTERVAL 1 HOUR
ORDER BY latency_ms DESC
LIMIT 20;
```

**Request size distribution:**
```sql
SELECT
  model,
  AVG(request_tokens) as avg_input_tokens,
  quantile(0.50)(request_tokens) as p50_input,
  quantile(0.95)(request_tokens) as p95_input,
  quantile(0.99)(request_tokens) as p99_input
FROM requests
WHERE timestamp > now() - INTERVAL 24 HOUR
GROUP BY model;
```

---

## Troubleshooting

### Prometheus Issues

#### Prometheus Not Scraping Targets

**Symptom:** Targets show as "DOWN" in Prometheus UI

**Diagnosis:**
```bash
# Check Prometheus logs
docker compose logs prometheus | grep -i error

# Verify target reachability from Prometheus container
docker compose exec prometheus wget -O- http://target-service:port/metrics

# Check Prometheus config reload
curl -X POST http://localhost:9090/-/reload
```

**Common Causes:**
1. **Network isolation** - Service not on `monitoring_tier` network
2. **Wrong port** - Target service port mismatch
3. **Firewall** - Host firewall blocking connections
4. **Service not started** - Target container not running

**Solutions:**
```yaml
# Add service to monitoring network
networks:
  monitoring_tier:
    external: true
    name: pmoves_monitoring

# Verify service exposes /metrics
# Add to your service code:
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

### High Memory Usage

**Symptom:** Prometheus OOM killed or high memory consumption

**Diagnosis:**
```bash
# Check Prometheus memory usage
docker stats prometheus

# Check time series count
curl http://localhost:9090/api/v1/label/__name__/values | jq '.data | length'
```

**Common Causes:**
1. **High cardinality metrics** - Too many label combinations
2. **Insufficient retention** - Too much data stored
3. **Scrape interval too short** - Default 15s is usually fine

**Solutions:**
```yaml
# Reduce retention (add to prometheus command)
--storage.tsdb.retention.time=7d

# Add recording rules to reduce query complexity
# See pmoves/monitoring/prometheus/recording.rules.yml
```

**Avoid High Cardinality:**
```python
# BAD - High cardinality labels
REQUEST_COUNT.labels(
    method="GET",
    endpoint="/api/users",
    user_id="12345",  # Too many unique values
    request_id="abc-def"  # Too many unique values
).inc()

# GOOD - Low cardinality labels
REQUEST_COUNT.labels(
    method="GET",
    endpoint="/api/users",
    status="200"
).inc()
```

---

### Loki Query Slow

**Symptom:** Loki queries timeout or take too long

**Diagnosis:**
```bash
# Check Loki logs
docker compose logs loki | grep -i "slow query"

# Check Loki metrics
curl http://localhost:3100/metrics | grep query
```

**Common Causes:**
1. **Query range too large** - Multi-day queries
2. **No label filters** - Full-text search only
3. **Regex filters** - Expensive operations

**Solutions:**
```logql
# BAD - Full scan
"error message"

# GOOD - Label filter first
{service="my-service"} |= "error message"

# BAD - Large time range
{service="my-service"} [7d]

# GOOD - Narrower range
{service="my-service"} [1h]
```

**Optimization Tips:**
1. Always filter by labels first
2. Limit time range when possible
3. Use `| line_format` to extract fields
4. Consider split queries (`split_queries_by_interval: 30m`)

---

### Grafana Dashboard Not Loading

**Symptom:** Dashboard shows "No data" or error

**Diagnosis:**
```bash
# Check Grafana logs
docker compose logs grafana | grep -i error

# Verify datasource connectivity
curl http://localhost:9090/api/v1/query?query=up

# Check dashboard provisioning
ls -la pmoves/monitoring/grafana/dashboards/
```

**Common Causes:**
1. **Datasource not reachable** - Prometheus/Loki down
2. **Dashboard JSON syntax error** - Invalid JSON
3. **Variable not defined** - Dashboard uses undefined variables

**Solutions:**
```bash
# Restart provisioning
docker compose restart grafana

# Verify datasource configuration
cat pmoves/monitoring/grafana/datasources/datasource.yml

# Validate JSON
cat dashboard.json | jq .
```

---

### Missing Container Logs

**Symptom:** Logs not appearing in Loki/Grafana

**Diagnosis:**
```bash
# Check Promtail logs
docker compose logs promtail | grep -i error

# Verify log files exist
ls -la /var/lib/docker/containers/*/*-json.log

# Check Promtail targets
curl http://localhost:9080/targets
```

**Common Causes:**
1. **Promtail not running** - Container stopped
2. **Docker socket not mounted** - Can't read container logs
3. **Log driver conflict** - Custom logging driver configured

**Solutions:**
```yaml
# Ensure Promtail has Docker socket
volumes:
  - /var/lib/docker/containers:/var/lib/docker/containers:ro
  - /var/run/docker.sock:/var/run/docker.sock:ro

# Check logging driver (should be json-file)
docker inspect my-service | grep -A 5 "LogConfig"
```

---

### TensorZero Observability Not Working

**Symptom:** No data in ClickHouse or TensorZero UI

**Diagnosis:**
```bash
# Check ClickHouse connection
docker exec -it tensorzero-clickhouse clickhouse-client --ping

# Verify observability enabled in TensorZero
docker compose logs tensorzero-gateway | grep observability

# Check ClickHouse tables
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero \
  --query "SHOW TABLES"
```

**Common Causes:**
1. **Observability disabled** - Not enabled in config
2. **ClickHouse connection failed** - Wrong URL or credentials
3. **Config format outdated** - Using legacy config syntax

**Solutions:**
```toml
# pmoves/tensorzero/config/tensorzero.toml
[gateway]
observability.enabled = true
```

```bash
# Verify environment variables
docker compose exec tensorzero-gateway env | grep CLICKHOUSE

# Should see:
# TENSORZERO_CLICKHOUSE_URL=http://tensorzero:tensorzero@tensorzero-clickhouse:8123/default
```

**Config Format Check:**
```toml
# OLD FORMAT (TensorZero < 2025.11.6)
[gateway.observability.clickhouse]
url = "http://..."
# ❌ This causes "unknown field" error

# NEW FORMAT (TensorZero 2025.11.6+)
[gateway]
observability.enabled = true
# ✅ Connection via TENSORZERO_CLICKHOUSE_URL env var
```

---

### Alert Not Firing

**Symptom:** Expected alert not triggered

**Diagnosis:**
```bash
# Check alert rules loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.name=="ServiceDown")'

# Check alert evaluation
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="ServiceDown")'

# Test query manually
# Use the expr from the alert rule
```

**Common Causes:**
1. **Alert condition not met** - Query returns false
2. **`for` duration not elapsed** - Alert requires sustained condition
3. **Syntax error in rule** - Invalid PromQL

**Solutions:**
```yaml
# Test the query
# Go to http://localhost:9090/graph
# Run the expr query to verify it returns data

# Check syntax
promtool check rules pmoves/monitoring/prometheus/alert.rules.yml

# Verify `for` duration
# If alert has `for: 5m`, condition must be true for 5 minutes continuously
```

---

## Best Practices

### Metrics Design

1. **Start with key metrics** - Don't measure everything initially
2. **Use appropriate metric types** - Counter for cumulative, Gauge for current state
3. **Avoid high cardinality** - Keep label values bounded
4. **Document metrics** - Add `help` text to all metrics
5. **Test queries** - Verify PromQL works in Grafana before relying on alerts

### Alert Design

1. **Alert on symptoms, not causes** - Alert on "high latency" not "CPU high"
2. **Use `for` duration** - Avoid alert flapping
3. **Severity levels** - Distinguish critical vs. warning
4. **Actionable alerts** - Include runbook links or remediation steps
5. **Test alerts** - Use alert testing before production deployment

### Dashboard Design

1. **Start with overview** - High-level health first
2. **Drill-down capability** - Link from overview to detailed dashboards
3. **Consistent time ranges** - Use variables for time ranges
4. **Use annotations** - Mark deployments, incidents
5. **Mobile-friendly** - Critical dashboards should work on mobile

### Log Management

1. **Structured logging** - Use JSON format with consistent fields
2. **Log levels matter** - Use appropriate levels (DEBUG, INFO, WARNING, ERROR)
3. **Avoid secrets** - Never log passwords, tokens, or PII
4. **Correlation IDs** - Add request IDs for traceability
5. **Log aggregation** - Centralize logs in Loki, don't use local files

---

## Quick Reference

### Service Ports

| Service | Internal Port | External Port (Default) |
|---------|---------------|-------------------------|
| Prometheus | 9090 | 9090 |
| Grafana | 3000 | 3002 |
| Loki | 3100 | 3100 |
| Promtail | 9080 | - |
| cAdvisor | 8080 | 9180 |
| Blackbox | 9115 | 9115 |

### Important Paths

| Component | Config Location |
|-----------|-----------------|
| Prometheus config | `/home/pmoves/PMOVES.AI/pmoves/monitoring/prometheus/prometheus.yml` |
| Alert rules | `/home/pmoves/PMOVES.AI/pmoves/monitoring/prometheus/alert.rules.yml` |
| Grafana datasources | `/home/pmoves/PMOVES.AI/pmoves/monitoring/grafana/datasources/datasource.yml` |
| Dashboards | `/home/pmoves/PMOVES.AI/pmoves/monitoring/grafana/dashboards/` |
| Loki config | `/home/pmoves/PMOVES.AI/pmoves/monitoring/loki/local-config.yaml` |
| Promtail config | `/home/pmoves/PMOVES.AI/pmoves/monitoring/promtail/config.yml` |
| Docker compose | `/home/pmoves/PMOVES.AI/pmoves/monitoring/docker-compose.monitoring.yml` |

### Common Commands

```bash
# Start monitoring stack
cd pmoves/monitoring && docker compose up -d

# Restart Prometheus
docker compose restart prometheus

# Reload Prometheus config (no restart needed)
curl -X POST http://localhost:9090/-/reload

# View Prometheus targets
curl http://localhost:9090/api/v1/targets | jq .

# Query Prometheus
curl "http://localhost:9090/api/v1/query?query=up" | jq .

# Check Loki health
curl http://localhost:3100/ready

# Query Loki
curl -G -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={service="agent-zero"}' | jq .

# View Grafana dashboards
# Navigate to http://localhost:3002

# Check ClickHouse
docker exec -it tensorzero-clickhouse clickhouse-client --ping

# Query ClickHouse
docker exec -it tensorzero-clickhouse clickhouse-client \
  --user tensorzero --password tensorzero \
  --query "SELECT COUNT(*) FROM requests"
```

---

## Additional Resources

### Documentation

- **Prometheus:** https://prometheus.io/docs/
- **Grafana:** https://grafana.com/docs/
- **Loki:** https://grafana.com/docs/loki/latest/
- **Promtail:** https://grafana.com/docs/loki/latest/clients/promtail/
- **PromQL:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **LogQL:** https://grafana.com/docs/loki/latest/logql/
- **TensorZero:** `/home/pmoves/PMOVES.AI/.claude/context/tensorzero.md`

### PMOVES.AI Specific

- **Services Catalog:** `.claude/context/services-catalog.md`
- **NATS Subjects:** `.claude/context/nats-subjects.md`
- **Testing Strategy:** `.claude/context/testing-strategy.md`
- **TensorZero Integration:** `.claude/context/tensorzero.md`

### Tools

- **Promtool:** Validate Prometheus configs and rules
  ```bash
  promtool check config prometheus.yml
  promtool check rules alert.rules.yml
  ```

- **Logcli:** Query Loki from command line
  ```bash
  logcli query '{service="agent-zero"}'
  ```

---

## Changelog

### 2026-01-29
- Initial documentation created
- Comprehensive monitoring stack guide
- Service integration examples
- Troubleshooting section
- Common query patterns

---

## Contributors

This guide is part of the PMOVES.AI production infrastructure documentation.

**Last Updated:** 2026-01-29
**Maintained By:** PMOVES.AI Infrastructure Team
