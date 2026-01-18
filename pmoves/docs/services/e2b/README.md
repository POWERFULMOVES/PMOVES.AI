# E2B — Agentic Computer Use Services

**Status:** In Progress (beta)

---

## Overview

E2B (Execution Environment for Bots) provides **self-hosted isolated sandboxes** for AI-generated code execution using Firecracker microVMs. This service enables PMOVES.AI agents to execute untrusted code securely, provide virtual desktop access for GUI operations, and perform web scraping automation.

**Deployment Target:** KVM VMs on Tailscale (VPN) + RustDesk (remote access)

### Services in this Group

| Service | Port | Purpose |
|---------|------|---------|
| e2b-mcp-server | 7073 | MCP bridge for Agent Zero integration |
| e2b-surf | 3080 | Next.js web interface for computer use |
| e2b-desktop | 6080 | NoVNC virtual desktop (GUI access) |
| e2b-sandbox | 7070 | Core sandbox execution backend |

---

## Compose

### E2B MCP Server

```yaml
e2b-mcp-server:
  image: pmoves-e2b-mcp-server:hardened
  container_name: pmoves-e2b-mcp-server-1
  hostname: e2b-mcp-server
  networks: [llm_tier, bus_tier, monitoring_tier]
  ports: ["7073:7073"]
  profiles: [e2b, agents]
  depends_on: [agent-zero, nats]
```

### E2B Surf

```yaml
e2b-surf:
  image: pmoves-e2b-surf:hardened
  container_name: pmoves-e2b-surf-1
  hostname: e2b-surf
  networks: [api_tier, app_tier, monitoring_tier]
  ports: ["3080:3000"]
  profiles: [e2b, ui]
```

### E2B Desktop

```yaml
e2b-desktop:
  image: pmoves-e2b-desktop:hardened
  container_name: pmoves-e2b-desktop-1
  hostname: e2b-desktop
  networks: [app_tier, monitoring_tier]
  ports: ["6080:6080"]
  profiles: [e2b, ui]
```

### E2B Sandbox (Self-Hosted)

```yaml
e2b-sandbox:
  image: pmoves-e2b-sandbox:hardened
  container_name: pmoves-e2b-sandbox-1
  hostname: e2b-sandbox
  networks: [app_tier, bus_tier, monitoring_tier]
  ports: ["7070:7070"]
  privileged: false
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:rw
  profiles: [e2b]
  cap_add: [SYS_ADMIN]
```

---

## Environment

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `E2B_API_KEY` | E2B API authentication key | *Required* |
| `E2B_DESKTOP_AUTH_TOKEN` | Desktop access token | *Required* |
| `E2B_MCP_SERVER_TOKEN` | MCP server authentication | *Required* |
| `E2B_SANDBOX_URL` | Sandbox backend URL | `http://e2b-sandbox:7070` |
| `E2B_DESKTOP_URL` | Desktop service URL | `http://e2b-desktop:6080` |
| `AGENT_ZERO_URL` | Agent Zero for MCP integration | `http://agent-zero:8080` |
| `NATS_URL` | NATS message bus | `nats://nats:4222` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `E2B_MAX_SANDBOXES` | Maximum concurrent sandboxes | `5` |
| `E2B_SANDBOX_MEMORY_MB` | Memory limit per sandbox | `2048` |
| `E2B_SANDBOX_CPU_LIMIT` | CPU limit per sandbox | `2` |
| `E2B_SANDBOX_TIMEOUT_SEC` | Max sandbox duration | `3600` |
| `E2B_DESKTOP_RESOLUTION` | Desktop resolution | `1920x1080` |
| `NEXT_PUBLIC_API_URL` | Surf web UI URL | `http://localhost:3080` |
| `E2B_DEBUG` | Enable debug logging | `false` |

---

## Health Check

### E2B MCP Server

```bash
curl http://localhost:7073/healthz
```

Returns service health + Agent Zero MCP connection status.

### E2B Surf

```bash
curl http://localhost:3080/api/health
```

Returns web interface health.

### E2B Desktop

```bash
curl http://localhost:6080/health
```

Returns NoVNC desktop health.

### E2B Sandbox (Self-Hosted)

```bash
curl http://localhost:7070/health
```

Returns sandbox backend health.

---

## API Endpoints

### E2B MCP Server

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/healthz` | Health check |
| POST | `/mcp/tools/list` | List available MCP tools |
| POST | `/mcp/tools/call` | Execute MCP tool |
| POST | `/sandbox/create` | Create new sandbox |
| POST | `/sandbox/execute` | Execute code in sandbox |
| DELETE | `/sandbox/{id}` | Terminate sandbox |

### E2B Surf

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/` | Web UI (Next.js) |
| POST | `/api/surf` | Start web surfing operation |
| GET | `/api/sessions` | List active sessions |
| DELETE | `/api/sessions/{id}` | Terminate session |

### E2B Desktop

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | NoVNC web interface |
| WebSocket | `/websockify` | VNC over WebSocket |

---

## Key Features

- **Firecracker MicroVMs** - Hardware-level isolation for code execution
- **NoVNC Desktop** - Browser-based virtual desktop for GUI operations
- **MCP Integration** - Native Model Context Protocol bridge to Agent Zero
- **Event Coordination** - NATS-based event publishing for sandbox lifecycle
- **Web Surfing** - Automated web scraping and content extraction
- **Self-Hostable** - Full self-hosting support on KVM with Tailscale + RustDesk
- **Security Hardened** - Non-root containers, read-only filesystems, capability dropping

---

## Smoke Testing

### Basic Health Checks

