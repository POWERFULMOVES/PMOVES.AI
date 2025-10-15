# Smoke Tests

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
2. Set shared secrets (change these):
   - `PRESIGN_SHARED_SECRET`
   - `RENDER_WEBHOOK_SHARED_SECRET`
   - Supabase REST endpoints:
     - `SUPA_REST_URL=http://127.0.0.1:54321/rest/v1` (host-side smoke harness + curl snippets)
     - `SUPA_REST_INTERNAL_URL=http://api.supabase.internal:8000/rest/v1` (compose services targeting the Supabase CLI stack)
   - With the Supabase CLI stack running, `make up` will replay all schema + seed SQL before the smoke harness executes. You can re-run it manually via `make supabase-bootstrap`.
   - If Neo4j is running (`pmoves-neo4j-1`), seed the CHIT mind-map aliases via `make neo4j-bootstrap` so `/mindmap/{id}` resolves during geometry checks.
3. Buckets: ensure MinIO has buckets you plan to use (defaults: `assets`, `outputs`). You can create buckets via the MinIO Console at `http://localhost:9001` if needed.

## 2) Preflight (Recommended)
- Cross‑platform: `make flight-check`
- Windows direct script: `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/env_check.ps1`

This checks tool availability, common ports, `.env` keys vs `.env.example`, and validates `contracts/topics.json`.

## 3) Start Core Stack
- Start data + workers profile (v2 gateway):
  - `make up`
- Wait ~15–30s for services to become ready.

Useful health checks:
- Presign: `curl http://localhost:8088/healthz`
- Render Webhook: `curl http://localhost:8085/healthz`
- PostgREST: `curl http://localhost:3000`
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

Expected: the Discord channel receives a rich embed with the Smoke Story title, namespace, published path, thumbnail, and tags. Remove `public_url` from the payload if you want to confirm the local-path fallback formatting.

## 4) Seed Demo Data (Optional but helpful)
- `make seed-data` (loads small sample docs into Qdrant/Meilisearch)
- Alternatively: `make load-jsonl FILE=$(pwd)/datasets/queries_demo.jsonl`

## 5) Run Smoke Tests
Choose one:
- macOS/Linux: `make smoke` (requires `jq`)
- Windows (no `jq` required): `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1`

What the smoke covers now (12 checks):
1) Qdrant ready (6333)
2) Meilisearch health (7700, warning only)
3) Neo4j UI reachable (7474, warning only)
4) Presign health (8088)
5) Render Webhook health (8085)
6) PostgREST reachable (3000)
7) Insert a demo row via Render Webhook
8) Verify a `studio_board` row exists via PostgREST
9) Run a Hi-RAG v2 query (8087)
10) Agent Zero `/healthz` reports the JetStream controller running
11) POST a generated `geometry.cgp.v1` packet to `/geometry/event`
12) Confirm the ShapeStore locator + calibration report via `/shape/point/{id}/jump` and `/geometry/calibration/report`

## 6) Geometry Bus (CHIT) — Extended Deep Dive

The smoke harness already exercises the ingest/jump/calibration flow with a synthetic CGP. Use the following manual walkthrough when you want to debug real packets, sign/encrypt payloads, or explore the decoders:

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

1. Start v2 GPU gateway or v2 gateway (serves UI):
   - `docker compose --profile gpu up -d hi-rag-gateway-v2-gpu` (GPU) or `docker compose --profile workers up -d hi-rag-gateway-v2`
2. Open http://localhost:8087/geometry/
3. Click Connect (room `public`). Post a CGP (make smoke-geometry) and watch points animate.
4. Open the page in a second browser window; both connect to `public` room. Use Share Shape to send a `shape-hello` on the DataChannel.
5. Click “Send Current CGP” to share the last geometry over the DataChannel; add a passphrase to sign the CGP capsule.
6. Toggle “Encrypt anchors” and set a passphrase to AES‑GCM encrypt constellation anchors client‑side before sending; the receiving gateway can decrypt if `CHIT_DECRYPT_ANCHORS=true`.

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

## Troubleshooting
- Port in use: change the host port in `docker-compose.yml` or stop the conflicting process.
- Qdrant not ready: `docker compose logs -f qdrant` and retry after a few seconds.
- 401 from Render Webhook: ensure `Authorization: Bearer $RENDER_WEBHOOK_SHARED_SECRET` matches `.env`.
- PostgREST errors: confirm `postgres` is up and `/supabase/initdb` scripts finished; check `docker compose logs -f postgres postgrest`.
- Rerank disabled: if providers are unreachable, set `RERANK_ENABLE=false` or configure provider keys in `.env`.

## Log Triage
- List services and status: `docker compose ps`
- Tail recent logs for core services:
  - `docker compose logs --since 15m presign render-webhook postgrest hi-rag-gateway-v2`
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
