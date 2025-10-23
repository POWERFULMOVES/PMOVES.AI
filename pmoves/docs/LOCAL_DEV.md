# Local Development & Networking
_Last updated: 2025-10-23_

Note: See consolidated index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md for cross-links.

Refer to `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` for the consolidated list of setup scripts, Make targets, and Supabase workflows that pair with the service and port notes below.

## Services and Ports
- qdrant: 6333 (internal name `qdrant`)
- meilisearch: 7700 (internal name `meilisearch`)
- neo4j: 7474/7687 (internal name `neo4j`)
- minio: 9000/9001 (internal name `minio`)
- postgres: 5432 (internal name `postgres`)
- postgrest: 3000 (internal name `postgrest`)
- presign: 8088 -> 8080 (internal name `presign`)
- hi-rag-gateway (v1, CPU): 8089 -> 8086 (internal name `hi-rag-gateway`)
- hi-rag-gateway-gpu (v1, GPU): 8090 -> 8086 (internal name `hi-rag-gateway-gpu`)
- hi-rag-gateway-v2 (CPU): 8086 (internal name `hi-rag-gateway-v2`)
- hi-rag-gateway-v2-gpu (GPU): 8087 -> 8086 (internal name `hi-rag-gateway-v2-gpu`)
- retrieval-eval: 8090 (internal name `retrieval-eval`)
- render-webhook: 8085 (internal name `render-webhook`)
- pdf-ingest: 8092 (internal name `pdf-ingest`)
- publisher-discord: 8094 -> 8092 (internal name `publisher-discord`)
- notebook-sync: 8095 (internal name `notebook-sync`) – polls Open Notebook and ships normalized content into LangExtract + extract-worker.

External bundles (via `make up-external`):
- wger: 8000 (nginx proxy to Django; override host mapping with `WGER_ROOT_URL` when reverse-proxying)
- Firefly III: ${FIREFLY_PORT:-8082} (set `FIREFLY_PORT` in `env.shared`; 8082 avoids the Agent Zero API on 8080)
- Open Notebook UI/API: 8503 / 5055 (override with `OPEN_NOTEBOOK_UI_PORT` / `OPEN_NOTEBOOK_API_PORT`)
- Jellyfin: 8096 (media server; run `make jellyfin-folders` to create `pmoves/data/jellyfin/` before first launch)

Integrations compose profiles (local containers + n8n automation):
- `make integrations-up-core` brings up n8n with the integrations-ready configuration.
- `make integrations-up-wger` / `make integrations-up-firefly` add the corresponding Postgres/MariaDB stacks.
- `make integrations-up-all` starts n8n, both integrations, and the optional flows watcher sidecar that auto-imports JSON under
  `pmoves/integrations/**/n8n/flows`.
- `make integrations-import-flows` runs the REST helper script once if you prefer manual imports.
- Stop everything with `make integrations-down` (removes volumes) and tail n8n logs via `make integrations-logs`.

All services are attached to the `pmoves-net` Docker network. Internal URLs should use service names (e.g., `http://qdrant:6333`).

## Environment

