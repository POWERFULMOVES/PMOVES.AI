# PMOVES Gateway (CHIT UI/API)

Experimental gateway bundling a small web UI and CHIT API routes.

## Service & Ports
- Compose service: `gateway` (if present in your compose profile)
- UI: `/` serves a demo UI for CHIT; REST under `/geometry/*`.

## Geometry Bus (CHIT) Integration
- Provides `POST /geometry/event`, `GET /shape/point/{id}/jump`, and decoder/calibration helpers.
- Uses in‑memory ShapeStore; optional learned text decode when `CHIT_T5_MODEL` is set.

## Related Docs
- CHIT spec and decoder notes:
  - `PMOVESCHIT.md`
  - `PMOVESCHIT_DECODERv0.1.md`
  - `PMOVESCHIT_DECODER_MULTIv0.1.md`
- See `pmoves/docs/SMOKETESTS.md` for end‑to‑end geometry checks.

