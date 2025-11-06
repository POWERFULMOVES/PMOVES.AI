# Venice + TensorZero Integration

This guide shows how to use PMOVES with a local or remote TensorZero gateway and the bundled Ollama sidecar. It also covers switching providers for embeddings and wiring retrieval to preferred models.

## Quickstart
- Launch the stack: `make -C pmoves up-tensorzero`
  - Starts ClickHouse, TensorZero gateway (port 3030), TensorZero UI (port 4000), and Ollama sidecar (port 11434).
  - Visit http://localhost:4000 for the UI.

## Using remote inference
- Set `TENSORZERO_BASE_URL=http://<remote>:3000` to send embedding requests to a remote gateway.
- Optional: stop the local sidecar if not needed: `docker stop pmoves-pmoves-ollama-1`.

## hi-rag gateway settings
- TensorZero backend (default):
  - `EMBEDDING_BACKEND=tensorzero`
  - `TENSORZERO_BASE_URL=http://tensorzero-gateway:3000`
  - `TENSORZERO_EMBED_MODEL=tensorzero::embedding_model_name::gemma_embed_local`
- Ollama backend:
  - `USE_OLLAMA_EMBED=true`
  - `OLLAMA_URL=http://pmoves-ollama:11434`
  - `OLLAMA_EMBED_MODEL=embeddinggemma:300m`
- Fallback: if neither provider is reachable, hi-rag uses `SentenceTransformer` (`all-MiniLM-L6-v2`).

## Model selection tips
- Start with `embeddinggemma:300m` for speed; swap to larger variants as needed.
- For reranking, Qwen/Qwen3-Reranker-4B is pre-configured in the GPU gateway. The first run downloads the model (~2 minutes), later runs are fast.

## Troubleshooting
- If the UI shows “Route not found: POST /v1/embeddings”, ensure the gateway is on 3000 and `TENSORZERO_BASE_URL` matches.
- If Ollama cannot run on the host (e.g., Jetson), keep TensorZero remote and do not start the local sidecar; the gateway still works.

## Operator UIs (PMOVES UI, Agent Zero, Archon)

Bring these up to operate and verify the stack end-to-end:

1) PMOVES Operator Console (Next.js)
- Ensure the Supabase CLI stack is running and the boot operator exists:
  ```bash
  make -C pmoves supa-start
  make -C pmoves supabase-boot-user   # idempotent; updates env.shared/.env.local
  ```
- Start the UI dev server:
  ```bash
  cd pmoves/ui
  npm install
  npm run dev
  # open http://localhost:3000
  ```
- The console auto‑authenticates using `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` written by `make supabase-boot-user`. To sign in manually, copy `SUPABASE_BOOT_USER_EMAIL` and `SUPABASE_BOOT_USER_PASSWORD` from `pmoves/.env.local` or `pmoves/env.shared`.
- The landing page includes Quick Links to common dashboards (Agent Zero, Archon health, Geometry, TensorZero, Jellyfin, Open Notebook, Supabase Studio). Override any link with `NEXT_PUBLIC_*` vars (see pmoves/ui/README.md).

2) Agent Zero UI
- Start the agents profile:
  ```bash
  make -C pmoves up-agents
  # Agent Zero UI: http://localhost:8080
  # Health: curl -sf http://localhost:8080/healthz | jq
  ```

3) Archon
- Runs with the agents profile as well:
  ```bash
  make -C pmoves up-agents
  # Health: http://localhost:8091/healthz
  make -C pmoves smoke-archon
  ```

Notes
- If NATS JetStream errors appear after upgrades, rebuild Agent Zero and restart: `docker compose -p pmoves build agent-zero && docker compose -p pmoves up -d agent-zero`.
- Keep `SUPABASE_SERVICE_ROLE_KEY` current in `pmoves/env.shared` so Archon can read/write its prompt tables.
