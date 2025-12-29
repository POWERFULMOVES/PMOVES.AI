# LangExtract Process Document

Process a document file using the orchestrator pipeline (Docling + TensorZero).

## Arguments

- `$ARGUMENTS` - File path or URL to the document to process

## Instructions

1. Call the LangExtract /process/document endpoint with the file path
2. The orchestrator will:
   - Convert the document using Docling MCP (PDF, DOCX, HTML, images)
   - Optionally analyze images with VL Sentinel
   - Chunk text using TensorZero-backed provider
   - Optionally ingest to extract-worker for embeddings
3. Report the processing results

```bash
curl -X POST http://localhost:8084/process/document \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "$ARGUMENTS",
    "namespace": "pmoves",
    "output_format": "text"
  }'
```

Report:
- Document conversion status
- Number of chunks extracted
- Number of chunks ingested (if auto_ingest enabled)
- Any errors from Docling, VL Sentinel, or extraction
