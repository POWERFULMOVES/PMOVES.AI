# PMOVES.AI on SPARK — Observable Endpoints

> Generated after `make showtime` completed successfully on `pmoves-dgx-spark`.

## Web UIs reachable from the SPARK host

| Service | URL | Status | Notes |
|---------|-----|--------|-------|
| **Agent Zero SPARK** | http://localhost:5082 | ✅ 200 | Main Agent Zero UI |
| **Agent Zero SPARK (alt)** | http://localhost:5083 | ✅ 200 | Same UI, second mapped port |
| **Open Notebook UI** | http://localhost:8503 | ✅ 307 → `/notebooks` | Streamlit UI |
| **Open Notebook API** | http://localhost:5055 | ✅ 200 | REST API |
| **n8n** | http://localhost:5678 | ✅ 200 `<title>n8n.io</title>` | Workflow automation |
| **Grafana** | http://localhost:3002 | ✅ 302 → login | Metrics / logs dashboards |
| **Prometheus** | http://localhost:9090 | ✅ 302 → expression browser | Metrics backend |
| **Hi-RAG Gateway v2** | http://localhost:8086 | ✅ 200 | CPU gateway |
| **Hi-RAG Gateway v2 GPU** | http://localhost:8087 | ✅ 200 | GPU gateway |
| **Archon API** | http://localhost:8091/healthz | ✅ 200 | Consolidated Archon service (after cleanup) |
| **Archon UI** | http://localhost:3737 | ✅ 200 | Served by consolidated Archon service |
| **Loki** | http://localhost:3100/ready | ✅ 200 | Log aggregation ready endpoint |

## API / backend endpoints

| Service | URL | Status | Notes |
|---------|-----|--------|-------|
| **TensorZero Gateway** | http://localhost:3030 | ⚠️ 404 at `/` | Gateway is healthy; POST to `/v1/chat/completions` |
| **presign** | http://localhost:8088 | ⚠️ 404 at `/` | Service is up; root has no handler |
| **publisher-discord** | http://localhost:8094 | ⚠️ 404 at `/` | Service is up; root has no handler |

## Known issues / not exposed on localhost

| Service | Expected | Actual | Why |
|---------|----------|--------|-----|
| **Supabase / Kong** | http://localhost:8000 | ❌ not listening | Only exposed on Docker internal networks for security. |
| **MinIO Console / S3** | http://localhost:9000 / 9001 | ❌ not listening | Only exposed on Docker internal networks. |
| **Cipher Memory** | http://localhost:8105 | ❌ not reachable | Runs in the external `PMOVES-Agent-Zero-SPARK` container; OpenClaw scope routes via `${TS_Z890}` fleet URL. |
| **Agent Zero MCP** | http://localhost:8080 | ❌ not listening | Runs in the external `PMOVES-Agent-Zero-SPARK` container; OpenClaw scope routes via `${TS_Z890}`. |

## Cleanup note

The separate `archon-ui` container has been removed. Archon now runs as a single consolidated service (`pmoves-archon-1`) on port **8091**, with the same UI available on port **3737**.

## Quick verification commands

```bash
# See all running containers
docker ps

# See host ports actually listening
ss -tlnp

# Quick HTTP smoke test
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5082
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8503
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5678
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3002

# Full flight check
make -C pmoves flight-check-retro
```

## Browser access

From the SPARK node desktop or any machine that can route to `pmoves-dgx-spark`, open:

- **Agent Zero**: http://pmoves-dgx-spark:5082
- **Open Notebook**: http://pmoves-dgx-spark:8503
- **n8n**: http://pmoves-dgx-spark:5678
- **Grafana**: http://pmoves-dgx-spark:3002
- **Archon UI**: http://pmoves-dgx-spark:3737

## Agent Zero A2A

Agent Zero mounts the A2A protocol router on its main HTTP port. On SPARK the main Agent Zero container is reachable on port **5082/5083**:

- Agent card: `http://localhost:5082/.well-known/agent-card.json`
- A2A v1 tasks: `http://localhost:5082/a2a/v1/...`

No separate A2A port is required.

## Visual evidence

Headless Chromium screenshots captured after bring-up:

- `pmoves/docs/evidence/http___localhost_5678.png` — n8n setup page
- `pmoves/docs/evidence/http___localhost_3002_login.png` — Grafana login page

Agent Zero and Open Notebook are JavaScript-heavy SPAs; their root HTML returns 200 with the correct `<title>` but the static screenshot is blank before JS hydration. Use the live URLs above to interact with them.
