# extract-worker — Embedding Pipeline

GPU-bound embedding worker for the Hi-RAG ingestion pipeline. Consumes text artifacts from NATS (transcripts from ffmpeg-whisper, page bodies from pdf-ingest, etc.), generates embeddings via TensorZero, and writes to Qdrant (vectors), Meilisearch (full-text), and Neo4j (graph).

> **Developer-facing CLAUDE.md** is in this directory with the TensorZero embedding contract (the easy way to mis-call the endpoint), pipeline placement diagram, and CHIT integration notes.

## Quick reference

- **Port**: `:8083` (internal Docker network only; subscribes NATS, no HTTP API surface for client traffic)
- **Health**: `GET /healthz` → `{"status": "ok"}`
- **Team**: Data (`pmoves/configs/agent-teams.yaml`)
- **Dependencies**: TensorZero (`:3030`), Qdrant (`:6333`), Meilisearch (`:7700`), Neo4j (`:7474`), NATS (`:4222`)
- **CHIT integration**: Partial (target: Full; per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`)

## NATS subjects

- Subscribes: `ingest.text.ready.v1` (from upstream extractors)
- Publishes: `ingest.embed.persisted.v1` (downstream — Hi-RAG can warm caches)

## Environment

- `TENSORZERO_BASE_URL` → `http://tensorzero:3030`
- `EMBEDDING_MODEL` → `qwen3_embedding_4b_local` (default; dim 2560)
- `QDRANT_URL`, `MEILI_URL`, `NEO4J_URI` — backend connections
- `NATS_URL` — `nats://nats:pmoves@nats:4222`

## Bringup

```bash
make -C pmoves up-extract-worker   # or via bringup-layered for full mesh
```

## Cross-references

- CLAUDE.md (this directory) — developer-facing notes including the TensorZero embedding endpoint gotcha.
- `pmoves/services/hi-rag-gateway-v2/` — query-side consumer.
- `.claude/CATALOG.md` — service catalog entry.
- `pmoves/docs/audit/2026-05-15-service-doc-audit.md` — flagged this README as P1 fix.
