# feat(hirag): v2 gateway with optional reranker + eval sweeps

**Summary**
Introduces **Hi‑RAG Gateway v2** with an optional re‑rank stage. Default model: `BAAI/bge-reranker-base`
via FlagEmbedding. You can toggle per-request (`use_rerank`) or globally via env.

**What’s included**
- `services/hi-rag-gateway-v2/` (FastAPI app with rerank fusion)
- `compose-hirag-v2-snippet.yml` + `.env` additions (`env.hirag.reranker.additions`)
- `services/retrieval-eval/eval_rerank.py` + `requirements-rerank.txt`
- `datasets/queries.jsonl` (starter)
- `docs/HI_RAG_RERANKER.md`

**Why**
Rerankers substantially improve early precision/Recall@K on many domains. This v2 isolates the feature to
avoid downtime and enables side‑by‑side evals before promoting to the main gateway.

**Usage**
```bash
docker compose --profile workers up -d hi-rag-gateway-v2
export HIRAG_URL=http://localhost:8087
pip install -r pmoves-v5/services/retrieval-eval/requirements-rerank.txt
python pmoves-v5/services/retrieval-eval/eval_rerank.py
```

**Env**
```
RERANK_ENABLE=true
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_TOPN=50
RERANK_K=10
```

**Follow‑ups (next PRs)**
- Add provider switch for **Qwen/Qwen3‑Reranker‑4B** (local), and **Cohere/Azure** (cloud) with a single
  `RERANK_PROVIDER` env + auth keys. Maintain eval harness parity across providers.
- Wire CI to run retrieval‑eval sweeps and publish artifacts.

_Last updated: 2025-08-28_
