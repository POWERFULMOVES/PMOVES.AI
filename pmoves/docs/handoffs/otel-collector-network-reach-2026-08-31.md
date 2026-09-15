# Handoff — OTEL collector unreachable by agent-zero + archon exporters (2026-08-31)

**Node:** 5090 · **Lane:** OTEL / A0↔Archon integration validation (operator-requested) · **Author:** 5090-CLAUDE

## What this fixes

`agent-zero` and `archon` both set
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://pmoves-otel-collector:4317`
(`docker-compose.agents.yml:52` and `:286`) — they try to export spans to the collector.

But the **collector (`pmoves-otel-collector`) is attached to `pmoves_monitoring` only**
(`docker-compose.tracing.yml:74-75`), while:

| service | networks | can reach collector? |
|---|---|---|
| otel-collector | `pmoves_monitoring` | — |
| tensorzero-gateway | `pmoves_api,bus,data,monitoring,external` | ✅ (on monitoring) |
| **agent-zero** | `pmoves_app,bus,external,api` | ❌ no monitoring |
| **archon** | `pmoves_api,app,bus` | ❌ no monitoring |

So `pmoves-otel-collector` never resolves for agent-zero/archon and **every span export
silently fails** (the Docker DNS name is only visible to containers sharing a network).
tensorzero traces work only because it happens to be multi-homed onto `pmoves_monitoring`.

(Their *direct* A0↔Archon wiring is fine — both share `pmoves_app`+`pmoves_bus`, and archon's
alias is `archon-server`. The gap is telemetry only.)

## Fix

Multi-home the **collector** onto `pmoves_app` + `pmoves_bus` (in addition to
`pmoves_monitoring`) in `docker-compose.tracing.yml`. One edit fixes every current and future
exporter on those internal networks, rather than adding `pmoves_monitoring` to each app.
The collector still reaches Jaeger/Tempo + Prometheus via `pmoves_monitoring`.

## Deploy / verify

Recreate the collector through the pipeline (tracing overlay), then confirm reachability
from an exporter:
```
# from inside agent-zero or archon, the collector name now resolves:
docker exec pmoves-agent-zero sh -c 'getent hosts pmoves-otel-collector || nslookup pmoves-otel-collector'
# and spans land: check the collector logs / Jaeger UI for agent-zero/archon service names.
```

## Not in this change
- No exporter-side change (the endpoint env is already correct).
- No SPARK PR existed for this (searched open PRs + AGNOTE) — this is the first fix.
