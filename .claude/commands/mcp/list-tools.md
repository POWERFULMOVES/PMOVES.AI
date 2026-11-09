# MCP — List Tools

Enumerate the tools a catalogued MCP server exposes, through the gateway when it is up.

## Arguments

- `$ARGUMENTS` - server name (optional; omit to list every catalogued server's tools)

## Instructions

1. With the fleet gateway running: `make -C pmoves mcp-gateway-verify` prints per-server tool counts and example tools — the canonical answer.
2. Direct (no gateway): for stdio servers run their list-tools entry point; for SSE servers perform the full MCP handshake (`initialize` → `notifications/initialized`, echoing `Mcp-Session-Id`) before `tools/list` — skipping the handshake is rejected by design.
3. Catalog-only: read the server's entry in `pmoves/config/mcp-gateway/catalog.yaml` for its declared tool surface without touching the network.
4. Output a table: server | transport | tool count | example tools.

## Notes

- `docker mcp tools ls` is NOT a substitute — it spawns its own gateway rather than querying the deployed one (documented in #2665).
