# Venice ↔ TensorZero Integration (Project Wiring)

This directory holds the “in-project” wiring so you can pick models and route embedding requests to local Ollama or a remote TensorZero gateway without editing code.

Quick start
- Bring up TensorZero (bundles Ollama sidecar): `make -C pmoves up-tensorzero`
- Apply a profile (writes into `pmoves/.env.local`):
  - Local embedding via Ollama: `make -C pmoves model-apply PROFILE=archon HOST=workstation_5090`
  - Agent Zero LLM for workstation: `make -C pmoves model-apply PROFILE=agent-zero HOST=workstation_5090`
- Pre‑pull common models: `make -C pmoves models-seed-ollama`
- Restart gateways: `make -C pmoves recreate-v2` (and `recreate-v2-gpu` if using the GPU variant)

Environment knobs
- `TENSORZERO_BASE_URL` points at the TensorZero gateway (OpenAI‑compatible path is auto‑appended). Defaults to `http://tensorzero-gateway:3000` when the stack is up.
- `TENSORZERO_EMBED_MODEL` selects the embedding route (e.g., `tensorzero::embedding_model_name::gemma_embed_local`).
- `OLLAMA_URL` and `OLLAMA_EMBED_MODEL` control local embeddings (`embeddinggemma:300m` by default).
- `OPENAI_COMPAT_BASE_URL` can point Agent Zero at a remote OpenAI‑compatible gateway if you don’t want TensorZero locally.

Notes
- The hi‑rag v2 services already read these env vars; switching models is a restart-only change.
- The project docs remain under `pmoves/docs/venice-tensorzero-integration/` for background; this folder is the operator entry point you’ll actually use.

