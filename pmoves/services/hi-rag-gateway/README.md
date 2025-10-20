# Hi‑RAG Gateway (v1)

Legacy gateway exposing CHIT geometry endpoints and basic retrieval.

## Service & Ports
- Compose service: `hi-rag-gateway`
- Ports: CPU `:8089` (host) → container `:8086`

## Make / Compose
- Start legacy CPU+GPU: `make up-legacy-both`
- Recreate CPU: `docker compose up -d --force-recreate --no-deps hi-rag-gateway`
- Smokes: use v2 smoke flow in `pmoves/docs/SMOKETESTS.md` for geometry; v1 endpoints mirror v2.

## Geometry Bus (CHIT) Integration
- Endpoints:
  - `POST /geometry/event` — accept `geometry.cgp.v1`
  - `GET /shape/point/{point_id}/jump`
  - `POST /geometry/decode/text|image|audio` (when enabled)
- Environment:
  - `CHIT_REQUIRE_SIGNATURE`, `CHIT_PASSPHRASE`, `CHIT_DECRYPT_ANCHORS`
  - `CHIT_DECODE_TEXT|IMAGE|AUDIO`, `CHIT_T5_MODEL`, `CHIT_CLIP_MODEL`, `CHIT_CODEBOOK_PATH`

