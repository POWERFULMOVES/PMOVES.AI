# Codex Home Overlay: PMOVES-ToKenism-Multi

Scope:
- CHIT geometry bus, tokenism simulation, and attribution routing parity.

Use this when:
- the task touches geometry packets, CHIT encoding/decoding, or attribution flow
- Codex needs the math/control-plane side of PMOVES rather than plain retrieval
- the traversal question involves `tokenism.*`, `geometry.*`, or swarm metadata

PMOVES companions:
- `PMOVES-HiRAG` for geometry-aware retrieval
- `Pmoves-hyperdimensions` for visualization and operator controls
- `EvoSwarm Controller` for swarm/meta evolution
- `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`

Core checks:
- `curl -fsS http://localhost:8086/hirag/admin/stats | jq .`
- `curl -fsS http://localhost:8086/geometry/calibration/report | jq .`
- `make -C pmoves web-geometry`

Related parity tokens:
- `/chit:encode`
- `/chit:decode`
- `/chit:visualize`
- `/chit:floos`

Related docs:
- `pmoves/docs/AGENTS/CODEX_ECOSYSTEM_TRAVERSAL.md`
- `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`
- `.claude/context/geometry-nats-subjects.md`

