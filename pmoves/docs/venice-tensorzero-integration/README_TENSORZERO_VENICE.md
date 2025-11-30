# Venice + TensorZero Integration (PMOVES)

1) Copy `tensorzero.toml` and `.env.tensorzero.example` to your repo root.
   - Rename `.env.tensorzero.example` -> `.env.tensorzero` and put real values.

2) Merge `compose.overrides.tensorzero.yml` and `compose.overrides.agents.yml` into your Docker Compose (or pass with `-f`).

3) Ensure Agent Zero and Hi-RAG services pick up the new env_files:
   - `.env.agent-zero.override` (written by models_sync.py)
   - `.env.hirag.override`      (written by models_sync.py)

4) Bring up:
   docker compose -f docker-compose.yml -f compose.overrides.tensorzero.yml -f compose.overrides.agents.yml up -d

5) Point all OpenAI-compatible clients to TensorZero:
   OPENAI_COMPAT_BASE_URL=http://tensorzero:3000
   - Agent Zero and Archon now only backfill `OPENAI_COMPATIBLE_BASE_URL*` values when they are unset. Set any per-surface overrides (LLM, embeddings, TTS, STT) before starting the services if you need split routing—those values will no longer be clobbered during startup.

6) Set Venice key in `.env.tensorzero`:
   VENICE_API_KEY=...

7) (Optional) Expose TensorZero via Cloudflare Tunnel for remote Jetsons/VPS.

Operator entry point
- If you’re working inside this repository, you don’t need to copy files around. Use:
  - `make -C pmoves up-tensorzero` to start the gateway + UI (and Ollama sidecar).
  - `make -C pmoves model-profiles` to list available model profiles.
  - `make -C pmoves model-apply PROFILE=archon HOST=workstation_5090` to write env values into `pmoves/.env.local`.
  - `make -C pmoves models-seed-ollama` to pre-pull recommended local models.
- TensorZero now fans out to multiple OpenAI-compatible providers (Venice, OpenRouter, OpenAI, Together, Cloudflare, etc.), so you can mix local and hosted backends behind a single base URL and keep per-service overrides in place.
- Add Hugging Face Inference Endpoints by defining a provider entry (see sample `tensorzero.toml`) and setting `HUGGINGFACE_API_TOKEN`/`HUGGINGFACE_ENDPOINT_BASE`. This keeps evaluation of in-house fine-tunes, Evo Swarm checkpoints, and published datasets on the same routed fabric as Venice/OpenRouter.
- Project-level notes live at `pmoves/venice-tensorzero-integration/README.md`.

## Local model + dataset automation

- Run `make -C pmoves models-sync PROFILE=agent-zero HOST=workstation_5090` (or `archon`, `media`, etc.) to apply the curated manifests via `pmoves/tools/models/models_sync.py`. Profiles capture provider-specific knobs (Ollama, vLLM, llama.cpp, Jetson builds) so multi-arch deployments get the right context window, decoding, and endpoint wiring.
- Use `make -C pmoves models-seed-ollama` and the hints printed by `models-sync` (`ollama pull ...`, `huggingface_hub snapshot_download ...`) to cache weights locally before the services start. This keeps TensorZero, Agent Zero, and Archon responsive even when offline.
- Authenticate Hugging Face once (`huggingface-cli login`) so `huggingface_hub` downloads for GGUF/Transformers assets succeed. Stored caches cover both inference and future fine-tune checkpoints you publish from CHIT/Evo Swarm workflows.
- Recorded datasets and fine-tune artefacts should be mirrored into Supabase Storage or MinIO and referenced from your Hugging Face space (or private org) so PMOVES automation can reuse them across environments.
