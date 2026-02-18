# Observability Dashboard

Check the status of the monitoring stack (Prometheus, Grafana, Loki).

## Instructions

Check health of the observability stack:
1. **Prometheus** (port 9090) - Metrics scraping
2. **Grafana** (port 3000) - Dashboard visualization
3. **Loki** (port 3100) - Log aggregation

```bash
# Prometheus health
curl -s http://localhost:9090/-/healthy && echo "Prometheus: healthy" || echo "Prometheus: unhealthy"
```

```bash
# Grafana health
curl -s http://localhost:3000/api/health | python -c "import sys,json; d=json.load(sys.stdin); print(f'Grafana: {d.get(\"database\",\"?\")} version={d.get(\"version\",\"?\")}')"
```

```bash
# Loki health
curl -s http://localhost:3100/ready && echo "Loki: ready" || echo "Loki: not ready"
```

```bash
# Container status
docker ps --filter "name=prometheus" --filter "name=grafana" --filter "name=loki" --filter "name=promtail" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Report:
- Each service health status
- Prometheus target count (up vs down)
- Grafana dashboard availability
- Loki ingestion rate
