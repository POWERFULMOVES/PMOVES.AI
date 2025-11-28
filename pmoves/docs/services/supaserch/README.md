# PMOVES‑SUPASERCH (Multimodal Holographic Deep Research)

PMOVES‑SUPASERCH (image: `pmoves-supaserch`) is a branded, long‑running, agent‑assisted research service that:

- Orchestrates multimodal research using:
  - DeepResearch worker (OpenRouter/local providers)
  - Archon/Agent Zero tools via MCP (codegen, crawling, tasking)
  - CHIT Geometry Bus for structured representations
  - Supabase/Qdrant/Meili indices for recall
- Surfaces rich, dynamic results to users and PMOVES agents; designed to run continuously in a VM with Internet access.

## Ports & Health
- HTTP: `${SUPASERCH_HOST_PORT:-8099}` → `/healthz` returns `{ "status": "ok" }` and reports NATS connectivity plus fallback target.
- Prometheus: `${SUPASERCH_HOST_PORT:-8099}/metrics` exposes request counts, latency histograms, and fallback counters.

## Environment
- `SUPASERCH_IMAGE` (optional override) — container image to run.
- `SUPASERCH_PORT` (default `8099`) — container HTTP port.
- `NATS_URL` — event bus for request/result envelopes.
- `SUPASERCH_HTTP_FALLBACK_URL` — optional HTTP search endpoint. Supports `{query}` or `{encoded_query}` substitution (defaults to `/healthz`).
- `SUPASERCH_FALLBACK_TIMEOUT` — HTTP fallback timeout in seconds (default `6`).
- `SUPA_REST_URL`, `HIRAG_URL` — REST + Geometry endpoints.

## Compose
Service is defined in `pmoves/docker-compose.yml` under profile `agents`/`workers`.

## Monitoring
- Prometheus blackbox probes `/healthz` (job: `supaserch`).
- Grafana Services Overview shows “Up: SupaSerch”.
- `make supaserch-smoke` publishes an envelope on `supaserch.request.v1`, waits for the result subject, and asserts the HTTP fallback responds with `status: ok`.

## Roadmap Tie‑ins
- Geometry/CHIT first‑class: SUPASERCH will emit geometry packets for downstream decoding.
- Agentic self‑evolving: Agent Zero can task Archon to clone repos and drive code changes (Claude/code LLMs) against local models, with optional cloud assistance.
- Continuous mode: service can run indefinitely (VM/lab nodes), enriching the knowledge graph and indices.

## Build & Publish
- Local multi‑arch push:

```bash
export DOCKER_USERNAME=…
export DOCKER_PASS=…
make -C pmoves docker-login buildx-setup \
  build-push-supaserch REGISTRY=docker.io IMAGE_NAMESPACE=$DOCKER_USERNAME IMAGE_TAG=vYYYYMMDD
```

- GHCR CI: `.github/workflows/integrations-ghcr.yml` builds `pmoves-supaserch` nightly and on demand.

## Integration Points
- NATS subjects: `supaserch.request.v1`, `supaserch.result.v1`
- MCP (future): `mcp://http?endpoint=http://archon_mcp:8051` for tooling
- CHIT bus: emits CGP packets to geometry gateway and Supabase channels.
- HTTP fallback: service issues a resilient HTTP call for availability; configure via `SUPASERCH_HTTP_FALLBACK_URL`.

