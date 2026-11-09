# MCP — Invoke a Tool

Call a tool on a catalogued MCP server with the correct handshake and auth.

## Arguments

- `$ARGUMENTS` - `server tool-name` followed by JSON arguments (e.g. `botz-mcp-bridge cast_list {}`)

## Instructions

1. Parse server, tool, and the JSON arguments from `$ARGUMENTS`. Reject non-JSON argument strings rather than guessing.
2. Route through the fleet gateway when it is up (`http://localhost:${MCP_GATEWAY_PORT:-8189}/mcp`, Bearer `MCP_GATEWAY_AUTH_TOKEN` from `env.tier-agent`): initialize, capture `Mcp-Session-Id`, send `notifications/initialized`, then `tools/call`.
3. Direct-to-server fallback: use the server's native transport (stdio for `uvx` servers, SSE handshake for HTTP servers) with the same JSON-RPC discipline.
4. Print the tool's structured result. If the call returns an error object, surface it verbatim — do not unwrap or summarize away the error code.
5. Never retry a state-changing call automatically; the caller decides.

## Notes

- State-changing actions still route through pmoves-chit-sign per the bootstrap CGP constraints.
