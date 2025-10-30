# Smoke Tests
Note: Related cross-links in pmoves/docs/PMOVES.AI PLANS/README_DOCS_INDEX.md.

This guide covers preflight wiring, starting the core stack, and running the local smoke tests. Use it as a quick readiness checklist before deeper testing.

## Prerequisites
- Docker Desktop (Compose v2 available via `docker compose`)
- PowerShell 7+ on Windows, or Bash/Zsh on macOS/Linux
- Optional: `jq` (required for `make smoke`; PowerShell script does not require it)

## 1) Environment Wiring
1. Create `.env` from the sample and append service snippets:
   - Windows (PowerShell):
     - `Copy-Item .env.example .env`
     - `Get-Content env.presign.additions, env.render_webhook.additions | Add-Content .env`
     - Optional rerank config: `Get-Content env.hirag.reranker.additions, env.hirag.reranker.providers.additions | Add-Content .env`
   - macOS/Linux (Bash):
     - `cp .env.example .env`
     - `cat env.presign.additions env.render_webhook.additions >> .env`
     - Optional: `cat env.hirag.reranker.additions env.hirag.reranker.providers.additions >> .env`
2. Start the Supabase CLI stack **before** running bootstrap or compose:
   - `supabase start --network-id pmoves-net` (or `make supa-start` once `supabase/config.toml` exists)
   - This keeps PostgREST + Realtime available so `make bootstrap` can pull fresh anon/service keys and websocket endpoints into `.env.local`.
3. Set shared secrets (change these):
   - `PRESIGN_SHARED_SECRET`
   - `RENDER_WEBHOOK_SHARED_SECRET`
   - Supabase REST endpoints:
     - `SUPA_REST_URL=http://127.0.0.1:54321/rest/v1` (host-side smoke harness + curl snippets)
     - `SUPA_REST_INTERNAL_URL=http://api.supabase.internal:8000/rest/v1` (compose services targeting the Supabase CLI stack)
   - After the CLI stack is running, execute `make bootstrap-data` to apply Supabase SQL, seed Neo4j, and load the demo Qdrant/Meili corpus before smokes. Re-run components individually with `make supabase-bootstrap`, `make neo4j-bootstrap`, or `make seed-data` if you only need one layer.
4. External integrations: copy tokens into `pmoves/.env.local` so the health/finance automations can run without errors.
   - `WGER_API_TOKEN`, `WGER_BASE_URL=http://cataclysm-wger:8000`
   - `FIREFLY_ACCESS_TOKEN`, `FIREFLY_BASE_URL=http://cataclysm-firefly:8080`
  - `OPEN_NOTEBOOK_API_TOKEN`, `OPEN_NOTEBOOK_API_URL=http://cataclysm-open-notebook:5055`
   - `JELLYFIN_API_KEY`, `JELLYFIN_URL=http://cataclysm-jellyfin:8096`
- Override ports before `make -C pmoves up-external` if your host is already using `8000`, `8080`, `8096`, or `8503` (for example, `export FIREFLY_PORT=8082` keeps Firefly off Agent Zero’s 8080 binding). See `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md` for per-service bring-up notes.
5. Buckets: ensure MinIO has buckets you plan to use (defaults: `assets`, `outputs`). You can create buckets via the MinIO Console at `http://localhost:9001` if needed.

## 2) Preflight (Recommended)
- Cross‑platform: `make flight-check` (checks Docker, Supabase CLI + Realtime websocket, external integration env, and geometry migrations)
- Windows direct script: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1`

This checks tool availability, common ports, `.env` keys vs `.env.example`, and validates `contracts/topics.json`.

Optional secret bundle:
- `make chit-encode-secrets` — snapshot `env.shared` into `pmoves/data/chit/env.cgp.json` using the CHIT CGP v0.1 format. Confirm round-trip with `make chit-decode-secrets ARGS="--out /tmp/env.from.chit"`. This ensures the encoder/decoder pair remain compatible with the docs in `pmoves/docs/PMOVESCHIT/`.

## 3) Start Core Stack
- Start data + workers profile (v2 gateway) after the Supabase CLI stack is online:
  - `make up`
- Wait ~15–30s for services to become ready. If you see `service missing` errors (Neo4j, Realtime, etc.), confirm the CLI stack is running and that `make up-external` completed successfully for Wger/Firefly/Open Notebook/Jellyfin.

Useful health checks:
- Presign: `curl http://localhost:8088/healthz`
- Render Webhook: `curl http://localhost:8085/healthz`
- PostgREST: `curl http://localhost:3010`
- Hi‑RAG v2 stats: `curl http://localhost:8087/hirag/admin/stats`
- Discord Publisher: `curl http://localhost:8092/healthz`

