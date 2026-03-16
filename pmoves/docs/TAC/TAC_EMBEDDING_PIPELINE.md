# TAC_EMBEDDING_PIPELINE
_Last updated: 2026-03-15_

## Mission

Unified text embedding, indexing, and document processing pipeline. Three worker services collaborate to transform raw content (transcripts, PDFs, text) into searchable vectors and full-text indexes consumed by Hi-RAG v2.

## Services

### Extract Worker (8083)
- **Role:** Text embedding and dual-indexing (Qdrant vectors + Meilisearch full-text)
- **Model:** `all-MiniLM-L6-v2` (default), configurable via `EXTRACT_WORKER_EMBEDDING_BACKEND`
- **API:** `POST http://localhost:8083/ingest`
- **Backend:** TensorZero (preferred) or direct model loading
- **Docker Profile:** `workers`

### LangExtract (8084)
- **Role:** Language detection and NLP preprocessing
- **Consumers:** Notebook Sync, Extract Worker
- **Used by:** Pipeline stages that need language classification before embedding

### PDF Ingest (8092)
- **Role:** Document ingestion orchestrator
- **Flow:** Reads PDFs from MinIO → extracts text → sends to Extract Worker
- **Docker Profile:** `orchestration`

## Architecture

```
Upstream Sources
  │
  ├── PMOVES.YT (transcripts)
  ├── PDF Ingest (8092) ──► MinIO PDFs
  ├── Notebook Sync (8095) ──► SurrealDB entries
  │
  ▼
LangExtract (8084)
  │ language detection
  ▼
Extract Worker (8083)
  │
  ├──► Qdrant (6333) — vector embeddings
  ├──► Meilisearch (7700) — full-text search
  │
  ▼
Hi-RAG v2 (8086) — unified retrieval
```

## NATS Integration

| Subject | Publisher | Consumer | Description |
|---------|-----------|----------|-------------|
| `ingest.file.added.v1` | PMOVES.YT, PDF Ingest | Extract Worker | New content available |
| `ingest.transcript.ready.v1` | FFmpeg-Whisper | Extract Worker | Transcript ready for indexing |

## Configuration

| Variable | Service | Default |
|----------|---------|---------|
| `EXTRACT_WORKER_EMBEDDING_BACKEND` | Extract Worker | `tensorzero` |
| `EXTRACT_WORKER_HOST_PORT` | Extract Worker | `8083` |
| `QDRANT__SERVICE__HOST` | Extract Worker | `qdrant` |
| `QDRANT__SERVICE__HTTP_PORT` | Extract Worker | `6333` |
| `MEILI_MASTER_KEY` | Extract Worker | Auto-generated |

## Production Readiness

| Check | Extract Worker | LangExtract | PDF Ingest |
|-------|---------------|------------|-----------|
| `/healthz` | TBD | TBD | TBD |
| NATS | Consumer | N/A | Publisher |
| Auth | Network isolation | Network isolation | Network isolation |
| GPU | Optional (embedding) | N/A | N/A |
| Docker | `workers` profile | `workers` profile | `orchestration` profile |

## Verification

```bash
curl -X POST http://localhost:8083/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"Test document for embedding pipeline","source":"tac-test"}'
```
