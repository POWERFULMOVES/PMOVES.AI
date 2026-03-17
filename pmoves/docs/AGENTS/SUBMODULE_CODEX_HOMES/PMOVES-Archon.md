# Codex Home Overlay: PMOVES-Archon

Scope:
- Archon API and UI operator parity in PMOVES hardened bring-up.

Use this when:
- the task is persona, prompt, form, or agent-configuration heavy
- Codex needs a Supabase-backed planning surface instead of raw MCP execution
- Agent Zero needs a companion planner rather than a direct tool call

PMOVES companions:
- `PMOVES-Agent-Zero` for orchestration
- `PMOVES-supabase` for prompt/state persistence
- `pmoves/integrations/archon` for the integration mount
- `pmoves/docs/AGENTS/PERSONAS.md` for persona routing policy

Core checks:
- `curl -fsS http://localhost:8091/healthz | jq .`
- `curl -fsS -o /dev/null -w "%{http_code}" http://localhost:3737/`
- `make -C pmoves archon-mcp-smoke`

Related parity tokens:
- `/archon:status`
- `/archon:forms`
- `/archon:prompts`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `.claude/context/submodules.md`
- `.claude/context/submodule-workflow.md`
