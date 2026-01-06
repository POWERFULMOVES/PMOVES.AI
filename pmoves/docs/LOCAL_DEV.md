# Local Development & Networking
_Last updated: 2025-12-14_

Note: See consolidated index at pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md for cross-links.

Refer to `pmoves/docs/LOCAL_TOOLING_REFERENCE.md` for the consolidated list of setup scripts, Make targets, and Supabase workflows that pair with the service and port notes below. For personal‑first setups, see [Single‑User (Owner) Mode](SECURITY_SINGLE_USER.md) for how the console auto‑authenticates with a boot JWT and avoids login prompts.

- `make first-run` — prompts for missing secrets, launches the Supabase CLI stack, starts core/agent/external services, applies Supabase + Neo4j migrations, seeds the Qdrant/Meili demo corpus, provisions the Supabase boot operator, and executes the 12-step smoke harness so every integration ships with branded defaults. See [FIRST_RUN.md](FIRST_RUN.md) for the full sequence and seeded resources.
- `make supabase-boot-user` — manually reprovision (or rotate) the Supabase operator and refresh `env.shared`/`.env.local` with the latest password + JWT. Use this after changing Supabase domains or when you intentionally rotate credentials.
- Optional provisioning bundle: `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` produces the same env overlays and stages the provisioning artifacts under `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS` before you run the stack locally or on a VPS. Pass `--with-glancer` to include the Glancer compose add-on and record it in `provisioning-manifest.json`; verify the add-on later with `python3 -m pmoves.tools.mini_cli status` (the status check reports whether the Glancer container is staged and healthy when Docker is available).

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
- hi-rag-gateway-v2 (CPU): `${HIRAG_V2_HOST_PORT:-8086}` → 8086 (internal name `hi-rag-gateway-v2`)
- hi-rag-gateway-v2-gpu (GPU): `${HIRAG_V2_GPU_HOST_PORT:-8087}` → 8086 (internal name `hi-rag-gateway-v2-gpu`)
  - Tip: when local tools already bind to 8086/8087 (e.g., legacy uvicorn processes), set `HIRAG_V2_HOST_PORT` / `HIRAG_V2_GPU_HOST_PORT` in `.env.local` (or the shell) before running `make up` to remap the published ports (for example `18086` / `18087`).
- Embedding defaults: the v2 gateways pull embeddings from TensorZero (`http://tensorzero-gateway:3000`) which proxies the bundled Ollama sidecar. Production default is `qwen3-embedding:4b` (`tensorzero::embedding_model_name::qwen3_embedding_4b_local`); for Jetson/low VRAM prefer `qwen3-embedding:0.6b` or `embeddinggemma:300m` (use a separate Qdrant collection; do not mix embedding dims). On hosts where Ollama cannot run, point `TENSORZERO_BASE_URL` at a remote gateway or leave `EMBEDDING_BACKEND` unset so services fall back to sentence-transformers.
- retrieval-eval: 8090 (internal name `retrieval-eval`)
- render-webhook: 8085 (internal name `render-webhook`)
- pdf-ingest: 8092 (internal name `pdf-ingest`)
- publisher-discord: 8094 -> 8092 (internal name `publisher-discord`)
- notebook-sync: 8095 (internal name `notebook-sync`) – polls Open Notebook and ships normalized content into LangExtract + extract-worker.
- channel-monitor: 8097 (internal name `channel-monitor`) – watches YouTube channels and queues new videos for pmoves-yt ingestion.
  - Tune yt-dlp via env: `YT_ARCHIVE_DIR` + `YT_ENABLE_DOWNLOAD_ARCHIVE` manage archive files, `YT_SUBTITLE_LANGS`/`YT_SUBTITLE_AUTO` pull captions, `YT_POSTPROCESSORS_JSON` overrides post-processing (defaults embed metadata + thumbnails).

Optional TensorZero gateway profile (`make -C pmoves up-tensorzero` or `docker compose --profile tensorzero up tensorzero-clickhouse tensorzero-gateway tensorzero-ui pmoves-ollama`):
- tensorzero-clickhouse: 8123 (internal name `tensorzero-clickhouse`)
- tensorzero-gateway: 3030 -> 3000 (internal name `tensorzero-gateway`)
- tensorzero-ui: 4000 (internal name `tensorzero-ui`)
- pmoves-ollama: 11434 (internal name `pmoves-ollama`) — optional; skip and point `TENSORZERO_BASE_URL` at a remote gateway when Ollama runs on another host or you’re deploying to Jetson-class hardware.

