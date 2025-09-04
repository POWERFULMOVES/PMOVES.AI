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

## Notes
- Ensure the stack is up (`make up`).
- Large files: run with enough memory and expect model download on first use.
