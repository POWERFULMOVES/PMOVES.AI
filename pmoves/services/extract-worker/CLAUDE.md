# extract-worker — Subsystem Context

> Subsystem-specific CLAUDE.md. Load on demand when working inside `pmoves/services/extract-worker/`. README (this directory) covers operator setup.

## Role

Embedding worker for the Hi-RAG ingestion pipeline. Consumes text artifacts (transcripts, PDFs, page bodies), generates embeddings via TensorZero, writes to Qdrant (vectors) + Meilisearch (full-text) + Neo4j (graph).

## TensorZero embedding contract

**The embedding endpoint format is non-obvious — get it wrong and you get a 404:**

- ✅ Correct: `http://tensorzero:3030/openai/v1/embeddings` with model `tensorzero::embedding_model_name::qwen3_embedding_4b_local`
- ❌ Wrong: `http://tensorzero:3030/v1/embeddings` (returns 404)

Vector dimensions (cite if you change models):
- `qwen3_embedding_4b_local` → **2560d** (NOT 3072 — common mistake)
- `qwen3_embedding_8b_local` → **4096d**

Hi-RAG-v2 assumes 2560d unless overridden. Check `pmoves/services/hi-rag-gateway-v2/` for the consumer side before bumping model.

## Pipeline placement

```
   Media ingest (PMOVES.YT, PDF, etc.)
              │
              ▼
       ffmpeg-whisper (audio → text) │ pdf-ingest (PDF → text)
              │
              ▼
       Hi-RAG ingestion queue (NATS)
              │
              ▼
     extract-worker (this) — embed + persist
              │
              ▼
       Qdrant + Meilisearch + Neo4j
              │
              ▼
       hi-rag-gateway-v2 query path
```

## CHIT integration

**Status: Partial** per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`. Embedded chunks should be CHIT-signed before persistence so retrieval can verify provenance. Raising to Full tier is on the Wave-1 backlog.

## Common tasks

- **Change embedding model**: update env var + verify dim assumption in Hi-RAG-v2 consumer + reindex affected collections.
- **Add a new content type**: extend the NATS subject consumer; respect the standard chunk schema (text + source_uri + offsets).
- **Debug throughput**: extract is GPU-bound (via TensorZero); check `/gpu:status` and `nvidia-smi` (or `rocm-smi`).
- **Backfill**: there's no incremental reindex tool yet — full pipeline replay required (TODO: add a `make -C pmoves reindex SERVICE=hirag` target).

## Cross-references

- README: this directory (currently 146 bytes — see audit).
- Audit: `pmoves/docs/audit/2026-05-15-service-doc-audit.md` flagged as P1 fix.
- TensorZero details: `.claude/context/tensorzero.md`.
- Consumers: `pmoves/services/hi-rag-gateway-v2/`, `pmoves/services/hi-rag-gateway/` (legacy).
- TAC tree: `pmoves/docs/TAC/TAC_HIRAG_RETRIEVAL.md`.
