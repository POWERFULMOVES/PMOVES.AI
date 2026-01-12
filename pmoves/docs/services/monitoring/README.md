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
  - cAdvisor UI/metrics: http://localhost:${CADVISOR_HOST_PORT:-9180}
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
- `CADVISOR_HOST_PORT=9180`
- `MON_INCLUDE_CADVISOR=true` to force-start cAdvisor on non-Linux hosts
- `MON_INCLUDE_NODE_EXPORTER=true` to add host metrics (requires Linux + shared root mount)

- Notes
- On Docker Desktop for Windows/macOS, cAdvisor’s kernel mounts can be limited. If cAdvisor reports unhealthy or fails to start, it will auto-retry; you can also temporarily comment out the service or run only on Linux hosts. The rest of the monitoring stack (Prometheus, Grafana, Blackbox, Loki/Promtail) works cross‑platform.
- When Docker is configured with the containerd image store (`storage-driver overlayfs` / `driver-type: io.containerd.snapshotter.v1`), keep the extra bind mount to `/var/lib/containerd/io.containerd.snapshotter.v1.overlayfs` intact so cAdvisor can read layer metadata. Without it you will see repeated `failed to identify the read-write layer ID` errors and the container list will be empty.
- When Docker Desktop rewrites the image store to the containerd snapshotter, create the overlay shim directory once before starting the stack. Either run `sudo mkdir -p /var/lib/docker/image/overlayfs` or use `docker run --rm --privileged -v /:/host alpine sh -c "mkdir -p /host/var/lib/docker/image/overlayfs"` to seed it without root access. This gives cAdvisor a mount point to bind the snapshotter path onto.
- Node Exporter is now opt-in; enable it with `MON_INCLUDE_NODE_EXPORTER=true make -C pmoves up-monitoring`. It still requires Linux with a shared `/` mount (bare metal or WSL2 with nested virtualization enabled).
- On WSL2 or Docker Desktop, run `sudo mount --make-rshared /` before starting the stack with node exporter enabled; the propagation flag resets after each reboot.
- When cAdvisor runs privileged it refreshes container metadata correctly (no more stale container lists). Restart the monitoring stack after changing Docker storage paths so the new mounts are detected.
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

Readiness & Alerts
- Loki readiness endpoint: `GET http://localhost:3100/ready` (CLI: `make -C pmoves loki-ready`).
- Example stat panel JSON: `docs/grafana/loki_readiness_panel.json`.
- Example alert rule JSON: `docs/grafana/alerts/loki_readiness_alert.json` (import into Grafana alerting and wire a contact point).

CLI helper
- `python pmoves/tools/monitoring_report.py` prints a quick status summary (targets, failures, top CPU containers).
