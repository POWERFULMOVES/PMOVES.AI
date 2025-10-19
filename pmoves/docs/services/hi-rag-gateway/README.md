# hi-rag-gateway — Service Guide

Status: Implemented (compose, legacy)

Overview
- Original hybrid RAG HTTP gateway.

Compose
- Service: `hi-rag-gateway`
- Port: `8086:8086`
- Profiles: `legacy`
- Depends on: `qdrant`, `neo4j`

Environment (selected)
- `QDRANT_URL`, `QDRANT_COLLECTION`, `SENTENCE_MODEL`
- `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `GRAPH_BOOST`, `ENTITY_CACHE_TTL`, `ENTITY_CACHE_MAX`
- `USE_MEILI`, `MEILI_URL`, `MEILI_API_KEY`
- `TAILSCALE_ONLY`, `TAILSCALE_ADMIN_ONLY`, `TAILSCALE_CIDRS`

Smoke
```
docker compose --profile legacy up -d qdrant neo4j hi-rag-gateway
docker compose ps hi-rag-gateway
curl -sS http://localhost:8086/ | head -c 200 || true
docker compose logs -n 50 hi-rag-gateway
```

Notes
- Preferred path is v2; see below.

Related
- v2: [hi-rag-gateway-v2](../hi-rag-gateway-v2/README.md)
