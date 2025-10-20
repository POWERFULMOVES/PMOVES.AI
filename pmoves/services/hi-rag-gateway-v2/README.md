# Hi‑RAG Gateway v2

FastAPI service providing retrieval and CHIT geometry endpoints.

## Service & Ports
- Compose service: `hi-rag-gateway-v2` (CPU) and `hi-rag-gateway-v2-gpu` (GPU)
- Ports: CPU `:8086`, GPU `:8087`

## Make / Compose
- Start core stack (includes v2 CPU): `make up`
- Ensure both v2 variants up: `make up-both-gateways`
- GPU profile only: `make up-gpu-gateways`
- Recreate containers: `make recreate-v2`, `make recreate-v2-gpu`
- Smokes: `make smoke`, `make smoke-qwen-rerank`

## Geometry Bus (CHIT) Integration
- Exposes CHIT endpoints and maintains an in‑memory `ShapeStore` cache.
- Endpoints:
  - `POST /geometry/event` — accept `geometry.cgp.v1` (CGP) and cache/broadcast
  - `GET /shape/point/{point_id}/jump` — return locator for a point
  - `POST /geometry/decode/text` — summarize/label from constellation geometry
  - `POST /geometry/calibration/report` — produce constellation calibration
  - Optional: `POST /geometry/decode/{image|audio}` when enabled
- Realtime warm/capture (optional): subscribes to Supabase Realtime `geometry.cgp.v1` and warms from PostgREST when `SUPA_*` is set.
- Important env flags:
  - `CHIT_REQUIRE_SIGNATURE`, `CHIT_PASSPHRASE`, `CHIT_DECRYPT_ANCHORS`
  - `CHIT_DECODE_TEXT|IMAGE|AUDIO`, `CHIT_T5_MODEL`, `CHIT_CLIP_MODEL`, `CHIT_CODEBOOK_PATH`
  - `CHIT_PERSIST_DB` with `PG*` vars to persist CGP into Postgres

## Quick Examples
```bash
# Publish a CGP (capsule with type + data)
curl -s http://localhost:8086/geometry/event \
  -H 'content-type: application/json' \
  -d '{"type":"geometry.cgp.v1","data":{"spec":"chit.cgp.v0.1","super_nodes":[]}}'

# Jump to a point
curl -s http://localhost:8086/shape/point/p.demo.1/jump

# Decode text from constellation
curl -s http://localhost:8086/geometry/decode/text \
  -H 'content-type: application/json' \
  -d '{"mode":"learned","constellation_id":"c.demo.1","k":5}'
```

## Related Docs
- See `pmoves/docs/SMOKETESTS.md` (geometry steps) and `pmoves/Makefile` targets listed above.

