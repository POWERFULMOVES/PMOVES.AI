# Hi‑RAG Reranker Providers

Set `RERANK_PROVIDER` to choose a reranker:
- `flag` (default): FlagEmbedding with `RERANK_MODEL` (e.g., `BAAI/bge-reranker-base`)
- `qwen`: Sentence-Transformers `CrossEncoder` with `QWEN_RERANK_MODEL` (e.g., `Qwen/Qwen3-Reranker-4B`)
- `cohere`: Cohere API (`COHERE_API_KEY`, `COHERE_RERANK_MODEL`)
- `azure`: Azure OpenAI chat scoring (`AZURE_OPENAI_*`)

> Qwen 4B is GPU‑heavy; ensure adequate VRAM or run with device=CPU (slower).

Per‑request overrides are available via POST `/hirag/query`:
```json
{"query":"...","use_rerank":true,"rerank_topn":50,"rerank_k":10}
```