```bash
# Test all E2B services
curl -f http://localhost:7073/healthz || echo "E2B MCP Server unhealthy"
curl -f http://localhost:3080/api/health || echo "E2B Surf unhealthy"
curl -f http://localhost:6080/health || echo "E2B Desktop unhealthy"

# Test NATS connectivity
nats pub "test.e2b.v1" "test message"
nats sub "e2b.>" --count 1
```

### Sandbox Creation Test

```bash
# Create a test sandbox (Python)
curl -X POST http://localhost:7073/sandbox/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $E2B_MCP_SERVER_TOKEN" \
  -d '{
    "duration": 300,
    "memory_mb": 512,
    "cpu_limit": 1
  }'
```

### Code Execution Test

```bash
# Execute Python code
curl -X POST http://localhost:7073/sandbox/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $E2B_MCP_SERVER_TOKEN" \
  -d '{
    "sandbox_id": "sb-test",
    "language": "python",
    "code": "print(\"Hello from E2B!\")"
  }'
```

---

## Make Targets

```bash
# Build all E2B images
make build-e2b

# Start E2B services
make e2b-up

# Stop E2B services
make e2b-down

# View E2B logs
make e2b-logs

# E2B health check
make e2b-health
```

---

## Dependencies

### PMOVES Services

- **Agent Zero** (port 8080) - MCP integration for tool execution
- **NATS** (port 4222) - Event bus for sandbox coordination
- **MinIO** (port 9000) - Sandbox template storage
- **Supabase** - Session metadata and management

### External Dependencies

- **Firecracker** - MicroVM runtime (self-hosted)
- **Tailscale** - VPN for KVM networking
- **RustDesk** - Remote desktop access
- **Docker** - Container runtime for sandbox spawning

### Submodules

- `pmoves/pmoves/vendor/e2b-infra` - Self-hosting Terraform/Makefiles
- `pmoves/pmoves/vendor/e2b` - Core E2B SDK
- `pmoves/pmoves/vendor/e2b-desktop` - NoVNC desktop client
- `pmoves/pmoves/vendor/e2b-spells` - Code execution patterns
- `pmoves/pmoves/vendor/e2b-surf` - Next.js web UI
- `pmoves/pmoves/vendor/e2b-mcp-server` - MCP bridge implementation

---

## Ops Quicklinks

### Documentation

- [E2B Integration Guide](../../E2B_INTEGRATION.md) - Complete integration documentation
- [NATS Subjects](../../../../.claude/context/nats-subjects.md) - Event bus subjects
- [Services Catalog](../../../../.claude/context/services-catalog.md) - Full service listing
- [Security Hardening](../../PMOVES.AI%20PLANS/E2B_SECURITY_HARDENING.md) - Security documentation

### External Links

- [E2B Official Docs](https://e2b.dev/docs)
- [E2B Self-Hosting Guide](https://github.com/e2b-dev/infra/blob/main/self-host.md)
- [Firecracker Documentation](https://firecracker-microvm.github.io/)

### Monitoring

- **Grafana Dashboard:** http://localhost:3000 (import `monitoring/grafana/dashboards/e2b.json`)
- **Prometheus Metrics:** http://localhost:9090 (query `e2b_*`)
- **Loki Logs:** http://localhost:3100 (query `{job="e2b-*"}`)

### Troubleshooting

```bash
# View logs
docker logs pmoves-e2b-mcp-server-1 -f
docker logs pmoves-e2b-surf-1 -f
docker logs pmoves-e2b-desktop-1 -f

# Restart services
docker compose restart e2b-mcp-server e2b-surf e2b-desktop

# Check NATS events
nats sub "e2b.>" --count 10
```

---

## NATS Subjects

E2B services publish/subscribe to the following NATS subjects:

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `e2b.desktop.request.v1` | Publish | Request desktop sandbox |
| `e2b.desktop.ready.v1` | Subscribe | Desktop ready notification |
| `e2b.desktop.completed.v1` | Subscribe | Session completed |
| `e2b.desktop.failed.v1` | Subscribe | Session failed |
| `e2b.spell.execute.v1` | Publish | Execute E2B spell |
| `e2b.spell.completed.v1` | Subscribe | Spell completed |
| `e2b.spell.failed.v1` | Subscribe | Spell failed |
| `e2b.surf.request.v1` | Publish | Request surf operation |
| `e2b.surf.completed.v1` | Subscribe | Surf completed |
| `e2b.surf.failed.v1` | Subscribe | Surf failed |

---

## Security Hardening

All E2B services follow PMOVES security best practices:

- **Non-root user:** `65532:65532`
- **Read-only filesystem:** `read_only: true`
- **Capability dropping:** `cap_drop: [ALL]`
- **Security options:** `no-new-privileges:true`
- **Secret encryption:** CHIT for sensitive values

**Important:** `e2b-sandbox` requires Docker socket mount for spawning sandbox containers. This is a controlled escape from containerization for the sandbox spawning function.

---

## Deployment Modes

### Cloud Mode (Default)

Uses E2B cloud-hosted sandboxes:

```bash
export E2B_API_KEY="your_cloud_api_key"
export E2B_SANDBOX_URL="https://api.e2b.dev"
```

### Self-Hosted Mode (KVM)

Uses local Firecracker VMs:

```bash
export E2B_API_KEY="local_jwt_secret"
export E2B_SANDBOX_URL="http://e2b-sandbox:7070"

# Start self-hosted sandbox backend
docker compose --profile e2b up -d e2b-sandbox
```

See [E2B Integration Guide](../../E2B_INTEGRATION.md#kvms-self-hosting-guide) for KVM deployment instructions.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-29 | Initial PMOVES.AI integration |