### Monitoring & Observability
- Start the monitoring stack (Prometheus + Grafana + Loki/Promtail + Blackbox + cAdvisor):
  - `make -C pmoves up-monitoring`
  - Grafana http://localhost:3002 (admin/admin), Prometheus http://localhost:9090
  - Docs: `pmoves/docs/services/monitoring/README.md`
- Quick status:
  - `make -C pmoves monitoring-status` (Prometheus targets summary)
  - `python pmoves/tools/monitoring_report.py` (targets, recent probe failures, top CPU containers)

Remote inference quick switch:
- To use a remote TensorZero instead of the local one, set `TENSORZERO_BASE_URL=http://<remote>:3000` before `make up` (or place it in `.env.local`).
- hi-rag v2 will automatically send embedding requests to that URL when `EMBEDDING_BACKEND=tensorzero` is set (default in the gateway).
- You can keep the local `pmoves-ollama` running or stop it via `docker stop pmoves-pmoves-ollama-1`; the gateway will prefer the configured backend.

### Tailscale & Tailnet Defaults
- `TAILSCALE_TAGS` (`tag:pmoves-vps,tag:pmoves-lab`) and `TAILSCALE_ADVERTISE_ROUTES` (`172.31.10.0/24,172.31.20.0/24`) live in `env.shared` so each host advertises the same lab subnets when it joins.
- Run `python3 -m pmoves.tools.mini_cli tailscale authkey` after generating a reusable key in Headscale or the Tailnet admin console; the helper hides input, writes `TAILSCALE_AUTHKEY` into `pmoves/env.shared`, and drops a matching secret at `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/tailscale/tailscale_authkey.txt` for remote provisioning. When Tailnet Lock is enabled, the helper calls `tailscale lock sign` by default so the stored key arrives pre-signed; use `--no-sign` if you are on a non-signing workstation.
- Use `pmoves/scripts/tailscale_brand_init.sh` on provisioned hosts. It reads the auth key from env or disk, optionally re-signs it (`TAILSCALE_SIGN_AUTHKEY=auto|true|false`), starts `tailscaled` when the systemd unit exists, runs `tailscale_brand_up.sh`, and writes a sentinel at `$HOME/.config/pmoves/tailnet-initialized` (override with `TAILSCALE_INIT_SENTINEL`). Set `TAILSCALE_FORCE_REAUTH=true` to ignore the sentinel when rotating keys.
- Provide `TAILSCALE_AUTHKEY` (or place a `tailscale/tailscale_authkey.txt` secret in the provisioning bundle) before running the init helper; `tailscale_brand_up.sh` adds `--ssh`, `--accept-routes`, tags, hostname, and optional login server automatically. Set `TAILSCALE_LOGIN_SERVER=https://<headscale-host>` when you operate a self-hosted control plane so the helper targets the correct coordinator.
- `TAILSCALE_ONLY` defaults to `false` for local dev so services stay reachable without a tailnet. Flip it to `true` (and keep `TAILSCALE_CIDRS=100.64.0.0/10`) on remote hosts to require requests to originate from tagged devices.
- `TAILSCALE_ADMIN_ONLY` remains `true` to gate `/hirag/admin/*` and similar endpoints even when tailnet enforcement is relaxed; adjust per host if you need public ingest while keeping admin paths private.

### Supabase runtime modes
- **Supabase CLI stack (`make supa-start`)** — launches the official Supabase Docker bundle (Postgres, auth, storage, Realtime, Studio) managed by the CLI. Requires the `supabase` binary in your `PATH`; monitor with `make supa-status` and shut down via `make supa-stop`.
- **Compose overlay (`make supabase-up`)** — reuses the main PMOVES Postgres container while attaching Gotrue, Realtime, Storage, and Studio through `docker-compose.supabase.yml`.
- Run `make supabase-bootstrap` after either approach to replay `supabase/initdb/*.sql`, `supabase/migrations/*.sql`, and `db/v5_12_grounded_personas.sql` into the CLI Postgres container. This keeps the CLI stack aligned with repo-owned schema changes.
- Use `make supa-use-local` / `make supa-use-remote` to swap `.env.local` presets so services know whether to hit the CLI stack (`http://postgrest:3000`) or a hosted Supabase project (`SUPABASE_URL`, `SUPABASE_KEY`). Refresh `.env.supa.remote` with `supabase db diff` output whenever production schema drifts.
- When you upgrade the Supabase CLI, follow the maintenance checklist in `pmoves/docs/services/supabase/README.md#6-upgrade--maintenance` and re-run `make -C pmoves smoke` afterwards to confirm downstream services still pass the 14-step harness.