### Optional GPU smoke
- Start with `make up-gpu`, then re-run health checks.
- Media/video services should log detection of GPU/VAAPI where available.

### Discord Publisher (content.published.v1)

Verify Discord wiring by emitting a `content.published.v1` event after the stack is up:

```bash
python - <<'PY'
import asyncio, json, os
from nats.aio.client import Client as NATS

async def main():
    nc = NATS()
    await nc.connect(os.getenv("NATS_URL", "nats://localhost:4222"))
    await nc.publish(
        "content.published.v1",
        json.dumps(
            {
                "topic": "content.published.v1",
                "payload": {
                    "title": "Smoke Story",
                    "namespace": "smoke-test",
                    "published_path": "smoke/story.md",
                    "public_url": "https://example.org/smoke-story",
                    "tags": ["demo", "smoke"],
                    "cover_art": {
                        "thumbnails": [
                            {"url": "https://placehold.co/640x360.png", "width": 640, "height": 360}
                        ]
                    },
                },
            }
        ).encode("utf-8"),
    )
    await nc.flush()
    await nc.drain()

asyncio.run(main())
PY
```

Expected: the Discord channel receives a rich embed with the Smoke Story title, namespace, published path, thumbnail, and tags.

- If the payload includes `duration`, the embed shows it as `H:MM:SS` (e.g., `0:05:32`).
- A `thumbnail_url` on the payload or its `meta` block overrides auto-selected cover art thumbnails.
- Jellyfin items emit deep links that append `&startTime=<seconds>` when timestamps (`start_time`, `start`, `t`) are present.
- Tags are quoted ( `` `tag` `` ) and capped at the first twelve entries so Discord renders them cleanly.
- When a summary is present alongside other description content, the remainder appears in a `Summary` field (truncated to Discord's limits) so operators can confirm spillover handling.

Remove `public_url` from the payload if you want to confirm the local-path fallback formatting.

## 4) Seed Demo Data (Optional but helpful)
- `make seed-data` (loads small sample docs into Qdrant/Meilisearch; already invoked by `make bootstrap-data`)
- Alternatively: `make load-jsonl FILE=$(pwd)/datasets/queries_demo.jsonl`

## 5) Run Smoke Tests

### 5a) Core Stack
Choose one:
- macOS/Linux: `make smoke` (requires `jq`)
- Windows (no `jq` required): `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1`

Checks (12):
1. Qdrant ready (`6333`)
2. Meilisearch health (`7700`, warning only)
3. Neo4j UI reachable (`7474`, warning only)
4. Presign health (`8088`)
5. Render Webhook health (`8085`)
6. PostgREST reachable (`3000`)
7. Insert a demo row via Render Webhook
8. Verify a `studio_board` row exists via PostgREST
9. Run a Hi-RAG v2 query (`8087`)
10. Agent Zero `/healthz` reports JetStream controller running
11. POST a generated `geometry.cgp.v1` packet to `/geometry/event`
12. Confirm ShapeStore locator + calibration via `/shape/point/{id}/jump` + `/geometry/calibration/report`

### UI Dropzone smoke

The Dropzone UI rides on the Supabase presign + render webhook path. Once the core stack is live:

1. `cd pmoves/ui && pnpm install` (or `npm install`) then run `pnpm dev`.
2. Open `http://localhost:3010/dashboard/ingest` and upload a small test file to the default bucket.
3. Watch Supabase for:
   - `upload_events` row progressing from `preparing → uploading → persisting → complete`.
   - `studio_board` insert with `meta.presigned_get` populated from the render webhook proxy.
   - Matching `videos` and `transcripts` rows keyed by the Dropzone `upload_id`.
4. Follow the “Open asset” link in the Recent uploads table to verify the MinIO-signed URL streams the object.
5. When smoke-complete, archive or delete the object from MinIO to keep the bucket tidy.

### 5b) Workflow Automations
Prereqs: Supabase CLI stack running (`supabase start --network-id pmoves-net`), `make bootstrap` secrets populated, `make up`, external services (`make -C pmoves up-external`), and `make up-n8n`.
1. Import/activate domain flows (shipped in repo):
   - `pmoves/n8n/flows/health_weekly_to_cgp.webhook.json`
   - `pmoves/n8n/flows/finance_monthly_to_cgp.webhook.json`
   - `pmoves/n8n/flows/wger_sync_to_supabase.json`
   - `pmoves/n8n/flows/firefly_sync_to_supabase.json`
2. Trigger health/finance CGP webhooks (IDs shown in n8n after activation):
   ```bash
   curl -X POST http://localhost:5678/webhook/<health-workflow-id>/webhook/health-cgp \
     -H 'content-type: application/json' -d '{}'
   curl -X POST http://localhost:5678/webhook/<finance-workflow-id>/webhook/finance-cgp \
     -H 'content-type: application/json' -d '{}'
   ```
   Expect: `{"ok":true}` from n8n and CGP packets landing in Supabase via hi-rag gateway.
3. Run the sync helpers directly when testing credentials:
   - `make -C pmoves demo-health-cgp` (requires `WGER_API_TOKEN`)
   - `make -C pmoves demo-finance-cgp` (requires `FIREFLY_ACCESS_TOKEN`)
   Watch Supabase tables (`health_workouts`, `health_weekly_summaries`, `finance_transactions`, `finance_monthly_summaries`) and MinIO asset paths for inserts.
4. Notebook sync smoke: `make -C pmoves up-open-notebook` (if using the local add-on) and ensure `OPEN_NOTEBOOK_API_*` envs resolve. Run `make -C pmoves notebook-seed-models` once `env.shared` includes your token + provider keys so `/api/models/providers` reports the enabled backends. `docker logs pmoves-notebook-sync-1` should show successful Supabase writes.

### 5c) Firefly Finance API Smoke
- Run `make smoke-firefly` (defaults to `http://localhost:8082`). The helper waits for the nginx front-end to answer and then calls `/api/v1/about` with `FIREFLY_ACCESS_TOKEN` (pulled from your shell or `pmoves/env.shared`). Expect a JSON payload showing the Firefly version and API version; failures usually mean the container could not finish migrations or the access token is missing. Override the host with `FIREFLY_ROOT_URL`.
- Populate demo data (optional but recommended before running the n8n sync):
  ```bash
  make -C pmoves firefly-seed-sample    # uses pmoves/data/firefly/sample_transactions.json
  ```
  Re-run with `DRY_RUN=1 make -C pmoves firefly-seed-sample` to preview API calls without mutating Firefly. After n8n sync completes, confirm the mirrored rows in Supabase:
  ```bash
  curl -sS "$SUPA_REST_URL/finance_transactions?source=eq.firefly" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    | jq 'map({occurred_at, category, amount, description})'
  ```
  Expect both revenue and expense rows for each of the 5-year projection categories (`AI-Enhanced Local Service Business`, `Sustainable Energy AI Consulting`, `Community Token Pre-Order System`, `Creative Content + Token Rewards`).

### 5d) Wger Static Proxy Smoke
- Ensure `make up-external-wger` (or `make up-external`) is running so both `cataclysm-wger` and `cataclysm-wger-nginx`
  containers are online. The nginx sidecar mirrors the upstream production guidance where Django writes the static
  bundle and nginx serves `/static` and `/media` from shared volumes.citeturn0search0
- Run `make smoke-wger` (defaults `WGER_ROOT_URL=http://localhost:8000`). The target:
  1. Performs an HTTP GET to confirm the proxy forwards requests to Gunicorn.
  2. Fetches `/static/images/logos/logo-font.svg` to ensure collectstatic artifacts are mounted correctly.
- The bring-up target now calls `scripts/wger_brand_defaults.sh`, which sets the Django `Site` record, admin email, and seed gym name using the `WGER_BRAND_*` variables. Override those env vars (for example, `WGER_BRAND_GYM_NAME="PMOVES Wellness Studio"`) before running `make up-external-wger` if you need different first-login branding.
- If the static check fails, recreate the containers with
  `docker compose -p pmoves -f docker-compose.external.yml up -d --force-recreate wger` to rerun `collectstatic`. Volume
  permission errors are the next suspect—verify `/home/wger/static` is owned by UID 1000 inside the Django container,
  matching the upstream deployment reference.citeturn0search0

### 5e) Creative Automations
Prereqs: tutorials installed (`pmoves/creator/tutorials/`), Supabase CLI stack running, `make bootstrap` secrets populated, `make up`, external services (`make -C pmoves up-external`), and `make up-n8n`.
1. Import/activate the creative webhook flows:
   - `pmoves/n8n/flows/wan_to_cgp.webhook.json`
   - `pmoves/n8n/flows/qwen_to_cgp.webhook.json`
   - `pmoves/n8n/flows/vibevoice_to_cgp.webhook.json`
2. Trigger WAN Animate after ComfyUI uploads the render:
   ```bash
   curl -X POST http://localhost:5678/webhook/wan-to-cgp \
     -H 'content-type: application/json' \
     -d '{
       "title":"Persona teaser",
       "namespace":"pmoves.art.darkxside",
       "persona":"darkxside",
       "workflow":"wan-animate-2.2",
       "asset_url":"s3://outputs/comfy/wan/darkxside-teaser.mp4",
       "reference_image":"s3://assets/personas/darkxside.png",
       "reference_motion":"s3://assets/reference/teaser-source.mp4",
       "prompt":"neo-noir alleyway reveal",
       "tags":["workflow:wan-animate","medium:video"],
       "duration_sec":12.5,
       "fps":30
     }'
   ```
   Expect: Supabase `studio_board` row (status `submitted` unless auto_approve=true) with creative metadata and a `geometry.cgp.v1` packet posted to hi-rag v2.
3. Trigger Qwen Image Edit+ and VibeVoice runs with analogous payloads (`/webhook/qwen-to-cgp`, `/webhook/vibevoice-to-cgp`). Include `asset_url`, `prompt`/`script`, persona tags, and any reference assets. Confirm MinIO/Supabase paths match the tutorial outputs and that geometry constellations land with `workflow:qwen-image-edit-plus` / `workflow:vibevoice-tts` tags.
4. Geometry UI (`make -C pmoves web-geometry`): filter constellations by namespace/persona to verify the render, edit, and audio clips appear with the correct metadata and jump links.

### 5e) Persona Film End-to-End (next milestone)
Persona film automation combines the creative flows above with Supabase tables (`persona_avatar`, `geometry_cgp_packets`) seeded with WAN outputs and audio narration. With the `persona_avatar` table now available (migration `2025-10-20_persona_avatar.sql`), the remaining work is wiring the UI + automation glue:
1. Chain WAN + VibeVoice requests (steps above) with matching `persona` and `namespace`.
2. Confirm n8n emits the geometry packets and that Supabase audit tables capture the creative assets.
3. Geometry UI avatars animate the resulting constellations (`make -C pmoves web-geometry`) once avatar metadata is present.

## 6) Geometry Bus (CHIT) — Extended Deep Dive

### Mindmap Graph (Neo4j)
1. Seed demo nodes for `/mindmap`: `make mindmap-seed` (requires the `neo4j` service running).
2. Fetch the seeded constellation: `make mindmap-smoke`.
   - Expected: JSON payload with `items` containing the `8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111` constellation points/media.
   - If you see `Neo4j unavailable`, confirm the container is healthy and `NEO4J_PASSWORD` matches the password you supplied when first starting the container.

## 6) Geometry Bus (CHIT) — End-to-end

1. Create minimal CGP payload `cgp.json`:
   ```json
   {
     "type": "geometry.cgp.v1",
     "data": {
       "spec": "chit.cgp.v0.1",
       "super_nodes": [
         { "constellations": [
           { "id": "c.test.1", "summary": "beat-aligned hook",
             "spectrum": [0.05,0.1,0.2,0.3,0.2,0.1,0.03,0.02],
             "points": [ { "id": "p.test.1", "modality": "video", "ref_id": "yt123", "t_start": 12.5, "frame_idx": 300, "proj": 0.8, "conf": 0.9, "text": "chorus line" } ]
           }
         ] }
       ]
     }
   }
   ```

2. Optional signing (if `CHIT_REQUIRE_SIGNATURE=true` in gateway):
   ```bash
   python - << 'PY'
   import json,sys
   from tools.chit_security import sign_cgp
   doc=json.load(open('cgp.json'))
   signed=sign_cgp(doc['data'],'change-me')
   json.dump({'type':'geometry.cgp.v1','data':signed}, open('cgp.signed.json','w'))
   PY
   ```

3. POST event:
   ```bash
   curl -s http://localhost:8086/geometry/event -H 'content-type: application/json' -d @cgp.json
   # or @cgp.signed.json if signing enabled
   ```

4. Jump test:
   ```bash
   curl -s http://localhost:8086/shape/point/p.test.1/jump
   ```

5. Optional decoders (set the matching `CHIT_DECODE_*` env var to `true` and install extras):
   - Learned text decode (requires `transformers`):
     ```bash
     curl -s http://localhost:8086/geometry/decode/text \
       -H 'content-type: application/json' \
       -d '{"mode":"learned","constellation_id":"c.test.1"}'
     ```
   - CLIP image decode (requires `sentence-transformers`, `pillow`; downloads assets on first run):
     ```bash
     curl -s http://localhost:8086/geometry/decode/image \
       -H 'content-type: application/json' \
       -d '{"constellation_id":"c.test.1","images":["https://example.org/sample.jpg"]}'
     ```
     The endpoint ranks provided image URLs against the constellation summary (or supplied `text`).
   - CLAP audio decode (requires `laion-clap`, `torch`, `numpy`):
     ```bash
     curl -s http://localhost:8086/geometry/decode/audio \
       -H 'content-type: application/json' \
       -d '{"constellation_id":"c.test.1","audios":["/path/to/sample.wav"]}'
     ```
     On first invocation the legacy gateway will download the CLAP checkpoint; subsequent calls reuse the cached model.

6. Calibration report:
   ```bash
   curl -s http://localhost:8086/geometry/calibration/report \
     -H 'content-type: application/json' \
     -d @cgp.json
   ```

   Expected: 200s; locator shows `{ "modality":"video","ref_id":"yt123","t":12.5,"frame":300 }`.

7. Mind-map query (requires `make neo4j-bootstrap`):
   ```bash
   python docs/pmoves_chit_all_in_one/pmoves_all_in_one/pmoves_chit_graph_plus_mindmap/scripts/mindmap_query.py \
     --base http://localhost:8087 \
     --cid <constellation_id>
   ```
   Substitute `<constellation_id>` with one of the seeded IDs (e.g., from the CSV). A JSON payload with `items` confirms Neo4j has the CHIT alias graph available.

## 7) Live Geometry UI + WebRTC

1. Start v2 gateways: `make up` (v2 CPU on :8086, v2 GPU on :8087 when available). Open http://localhost:8087/geometry/ (GPU) or http://localhost:8086/geometry/ (CPU)
2. Start v1 gateways if needed: `make up-legacy-both` (v1 CPU on :8089, v1 GPU on :8090)
3. Click Connect (room `public`). Post a CGP (make smoke-geometry) and watch points animate.
4. Open the page in a second browser window; both connect to `public` room. Use Share Shape to send a `shape-hello` on the DataChannel.
5. Click “Send Current CGP” to share the last geometry over the DataChannel; add a passphrase to sign the CGP capsule.
6. Toggle “Encrypt anchors” and set a passphrase to AES‑GCM encrypt constellation anchors client‑side before sending; the receiving gateway can decrypt if `CHIT_DECRYPT_ANCHORS=true`.

## 8) Health/Finance → CGP Demo (New)

Use the mapper helper to turn summary events into CGPs and post them to the gateway.

1. Ensure the v2 gateway is running on `:8086` or set `HIRAG_URL` to `http://localhost:8087` for GPU.
2. Health weekly summary:
   ```bash
   make -C pmoves demo-health-cgp
   ```
   Expected: HTTP 200 from `/geometry/event`. Open the geometry UI and look for constellations `health.adh.*` and `health.load.*`.
3. Finance monthly summary:
   ```bash
   make -C pmoves demo-finance-cgp
   ```
   Expected: HTTP 200 and constellations per category (e.g., `fin.Housing.<YYYY-MM>`). Use jump/labels to inspect spectra.

### 8.1) n8n Webhook Variant (real data)

1. Start n8n: `make -C pmoves up-n8n`
2. Import flows (already in repo):
   - `pmoves/n8n/flows/health_weekly_to_cgp.webhook.json`
   - `pmoves/n8n/flows/finance_monthly_to_cgp.webhook.json`
   Use the n8n UI or Public API (`/api/v1/workflows`) with `X-N8N-API-KEY`.
3. Activate both flows in the UI (toggle Active). Production webhooks register only when the workflow is active.
4. Trigger:
   - Health: `curl -X POST http://localhost:5678/webhook/health-cgp -H 'content-type: application/json' -d '{}'`
   - Finance: `curl -X POST http://localhost:5678/webhook/finance-cgp -H 'content-type: application/json' -d '{}'`
5. Expect: `{"ok":true}` from the flow and `{"ok":true}` from `/geometry/event`. Verify persistence via PostgREST as above.

### Optional: Persist CGPs to Postgres

Enable gateway persistence and verify rows via PostgREST:

1. Set env for `hi-rag-gateway-v2` and recreate:
   ```bash
   export CHIT_PERSIST_DB=true \
     PGHOST=postgrest PGUSER=postgres PGPASSWORD=postgres PGDATABASE=postgres
   make -C pmoves recreate-v2
   ```
2. Re-run the demo mappers (steps above).
3. Verify tables via PostgREST:
   ```bash
   curl -s "http://localhost:3010/constellations?order=created_at.desc&limit=5" | jq '.[].summary'
   curl -s "http://localhost:3010/shape_points?order=created_at.desc&limit=5" | jq '.[].id'
   ```
### Quick DB smoke (Supabase)

### Quick DB smoke (Supabase)
- `make smoke-geometry-db` — verifies the seeded demo constellation is reachable via PostgREST (`constellations`, `shape_points`, and `shape_index`). Ensure `SUPABASE_REST_URL` or `SUPA_REST_URL` is exported; defaults to `http://localhost:3010`.
 
 ## 8) Mesh Handshake (NATS)

1. Start mesh: `make mesh-up` (starts NATS + mesh-agent).
2. In the UI, click “Send Signed CGP → Mesh”. This calls the gateway, which publishes to `mesh.shape.handshake.v1`.
3. The mesh-agent receives the capsule, verifies HMAC if `MESH_PASSPHRASE` is set, and posts it to `/geometry/event` so your UI updates locally.
4. Optional: set `MESH_PASSPHRASE` to enforce signature verification across nodes; use the same passphrase in the UI when signing.

## 9) Import Capsule → DB (Offline Ingest)

1. Use the provided example capsule: `datasets/example_capsule.json`
2. From the UI, click “Load Capsule”, choose the file, set passphrase if signing was used, and click “Import DB”.
3. Expected: UI updates; Supabase tables insert rows (anchors, constellations, shape_points). If Realtime is running, events stream to subscribers.

4. Alternatively, publish via CLI: `make mesh-handshake FILE=cgp.json`.
   - Signaling goes through `/ws/signaling/public`. DataChannel is p2p.


Optional smoke targets:
- `make smoke-presign-put` — end‑to‑end presign PUT and upload
- `make smoke-rerank` — query with `use_rerank=true` (provider optional)
- `make smoke-langextract` — extract chunks from XML via `langextract` and load
- `make smoke-archon` — hit `http://localhost:8091/healthz` and ensure Archon reports `status: "ok"` (requires NATS + Supabase CLI stack)
- `make smoke-hirag-v1` — query v1 gateway (auto-detects 8090→8089)
- `make harvest-consciousness` — scaffold consciousness corpus, generate processed artifacts, and (if Supabase CLI is installed) apply schema; follow with the Selenium scrape + geometry publish steps below.
- `make ingest-consciousness-yt` — search YouTube for each consciousness chunk, invoke pmoves-yt ingest/emit, and record video mappings (`processed-for-rag/supabase-import/consciousness-video-sources.json`).

Consciousness follow-up:
1. `pwsh -File pmoves/data/consciousness/Constellation-Harvest-Regularization/scripts/selenium-scraper.ps1` (run on a host with PowerShell + Chrome).
2. Apply schema:
   ```bash
   supabase status --output env > supabase/.tmp_env && source supabase/.tmp_env
   psql "$${SUPABASE_DB_URL}" -f pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-schema.sql
   ```
   *(Compose runtime)* `docker compose -p pmoves exec postgres psql -U pmoves -d pmoves -f pmoves/data/.../consciousness-schema.sql`
3. Import `processed-for-rag/supabase-import/n8n-workflow.json` into n8n and process `embeddings-ready/consciousness-chunks.jsonl`.
4. `make -C pmoves ingest-consciousness-yt` (after `make -C pmoves up-yt`) to download authoritative interviews and emit CGPs for each chunk.
5. Publish geometry sample via `make mesh-handshake FILE=pmoves/data/consciousness/Constellation-Harvest-Regularization/processed-for-rag/supabase-import/consciousness-geometry-sample.json`.
6. Record evidence (chunk counts, Supabase rows, geometry IDs, video IDs) in `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.

## Troubleshooting
- Port in use: change the host port in `docker-compose.yml` or stop the conflicting process.
- Qdrant not ready: `docker compose logs -f qdrant` and retry after a few seconds.
- 401 from Render Webhook: ensure `Authorization: Bearer $RENDER_WEBHOOK_SHARED_SECRET` matches `.env`.
- PostgREST errors: confirm `postgres` is up and `/supabase/initdb` scripts finished; check `docker compose logs -f postgres postgrest`.
- Rerank disabled: if providers are unreachable, set `RERANK_ENABLE=false` or configure provider keys in `.env`.

## Log Triage
- List services and status: `docker compose ps`
- Tail recent logs for core services:
  - `docker compose logs --since 15m presign render-webhook postgrest hi-rag-gateway hi-rag-gateway-gpu hi-rag-gateway-v2 hi-rag-gateway-v2-gpu`
  - `docker compose logs -f render-webhook` (follow live)
  - Shortcut: `make logs-core` (follow) or `make logs-core-15m`
- Common signals:
  - render-webhook JSONDecodeError on insert → ensure PostgREST returns JSON. Rebuild service after updating to headers with `Prefer: return=representation`:
    - `docker compose build render-webhook && docker compose up -d render-webhook`
  - Neo4j UnknownLabelWarning (e.g., `Entity`) → expected until graph/dictionary is seeded.

## Cleanup
- Stop containers: `make down`
- Remove volumes (destructive): `make clean`
## YouTube → Index + Shapes

Prereqs
- Services: `ffmpeg-whisper`, `pmoves-yt`, `hi-rag-gateway-v2` up and healthy.
- Data: `postgres`, `postgrest`, `qdrant`, `minio`, `neo4j` up.

Steps
- Ingest and emit (replace URL):
  - `make yt-emit-smoke URL=https://www.youtube.com/watch?v=2Vv-BfVoq4g`
- What it checks:
  - /yt/info yields a valid `video_id`
  - /yt/ingest downloads, extracts audio, transcribes (faster-whisper)
  - /yt/emit segments transcript into chunks and posts them to /hirag/upsert-batch; emits CGP to /geometry/event
  - /shape/point/p:yt:<id>:0/jump returns a valid video locator

Optional
- Summarize with Gemma (Ollama default):
  - `curl -X POST http://localhost:8077/yt/summarize -H 'content-type: application/json' -d '{"video_id":"<id>","style":"short"}' | jq`

## Preflight + Health Checks

Run a quick preflight (tools, ports, missing .env keys) and full retro report with HTTP health:

- `make flight-check-retro` (full, styled, includes HTTP health table)
- `make preflight` (quick JSON snapshot + styled summary)

HTTP endpoints checked:
- Qdrant `/ready`
- Meilisearch `/health`
- PostgREST `/` (200)
- Neo4j UI `/` (200)
- Presign `/healthz` (expects `{ok:true}`)
- Render Webhook `/healthz` (expects `{ok:true}`)
- Hi‑RAG v2 `/` (expects `{ok:true}`)
- PMOVES.YT `/healthz` (expects `{ok:true}`)
- ffmpeg‑whisper `/healthz` (expects `{ok:true}`)
- publisher-discord `/healthz` (expects `{ok:true}`)
- jellyfin-bridge `/healthz` (expects `{ok:true}`)

## Discord Publisher

- Set `DISCORD_WEBHOOK_URL` in `.env` to your channel webhook.
- Start service: `docker compose --profile orchestration up -d publisher-discord nats`.
- Smoke: `curl -X POST http://localhost:8092/publish -H 'content-type: application/json' -d '{"content":"PMOVES test ping"}'`
  - Expect 200/204 from Discord webhook (message in channel).

## Jellyfin Bridge

- Optional: set `JELLYFIN_URL` and `JELLYFIN_API_KEY` in `.env` to enable live checks.
- Link a video: `curl -X POST http://localhost:8093/jellyfin/link -H 'content-type: application/json' -d '{"video_id":"<id>","jellyfin_item_id":"<jf_id>"}'`
- Get playback URL: `curl -X POST http://localhost:8093/jellyfin/playback-url -H 'content-type: application/json' -d '{"video_id":"<id>","t":42}'`
  - Expect a URL pointing at Jellyfin web with start time.
- Auto-linking (optional): set `JELLYFIN_AUTOLINK=true` and (optionally) `AUTOLINK_INTERVAL_SEC=60` to periodically map recent videos by title.
- Search: `curl 'http://localhost:8093/jellyfin/search?query=<title>'`
- Map by title: `curl -X POST http://localhost:8093/jellyfin/map-by-title -H 'content-type: application/json' -d '{"video_id":"<id>","title":"<title>"}'`

## Content Publisher

- The publisher listens on `content.publish.approved.v1` and stages media as `<MEDIA_LIBRARY_PATH>/<namespace>/<slug>.<ext>`.
- Outgoing `content.published.v1` envelopes now include the source `description`, `tags`, and merged `meta` fields, plus optional
  `public_url`/`jellyfin_item_id` whenever Jellyfin confirms a library refresh.
- Configure `MEDIA_LIBRARY_PUBLIC_BASE_URL` to advertise HTTP paths for the downloaded artifacts.
- Regression coverage now includes a unit test that simulates a MinIO download failure and asserts the publisher emits the
  `content.publish.failed.v1` envelope with merged metadata and audit context (`test_handle_download_failed_emits_failure_envelope`).

## Playlist/Channel Ingestion

- `make yt-playlist-smoke URL=<playlist_or_channel_url>`
  - Starts a `yt_jobs` playlist job (max_videos=3)
  - Polls `yt_items` until at least one item is present
  - Picks the first completed (or first available) `video_id`, emits chunks+CGP, and verifies geometry jump
