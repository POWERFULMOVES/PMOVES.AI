# Meilisearch — Lexical Search

Status: Compose-managed (data plane)

Overview
- Lightweight lexical scoring; combined with vectors in Hi‑RAG v2.

Compose
- Service: `meilisearch`
- Ports: `7700:7700`
- Profile: `data`
- Network: `pmoves-net`

Used by
- `hi-rag-gateway-v2` (if `USE_MEILI=true`)
- `extract-worker` (bulk index)

Env (clients)
- `USE_MEILI=true`
- `MEILI_URL=http://meilisearch:7700`
- `MEILI_API_KEY` (optional bearer)

Make
- `make up` starts meili; v2‑GPU defaults `USE_MEILI=true`.
