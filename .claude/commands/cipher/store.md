# Cipher Store

Store a memory entry in Cipher Memory (Neo4j-backed knowledge graph).

## Instructions

Store a memory entry in Cipher Memory. The user should provide:
1. **Content** — the knowledge/memory to store
2. **Category** — optional category (e.g., `agent_plan`, `agent_checkpoint`, `agent_completion`)

```bash
# Store memory via Cipher Memory API (port 8096)
curl -s -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "$CONTENT",
    "category": "$CATEGORY",
    "source": "claude-code",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'
```

```bash
# Verify storage
curl -s "http://localhost:8096/api/memory/search?q=$SEARCH_TERM&limit=1"
```

**Notes:**
- Cipher Memory also available via MCP tools: `pmoves_cipher_store`
- Categories: `agent_plan`, `agent_checkpoint`, `agent_completion`, `pattern`, `learning`
- Content is indexed in Neo4j for graph traversal queries
