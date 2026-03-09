# Codex Home Overlay: PMOVES-Agent-Zero

Scope:
- Agent Zero orchestrator runtime and MCP bridge parity.

Core checks:
- `curl -fsS http://localhost:8080/healthz | jq .`
- `curl -fsS http://localhost:8080/mcp/health | jq .`
- `make -C pmoves agents-headless-smoke`

Related parity tokens:
- `/agents:status`
- `/agents:mcp-query`
- `/agents:execute`
