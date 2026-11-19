# MCP Server → Node Map

## Purpose

Single reference for where each first-party MCP package runs, how fleet nodes reach it, which env var carries its secret, and how it is wired into Agent Zero. Target placement defined by the `feat/mcp-server-node-mapping` lane; rows marked **PLANNED** are not yet deployed.

## Node placement

| Package | Node (target) | Runtime shape | Endpoint | Auth env var | Status |
| --- | --- | --- | --- | --- | --- |
| `pmoves-tailscale-mcp` | **KVM2** (Hostinger VPS) | container (`--network none`, mounts `tailscaled.sock`), no published ports | `PMOVES_TAILSCALE_MCP_ENDPOINT` | tailnet-local (tailscaled socket auth) | **deployed + verified on KVM2** (MCP handshake + tools/list) |
| `pmoves-composio-mcp-plugin` (hosted Composio Connect, proxied) | **SPARK** (first, live-target) → **KVM2** (kit ready) | supergateway 4.2.0 container (`supercorp/supergateway:4.2.0@sha256:61ffc26b…`, amd64+arm64) re-serving `https://connect.composio.dev/mcp` over streamable HTTP, loopback bind `127.0.0.1:8190` (`COMPOSIO_MCP_BIND`/`COMPOSIO_MCP_PORT`). Kit `deploy/kvm2/composio-mcp/`; SPARK `make -C pmoves up-composio-mcp`, proof `make -C pmoves composio-mcp-smoke` | SPARK host `http://127.0.0.1:8190/composio/mcp`; in-mesh `COMPOSIO_MCP_ENDPOINT=http://composio-mcp:8000/composio/mcp`; KVM2 `https://<kvm2>.<tailnet>.ts.net:8190/composio/mcp` via `tailscale serve` | Upstream: `COMPOSIO_MCP_CONSUMER_KEY` (`ck_` Connect consumer key, sent as `x-consumer-api-key`) — **not** `COMPOSIO_API_KEY` (that slot now carries a `uak_` user key). Callers: `COMPOSIO_MCP_GATEWAY_KEY` (Bearer). Both live in the proxy's chmod-600 env file | **NOT DEPLOYED (2026-10-21)** — compose blocks are operator-apply (`pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md`); proxy-owned `ck_` client not yet minted; tool list unverified. The old plan's `@composio/mcp` is deprecated upstream, and Composio ships no self-hostable MCP server |
| `titanmail` (seed spec) | **KVM2** | MCP server, loopback bind | `PMOVES_TITANMAIL_MCP_ENDPOINT=http://kvm2:<PORT>/sse` | composio connectors reuse `COMPOSIO_API_KEY` | **SEED SPEC ONLY** — see `research/analyses/2026-10-09_TITANMAIL_MCP_SPEC.md` |
| `pmoves-cipher-mcp` | **A0 prod side (8081 stack)** | compose service `cipher-api` | `PMOVES_CIPHER_MCP_ENDPOINT=http://pmoves-cipher-mcp:8080/sse`; streamable-http form `CIPHER_MCP_HTTP_URL=http://cipher-api:8105/mcp` | `CIPHER_API_TOKEN` (Bearer header) | live |
| `pmoves-e2b-mcp-server` | **GPU node** | container | `PMOVES_E2B_MCP_ENDPOINT` | `E2B_API_KEY` | mapping defined |
| `pmoves-nats-mcp` | **Bus node** (JetStream host) | container | `PMOVES_NATS_MCP_ENDPOINT` | `NATS_URL` (no per-call auth; broker ACLs) | mapping defined |
| `pmoves-hirag-mcp` | compose mesh (with HiRAG service) | container | `PMOVES_HIRAG_MCP_ENDPOINT=http://pmoves-hirag-mcp:8080/sse` | internal mesh | live |

## Fleet access model

- VPS-hosted MCP servers (KVM2) bind **127.0.0.1 only**. Fleet nodes reach them over **Tailscale**, never the public internet.
- Compose-mesh servers use in-network DNS names (`http://pmoves-<name>-mcp:8080/sse`) on the shared A0 network.
- Tailscale status checks go through `make -C pmoves fleet-status` (raw `tailscale status` leaks IPs — Known Road).

