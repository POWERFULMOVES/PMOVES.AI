# hi-rag-gateway-v2 — Service Guide

Status: Implemented (compose)

Overview
- Hybrid RAG with rerankers and Neo4j entity boost.

Compose
- Service: `hi-rag-gateway-v2` (and GPU variant `hi-rag-gateway-v2-gpu`).
- Ports: `8086:8086` (v2), `8087:8086` (GPU variant)
- Profiles: `workers`, `gateway` (plus `gpu` for GPU variant)
- Depends on: `qdrant`, `neo4j`

Environment (selected)
- Core: `QDRANT_URL`, `QDRANT_COLLECTION`, `SENTENCE_MODEL`, `INDEXER_NAMESPACE`, `ALPHA`
- Rerank: `RERANK_ENABLE`, `RERANK_MODEL`, `RERANK_TOPN`, `RERANK_K`, `RERANK_FUSION`
- Search: `USE_MEILI`, `MEILI_URL`, `MEILI_API_KEY`
- Graph: `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GRAPH_BOOST`, `ENTITY_CACHE_TTL`, `ENTITY_CACHE_MAX`, `NEO4J_DICT_REFRESH_SEC`, `NEO4J_DICT_LIMIT`
- Optional: `USE_OLLAMA_EMBED`, `OLLAMA_URL`, `TAILSCALE_ONLY`, `TAILSCALE_CIDRS`
- GPU variant adds: `CHIT_DECODE_*`, `CHIT_PERSIST_DB`, `PG*`

Smoke
```
docker compose up -d qdrant neo4j hi-rag-gateway-v2
docker compose ps hi-rag-gateway-v2
curl -sS http://localhost:8086/ | head -c 200 || true
docker compose logs -n 50 hi-rag-gateway-v2
```

Ops Quicklinks
- Reranker guide: [HI_RAG_RERANKER](../../PMOVES.AI%20PLANS/HI_RAG_RERANKER.md)
- Providers: [HI_RAG_RERANK_PROVIDERS](../../PMOVES.AI%20PLANS/HI_RAG_RERANK_PROVIDERS.md)
