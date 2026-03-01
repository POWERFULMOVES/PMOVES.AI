# Codex Home Overlay: PMOVES-Archon

Scope:
- Archon API and UI operator parity in PMOVES hardened bring-up.

Core checks:
- `curl -fsS http://localhost:8091/healthz | jq .`
- `curl -fsS -o /dev/null -w "%{http_code}" http://localhost:3737/`
- `make -C pmoves archon-mcp-smoke`

Related parity tokens:
- `/archon:status`
- `/archon:forms`
- `/archon:prompts`
