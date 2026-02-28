# Cipher Store

Store a memory entry in Cipher Memory (Neo4j-backed knowledge graph).

## Instructions

Store a memory entry. First check if Cipher Memory is reachable.
If it is NOT reachable, fall back to local auto-memory (write to MEMORY.md instead).
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

Run this check. If it fails, skip to the **Fallback** section below.

```bash
curl -sf --max-time 3 http://localhost:8096/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

### Step 2a: Store via Cipher Memory (only if CIPHER_UP)

```bash
curl -s -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$CONTENT",
    "category": "$CATEGORY",
    "source": "claude-code",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'
```

### Step 2b: Fallback — store in local auto-memory (if CIPHER_DOWN)

If the health check shows `CIPHER_DOWN`, do NOT attempt the curl POST.
Instead, append the memory to your auto-memory file using the Write or Edit tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md`
- Add the content under an appropriate section heading

This ensures the memory is persisted even when Docker services are offline.

**Notes:**
- Cipher Memory also available via MCP tool: `pmoves_cipher_store` (requires MCP server running)
- Categories: `agent_plan`, `agent_checkpoint`, `agent_completion`, `pattern`, `learning`
- Content is indexed in Neo4j for graph traversal queries when Cipher is online
