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

> **RETRACTED 2026-09-09 — this blocker was measurably false.** It read: "MCP tools
> are currently blocked ... `GET /api/memory/search` ... does not exist in
> `Pmoves-cipher` (no `/api/memory` routes registered in `server.ts`) ... Use the
> fallback below." That instruction told every agent to SKIP cipher, and agents
> followed it.
>
> Measured on Z890 against the live container at submodule pin `e24f1323`:
> `POST /api/memory` -> **201** with a non-null `embedding_id`, and a semantic
> recall phrased differently from the stored text returned the new record. The
> routes exist — `Pmoves-cipher/src/pmoves/memory-routes.ts`. The A1-Shim
> re-implemented them (`Pmoves-cipher/PMOVES.AI_INTEGRATION.md` §Contracts), which
> is exactly what the 2026-04-01 note was waiting for; nobody came back to clear it.
>
> **The blocker you WILL hit instead is identity, not routing.** Every store/search
> call requires `agentId`, and it must match the agent your token was minted for:
>
> ```
> 403 token belongs to agent 'bootstrap', but request specified 'z890-claude'
> ```
>
> A node holding a shared `bootstrap` token refuses your real signing-card id
> (`pmoves/config/signing_identity_cards.yaml`). That is the credential being
> mis-provisioned, not the service being down — do not "fix" it by falling back.
> Cross-agent `agentId: "*"` is refused outright under token enforcement
> (`memory-routes.ts`). Remedy is a per-agent mint through the CHIT pipeline.
>
> **Never** read `CIPHER_API_TOKEN` out of `docker inspect` or a container env to
> work around this. That is a CHIT-pipeline bypass; it was done during this
> investigation and it was wrong. If the MCP server is not connected in your
> session, say so and use auto-memory — that is the documented rule, not a
> failure state.

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
