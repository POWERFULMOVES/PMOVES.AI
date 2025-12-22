# LangExtract Status

Check the LangExtract service health and current provider configuration.

## Instructions

1. Check LangExtract health endpoint
2. Get provider configuration from /provider endpoint
3. If provider is "orchestrator", show MCP tool availability status

```bash
# Health check
curl -sf http://localhost:8084/healthz && echo "LangExtract: healthy" || echo "LangExtract: unavailable"

# Provider configuration
curl -s http://localhost:8084/provider | jq .
```

Report the following information:
- Service health status
- Current provider type (rule, orchestrator, tensorzero, openai, gemini, cloudflare)
- Orchestrator settings if applicable:
  - auto_ingest: Whether chunks are auto-ingested to extract-worker
  - use_docling: Whether Docling MCP is enabled for document conversion
  - use_vl: Whether VL Sentinel is enabled for image analysis