External bundles (via `make up-external`):
- wger: 8000 (nginx proxy to Django; override host mapping with `WGER_ROOT_URL` when reverse-proxying)
- Firefly III: ${FIREFLY_PORT:-8082} (set `FIREFLY_PORT` in `env.shared`; 8082 avoids the Agent Zero API on 8080)
- Open Notebook UI/API: 8503 / 5055 (override with `OPEN_NOTEBOOK_UI_PORT` / `OPEN_NOTEBOOK_API_PORT`)
- Jellyfin: 8096 (media server; run `make jellyfin-folders` to create `pmoves/data/jellyfin/` before first launch)

## Web UI Quick Links
| UI | Default URL | Bring-Up Command | Notes |
| --- | --- | --- | --- |
| Supabase Studio | http://127.0.0.1:65433 | `make -C pmoves supa-start` *(CLI-managed)* | Requires the Supabase CLI stack; confirm status with `make -C pmoves supa-status`. |
| Notebook Workbench (Next.js) | http://localhost:4482/notebook-workbench | `npm run dev` in `pmoves/ui` | Lint + env validation via `make -C pmoves notebook-workbench-smoke ARGS="--thread=<uuid>"`. |
| Agent Zero Admin (FastAPI docs) | http://localhost:8080/docs | `make -C pmoves up` | Useful for manual message dispatch debugging; default UI badge probes `/healthz` (override with `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH`). |
| TensorZero Playground | http://localhost:4000 | `make -C pmoves up-tensorzero` | Brings up ClickHouse, gateway/UI, and `pmoves-ollama`. Gateway API at http://localhost:3030; set `TENSORZERO_BASE_URL` to a remote gateway if Ollama runs elsewhere. |
| Firefly Finance | http://localhost:8082 | `make -C pmoves up-external-firefly` | Set `FIREFLY_APP_KEY`/`FIREFLY_ACCESS_TOKEN` in `pmoves/env.shared` before first login. |
| Wger Coach Portal | http://localhost:8000 | `make -C pmoves up-external-wger` | Auto-applies brand defaults; admin credentials live in `pmoves/env.shared`. |
| Jellyfin Media Hub | http://localhost:8096 | `make -C pmoves up-external-jellyfin` | First boot runs schema migrations; mark libraries inside the UI after media folders are populated. |
| Open Notebook UI | http://localhost:8503 | `docker start cataclysm-open-notebook` *(or `make -C pmoves notebook-up`)* | Ensure SurrealDB is reachable (`OPEN_NOTEBOOK_SURREAL_URL`/`OPEN_NOTEBOOK_SURREAL_ADDRESS`) and keep `OPEN_NOTEBOOK_PASSWORD` aligned with `OPEN_NOTEBOOK_API_TOKEN`. |
| n8n Automation | http://localhost:5678 | `make -C pmoves up-n8n` | Imports live under `pmoves/integrations/**/n8n/flows`; authenticate with credentials from `pmoves/env.shared`. |

Integrations compose profiles (local containers + n8n automation):
- `make integrations-up-core` brings up n8n with the integrations-ready configuration.
- `make integrations-up-wger` / `make integrations-up-firefly` add the corresponding Postgres/MariaDB stacks.
- `make integrations-up-all` starts n8n, both integrations, and the optional flows watcher sidecar that auto-imports JSON under
  `pmoves/integrations/**/n8n/flows`.
- `make integrations-import-flows` runs the REST helper script once if you prefer manual imports.
- Stop everything with `make integrations-down` (removes volumes) and tail n8n logs via `make integrations-logs`.

All services are attached to the `pmoves-net` Docker network. Internal URLs should use service names (e.g., `http://qdrant:6333`).

### Cloudflare tunnel (optional remote access)

Use the bundled `cloudflared` helper when you need to expose local services to collaborators:

- Populate `pmoves/env.shared` (or `.env.local`) with either `CLOUDFLARE_TUNNEL_TOKEN` **or** the tuple `CLOUDFLARE_TUNNEL_NAME`, `CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_CERT`/`CLOUDFLARE_CRED_FILE`. These map directly to the values Cloudflare provides after `cloudflared tunnel create` or `cloudflared tunnel login`.
- Optional overrides:
  - `CLOUDFLARE_TUNNEL_INGRESS` — comma-separated ingress rules such as `geometry=http://hi-rag-gateway-v2:8086,yt=http://pmoves-yt:8077`.
  - `CLOUDFLARE_TUNNEL_HOSTNAMES` — the hostnames that should be created or updated (e.g., `hi-rag.local.pmoves.ai`).
  - `CLOUDFLARE_TUNNEL_METRICS_PORT` — exported metrics listener (defaults to none).
