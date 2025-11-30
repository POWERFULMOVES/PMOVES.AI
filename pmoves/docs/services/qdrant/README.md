# Qdrant — Vector DB

Status: Compose-managed (data plane)

Overview
- Vector database backing similarity search for Hi‑RAG (v1/v2) and extract/ingest jobs.

Compose
- Service: `qdrant`
- Ports: `6333:6333`
- Profile: `data`
- Network: `pmoves-net`

Used by
- `hi-rag-gateway` and `hi-rag-gateway-v2` (vector search and collection (re)create)
- `extract-worker`, `pdf-ingest`, `pmoves-yt` (chunk upserts)

Environment (typical in clients)
- `QDRANT_URL` (e.g., `http://qdrant:6333`)
- `QDRANT_COLLECTION` (e.g., `pmoves_chunks`)

Make
- `make up` starts qdrant with the stack.
- `make smoke` validates vector lookups via v2.
