# MCP Server → Node Map

## Purpose

Single reference for where each first-party MCP package runs, how fleet nodes reach it, which env var carries its secret, and how it is wired into Agent Zero. Target placement defined by the `feat/mcp-server-node-mapping` lane; rows marked **PLANNED** are not yet deployed.

## Node placement

| Package | Node (target) | Runtime shape | Endpoint | Auth env var | Status |
| --- | --- | --- | --- | --- | --- |
| `pmoves-tailscale-mcp` | **KVM2** (Hostinger VPS) | container (`--network none`, mounts `tailscaled.sock`), no published ports | `PMOVES_TAILSCALE_MCP_ENDPOINT` | tailnet-local (tailscaled socket auth) | **deployed + verified on KVM2** (MCP handshake + tools/list) |
| `pmoves-composio-mcp-plugin` | **KVM2** | npx `@composio/mcp` proxy container, loopback bind | `COMPOSIO_MCP_ENDPOINT=http://kvm2:<PORT>/sse` (add post-deploy) | `COMPOSIO_API_KEY` (lives in `env.shared` + `env.tier-llm`) | **PLANNED — deploy blocked 2026-10-09** (SSH unreachable + broken key, see Pending) |
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

Remote/loopback MCP endpoints (composio, titanmail, tailscale-on-KVM2) wire in as `streamable-http`/SSE entries pointing at `http://kvm2:<port>/sse` once the tailnet route exists.

### 2. `PMOVES_*_MCP_ENDPOINT` convention (`env.shared.example`)

```bash
PMOVES_CIPHER_MCP_ENDPOINT=http://pmoves-cipher-mcp:8080/sse
PMOVES_E2B_MCP_ENDPOINT=http://pmoves-e2b-mcp:8080/sse
PMOVES_HIRAG_MCP_ENDPOINT=http://pmoves-hirag-mcp:8080/sse
PMOVES_NATS_MCP_ENDPOINT=http://pmoves-nats-mcp:8080/sse
PMOVES_TAILSCALE_MCP_ENDPOINT=http://pmoves-tailscale-mcp:8080/sse
# post-deploy additions (KVM2, tailnet):
# COMPOSIO_MCP_ENDPOINT=http://kvm2:<PORT>/sse
# PMOVES_TITANMAIL_MCP_ENDPOINT=http://kvm2:<PORT>/sse
```

### 3. Operational rules

- Tier files (`env.tier-*`) are **funnel outputs** — never hand-edit; the funnel is the only supported path (`make -C pmoves secrets-funnel`, defined in `pmoves/mk/codex.mk`).
- Raw `docker compose -f <overlay>.yml up` fails (base-layer networks) — use `make -C pmoves overlay-up-<tier>` / `up-<svc>` (Known Road).
- On VPS nodes, deploy secrets via env files (`/opt/<svc>/.env`, chmod 600) — API keys **never** on command lines or in logs.

## Pending items (2026-10-09)

1. **KVM2 SSH access broken from the Windows host**: both routes (`167.88.38.57`, `31.97.42.207:22`) timed out (circuit breaker: 2 attempts, stopped). Additionally `HOSTINGER_SSH_PRIVATE_KEY` in `env.tier-agent` is **structurally truncated** (value = BEGIN header only, no key body/END marker) — re-funnel the key before the KVM2 deployment lane.
2. Composio proxy deployment on KVM2 (docker + `/opt/composio-mcp/.env` + loopback bind + SSE health probe) is specified but **not executed**; port to be recorded here after deploy.
3. Titanmail build: see seed spec; placement KVM2.
