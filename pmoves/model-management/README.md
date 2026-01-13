# PMOVES Model Management (Project)

This folder complements the docs starter and provides project commands to set and swap models without editing code.

Profiles and commands
- List available manifests: `make -C pmoves model-profiles`
- Apply a profile (writes into `pmoves/.env.local`):
  - Archon/Hi‑RAG defaults: `make -C pmoves model-apply PROFILE=archon HOST=workstation_5090`
  - Agent Zero defaults: `make -C pmoves model-apply PROFILE=agent-zero HOST=workstation_5090`
- Swap a single model on the fly:
  - `make -C pmoves model-swap SERVICE=hirag NAME=Qwen/Qwen3-Reranker-4B`

Environment keys (now included in `env.shared.example`)
- `TENSORZERO_BASE_URL`, `TENSORZERO_EMBED_MODEL`, `TENSORZERO_API_KEY`
- `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`
- `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_EMBED_MODEL`
- `RERANK_*` (enable/model/topn/k/fusion), `SENTENCE_MODEL`

After changing models, restart affected containers:
- Hi‑RAG v2 (CPU): `make -C pmoves recreate-v2`
- Hi‑RAG v2 (GPU): `make -C pmoves recreate-v2-gpu`
- Agents: `make -C pmoves up-agents`

