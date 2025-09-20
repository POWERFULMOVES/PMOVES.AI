# PMOVES + CHIT: Live Workflow Demo

The gateway now executes the full ingestion → indexing → graph → visualisation loop against the running PMOVES stack.

## What this demonstrates

- **Ingest**: `/yt/ingest` downloads media, extracts transcripts, and emits contract events.
- **Index**: transcript chunks are pushed into Hi-RAG (`/hirag/upsert-batch`) with matching `kb.upsert.*` events.
- **Graph**: the resulting constellations are mirrored into Neo4j for MindMap visualisation.
- **Visualise**: CHIT APIs decode constellations, expose artefacts, and serve SVGs for recent shapes.
- **Playback**: Jellyfin bridge returns direct playback URLs for the indexed video.

## Quick start

1. Ensure the supporting services are running (Supabase/PostgREST, pmoves-yt, hi-rag-gateway, Neo4j, Jellyfin bridge, NATS).
2. Install the gateway dependencies and start the API:

```bash
pip install -r requirements.txt
uvicorn pmoves.services.gateway.gateway.main:app --host 0.0.0.0 --port 8085
```

3. Hit the landing page at http://localhost:8085/ — paste a YouTube URL and click **Run Orchestration**. The UI will stream the manifest and show the latest contract events as they arrive.

## Inspecting the results

- **Events**: `GET /events/recent` shows envelopes validated against `contracts/topics.json`.
- **Hi-RAG**: `POST /hirag/query` (via the manifest) demonstrates hybrid retrieval for the new chunks.
- **CHIT**: `GET /viz/shape/{shape_id}.svg`, `POST /geometry/decode/text`, and the persisted `/data/{shape_id}.json` expose the shape.
- **Neo4j**: `GET /mindmap/{constellation_id}` surfaces the points linked to media references.
- **Playback**: `POST /jellyfin/playback-url` (through the manifest) confirms the Jellyfin bridge mapping.

## API surface recap

- `POST /workflow/demo_run` — orchestrated ingest + index + graph + CHIT decode.
- `GET /events/recent` and `POST /events/publish` — inspect/publish PMOVES contract events.
- `POST /geometry/event` / `POST /geometry/decode/text` / `POST /geometry/calibration/report` — CHIT primitives.
- `GET /viz/recent`, `POST /viz/constellation.svg` — SVG rendering helpers.
- `GET /mindmap/{constellation_id}` — MindMap slice backed by Neo4j.

## Troubleshooting tips

| Symptom | Likely cause |
|---------|--------------|
| `503 Neo4j unavailable` | Set `NEO4J_URL`, `NEO4J_USER`, and `NEO4J_PASSWORD` to reach the graph instance. |
| Hi-RAG upsert fails | Check `HIRAG_URL` and ensure the service exposes `/hirag/upsert-batch`. |
| Playback missing | Provide `JELLYFIN_BRIDGE_URL` or `JELLYFIN_URL` pointing to the Jellyfin bridge. |
| No events recorded | Configure `NATS_URL` to a reachable broker. |

When services are unavailable the workflow still completes with partial data; the manifest highlights which integrations succeeded and which were skipped.
