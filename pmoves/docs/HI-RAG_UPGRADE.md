# Hi‑RAG Hybrid Upgrade

Add/confirm these in your `.env`:

```env
# Hi‑RAG hybrid extras
SENTENCE_MODEL=all-MiniLM-L6-v2
USE_OLLAMA_EMBED=false
OLLAMA_URL=http://ollama:11434
```

Compose service snippet (paste under services):

```yaml
  hi-rag-gateway:
    build: ./services/hi-rag-gateway
    restart: unless-stopped
    env_file: [.env]
    environment:
      - QDRANT_URL=${QDRANT_URL}
      - QDRANT_COLLECTION=${QDRANT_COLLECTION}
      - SENTENCE_MODEL=${SENTENCE_MODEL:-all-MiniLM-L6-v2}
      - USE_OLLAMA_EMBED=${USE_OLLAMA_EMBED:-false}
      - OLLAMA_URL=${OLLAMA_URL:-http://ollama:11434}
      - HIRAG_HTTP_PORT=${HIRAG_HTTP_PORT:-8086}
      - NEO4J_URL=${NEO4J_URL}
      - NEO4J_USER=${NEO4J_USER}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - GRAPH_BOOST=${GRAPH_BOOST:-0.15}
      - ENTITY_CACHE_TTL=${ENTITY_CACHE_TTL:-60}
      - ENTITY_CACHE_MAX=${ENTITY_CACHE_MAX:-1000}
      - USE_MEILI=${USE_MEILI:-false}
      - MEILI_URL=${MEILI_URL:-http://meilisearch:7700}
      - MEILI_API_KEY=${MEILI_MASTER_KEY:-master_key}
      - NEO4J_DICT_REFRESH_SEC=${NEO4J_DICT_REFRESH_SEC:-60}
      - NEO4J_DICT_LIMIT=${NEO4J_DICT_LIMIT:-50000}
      - TAILSCALE_ONLY=${TAILSCALE_ONLY:-true}
      - TAILSCALE_ADMIN_ONLY=${TAILSCALE_ADMIN_ONLY:-true}
      - TAILSCALE_CIDRS=${TAILSCALE_CIDRS:-100.64.0.0/10}
    ports: ["8086:8086"]
    depends_on: [qdrant, neo4j]
```

### Tailnet gating

- `TAILSCALE_ONLY=true` restricts **every** endpoint (REST + WebSocket) to Tailnet source IPs.
- `TAILSCALE_ADMIN_ONLY=true` keeps the public `/hirag/query` and geometry helpers open while still locking admin, ingest, and mutation endpoints to Tailnet clients when `TAILSCALE_ONLY` is `false`.
- Both Hi‑RAG gateways (`hi-rag-gateway` and `hi-rag-gateway-v2`) share the same environment variables and CIDR list.

Example configurations:

```env
# Admin-only Tailnet enforcement
TAILSCALE_ONLY=false
TAILSCALE_ADMIN_ONLY=true

# Full service behind Tailnet (overrides the admin flag)
TAILSCALE_ONLY=true
TAILSCALE_ADMIN_ONLY=true
```

Endpoints:

- POST /hirag/query
- GET  /hirag/admin/stats   (Tailscale‑gated)
- POST /hirag/admin/refresh (Tailscale‑gated)
- POST /hirag/admin/cache/clear (Tailscale‑gated)

