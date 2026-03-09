# Codex Home Overlay: PMOVES-BoTZ

Scope:
- BoTZ agent lifecycle, MCP gateway parity, and role orchestration.

Core checks:
- `make -C pmoves codex-health-quick`
- `make -C pmoves codex-audit`
- `curl -fsS http://localhost:8080/healthz | jq .`

Related parity tokens:
- `/botz:init`
- `/botz:mcp`
- `/botz:profile`
