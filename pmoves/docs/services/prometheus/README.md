# prometheus — Service Guide

Status: Implemented (compose)

Overview
- Prometheus is PMOVES.AI's metrics collection and monitoring system, scraping `/metrics` endpoints from all services and storing time-series data for querying, alerting, and visualization.
- The `prometheus` container runs Prometheus v2.55.1 on port 9090, providing a powerful query language (PromQL) for analyzing service performance, resource usage, and custom metrics.
- Integrates with Grafana (port 3002) for dashboard visualization, Loki for log aggregation, and cAdvisor for container metrics.
- Scrape targets defined in `pmoves/monitoring/prometheus/prometheus.yml` with 15-second intervals for both scraping and evaluation.

Compose
- Service: `prometheus`
- Ports: `9090:9090` (web UI and API)
- Profiles: (monitoring stack - started via `docker-compose.monitoring.yml`)
- Depends on: (no dependencies - core infrastructure)
- Networks: `pmoves_monitoring` (external)
- Volumes: `prometheus-data` (metrics storage)

Environment (core)
- No service-specific environment variables (configured via prometheus.yml).
- Uses `--web.enable-lifecycle` flag for hot-reload via HTTP API.

Command-line arguments
- `--config.file=/etc/prometheus/prometheus.yml` — Configuration file path.
- `--storage.tsdb.path=/prometheus` — Time-series database storage path.
- `--web.enable-lifecycle` — Enable HTTP API for config reload and snapshot management.

Scrape configurations
- Scrape interval: 15 seconds (global default).
- Evaluation interval: 15 seconds (for recording rules and alerting).
- Retention: Default 15 days (configurable via `--storage.tsdb.retention.time`).

Active scrape jobs (from prometheus.yml)
- `prometheus` — Prometheus self-monitoring (target: `prometheus:9090`).
- `cadvisor` — Container metrics (target: `cadvisor:8080`).
- `loki` — Log aggregation metrics (target: `loki:3100`).

Direct /metrics scraping
- `flute-gateway` — Voice communication metrics (target: `flute-gateway:8055`).
- `tensorzero-gateway` — LLM gateway metrics (target: `tensorzero-gateway:3000`).
- `deepresearch-metrics` — Research planning metrics (target: `deepresearch:8098`).
- `supaserch-metrics` — Deep research orchestrator metrics (target: `supaserch:8099`).
- `gpu-orchestrator` — GPU resource management (target: `gpu-orchestrator:8200`).

Tier 2 services (added 2025-12-24)
- `hi-rag-gateway-v2` — Hybrid RAG metrics (target: `hi-rag-gateway-v2:8086`).
- `extract-worker` — Embedding and indexing metrics (target: `extract-worker:8083`).
- `pmoves-yt` — YouTube ingestion metrics (target: `pmoves-yt:8077`).
- `agent-zero` — Agent orchestration metrics (target: `agent-zero:80`).
- `archon` — Agent service metrics (target: `archon:8091`).

Tier 3 services (added 2025-12-24)
- `jellyfin-bridge` — Jellyfin integration metrics (target: `jellyfin-bridge:8093`).
- `pdf-ingest` — Document ingestion metrics (target: `pdf-ingest:8092`).
- `notebook-sync` — Notebook synchronization metrics (target: `notebook-sync:8095`).
- `langextract` — NLP preprocessing metrics (target: `langextract:8084`).
- `presign` — URL presigning metrics (target: `presign:8088`).

Tier 4 services (added 2025-12-25)
- `render-webhook` — ComfyUI render metrics (target: `render-webhook:8085`).
- `session-context-worker` — Session management metrics (target: `session-context-worker:8100`).
- `messaging-gateway` — Messaging system metrics (target: `messaging-gateway:8101`).

Blackbox HTTP probes
- Health check probes for services without /metrics endpoints via `blackbox_exporter`.
- Probes target: `http://host.docker.internal:<port>/healthz` or `/`.
- Services probed:
  - Agent Zero (`:80/healthz`)
  - Hi-RAG v2 CPU (`:8086/`)
  - Hi-RAG v2 GPU (`:8087/`)
  - Presign (`:8088/healthz`)
  - Archon (`:8091/healthz`)
  - Channel Monitor (`:8097/healthz`)
  - TensorZero UI (`:4000`)
  - Flute Gateway (`:8055/healthz`)

API Endpoints (web UI and API)
- `GET http://localhost:9090/` — Prometheus web UI:
  - Query browser with PromQL auto-completion.
  - Graph visualization for time-series data.
  - Target status (up/down, scrape errors).
  - Configuration viewing and validation.

- `GET http://localhost:9090/api/v1/query?query=<promql>` — Instant query:
  - Returns current value for a PromQL expression.
  - Example: `http://localhost:9090/api/v1/query?query=up`

- `GET http://localhost:9090/api/v1/query_range?query=<promql>&start=<timestamp>&end=<timestamp>&step=<duration>` — Range query:
  - Returns time-series data for a time range.
  - Example: `http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])&start=2025-01-01T00:00:00Z&end=2025-01-01T01:00:00Z&step=1m`

