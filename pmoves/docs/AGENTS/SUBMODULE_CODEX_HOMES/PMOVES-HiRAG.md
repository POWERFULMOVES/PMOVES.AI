# Codex Home Overlay: PMOVES-HiRAG

Scope:
- HiRAG CPU/GPU parity, geometry packet health, rerank smoke.

Core checks:
- `curl -fsS http://localhost:8086/hirag/admin/stats | jq .`
- `curl -fsS http://localhost:8087/hirag/admin/stats | jq .`
- `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`

Related parity tokens:
- `/search:hirag`
- `/chit:bus`
- `/gpu:status`
