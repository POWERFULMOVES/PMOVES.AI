# Local Development & Networking

Refer to `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` for the consolidated list of setup scripts, Make targets, and Supabase workflows that pair with the service and port notes below.

## Services and Ports
- qdrant: 6333 (internal name `qdrant`)
- meilisearch: 7700 (internal name `meilisearch`)
- neo4j: 7474/7687 (internal name `neo4j`)
- minio: 9000/9001 (internal name `minio`)
- postgres: 5432 (internal name `postgres`)
- postgrest: 3000 (internal name `postgrest`)
- presign: 8088 -> 8080 (internal name `presign`)
- hi-rag-gateway-v2: 8086 -> 8086 (internal name `hi-rag-gateway-v2`)
- retrieval-eval: 8090 (internal name `retrieval-eval`)
- render-webhook: 8085 (internal name `render-webhook`)
- pdf-ingest: 8092 (internal name `pdf-ingest`)
- publisher-discord: 8094 -> 8092 (internal name `publisher-discord`)

All services are attached to the `pmoves-net` Docker network. Internal URLs should use service names (e.g., `http://qdrant:6333`).

## Environment

Quick start:
- Windows without Make: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`
- With Make: `make env-setup` to interactively fill `.env` from `.env.example`, then `make env-check` to confirm nothing is missing.
- Optional: install `direnv` and copy `pmoves/.envrc.example` to `pmoves/.envrc` for auto‑loading.

See also: `docs/SECRETS.md` for optional secret provider integrations.

Manual notes: Create `.env` (or start with `.env.example`) and include keys from:
- `env.presign.additions` (MINIO creds and shared secret)
- `env.render_webhook.additions` (webhook shared secret)
- `env.hirag.reranker.additions`, `env.hirag.reranker.providers.additions` (optional reranker config)
- `MEDIA_VIDEO_FRAMES_BUCKET` (optional) to store extracted video frames separately from the source bucket; defaults to the
  incoming media bucket when unset. Use `MEDIA_VIDEO_FRAMES_PREFIX` to customize the object key prefix (defaults to
  `media-video/frames`).

## External-Mode (reuse existing infra)
If you already run Neo4j, Meilisearch, Qdrant, or Supabase elsewhere, you can prevent PMOVES from starting local containers:

1. Set flags in `.env.local`:
   ```
   EXTERNAL_NEO4J=true
   EXTERNAL_MEILI=true
   EXTERNAL_QDRANT=true
   EXTERNAL_SUPABASE=true
   ```
2. Ensure the corresponding URLs/keys in `.env.local` point at your instances.
3. Run `make up` (Compose profiles skip local services automatically).

## GPU Enablement
For media/AI components you can enable GPU or VAAPI:
- Install NVIDIA Container Toolkit (or expose `/dev/dri` for Intel/VAAPI).
- Start with: `make up-gpu`
- The overrides in `docker-compose.gpu.yml` add device reservations to `media-video` and `jellyfin-bridge`.
Notes:
- Verify drivers on the host (`nvidia-smi` or `/dev/dri` presence).
- Service logs will indicate whether acceleration was detected.

## Backups & Restore
- **Backup:** `make backup` → `backups/<timestamp>/`
  - Postgres SQL dump, Qdrant snapshot request JSON, MinIO mirror (requires `mc` alias inside minio), Meili dump handle.
- **Restore (outline):**
  1. `docker compose down`
  2. Restore Postgres via `psql < postgres.sql`
  3. Restore Qdrant using the snapshot (import via API or replace snapshot dir)
  4. Mirror MinIO folder back; re-seed Meili from dump file via Meili admin.

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
- Agents stack (NATS, Agent Zero, Archon, Mesh Agent, publisher-discord): `make up-agents`
- n8n (Docker): `make up-n8n` (listens on http://localhost:5678)
- Windows prerequisites: `make win-bootstrap` (installs Python, Git, Make, jq via Chocolatey)

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
  - Install deps first: `make flightcheck-install-deps` (installs `tools/flightcheck/requirements.txt` via uv/pip)
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
  10. Agent Zero `/healthz` reports the JetStream controller running.
  11. Generated `geometry.cgp.v1` packet posts successfully to `/geometry/event`.
  12. ShapeStore jump + calibration report respond for that packet.
- Successful runs exit with code `0` and print `Smoke tests passed.` Any failure stops the script and surfaces the failing check.

## Health Checks

- Presign: `curl http://localhost:8088/healthz`
- Webhook: `curl http://localhost:8085/healthz`
- Hi‑RAG v2 stats: `curl http://localhost:8086/hirag/admin/stats`
- Retrieval‑Eval UI: `http://localhost:8090`
- PostgREST: `http://localhost:3000`
  - After seeding: try a query with `namespace=pmoves` in `/hirag/query`
- Publisher-Discord: `curl http://localhost:8094/healthz`
  - Make helper: `make health-publisher-discord`
 - Agent Zero: `curl http://localhost:8080/healthz`
   - Make helper: `make health-agent-zero`
 - Jellyfin Bridge: `curl http://localhost:8093/healthz`
   - Make helper: `make health-jellyfin-bridge`

## n8n Flows (Quick Import)