- `POST http://localhost:9090/-/reload` — Hot-reload configuration:
  - Reloads prometheus.yml without restart.
  - Requires `--web.enable-lifecycle` flag.

- `GET http://localhost:9090/targets` — Scrape target status:
  - Shows all configured targets.
  - Health status (up/down), last scrape time, error messages.

Common PromQL queries
- Service health:
  ```promql
  up  # All target health status
  up{job="agent-zero"}  # Specific job health
  ```

- Request rate:
  ```promql
  rate(http_requests_total[5m])  # Per-second rate over 5m
  sum(rate(http_requests_total[5m])) by (job)  # Rate by job
  ```

- Latency percentiles:
  ```promql
  histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))  # P95 latency
  histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))  # P99 latency
  ```

- Error rate:
  ```promql
  rate(http_requests_total{status=~"5.."}[5m])  # 5xx error rate
  sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)  # Error rate by job
  ```

- Container metrics (via cAdvisor):
  ```promql
  rate(container_cpu_usage_seconds_total[5m])  # CPU usage rate
  container_memory_usage_bytes  # Memory usage
  rate(container_network_receive_bytes_total[5m])  # Network receive rate
  rate(container_network_transmit_bytes_total[5m])  # Network transmit rate
  ```

- TensorZero metrics:
  ```promql
  tensorzero_request_duration_seconds{quantile="0.95"}  # P95 latency
  rate(tensorzero_requests_total[5m])  # Request rate by model
  sum(tensorzero_tokens_total) by (model)  # Token usage by model
  ```

Smokes & tests
- Minimal container smoke:
  ```bash
  docker compose -f monitoring/docker-compose.monitoring.yml up -d prometheus
  docker compose -f monitoring/docker-compose.monitoring.yml ps prometheus
  curl -sS http://localhost:9090/-/healthy | jq .
  docker compose -f monitoring/docker-compose.monitoring.yml logs -n 50 prometheus
  ```

- Test Prometheus API:
  ```bash
  # Query all targets
  curl http://localhost:9090/api/v1/targets | jq .

  # Query metric
  curl http://localhost:9090/api/v1/query?query=up | jq .

  # Query specific job
  curl 'http://localhost:9090/api/v1/query?query=up{job="prometheus"}' | jq .
  ```

- Verify scrape targets:
  ```bash
  # Check target status in browser
  open http://localhost:9090/targets

  # Or via API
  curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'
  ```

- Test configuration reload:
  ```bash
  curl -X POST http://localhost:9090/-/reload
  ```

- Check metrics from a specific service:
  ```bash
  # Direct scrape
  curl http://localhost:8080/metrics  # Agent Zero

  # Via Prometheus
  curl 'http://localhost:9090/api/v1/query?query=up{job="agent-zero"}' | jq .
  ```

Make-based health checks
- `make -C pmoves health-prometheus` — Verify Prometheus health:
  - Checks `/-/healthy` endpoint.
  - Verifies configuration syntax.
  - Tests API query responsiveness.

- `make -C pmoves up-monitoring` — Start monitoring stack:
  - Brings up Prometheus, Grafana, Loki, Promtail, cAdvisor, Blackbox.
  - Creates necessary volumes and networks.

Runbook
- Start Prometheus:
  ```bash
  cd pmoves/monitoring && docker compose -f docker-compose.monitoring.yml up -d prometheus
  ```

- View Prometheus UI:
  ```bash
  open http://localhost:9090
  ```

- Reload configuration without restart:
  ```bash
  curl -X POST http://localhost:9090/-/reload
  ```

- View Prometheus logs:
  ```bash
  docker compose -f monitoring/docker-compose.monitoring.yml logs -f prometheus
  ```

- Check configuration syntax:
  ```bash
  docker run --rm -v $(pwd)/monitoring/prometheus:/etc/prometheus prom/prometheus:latest \
    promtool check config /etc/prometheus/prometheus.yml
  ```

- Query metrics via API:
  ```bash
  # Simple query
  curl 'http://localhost:9090/api/v1/query?query=up' | jq .

  # Range query (last hour)
  START=$(date -d '1 hour ago' +%s)
  END=$(date +%s)
  curl "http://localhost:9090/api/v1/query_range?query=rate(http_requests_total[5m])&start=$START&end=$END&step=1m" | jq .
  ```

- Backup Prometheus data:
  ```bash
  docker exec prometheus tar -czf /tmp/prometheus-backup.tar.gz /prometheus
  docker cp prometheus:/tmp/prometheus-backup.tar.gz ./prometheus-backup-$(date +%Y%m%d).tar.gz
  ```

- Create snapshot (for migration):
  ```bash
  curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot
  ```

Alerting (if configured)
- Alert rules file: `pmoves/monitoring/prometheus/alert.rules.yml`
- Rule evaluation interval: 15 seconds
- View active alerts:
  ```bash
  curl http://localhost:9090/api/v1/alerts | jq .
  ```
