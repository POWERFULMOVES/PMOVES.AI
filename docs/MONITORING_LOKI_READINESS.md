# Loki Readiness and Grafana Alerts

## Readiness Probe
- Endpoint: `GET http://localhost:3100/ready`
- Make helper: `make -C pmoves loki-ready` (expects HTTP 200)

## Grafana Alert (Example Panel JSON)
- Import the example panel from `docs/grafana/loki_readiness_panel.json` into your dashboard.
- The panel flags non‑200 readiness or scrape errors.

## Notes
- On Linux desktops, cAdvisor can be included for container metrics: `MON_INCLUDE_CADVISOR=true make -C pmoves up-monitoring`.