- Combine hostnames and ingress rules when you need multiple services behind a single tunnel, e.g. `CLOUDFLARE_TUNNEL_HOSTNAMES=hi-rag.local.pmoves.ai,publisher.local.pmoves.ai` with `CLOUDFLARE_TUNNEL_INGRESS=hi-rag=http://hi-rag-gateway-v2:8086,publisher=http://publisher-discord:8092`.
- Start/stop the tunnel with `make up-cloudflare` / `make down-cloudflare`; fetch the active URL via `make cloudflare-url` and tail logs with `make logs-cloudflare`.
- When the tunnel is active the connector runs in the `cloudflare` compose profile; ensure your Supabase or Jellyfin hostnames are routable through the ingress rules you define.

## Environment

Quick start:
- Windows without Make: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`
- With Make: `make env-setup` (runs `python3 -m pmoves.tools.secrets_sync generate` under the hood) to produce `.env.generated` / `env.shared.generated` from `pmoves/chit/secrets_manifest.yaml`, then run `make bootstrap` to capture Supabase CLI endpoints (including Realtime) before `make env-check`. When you populate Supabase values, use the live keys surfaced by `make supa-status` (`sb_publishable_…` / `sb_secret_…`) so Archon, Agent Zero, and other agents load the correct service role credentials.
- UI scripts: every `npm run` command under `pmoves/ui` now shells through `node scripts/with-env.mjs …`, which layers `env.shared`, `env.shared.generated`, `.env.generated`, `.env.local`, and `pmoves/ui/.env.local`. Keep the canonical secrets in `pmoves/env.shared` and machine-specific overrides in `.env.local`; the UI inherits them automatically.

### Console dev helpers
- Start the console on port 3001 (auto-loads env and boot JWT):
  - `make -C pmoves ui-dev-start`
- Stop and view logs:
  - `make -C pmoves ui-dev-stop`
  - `make -C pmoves ui-dev-logs`
- Auto-auth: the console skips /login when `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` is present. Generate/update it with `make -C pmoves supabase-boot-user`, then restart the console.

### Agent UIs (headless MCP with console wrappers)
- Archon page: `http://localhost:3001/dashboard/archon` — Health/Info, prompts editor link, and a button to open the native API.
- Agent Zero page: `http://localhost:3001/dashboard/agent-zero` — Health/Info, MCP connection details, and a button to open the native UI/API.

You can customize the badge probe paths if your forks expose different health endpoints:

- `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`, fallbacks: `/api/health` → `/`).
- `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`, fallbacks: `/api/health` → `/`).

See also: `pmoves/docs/SERVICE_HEALTH_ENDPOINTS.md`.
- Personas page: `http://localhost:3001/dashboard/personas` — Lists personas from `pmoves_core.personas`.

### Full‑stack bring‑up helper

Use the one‑shot bring‑up to start Supabase, core PMOVES services, Agents/APIs/UIs, external stacks, monitoring, and the Console UI, then wait for health and auto‑capture evidence (yt‑dlp docs, Loki /ready, Hi‑RAG stats, etc.). This is handy for smoke‑ready demos:

```
make -C pmoves bringup-with-ui
```

Tuning waits (slow GPU model warm‑up):

```
WAIT_T_LONG=300 make -C pmoves bringup-with-ui
```

Parallelization: readiness checks are sequential for robustness and clear logs. If you’d like a parallel mode (background curls + barrier), we can add it.

### Use published Agent UI images
- You can run Agents from prebuilt images (includes native UIs) instead of local builds:
  - Set/confirm in `pmoves/env.shared`:
    - `AGENT_ZERO_IMAGE=ghcr.io/cataclysm-studios-inc/pmoves-agent-zero:pmoves-latest`
    - `ARCHON_IMAGE=ghcr.io/cataclysm-studios-inc/pmoves-archon:pmoves-latest`
  - Start with images: `make -C pmoves up-agents-published`
- To pin versions, change the tags above (e.g., `:v0.9.6`).
- If you maintain your own registry, point the variables at your GHCR/ECR tags.

### Use your forks (integrations-workspace)
You can build and run Agent Zero and Archon directly from your forks without modifying this repo:

1) Clone your forks into the workspace directory (default `../integrations-workspace` relative to `pmoves/`):
```
make -C pmoves agents-integrations-clone
```
This clones:
- https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git → `$(INTEGRATIONS_WORKSPACE)/PMOVES-Agent-Zero`
- https://github.com/POWERFULMOVES/PMOVES-Archon.git → `$(INTEGRATIONS_WORKSPACE)/PMOVES-Archon`

2) Build and start agents from your forks:
```
make -C pmoves build-agents-integrations
make -C pmoves up-agents-integrations
```

