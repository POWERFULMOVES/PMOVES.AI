Trigger LLM-based research planning via DeepResearch service.

DeepResearch is an Alibaba Tongyi-powered research planning service that breaks down complex research questions into structured multi-step plans. It automatically publishes results to Open Notebook for persistent storage.

## Usage

Run this command when:
- User requests comprehensive research on a complex topic
- Need multi-step research planning with intermediate results
- Want automatic storage of research findings in Open Notebook
- Require structured research with citations and sources

## Implementation

Execute the following steps:

1. **Check DeepResearch service health:**
   ```bash
   curl http://localhost:8098/healthz
   ```

   Verify service is operational before submitting research requests.

2. **Publish research request to NATS:**
   ```bash
   nats pub "research.deepresearch.request.v1" '{
     "query": "<research_question>",
     "requester": "claude-code-cli",
     "context": {
       "depth": "comprehensive",
       "sources": ["web", "knowledge_base"]
     }
   }'
   ```

   DeepResearch listens on this subject and processes requests asynchronously.

3. **Subscribe to results (optional):**
   ```bash
   nats sub "research.deepresearch.result.v1" --count=1
   ```

   Wait for research completion event. Includes research plan, findings, and Open Notebook reference.

4. **Alternative: Direct API call (if available):**
   ```bash
   curl -X POST http://localhost:8098/research \
     -H "Content-Type: application/json" \
     -d '{
       "query": "<research_question>",
       "options": {
         "depth": "comprehensive",
         "auto_save": true
       }
     }'
   ```

5. **Report results to user:**
   - Research plan structure (steps, sub-questions)
   - Key findings and insights
   - Sources and citations
   - Open Notebook link for full research document

## NATS Integration

**DeepResearch uses event-driven architecture:**

- **Request subject:** `research.deepresearch.request.v1`
- **Result subject:** `research.deepresearch.result.v1`

Results are automatically published when research completes.

## Open Notebook Integration

DeepResearch automatically saves research to Open Notebook:
- Structured research plans
- Intermediate findings
- Final synthesis and conclusions
- Citations and source references

Access via `OPEN_NOTEBOOK_API_URL` with API token.

## Example Research Request

```bash
nats pub "research.deepresearch.request.v1" '{
  "query": "What are the latest advancements in hybrid RAG architectures?",
  "requester": "claude-code-cli",
  "context": {
    "depth": "comprehensive",
    "time_range": "2024-2025",
    "sources": ["academic", "industry"]
  }
}'
```

## Research Depth Levels

- **Quick** - Surface-level overview, 2-3 steps
- **Standard** - Balanced research, 4-6 steps
- **Comprehensive** - Deep dive, 7-10+ steps with sub-questions

## Integration with Other Services

DeepResearch coordinates with:
- **SupaSerch** - Multimodal holographic research orchestration
- **Hi-RAG v2** - Knowledge base retrieval for context
- **Open Notebook** - Persistent storage of research artifacts

## Monitoring

Check DeepResearch metrics:
```bash
curl http://localhost:8098/metrics
```

View active research tasks, completion rate, and error counts.

## Notes

- DeepResearch uses Alibaba Tongyi for LLM-based planning
- Research is asynchronous - results published to NATS when complete
- All research is automatically saved to Open Notebook
- Port 8098 for HTTP API
- NATS subjects follow versioned pattern (`.v1` suffix)
- For real-time research progress, subscribe to result subject before submitting
- Check service logs: `docker compose logs deepresearch`
- Part of `orchestration` compose profile
