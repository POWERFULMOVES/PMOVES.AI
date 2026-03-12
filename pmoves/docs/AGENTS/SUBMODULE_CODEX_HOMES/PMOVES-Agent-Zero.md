# Codex Home Overlay: PMOVES-Agent-Zero

Scope:
- Agent Zero orchestrator runtime and MCP bridge parity.

Use this when:
- the task needs cross-service orchestration, MCP calls, or agent handoff
- Codex needs a control-plane entrypoint into the wider PMOVES stack
- persona, tool, or workflow routing must be delegated instead of hard-coded

PMOVES companions:
- `PMOVES-Archon` for prompts/forms/planning
- `Pmoves-cipher` for checkpoint and reasoning continuity
- `PMOVES-BoTZ` for MCP tool inventory
- `PMOVES-tensorzero` for model routing
- `pmoves/docs/AGENTS/PERSONAS.md` for persona lane selection

Core checks:
- `curl -fsS http://localhost:8080/healthz | jq .`
- `curl -fsS http://localhost:8080/mcp/health | jq .`
- `make -C pmoves agents-headless-smoke`

Related parity tokens:
- `/agents:status`
- `/agents:mcp-query`
- `/agents:execute`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- `.claude/context/mcp-api.md`
