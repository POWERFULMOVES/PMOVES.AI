# Monitoring Stack Integration for SEED BRANCHED DEFAULTS

## Overview

This document describes the **production monitoring stack** that should be enabled as part of the hardened PMOVES.AI baseline. All monitoring components have been tested and are production-ready.

## Components

| Service | Port | Purpose | Profile |
|---------|------|---------|----------|
| **Prometheus** | 9090 | Metrics collection & aggregation | monitoring |
| **Grafana** | 3002 | Dashboard visualization | monitoring |
| **Loki** | 3100 | Log aggregation | monitoring |
| **Promtail** | 9115 | Container log collection | monitoring |
| **Blackbox** | 9115 | Exported metrics (container stats) | monitoring |

## Startup Commands

### Start All Services
```bash
# Option 1: Using monitoring profile
docker compose -f pmoves/docker-compose.monitoring.yml up -d

# Option 2: Using main compose (recommended)
docker compose --profile monitoring up -d
```

### Start Individual Components
```bash
# Prometheus only
docker compose up prometheus

# Grafana only
docker compose up grafana

# All monitoring stack
docker compose up prometheus grafana loki promtail blackbox
```

## Access URLs

| Service | URL | Credentials |
|---------|-----|------------|
| **Grafana** | http://localhost:3002 | admin / admin |
| **Prometheus** | http://localhost:9090 | - |
| **Prometheus UI** | http://localhost:9090/targets | - |

## Service Health Checks

### Prometheus
```bash
curl -f http://localhost:9090/-/ready || exit 1
```

### Grafana
```bash
curl -f http://localhost:3002/api/health || exit 1
```

### Loki
```bash
curl -f http://localhost:3100/ready || exit 1
```

### Promtail
```bash
# Check via Prometheus
curl http://localhost:9090/api/v1/query?query=up{job="promtail"}
```

## Network Architecture

All monitoring services connect via:
- **pmoves_monitoring** bridge network (172.30.5.0/24)
- Connection to other tier networks for metrics collection

## Configuration Files

| File | Purpose |
|------|---------|
| `pmoves/monitoring/prometheus/prometheus.yml` | Prometheus configuration |
| `pmoves/monitoring/grafana/datasources/*` | Dashboard definitions |
| `pmoves/monitoring/loki/local-config.yaml` | Loki configuration |
| `pmoves/monitoring/promtail/config.yml` | Promtail configuration |

## Integration with PMOVES Services

### Target Labels Format
Services expose metrics with standardized labels:
- `job="promtail"` - For Promtail scraper
- `monitoring_job="true"` - Indicates monitoring job
- Service-specific labels via container name or environment

### Data Retention

- **Prometheus**: 15 days default (configurable)
- **Grafana**: Dashboards auto-loaded from datasources
- **Loki**: Logs from all services via Promtail

## Troubleshooting

### Services Not Starting
```bash
# Check if service is running
docker ps | grep prometheus

# Check logs
docker logs prometheus
docker logs grafana

# Restart individual service
docker compose restart prometheus
```

### Health Check Endpoints

| Endpoint | Expected Response |
|----------|------------------|
| `GET /api/healthz` | Agent Zero health |
| `GET /-/ready` | Monitoring ready check |
| `GET /metrics` | Prometheus metrics API |

## Production Notes

- All monitoring services run with **read-only** rootfs for security
- `cap_drop: [ALL]` for privilege removal
- `security_opt: [no-new-privileges:true]` for hardening
- Networks isolated in tiered bridge networks

## See Also

- [Makefile](../Makefile) - Full target reference
- [Docker Compose Networking Guide](./DOCKER_COMPOSE_NETWORKING_GUIDE.md)
- [Service Discovery](../SERVICE_DISCOVERY.md)
