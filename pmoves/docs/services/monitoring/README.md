PMOVES Monitoring Stack (Prometheus + Grafana + Loki)
================================================================

What you get
- Prometheus (metrics, target probes via blackbox)
- Grafana (pre-provisioned with Prometheus + Loki)
- Loki + Promtail (container log aggregation)
- cAdvisor (container CPU/mem/disk/IO)
- Blackbox Exporter (HTTP health for core services)

Quickstart
- Start: `make -C pmoves up-monitoring`
- Open:  `make -C pmoves monitoring-open`
  - Grafana: http://localhost:3002 (admin/admin)
  - Prometheus: http://localhost:9090
- Smoke: `make -C pmoves monitoring-smoke` (wait ~15s on first run)

What’s wired by default
- HTTP probes for:
  - hi-rag-gateway-v2 (CPU): http://localhost:${HIRAG_V2_HOST_PORT:-8086}/hirag/healthz
  - hi-rag-gateway-v2-gpu: http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/hirag/healthz
  - presign: http://localhost:8088/healthz
  - archon: http://localhost:8091/healthz
- channel-monitor: http://localhost:8097/healthz
- deepresearch: http://localhost:8098/healthz
  - jellyfin overlay: http://localhost:9096
  - tensorzero UI: http://localhost:4000
  - n8n: http://localhost:5678
  - Supabase REST (CLI): http://localhost:65421/rest/v1
- Container logs: Promtail tails Docker JSON logs and pushes into Loki.
- Container resources: cAdvisor surfaces per-container CPU/memory for dashboards.

Env knobs
- `PROMETHEUS_HOST_PORT=9090`
- `GRAFANA_HOST_PORT=3002`
- `LOKI_HOST_PORT=3100`
- `CADVISOR_HOST_PORT=8080`
- `MON_INCLUDE_CADVISOR=true` to force-start cAdvisor on non-Linux hosts

Notes
- On Docker Desktop for Windows/macOS, cAdvisor’s kernel mounts can be limited. If cAdvisor reports unhealthy or fails to start, it will auto-retry; you can also temporarily comment out the service or run only on Linux hosts. The rest of the monitoring stack (Prometheus, Grafana, Blackbox, Loki/Promtail) works cross‑platform.
- DeepResearch health is a lightweight FastAPI endpoint inside the worker (port `8098`); it reports `nats_connected` and returns 200 if the process is live.

Linking Agent Zero / Archon traces (future)
- Both services can emit OpenTelemetry (OTLP). When you enable an OTLP collector, set:
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
  - `OTEL_SERVICE_NAME=pmoves`
  and pass through these env vars to `agent-zero` and `archon` services in `docker-compose.yml`.
- This repo ships metrics/logs first; traces can be added with an OTEL Collector + Tempo as a follow-up.

Dashboards
- Grafana ships with a simple “PMOVES Services Overview” dashboard:
  - Up/down widgets for key services
  - HTTP probe duration trend
  - Top containers by CPU (via cAdvisor)
  - Recent logs (via Loki)
  Import your own dashboards as needed.

CLI helper
- `python pmoves/tools/monitoring_report.py` prints a quick status summary (targets, failures, top CPU containers).