Quick start:
- Windows without Make: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`
- With Make: `make env-setup` (runs `python3 -m pmoves.tools.secrets_sync generate` under the hood) to produce `.env.generated` / `env.shared.generated` from `pmoves/chit/secrets_manifest.yaml`, then run `make bootstrap` to capture Supabase CLI endpoints (including Realtime) before `make env-check`. When you populate Supabase values, use the live keys surfaced by `make supa-status` (`sb_publishable_…` / `sb_secret_…`) so Archon, Agent Zero, and other agents load the correct service role credentials.
- No Make? `python3 -m pmoves.tools.onboarding_helper generate` produces the same env files and reports any missing CHIT labels before you bring up containers.
- Configure Crush with `python3 -m pmoves.tools.mini_cli crush setup` so your local Crush CLI session understands PMOVES context paths, providers, and MCP stubs.
- Optional: install `direnv` and copy `pmoves/.envrc.example` to `pmoves/.envrc` for auto‑loading.

### Crush CLI Integration

Crush provides a terminal-native assistant with MCP support. To align it with
PMOVES:

1. Install Crush via your preferred package manager (brew, npm, winget, etc.).
2. Install the Python dependencies needed by the mini CLI (`uv pip install typer[all] PyYAML`).
3. Run `python3 -m pmoves.tools.mini_cli crush setup` to generate `~/.config/crush/crush.json`.
4. Verify with `python3 -m pmoves.tools.mini_cli crush status` and review `CRUSH.md` for usage tips.

The generated config auto-detects API keys from `.env.generated`/`env.shared`,
registers MCP stubs (mini CLI, Docker, n8n), and seeds default context paths so
Crush starts with PMOVES-aware prompts.

See also: `docs/SECRETS.md` for optional secret provider integrations.

Manual notes: `env.shared.generated` now carries the Supabase + Meili secrets consumed by Compose. Keep `env.shared` around for local overrides or non-secret feature flags and include any additions from:
- `env.presign.additions` (MINIO creds and shared secret)
- `env.render_webhook.additions` (webhook shared secret)
- `env.hirag.reranker.additions`, `env.hirag.reranker.providers.additions` (optional reranker config)
- `MEDIA_VIDEO_FRAMES_BUCKET` (optional) to store extracted video frames separately from the source bucket; defaults to the
  incoming media bucket when unset. Use `MEDIA_VIDEO_FRAMES_PREFIX` to customize the object key prefix (defaults to
  `media-video/frames`).
- `OPEN_NOTEBOOK_API_URL` (+ optional `OPEN_NOTEBOOK_API_TOKEN`) to enable the notebook-sync worker (read from `env.shared`). Adjust `NOTEBOOK_SYNC_INTE
RVAL_SECONDS`, `NOTEBOOK_SYNC_DB_PATH`, or override `LANGEXTRACT_URL` / `EXTRACT_WORKER_URL` when targeting external services.

## Remote Access via Cloudflare Tunnel

Use the `cloudflare` Compose profile and helper Make targets to expose a local or self-hosted stack without hand-crafted SSH tunnels.

### 1. Generate connector credentials

1. In Cloudflare Zero Trust → **Access → Tunnels**, click **Add a connector**.
2. Choose **Docker** and copy the generated token (preferred) or download the `cert.pem` credentials bundle for existing accounts. When defining public hostnames, point the origin service at the PMOVES endpoint you plan to surface (e.g., `http://host.docker.internal:8086` for a local gateway or `http://hi-rag-gateway-v2:8086` when the tunnel runs on the same Docker network as the services).

### 2. Wire the environment

- Add the token (or tunnel name) to `pmoves/env.shared`:
  ```env
  CLOUDFLARE_TUNNEL_TOKEN=eyJ...   # token path
  # OR
  CLOUDFLARE_TUNNEL_NAME=pmoves-gateway
  CLOUDFLARE_CREDENTIALS_DIR=./cloudflared
  ```
- For cert-based flows, drop the downloaded `cert.pem` and tunnel JSON into the `pmoves/cloudflared/` directory (or override `CLOUDFLARE_CREDENTIALS_DIR`) so the container can read them.

### 3. Start / stop the tunnel

- `make up-cloudflare` — loads `env.shared`, starts the `cloudflared` connector, and attempts to print the latest public URL.
- `make cloudflare-url` — reprints the most recent `https://…` surfaced in the connector logs.
- `make logs-cloudflare` — follow connector logs (handy while waiting for registration or debugging errors).
- `make down-cloudflare` / `make restart-cloudflare` — stop or bounce the connector without touching the rest of the stack.

### 4. Local vs. self-hosted considerations

- **Local laptops / desktops**: configure the origin service in Cloudflare Zero Trust as `http://host.docker.internal:<port>` so requests reach services running on the host network. Ensure Docker Desktop exposes the relevant ports.
- **VPS / bare metal hosts**: when the tunnel runs alongside PMOVES containers, map hostnames to in-network services (e.g., `http://hi-rag-gateway-v2:8086`, `http://render-webhook:8085`, or `http://postgrest:3000`). No additional reverse proxy is required because `cloudflared` attaches to `pmoves-net`.
- **Firewall rules**: allow outbound TCP 7844 and 443 so `cloudflared` can reach Cloudflare’s edge. No inbound ports are needed, but keep the local firewall open for whichever services the tunnel targets (Supabase REST, Hi‑RAG gateway, etc.).

### 5. Validate connectivity

1. Tail the connector: `make logs-cloudflare` — wait for `Registered tunnel connection` + a public URL.
2. Print the URL directly: `make cloudflare-url`.
3. Hit the exposed service from outside your network:
   ```bash
   curl -i https://<tunnel-host>/healthz
   ```
   Replace `/healthz` with an endpoint that matches the service you exposed (e.g., `/hirag/query`). Capture these commands and responses in the PR evidence log when validating remote access.

`make down-cloudflare` is idempotent, so it is safe to run after validation to ensure the connector shuts down cleanly.

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

