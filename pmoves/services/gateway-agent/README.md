# PMOVES Gateway Agent

Central orchestrator for 100+ MCP (Model Context Protocol) tools in the PMOVES.AI infrastructure.

## Overview

The Gateway Agent provides a unified API for discovering and executing MCP tools across all PMOVES services. It integrates with:
- **Agent Zero** (8080) - Tool discovery and subagent spawning
- **Cipher Memory** (3025) - Skills storage and retrieval
- **TensorZero** (3030) - LLM inference and observability
- **Supabase** (3010) - Session and skill persistence

## Quick Start

```bash
# Build the Gateway Agent
docker compose build gateway-agent

# Deploy with dependencies
docker compose --profile gateway up -d gateway-agent

# Check health
curl http://localhost:8100/healthz

# List all tools
curl http://localhost:8100/tools
```

## API Endpoints

### GET /healthz
Health check endpoint.

**Response:**
```json
{
  "status": "healthy|degraded",
  "timestamp": "2025-12-26T12:00:00",
  "services": {
    "agent_zero": "healthy",
    "cipher": "healthy",
    "tensorzero": "healthy"
  }
}
```

### GET /tools
List all available MCP tools.

**Query Parameters:**
- `category` (optional) - Filter by category
- `force_refresh` (optional) - Bypass cache and re-discover

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

### POST /tools/execute
Execute an MCP tool.

**Request:**
```json
{
  "tool_name": "n8n_agent:list_workflows",
  "parameters": {},
  "timeout": 30
}
```

**Response:**
```json
{
  "success": true,
  "result": {...},
  "error": null,
  "execution_time_ms": 123
}
```

### POST /skills/store
Store a learned skill pattern in Cipher memory.

**Request:**
```json
{
  "name": "restart_web_server",
  "description": "Restart web server on VPS",
  "category": "infrastructure",
  "pattern": "SSH to VPS → systemctl restart nginx",
  "outcome": "Server restarted successfully",
  "mcp_tool": "hostinger:execute_ssh_command"
}
```

### POST /skills/search
Search for stored skills in Cipher memory.

**Request:**
```json
{
  "query": "restart server",
  "category": "infrastructure",
  "limit": 10
}
```

### GET /secrets
List available service credentials (masked for security).

**Response:**
```json
{
  "hostinger": "key123abc...",
  "tailscale": "tskey...",
  "n8n": "n8nkey..."
}
```

## Tool Categories

| Category | Description | Tools |
|----------|-------------|-------|
| infrastructure | VPS, DNS, hosting | Hostinger, Tailscale |
| automation | Workflows, scheduling | n8n-agent |
| execution | Code execution | E2B Runner |
| vision | Image/video analysis | VL Sentinel |
| documents | PDF, document conversion | Docling MCP |
| memory | Knowledge storage | Cipher Memory |
| api | API testing | Postman MCP |
| research | Knowledge discovery | Hi-RAG, SupaSerch |

## Development

### Running Tests

```bash
# Unit tests
pytest pmoves/tests/services/test_gateway_agent.py -v

# Integration tests (requires services running)
pytest -m integration pmoves/tests/integration/test_gateway_agent_integration.py -v

# API contract tests
pytest pmoves/tests/services/test_gateway_agent_api.py -v

# All tests with coverage
pytest --cov=pmoves/services/gateway-agent pmoves/tests/
```

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn app:app --host 0.0.0.0 --port 8100 --reload
```

### Project Structure

```
gateway-agent/
├── app.py              # Main FastAPI application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container definition
└── README.md          # This file
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| PORT | No | Server port (default: 8100) |
| AGENT_ZERO_URL | Yes | Agent Zero MCP API URL |
| CIPHER_URL | No | Cipher Memory URL |
| TENSORZERO_URL | No | TensorZero Gateway URL |
| SUPABASE_URL | No | Supabase API URL |
| SUPABASE_SERVICE_KEY | No | Supabase service role key |
| TOOL_CACHE_TTL | No | Tool cache TTL in seconds (default: 300) |

### GitHub Secrets

The following secrets should be set in GitHub Actions for deployment:

- `HOSTINGER_API_KEY` - Hostinger VPS API token
- `TAILSCALE_AUTHKEY` - Tailscale auth key
- `TAILSCALE_API_KEY` - Tailscale API key
- `N8N_API_KEY` - n8n API key
- `POSTMAN_API_KEY` - Postman API key
- `E2B_API_KEY` - E2B sandbox API key
- `VENICE_API_KEY` - Venice AI API key
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GEMINI_API_KEY` - Google Gemini API key

## Deployment

### Docker Compose

```yaml
# From pmoves/docker-compose.yml
gateway-agent:
  build: ./services/gateway-agent
  image: pmoves/gateway-agent:latest
  container_name: pmoves-gateway-agent
  ports: ["8100:8100"]
  environment:
    - AGENT_ZERO_URL=http://agent-zero:8080
    - CIPHER_URL=http://pmoves-botz-cipher:8000
    - TENSORZERO_URL=http://tensorzero-gateway:3030
  profiles: ["agents", "gateway"]
```

### Manual Deployment

```bash
# Build image
docker build -t pmoves/gateway-agent:latest .

# Run container
docker run -d \
  --name pmoves-gateway-agent \
  -p 8100:8100 \
  -e AGENT_ZERO_URL=http://agent-zero:8080 \
  -e CIPHER_URL=http://cipher:3025 \
  pmoves/gateway-agent:latest
```

## Troubleshooting

### Gateway shows "degraded" status
- Check Agent Zero: `curl http://localhost:8080/healthz`
- Check TensorZero: `curl http://localhost:3030/healthz`
- Check Cipher: `curl http://localhost:3025/health`

### No tools discovered
- Force refresh: `curl http://localhost:8100/tools?force_refresh=true`
- Check Agent Zero MCP: `curl http://localhost:8080/mcp/commands`
- Verify network connectivity between containers

### Tool execution fails
- Check container is running: `docker ps | grep <service>`
- Check credentials: `curl http://localhost:8100/secrets`
- Review container logs: `docker logs pmoves-gateway-agent-1`

## License

Part of the PMOVES.AI infrastructure. See main project LICENSE for details.
