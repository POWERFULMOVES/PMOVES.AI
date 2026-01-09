Query the Hi-RAG v2 hybrid retrieval system for knowledge and context.

This command queries PMOVES's production Hi-RAG v2 service (port 8086) which combines:
- **Qdrant** - Vector semantic search
- **Neo4j** - Knowledge graph traversal
- **Meilisearch** - Full-text keyword search
- **Cross-encoder reranking** - Improved relevance

The system automatically reranks results for optimal relevance using transformer models.

## Usage

When the user asks to search the knowledge base or needs context retrieval, use this command.

## Implementation

Execute the following steps:

1. **Query Hi-RAG v2:**
   ```bash
   curl -X POST http://localhost:8086/hirag/query \
     -H "Content-Type: application/json" \
     -d '{"query": "<user_query>", "top_k": 10, "rerank": true}'
   ```

2. **Parse the JSON response** which contains:
   - `results` - Array of relevant context chunks
   - `metadata` - Source information, scores, relationships
   - `reranked` - Boolean indicating if reranking was applied

3. **Present results to user:**
   - Show relevant context found
   - Include source references from metadata
   - Explain relevance based on scores

## Example

```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How does Agent Zero coordinate with other agents?", "top_k": 10, "rerank": true}'
```

## Notes

- Hi-RAG v2 (ports 8086/8087) is the **preferred** system over v1 (8089/8090)
- GPU version on 8087 uses advanced reranking models for better results
- Results are automatically cached for performance
- Check service health: `curl http://localhost:8086/healthz`
