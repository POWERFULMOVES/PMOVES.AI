# pmoves-cipher-mcp

MCP (Model Context Protocol) bridge for Claude Code CLI to communicate with Cipher Memory.

## Overview

This bridge enables Claude Code to store and retrieve memories from Cipher Memory, providing persistent context across sessions.

```
Claude Code CLI
    ↓ (stdio MCP)
pmoves-cipher-mcp (Python)
    ↓ (HTTP)
Cipher Memory (Node.js)
    ↓
Qdrant (Vector Storage) + Neo4j (Knowledge Graph)
```

## Installation

```bash
# With uv
uv pip install -e /path/to/pmoves-cipher-mcp

# Or with pip
pip install -e /path/to/pmoves-cipher-mcp
```

## Claude Code Configuration

Add to `~/.config/claude-code/config.json`:

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
        "PYTHONPATH": "/home/pmoves/PMOVES.AI/pmoves-cipher-mcp"
      }
    }
  }
}
```

## MCP Tools

### pmoves_cipher_store

Store knowledge in Cipher Memory.

**Categories:**
- `code_pattern`: Reusable code patterns
- `decision`: Architectural decisions
- `context`: Project-specific context
- `submodule`: Submodule knowledge
- `architecture`: System patterns
- `reasoning`: Reasoning traces

**Example:**
```python
pmoves_cipher_store(
    content="PMOVES submodules use pmoves_integrations framework",
    category="code_pattern",
    tags=["submodule", "pmoves", "integration"]
)
```

### pmoves_cipher_search

Search stored memories using semantic search.

**Example:**
```python
pmoves_cipher_search(
    query="submodule integration patterns",
    category="code_pattern",
    limit=5
)
```

### pmoves_cipher_store_reasoning

Store reasoning traces for complex problems.

**Example:**
```python
pmoves_cipher_store_reasoning(
    question="How to handle circular submodule references?",
    reasoning="The architecture shows that PMOVES-DoX has nested references...",
    result="Use root-level submodules and runtime networking integration"
)
```

### pmoves_cipher_reasoning_patterns

Search past reasoning traces.

**Example:**
```python
pmoves_cipher_reasoning_patterns(
    query="nested submodule architecture",
    limit=3
)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CIPHER_URL` | Cipher Memory service URL | `http://localhost:8081` |
| `NATS_URL` | NATS server URL | `nats://nats:4222` |
| `PYTHONPATH` | Module search path | (auto-detected) |

## Development

```bash
# Run tests
uv run pytest

# Run with type checking
uv run mypy cipher_mcp/

# Run linter
uv run ruff check cipher_mcp/

# Start MCP server manually
uv run python -m cipher_mcp.server

# Health check
uv run python main.py health

# Announce to service mesh
uv run python main.py announce
```

## Architecture

```
pmoves-cipher-mcp/
├── cipher_mcp/
│   ├── __init__.py      # Package init
│   ├── server.py        # MCP server (stdio)
│   ├── tools.py         # Tool definitions & handlers
│   └── client.py        # Cipher HTTP client
├── pmoves_announcer/    # NATS service discovery
├── pmoves_health/       # Health check endpoints
├── pmoves_registry/     # Service URL resolution
├── pmoves_common/       # Shared types
├── main.py              # Entry point
└── pyproject.toml       # Project config
```

## Integration with PMOVES.AI

The bridge integrates with PMOVES.AI service mesh:

1. **NATS**: Announces availability to service mesh
2. **Health Checks**: Monitors Cipher connectivity
3. **Service Registry**: Resolves Cipher URL dynamically
4. **Common Types**: Uses PMOVES ServiceTier, HealthStatus

## Troubleshooting

### Cipher connection refused
```bash
# Check Cipher is running
curl http://localhost:8081/health

# Verify CIPHER_URL
echo $CIPHER_URL
```

### MCP tools not showing
```bash
# Verify Claude Code config
cat ~/.config/claude-code/config.json

# Test MCP server manually
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  uv run python -m cipher_mcp.server
```

### Import errors
```bash
# Verify PYTHONPATH
export PYTHONPATH=/home/pmoves/PMOVES.AI/pmoves-cipher-mcp:$PYTHONPATH

# Reinstall
uv pip install -e .
```

## License

Elastic-2.0
