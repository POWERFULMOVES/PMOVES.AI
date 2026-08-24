# MCP — Connect a Server

Bring a catalogued MCP server into the session and prove the handshake before use.

## Arguments

- `$ARGUMENTS` - server name (e.g. `botz-mcp-bridge`, `pmoves-hirag-mcp`) and optional transport flags

## Instructions

1. Resolve the server from `pmoves/config/mcp-gateway/catalog.yaml` (compose fleet) or the `mcp_servers` block of `pmoves/config/agent_registry.yaml` (discovery plane). A name present in neither is not a PMOVES server — stop and say so.
2. For stdio servers (`command: uvx ...`), run the entry point and list tools once to prove importability:
   `npx @modelcontextprotocol/inspector --cli <command> <args...>` or the server's own list-tools path.
3. For SSE/streaming servers, verify the endpoint answers (`/healthz` or the SSE handshake) before declaring connected. Streamable HTTP requires `initialize` → `notifications/initialized`; a raw `tools/list` POST is rejected by design.
4. If the fleet MCP Gateway is running (`make -C pmoves up-mcp-gateway`, default host port 8189), prefer connecting through it with the pipeline token (`MCP_GATEWAY_AUTH_TOKEN` via `env.tier-agent`) — one authenticated endpoint for every catalogued server.
5. Report: server, transport, endpoint, tool count, and the first three tool names.

## Notes

- Never paste the gateway token. Read it from the tier env files.
- A server that answers 401 without credentials is behaving correctly — supply the token, don't bypass.
