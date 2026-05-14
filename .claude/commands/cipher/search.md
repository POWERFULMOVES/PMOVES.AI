# Cipher Search

Search Cipher Memory for stored knowledge and reasoning traces.

## Instructions

Search the Cipher Memory knowledge graph. Use the MCP tool as the primary path.
If Cipher is unreachable or MCP fails, search local auto-memory instead.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8105/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

### Step 2a: Search via MCP tool (primary — if CIPHER_UP)

Use the MCP tool `pmoves_cipher_search`:

```
Tool: pmoves_cipher_search
Arguments:
  query: "$QUERY"
  category: "$CATEGORY"       # optional filter
  tags: ["$TAG1"]             # optional filter
  limit: 10                   # optional, default 10
```

**Category filters** (must match `tools.py` enum):
`code_pattern`, `decision`, `context`, `submodule`, `architecture`, `reasoning`

> **Known issue (2026-04-01):** MCP tools are currently blocked by the same gap as REST.
> The MCP client (`pmoves-cipher-mcp/cipher_mcp/client.py`) calls `GET /api/memory/search`
> which does not exist in `Pmoves-cipher` (no `/api/memory` routes registered in `server.ts`).
> Until the cipher-api submodule implements these routes, MCP tools will return 404.
> **Use the fallback below.**

### Step 2b: Fallback — search local auto-memory (if CIPHER_DOWN or MCP fails)

If the health check shows `CIPHER_DOWN`, or MCP returns a 404/connection error,
do NOT retry. Instead, search the auto-memory file using the Read and Grep tools:
- Index file: `~/.claude/projects/<project>/memory/MEMORY.md`
- Read the index, then follow links to topic files matching the query
- Use Grep to search across all `*.md` files in the memory directory

### Marco/Polo pattern

Search with a different phrasing than how the memory was stored.
Cipher's embedding model bridges intent across phrasings.

```
# If stored as: "Agent orientation: claims register shows lanes A, B, C active"
# Search with: "what lanes are currently claimed"
```

When searching locally (fallback), use multiple keyword variations since
local search is keyword-based, not semantic.
