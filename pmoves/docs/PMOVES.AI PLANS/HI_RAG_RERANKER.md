# Hi‑RAG Reranker (v2) + Eval Sweeps

## Gateway v2
New service `hi-rag-gateway-v2` adds an **optional rerank stage** (default on). Defaults differ by profile:
- CPU profile: `BAAI/bge-reranker-base`
- GPU profile: `Qwen/Qwen3-Reranker-4B`

### Defaults
- Reranking is enabled by default (`RERANK_ENABLE=true`) in v2.
- CPU compose defaults to `BAAI/bge-reranker-base`.
- GPU compose overrides to `Qwen/Qwen3-Reranker-4B` and sets the local model path.

Environment (single authoritative block):
```
# Shared defaults
RERANK_ENABLE=true
RERANK_TOPN=50
RERANK_K=10

# CPU default (compose)
RERANK_MODEL=BAAI/bge-reranker-base

# GPU override (compose for hi-rag-gateway-v2-gpu)
RERANK_MODEL=Qwen/Qwen3-Reranker-4B
RERANK_MODEL_PATH=/models/qwen/Qwen3-Reranker-4B
```
Endpoint unchanged: `POST /hirag/query` accepts `use_rerank`, `rerank_topn`, `rerank_k` overrides.

## Eval Sweep
Run evaluation against v2 with and without rerank:
```
export HIRAG_URL=http://localhost:8086
python services/retrieval-eval/eval_rerank.py
```
Outputs Recall@K and nDCG@K table.

## Compose
Use `compose-hirag-v2-snippet.yml` and add `.env` with `env.hirag.reranker.additions`.
