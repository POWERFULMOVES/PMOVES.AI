# Codex Home Overlay: PMOVES-BoTZ

Scope:
- BoTZ agent lifecycle, MCP gateway parity, and role orchestration.

Use this when:
- Codex needs MCP servers, tool catalogs, or skills marketplace behavior
- the work is tool-first, sandbox-first, or multi-tool integration heavy
- the traversal question is "which tool or skill should PMOVES use?"

PMOVES companions:
- `PMOVES-Agent-Zero` for orchestration
- `Pmoves-cipher` for memory-backed tool traces
- `PMOVES-n8n` for workflow glue
- `pmoves/docs/AGENTS/PmovesSKillZ.md`
- `pmoves/configs/skill-pairings.yaml`

Core checks:
- `make -C pmoves codex-health-quick`
- `make -C pmoves codex-audit`
- `curl -fsS http://localhost:8080/healthz | jq .`

Related parity tokens:
- `/botz:init`
- `/botz:mcp`
- `/botz:profile`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/AGENTS/PmovesSKillZ.md`
- `pmoves/configs/submodule_skill_registry.json`
