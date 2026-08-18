Query or execute commands via Agent Zero's MCP command API.

The Agent Zero supervisor exposes a small REST surface for listing and dispatching
named MCP commands. This command provides access to that surface.

> The supervisor on 8080 is a REST facade, not an MCP protocol server. The real
> MCP protocol server runs in the A0 runtime — see "MCP protocol server" below.

## Usage

Run this command to:
- List the MCP commands the supervisor can dispatch
- Execute a named MCP command with arguments
- Check supervisor and runtime health

## Implementation

Execute the following steps:

1. **Check supervisor health:**
   ```bash
   curl -sf http://localhost:8080/healthz | jq '{status, nats: .nats.connected, runtime: .runtime.status}'
   ```

2. **List available MCP commands:**
   ```bash
   curl -sf http://localhost:8080/mcp/commands | jq '.commands[] | {name, description}'
   ```

   Also returns the active form and the runtime/knowledge-base directories.

3. **Execute an MCP command** — the body is `{cmd, arguments}`:
   ```bash
   curl -sf -X POST http://localhost:8080/mcp/execute \
     -H "Content-Type: application/json" \
     -d '{"cmd": "notebook.search", "arguments": {"query": "<search terms>", "limit": 5}}' | jq .
   ```

   Returns `{cmd, result}`. An unknown `cmd` returns 404; bad arguments return 400.

4. **Report results to user:**
   - Supervisor health and NATS connectivity
   - Command inventory
   - Command output

## Authentication

None on these routes. The supervisor declares no inbound auth dependency. It
forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`) to the A0 runtime on your behalf.
A 401 here means an ingress in front of 8080 added auth — not this service.

Two other surfaces on this service **do** authenticate:

- **A0 runtime** on 8081 — `X-API-KEY` (or `api_key` in the JSON body), checked
  against `mcp_server_token`.
- **A2A routes** (`/a2a/v1/*`, `/.well-known/agent-card.json`) — a Supabase JWT
  as `Authorization: Bearer <jwt>`, validated with `SUPABASE_JWT_SECRET` and
  gated by `A2A_DISCOVERY_PUBLIC` / `A2A_TASKS_PUBLIC` (both default `false`,
  so auth is required unless explicitly opened).

## Available commands

`geometry.publish_cgp`, `geometry.jump`, `geometry.decode_text`,
`geometry.calibration.report`, `ingest.youtube`, `media.transcribe`,
`comfy.render`, `notebook.search`, `form.get`, `form.switch`,
`a2a.strategic_handoff`, `e2b.sandbox.create`, `e2b.sandbox.execute`,
`e2b.sandbox.terminate`, `e2b.desktop.create`, `e2b.spell.execute`,
`e2b.surf.scrape`

Source of truth: `pmoves/services/agent-zero/mcp_server.py` `COMMAND_REGISTRY`.
Re-read it rather than trusting this list — `GET /mcp/commands` is authoritative
at runtime.

## MCP protocol server

The real MCP protocol server runs inside the A0 runtime and is token-pathed:

- `http://localhost:8081/t-$AGENT_ZERO_MCP_TOKEN/sse`
- `http://localhost:8081/t-$AGENT_ZERO_MCP_TOKEN/http`
- `http://localhost:8081/t-$AGENT_ZERO_MCP_TOKEN/messages/`

The token comes from `MCP_SERVER_TOKEN` (`AGENT_ZERO_MCP_TOKEN` in compose);
when unset, A0 derives one per instance and the path changes.

## Submitting work

To submit a free-form task rather than a named command, use `/agents:execute`
(`POST /tasks`) and poll with `/agents:task-status` (`GET /jobs/{context_id}`).

## UI Access

Agent Zero UI is available at: `http://localhost:8081`

## Notes

- Monitor MCP usage: `curl -s http://localhost:8080/metrics | grep mcp`
- Agent Zero health: `curl -s http://localhost:8080/healthz`
- Canonical API surface: `pmoves/docs/operations/AGENT_ZERO_API.md`