### Cloudflare Workers AI (LangExtract)

- Enable the provider by setting `LANGEXTRACT_PROVIDER=cloudflare` and exporting:
  - `CLOUDFLARE_ACCOUNT_ID=<uuid from dash.cloudflare.com>`
  - `CLOUDFLARE_API_TOKEN=<token with Workers AI permissions>`
  - `CLOUDFLARE_LLM_MODEL=@cf/meta/llama-3.1-8b-instruct` (or any catalog slug)
- Optional overrides:
  - `CLOUDFLARE_API_BASE=https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run` (default) — swap to a mock URL during tests.
  - `OPENAI_API_BASE=https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai` for other OpenAI-compatible clients.
- Free plan quota (as of 2025-10-23): 10k text tokens/day and ~100 generations/day for meta Llama 3.1 models. Queue longer batch ingests or throttle concurrency to stay within limits.
- Local dev workflow:
  1. Add the variables to `.env` and `env.shared` (or rely on `make env-setup`).
  2. Run `LANGEXTRACT_PROVIDER=cloudflare uvicorn pmoves.services.langextract.api:app --reload` to exercise the FastAPI endpoints.
  3. Capture smoke evidence with `curl -X POST http://localhost:8084/extract/text ...` once the mock or real Workers AI token is available.
- VPS deployment: sync the same variables into your secret manager (Docker Swarm, Fly.io, Coolify). Document the base URL helper in `.env` so ops teams can rotate tokens without rediscovering the Cloudflare path.

