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

6) Set Venice key in `.env.tensorzero`:
   VENICE_API_KEY=...

7) (Optional) Expose TensorZero via Cloudflare Tunnel for remote Jetsons/VPS.

Operator entry point
- If you’re working inside this repository, you don’t need to copy files around. Use:
  - `make -C pmoves up-tensorzero` to start the gateway + UI (and Ollama sidecar).
  - `make -C pmoves model-profiles` to list available model profiles.
  - `make -C pmoves model-apply PROFILE=archon HOST=workstation_5090` to write env values into `pmoves/.env.local`.
  - `make -C pmoves models-seed-ollama` to pre-pull recommended local models.
- Project-level notes live at `pmoves/venice-tensorzero-integration/README.md`.
