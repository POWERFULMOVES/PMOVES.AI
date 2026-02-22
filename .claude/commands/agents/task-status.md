Query task completion status via Agent Zero's MCP API.

Check the status and results of tasks submitted via `/agents:execute` or the MCP API directly.

## Usage

Run this command with a task ID:
- `/agents:task-status task-abc123` - Check specific task
- `/agents:task-status` - List recent tasks

## Implementation

Execute the following steps:

1. **Check Agent Zero MCP health:**
   ```bash
   curl -sf http://localhost:8080/mcp/health \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq .
   ```

2. **Query specific task (if task ID provided):**
   ```bash
   curl -sf "http://localhost:8080/mcp/task/<task_id>" \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq .
   ```

   Returns task status, results, and execution metadata.

3. **List active agents and their tasks (if no task ID):**
   ```bash
   curl -sf http://localhost:8080/mcp/agents \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq '{
       supervisor: .supervisor.active_tasks,
       subordinates: [.subordinates[] | {id, status, specialization}]
     }'
   ```

4. **Report results to user:**
   - Task status: `queued`, `running`, `completed`, `failed`, `timeout`
   - Task results if completed
   - Execution time
   - Any errors if failed

## Authentication

Requires `MCP_CLIENT_SECRET` environment variable.

## Task Status Values

| Status | Description |
|--------|-------------|
| `queued` | Task accepted, waiting for agent runtime |
| `running` | Agent is actively working on the task |
| `completed` | Task finished successfully, results available |
| `failed` | Task encountered an error |
| `timeout` | Task exceeded `timeout_seconds` limit |

## Notes

- Tasks are queued in NATS JetStream for reliable delivery
- Completed task results are retained for a configurable period
- Failed tasks include error details in the response
- Monitor all tasks via Prometheus: `curl http://localhost:8080/metrics | grep task`
- See `.claude/context/agent-zero-orchestration.md` for full API reference
