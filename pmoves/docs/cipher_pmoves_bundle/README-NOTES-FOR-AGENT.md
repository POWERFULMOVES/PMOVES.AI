# Cipher ↔ PMOVES Bundle (with Notes for Agent)
Contents:
- Dockerfile.cipher – Cipher as MCP HTTP server (port 8765)
- docker-compose.cipher.yml – service on external `pmoves` network
- cipher.yml – embeddings chain (Ollama Qwen3 → HF Qwen3 → Ollama nomic) + pgvector
- pmoves_core_pgvector_1536.sql – base schema (VECTOR(1536))
- pmoves_core_views.sql – views + helpers (NN search + upsert)
- Notes for Agent – contracts & pseudocode

## Build & Run
docker build -f Dockerfile.cipher -t local/cipher-mcp:latest .
docker network create pmoves || true
docker compose -f docker-compose.cipher.yml up -d

## Codex MCP (HTTP)
Add to C:\Users\russe\.codex\config.toml:
[mcpServers.CIPHER_HTTP]
type = "http"
url  = "http://localhost:8765/mcp"

## Env
- HF_API_KEY
- PMOVES_PG_DSN_NET=postgresql://pmoves:pmoves@postgres:5432/pmoves
- EMBEDDING_DIM=1536
- Optional: MEILI_*

## Agent Notes (summary)
- Embed via MCP→Cipher; Cipher resolves Ollama→HF fallbacks.
- Persist messages/memory then upsert embedding with object_type/object_id link.
- Search via pmoves_core.embed_search_l2(query_vec, k, probes).
- One table = one dimension. Keep 1536 throughout, or create a separate 768 table for nomic.
