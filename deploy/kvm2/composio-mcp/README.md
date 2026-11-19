# Composio MCP fleet proxy — KVM2 deploy kit (NOT yet deployed)

A loopback-bound streamable-HTTP proxy in front of **hosted** Composio Connect
(`https://connect.composio.dev/mcp`). The same compose file runs on SPARK
(`make -C pmoves up-composio-mcp`) and on KVM2 (this kit, via a Hostinger Docker
project). Research, provenance and the reviewed compose blocks:
[`pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md`](../../../pmoves/docs/handoffs/COMPOSIO_MCP_SELFHOST.md).

| Piece | Value |
|---|---|
| Bridge | `supercorp/supergateway:4.2.0@sha256:61ffc26bf72b0b252a3aba926ff67b9d78e7181d19905f1f9c8fc6b7f6c3ad3d` (amd64 + arm64) |
| Upstream | `https://connect.composio.dev/mcp`, header `x-consumer-api-key: ck_…` |
| Listen | `127.0.0.1:8190` → container `8000`; MCP path `/composio/mcp`; `/healthz` (no auth) |
| Caller auth | `Authorization: Bearer <COMPOSIO_MCP_GATEWAY_KEY>` (or `X-API-Key`) — 401 without it |

## Files

- `docker-compose.yml` — the service (Block 1 of the handoff). **The only file the Hostinger project needs.**
- `docker-compose.pmoves-mesh.yml` — SPARK-only overlay (joins `pmoves_app`). Not used on KVM2.

Both are operator-apply in the PR that introduced this kit (compose files are a
Known Road domain); if they are missing here, place them from the handoff.

## Secrets contract — `/opt/composio-mcp/.env`

```
COMPOSIO_MCP_CONSUMER_KEY=ck_…        # Connect consumer key of a client created FOR this proxy
COMPOSIO_MCP_GATEWAY_KEY=…            # random: openssl rand -hex 32 (inside the editor session, not echoed)
# optional: COMPOSIO_MCP_UPSTREAM_URL=…  (defaults to Connect)
```

- Directory `0700`, file `0600`, owner root. Write it with an editor over the
  VS Code Remote-SSH session — **never** `echo KEY=… > file` (shell history) and
  never through the Hostinger API (the call body lands in the agent transcript).
- An unset key is a startup error in supergateway, so a missing or misspelt
  line fails closed: the container restarts and never turns healthy.
- Never use `COMPOSIO_API_KEY` here: that slot carries a `uak_` user key, and
  Connect's header auth takes a `ck_` consumer key.

## Hostinger steps (operator, or an agent with the Hostinger MCP)

1. **Secrets first (SSH / VS Code Remote):**
   `sudo install -d -m 700 /opt/composio-mcp`, create `/opt/composio-mcp/.env`
   as above in an editor, `sudo chmod 600 /opt/composio-mcp/.env`.
2. **Compose capability check (SSH):** `docker compose version` must be
   **≥ 2.24.0** — the file uses inline `configs.content` (2.23.1+) and the long
   `env_file` form with `required:` (2.24.0+). UNVERIFIED on KVM2 as of writing.
3. **Create the project:** Hostinger MCP `VPS_createNewProjectV1` with the KVM2
   `virtualMachineId`, project name `composio-mcp`, and the content of
   `docker-compose.yml` verbatim. No secret goes in this call — the compose file
   only *references* `/opt/composio-mcp/.env`.
4. **Check it:** `VPS_getProjectContainersV1` / `VPS_getProjectLogsV1` for
   `composio-mcp`; on the box `curl -s http://127.0.0.1:8190/healthz` → `ok`.
5. **Expose to the tailnet only** (Tailscale serve, never Funnel):
   ```bash
   sudo tailscale serve --bg --https=8190 http://127.0.0.1:8190
   tailscale serve status
   ```
   Fleet URL: `https://<kvm2-magicdns-name>.<tailnet>.ts.net:8190/composio/mcp`
   (TLS terminated by tailscaled; the container stays on loopback). The tailnet
   ACL must allow the calling nodes to reach KVM2 `:8190`.
6. **Smoke from a fleet node** (gateway key exported in that shell only):
   ```bash
   COMPOSIO_MCP_SMOKE_URL=https://<kvm2>.<tailnet>.ts.net:8190/composio/mcp \
     make -C pmoves composio-mcp-smoke
   ```
   Exit 0 = handshake + tools listed; 1 = proxy answered wrong (bad key, upstream
   refusal); 3 = could not measure.
7. Record the tailnet URL in `pmoves/docs/operations/MCP_SERVER_NODE_MAP.md`
   (composio row) and set `COMPOSIO_MCP_ENDPOINT` for clients that use KVM2.

## Hosted Connect vs this proxy

| | Hosted Connect direct (`.claude/mcp.json` `composio`) | This proxy (`composio-local`, A0 `composio`) |
|---|---|---|
| Tools | 7 `COMPOSIO_*` meta-tools | the same 7 — it re-serves Connect |
| Auth to Composio | in-band OAuth in the client (browser) | `ck_` consumer key held only by the proxy |
| Headless clients (A0, Hermes, cron) | no — needs a browser OAuth dance | yes |
| Whose connected apps | the OAuth'd user | the Connect client the `ck_` key belongs to |
| App connection (Gmail, Slack…) | OAuth link in-band | still in-band: `COMPOSIO_MANAGE_CONNECTIONS` returns a link; a human opens it |
| Execution location | Composio cloud | Composio cloud (the proxy only relays) |
| Works if Composio is down | no | no |
