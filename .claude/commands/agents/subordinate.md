Create a subordinate agent via Agent Zero's MCP API.

Subordinate agents are on-demand, specialized agents with limited scope and tools. They execute independently and report results back to the supervisor.

## Usage

Run this command to create a specialized agent:
- `/agents:subordinate log-analyzer` - Create log analysis agent
- `/agents:subordinate --tools python,sql data-analyst` - Custom tools

## Implementation

Execute the following steps:

1. **Check Agent Zero MCP health:**
   ```bash
   curl -sf http://localhost:8080/mcp/health \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq .
   ```

   If not healthy, inform user and stop.

2. **Create subordinate agent:**
   ```bash
   curl -X POST http://localhost:8080/mcp/subordinate/create \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{
       "config": {
         "name": "<agent_name>",
         "specialization": "<description_of_specialization>",
         "tools": ["<tool1>", "<tool2>"],
         "max_turns": 10,
         "timeout_seconds": 120
       }
     }'
   ```

   Returns subordinate ID, status, and capabilities.

3. **Verify subordinate is active:**
   ```bash
   curl -sf http://localhost:8080/mcp/agents \
     -H "Authorization: Bearer $MCP_CLIENT_SECRET" | jq '.subordinates'
   ```

4. **Report results to user:**
   - Subordinate agent ID
   - Assigned specialization and tools
   - Status (ready/busy)
   - How to submit tasks to this subordinate

## Authentication

Requires `MCP_CLIENT_SECRET` environment variable.

## Common Subordinate Types

| Name | Specialization | Tools |
|------|----------------|-------|
| `log-analyzer` | Log analysis and pattern detection | grep, awk, analysis |
| `code-reviewer` | Code review and quality checks | file_operations |
| `data-analyst` | Data querying and analysis | python, sql |
| `doc-writer` | Documentation generation | file_operations |

## Notes

- Subordinates are ephemeral — auto-destroyed after task completion or timeout
- Each subordinate has its own isolated context window
- Results published to NATS `agent.subordinate.result.v1`
- Default max turns: 10; default timeout: 120 seconds
- See `.claude/context/agent-zero-orchestration.md` for the full subordinate model
