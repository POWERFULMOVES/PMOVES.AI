# BoTZ MCP Gateway — Deploy Spec (for review)

**Status:** DRAFT spec — nothing deployed. Review before building.
**Author:** 4090-claude · 2026-06-20
**Goal:** stand up `PMOVES-BotZ-gateway` (fork of `microsoft/mcp-gateway`, .NET, port 8052) as the **host-reachable unified MCP front** that routes to internal-tier MCP backends (Cipher, Hi-RAG, the 5 observability MCPs). This is also the *only* correct way for the host-side Claude Code MCP client to reach Cipher, since `pmoves_*` are `internal: true`.

## Disambiguation (important)
- **`PMOVES-BotZ-gateway/`** (submodule, .NET, :8052, `microsoft/mcp-gateway` fork) — the **MCP reverse-proxy** with `/adapters` control plane. ← THIS is what we deploy.
- **`services/botz-gateway/`** (in-repo Python, :8102, "bot mgmt + Geometry BUS", `make up-bots`) — a *different* service. Not the MCP gateway. Leave as-is.

## The central constraint
`pmoves_app/bus/data` are `internal: true` (docker-compose.yml ~4272-4284). **A container on internal-only networks cannot publish a host port.** Therefore the gateway must be attached to **two** networks:
1. **`pmoves_app`** (internal) — to reach `cipher-api:8105`, `hi-rag-gateway-v2`, etc.
2. **a non-internal bridge** — to publish `:8052` to the host. Options: (a) reuse an existing non-internal pmoves network if one exists, or (b) **add a `pmoves_edge` bridge network (`internal: false`)** dedicated to host-facing gateways. Verify which non-internal nets already exist (`docker network ls` + grep compose for `internal: false`/networks without the flag) before creating a new one.

## Phase A — Deploy the gateway as a compose service

Add a `botz-mcp-gateway` service (own overlay `docker-compose.botz-mcp.yml`, or into `docker-compose.agents.yml`). Sketch (verify .NET build specifics against `PMOVES-BotZ-gateway/Dockerfile` + `docker-compose.pmoves.yml` template + `PMOVES.AI_INTEGRATION.md`):

```yaml
services:
  botz-mcp-gateway:
    build:
      context: ../PMOVES-BotZ-gateway
      dockerfile: Dockerfile            # confirm path (dotnet/ subdir?)
    image: ${BOTZ_MCP_GATEWAY_IMAGE:-ghcr.io/powerfulmoves/pmoves-botz-mcp-gateway:pmoves-latest}
    environment:
      - ASPNETCORE_URLS=http://0.0.0.0:8052
      - BOTZ_GATEWAY_TOKEN=${BOTZ_GATEWAY_TOKEN:-}      # control-plane auth (secrets pipeline)
    ports:
      - "${BOTZ_GATEWAY_BIND:-127.0.0.1}:8052:8052"      # host publish (needs non-internal net below)
    networks: [pmoves_app, pmoves_edge]                  # internal (reach backends) + non-internal (host publish)
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8052/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
networks:
  pmoves_edge:
    driver: bridge
    internal: false        # ONLY if no existing non-internal net is reused
```

**Known-Road compose edit:** `pmoves/docker-compose*.yml` are guard-protected by basename — author this under the documented elevation (chitSafePaths allow-list entry with a stated reason, or `KNOWN_ROAD=compose:pr:<n>` at session launch), NOT a renamed file. (Per [[feedback_governance_flow_not_walls]].)
**Bring-up:** add a `make up-botz-mcp` target mirroring the hi-rag single-service pattern (`$(DC) up -d --no-deps --build --recreate botz-mcp-gateway`) so it's a Known Road, not raw compose.

## Phase B — Register adapters (control plane)

Once `:8052/healthz` is green, register one adapter per backend (persist in `PMOVES-BotZ-gateway/deployment/` or a boot seed so they survive restart):

| Adapter | Backend (reachable over pmoves_app) | Transport |
|---|---|---|
| `cipher` | `http://cipher-api:8105/mcp/sse` | SSE (native) |
| `hirag` | `pmoves-hirag-mcp` bridge → Hi-RAG v2 (`hi-rag-gateway-v2:8086`) | stdio/streamable-http (containerize the bridge) |
| `grafana` | `python -m pmoves.tools.observability.mcp_grafana` | stdio |
| `prometheus` | `…mcp_prometheus` | stdio |
| `loki` | `…mcp_loki` | stdio |
| `jaeger` | `…mcp_jaeger` | stdio |
| `tensorzero` | `…mcp_tensorzero` | stdio |
| `jcodemunch` | PMOVES-jcodemunch-mcp (after onboarding) | per its README |

`curl -X POST http://localhost:8052/adapters -H "Authorization: Bearer $BOTZ_GATEWAY_TOKEN" -d '{"name":"cipher","transport":"sse","url":"http://cipher-api:8105/mcp/sse"}'` (confirm exact schema against the gateway's OpenAPI in `PMOVES-BotZ-gateway/openapi/`).

## Phase C — Repoint clients to the gateway

- **`.claude/mcp.json`**: add `pmoves-mcp-gateway` → sse `http://localhost:8052/mcp` (Bearer `${BOTZ_GATEWAY_TOKEN}`). **Keep the direct `pmoves-cipher` entry as transition fallback**, retire after validation (same discipline as the `_pmoves-cipher-legacy-python-wrapper` entry). NOTE: the direct `pmoves-cipher` localhost:8105 entry **cannot work on this host** (internal net) — the gateway entry is what actually connects.
- **`pmoves/docker/pmoves-4090-web/profile.yaml`**: replace per-server blocks with the single gateway server.

## Phase D — Validate (via MCP skills)
- `curl localhost:8052/healthz` (host reach proves the non-internal-net bridge works).
- Through the gateway: list tools; round-trip one low-effect tool per adapter (cipher store/search, prometheus instant query, hirag query).
- This is also the **host-reachable Cipher fix** (task #3) and the 100+ tool/agent unlock.

## Verify-at-deploy unknowns (flagged)
1. `PMOVES-BotZ-gateway/Dockerfile` build path + .NET base image size (could be a slow pull — schedule when registry isn't throttled).
2. Exact `/adapters` POST schema (read `openapi/`).
3. Whether an existing non-internal pmoves network can be reused vs creating `pmoves_edge`.
4. `BOTZ_GATEWAY_TOKEN` provisioning via the secrets pipeline (add to manifest → `secrets-funnel`).
5. The `pmoves-hirag-mcp` bridge must be containerized/registerable (it's stdio today) — ties to task #6.

## Dependencies / order
Onboard `pmoves-hirag-mcp` repo (task #6) before its adapter. Observability MCPs (#1361) already exist. Cipher already healthy. gateway-agent (:8100, separate) is the Agent-Zero MCP-tool orchestrator — complementary, not this gateway.
