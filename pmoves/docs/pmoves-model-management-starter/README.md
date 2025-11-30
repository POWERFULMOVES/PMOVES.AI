# PMOVES Model Management Starter

This starter explains how to pick embedding/rerank models, switch providers at runtime, and bring up Agent Zero and Archon UIs for orchestration.

## Embeddings
- Local (Ollama): set `USE_OLLAMA_EMBED=true`, `OLLAMA_URL=http://pmoves-ollama:11434`, and pick `OLLAMA_EMBED_MODEL=embeddinggemma:300m`.
- Remote (TensorZero): set `EMBEDDING_BACKEND=tensorzero`, `TENSORZERO_BASE_URL=http://<remote>:3000`, and choose `TENSORZERO_EMBED_MODEL` (e.g., `tensorzero::embedding_model_name::gemma_embed_local`).
- Fallback: without providers, hi-rag uses `all-MiniLM-L6-v2` via sentence-transformers.

## Reranking
- Default GPU reranker: `Qwen/Qwen3-Reranker-4B` (batch=1). The gateway pads/loops queries to keep rerank active during smokes.
- To disable rerank: set `RERANK_ENABLE=false` in the gateway env.

## Agent UIs
- Start the agents stack: `make -C pmoves up-agents` (NATS, Agent Zero, Archon, Mesh Agent, publisher-discord).
- Agent Zero UI: http://localhost:8080 (health: `make -C pmoves health-agent-zero`).
- Archon UI/health: http://localhost:8091/healthz (smoke: `make -C pmoves smoke-archon`).
- If NATS JetStream errors appear after image upgrades, rebuild and restart Agent Zero:
  ```bash
  docker compose -p pmoves build agent-zero && docker compose -p pmoves up -d agent-zero
  ```

## Env layering (where to put values)
- Put branded defaults in `pmoves/env.shared`.
- Generated secrets live in `pmoves/env.shared.generated` and `.env.generated`.
- Local overrides go in `pmoves/.env.local` (not committed) and are merged by `make env-setup`.

## Verification checklist
- `make -C pmoves smoke` → core stack checks + geometry ingest.
- `make -C pmoves smoke-gpu` → GPU rerank path.
- `make -C pmoves yt-emit-smoke URL=<youtube_url>` → YouTube ingest/CJP.
- `make -C pmoves web-geometry` → open the geometry console; confirm search returns results.
