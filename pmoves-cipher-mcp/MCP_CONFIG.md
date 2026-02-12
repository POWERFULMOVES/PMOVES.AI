# MCP Client Configuration for Cipher Memory

## Claude Code Desktop App

Add to `~/.config/claude-code/config.json` (Linux/macOS) or `%APPDATA%\claude-code\config.json` (Windows):

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/home/pmoves/PMOVES.AI/pmoves-cipher-mcp",
        "run",
        "python",
        "-m",
        "cipher_mcp.server"
      ],
      "env": {
        "CIPHER_URL": "http://localhost:8081",
        "PYTHONPATH": "/home/pmoves/PMOVES.AI/pmoves-cipher-mcp",
        "NATS_URL": "nats://nats:4222"
      }
    }
  }
}
```

## Project-Level Configuration

For project-specific configuration, create `.mcp.json` in PMOVES.AI root:

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "./pmoves-cipher-mcp",
        "run",
        "python",
        "-m",
        "cipher_mcp.server"
      ],
      "env": {
        "CIPHER_URL": "http://localhost:8081",
        "PYTHONPATH": "./pmoves-cipher-mcp",
        "NATS_URL": "nats://nats:4222"
      }
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CIPHER_URL` | Cipher Memory service URL | `http://localhost:8081` |
| `PYTHONPATH` | Module search path | `./pmoves-cipher-mcp` |
| `NATS_URL` | NATS server URL | `nats://nats:4222` |
| `TENSORZERO_URL` | TensorZero gateway (optional) | (from registry) |

## Docker Setup

When running in Docker, update paths:

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "exec",
        "pmoves-cipher-mcp",
        "python",
        "-m",
        "cipher_mcp.server"
      ],
      "env": {
        "CIPHER_URL": "http://cipher-memory:8081",
        "NATS_URL": "nats://nats:4222"
      }
    }
  }
}
```

## Verification

Test MCP connection:

```bash
# Test MCP server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  uv run --directory /home/pmoves/PMOVES.AI/pmoves-cipher-mcp \
  python -m cipher_mcp.server

# Check Cipher is reachable
curl http://localhost:8081/health

# In Claude Code, verify tools show up:
# - pmoves_cipher_store
# - pmoves_cipher_search
# - pmoves_cipher_store_reasoning
# - pmoves_cipher_reasoning_patterns
```

## Troubleshooting

### Tools not showing in Claude Code

1. Check config path:
   - Linux: `~/.config/claude-code/config.json`
   - macOS: `~/Library/Application Support/Claude/config.json`
   - Windows: `%APPDATA%\claude-code\config.json`

2. Restart Claude Code after config changes

3. Check Claude Code logs for errors

### Import errors

```bash
# Verify Python path
export PYTHONPATH=/home/pmoves/PMOVES.AI/pmoves-cipher-mcp:$PYTHONPATH

# Test imports
uv run python -c "from cipher_mcp import tools; print(tools.TOOLS)"
```

### Cipher connection failed

```bash
# Check Cipher is running
curl http://localhost:8081/health

# Or if in Docker
docker exec cipher-memory curl http://localhost:8081/health
```

### UV not found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip
pip install uv
```

## Alternative: Python Direct

If uv is not available, use python directly:

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "-m",
        "cipher_mcp.server"
      ],
      "cwd": "/home/pmoves/PMOVES.AI/pmoves-cipher-mcp",
      "env": {
        "PYTHONPATH": "/home/pmoves/PMOVES.AI/pmoves-cipher-mcp",
        "CIPHER_URL": "http://localhost:8081"
      }
    }
  }
}
```