- Import: open n8n → Workflows → Import from File → load `pmoves/n8n/flows/approval_poller.json` and `pmoves/n8n/flows/echo_publisher.json`.
- Credentials/env:
  - `SUPABASE_REST_URL` and `SUPABASE_SERVICE_ROLE_KEY` (poller GET/PATCH)
  - `AGENT_ZERO_BASE_URL` and optional `AGENT_ZERO_EVENTS_TOKEN` (poller POST `/events/publish`)
  - `DISCORD_WEBHOOK_URL` and `DISCORD_WEBHOOK_USERNAME` (echo publisher webhook)
- Keep flows inactive until Discord webhook ping succeeds.
- Manual ping:
  - Make: `make discord-ping MSG="PMOVES Discord wiring check"`
  - PowerShell: `pwsh -File pmoves/scripts/discord_ping.ps1 -Message "PMOVES Discord wiring check"`

### Preview a `content.published.v1` embed
- Ensure Agent Zero (`agents` profile) and publisher-discord (`orchestration` profile) are running and NATS is up.
- Make: `make demo-content-published` (uses `pmoves/contracts/samples/content.published.v1.sample.json`)
- Bash script: `./pmoves/tools/publish_content_published.sh`
- PowerShell: `pwsh -File pmoves/tools/publish_content_published.ps1`

### Seed an approved studio_board row (Supabase CLI)
- Make (Bash): `make seed-approval TITLE="Demo" URL="s3://outputs/demo/example.png"`
- PowerShell: `make seed-approval-ps TITLE="Demo" URL="s3://outputs/demo/example.png"`

## n8n (Docker) Quick Start

- Bring up n8n: `make up-n8n` → UI at `http://localhost:5678` (launches `n8n` and the `n8n-runners` sidecar)
- Env inside n8n (prewired in compose override):
  - `SUPABASE_REST_URL=http://host.docker.internal:54321/rest/v1` (Supabase CLI)
  - `SUPABASE_SERVICE_ROLE_KEY=<paste service role key>`
  - `AGENT_ZERO_BASE_URL=http://agent-zero:8080`
  - `DISCORD_WEBHOOK_URL` + `DISCORD_WEBHOOK_USERNAME`
  - `N8N_RUNNERS_AUTH_TOKEN=<shared secret>` (same value powers the sidecar connection; stash in `.env.local` and rotate if leaked)
- Import flows from `pmoves/n8n/flows/*.json` and keep inactive until secrets are set.
- Activate poller then echo publisher; verify Discord receives an embed.

### Alternative: one‑liner docker run (Windows/Linux)

> **Note:** one-off `docker run` commands only support manual executions. For cron triggers, rely on the compose stack so the runners sidecar can attach.

```sh
docker compose --project-name pmoves -f pmoves/docker-compose.n8n.yml up n8n n8n-runners
```

## Avatars & Realtime (full Supabase)

- Bring up full stack: `./scripts/pmoves.ps1 up-fullsupabase` (or `supabase start`)
- Create Storage bucket: `./scripts/pmoves.ps1 init-avatars`
- Open realtime UI: `http://localhost:8090/static/realtime.html` (connect with CLI anon key)
- Upload avatar: use the Upload control; preview and assign to latest `studio_board` row.

## Notes

- A local Postgres + PostgREST are included. `render-webhook` and the other compose workers now honour `SUPA_REST_INTERNAL_URL` (defaults to the compose host `http://postgrest:3000`). Host-side scripts continue to use `SUPA_REST_URL` (`http://postgrest:3000`). Override both if you rely on the Supabase CLI (`http://127.0.0.1:54321/rest/v1` + `http://api.supabase.internal:8000/rest/v1`) or a remote Supabase instance. When the Supabase CLI stack is running, `make up` auto-runs the `supabase-bootstrap` helper so schema migrations and seeds are replayed before smoke tests.
- Neo4j seeds: the bundled `neo4j/datasets/person_aliases_seed.csv` keeps the alias dictionary in sync while `neo4j/cypher/010_chit_geometry_fixture.cypher` and `011_chit_geometry_smoke.cypher` replay the curated CHIT constellation and confirm it spans multiple modalities. Run `make neo4j-bootstrap` (or `scripts/neo4j_bootstrap.sh`) after launching `pmoves-neo4j-1`; `make up` triggers the same helper automatically when the container is online.
- For Cataclysm Provisioning, the stable network name `pmoves-net` allows cross‑stack service discovery.
- Clean up duplicate .env keys: `make env-dedupe` (keeps last occurrence, writes `.env.bak`).

## Python Virtual Environment (optional)

- Windows (PowerShell 7+):
  - `pwsh -NoProfile -ExecutionPolicy Bypass -File pmoves/scripts/create_venv.ps1`
  - Activate: `.\\.venv\\Scripts\\Activate.ps1`
- Linux/macOS:
  - `bash pmoves/scripts/create_venv.sh`
  - Activate: `source .venv/bin/activate`
- Or use Make: `make venv` (auto-selects the right script)

Minimal venv (only tools helpers):
- Windows: `make venv-min`
- Linux/macOS: `make venv-min`

Tip (Windows): If `make` is missing, `make setup` installs GNU Make via Chocolatey when available and then installs Python requirements across services using the preferred package manager.
