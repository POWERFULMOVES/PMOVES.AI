# Codex Home Overlay: Pmoves-hyperdimensions

Scope:
- Hyperdimensions control-plane parity for geometry-driven rendering lanes.

Core checks:
- `make -C pmoves web-geometry`
- `curl -fsS http://localhost:8086/geometry/calibration/report | jq .`
- `curl -fsS http://localhost:8113/config | jq .`

Related parity tokens:
- `/hyperdim:render`
- `/hyperdim:animate`
- `/hyperdim:export`