- Configure AlertManager for alert routing (not included in base setup)

Integration with Grafana
- Prometheus datasource pre-configured in Grafana.
- URL: `http://prometheus:9090`
- Access Grafana at `http://localhost:3002` (default credentials: admin/admin).
- Pre-configured dashboards:
  - Services Overview (service health, latency, throughput).
  - Container Metrics (CPU, memory, network via cAdvisor).
  - Prometheus stats (scrape health, series count, storage).

Service integration patterns
- Expose `/metrics` endpoint for service metrics:
  ```python
  from prometheus_client import Counter, Histogram, start_http_server

  request_count = Counter('http_requests_total', 'Total requests', ['method', 'endpoint'])
  request_duration = Histogram('http_request_duration_seconds', 'Request duration')

  @request_duration.time()
  def handle_request():
      request_count.labels(method='GET', endpoint='/api').inc()
      # ... request handling ...

  start_http_server(8080)  # Expose metrics on port 8080
  ```

- Add service to Prometheus scrape config:
  ```yaml
  scrape_configs:
    - job_name: my-service
      static_configs:
        - targets: ["my-service:8080"]
  ```

- Reload Prometheus config:
  ```bash
  docker compose -f monitoring/docker-compose.monitoring.yml exec prometheus \
    wget -qO- --post-data='' http://localhost:9090/-/reload
  ```

Best practices
- Use histogram metrics for latency (not summaries) for aggregatable percentiles.
- Include meaningful labels for filtering and grouping (job, instance, status, etc.).
- Set appropriate scrape intervals (15s for most services, 1m for low-frequency metrics).
- Use recording rules for expensive queries (pre-compute complex PromQL).
- Monitor Prometheus own health via `/targets` and `/prometheus` metrics.
- Set retention policy based on storage capacity (default 15 days).
- Use Grafana for visualization, Prometheus for data collection.
- Test configuration changes in staging before production.
- Use `promtool` to validate configuration syntax.
- Keep time-series count under 1 million for performance (use labels carefully).
- Query with `rate()` or `irate()` for counters, not raw values.
- Use `sum() by (label)` for aggregations across labels.

Troubleshooting
- Prometheus won't start:
  - Check configuration syntax: `promtool check config prometheus.yml`
  - Verify volume permissions: `docker volume inspect prometheus-data`
  - Check port conflicts: `lsof -i :9090`
  - Review logs: `docker compose -f monitoring/docker-compose.monitoring.yml logs prometheus`

- Targets not scraping:
  - Verify target health: `curl http://localhost:9090/targets`
  - Check network connectivity: `docker compose exec prometheus ping <service-name>`
  - Verify /metrics endpoint: `curl http://<service-host>:<port>/metrics`
  - Check service logs for errors

- High memory usage:
  - Check time-series count: `curl http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series`
  - Reduce label cardinality (high cardinality labels cause memory bloat).
  - Adjust retention policy: `--storage.tsdb.retention.time=7d`

- Queries slow:
  - Check query statistics: `http://localhost:9090/consoles/prometheus.html`
  - Optimize expensive queries with recording rules.
  - Reduce query time ranges or increase step interval.
  - Check for slow scrapes: `rate(prometheus_tsdb_compaction_duration_seconds)`

- Disk space full:
  - Check data size: `du -sh /var/lib/docker/volumes/pmoves_prometheus-data`
  - Adjust retention: Add `--storage.tsdb.retention.time=7d` to command args.
  - Create snapshot and backup old data.
  - Monitor via `prometheus_tsdb_storage_blocks_bytes metric`.

Ops Quicklinks
- Prometheus documentation: https://prometheus.io/docs
- PromQL reference: https://prometheus.io/docs/prometheus/latest/querying/basics/
- Best practices: https://prometheus.io/docs/practices/
- Alerting guide: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Client libraries: https://prometheus.io/docs/instrumenting/clientlibs/
- PMOVES monitoring config: `pmoves/monitoring/prometheus/prometheus.yml`
- Alert rules: `pmoves/monitoring/prometheus/alert.rules.yml`
- Monitoring compose: `pmoves/monitoring/docker-compose.monitoring.yml`
- Grafana dashboards: `pmoves/monitoring/grafana/dashboards/`

Storage and retention
- Default retention: 15 days (configurable).
- Storage location: `/prometheus` volume (`prometheus-data`).
- Estimated data size: ~1GB per day for 100 scrape targets with 15s interval.
- Check disk usage: `docker exec prometheus du -sh /prometheus`
- Adjust retention: Add `--storage.tsdb.retention.time=<duration>` to command args.

Performance tuning
- Reduce scrape interval for low-frequency metrics (30s or 1m).
- Increase evaluation interval for recording rules (30s or 1m).
- Use `--storage.tsdb.retention.time` to limit disk usage.
- Monitor `prometheus_tsdb_head_samples_appended_total` for write throughput.
- Monitor `prometheus_tsdb_compaction_duration_seconds` for compaction health.
- Consider remote write for long-term storage (Thanos, VictoriaMetrics, Cortex).
