# Observability Map
_Generated: 2026-02-18 16:45:11_

## Scrape Jobs
| Job | Targets (config) | Module/Path | Live Health (up/total) |
| --- | --- | --- | --- |
| `agent-zero` | agent-zero:8080 | `/metrics` | n/a |
| `archon` | archon:8091 | `/metrics` | n/a |
| `blackbox_http` | http://agent-zero:8080/healthz, http://hi-rag-gateway-v2:8086/hirag/admin/stats, http://host.docker.internal:8087/ (+5 more) | `http_2xx` | n/a |
| `cadvisor` | cadvisor:8080 | `/metrics` | n/a |
| `deepresearch-metrics` | deepresearch:8098 | `/metrics` | n/a |
| `extract-worker` | extract-worker:8083 | `/metrics` | n/a |
| `flute-gateway` | flute-gateway:8055 | `/metrics` | n/a |
| `gpu-orchestrator` | gpu-orchestrator:8200 | `/metrics` | n/a |
| `hi-rag-gateway-v2` | http://hi-rag-gateway-v2:8086/hirag/admin/stats | `http_2xx` | n/a |
| `jellyfin-bridge` | jellyfin-bridge:8093 | `/metrics` | n/a |
| `langextract` | langextract:8084 | `/metrics` | n/a |
| `loki` | loki:3100 | `/metrics` | n/a |
| `messaging-gateway` | messaging-gateway:8101 | `/metrics` | n/a |
| `notebook-sync` | notebook-sync:8095 | `/metrics` | n/a |
| `pdf-ingest` | pdf-ingest:8092 | `/metrics` | n/a |
| `pmoves-yt` | pmoves-yt:8077 | `/metrics` | n/a |
| `presign` | presign:8080 | `/metrics` | n/a |
| `prometheus` | prometheus:9090 | `/metrics` | n/a |
| `render-webhook` | render-webhook:8085 | `/metrics` | n/a |
| `session-context-worker` | session-context-worker:8100 | `/metrics` | n/a |
| `supabase-postgres` | postgres-exporter:9187 | `/metrics` | n/a |
| `supabase-realtime` | http://realtime:4000/api/ping | `http_2xx_or_401` | n/a |
| `supabase_health` | http://auth:9999/health, http://rest:3000/, http://realtime:4000/ | `http_2xx_or_401` | n/a |
| `supaserch-metrics` | supaserch:8099 | `/metrics` | n/a |
| `tensorzero-gateway` | tensorzero-gateway:3000 | `/metrics` | n/a |

## Dashboard Coverage
| Job | Dashboards |
| --- | --- |
| `agent-zero` | `agent-zero.json` (heuristic) |
| `archon` | `archon.json` (heuristic) |
| `blackbox_http` | _none_ |
| `cadvisor` | _none_ |
| `deepresearch-metrics` | `deepresearch.json` (heuristic) |
| `extract-worker` | `extract-worker.json` (heuristic) |
| `flute-gateway` | `flute-gateway.json` (heuristic) |
| `gpu-orchestrator` | `gpu-orchestrator.json` (heuristic) |
| `hi-rag-gateway-v2` | _none_ |
| `jellyfin-bridge` | _none_ |
| `langextract` | _none_ |
| `loki` | _none_ |
| `messaging-gateway` | `messaging-gateway.json` (heuristic) |
| `notebook-sync` | _none_ |
| `pdf-ingest` | _none_ |
| `pmoves-yt` | `pmoves-yt.json` (heuristic) |
| `presign` | _none_ |
| `prometheus` | _none_ |
| `render-webhook` | `render-webhook.json` (heuristic) |
| `session-context-worker` | `session-context-worker.json` (heuristic) |
| `supabase-postgres` | `supabase.json` (heuristic) |
| `supabase-realtime` | `supabase.json` (heuristic) |
| `supabase_health` | `supabase.json` (heuristic) |
| `supaserch-metrics` | `supaserch.json` (heuristic) |
| `tensorzero-gateway` | `tensorzero.json` (heuristic) |

## Gaps
- Scrape jobs with no explicit dashboard job selector:
  - `blackbox_http`
  - `cadvisor`
  - `hi-rag-gateway-v2`
  - `jellyfin-bridge`
  - `langextract`
  - `loki`
  - `notebook-sync`
  - `pdf-ingest`
  - `presign`
  - `prometheus`
- No orphaned dashboard job selectors detected.

## Notes
- `monitoring-smoke` validates monitoring stack readiness + blackbox samples.
- `monitoring-smoke-prod` adds required-job assertions for production audits.
- Run `make -C pmoves observability-audit` after changing Prometheus jobs or Grafana dashboards.

