# PMOVES Gateway Service

The gateway orchestrates YouTube ingestion, Hi-RAG indexing, Neo4j enrichment, and CHIT visualisation behind a single FastAPI surface.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn pmoves.services.gateway.gateway.main:app --host 0.0.0.0 --port 8085
```

### Required environment

| Variable | Description |
|----------|-------------|
| `YT_URL` | Base URL for the pmoves-yt service (defaults to `http://pmoves-yt:8077`). |
| `SUPA_REST_URL` | Supabase REST endpoint for metadata enrichment. |
| `HIRAG_URL` | Hi-RAG gateway base URL (`/hirag/upsert-batch`, `/hirag/query`). |
| `JELLYFIN_URL` or `JELLYFIN_BRIDGE_URL` | Jellyfin bridge base URL for playback links. |
| `NATS_URL` | (Optional) NATS broker for publishing/consuming contract events. |

Set these before starting the service so `/workflow/demo_run` can reach the live dependencies.

## Try it out

- http://localhost:8085/ — landing page with orchestration controls and event feed.
- http://localhost:8085/demo/shapes-webrtc — WebRTC shapes demo (open in two tabs).
- http://localhost:8085/web/client.html — manual CHIT API tester.
- http://localhost:8085/docs — interactive OpenAPI documentation.
- http://localhost:8085/events/recent — recent contract events captured from NATS.

## Workflow demo

Trigger the full workflow against a YouTube URL:

```bash
curl -s http://localhost:8085/workflow/demo_run \
  -H 'content-type: application/json' \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "per_constellation": 16}' | jq
```

Response highlights:

- `video` — basic metadata from pmoves-yt.
- `hirag` — Hi-RAG upsert status + a search sample.
- `shape` — CHIT shape ID, decode output, and calibration artefacts.
- `neo4j.sample` — points mirrored into the graph for MindMap visualisation.
- `events` — most recent contract envelopes seen by the gateway.

All geometry artefacts are also exposed under `/data/{shape_id}.json` and `/artifacts/reconstruction_report.md` for inspection.
