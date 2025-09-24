# Local Development & Networking

## Services and Ports
- qdrant: 6333 (internal name `qdrant`)
- meilisearch: 7700 (internal name `meilisearch`)
- neo4j: 7474/7687 (internal name `neo4j`)
- minio: 9000/9001 (internal name `minio`)
- postgres: 5432 (internal name `postgres`)
- postgrest: 3000 (internal name `postgrest`)
- presign: 8088 -> 8080 (internal name `presign`)
- hi-rag-gateway-v2: 8087 -> 8086 (internal name `hi-rag-gateway-v2`)
- retrieval-eval: 8090 (internal name `retrieval-eval`)
- render-webhook: 8085 (internal name `render-webhook`)

All services are attached to the `pmoves-net` Docker network. Internal URLs should use service names (e.g., `http://qdrant:6333`).

## Environment
Create `.env` (or start with `.env.example`) and include keys from:
- `env.presign.additions` (MINIO creds and shared secret)
- `env.render_webhook.additions` (webhook shared secret)
- `env.hirag.reranker.additions`, `env.hirag.reranker.providers.additions` (optional reranker config)
- `MEDIA_VIDEO_FRAMES_BUCKET` (optional) to store extracted video frames separately from the source bucket; defaults to the
  incoming media bucket when unset. Use `MEDIA_VIDEO_FRAMES_PREFIX` to customize the object key prefix (defaults to
  `media-video/frames`).

Defaults baked into compose:
- `MINIO_ENDPOINT` defaults to `minio:9000` for in-network access.
- `FRAME_BUCKET` (optional) directs media-video frame uploads to a specific bucket; falls back to the source bucket when unset.
- `HIRAG_URL` in `retrieval-eval` points to `hi-rag-gateway-v2:8086`.
 - Local PostgREST at `http://postgrest:3000` with a local Postgres database.

Embedding providers (local-first):
- Ollama: set `OLLAMA_URL` and `OLLAMA_EMBED_MODEL` (default nomic-embed-text).
- OpenAI-compatible endpoints (LM Studio, vLLM, NVIDIA NIM): set `OPENAI_COMPAT_BASE_URL` and `OPENAI_COMPAT_API_KEY`.
- Hugging Face Inference: set `HF_API_KEY` and optionally `HF_EMBED_MODEL`.
If none are configured/reachable, the gateway falls back to `SENTENCE_MODEL` locally.

OpenAI-compatible presets:
- OpenRouter: set `OPENAI_API_BASE=https://openrouter.ai/api` and `OPENAI_API_KEY=<token>`.
- Groq: set `OPENAI_API_BASE=https://api.groq.com/openai` and `OPENAI_API_KEY=<token>`.
- LM Studio: set `OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1` and leave API key blank.

## Start
- `make up` (v2 gateway by default)
- Legacy gateway: `make up-legacy`
- Seed demo data (Qdrant/Meili): `make seed-data`

### Events (NATS)

- To publish/receive events locally, start a broker and enable it in env:
  - `make up-nats` (starts `nats` service and writes `YT_NATS_ENABLE=true` + `NATS_URL=nats://nats:4222` to `.env.local`).
  - Restart any services that should emit/subscribe after enabling.
  - If you don’t need events, skip this; services run fine without NATS.

### Supabase: Local CLI vs Self‑Hosted

- Local parity (via Supabase CLI):
  - Install CLI (Windows): `winget install supabase.supabase` (or `npm i -g supabase`)
  - Init once: `make supa-init`
  - Start: `make supa-start`
  - Use local endpoints: `make supa-use-local` then run `make supa-status` and paste keys into `.env.local`
  - Bring up pmoves: `make up` (default `SUPA_PROVIDER=cli` skips Compose Postgres/PostgREST)
  - Stop CLI: `make supa-stop`

- Self‑hosted remote:
  - Prefill endpoints: `.env.supa.remote` (committed without secrets)
  - Extract keys from `supa.md` locally: `make supa-extract-remote`
  - Activate remote: `make supa-use-remote` (copies to `.env.local`)
  - Run pmoves: `make up`

- Compose alternative (lite Supabase):
  - `SUPA_PROVIDER=compose make up` then `make supabase-up`
  - Stop: `make supabase-stop` or `make down`

### Flight Check (recommended)

- Quick preflight (cross-platform): `make flight-check`
- Retro UI (Rich, retro console vibe): `make flight-check-retro`
  - Or run directly: `python tools/flightcheck/retro_flightcheck.py --quick`
  - Installs deps from `tools/flightcheck/requirements.txt` if needed
  - Options: `--theme amber` for amber CRT look, `--beep` for a tiny chiptune on success
  - Full mode adds a Docker services panel (state/health) when compose is up
  - Extra themes: `--theme neon` (blue/purple neon), `--theme galaxy` (deep space blue/purple), `--theme cb` (colorblind-safe)

### Windows/WSL smoke script

- Purpose: fast confidence check for local Docker stacks without requiring GNU Make.
- Location: `scripts/smoke.ps1`.
- Prerequisites:
  - Docker Desktop (or WSL2 backend) with the PMOVES stack running (`make up` or `./scripts/pmoves.ps1 up`).
  - PostgREST + presign + render-webhook endpoints exposed to `localhost` (default compose config).
- Run it from an elevated PowerShell or WSL session:
  - Windows PowerShell 7+: `pwsh -NoProfile -ExecutionPolicy Bypass -File ./scripts/smoke.ps1`
  - WSL (pwsh installed): `pwsh -NoLogo -File ./scripts/smoke.ps1`
- Optional parameters:
  - `-TimeoutSec <int>`: per-check deadline (default `60`). Increase to give containers more time on cold boots.
  - `-RetryDelayMs <int>`: delay between retries (default `1000`).
- What it validates (in order):
  1. Qdrant readiness probe.
  2. Meilisearch health (warning-only).
  3. Neo4j browser availability (warning-only).
  4. Presign service `/healthz`.
  5. Render-webhook `/healthz`.
  6. PostgREST root endpoint.
  7. Authenticated render-webhook insert (uses `RENDER_WEBHOOK_SHARED_SECRET` or `change_me`).
  8. `studio_board` latest row returned via PostgREST.
  9. Hi-RAG v2 query returns hits.
- Successful runs exit with code `0` and print `Smoke tests passed.` Any failure stops the script and surfaces the failing check.

## Health Checks

- Presign: `curl http://localhost:8088/healthz`
- Webhook: `curl http://localhost:8085/healthz`
- Hi‑RAG v2 stats: `curl http://localhost:8087/hirag/admin/stats`
- Retrieval‑Eval UI: `http://localhost:8090`
- PostgREST: `http://localhost:3000`
  - After seeding: try a query with `namespace=pmoves` in `/hirag/query`

## Avatars & Realtime (full Supabase)

- Bring up full stack: `./scripts/pmoves.ps1 up-fullsupabase` (or `supabase start`)
- Create Storage bucket: `./scripts/pmoves.ps1 init-avatars`
- Open realtime UI: `http://localhost:8090/static/realtime.html` (connect with CLI anon key)
- Upload avatar: use the Upload control; preview and assign to latest `studio_board` row.

## Notes

- A local Postgres + PostgREST are included. `render-webhook` points to `http://postgrest:3000` by default; override `SUPA_REST_URL` in `.env` to target your self‑hosted instance.
- For Cataclysm Provisioning, the stable network name `pmoves-net` allows cross‑stack service discovery.
- Clean up duplicate .env keys: `make env-dedupe` (keeps last occurrence, writes `.env.bak`).
