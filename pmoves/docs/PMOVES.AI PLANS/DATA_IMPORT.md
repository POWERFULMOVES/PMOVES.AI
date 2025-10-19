# Data Import (Qdrant + Meilisearch)

## JSONL format
- One JSON object per line.
- Required: `text`
- Optional: `doc_id`, `section_id`, `chunk_id`, `namespace` (defaults to `INDEXER_NAMESPACE`).

Example line:
```
{"doc_id":"guide","section_id":"intro","chunk_id":"guide-intro-1","namespace":"pmoves","text":"PMOVES is a modular orchestration mesh..."}
```

## Commands
- Seed small demo set:
  - `make seed-data`
- Load your JSONL file:
  - `make load-jsonl FILE=/absolute/path/to/data.jsonl [NAMESPACE=pmoves]`

The loader:
- Embeds `text` via SentenceTransformers and upserts to Qdrant collection `${QDRANT_COLLECTION}`.
- Indexes documents into Meilisearch index `${QDRANT_COLLECTION}` when available.

## PDF ingestion from MinIO / S3
The `pdf-ingest` service downloads PDFs stored in MinIO/S3, extracts paragraphs via `libs.langextract`, and forwards chunks to the extract worker so they land in Qdrant/Meilisearch.

1. Ensure the core stack is running (`make up`). The workers profile now launches `pdf-ingest` alongside langextract and extract-worker.
2. Upload a PDF to MinIO (or any S3-compatible bucket). A presign shortcut:
   ```bash
   curl -s -X POST http://localhost:8088/presign/put \
     -H 'content-type: application/json' \
     -H "Authorization: Bearer ${PRESIGN_SHARED_SECRET:-change_me}" \
     -d '{"bucket":"assets","key":"pdfs/sample.pdf","content_type":"application/pdf","expires":300}' \
     | jq -r '.url' \
     | xargs -I {} curl -s -X PUT -H 'Content-Type: application/pdf' --data-binary @pmoves/datasets/sample.pdf '{}' >/dev/null
   ```
3. Trigger ingestion:
   ```bash
   curl -s http://localhost:8092/pdf/ingest \
     -H 'content-type: application/json' \
     -d '{"bucket":"assets","key":"pdfs/sample.pdf","namespace":"pmoves","title":"Sample PDF"}' | jq .
   ```

The service emits `ingest.file.added.v1` and `ingest.document.ready.v1` events (via NATS) and mirrors any langextract errors into Supabase through `extract-worker`.

## Notes
- Ensure the stack is up (`make up`).
- Large files: run with enough memory and expect model download on first use.
- Control PDF fan-out via env vars:
  - `PDF_DEFAULT_BUCKET`, `PDF_DEFAULT_NAMESPACE` – fallbacks for the service request body.
  - `PDF_MAX_PAGES` – limit pages processed per document (0 = all pages).
  - `PDF_INGEST_EXTRACT_URL` – override the extract-worker endpoint when running standalone.
