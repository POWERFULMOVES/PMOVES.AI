# Hi‑RAG Reranker Providers

Set `RERANK_PROVIDER` to choose a reranker:
- `flag` (default): FlagEmbedding with `RERANK_MODEL` (default `Qwen/Qwen3-Reranker-4B`)
- `qwen`: Sentence-Transformers `CrossEncoder` with `QWEN_RERANK_MODEL` (e.g., `Qwen/Qwen3-Reranker-4B`)
- `cohere`: Cohere API (`COHERE_API_KEY`, `COHERE_RERANK_MODEL`)
- `azure`: Azure OpenAI chat scoring (`AZURE_OPENAI_*`)
- `tensorzero`: TensorZero function gateway (`TENSORZERO_BASE_URL`, `TENSORZERO_RERANK_FUNCTION`, optional `TENSORZERO_API_KEY`)

> Qwen 4B is GPU‑heavy; ensure adequate VRAM or run with device=CPU (slower).

When `tensorzero` is selected the gateway posts query/doc pairs to `TENSORZERO_RERANK_FUNCTION`. Failures automatically fall back to the local FlagEmbedding flow so smoke tests keep passing.

Per‑request overrides are available via POST `/hirag/query`:
```json
{"query":"...","use_rerank":true,"rerank_topn":50,"rerank_k":10}
```
