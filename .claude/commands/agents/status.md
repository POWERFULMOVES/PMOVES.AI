Check Agent Zero orchestrator status and health.

Agent Zero is the control-plane orchestrator for PMOVES.AI. This command checks the supervisor's health, NATS connectivity, and runtime status.

## Usage

Run this command to:
- Verify the Agent Zero supervisor is operational
- Check NATS message bus connectivity
- Confirm the embedded agent runtime is healthy
- Confirm the MCP command dispatch surface is live

## Implementation

Execute the following steps:

1. **Query the supervisor health endpoint:**
   ```bash
   curl -sf http://localhost:8080/healthz | jq .
   ```

2. **Parse the response** which includes:
   - `status` — `ok` when the runtime child process is running, else `stopped`
   - `nats.connected` / `nats.use_jetstream` / `nats.subjects` — message bus state
   - `runtime` — runtime health, present only when the child process is running

3. **List available MCP commands** (confirms the dispatch surface is live):
   ```bash
   curl -sf http://localhost:8080/mcp/commands | jq '.commands | length'
   ```

   Returns the active form, runtime dirs, and the registered command list.

4. **Report to user:**
   - Overall Agent Zero status (healthy/degraded/down)
   - NATS connectivity status
   - Runtime status
   - MCP command count

## Authentication

None. The supervisor declares no inbound auth dependency on these routes. It
forwards `X-API-KEY` (`AGENT_ZERO_API_KEY`) to the A0 runtime on your behalf.

## MCP protocol server

The supervisor on 8080 is a REST facade — it is **not** an MCP protocol server.
The real MCP server runs inside the A0 runtime and is token-pathed:

- `http://localhost:8081/t-$AGENT_ZERO_MCP_TOKEN/sse`
- `http://localhost:8081/t-$AGENT_ZERO_MCP_TOKEN/http`

The token comes from `MCP_SERVER_TOKEN` (`AGENT_ZERO_MCP_TOKEN` in compose);
when unset, A0 derives one per instance and the path changes.

## UI Access

Agent Zero UI is available at: `http://localhost:8081`

## Notes

- Agent Zero coordinates agent activity via NATS
- If NATS is down, Agent Zero cannot coordinate tasks
- Check NATS independently: `nats server info` (if nats-cli installed)
- Logs: `docker compose logs agent-zero`
- Canonical API surface: `pmoves/docs/operations/AGENT_ZERO_API.md`
