# PMOVES Agent Zero

Pinokio launcher for the PMOVES Agent Zero mesh entrypoint.

This launcher is a thin wrapper over the repo-supported PMOVES startup flow. It does not fork Agent Zero application logic into a separate Pinokio app folder. Instead, it launches the current PMOVES stack from `../../pmoves`, seeds the runtime MCP map, and exposes the Agent Zero UI and API endpoints through Pinokio.

## Quick Start

1. Click **Install** to bootstrap `pmoves/env.shared` and seed Agent Zero MCP defaults.
2. Click **Start Agent Tier** to launch Agent Zero plus the supported PMOVES agent stack.
3. Open the **Agent Zero UI** at `http://localhost:8081`.
4. Use **Status** to inspect health and current MCP commands.

## Scripts

| Script | Purpose |
|--------|---------|
| `install.js` | Bootstrap PMOVES env files and seed `data/agent-zero/runtime/mcp/servers.env` |
| `start.js` | Start the supported PMOVES agent tier and tail Agent Zero logs |
| `status.js` | Show container status, `/healthz`, and `/mcp/commands` |
| `update.js` | Pull latest PMOVES changes, refresh submodules, and reseed MCP runtime |
| `reset.js` | Stop Agent Zero and clear runtime/log state before reseeding |

## What Start Launches

The launcher uses the repo-supported `make up-agents-ui` path from `pmoves/Makefile`. That brings up:

- NATS + JetStream bootstrap
- Agent Zero API and UI
- Archon API and UI
- DeepResearch
- SupaSerch
- Mesh Agent
- Publisher-Discord

That matches the current PMOVES control-plane bring-up better than a fake standalone Agent Zero package.

## API Reference

### Agent Zero API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `http://localhost:8080/healthz` | GET | Health check and controller status |
| `http://localhost:8080/config/environment` | GET | Resolved runtime configuration |
| `http://localhost:8080/mcp/commands` | GET | List MCP helpers and runtime metadata |
| `http://localhost:8080/mcp/execute` | POST | Execute an MCP command |
| `http://localhost:8080/docs` | GET | FastAPI docs |
| `http://localhost:8081` | GET | Agent Zero UI |

**Curl**

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/mcp/commands
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"cmd":"geometry.jump","arguments":{"point_id":"demo"}}'
```

**Python**

```python
import requests

print(requests.get("http://localhost:8080/healthz").json())
print(requests.get("http://localhost:8080/mcp/commands").json())
result = requests.post(
    "http://localhost:8080/mcp/execute",
    json={"cmd": "geometry.jump", "arguments": {"point_id": "demo"}},
)
print(result.json())
```

**JavaScript**

```javascript
const health = await fetch("http://localhost:8080/healthz").then(r => r.json())
const commands = await fetch("http://localhost:8080/mcp/commands").then(r => r.json())
const result = await fetch("http://localhost:8080/mcp/execute", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ cmd: "geometry.jump", arguments: { point_id: "demo" } })
}).then(r => r.json())
```

## Notes

- MCP defaults are seeded into `pmoves/data/agent-zero/runtime/mcp/servers.env`.
- This launcher intentionally tracks the PMOVES repo layout instead of a separate `app/` clone.
- Provider-specific agent customization belongs in Pinokio plugins such as `pmoves-codex`, not inside this launcher.
