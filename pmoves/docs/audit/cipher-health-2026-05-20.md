# Cipher API Health Audit — 2026-05-20

**Audit ID:** `CIPHER-AUDIT-2026-05-20`
**Audited by:** 5090-CLAUDE (Opus 4.7)
**Lane:** L4 of 5-lane orchestration (see `~/.claude/plans/nested-sniffing-pancake.md`)
**Trigger:** `curl -sf http://localhost:8105/healthz` returning empty body during session-start sitrep.

## Summary

Cipher API container (`pmoves-cipher-api-1`) reports `Up 24h (healthy)` via Docker's internal healthcheck, yet **zero external connectivity** is available on the host. Investigation reveals two distinct root causes layered on top of each other:

1. **Docker Desktop WSL2 silent-bind class** (known per `feedback_docker_desktop_windows_silent_bind.md` + PR #1512). Compose intent `0.0.0.0:8105:3000` is silently dropped — `docker inspect` shows `Ports: {"3000/tcp":[]}` (empty array). No host-to-container path exists.
2. **REST API surface is `/health` + `/mcp/sse` only.** Every `/api/*` route the MCP client expects (`/api/memory`, `/api/sessions`, `/api/message`, `/api/health`) returns HTTP 404 from inside the container. The long-standing 3-layer gap (`project_cipher_3layer_gap.md`) is confirmed: the routes the client targets simply do not exist server-side.

Cipher Memory is therefore broken end-to-end:
- Host can't reach the container (issue 1)
- Even if host could reach it, the `/api/memory` endpoints don't exist (issue 2)
- Only the SSE MCP transport (`/mcp/sse`) is functional, and it's also blocked from host by issue 1

The skills layer (Layer 1) already auto-falls-back to local `MEMORY.md` per the 3-layer gap memory entry, so impact on day-to-day work is limited; cross-session continuity flows through the file system, not Cipher.

## Investigation log

### Port mapping inspection

```bash
$ docker port pmoves-cipher-api-1
(empty)

$ docker inspect pmoves-cipher-api-1 --format '{{json .NetworkSettings.Ports}}'
{"3000/tcp":[]}
```

The container exposes container-port `3000` (not `8105` — the host-side mapped port). Catalog references to "port 8105" describe the *intended* host binding, not the in-container service port.

### Compose definition

`pmoves/docker-compose.yml`:

```yaml
cipher-api:
  command: ["node", "dist/src/app/index.cjs", "--mode", "api", "--port", "3000",
            "--host", "0.0.0.0", "--agent", "/app/memAgent/cipher.yml",
            "--mcp-transport-type", "sse"]
  ports:
    - "${CIPHER_BIND:-0.0.0.0}:${CIPHER_PORT:-8105}:3000"
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:3000/health"]
```

- Internal port: 3000 (correct in compose)
- Healthcheck: probes `127.0.0.1:3000/health` (inside container — passes regardless of host binding)
- Host port mapping: `${CIPHER_PORT:-8105}:3000` — should publish, but Docker Desktop WSL2 ignores the bind on this host

### Internal route surface

Probed from inside the container network:

| Path | HTTP code | Notes |
|---|---|---|
| `/health` | **200** | Full JSON: `status: healthy, uptime: 93367s, websocket {active: true}` |
| `/` | 404 | No root route |
| `/api/health` | 404 | Not registered — but Archon-style alias may be expected by some clients |
| `/api/memory` | **404** | Long-standing 3-layer gap confirmed: clients call this but server doesn't register it |
| `/api/sessions` | 404 | Same — clients expect, server doesn't have |
| `/api/message` | 404 | Same |
| `/mcp/sse` | **200** | SSE works: emits `event: endpoint` with `data: /mcp?sessionId=<uuid>` |

The only functional endpoints are `/health` and `/mcp/sse`.

### Live MCP transport sample

```
$ docker exec pmoves-cipher-api-1 wget -qO- http://127.0.0.1:3000/mcp/sse
event: endpoint
data: /mcp?sessionId=cc7b2074-0434-41db-9708-f61a899703b6
```

SSE transport is functional — sessions can be opened over `/mcp` with a `sessionId` query parameter. If host binding were fixed, this is the path the Claude Code MCP client (`.claude/mcp.json` `pmoves-cipher` entry) would consume.

### Catalog vs reality drift

`.claude/CATALOG.md:36` says:

> **Cipher Memory** `:8105` — Knowledge-graph memory (Neo4j backend). MCP bridge at `pmoves-cipher-mcp/` (stdio). API: `POST /api/memory`, `GET /api/memory/search?q=...`. Health: `GET /health`.

Drift items:
- `:8105` is the *host port* (not in-container port — that's 3000). Describing the catalog as ":8105 (host) → :3000 (container)" would be more accurate, especially given the WSL2 silent-bind class.
- `POST /api/memory` and `GET /api/memory/search` — described as if implemented, but server returns 404 for both.

`.claude/CATALOG.md:123` already acknowledges the silent-bind issue:

> `pmoves-cipher` | SSE `localhost:8105/mcp/sse` | none | cipher-api container | Per-host bind broken on Docker Desktop WSL2 (PR #1512 documents the operator-side `CIPHER_BIND` override fix)

…but the `:8105` line further up the same doc still implies the API path is working. Both lines should align.

## Recommendations (out of scope for L4 — surface for separate PRs)

### Tier A — short, can land soon

1. **Catalog correction**: update `.claude/CATALOG.md:36` to mark `/api/memory*` routes as *not implemented upstream*, point at the MCP SSE transport as the supported path. Note the host port is 8105 → container 3000.
2. **Memory entry refresh**: update `~/.claude/projects/.../memory/project_cipher_3layer_gap.md` with the 2026-05-20 evidence (still applies, but be specific about which routes were probed).

### Tier B — submodule scope (`Pmoves-cipher`)

3. **Decide: implement `/api/memory` routes or remove client expectation.** Two paths:
   - **a**: implement CRUD in `Pmoves-cipher/src/app/api/server.ts` matching what `pmoves-cipher-mcp/cipher_mcp/client.py` calls (POST + GET memory, GET memory/search). This unlocks REST-style usage by non-MCP clients.
   - **b**: drop the REST client path; route everything through MCP SSE (`/mcp/sse` already works). Update `pmoves-cipher-mcp/client.py` to dispatch via SSE instead of HTTP REST.
   - The upstream Cipher project (pre-fork) is the source of truth — read its docs/CHANGELOG before picking a side (per `feedback_read_upstream_docs_first.md`, mistake at PR #1495 phantom-routes saga came from picking before reading).

### Tier C — operator-driven, Docker Desktop class

4. **WSL2 silent-bind workaround**: PR #1512 documented the `CIPHER_BIND` override. Verify the operator-side fix on this host (5090) — possibly missing or unset. Or move Cipher to the `pmoves-net` shared bridge network and access it from peer containers (e.g., agent-zero) rather than host directly. This is operator-driven configuration, not a code change.

## Verification commands

For any future session validating Cipher API health, the correct probes are:

```bash
# Container is alive (host-network bypass)
docker exec pmoves-cipher-api-1 wget -qO- http://127.0.0.1:3000/health | jq .status
# Expect: "healthy"

# Host can reach (proves silent-bind workaround applied)
curl -sf http://localhost:8105/health | jq .status
# Expect: "healthy"  ; Actual on 5090 (2026-05-20): connection refused

# MCP SSE handshake (transport plane, what Claude Code uses)
docker exec pmoves-cipher-api-1 wget -qSO- http://127.0.0.1:3000/mcp/sse | head -3
# Expect: event: endpoint\ndata: /mcp?sessionId=<uuid>

# REST API (would unblock Layer 2 client)
docker exec pmoves-cipher-api-1 wget -qSO- http://127.0.0.1:3000/api/memory | head -3
# Expect: HTTP 200 with route handler  ; Actual: 404 — route not registered
```

## Lane disposition

L4 finding doc complete. Recommendations in **Tier A** are docs-only and could be folded into this PR if scope permits. Tiers B + C are deliberately out of scope per the plan file:

> L4 only investigates; the actual `/api/memory` route fix is a separate PR in `Pmoves-cipher` submodule scope.

agent_signature (advisory unsigned-local): `ACK::5090-CLAUDE::CIPHER-HEALTH-AUDIT-2026-05-20`