3) Update later:
```
make -C pmoves agents-integrations-pull
make -C pmoves build-agents-integrations
make -C pmoves up-agents-integrations
```

Notes:
- Override the workspace path with `INTEGRATIONS_WORKSPACE=/path/to/integrations-workspace`.
- Ports and env remain the same (Agent Zero on 8080, Archon on 8091); the override compose file only swaps the build contexts.

If your fork’s internal port differs, adjust `AGENT_ZERO_EXTRA_ARGS` / `ARCHON_SERVER_PORT` or update the compose mapping. The console reads `NEXT_PUBLIC_AGENT_ZERO_URL` / `NEXT_PUBLIC_ARCHON_URL`.
- Docker Compose now reads the same set in order: `env.shared.generated` (CHIT secrets) → `env.shared` (branded defaults) → `.env.generated` (local secret bundles) → `.env.local` (per-machine overrides). The root `.env` file is no longer sourced; keep any host-specific tweaks in `.env.local` instead of editing `.env`.
- Supabase CLI remains the default backend for both local laptops and self-hosted VPS installs; `env.shared` ships with the CLI ports/keys, and `make supa-status` → `make env-setup` keeps `.env.local` aligned with the CLI stack unless you explicitly run `make supa-use-remote`.
- No Make? `python3 -m pmoves.tools.onboarding_helper generate` produces the same env files and reports any missing CHIT labels before you bring up containers.
- Configure Crush with `python3 -m pmoves.tools.mini_cli crush setup` so your local Crush CLI session understands PMOVES context paths, providers, and MCP stubs.
  - Optional: install `direnv` and copy `pmoves/.envrc.example` to `pmoves/.envrc` for auto‑loading.
- TensorZero gateway (optional): copy `pmoves/tensorzero/config/tensorzero.toml.example` to `pmoves/tensorzero/config/tensorzero.toml`, then set `TENSORZERO_BASE_URL=http://localhost:3030` (and `TENSORZERO_API_KEY` if required). `make -C pmoves up-tensorzero` now starts ClickHouse, the gateway/UI, and `pmoves-ollama`, so the default `qwen3_embedding_4b_local` embedding route works without manual pulls. If you deploy on hardware that cannot run Ollama (Jetson, remote inference nodes), skip the sidecar and point `TENSORZERO_BASE_URL` at a remote gateway instead. Setting `LANGEXTRACT_PROVIDER=tensorzero` routes LangExtract through the gateway; populate `LANGEXTRACT_REQUEST_ID` / `LANGEXTRACT_FEEDBACK_*` variables to tag observability traces.
  - Advanced toggles: `TENSORZERO_MODEL` overrides the default chat backend, `TENSORZERO_TIMEOUT_SECONDS` adjusts request timeouts, and `TENSORZERO_STATIC_TAGS` (JSON or `key=value,key2=value2`) forwards deployment metadata as `tensorzero::tags`.
  - Observability: the gateway ships with observability disabled, but the `gateway.observability.clickhouse` block already points at the bundled ClickHouse defaults (`http://tensorzero-clickhouse:8123`, user/password/database `tensorzero`). Follow [`pmoves/docs/services/open-notebook/TENSORZERO_OBSERVABILITY_NOTES.md`](services/open-notebook/TENSORZERO_OBSERVABILITY_NOTES.md) to confirm the env vars and flip `observability.enabled` to `true` when you want metrics.

### Model provider registry (Archon)
- Archon persists model API keys and default provider choices inside Supabase so downstream agents pull credentials at runtime. Populate the registry with `uv run python pmoves/scripts/credentials/set_archon_provider.py --provider <slug> --key <api-key> [--service-type llm|embedding] [--make-default]`. Run with `--dry-run` to inspect the payload without storing secrets.
- Provider slugs are lowercase and match Archon’s adapters (`openai`, `anthropic`, `google`, `gemini`, `groq`, `mistral`, `deepseek`, `xai`, `together`, `tensorzero`, `ollama`, etc.). Use `--service-type embedding` when registering embedding-only backends (TensorZero, Voyage, sentence-transformers proxies) so the correct default flips.
- `--make-default` promotes the uploaded credential to the active provider for the chosen service type. Archon, Agent Zero, and Hi‑RAG v2 pull the active `llm` provider for chat/orchestration and the active `embedding` provider for rerank + retrieval tasks within a few seconds thanks to cache invalidation in the new `/api/credentials/provider` endpoint.
- When you point `TENSORZERO_BASE_URL` at a local or remote gateway, register it once via `--provider tensorzero --service-type embedding --make-default` so Archon and Agent Zero rely on TensorZero for embeddings while keeping OpenAI (or any other slug) as the LLM default. To drive LLM traffic through TensorZero’s OpenAI-compatible route, upload the same key with `--service-type llm --make-default` and ensure `OPENAI_COMPATIBLE_BASE_URL[_LLM]` in `pmoves/env.shared` targets the gateway.
- Keys live in the `archon_settings` table; rotate them by rerunning the helper or delete the row via `DELETE /api/credentials/<key>` if you prefer manual cleanup. After updates, rerun `make -C pmoves smoke` (or at minimum `make -C pmoves archon-ui-smoke`) to confirm the new defaults propagate through the stack.

