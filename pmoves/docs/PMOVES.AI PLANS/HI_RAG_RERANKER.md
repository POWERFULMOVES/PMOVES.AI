# Hi‑RAG Reranker (v2) + Eval Sweeps

## Gateway v2
New service `hi-rag-gateway-v2` adds an **optional rerank stage** (default on) using `BAAI/bge-reranker-base` via FlagEmbedding.
Environment:
```
RERANK_ENABLE=true
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_TOPN=50
RERANK_K=10
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
