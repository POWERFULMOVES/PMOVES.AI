# cipher-village-pr-3-mcp-catalog-bridge

Field brief for **any implementation agent** — implement Phase B PR 3 of the
Cipher Village architecture. Cipher brokers the BoTZ gateway tool registry so
agents can discover available MCPs through cipher.

Source architecture: `pmoves/docs/TAC/TAC_CIPHER_VILLAGE.md` §Phase B PR 3.

## Arguments

- `botz_gateway_url` (string, default `${BOTZ_GATEWAY_URL:-http://gateway-agent:8111}`):
  the gateway-agent endpoint that proxies BoTZ ToolRegistry.
- `redis_url` (string, optional, default `${REDIS_URL:-redis://redis:6379}`):
  direct Redis connection to read `tool:list` + `tool:{name}` keys
  (the .NET BoTZ gateway's persistence layer). If unreachable, falls back to
  gateway-agent HTTP API.
- `refresh_interval_seconds` (number, default 300): how often cipher refreshes
  its cached catalog from the source.

## Implementation

### 1. Create mcp-catalog.ts

Create `Pmoves-cipher/src/pmoves/mcp-catalog.ts`:

```typescript
export interface MCPRegistryEntry {
  name: string                    // tool name (e.g. "pmoves_supabase")
  description: string
  transport: 'stdio' | 'sse' | 'http'
  endpoint?: string               // URL for sse/http, or command for stdio
  args?: string[]                 // for stdio
  env_required?: string[]         // env vars the MCP needs
  scopes?: string[]               // which agent scopes can see this tool
  source: 'botz-redis' | 'gateway-agent' | 'static'
}

export class MCPCatalogClient {
  // Reads from Redis (tool:list → tool:{name} keys) OR falls back to
  // gateway-agent GET /tools endpoint. Caches in-memory with TTL.
  constructor(redisUrl: string, gatewayUrl: string, ttlSeconds: number)
  async list(agentId?: string): Promise<MCPRegistryEntry[]>  // filtered by scopes
  async get(name: string): Promise<MCPRegistryEntry | null>
  async refresh(): Promise<void>  // force re-read from source
}
```

Key implementation details:
- Redis path: `GET tool:list` → JSON array of names → for each, `GET tool:{name}` → JSON `ToolResource`
- Map .NET `ToolResource` to `MCPRegistryEntry` (field names differ — see `PMOVES-BotZ-gateway/dotnet/Microsoft.McpGateway.Management/src/Contracts/ToolResource.cs`)
- Gateway-agent fallback: `GET http://gateway-agent:8111/tools` → `ToolRegistry.list_tools()` output (see `pmoves/services/gateway-agent/app.py:215-305`)
- If both unreachable: return empty list (fail-open, don't block agent boot)
- Scope filtering: if entry has `scopes` and agent's token has scopes, intersect; if no overlap, hide the entry

### 2. Add two new MCP tools to mcp-sse.ts

In `Pmoves-cipher/src/pmoves/mcp-sse.ts`, add to the tools array:

```typescript
{
  name: 'pmoves_cipher_mcp_list',
  description: 'List available MCP servers from the BoTZ gateway tool registry. Returns name, transport, endpoint, and required env for each. Use this to discover what tools are available before connecting directly.',
  inputSchema: {
    type: 'object',
    properties: {
      agentId: {type: 'string', description: 'Agent identifier (for scope filtering).'},
      transport: {type: 'string', enum: ['stdio', 'sse', 'http'], description: 'Filter by transport type.'},
    },
    required: ['agentId'],
  },
},
{
  name: 'pmoves_cipher_mcp_get',
  description: 'Get detailed configuration for one MCP server from the BoTZ gateway registry. Returns the full connection config (command, args, env, URL) needed to connect directly.',
  inputSchema: {
    type: 'object',
    properties: {
      name: {type: 'string', description: 'MCP server name (from mcp_list).'},
      agentId: {type: 'string'},
    },
    required: ['name', 'agentId'],
  },
}
```

### 3. Wire catalog client into buildMcpServer

In the `CallToolRequestSchema` handler, add:

```typescript
if (name === 'pmoves_cipher_mcp_list') {
  const {agentId, transport} = args as {agentId: string; transport?: string}
  const catalog = getMCPCatalogClient()
  const entries = await catalog.list(agentId)
  const filtered = transport ? entries.filter(e => e.transport === transport) : entries
  return {content: [{type: 'text', text: JSON.stringify({mcpServers: filtered})}]}
}

if (name === 'pmoves_cipher_mcp_get') {
  const {name: mcpName, agentId} = args as {name: string; agentId: string}
  const catalog = getMCPCatalogClient()
  const entry = await catalog.get(mcpName)
  if (!entry) return {content: [{type: 'text', text: JSON.stringify({error: 'Not found'})}]}
  return {content: [{type: 'text', text: JSON.stringify(entry)}]}
}
```

### 4. NATS event on catalog change

Add to `Pmoves-cipher/src/pmoves/nats-emitter.ts`:

```typescript
emitMcpCatalogUpdated(entryCount: number, source: string): void
// Subject: cipher.mcp.catalog.updated.v1
// Payload: {entry_count, source, ts}
```

Publish after each `refresh()` call.

## Related

- `PMOVES-BotZ-gateway/dotnet/Microsoft.McpGateway.Management/src/` — Redis-backed CRUD (.NET)
- `PMOVES-BotZ-gateway/dotnet/Microsoft.McpGateway.Management/src/Contracts/ToolResource.cs` — schema to map from
- `pmoves/services/gateway-agent/app.py:215-305` — `ToolRegistry` Python fallback source
- `PMOVES-BoTZ/features/cipher/pmoves_cipher/src/core/mcp/aggregator.ts` — cipher's in-memory aggregator (alternative source)
- `.claude/context/nats-subjects.md` — add `cipher.mcp.catalog.updated.v1`

## Notes

- Three tool-registry sources exist (BotZ .NET/Redis, gateway-agent Python, cipher aggregator). This PR reads from the first two; the aggregator is a secondary source for BoTZ-internal tools.
- Fail-open: if neither Redis nor gateway-agent is reachable, return empty list. Never block agent boot on catalog availability.
- The .NET gateway stores tools in Redis keys `tool:{name}` (JSON) and `tool:list` (JSON array of names). The Python gateway-agent caches via `GET /mcp/commands` from Agent Zero with 5-min TTL.
- Scope filtering is advisory in this PR (PR 2 tokens haven't landed yet). When PR 2 ships, the `agentId` parameter here will be cross-checked against `req.agentId` from the token.
- Don't proxy tool EXECUTION through cipher — only discovery. Agents connect to the MCP directly once they know the endpoint. Cipher is the catalog, not the proxy.

## Verification

```bash
# 1. Ensure gateway-agent is up (it is on SPARK)
docker ps --filter name=gateway-agent

# 2. Via MCP tool:
#    pmoves_cipher_mcp_list(agentId="crush-spark")
#    → should return the gateway-agent's tool list

# 3. Via REST (quick check):
#    GET http://gateway-agent:8111/tools
#    → compare with cipher output

# 4. NATS subscription check:
#    nats sub cipher.mcp.catalog.updated.v1
#    → should fire on refresh
```
