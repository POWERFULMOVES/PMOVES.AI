# Alertmanager Discord Bridge

## Overview

The Alertmanager Discord Bridge receives webhook payloads from Prometheus Alertmanager
and forwards them as rich Discord embed messages with severity-based color coding.

Part of **PMOVES-P3 Recommendation #4**: Configure Alertmanager for PMOVES.AI.

## Architecture

```
Prometheus -> Alertmanager -> Discord Bridge -> Discord Channel
                (routing)     (formatting)     (notification)
```

### Alert Flow

1. Prometheus evaluates alert rules (20+ rules across 7 groups)
2. Firing alerts are sent to Alertmanager
3. Alertmanager routes by severity: critical, warning, info, default
4. Discord bridge formats alerts as rich embeds with color coding
5. Embeds are posted to configured Discord webhook

### Severity Routing

| Severity | Color   | Group Wait | Repeat Interval | Response Time |
|----------|---------|------------|-----------------|---------------|
| Critical | Red     | 5s         | 1h              | 5 minutes     |
| Warning  | Yellow  | 30s        | 12h             | 30 minutes    |
| Info     | Blue    | 30s        | 24h             | Next shift    |
| Default  | Grey    | 10s        | 4h              | Best effort   |

### Inhibition Rules

- Critical alerts automatically suppress warning alerts for the same alertname + service
- Prevents alert fatigue during incidents

## Services

### Alertmanager (pmoves-alertmanager)

- **Image**: prom/alertmanager:v0.28.1
- **Port**: 9093 (configurable via ALERTMANAGER_PORT)
- **Config**: config/alertmanager/alertmanager.yml
- **Network**: pmoves_monitoring

### Discord Bridge (pmoves-alertmanager-discord-bridge)

- **Port**: 9094 (configurable via BRIDGE_PORT)
- **Network**: pmoves_monitoring
- **Health**: GET /health
- **Metrics**: GET /metrics

## Deployment

### Using Docker Compose Overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.alertmanager.yml up -d
```

### Environment Variables

| Variable                              | Required | Default    | Description                 |
|---------------------------------------|----------|------------|-----------------------------|
| ALERTMANAGER_DISCORD_WEBHOOK_URL      | Yes      | -          | Discord channel webhook URL |
| DISCORD_WEBHOOK_URL                   | Alt      | -          | Alias for above             |
| ALERTMANAGER_PORT                     | No       | 9093       | Alertmanager HTTP port      |
| ALERTMANAGER_BIND                     | No       | 127.0.0.1  | Alertmanager bind address   |
| BRIDGE_PORT                           | No       | 9094       | Bridge HTTP port            |
| BRIDGE_BIND                           | No       | 127.0.0.1  | Bridge bind address         |
| BRIDGE_LOG_LEVEL                      | No       | INFO       | Python log level            |

### Setting the Discord Webhook

Add to env.shared or the appropriate tier env file:

```bash
ALERTMANAGER_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## Prometheus Integration

Add to your prometheus.yml:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
```

## API Endpoints

### POST /alerts
Default alert receiver (all severities).

### POST /alerts/critical
Critical severity receiver.

### POST /alerts/warning
Warning severity receiver.

### POST /alerts/info
Info severity receiver.

### GET /health
Health check. Returns:
```json
{
  "status": "healthy",
  "webhook_configured": true,
  "uptime_seconds": 3600
}
```

### GET /metrics
Prometheus-compatible metrics:
- alertmanager_bridge_alerts_received_total{severity, status}
- alertmanager_bridge_alerts_sent_total{severity}
- alertmanager_bridge_alerts_failed_total{severity}
- alertmanager_bridge_up

## Runbooks

Severity-specific runbooks at config/alertmanager/runbooks/:

- critical-runbook.md -- 5-minute response, full incident procedure
- warning-runbook.md  -- 30-minute response, standard investigation
- info-runbook.md     -- Awareness only, trend analysis

## Existing Alert Rules

PMOVES.AI has 20+ alert rules across 7 groups:

| Group             | Rules | Severities           |
|-------------------|-------|----------------------|
| service_health    | 2     | critical, warning    |
| error_rates       | 3     | warning              |
| latency           | 3     | warning              |
| resources         | 3     | warning              |
| agents            | 2     | warning              |
| data_pipeline     | 3     | warning              |
| security          | 2     | warning, info        |
| github_runners    | 5     | critical, warning    |

Source: monitoring/prometheus/alert.rules.yml

## Troubleshooting

### Bridge not sending to Discord

1. Check DISCORD_WEBHOOK_URL is set
2. Check bridge logs: docker logs pmoves-alertmanager-discord-bridge --tail 50
3. Test webhook manually with curl

### Alertmanager not receiving alerts

1. Check Prometheus config has alertmanager target
2. Check Alertmanager UI: http://localhost:9093
3. Check Alertmanager logs: docker logs pmoves-alertmanager --tail 50

---

*Part of PMOVES.AI Observability (P3) | Last updated: 2026-04-10*
