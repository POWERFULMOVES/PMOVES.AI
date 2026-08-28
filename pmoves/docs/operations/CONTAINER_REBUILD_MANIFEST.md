# Container Rebuild Manifest

_Created: 2026-03-28 by 4090-claude_
_Owner: z890-claude (Infrastructure Coordinator)_

## Why

Six service images have accumulated Dockerfile, dependency, or submodule changes since their last GHCR publish. Stale images block W1 (voice), W3 (Discord), W4 (content), W5 (enterprise), and W6 (life integration) workstreams.

## Services

| # | Service | Compose File | Build Context | Dockerfile | GHCR Tag |
|---|---------|-------------|--------------|------------|----------|
| 1 | **flute-gateway** | `docker-compose.yml` | `pmoves/` | `services/flute-gateway/Dockerfile` | `ghcr.io/powerfulmoves/pmoves-flute-gateway:latest` |
| 2 | **tensorzero** | `docker-compose.yml` | — (upstream image) | — | `tensorzero/gateway:2026.1.8` |
| 3 | **publisher-discord** | `docker-compose.yml` | `pmoves/` | `services/publisher-discord/Dockerfile` | — (local build) |
| 4 | **botz-gateway** | `docker-compose.yml` | `pmoves/services/botz-gateway` | `Dockerfile` | — (local build) |
| 5 | **cipher-memory** | `docker-compose.yml` | `../Pmoves-cipher` | `Dockerfile` | — (local build) |
| 6 | **pmoves-yt** | `docker-compose.integrations.images.yml` | — (GHCR image) | — | `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest` |

## What Each Rebuild Unblocks

| Service | Workstreams | Specific Feature |
|---------|------------|-----------------|
| flute-gateway | W1, W6 | Voice binding for personas, prosodic routing, Pipecat WebSocket |
| tensorzero | All | Model routing, Qwen3-4b embedding default, provider proxy |
| publisher-discord | W3, M2 | Discord classrooms, MCP bridge, approval → publish loop |
| botz-gateway | W1 | BoTZ CLI bridge, persona selector, skill pairing |
| cipher-memory | W6 | Agent memory, reasoning traces, pattern storage |
| pmoves-yt | W4 | Content publishing pipeline, YouTube ingestion |

## Execution Plan (z890-claude)

### Quick path (local builds, no GHCR push)
```bash
cd pmoves

# Rebuild all local-build services
docker compose build flute-gateway publisher-discord botz-gateway

# Cipher-memory builds from submodule
docker compose build cipher-memory

# Restart with fresh images
make up-agents
make up-integrations
```

### Full path (GHCR publish for multi-node deployment)
```bash
# Flute-Gateway (the only custom GHCR image currently)
docker build -t ghcr.io/powerfulmoves/pmoves-flute-gateway:latest -f services/flute-gateway/Dockerfile .
docker push ghcr.io/powerfulmoves/pmoves-flute-gateway:latest

# PMOVES.YT (published by CI, but can be triggered manually)
# Check: gh workflow run ghcr-pmoves-yt.yml
```

### Verification
```bash
# After rebuilds, verify all services start healthy
make verify-all

# Check specific service health
curl http://localhost:8055/healthz   # flute-gateway
curl http://localhost:3030/health    # tensorzero
curl http://localhost:8105/health    # cipher-memory
```

## Registry Consolidation (2026-03-28, z890-claude)

**FIXED:** `docker-compose.integrations.images.yml` was pointing to `ghcr.io/cataclysm-studios-inc/pmoves-yt` — an image that does not exist. Corrected to `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest` (verified via `docker manifest inspect`).

**Also fixed:** 4 PR-kit compose files normalized from uppercase `POWERFULMOVES` to lowercase `powerfulmoves` for consistency.

**Runner status:** All 4 self-hosted runners are offline. CI-based builds (`integrations-ghcr.yml`) cannot publish until a runner comes online. 4 stuck queued runs were cancelled.

## Notes

- **TensorZero** uses the upstream `tensorzero/gateway:2026.1.8` image — no custom build needed unless PMOVES adds a custom Dockerfile. The OPENAI_API_KEY placeholder was added in `f385c21fe` but that's an env var, not an image change.
- **PMOVES.YT** is published via CI to GHCR at `ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest`. Image exists and pulls correctly after registry fix.
- **Cipher-memory** builds from the `Pmoves-cipher` submodule (note: lowercase `P` in path). Ensure the submodule is initialized.
- Run `make -C pmoves secrets-funnel` before starting services to ensure env tiers are hydrated.
