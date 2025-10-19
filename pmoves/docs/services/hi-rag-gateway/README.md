# hi-rag-gateway — Service Guide

Status: Implemented (compose, legacy) — CPU and GPU variants

Overview
- Original hybrid RAG HTTP gateway.

Compose
- Service: `hi-rag-gateway` (CPU)
- Service: `hi-rag-gateway-gpu` (GPU)
- Ports: CPU `8089:8086`, GPU `8090:8086`
- Profiles: `legacy` (+`gpu` for GPU variant)
- Depends on: `qdrant`, `neo4j`

Environment (selected)
- `QDRANT_URL`, `QDRANT_COLLECTION`, `SENTENCE_MODEL`
- `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `GRAPH_BOOST`, `ENTITY_CACHE_TTL`, `ENTITY_CACHE_MAX`
- `USE_MEILI`, `MEILI_URL`, `MEILI_API_KEY`
- `TAILSCALE_ONLY`, `TAILSCALE_ADMIN_ONLY`, `TAILSCALE_CIDRS`
- Rerank (optional): `RERANK_ENABLE` (default false on CPU; true on GPU), `RERANK_MODEL` (default `BAAI/bge-reranker-base`), `RERANK_TOPN` (50), `RERANK_K` (10)

GPU notes
- The GPU variant installs CUDA Torch wheels and prefers CUDA automatically; falls back to CPU when unavailable.
- Enable reranking on CPU by setting `RERANK_ENABLE=true`; GPU variant enables rerank by default.

Smoke
```
# CPU
docker compose --profile legacy up -d qdrant neo4j hi-rag-gateway
curl -sS http://localhost:8089/hirag/query -H 'content-type: application/json' -d '{"query":"hello","namespace":"pmoves","k":3}' | jq .

# GPU (preferred)
docker compose --profile gpu --profile legacy up -d hi-rag-gateway-gpu
curl -sS http://localhost:8090/hirag/query -H 'content-type: application/json' -d '{"query":"hello","namespace":"pmoves","k":3}' | jq .
```

Notes
- v1 now supports optional reranking via CrossEncoder. v2 remains the preferred path for advanced features and UI.

Related
- v2: [hi-rag-gateway-v2](../hi-rag-gateway-v2/README.md)
