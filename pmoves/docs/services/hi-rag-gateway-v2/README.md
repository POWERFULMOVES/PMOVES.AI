# hi-rag-gateway-v2 — Service Guide

Status: Implemented (compose)

Overview
- Hybrid RAG with rerankers and Neo4j entity boost.

Compose
- Service: `hi-rag-gateway-v2` (and GPU variant `hi-rag-gateway-v2-gpu`).
- Ports: `${HIRAG_V2_HOST_PORT:-8086}:8086` (v2 CPU), `${HIRAG_V2_GPU_HOST_PORT:-8087}:8086` (v2 GPU)
- Profiles: `workers`, `gateway` (plus `gpu` for GPU variant)
- Depends on: `qdrant`, `neo4j`

Environment (selected)
- Core: `QDRANT_URL`, `QDRANT_COLLECTION`, `SENTENCE_MODEL`, `INDEXER_NAMESPACE`, `ALPHA`
- Rerank: `RERANK_ENABLE`, `RERANK_MODEL`, `RERANK_TOPN`, `RERANK_K`, `RERANK_FUSION`
- Search: `USE_MEILI`, `MEILI_URL`, `MEILI_API_KEY`
- Graph: `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GRAPH_BOOST`, `ENTITY_CACHE_TTL`, `ENTITY_CACHE_MAX`, `NEO4J_DICT_REFRESH_SEC`, `NEO4J_DICT_LIMIT`
- Optional: `USE_OLLAMA_EMBED`, `OLLAMA_URL`, `TAILSCALE_ONLY`, `TAILSCALE_CIDRS`
- Host ports: override `HIRAG_V2_HOST_PORT` (CPU, default `8086`) and `HIRAG_V2_GPU_HOST_PORT` (GPU, default `8087`) when local services already occupy those ports.
- GPU variant adds: `CHIT_DECODE_*`, `CHIT_PERSIST_DB`, `PG*`

Realtime
- Fallback: If `SUPABASE_REALTIME_URL` resolves to a host‑only DNS (e.g., `api.supabase.internal`), v2 auto‑derives `ws://host.docker.internal:65421/realtime/v1` using `SUPA_REST_URL`/`SUPA_REST_INTERNAL_URL`.
- Recommended `.env.local` (host):
  - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPA_REST_INTERNAL_URL=http://host.docker.internal:65421/rest/v1`
  - `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`
- Admin stats guard: stats are Tailscale‑admin only unless `SMOKE_ALLOW_ADMIN_STATS=true` (for local smokes).
- Reranker model label (reporting only): `POST /hirag/admin/reranker/model/label {"label":"Qwen/Qwen3-Reranker-4B"}`

Defaults
- Meilisearch lexical: enabled by default for v2‑GPU (compose sets `USE_MEILI=true`). CPU v2 honors `USE_MEILI` from env.
- v2‑GPU reranker default: `RERANK_MODEL=Qwen/Qwen3-Reranker-4B` (overridable with env).
- CUDA compatibility: Blackwell‑class GPUs (e.g., RTX 5090) require PyTorch wheels built with CUDA 12.8+ (`cu128`). The GPU compose target now defaults to `TORCH_CUDA_VERSION=cu128` and installs `torch==2.9.0` with those kernels. Rebuild the image (`docker compose build hi-rag-gateway-v2-gpu`) after pulling these changes so the container picks up the new runtime.

Stable GHCR image (no local build)
- If you prefer the published, prebuilt image (known‑good CUDA + Torch combo), use the override file:
  ```bash
  docker compose -p pmoves -f docker-compose.yml -f docker-compose.gpu-image.yml --profile gpu up -d hi-rag-gateway-v2-gpu
  ```
- Or set `HIRAG_V2_GPU_IMAGE=ghcr.io/cataclysm-studios-inc/hi-rag-gateway-v2-gpu:cu128-py310-stable` in `pmoves/env.shared` and run `make -C pmoves up-gpu-gateways`.
- Embedding pipeline: services now try TensorZero first (`TENSORZERO_BASE_URL`, defaulting to `http://tensorzero-gateway:3000`) using the bundled Ollama-backed `embeddinggemma:latest` / `embeddinggemma:300m` models. Ensure `make up-tensorzero` and `ollama pull embeddinggemma:latest` (requires Ollama ≥ 0.11.10) so the gateway can answer GPU queries without falling back to `sentence-transformers/all-MiniLM-L6-v2`. citeturn0search0turn0search2

Neo4j warm dictionary
- Startup no longer emits `UnknownPropertyKey` warnings when `type` is absent on individual `Entity` nodes—the warm cache now checks `keys(e)` before reading the property and falls back to `UNK`.
- To force refresh after updating nodes: `docker compose --profile workers exec hi-rag-gateway-v2 python -c "from app import refresh_warm_dictionary; refresh_warm_dictionary(); print('ok')"` and repeat for the GPU variant if in use.
- Fresh stacks: run `make bootstrap-data` to apply Supabase SQL, seed Neo4j, and load the Qdrant/Meili demo corpus before popping the smokes.

Smoke
```
docker compose up -d qdrant neo4j hi-rag-gateway-v2
docker compose ps hi-rag-gateway-v2
curl -sS http://localhost:8086/ | head -c 200 || true
docker compose logs -n 50 hi-rag-gateway-v2
```

Make targets
- `make up` — brings up data + v2.
- `make up-gpu-gateways` — ensures v2‑GPU is up (soft‑starts qdrant/neo4j if needed).
- `make recreate-v2` / `make recreate-v2-gpu` — force‑recreate containers (no deps).
- `make smoke` / `make smoke-gpu` / `make smoke-qwen-rerank` — core smokes. `smoke-gpu` now runs the rerank query from inside the GPU container so FlagEmbedding/Qwen models that reject batch sizes >1 are re-run sequentially (expect the first run to download the 4B checkpoint).

Ops Quicklinks
- Reranker guide: [HI_RAG_RERANKER](../../PMOVES.AI%20PLANS/HI_RAG_RERANKER.md)
- Providers: [HI_RAG_RERANK_PROVIDERS](../../PMOVES.AI%20PLANS/HI_RAG_RERANK_PROVIDERS.md)
