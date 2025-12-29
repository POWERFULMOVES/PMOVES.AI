# Gateway Agent User Guide

This guide explains how to use the PMOVES Gateway Agent to discover and execute MCP tools, store skills, and manage credentials.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Discovering Tools](#discovering-tools)
3. [Executing Tools](#executing-tools)
4. [Managing Skills](#managing-skills)
5. [Checking Health](#checking-health)
6. [Troubleshooting](#troubleshooting)
7. [Python SDK Examples](#python-sdk-examples)

## Quick Start

### Using curl

```bash
# Check if Gateway is running
curl http://localhost:8100/healthz

# List all available tools
curl http://localhost:8100/tools

# List tools in a specific category
curl http://localhost:8100/tools?category=automation
```

### Using the Web UI

```
Open your browser to: http://localhost:8100/docs
```

This will show the interactive Swagger UI documentation.

## Discovering Tools

### List All Tools

```bash
curl http://localhost:8100/tools
```

**Response:**
```json
{
  "total": 5,
  "tools": [
    {
      "name": "n8n_agent:list_workflows",
      "description": "List all n8n workflows",
      "category": "automation",
      "mcp_server": "n8n-agent",
      "parameters": {},
      "enabled": true
    }
  ],
  "categories": {
    "automation": 2,
    "documents": 1,
    "memory": 1,
    "infrastructure": 1
  }
}
```

### Filter by Category

```bash
# Infrastructure tools (VPS, DNS, etc.)
curl http://localhost:8100/tools?category=infrastructure

# Automation tools (workflows, scheduling)
curl http://localhost:8100/tools?category=automation

# Document tools (PDF conversion)
curl http://localhost:8100/tools?category=documents

# Memory tools (skills, knowledge)
curl http://localhost:8100/tools?category=memory
```

### Force Refresh Cache

The Gateway caches tool definitions for 5 minutes. To force a refresh:

```bash
curl http://localhost:8100/tools?force_refresh=true
```

## Executing Tools

### Basic Execution

```bash
curl -X POST http://localhost:8100/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "n8n_agent:list_workflows",
    "parameters": {},
    "timeout": 30
  }'
```

**Response:**
```json
{
  "success": true,
  "result": {
    "workflows": [...]
  },
  "error": null,
  "execution_time_ms": 123
}
```

### Execution with Parameters

```bash
curl -X POST http://localhost:8100/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "docling:convert_document",
    "parameters": {
      "file_path": "/path/to/document.pdf",
      "output_format": "markdown"
    },
    "timeout": 60
  }'
```

### Handling Errors

If a tool fails, the response will indicate the error:

```json
{
  "success": false,
  "result": null,
  "error": "Tool not found: nonexistent:tool",
  "execution_time_ms": 5
}
```

## Managing Skills

Skills are learned patterns stored in Cipher Memory that can be retrieved and reused.

### Store a Skill

```bash
curl -X POST http://localhost:8100/skills/store \
  -H "Content-Type: application/json" \
  -d '{
    "name": "restart_web_server",
    "description": "Restart web server on VPS when it becomes unresponsive",
    "category": "infrastructure",
    "pattern": "1. SSH to VPS → 2. Check nginx status → 3. systemctl restart nginx → 4. Verify service is running",
    "outcome": "Web server restarted successfully and responding to HTTP requests",
    "mcp_tool": "hostinger:execute_ssh_command"
  }'
```

### Search Skills

```bash
curl -X POST http://localhost:8100/skills/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restart server",
    "limit": 10
  }'
```

### Search Skills by Category

```bash
curl -X POST http://localhost:8100/skills/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deploy",
    "category": "automation",
    "limit": 5
  }'
```

## Checking Health

### Check Gateway Health

```bash
curl http://localhost:8100/healthz
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-26T12:00:00Z",
  "services": {
    "agent_zero": "healthy",
    "cipher": "healthy",
    "tensorzero": "healthy"
  }
}
```

### Check Available Credentials

```bash
curl http://localhost:8100/secrets
```

**Response:**
```json
{
  "hostinger": "hp_xxx123abc...",
  "tailscale": "tskey-auth-...",
  "n8n": "n8n_api_..."
}
```

> **Note:** Secret values are masked for security. Only the first few characters are shown.

## Troubleshooting

### Gateway shows "degraded" status

**Symptoms:**
```json
{
  "status": "degraded",
  "services": {
    "agent_zero": "unreachable: Connection refused"
  }
}
```

**Solutions:**

1. Check if Agent Zero is running:
   ```bash
   curl http://localhost:8080/healthz
   ```

2. Start Agent Zero if needed:
   ```bash
   docker compose --profile agents up -d agent-zero
   ```

3. Check network connectivity:
   ```bash
   docker network ls | grep pmoves
   docker network inspect pmoves_api
   ```

### No tools discovered

**Symptoms:**
```json
{
  "total": 0,
  "tools": []
}
```

**Solutions:**

1. Force refresh the cache:
   ```bash
   curl http://localhost:8100/tools?force_refresh=true
   ```

2. Check Agent Zero MCP commands endpoint:
   ```bash
   curl http://localhost:8080/mcp/commands
   ```

3. Check Gateway logs:
   ```bash
   docker logs pmoves-gateway-agent-1 --tail 50
   ```

### Tool execution fails

**Symptoms:**
```json
{
  "success": false,
  "error": "Tool not found: n8n_agent:list_workflows"
}
```

**Solutions:**

1. Verify the tool exists:
   ```bash
   curl http://localhost:8100/tools | jq '.tools[] | select(.name=="n8n_agent:list_workflows")'
   ```

2. Check if the upstream container is running:
   ```bash
   docker ps | grep n8n
   ```

3. Check credentials:
   ```bash
   curl http://localhost:8100/secrets
   ```

### Permission errors

**Symptoms:**
```json
{
  "error": "Unauthorized: Invalid API key"
}
```

**Solutions:**

1. Check environment variables:
   ```bash
   docker exec pmoves-gateway-agent-1 env | grep API_KEY
   ```

2. Verify GitHub Secrets are set:
   ```bash
   gh secret list
   ```

3. Restart the service with updated credentials:
   ```bash
   docker compose --profile gateway up -d gateway-agent
   ```

## Python SDK Examples

### Basic Client

```python
import asyncio
from httpx import AsyncClient

class GatewayClient:
    def __init__(self, base_url: str = "http://localhost:8100"):
        self.base_url = base_url
        self.client = None

    async def __aenter__(self):
        self.client = AsyncClient(base_url=self.base_url, timeout=30.0)
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def list_tools(self, category: str = None):
        """List all available tools"""
        params = {"category": category} if category else {}
        response = await self.client.get("/tools", params=params)
        response.raise_for_status()
        return response.json()

    async def execute_tool(self, tool_name: str, parameters: dict = None):
        """Execute a tool"""
        response = await self.client.post(
            "/tools/execute",
            json={
                "tool_name": tool_name,
                "parameters": parameters or {},
                "timeout": 30
            }
        )
        response.raise_for_status()
        return response.json()

    async def store_skill(self, name: str, description: str, **kwargs):
        """Store a skill pattern"""
        response = await self.client.post(
            "/skills/store",
            json={
                "name": name,
                "description": description,
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
async def main():
    async with GatewayClient() as client:
        # List automation tools
        tools = await client.list_tools(category="automation")
        print(f"Found {tools['total']} automation tools")

        # Execute a tool
        result = await client.execute_tool(
            "n8n_agent:list_workflows",
            parameters={}
        )
        if result["success"]:
            print(f"Result: {result['result']}")

asyncio.run(main())
```

### Workflow Automation

```python
async def automate_workflow_restart(client: GatewayClient):
    """Automated workflow for restarting a service"""

    # 1. Store the learned pattern
    await client.store_skill(
        name="restart_n8n_workflow",
        description="Restart n8n workflow when it gets stuck",
        category="automation",
        pattern="list workflows → find stuck workflow → restart → verify",
        outcome="Workflow restarted successfully",
        mcp_tool="n8n_agent:restart_workflow"
    )

    # 2. Search for similar skills
    skills = await client.search_skills("restart workflow")
    print(f"Found {len(skills)} relevant skills")

    # 3. Execute the restart
    result = await client.execute_tool(
        "n8n_agent:restart_workflow",
        parameters={"workflow_id": "123"}
    )

    return result["success"]
```

## Additional Resources

- **API Documentation**: http://localhost:8100/docs
- **Architecture Guide**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Service README**: [README.md](../../services/gateway-agent/README.md)
- **PMOVES Documentation**: /home/pmoves/PMOVES.AI/docs/
