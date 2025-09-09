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

## 4) Seed Demo Data (Optional but helpful)
- `make seed-data` (loads small sample docs into Qdrant/Meilisearch)
- Alternatively: `make load-jsonl FILE=$(pwd)/datasets/queries_demo.jsonl`

## 5) Run Smoke Tests
Choose one:
- macOS/Linux: `make smoke` (requires `jq`)
- Windows (no `jq` required): `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1`

What the smoke covers:
1) Qdrant ready (6333)
2) Meilisearch health (7700, warned if missing)
3) Neo4j UI reachable (7474, warned if not)
4) Presign health (8088)
5) Render Webhook health (8085)
6) PostgREST reachable (3000)
7) Insert a demo row via Render Webhook
8) Verify a `studio_board` row exists via PostgREST
9) Run a Hi-RAG v2 query (8087)

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

5. (Optional) Learned text decode (requires `CHIT_DECODE_TEXT=true` and `transformers`):
   ```bash
   curl -s http://localhost:8086/geometry/decode/text \
     -H 'content-type: application/json' \
     -d '{"mode":"learned","constellation_id":"c.test.1"}'
   ```

6. Calibration report:
   ```bash
   curl -s http://localhost:8086/geometry/calibration/report \
     -H 'content-type: application/json' \
     -d @cgp.json
   ```

Expected: 200s; locator shows `{ "modality":"video","ref_id":"yt123","t":12.5,"frame":300 }`.

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
4. Alternatively, publish via CLI: `make mesh-handshake FILE=cgp.json`.
   - Signaling goes through `/ws/signaling/public`. DataChannel is p2p.


Optional smoke targets:
- `make smoke-presign-put` — end‑to‑end presign PUT and upload
- `make smoke-rerank` — query with `use_rerank=true` (provider optional)
- `make smoke-langextract` — extract chunks from XML via `langextract` and load

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
