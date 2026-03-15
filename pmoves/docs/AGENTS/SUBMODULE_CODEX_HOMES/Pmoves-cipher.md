# Codex Home Overlay: Pmoves-cipher

Scope:
- Cipher memory service parity for store/search/reasoning traces.

Use this when:
- Codex needs durable memory across sessions, PR waves, or agent handoffs
- you need checkpoint/resume behavior for a long-running task
- the lane needs a factual memory surface instead of doc-only notes

PMOVES companions:
- `PMOVES-Agent-Zero` and `PMOVES-Archon` for routed execution
- `PMOVES-supabase` for persistent metadata/state
- `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md`

Core checks:
- `curl -fsS http://localhost:8096/health | jq .`
- `uv run --directory ./pmoves-cipher-mcp python -m cipher_mcp.server`
- `curl -s "http://localhost:8096/api/memory/search?q=pmoves&limit=5"`

Related parity tokens:
- `/cipher:store`
- `/cipher:search`
- `/cipher:reasoning`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`
- `.claude/skills/pmoves-cipher-memory/SKILL.md`
