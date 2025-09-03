# Retrieval Eval Guide (with Rerank Providers)
_Last updated: 2025-08-29_

## Gateway v2
- Endpoint: `POST /hirag/query` (accepts `use_rerank`, `rerank_topn`, `rerank_k`).
- Admin: `/hirag/admin/stats` shows provider/model status.

## Providers
```
RERANK_PROVIDER=flag|qwen|cohere|azure
# flag/bge
RERANK_MODEL=BAAI/bge-reranker-base
# qwen
QWEN_RERANK_MODEL=Qwen/Qwen3-Reranker-4B
# cohere
COHERE_API_KEY=...
COHERE_RERANK_MODEL=rerank-english-v3.0
# azure
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-06-01
```

## Run Sweep
```
export HIRAG_URL=http://localhost:8087
pip install -r pmoves-v5/services/retrieval-eval/requirements-rerank.txt
python pmoves-v5/services/retrieval-eval/eval_rerank.py
```
Outputs table: `Recall@K`, `nDCG@K` for with/without rerank.
