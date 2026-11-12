# Handoff: Composio MCP fleet proxy (SPARK first, then KVM2) — operator-apply compose blocks

**Branch:** `feat/composio-mcp-selfhost` · **Written:** 2026-10-21 on SPARK (DGX Spark, aarch64)
**Known Road reason this file provides:** `compose:handoff:COMPOSIO_MCP_SELFHOST.md`

## Why part of this PR is operator-apply

Every compose file in the repo is in the `compose` Known Road domain. The
delivery agent's writes to the two new compose files below were refused by the
write guard (the node's file grant, `compose:pr:3326`, is 284 h old and void),
and agents may not write `.known-road-active` themselves. Per the brief, a
protected-file refusal is not worked around: the exact file contents are here,
reviewed and test-pinned, for the operator to place.

`pmoves/tests/test_composio_mcp_proxy.py` parses the fenced blocks in THIS file
and asserts the contract (loopback bind, tag+digest pin, healthcheck, no
literal key, fail-closed key references). Once the files exist on disk the same
test asserts they are byte-identical to these blocks, so the doc and the kit
cannot drift apart.

### Apply (operator, ~2 minutes)

```bash
# 1. open the road for this job only (expires on its own after 24 h)
echo 'compose:handoff:COMPOSIO_MCP_SELFHOST.md' > .claude/hooks/damage-control/.known-road-active
# 2. place the three blocks below at the paths named in their headers
#    (block 3 is a one-line edit inside docker-compose.yml, then regenerate the split overlays)
make -C pmoves compose-split
# 3. prove it, then close the road
python3 -m pytest -q pmoves/tests/test_composio_mcp_proxy.py
rm .claude/hooks/damage-control/.known-road-active
```

## What upstream actually offers (researched 2026-10-21)

| Question | Answer | Source |
|---|---|---|
| Is there a self-hostable Composio MCP server? | **No.** Connect (`https://connect.composio.dev/mcp`) and per-session MCP URLs are hosted by Composio. | `PMOVES-composio/docs/content/docs/composio-connect.mdx`, `sessions-via-mcp.mdx` (docs.composio.dev/docs/composio-connect, /docs/sessions-via-mcp) |
| Is `@composio/mcp` still the package? | **No.** npm `@composio/mcp` latest `1.0.9` is marked deprecated: "Package no longer supported". It was a setup CLI, not a server. | `registry.npmjs.org/@composio/mcp` |
| How does a headless client authenticate to Connect? | `x-consumer-api-key: ck_…` (a Connect consumer key). `ak_` project keys and `uak_` user keys are different credentials. | `composio-connect.mdx` "Generic MCP URL"; `kb/guide/consumer-project-boundaries-and-auth-selection.mdx` |
| Bridge | **supergateway 4.2.0** (`supercorp/supergateway:4.2.0@sha256:61ffc26b…`, node:20-alpine, amd64+arm64). Remote streamable-HTTP → streamable-HTTP re-serve, `--header` to upstream, inbound `apiKey`, `${VAR}` expansion from env in `--config`, unset var = startup error. | npm `supergateway@4.2.0` README ("Remote server → SSE, WS or Streamable HTTP", "Requiring an API key", "Several servers from a config file"); Docker Hub `supercorp/supergateway` tags |

Measured locally (supergateway run as a plain process on 127.0.0.1, dummy keys,
no container): `--checkConfig` accepts the config; with the consumer key unset it
refuses to start (`${COMPOSIO_MCP_CONSUMER_KEY} is not set`); `/healthz` → `ok`
without auth; POST without the gateway key → 401; with it, the proxy forwards to
Connect, which answered a dummy `ck_` with the same 401 body it gives a direct
call (`Authorization required`) — i.e. the header reaches Connect intact. A real
`ck_` key was not used; the full tool list is UNVERIFIED until `make -C pmoves
composio-mcp-smoke` runs on SPARK with the operator's key.

## Block 1 — portable service (SPARK + KVM2)

```yaml file=deploy/kvm2/composio-mcp/docker-compose.yml
# Composio MCP fleet proxy -- ONE portable compose file for SPARK and KVM2.
# Contract + provenance: pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md
#
# Composio MCP is HOSTED only (no self-hostable server upstream; npm
# @composio/mcp is deprecated). This is a PMOVES-owned streamable-HTTP proxy in
# front of Composio Connect: supergateway re-serves the remote server, injecting
# the Connect consumer key (x-consumer-api-key, ck_*) upstream and requiring its
# OWN gateway key from callers. Fleet clients never hold the Composio key.
#
# Secrets contract (never on a command line, never in this file):
#   ${COMPOSIO_MCP_ENV_FILE:-/opt/composio-mcp/.env}  chmod 600:
#     COMPOSIO_MCP_CONSUMER_KEY=ck_...
#     COMPOSIO_MCP_GATEWAY_KEY=<random, e.g. openssl rand -hex 32>
#   supergateway expands ${VAR} in its config from the container env at start
#   and refuses to start when one is unset -- a missing key fails closed.
#
# SPARK: make -C pmoves up-composio-mcp    KVM2: deploy/kvm2/composio-mcp/README.md
# Smoke: make -C pmoves composio-mcp-smoke

name: composio-mcp

services:
  composio-mcp:
    # supergateway 4.2.0 -- node:20-alpine, amd64 + arm64. Re-pin deliberately.
    image: ${COMPOSIO_MCP_IMAGE:-supercorp/supergateway:4.2.0@sha256:61ffc26bf72b0b252a3aba926ff67b9d78e7181d19905f1f9c8fc6b7f6c3ad3d}
    container_name: pmoves-composio-mcp
    hostname: composio-mcp
    restart: unless-stopped
    command: ["--config", "/etc/supergateway/composio.jsonc"]
    env_file:
      - path: ${COMPOSIO_MCP_ENV_FILE:-/opt/composio-mcp/.env}
        required: true
    configs:
      - source: composio_gateway
        target: /etc/supergateway/composio.jsonc
    ports:
      # Loopback on every node. KVM2 reaches the tailnet via `tailscale serve`.
      - "${COMPOSIO_MCP_BIND:-127.0.0.1}:${COMPOSIO_MCP_PORT:-8190}:8000"
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop: [ALL]
    security_opt:
      - no-new-privileges:true
    mem_limit: 256m
    healthcheck:
      # Gateway-level /healthz: unauthenticated, does NOT dial Composio, so an
      # upstream blip does not flap the container. composio-mcp-smoke proves
      # the upstream path.
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8000/healthz || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "3"

configs:
  composio_gateway:
    # `$$` is compose's literal `$`: these references reach supergateway
    # unexpanded and it fills them from the container env. Endpoint:
    # http://<host>:<port>/composio/mcp
    content: |
      {
        "port": 8000,
        "logFormat": "json",
        "healthEndpoint": "/healthz",
        "mcpServers": {
          "composio": {
            "type": "http",
            "url": "$${COMPOSIO_MCP_UPSTREAM_URL:-https://connect.composio.dev/mcp}",
            "headers": { "x-consumer-api-key": "$${COMPOSIO_MCP_CONSUMER_KEY}" },
            "outputTransport": "streamableHttp",
            "stateful": true,
            "apiKey": "$${COMPOSIO_MCP_GATEWAY_KEY}"
          }
        }
      }
```

## Block 2 — SPARK mesh overlay (lets Agent Zero reach it by DNS)

```yaml file=deploy/kvm2/composio-mcp/docker-compose.pmoves-mesh.yml
# SPARK only: attach the proxy to the PMOVES app mesh so Agent Zero reaches it at
#   http://composio-mcp:8000/composio/mcp
# without widening the host bind. Not used on KVM2 (no PMOVES mesh there).
services:
  composio-mcp:
    networks:
      - default
      - pmoves_app

networks:
  pmoves_app:
    external: true
```

## Block 3 — Agent Zero client entry (`pmoves/docker-compose.yml`, then `make -C pmoves compose-split`)

In the agent-zero service's `A0_SET_mcp_servers=` JSON, append this entry after
`"wealth":{…}` (inside the outer `mcpServers` object):

```json a0-entry
"composio":{"type":"streamable-http","url":"${COMPOSIO_MCP_ENDPOINT:-http://composio-mcp:8000/composio/mcp}","headers":{"Authorization":"Bearer ${COMPOSIO_MCP_GATEWAY_KEY}"},"disabled":${COMPOSIO_MCP_A0_DISABLED:-true}}
```

Guarding: A0 boots regardless. `MCPConfig.__init__`
(`PMOVES-Agent-Zero/helpers/mcp_handler.py`) catches a per-server
construct/initialize failure and records it as that server's error, and an entry
with `"disabled": true` is skipped outright ("Disabled in config"). The entry
ships **disabled by default**; set `COMPOSIO_MCP_A0_DISABLED=false` (must be the
literal `true`/`false` — it is spliced into JSON) once the proxy smokes green.
`COMPOSIO_MCP_GATEWAY_KEY` reaches A0's compose interpolation only through the
tier env files, so it needs a secrets-funnel slot (see "Operator follow-ups").

## Operator follow-ups (not in this PR)

1. **Connect client + key.** Create a Connect client for the proxy (e.g.
   `composio-mcp-spark`, then `composio-mcp-kvm2`) with the `ak_` project key
   (`POST /api/v3/mcp/clients`, as in `COMPOSIO_DISCORD_ONBOARDING.md` step 4.2)
   and take its `ck_` key. Do **not** reuse `COMPOSIO_CONSUMER_KEY_KIMI` — that
   is kimi-knuckles' identity — and do not use `COMPOSIO_API_KEY`: per the
   registry comment in `pmoves/tools/chit_manifest_register.py` that slot now
   carries a `uak_` user key, which Connect's header auth does not take.
2. **Secrets slots.** Register `COMPOSIO_MCP_GATEWAY_KEY` (and, if the proxy
   key should funnel rather than live only in the node-local env file,
   `COMPOSIO_MCP_CONSUMER_KEY`, prefix `ck_`) in the CHIT manifest — the manifest
   files are zero-access to agents.
3. KVM2 deploy per `deploy/kvm2/composio-mcp/README.md`, then record the
   tailnet URL in `pmoves/docs/operations/MCP_SERVER_NODE_MAP.md`.
