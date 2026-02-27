# Cipher Search

Search Cipher Memory for stored knowledge and reasoning traces.

## Instructions

Search the Cipher Memory knowledge graph. First check if the service is reachable.
If it is NOT reachable, search local auto-memory (MEMORY.md) instead.
Do NOT let a connection failure interrupt your workflow.

### Step 1: Health check (silent, non-blocking)

```bash
curl -sf --max-time 3 http://localhost:8096/health > /dev/null 2>&1 && echo "CIPHER_UP" || echo "CIPHER_DOWN"
```

### Step 2a: Search via Cipher Memory (only if CIPHER_UP)

```bash
curl -s "http://localhost:8096/api/memory/search?q=$QUERY&limit=10" | python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d if isinstance(d, list) else d.get('results', [])
for i, r in enumerate(results):
    print(f'{i+1}. [{r.get(\"category\",\"?\")}] {r.get(\"content\",\"?\")[:120]}...')
    print(f'   source={r.get(\"source\",\"?\")} ts={r.get(\"timestamp\",\"?\")}')
"
```

### Step 2b: Fallback — search local auto-memory (if CIPHER_DOWN)

If the health check shows `CIPHER_DOWN`, do NOT attempt the curl call.
Instead, read and search the auto-memory file using the Read tool:
- File: `~/.claude/projects/<project>/memory/MEMORY.md`
- Search for the user's query terms within the file content

**Notes:**
- Also available via MCP tool: `pmoves_cipher_search` (requires MCP server running)
- Supports semantic search over Neo4j graph when online
- Results include category, source, and timestamp metadata
