# External Integrations Bring‑Up (Wger, Firefly III, Open Notebook, Jellyfin)

This guide links the official integration repos and explains how to run them alongside PMOVES on the shared `pmoves-net` so n8n flows and services can talk to them directly.

## Repos
- Wger (Health): https://github.com/POWERFULMOVES/Pmoves-Health-wger.git
- Firefly III (Finance): https://github.com/POWERFULMOVES/pmoves-firefly-iii.git
- Open Notebook: https://github.com/POWERFULMOVES/Pmoves-open-notebook.git
- Jellyfin: https://github.com/POWERFULMOVES/PMOVES-jellyfin.git

## Network
Ensure the shared network exists so external stacks can attach:
```bash
docker network create pmoves-net || true
```

## Wger (Health)
The PMOVES compose bundle now wraps the upstream Django container with the official nginx static
proxy recommended by the Wger project, so you no longer need to maintain a separate clone just to
host the UI.citeturn0search0

1) Bring the stack up from the PMOVES workspace:
```bash
DOCKER_CONFIG=$PWD/.docker-nocreds \
  docker compose -p pmoves -f docker-compose.external.yml up -d wger wger-nginx
```
   - This recreates the `pmoves-wger` Django service and the `pmoves-wger-nginx` proxy, sharing
     volumes for `/static` and `/media`.
   - The UI remains available at `http://localhost:8000`, which the proxy forwards to Django.
2) Configure PMOVES -> Wger integration secrets in `pmoves/env.shared`:
```
WGER_BASE_URL=http://wger:8000
WGER_API_TOKEN=<your-token>
```
3) n8n flow: import `pmoves/n8n/flows/wger_sync_to_supabase.json`, activate, and trigger a test run
   to confirm Supabase receives payloads.

## Firefly III (Finance)
1) Clone and run:
```bash
cd ..
git clone https://github.com/POWERFULMOVES/pmoves-firefly-iii.git
cd pmoves-firefly-iii
docker network create pmoves-net || true
docker compose up -d
```
2) Base URL and token
- In `pmoves/env.shared`:
```
FIREFLY_BASE_URL=http://firefly:8080
FIREFLY_ACCESS_TOKEN=<your-access-token>
FIREFLY_PORT=8082
```
 - Host port override: Firefly defaults to host port 8080, which clashes with Agent Zero’s API. `FIREFLY_PORT` (set to `8082` above) keeps the services side-by-side; adjust if 8082 is unavailable on your workstation.
3) n8n flow: import `pmoves/n8n/flows/firefly_sync_to_supabase.json` then activate.

## Open Notebook
1) Clone and run:
```bash
cd ..
git clone https://github.com/POWERFULMOVES/Pmoves-open-notebook.git
cd Pmoves-open-notebook
docker network create pmoves-net || true
docker compose up -d
```
2) In `pmoves/env.shared`:
```
OPEN_NOTEBOOK_API_URL=http://open-notebook:5055
OPEN_NOTEBOOK_API_TOKEN=<token>
OPEN_NOTEBOOK_PASSWORD=<optional-password-if-used>
# Provider keys (only add the ones you have)
OPENAI_API_KEY=<openai>
GROQ_API_KEY=<groq>
ANTHROPIC_API_KEY=<anthropic>
GEMINI_API_KEY=<gemini>
```
3) PMOVES Make target: `make up-open-notebook` (uses a local add‑on) as an alternative.
4) Seed models/defaults once the container is running:
```bash
make -C pmoves notebook-seed-models
curl -s http://localhost:5055/api/models/providers | jq '.available'
```
   - The curl should list your enabled providers (`["openai","groq",...]`). If it is empty, double-check your env exports.
   - For sessions where you keep provider credentials in `testkeys.md`, load them into the environment first:
     ```bash
     set -a
     source testkeys.md
     set +a
     ```

## Jellyfin
1) Clone and run:
```bash
cd ..
git clone https://github.com/POWERFULMOVES/PMOVES-jellyfin.git
cd PMOVES-jellyfin
docker network create pmoves-net || true
docker compose up -d
```
2) Back in the PMOVES workspace:
```bash
make -C pmoves jellyfin-folders
```
   - Creates `pmoves/data/jellyfin/{config,cache,transcode,media/...}` which the compose file bind-mounts to `/config`,
     `/cache`, `/transcodes`, and `/media`. Drop files into the Movies/TV/etc. subfolders or edit the compose file to add
     additional host paths.
3) In `pmoves/env.shared` configure the Jellyfin bridge + publisher:
```
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=<key>
JELLYFIN_USER_ID=<optional>
JELLYFIN_PUBLISHED_URL=http://localhost:8096   # or your tailscale/base URL
```
4) Plugins and clients:
   - Server dashboard → Plugins → Catalog → install **Kodi Sync Queue** (stable repo) so Jellyfin pushes updates to Kodi.citeturn1search1
   - If the catalog is empty, add `https://repo.jellyfin.org/releases/plugin/manifest-stable.json` under Repositories.citeturn1search1
   - On Kodi devices install **Jellyfin for Kodi** from the official add-on store, sign in with the same base URL/API key,
     and enable auto-sync.citeturn1search1

## n8n Public API (import + run)
- API base: `http://localhost:5678/api/v1` with header `X-N8N-API-KEY: $N8N_API_KEY`.
- Import a flow:
```bash
curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H 'content-type: application/json' \
  -d @pmoves/n8n/flows/wger_sync_to_supabase.json \
  http://localhost:5678/api/v1/workflows
```
- Activate via UI (toggle Active). Some builds don’t support activation via API.

## Health checks
- Wger UI: http://localhost:8000 (adjust per repo compose)
- Firefly III UI: http://localhost:8080
- Open Notebook UI: http://localhost:8503 (if using PMOVES add‑on) or repo default
- Jellyfin: http://localhost:8096
