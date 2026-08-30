# Known Road: fix monitoring compose mount paths (observability was a hollow shell)

**Domain:** compose · **File:** `pmoves/monitoring/docker-compose.monitoring.yml`
**Date:** 2026-08-02 · **Proposed by:** z890-claude · **Reason class:** handoff (this file)

## Why this road

The observability stack was running with **empty configs on every service** — a hollow
shell ("observation is a shim, not usable/readable").

Root cause: `make up-monitoring` runs
`docker compose -p monitoring -f monitoring/docker-compose.monitoring.yml up -d` from
`pmoves/`. With `-f` and no `--project-directory`, Compose sets the project dir to the
compose file's own directory (`pmoves/monitoring/`). Every mount was written
`./monitoring/X`, resolving to **`pmoves/monitoring/monitoring/X`** — an empty double-path
Docker auto-creates — instead of the real configs at `pmoves/monitoring/X/`.

Observed (2026-08-02): prometheus **0 scrape targets** + crash-looping; promtail
crash-loop (`/etc/promtail/config.yml does not exist`); no metrics/logs/dashboards → the
ClickHouse disk-faucet (2.4 GB/min) was invisible.

## The change

Make every bind-mount source relative to the compose file's own directory:

    - ./monitoring/<svc>   →   - ./<svc>

(7 mounts: prometheus, grafana×3, loki, promtail, blackbox). Configs live at
`pmoves/monitoring/<svc>/`, so `./<svc>` resolves correctly regardless of project-dir.

## Verified (z890, 2026-08-02 after fix)

Prometheus **24 targets UP** (was 0); promtail **Up** (was crash-looping); all 5 monitoring
containers healthy; no double-dir regenerated.

## Fleet impact + follow-ups

- **Fleet-wide:** every node's monitoring has the same empty-config bug → apply on each.
- cAdvisor is `profiles: ["linux"]` (skipped on Windows z890). Linux nodes get per-container
  disk/write metrics from it; z890 needs an alternative "faucet gauge" — follow-up.
- Next: Grafana panel for per-container write-rate + disk headroom + alert, so a runaway
  shows before it floods. Relates [[project_clickhouse_syslog_runaway]].
