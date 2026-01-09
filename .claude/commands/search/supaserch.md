Execute multimodal holographic deep research using SupaSerch.

SupaSerch is PMOVES's advanced research orchestrator that coordinates multiple search and analysis tools to answer complex queries. It combines:
- **DeepResearch** - LLM-based research planning
- **Agent Zero MCP tools** - Code execution, web crawling
- **Hi-RAG** - Knowledge base retrieval
- **Supabase/Qdrant/Meilisearch** - Multi-source data querying

This is the most powerful research capability in PMOVES.AI.

## Usage

Use this command for:
- Complex multi-faceted research questions
- Queries requiring multiple data sources
- Research that needs planning and multi-step execution
- Questions that benefit from LLM reasoning + tool use

For simpler knowledge retrieval, use `/search:hirag` instead.

## Implementation

### Method 1: Via NATS (Async, Recommended)

1. **Publish research request to NATS:**
   ```bash
   nats pub "supaserch.request.v1" '{
     "query": "<user_research_question>",
     "request_id": "<unique_id>",
     "requester": "claude-code-cli"
   }'
   ```

2. **Subscribe to results:**
   ```bash
   nats sub "supaserch.result.v1" --max 1
   ```

3. **Parse the result** and present to user with:
   - Research findings
   - Source references
   - Methodology used

### Method 2: Via HTTP (if available)

If SupaSerch exposes an HTTP endpoint:

```bash
curl -X POST http://localhost:8099/research \
  -H "Content-Type: application/json" \
  -d '{"query": "<user_research_question>"}'
```

## Check Service Status

```bash
# Health check
curl http://localhost:8099/healthz

# Metrics (includes research count, latency)
curl http://localhost:8099/metrics
```

## Notes

- SupaSerch runs continuously, processing requests from NATS
- Results are automatically stored in Open Notebook for future reference
- Metrics available at `/metrics` for Prometheus scraping
- For simple knowledge queries, Hi-RAG v2 is faster
- For complex research needing multi-step planning, SupaSerch is the right tool
- Check logs: `docker compose logs supaserch`
