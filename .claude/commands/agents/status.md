Check Agent Zero orchestrator status and health.

Agent Zero is the control-plane orchestrator for PMOVES.AI. This command checks its health, NATS connectivity, and runtime status.

## Usage

Run this command to:
- Verify Agent Zero is operational
- Check NATS message bus connectivity
- Confirm embedded agent runtime is healthy
- Validate MCP API availability

## Implementation

Execute the following steps:

1. **Query Agent Zero health endpoint:**
   ```bash
   curl http://localhost:8080/healthz
   ```

2. **Parse the response** which includes:
   - `supervisor_status` - Control plane health
   - `embedded_runtime_status` - Agent runtime health
   - `nats_connected` - Message bus connectivity
   - Overall health status

3. **Check MCP API availability:**
   ```bash
   curl http://localhost:8080/mcp/ 2>&1 | head -n 1
   ```

   Should return a response (even if error) indicating the endpoint exists.

4. **Report to user:**
   - Overall Agent Zero status (healthy/degraded/down)
   - NATS connectivity status
   - Runtime status
   - MCP API availability

## Advanced: Check Subordinate Agents

If MCP API credentials are configured, you can query active subordinates:

```bash
curl -X POST http://localhost:8080/mcp/list-agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

## UI Access

Agent Zero UI is available at: `http://localhost:8081`

## Notes

- Agent Zero coordinates all agent activities via NATS
- MCP API (`/mcp/*`) is used by Archon and other services for agent integration
- If NATS is down, Agent Zero cannot coordinate tasks
- Check NATS independently: `nats server info` (if nats-cli installed)
- Logs: `docker compose logs agent-zero`
