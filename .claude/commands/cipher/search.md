# Cipher Search

Search Cipher Memory for stored knowledge and reasoning traces.

## Instructions

Search the Cipher Memory knowledge graph. The user should provide a search query.

```bash
# Search Cipher Memory (port 8096)
curl -s "http://localhost:8096/api/memory/search?q=$QUERY&limit=10" | python -c "
import sys, json
d = json.load(sys.stdin)
results = d if isinstance(d, list) else d.get('results', [])
for i, r in enumerate(results):
    print(f'{i+1}. [{r.get(\"category\",\"?\")}] {r.get(\"content\",\"?\")[:120]}...')
    print(f'   source={r.get(\"source\",\"?\")} ts={r.get(\"timestamp\",\"?\")}')
"
```

```bash
# Check Cipher Memory health
curl -s http://localhost:8096/health
```

**Notes:**
- Also available via MCP tool: `pmoves_cipher_search`
- Supports semantic search over Neo4j graph
- Results include category, source, and timestamp metadata
