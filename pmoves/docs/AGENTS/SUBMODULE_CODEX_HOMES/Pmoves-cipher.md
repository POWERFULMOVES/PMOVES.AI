# Codex Home Overlay: Pmoves-cipher

Scope:
- Cipher memory service parity for store/search/reasoning traces.

Core checks:
- `curl -fsS http://localhost:8096/health | jq .`
- `uv run --directory ./pmoves-cipher-mcp python -m cipher_mcp.server`
- `curl -s "http://localhost:8096/api/memory/search?q=pmoves&limit=5"`

Related parity tokens:
- `/cipher:store`
- `/cipher:search`
- `/cipher:reasoning`
