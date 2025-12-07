Manage and verify MCP (Model Context Protocol) toolkits for PMOVES.

MCP toolkits provide standardized interfaces for LLM agents to interact with external tools and services.

## Usage

Run this command when:
- Checking which MCP tools are available
- Verifying MCP toolkit health and connectivity
- Getting setup instructions for specific tools
- Troubleshooting MCP integration issues

## Arguments

- `$ARGUMENTS` - Action and options:
  - `list` - List all configured MCP toolkits with availability status
  - `health` - Run health checks on all MCP tools
  - `setup <tool_id>` - Show setup instructions for a specific tool

## Implementation

Execute the appropriate command based on the action:

1. **List MCP tools:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli mcp list
   ```

2. **Run health checks:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli mcp health
   ```

3. **Show setup instructions:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli mcp setup <tool_id>
   ```

## MCP Tool Status

The `list` command shows for each tool:
- Tool ID and name
- Status: `ready` or `missing commands: <list>`
- Required commands that must be available

## Available MCP Toolkits

Common MCP tools in PMOVES:
- File system tools (read, write, search)
- Git operations
- Docker management
- Database queries (Supabase, Neo4j, Qdrant)
- NATS messaging
- TensorZero LLM gateway
- Hi-RAG knowledge retrieval

## Health Checks

Health checks verify:
- Required CLI commands are available
- Service endpoints are reachable
- Authentication is configured
- Permissions are correct

## Related Commands

- `/botz:profile` - Hardware profile with MCP adapter settings
- `/agents:mcp-query` - Query Agent Zero's MCP API
- `/health:check-all` - Full service health verification

## Notes

- MCP tools are defined in `pmoves/data/mcp/tools.yaml`
- Some tools require specific CLI installations (e.g., `nats`, `docker`)
- Agent Zero uses MCP to expose instruments to external integrations
