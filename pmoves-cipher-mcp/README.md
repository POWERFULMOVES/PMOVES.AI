# PMOVES Cipher MCP Bridge

MCP (Model Context Protocol) server that bridges **Claude Code CLI** to the
**Cipher Memory** knowledge-graph service.

## Architecture

```
Claude Code CLI  ──stdio──►  cipher_mcp (Python)  ──HTTP──►  Cipher Memory (Node.js / Neo4j)
                                    │
                              NATS announce
                              health loop
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `pmoves_cipher_store` | Store knowledge with category and tags |
| `pmoves_cipher_search` | Semantic search over stored memories |
| `pmoves_cipher_store_reasoning` | Store chain-of-thought reasoning traces |
| `pmoves_cipher_reasoning_patterns` | Search past reasoning for similar problems |

### Categories

`code_pattern` · `decision` · `context` · `submodule` · `architecture` · `reasoning`

## Quick Start

```bash
# Run directly
cd pmoves-cipher-mcp
uv run python -m cipher_mcp.server

# Or via main entry point (includes health + NATS announce)
uv run python main.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CIPHER_URL` | `http://localhost:8105` | Cipher Memory API base URL |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS server for announcements |

## Claude Code Integration

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "pmoves-cipher": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "./pmoves-cipher-mcp", "run", "python", "-m", "cipher_mcp.server"],
      "env": {
        "CIPHER_URL": "http://localhost:8105",
        "NATS_URL": "nats://nats:pmoves@nats:4222"
      }
    }
  }
}
```

## Docker

The Cipher Memory backend runs as `cipher-api` in the PMOVES docker-compose
stack (profile: `agents`, port 8105). It shares the existing Neo4j instance.

## Package Structure

```
pmoves-cipher-mcp/
├── cipher_mcp/          # MCP server, tools, HTTP client
├── pmoves_announcer/    # NATS service discovery
├── pmoves_common/       # Shared types (ServiceTier, HealthStatus)
├── pmoves_health/       # Async health checks
├── pmoves_registry/     # Service URL resolution
├── main.py              # Entry point (health + announce + MCP)
└── pyproject.toml
```
