Query or execute commands via Agent Zero's MCP API.

Agent Zero exposes a Model Context Protocol (MCP) server that allows external services and agents to delegate tasks, create subordinate agents, and query agent status. This command provides access to Agent Zero's MCP endpoints.

## Usage

Run this command to:
- Execute tasks via Agent Zero's agent runtime
- Query status of active agents and subordinates
- List available MCP commands and capabilities
- Check task execution status
- Create specialized subordinate agents

## Implementation

Execute the following steps:

1. **Check MCP API health:**
   ```bash
   curl http://localhost:8080/mcp/health
   ```

   Should return MCP version, agent runtime status, and NATS connectivity.

2. **List available MCP commands:**
   ```bash
   curl http://localhost:8080/mcp/commands \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET"
   ```

   Shows all available MCP endpoints and their parameters.

3. **List active agents:**
   ```bash
   curl http://localhost:8080/mcp/agents \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET"
   ```

   Returns supervisor and subordinate agent details, status, and task counts.

4. **Execute a task (example):**
   ```bash
   curl -X POST http://localhost:8080/mcp/execute \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{
       "task": "<task_description>",
       "context": {},
       "priority": "normal",
       "timeout_seconds": 300
     }'
   ```

   Returns task ID and status. Task executes asynchronously via agent runtime.

5. **Query task status (if task submitted):**
   ```bash
   curl http://localhost:8080/mcp/task/<task_id> \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET"
   ```

   Shows task completion status, results, and execution time.

6. **Report results to user:**
   - MCP API health and connectivity status
   - List of active agents (supervisor + subordinates)
   - Available commands and capabilities
   - Task execution results (if task was submitted)

## Authentication

MCP endpoints require authentication via `MCP_CLIENT_SECRET`:

```bash
export MCP_CLIENT_SECRET="your-secret-key"
```

If `MCP_CLIENT_SECRET` is not set, only the health endpoint will work.

## Example: Create Subordinate Agent

```bash
curl -X POST http://localhost:8080/mcp/subordinate/create \
  -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "log-analyzer",
      "specialization": "log analysis and pattern detection",
      "tools": ["grep", "awk", "analysis"]
    }
  }'
```

Returns subordinate agent ID and capabilities.

## MCP Integration

Agent Zero's MCP API is used by:
- **Archon** - Supabase-backed agent form management
- **SupaSerch** - Holographic research orchestration
- **Custom services** - Your integrations

## UI Access

Agent Zero UI is available at: `http://localhost:8081`

## Notes

- MCP API is the primary interface for agent-to-agent communication
- Tasks submitted via MCP are queued in NATS JetStream for reliability
- Subordinate agents can be created for specialized tasks with limited context
- All MCP calls require `MCP_CLIENT_SECRET` except health endpoint
- Monitor MCP usage: `curl http://localhost:8080/metrics | grep mcp`
- Reference: `.claude/context/mcp-api.md` for complete API documentation
- Agent Zero health: `curl http://localhost:8080/healthz`