## Start
- `make up` (data + workers, v2 CPU on :8086, v2 GPU on :8087 when available)
- `make up-legacy-both` (v1 CPU on :8089, v1 GPU on :8090 when available)
- Legacy gateway: `make up-legacy`
- Seed demo data (Qdrant/Meili): `make seed-data`
- Agents stack (NATS, Agent Zero, Archon, Mesh Agent, publisher-discord): `make up-agents`
- n8n (Docker): `make up-n8n` (listens on http://localhost:5678)
- Windows prerequisites: `make win-bootstrap` (installs Python, Git, Make, jq via Chocolatey)

### Notebook Sync Worker

- Included with the default `make up` stack once `OPEN_NOTEBOOK_API_URL` is configured.
- Start individually: `docker compose up notebook-sync` (requires the data + workers profile services).
- Health check: `curl http://localhost:8095/healthz`.
- Manual poll: `curl -X POST http://localhost:8095/sync` (returns HTTP 409 while a run is in-flight).
- Interval tuning: `NOTEBOOK_SYNC_INTERVAL_SECONDS` (seconds, defaults to 300).
- Cursor storage: `NOTEBOOK_SYNC_DB_PATH` (default `/data/notebook_sync.db` mounted via the `notebook-sync-data` volume).

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
- Bring up pmoves: `make up` (default `SUPABASE_RUNTIME=cli` skips Compose Postgres/PostgREST)
  - Stop CLI: `make supa-stop`

- Self‑hosted remote:
  - Prefill endpoints: `.env.supa.remote` (committed without secrets)
  - Extract keys from `supa.md` locally: `make supa-extract-remote`
  - Activate remote: `make supa-use-remote` (copies to `.env.local`)
  - Run pmoves: `make up`

- Compose alternative (lite Supabase):
- `SUPABASE_RUNTIME=compose make up` then `make supabase-up`
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
  10. Agent Zero `/healthz` reports the JetStream controller running.
  11. Generated `geometry.cgp.v1` packet posts successfully to `/geometry/event`.
  12. ShapeStore jump + calibration report respond for that packet.
- Successful runs exit with code `0` and print `Smoke tests passed.` Any failure stops the script and surfaces the failing check.

## Health Checks

- Presign: `curl http://localhost:8088/healthz`
- Webhook: `curl http://localhost:8085/healthz`
- Hi‑RAG v2 stats: `curl http://localhost:8087/hirag/admin/stats`
- Retrieval‑Eval UI: `http://localhost:8090`
- PostgREST: `http://localhost:3000`
  - After seeding: try a query with `namespace=pmoves` in `/hirag/query`
- Publisher-Discord: `curl http://localhost:8094/healthz`
  - Make helper: `make health-publisher-discord`
 - Agent Zero: `curl http://localhost:8080/healthz`
   - Make helper: `make health-agent-zero`
- Jellyfin Bridge: `curl http://localhost:8093/healthz`
  - Make helper: `make health-jellyfin-bridge`
- Jellyfin UI: `http://localhost:8096`
  - Run `make jellyfin-folders` before first boot to create the default `Movies/TV/Music/...` directories under `pmoves/data/jellyfin/media`.
  - Set `JELLYFIN_PUBLISHED_URL` in `env.shared` when exposing the server beyond localhost so deep links render correctly.

### Jellyfin Library & Kodi Integration

1. Prepare library folders: `make jellyfin-folders`. Copy media into the resulting structure or mount additional host paths by editing `docker-compose.external.yml` (`./data/jellyfin/media` is bound to `/media` in the container).
2. First-run wizard: add the Movies/TV/Music folders created above and configure metadata providers/time zone.
3. Install the official Kodi Sync Queue plugin from Dashboard → Plugins → Catalog → "Kodi Sync Queue" (stable repo).citeturn1search1 This enables instant library updates for Jellyfin for Kodi clients.
4. On Kodi devices, install the "Jellyfin for Kodi" add-on (Download → Video add-ons → Jellyfin), sign in with the same server URL/API key, and enable automatic sync.citeturn1search1
5. Optional: add Jellyfin's stable plugin repository manually (`https://repo.jellyfin.org/releases/plugin/manifest-stable.json`) if the catalog isn't pre-populated.citeturn1search1

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

- Bring up n8n: `make up-n8n` → UI at `http://localhost:5678`
- Env inside n8n (prewired in compose override):
  - `SUPABASE_REST_URL=http://host.docker.internal:65421/rest/v1` (Supabase CLI)
  - `SUPABASE_SERVICE_ROLE_KEY=<paste service role key>`
  - `AGENT_ZERO_BASE_URL=http://agent-zero:8080`
  - `DISCORD_WEBHOOK_URL` + `DISCORD_WEBHOOK_USERNAME`
- Import flows from `pmoves/n8n/flows/*.json` and keep inactive until secrets are set.
- Activate poller then echo publisher; verify Discord receives an embed.

### Alternative: one‑liner docker run (Windows/Linux)

```sh
docker run --name n8n --rm -it \
  -p 5678:5678 \
  --network pmoves-net \
  -e N8N_PORT=5678 -e N8N_PROTOCOL=http -e N8N_HOST=localhost -e WEBHOOK_URL=http://localhost:5678 \
  -e SUPABASE_REST_URL=http://host.docker.internal:65421/rest/v1 \
  -e SUPABASE_SERVICE_ROLE_KEY="<service_role_key>" \
  -e AGENT_ZERO_BASE_URL=http://agent-zero:8080 \
  -e DISCORD_WEBHOOK_URL="<discord_webhook_url>" \
  -e DISCORD_WEBHOOK_USERNAME="PMOVES Publisher" \
  n8nio/n8n:latest
```

## Avatars & Realtime (full Supabase)

- Bring up full stack: `./scripts/pmoves.ps1 up-fullsupabase` (or `supabase start`)
- Create Storage bucket: `./scripts/pmoves.ps1 init-avatars`
- Open realtime UI: `http://localhost:8090/static/realtime.html` (connect with CLI anon key)
- Upload avatar: use the Upload control; preview and assign to latest `studio_board` row.

## Notes

- A local Postgres + PostgREST are included. `render-webhook` and the other compose workers now honour `SUPA_REST_INTERNAL_URL` (defaults to the Supabase CLI gateway `http://host.docker.internal:65421/rest/v1`). Host-side scripts continue to use `SUPA_REST_URL` (`http://127.0.0.1:65421/rest/v1`). Override both if you point the stack at a remote Supabase instance. After launching the Supabase CLI stack, run `make bootstrap-data` (or `make supabase-bootstrap`) so schema migrations and seeds replay before smoke tests.
- Realtime DNS fallback: if `hi-rag-gateway-v2` finds `SUPABASE_REALTIME_URL` is set but its hostname doesn’t resolve inside the container (e.g., `api.supabase.internal` not shared on the compose network), it now auto-derives a working websocket endpoint from `SUPA_REST_INTERNAL_URL`/`SUPA_REST_URL` (host‑gateway safe). To force an explicit target, set `SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1` in `.env.local`.
- Neo4j seeds: the bundled `neo4j/datasets/person_aliases_seed.csv` + `neo4j/cypher/*.cypher` scripts wire in the CHIT mind-map aliases. Run `make neo4j-bootstrap` after launching `pmoves-neo4j-1`, or rely on `make bootstrap-data` to run it automatically together with Supabase SQL and the Qdrant/Meili demo load.
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
