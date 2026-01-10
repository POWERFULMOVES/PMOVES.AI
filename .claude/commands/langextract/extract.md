# LangExtract Extract

Extract and chunk text content for ingestion into the PMOVES knowledge base.

## Arguments

- `$ARGUMENTS` - Text content to extract and chunk

## Instructions

1. Call the LangExtract /extract/text endpoint with the provided text
2. Parse the response to get chunks and any errors
3. Report the number of chunks extracted and their IDs

```bash
curl -X POST http://localhost:8084/extract/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "$ARGUMENTS",
    "namespace": "pmoves",
    "doc_id": "cli-extract"
  }'
```

Report:
- Number of chunks extracted
- Chunk IDs and brief content preview (first 50 chars)
- Any errors encountered during extraction
- Ingestion status if auto_ingest is enabled
