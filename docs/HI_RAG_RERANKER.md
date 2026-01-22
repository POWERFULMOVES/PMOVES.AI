# Hi‑RAG Reranker — Enablement and Smokes

The v2 GPU gateway supports cross‑encoder reranking. Use this page to enable it and validate with smokes.

## Enable
- Set on the GPU gateway container:
  - `RERANK_ENABLE=true`
  - `RERANK_MODEL=Qwen/Qwen3-Reranker-4B` (default in local profile) or another supported model
- Optional provider knobs live alongside model settings; see `pmoves/models/archon.yaml` and `pmoves/env.hirag.reranker.providers.additions`.

## Validate
- Stats should show reranker enabled and the model name:
  - `curl -s http://localhost:8087/hirag/admin/stats | jq '.rerank_enabled, .rerank_model'`
- Strict smoke (requires `used_rerank==true`):
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`

## Notes
- The first run may download a large checkpoint; allow time before running strict smokes.
- If strict smoke fails, check container logs for provider/model errors and verify internet/GPU availability.
