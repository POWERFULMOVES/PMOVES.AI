# Service Health Endpoints & Console Badges

The PMOVES console renders Quick Links with live health badges. Some integrations expose different health paths depending on the fork or image you run. You can customize the badge probes via environment variables.

## Agent Zero (MCP)
- Default base URL: `NEXT_PUBLIC_AGENT_ZERO_URL` (default `http://localhost:8080`)
- Health path override: `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`)
- Fallback order if the custom path fails: `/healthz` → `/api/health` → `/`

## Archon (MCP)
- Default base URL: `NEXT_PUBLIC_ARCHON_URL` (default `http://localhost:8091`)
- Health path override: `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`)
- Fallback order: `/healthz` → `/api/health` → `/`

## HiRAG Gateway v2 (REST-only — no MCP)
- Base URL: `http://localhost:8086` (compose `pmoves-hi-rag-gateway-v2-1`)
- Query: `POST /hirag/query` — body `QueryReq`: `query`, `namespace`, `k`, `alpha`, `use_rerank`, `rerank_topn`, `rerank_k`, `entity_types`. NOT `top_k`/`rerank` (unknown fields are silently dropped; fixed in Pmoves-cipher PR #14).
- Health: `GET /` answers `{"ok":true,"service":"hi-rag-gateway-v2","hint":"POST /hirag/query"}`; admin: `/hirag/admin/stats`
- OpenAPI: `GET /openapi.json`. No MCP endpoint exists on this port — MCP clients must not target it.

## Agent Zero MCP (SSE + token)
- API/UI: `http://localhost:8080`; UI also published on `:8081`
- MCP surface: SSE `http://localhost:8081/mcp/t-${AGENT_ZERO_MCP_TOKEN}/sse` (token embedded in path — generator-canonical). `:8080/mcp` answers "session not found" — do not use.

## Cipher API (memory + MCP)
- Base URL: `http://localhost:8105` (compose `pmoves-cipher-api-1`)
- MCP surface: SSE `http://localhost:8105/mcp/sse`, bearer `${CIPHER_API_TOKEN:-}` (empty bearer accepted by current server)
- Health: `GET /health` (container healthcheck). Image must postdate the #2729/#2762 server fixes — older images 401 both SSE paths.

## Archon port map (verified 2026-09-03)
- Host `:8091` and `:3737` both map to container `:3090` — same service. Archon is REST-only (fleet decision #2303): rich health `GET /api/health`, simple `GET /health`. No MCP.
- Do NOT point other services' MCP configs at `:8091` — it is Archon, not BoTZ.

## BoTZ Gateway
- Base URL: `http://localhost:8054` (compose `pmoves-botz-gateway-1`)
- `/mcp` answers 404 — MCP surface unverified (as of 2026-09-03).

## PostgREST / Personas (pmoves_core)
When Supabase CLI REST (65421) does not expose the `pmoves_core` schema, the console can query an alternate PostgREST directly using the `Accept-Profile: pmoves_core` header.

- Console fallback REST base: `POSTGREST_URL` (default `http://localhost:3010` if compose PostgREST is running)
- Optional service wired to Supabase CLI DB:
  - Compose service `postgrest-cli` publishes `http://localhost:3011` by default.
  - Start it with: `docker compose -p pmoves up -d postgrest-cli`
  - Then set `POSTGREST_URL=http://localhost:3011`.

## Example (pmoves/env.shared)
```
NEXT_PUBLIC_AGENT_ZERO_URL=http://localhost:8080
NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH=/health
NEXT_PUBLIC_ARCHON_URL=http://localhost:8091
NEXT_PUBLIC_ARCHON_HEALTH_PATH=/api/health
POSTGREST_URL=http://localhost:3011
```

After editing `pmoves/env.shared`, run `make -C pmoves env-setup` (or restart the console dev server) so changes apply to the UI.

## Model Registry
- Default base URL: `http://localhost:8110`
- Health path: `/healthz`
- Additional endpoints:
  - `GET /api/models` — List registered models
  - `GET /api/providers` — List model providers
  - `GET /api/deployments` — List active model deployments
- NATS: Publishes `model.registry.updated.v1` on catalog mutations
- Compose profile: `orchestration`

## GPU Orchestrator
- Default base URL: `http://localhost:8200`
- Health path: `/healthz`
- Additional endpoints:
  - `GET /api/v1/status` — GPU status (VRAM, loaded models)
  - `GET /api/v1/models` — List models loaded on GPU
  - `GET /metrics` — Prometheus metrics
- NATS subjects:
  - Publishes: `mesh.gpu.status.v1` (every 5s), `mesh.gpu.model.loaded.v1`, `mesh.gpu.model.unloaded.v1`, `mesh.gpu.vram.warning.v1`
  - Subscribes: `mesh.gpu.command.v1` (load/unload/optimize requests)
  - Publishes: `mesh.gpu.command.result.v1` (command execution results)
- **Note:** Only available when NVIDIA GPU runtime is present. The `make up-model-management` target auto-detects this.
- Compose profile: `gpu`

## Transcribe Backend
- Default base URL: `http://localhost:8074`
- Health path: `/healthz`
- Submodule: `PMOVES-transcribe-and-fetch`
- Compose profile: `workers`
