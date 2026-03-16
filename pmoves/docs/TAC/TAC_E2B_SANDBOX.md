# TAC_E2B_SANDBOX
_Last updated: 2026-03-15_

## Mission

Self-hosted code execution sandbox ecosystem built on Firecracker microVMs. Provides hardware-isolated execution environments for agent tasks via MCP integration, browser automation, and NoVNC desktop access — all running on local KVM infrastructure (Z890, 5090, or cloud KVMs via Terraform).

## Services

| Service | Port | Technology | Health |
|---------|------|-----------|--------|
| **E2B MCP Server** | 7073 | Node 22 Alpine, MCP bridge | `GET /healthz` |
| **E2B Surf** | 3080 | Next.js standalone, browser automation | `GET /api/health` |
| **E2B Desktop** | 6080 | NoVNC, browser-based VNC | `GET /health` |
| **E2B Sandbox** | 7070 | Firecracker microVM backend | `GET /health` |

## Architecture

```
Agent Zero (8080)
  │
  ▼ MCP tool call
E2B MCP Server (7073)
  │
  ├─── E2B Sandbox (7070)           ← Firecracker microVM backend
  │      │ docker.sock mount (controlled escape)
  │      │ SYS_ADMIN capability
  │      └── Spawns isolated microVMs per execution
  │
  ├─── E2B Desktop (6080)           ← NoVNC virtual desktop
  │      └── WebSocket /websockify
  │
  └─── E2B Surf (3080)              ← Next.js web automation
         └── Browser interaction sessions

  NATS (4222) ◄──── Event coordination
  MinIO (9000) ◄──── Template storage
  Supabase ◄──── Session metadata
```

## Submodules (5)

| Submodule | Branch | Purpose |
|-----------|--------|---------|
| `PMOVES-E2B-Danger-Room` | `PMOVES.AI-Edition-Hardened` | Core Firecracker sandbox runtime |
| `PMOVES-E2B-Danger-Room-Desktop` | `PMOVES.AI-Edition-Hardened` | NoVNC desktop implementation |
| `PMOVES-E2b-Spells` | `PMOVES.AI-Edition-Hardened` | Code execution templates/patterns |
| `PMOVES-Danger-infra` | `PMOVES.AI-Edition-Hardened` | Terraform/Make for KVM provisioning |
| `pmoves-e2b-mcp-server` | `PMOVES.AI-Edition-Hardened` | MCP bridge to Agent Zero |

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `e2b.desktop.request.v1` | Publish | Request desktop sandbox |
| `e2b.desktop.ready.v1` | Subscribe | Desktop ready |
| `e2b.desktop.completed.v1` | Subscribe | Session completed |
| `e2b.desktop.failed.v1` | Subscribe | Session failed |
| `e2b.spell.execute.v1` | Publish | Execute spell (code pattern) |
| `e2b.spell.completed.v1` | Subscribe | Spell completed |
| `e2b.surf.request.v1` | Publish | Request surf operation |
| `e2b.surf.completed.v1` | Subscribe | Surf completed |

## Configuration

| Variable | Tier | Default |
|----------|------|---------|
| `E2B_API_KEY` | `env.tier-llm` | CHIT-encrypted |
| `E2B_MCP_SERVER_TOKEN` | `env.tier-llm` | CHIT-encrypted |
| `E2B_SANDBOX_URL` | `env.tier-llm` | `http://e2b-sandbox:7070` |
| `E2B_DESKTOP_URL` | `env.tier-api` | `http://e2b-desktop:6080` |
| `E2B_DESKTOP_AUTH_TOKEN` | `env.tier-api` | CHIT-encrypted |
| `AGENT_ZERO_URL` | `env.tier-llm` | `http://agent-zero:8080` |
| `E2B_MAX_SANDBOXES` | — | `5` |
| `E2B_SANDBOX_MEMORY_MB` | — | `2048` |
| `E2B_SANDBOX_CPU_LIMIT` | — | `2` |
| `E2B_SANDBOX_TIMEOUT_SEC` | — | `3600` |
| `E2B_DESKTOP_RESOLUTION` | — | `1920x1080` |
| `E2B_TELEMETRY_DISABLED` | — | `1` |

## API Endpoints

**MCP Server (7073):**
- `POST /mcp/tools/list` — List available tools
- `POST /mcp/tools/call` — Execute MCP tool
- `POST /sandbox/create` — Create new sandbox
- `POST /sandbox/execute` — Execute code in sandbox
- `DELETE /sandbox/{id}` — Terminate sandbox

**Surf (3080):**
- `POST /api/surf` — Start web surfing
- `GET /api/sessions` — List active sessions
- `DELETE /api/sessions/{id}` — Terminate session

**Desktop (6080):**
- `WebSocket /websockify` — VNC over WebSocket

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Hardware | Firecracker microVMs (KVM kernel isolation) |
| Network | Separate network namespaces per sandbox |
| Resources | cgroups: 2 CPU cores, 2 GB memory per sandbox |
| Container | Non-root user (UID 65532), read-only FS, capability dropping |
| Secrets | CHIT encryption at rest for API keys/tokens |
| Docker | Controlled socket mount (`/var/run/docker.sock:rw`) for Sandbox only |

## BoTZ Integration

E2B feature module at `PMOVES-BoTZ/features/e2b/`:
- FastAPI wrapper (`app_e2b.py`) exposing `/sandbox/run`, `/sandbox/exec`, `/sandbox/stop`
- Bridges BoTZ skill execution to E2B sandbox environments

## Deployment

```bash
# Docker Compose (testing/development)
docker compose --profile e2b --profile agents up -d

# Make targets
make build-e2b          # Build all E2B images
make e2b-up             # Start services
make e2b-down           # Stop services
make e2b-health         # Health check all 4 services

# Production (Terraform for KVM/cloud)
cd PMOVES-Danger-infra && terraform apply
```

## Production Readiness

| Check | MCP Server | Surf | Desktop | Sandbox |
|-------|-----------|------|---------|---------|
| `/healthz` | Present | Present | Present | Present |
| NATS | Active | Active | Active | Active |
| Auth | CHIT-encrypted tokens | CHIT-encrypted | Auth token | SYS_ADMIN cap |
| Docker profile | `e2b` | `e2b` | `e2b` | `e2b` |
| Non-root | UID 65532 | UID 65532 | UID 65532 | SYS_ADMIN required |
| Hardened branch | Yes | Yes | Yes | Yes |

## Verification

```bash
curl -s http://localhost:7073/healthz   # MCP Server
curl -s http://localhost:3080/api/health # Surf
curl -s http://localhost:6080/health     # Desktop
curl -s http://localhost:7070/health     # Sandbox
```
