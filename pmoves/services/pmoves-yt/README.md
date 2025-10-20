# PMOVES.YT — Ingest + CGP Publisher

YouTube ingest helper that emits CHIT geometry after analysis.

## Service & Ports
- Compose service: `pmoves-yt`
- Starts with `make up-yt` (brings up `ffmpeg-whisper` too)

## Geometry Bus (CHIT) Integration
- Publishes `geometry.cgp.v1` to the Hi‑RAG gateway:
  - Endpoint: `POST ${HIRAG_URL}/geometry/event`
- Environment:
  - `HIRAG_URL` — base URL for the geometry gateway (`http://localhost:8086` by default)

## Smoke
- See `pmoves/services/pmoves-yt/tests/test_emit.py` for the CGP emission assertion.
- Run the main smokes in `pmoves/docs/SMOKETESTS.md` after `make up`.