## Wiring patterns

### 1. `A0_SET_mcp_servers` (A0 seeds its MCP client at init)

Defined per-compose in `pmoves/docker-compose.agents.yml` (~line 135, mirrored in `pmoves/docker-compose.yml`). Two entry forms:

```jsonc
{
  "mcpServers": {
    // stdio form (command-based):
    "docker": { "command": "docker", "args": ["run", "--rm", "-i", "mcp/docker"] },
    // streamable-http form (url-based, auth via headers):
    "cipher": {
      "type": "streamable-http",
      "url": "${CIPHER_MCP_HTTP_URL:-http://cipher-api:8105/mcp}",
      "headers": { "Authorization": "Bearer ${CIPHER_API_TOKEN}" }
    }
  }
}
```

Remote/loopback MCP endpoints (titanmail, tailscale-on-KVM2) wire in as `streamable-http`/SSE entries pointing at `http://kvm2:<port>/sse` once the tailnet route exists. Composio's A0 entry (`composio`, streamable-http, `${COMPOSIO_MCP_ENDPOINT}` + `Authorization: Bearer ${COMPOSIO_MCP_GATEWAY_KEY}`, `"disabled": ${COMPOSIO_MCP_A0_DISABLED:-true}`) is Block 3 of `pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md` — operator-apply, ships disabled; A0's `MCPConfig` records a failing server as that server's error and keeps booting.

### 2. `PMOVES_*_MCP_ENDPOINT` convention (`env.shared.example`)

```bash
PMOVES_CIPHER_MCP_ENDPOINT=http://pmoves-cipher-mcp:8080/sse
PMOVES_E2B_MCP_ENDPOINT=http://pmoves-e2b-mcp:8080/sse
PMOVES_HIRAG_MCP_ENDPOINT=http://pmoves-hirag-mcp:8080/sse
PMOVES_NATS_MCP_ENDPOINT=http://pmoves-nats-mcp:8080/sse
PMOVES_TAILSCALE_MCP_ENDPOINT=http://pmoves-tailscale-mcp:8080/sse
# post-deploy additions (KVM2, tailnet):
COMPOSIO_MCP_ENDPOINT=http://composio-mcp:8000/composio/mcp   # SPARK in-mesh; KVM2: https://<kvm2>.<tailnet>.ts.net:8190/composio/mcp
# PMOVES_TITANMAIL_MCP_ENDPOINT=http://kvm2:<PORT>/sse
```

### 3. Operational rules

- Tier files (`env.tier-*`) are **funnel outputs** — never hand-edit; the funnel is the only supported path (`make -C pmoves secrets-funnel`, defined in `pmoves/mk/codex.mk`).
- Raw `docker compose -f <overlay>.yml up` fails (base-layer networks) — use `make -C pmoves overlay-up-<tier>` / `up-<svc>` (Known Road).
- On VPS nodes, deploy secrets via env files (`/opt/<svc>/.env`, chmod 600) — API keys **never** on command lines or in logs.

## Pending items (2026-10-09)

1. **KVM2 SSH access broken from the Windows host**: both routes (`167.88.38.57`, `31.97.42.207:22`) timed out (circuit breaker: 2 attempts, stopped). Additionally `HOSTINGER_SSH_PRIVATE_KEY` in `env.tier-agent` is **structurally truncated** (value = BEGIN header only, no key body/END marker) — re-funnel the key before the KVM2 deployment lane.
2. Composio proxy (updated 2026-10-21): kit + Make road landed (`deploy/kvm2/composio-mcp/`, `up-composio-mcp`, `composio-mcp-smoke`, host port 8190). **Not executed** on SPARK or KVM2: needs the operator-applied compose blocks, a `ck_` key for a proxy-owned Connect client, and (KVM2) the Hostinger project + `tailscale serve` steps in `deploy/kvm2/composio-mcp/README.md`. Record the KVM2 tailnet URL here after deploy.
3. Titanmail build: see seed spec; placement KVM2.
