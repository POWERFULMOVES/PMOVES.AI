Submit a task for execution via Agent Zero's MCP API.

Agent Zero's MCP API accepts task submissions that are executed asynchronously via the agent runtime. Tasks are queued in NATS JetStream for reliable delivery.

## Usage

Run this command with a task description:
- `/agents:execute Analyze the latest deployment logs` - Submit task
- `/agents:execute --priority high "Review security audit results"` - High priority

## Implementation

Execute the following steps:

1. **Check Agent Zero MCP health:**
   ```bash
   curl -sf http://localhost:8080/mcp/health \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq .
   ```

   If not healthy, inform user and stop.

2. **Submit task for execution:**
   ```bash
   curl -X POST http://localhost:8080/mcp/execute \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{
       "task": "<user_provided_task_description>",
       "context": {},
       "priority": "normal",
       "timeout_seconds": 300
     }'
   ```

   Returns `task_id` and initial status.

3. **Poll for completion (wait up to 30s):**
   ```bash
   curl -sf "http://localhost:8080/mcp/task/<task_id>" \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq .
   ```

   Check `status` field: `queued`, `running`, `completed`, `failed`, `timeout`.

4. **Report results to user:**
   - Task ID for future reference
   - Current status
   - Results if completed
   - Execution time

## Authentication

Requires `MCP_CLIENT_SECRET` environment variable:
```bash
export MCP_CLIENT_SECRET="your-secret-key"
```

## Notes

- Tasks execute asynchronously via Agent Zero's agent runtime
- NATS JetStream provides reliable delivery (`AGENTZERO_JETSTREAM=true`)
- Default timeout: 300 seconds (5 minutes)
- Priority levels: `low`, `normal`, `high`
- Monitor task metrics: `curl http://localhost:8080/metrics | grep mcp`
- See `.claude/context/agent-zero-orchestration.md` for detailed API reference
