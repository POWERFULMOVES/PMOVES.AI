# Cipher Store

Store a memory entry in Cipher Memory (Neo4j-backed knowledge graph).

## Instructions

Store a memory entry. Use the MCP tool as the primary path.
If Cipher is unreachable or MCP fails, fall back to local auto-memory.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8105/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

### Step 2a: Store via MCP tool (primary — if CIPHER_UP)

Use the MCP tool `pmoves_cipher_store`:

```yaml
Tool: pmoves_cipher_store
Arguments:
  content: "$CONTENT"
  category: "$CATEGORY"
  tags: ["$TAG1", "$TAG2"]
  metadata: { "source": "claude-code", "session": "$SESSION_ID" }
```

**Categories** (must match `tools.py` enum):
- `code_pattern` — Reusable code patterns and conventions
- `decision` — Architectural decisions and rationale
- `context` — Project-specific context
- `submodule` — Submodule knowledge and configuration
- `architecture` — System patterns and design
- `reasoning` — Chain-of-thought reasoning traces

> **Status (2026-07-24):** the `/api/memory` CRUD routes LANDED in Pmoves-cipher
> (fork PR #5, 2026-07-14 wave — same wave added the Qdrant embedding sidecar,
> hybrid search with BM25 sparse + dense RRF fusion, and Ollama fallback). The
> live API now returns **401 (auth required)**, not 404 — callers need the
> Cipher API key from the env tier. If the MCP tool is absent from the session
> or returns 401/connection errors, use the fallback below; do not retry.

### Step 2b: Fallback — store in local auto-memory (if CIPHER_DOWN or MCP fails)

If the health check shows `CIPHER_DOWN`, or MCP returns a 404/connection error,
do NOT retry. Instead, write the memory to your auto-memory file using the Write or Edit tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md` (index) + a topic file
- Add the content under an appropriate section heading
- Follow the memory file frontmatter format (name, description, type)

This ensures the memory is persisted even when Cipher services are offline.

### Marco/Polo pattern

Store with intent-shaped phrasing. When you later search, rephrase the query.
Cipher's embedding model bridges the gap between how you stored and how you search.

```text
# Marco (store)
/cipher:store Agent orientation: claims register shows lanes A, B, C active

# Polo (search later with different phrasing)
/cipher:search what lanes are currently claimed
```
