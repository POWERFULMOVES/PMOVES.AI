# PMOVES + CHIT: Offline Workflow Demo

This demo shows how CHIT augments each stage of the PMOVES workflow without requiring any external services. It stitches together the existing CHIT endpoints into a simple, end‑to‑end run that you can execute locally.

## What this demonstrates

- Ingest: Accept a CHIT Geometry Packet (CGP) and persist it (`/data/{shape_id}.json`).
- Decode: Geometry‑only text decoding over a codebook to summarize each constellation.
- Calibrate: Reconstruct and score the constellations (KL/JS/Coverage) and write artifacts.
- Visualize: Render constellations as SVG; inspect recent shapes and indices.

CHIT’s role: CGP provides a compact, modality‑agnostic description (anchor + spectrum + points). This enables consistent ingest, retrieval/decoding, and visualization across PMOVES stages.

## Quick start

1) Install deps and run the gateway demo (Python 3.11+):

```bash
pip install -r requirements-demo.txt
uvicorn gateway.main:app --reload
```

2) Run the workflow demo (uses `tests/data/cgp_fixture.json`):

```bash
curl -s http://localhost:8000/workflow/demo_run \
  -H "content-type: application/json" \
  -d '{"per_constellation": 20}' | jq 
```

Response includes:

- `shape_id`, `data_url` → persisted CGP you can fetch.
- `artifacts.reconstruction_report` → Markdown report.
- `decode` → geometry‑only summaries per constellation.
- `viz.constellation_svg_endpoint` → POST a Constellation to render SVG.

3) Open the UI entry points:

- Root: http://localhost:8000/
- Client test page: http://localhost:8000/web/client.html
- Mix & Match playground: http://localhost:8000/web/playground.html
- API docs: http://localhost:8000/docs

## How this maps to PMOVES

- Ingest (PMOVES services → Gateway): CGP acts as the interchange. Demo persists to `/data/*` (mocking storage/event bus).
- Retrieval/Decode (Search/RAG): Geometry‑only decode uses a codebook to produce summaries; in production swap the codebook and add learned decoders.
- Calibration/QA (Eval/Scoring): JS/KL/Coverage quantify how well the observed spectrum matches the empirical distribution from the codebook.
- Visualization (Operator tools): SVG and recent‑shape APIs expose anchors/constellations for interactive UIs (timeline scrubbing, multi‑modal jumps).

## Extending toward real services

- Storage/DB: Replace `/data/*` writes with Supabase tables (`anchors`, `constellations`, `shape_points`).
- Realtime bus: Forward CGP ingest to Supabase Realtime; mirror recent shapes in a cache.
- Learned decoders: Enable `CHIT_DECODE_TEXT=true` and integrate a tiny T5 pipeline for generative summaries.
- Multi‑modal: Wire CLIP/CLAP decoders for images/audio; add jump handlers to video/audio/text assets.

## Useful endpoints

- `POST /workflow/demo_run` — one‑shot ingest → decode → calibrate → manifest.
- `POST /geometry/event` — persist CGP as a shape.
- `POST /geometry/decode/text` — geometry‑only or learned decode.
- `POST /geometry/calibration/report` — write Markdown + metrics JSON.
- `POST /viz/constellation.svg` — render SVG for a Constellation.
- `GET /viz/recent` — list recent shape IDs.


