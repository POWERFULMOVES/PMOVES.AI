# Notebook Query

Query the Open Notebook knowledge base via SurrealDB.

## Instructions

The user should provide a search query or topic. This queries the Open Notebook via:
1. **Hi-RAG v2** — semantic search over indexed notebook content
2. **Meilisearch** — full-text keyword search

```bash
# Query via Hi-RAG v2 (preferred — combines vector + graph + full-text)
curl -s -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "$QUERY", "top_k": 10, "rerank": true}'
```

```bash
# Direct Meilisearch query (keyword search)
curl -s "http://localhost:7700/indexes/pmoves_chunks/search" \
  -H "Content-Type: application/json" \
  -d '{"q": "$QUERY", "limit": 10}'
```

Report:
- Top matching results with relevance scores
- Source documents and snippets
- Total matches found
