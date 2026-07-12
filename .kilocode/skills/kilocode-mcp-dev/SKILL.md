---
name: kilocode-mcp-dev
description: MCP server development and integration for PMOVES.AI. Use when building MCP servers, configuring MCP clients, or wiring agent-to-agent communication via Model Context Protocol.
keywords: [mcp, model-context-protocol, integration, agent, server]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode MCP Development

MCP server development and integration using GLM-5.2 for tool definition, schema validation, and agent wiring.

## Purpose

Build, configure, and integrate MCP servers that enable PMOVES agents to interact with external services through well-designed tools.

## Capabilities

- 🔧 Build MCP servers (Python FastMCP or Node/TypeScript SDK)
- 🔗 Configure MCP clients in `kilo.json` and `.claude/mcp.json`
- 🛡️ Validate tool schemas and permission grants
- 📡 Wire agent-to-agent communication via MCP protocol
- ✅ Test MCP server connectivity and tool execution

## Integration Points

- **Z.AI MCP Servers**: zai-vision (local), zai-web-search/reader/zread (remote)
- **PMOVES MCP Servers**: pmoves-cipher, tailscale, huggingface, docker
- **KiloCode Permission**: `{server}_{tool}` pattern in `kilo.json`
- **Claude Code MCP Config**: `.claude/mcp.json`

## Workflow

### Step 1: Design the MCP Server

```python
# Python FastMCP pattern
from fastmcp import FastMCP

mcp = FastMMC("pmoves-custom-server")

@mcp.tool()
def get_status(service: str) -> dict:
    """Get health status of a PMOVES service."""
    # Implementation
    return {"service": service, "status": "healthy"}
```

### Step 2: Register in kilo.json

```jsonc
{
  "mcp": {
    "pmoves-custom": {
      "type": "local",
      "command": ["python", "-m", "pmoves.tools.mcp.custom_server"],
      "environment": { "API_KEY": "${API_KEY}" }
    }
  },
  "permission": {
    "pmoves-custom_*": "allow"
  }
}
```

### Step 3: Test Connectivity

```bash
# Check MCP server responds
curl -sf http://localhost:8080/healthz

# Verify in KiloCode
# Use /mcps command to list available MCP tools
```

## Trigger Phrases

- "build MCP server"
- "wire MCP integration"
- "configure MCP client"
- "add agent tool"