### UI Workspace (Next.js + Supabase Platform Kit)

- Location: `pmoves/ui/` (Next.js App Router + Tailwind). The workspace consumes the same Supabase CLI stack that powers the core services.
- Prerequisites: run `make supa-start` and `make supa-status` so `pmoves/.env.local` is populated with `SUPABASE_URL`, anon key, service role key, REST URL, and realtime URL.
- Env loading: every `npm run` script shells through `node scripts/with-env.mjs …`, layering `pmoves/env.shared`, `env.shared.generated`, `.env.generated`, `.env.local`, and `pmoves/ui/.env.local`. Update those root files (not the UI directory) when pointing the console at a different Supabase project.
- Install dependencies: `cd pmoves/ui && npm install` (or `yarn install`).
- Dev server: `npm run dev` / `yarn dev` (default http://localhost:4482). Because the launcher preloads the root env files, no additional sourcing is required. Pair with `make supa-start` to back the UI against the local Supabase CLI gateway.
- Other scripts: `npm run lint`, `npm run build`, `npm run start`.
- Tests: `npm run test` (unit/component via Jest + Testing Library) and `npm run test:e2e` (Playwright smoke). Run `npx playwright install` once to download the browser engines before exercising the E2E suite.
- Shared helpers: `pmoves/ui/config/index.ts` exposes API + websocket URLs, while `pmoves/ui/lib/supabaseClient.ts` and `pmoves/ui/lib/supabase.ts` return typed Supabase clients (browser/service-role). These helpers throw descriptive errors if the Supabase env vars are missing.
- Notebook Workbench: visit `http://localhost:4482/notebook-workbench` to manage `message_views`, view groups, and snapshots for a Supabase thread. Follow the dedicated guide at [`pmoves/docs/UI_NOTEBOOK_WORKBENCH.md`](UI_NOTEBOOK_WORKBENCH.md) for setup steps and troubleshooting.
- Smoketest: run `make -C pmoves notebook-workbench-smoke ARGS="--thread=<thread_uuid>"` after UI changes to lint the bundle and confirm Supabase connectivity.
- Edge auth proxy: `pmoves/ui/proxy.ts` enforces session checks for all non-public routes using the Supabase auth helper. Update its `PUBLIC_PATHS` set when adding new unauthenticated pages.
- Security expectations: the ingestion dashboard now requires a Supabase-authenticated session. `upload_events` rows are stamped with `owner_id`, and the UI only presigns objects under `namespace/users/<owner-id>/uploads/<uuid>/`. Anonymous callers can no longer generate presigned GETs or mutate upload metadata.
- Upload event instrumentation: the console now logs `[metric] uploadEvents...` entries to the browser console for fetches, deletes, and smoke clears. Run `npm run typecheck` before committing UI changes and `npm run smoke:upload-events` to execute the focused Jest suite that validates the Supabase contract and metric hooks.

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

### Supabase auth redirect & provider setup

The Next.js console under `pmoves/ui` uses Supabase for session management. To enable both
password and social sign-in locally:

1. Copy the new UI variables from `pmoves/.env.example` into your `.env.local` or
   allow `make env-setup` to merge them. Minimum required keys:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_SUPABASE_AUTH_CALLBACK_URL` (defaults to `http://localhost:3000/callback`)
   - Optional flags: `NEXT_PUBLIC_SUPABASE_PASSWORD_AUTH_ENABLED` /
     `NEXT_PUBLIC_SUPABASE_OAUTH_ENABLED` to toggle UI experiences without editing code.
2. In Supabase Studio → **Authentication → URL Configuration**, add the callback URL from the
   variable above to the redirect allow-list (e.g., `http://localhost:3000/callback`).
3. For social providers (GitHub, Google, etc.):
   - Enable the provider in `supabase/config.toml` under `[auth.external.<provider>]` by setting
     `enabled = true`.
   - Supply the OAuth client ID/secret via environment variables (for example,
     `SUPABASE_AUTH_EXTERNAL_GITHUB_SECRET`) or update the config for self-hosted setups.
   - Supabase will surface the sign-in buttons automatically once the config is toggled and the
     feature flag `NEXT_PUBLIC_SUPABASE_OAUTH_ENABLED` remains `true`.
4. Restart the Supabase CLI stack (`make supa-stop && make supa-start`) so config changes apply,
   then run `pnpm install` (or `npm install`) inside `pmoves/ui` before `pnpm dev` to boot the Next
   console on port 3000.

Tip: when testing third-party providers, configure the OAuth app’s redirect URL to match the
Supabase callback path above to avoid provider-side mismatches.

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
- Ollama: set `OLLAMA_URL` and `OLLAMA_EMBED_MODEL` (default `qwen3-embedding:4b`).
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
- `make up` (data + workers, v2 CPU on :${HIRAG_V2_HOST_PORT:-8086}, v2 GPU on :${HIRAG_V2_GPU_HOST_PORT:-8087} when available)
- `make up-legacy-both` (v1 CPU on :8089, v1 GPU on :8090 when available)
- Legacy gateway: `make up-legacy`
- Seed demo data (Qdrant/Meili): `make seed-data`
- Agents stack (NATS, Agent Zero, Archon, Mesh Agent, publisher-discord): `make up-agents`
- n8n (Docker): `make up-n8n` (listens on http://localhost:5678)
- Windows prerequisites: `make win-bootstrap` (installs Python, Git, Make, jq via Chocolatey)

### Notebook Sync Worker

- Included with the default `make up` stack once `OPEN_NOTEBOOK_API_URL` is configured (defaults to `http://localhost:5055`).
- Start individually: `docker compose up notebook-sync` (requires the data + workers profile services).
- Health check: `curl http://localhost:8095/healthz`.
- Manual poll: `curl -X POST http://localhost:8095/sync` (returns HTTP 409 while a run is in-flight).
- Interval tuning: `NOTEBOOK_SYNC_INTERVAL_SECONDS` (seconds, defaults to 300; set to `0` to disable polling).
- Live/offline toggle: `NOTEBOOK_SYNC_MODE` (`live` or `offline`) controls whether the worker processes updates at all.
- Source filter: `NOTEBOOK_SYNC_SOURCES` (comma list of `notebooks`, `notes`, `sources`) limits which resources feed LangExtract.
- Cursor storage: `NOTEBOOK_SYNC_DB_PATH` (default `/data/notebook_sync.db` mounted via the `notebook-sync-data` volume).
- Extract worker routing: set `EMBEDDING_BACKEND=tensorzero` to call the TensorZero gateway for chunk embeddings (uses `TENSORZERO_BASE_URL` + `TENSORZERO_EMBED_MODEL`, default `tensorzero::embedding_model_name::qwen3_embedding_4b_local`, which proxies to Ollama's `qwen3-embedding:4b`). Leave unset for local `sentence-transformers`.

### Mindmap + Open Notebook integration

- Set `MINDMAP_BASE` (defaults to `http://localhost:8086`), `MINDMAP_CONSTELLATION_ID`, and `MINDMAP_NOTEBOOK_ID` in `env.shared`/`.env.local`. `make env-setup` propagates the base and constellation into `docker-compose.open-notebook.yml` so the Notebook container can resolve the gateway; the notebook ID is used by the sync script/targets below.
- After seeding (`make mindmap-seed`), run `python pmoves/scripts/mindmap_query.py --base $MINDMAP_BASE --cid $MINDMAP_CONSTELLATION_ID --limit 25 --offset 0` to preview the enriched payload. The CLI prints a summary (`returned`, `total`, `remaining`, `has_more`) and the JSON contains `media_url` + `notebook` metadata ready for ingestion.
- Launch Notebook (`make notebook-up`) and seed models (`make notebook-seed-models`). When adding a Notebook data source, point it at `${MINDMAP_BASE}/mindmap/${MINDMAP_CONSTELLATION_ID}?limit=50&enrich=true` to surface constellation context inside the UI, or run `make mindmap-notebook-sync ARGS="--dry-run"` (see `pmoves/scripts/mindmap_to_notebook.py`) to push nodes as Notebook sources via the API.
- When you launch `make notebook-up`, the bundled SurrealDB endpoint now defaults to `ws://localhost:8000/rpc`; override `OPEN_NOTEBOOK_SURREAL_URL` / `OPEN_NOTEBOOK_SURREAL_ADDRESS` (legacy aliases: `SURREAL_URL` / `SURREAL_ADDRESS`) in `.env.local` if you target an external Surreal instance. The UI ships with `OPEN_NOTEBOOK_PASSWORD=changeme`—log in with that and update it immediately for your environment. Whatever password you keep here must also be copied into `OPEN_NOTEBOOK_API_TOKEN`, since the REST helpers and agents authenticate with the same bearer secret.
- Hi-RAG search sync: `make hirag-notebook-sync ARGS="--query 'what is pmoves' --k 20 --dry-run"` uses `pmoves/scripts/hirag_search_to_notebook.py` to pull semantic hits from `/hirag/query` and post them into Open Notebook. Configure `HIRAG_NOTEBOOK_ID` (or reuse `MINDMAP_NOTEBOOK_ID`) plus `OPEN_NOTEBOOK_API_TOKEN` first—the script dedupes on URL/title so repeated runs only append novel hits.
- No embedding provider keys? Pass `--no-embed` to the ingestion helpers (or set `--embed` only when keys exist). Otherwise the backend tries to instantiate OpenAI/Groq clients and returns `ValueError("OpenAI API key not found")`.
- Local embeddings: if you prefer staying inside the PMOVES stack, set `OLLAMA_API_BASE=http://ollama:11434` (or your self-hosted endpoint), restart `ollama` via Compose, and rerun `make notebook-seed-models`. The seeder will register `ollama` models so Notebook uses local vectors.
- Scheduling vs on-demand: run `make mindmap-notebook-sync` / `make hirag-notebook-sync` manually whenever you want fresh context, or wire the same commands into cron/n8n once you’re ready for continuous sync. There’s intentionally no default scheduler so operators keep full control.

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
- Hi‑RAG v2 stats: `curl http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/hirag/admin/stats` (or `${HIRAG_V2_HOST_PORT:-8086}` for CPU-only bring-up)
- Mindmap API (Neo4j-backed): `curl http://localhost:8086/mindmap/<constellation_id>?offset=0&limit=50` (after `make mindmap-seed` the demo ID is `8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111`). Responses now include `media_url`, timestamps, Notebook payloads, and pagination metadata (`total`, `returned`, `remaining`, `has_more`).
- Retrieval‑Eval UI: `http://localhost:8090`
- PostgREST: `http://localhost:3010`
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
3. Install the official Kodi Sync Queue plugin from Dashboard → Plugins → Catalog → "Kodi Sync Queue" (stable repo). This enables instant library updates for Jellyfin for Kodi clients.
4. On Kodi devices, install the "Jellyfin for Kodi" add-on (Download → Video add-ons → Jellyfin), sign in with the same server URL/API key, and enable automatic sync.
5. Optional: add Jellyfin's stable plugin repository manually (`https://repo.jellyfin.org/releases/plugin/manifest-stable.json`) if the catalog isn't pre-populated.

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

### Open Notebook Integration

- The bundled Open Notebook container (UI on `http://localhost:8503`, API on `:5055`) requires the API port 5055 to be exposed. PMOVES compose targets already do this; if you self‑run the upstream image, expose `-p 5055:5055`.
- Docs for PMOVES’ fork live at `integrations-workspace/Pmoves-open-notebook/docs/index.md` and include the v1 migration notes, REST docs link, and troubleshooting.
- Env keys: set `OPEN_NOTEBOOK_SURREAL_URL` and/or `OPEN_NOTEBOOK_SURREAL_ADDRESS` so the UI can reach SurrealDB; keep `OPEN_NOTEBOOK_API_TOKEN` in sync with `OPEN_NOTEBOOK_PASSWORD`.

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
### Personas REST fallback (PostgREST)

If the Supabase CLI REST host (65421) does not expose `pmoves_core`, the console personas page can query a PostgREST instance directly using profile headers.

- Start the CLI-bound PostgREST: `docker compose -p pmoves up -d postgrest-cli` (publishes `http://localhost:3011`).
- Set `POSTGREST_URL=http://localhost:3011` in `pmoves/env.shared` and run `make -C pmoves env-setup`.
- Reload `/dashboard/personas`.

Alternatively, run the compose PostgREST on `http://localhost:3010` and set `POSTGREST_URL` accordingly.
## Personas REST access (pmoves_core)
The console now uses the Supabase CLI REST for pmoves_core tables.

- We expose `pmoves_core` and `pmoves_kb` in `supabase/config.toml [api.schemas]`.
- Grants are applied via `pmoves/db/v5_13_pmoves_core_rest_grants.sql`.
- No separate PostgREST is required; leave `POSTGREST_URL` commented in `pmoves/env.shared`.

Quick check:
`curl -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H 'Accept-Profile: pmoves_core' http://127.0.0.1:65421/rest/v1/personas?limit=1`
