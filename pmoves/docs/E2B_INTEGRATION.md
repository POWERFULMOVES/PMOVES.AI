# E2B Agentic Computer Use Integration Guide

**Status:** Beta
**Version:** 1.0.0
**Last Updated:** 2025-12-29

---

## Overview

E2B (Execution Environment for Bots) provides **self-hosted isolated sandboxes** for AI-generated code execution using Firecracker microVMs. This integration enables PMOVES.AI agents to:

- Execute untrusted code in secure, isolated environments
- Provide virtual desktop access for agentic GUI operations (NoVNC)
- Run predefined "spells" (code execution patterns)
- Perform web scraping and computer use automation

**Deployment Target:** KVM VMs on Tailscale (VPN) + RustDesk (remote access)

### Components

| Component | Repository | Purpose | Tier |
|-----------|------------|---------|------|
| E2B Infra | `PMOVES-Danger-infra` | Self-hosting Terraform/Makefiles | N/A |
| E2B Sandbox | `PMOVES-E2B-Danger-Room` | Core sandbox execution backend | `app_tier`, `bus_tier` |
| E2B Desktop | `PMOVES-E2B-Danger-Room-Deskdesktop` | NoVNC virtual desktop | `app_tier`, `monitoring_tier` |
| E2B Spells | `PMOEVES-E2b-Spells` | Code execution patterns | N/A (library) |
| E2B Surf | `pmoves-surf` | Next.js web UI | `api_tier`, `app_tier` |
| E2B MCP Server | `pmoves-e2b-mcp-server` | Agent Zero bridge | `llm_tier`, `bus_tier` |

---

## Prerequisites

### Hardware Requirements

**For KVM Host (Self-Hosting):**
- CPU: 16+ cores (for multiple concurrent sandboxes)
- RAM: 64GB+ (4GB per sandbox minimum)
- Storage: NVMe SSD (1TB+) for VM disk images
- Network: 10Gbps connection recommended
- Virtualization: Intel VT-x/AMD-V enabled in BIOS

### Software Requirements

**Required Tools:**
- **Docker** 20.10+ - Container runtime
- **Packer** v1.5.x - For building disk images
- **Terraform** v1.5.7 - Infrastructure as Code (MPL licensed)
- **Google Cloud CLI** - For GCP deployment (if using cloud)
- **Golang** 1.25.4+ - For building E2B components
- **Tailscale** - VPN for secure KVM networking
- **RustDesk** - Remote desktop access for KVMs

### PMOVES Services

- **Agent Zero** - For MCP integration (port 8080)
- **NATS** - Event bus for coordination (port 4222)
- **MinIO** - For sandbox template storage (port 9000)
- **Supabase** - For metadata and session management

---

## Configuration

### Environment Variables

Create or update the following environment files:

#### `pmoves/.env` (or `.env.local`)

```bash
# ============================================================
# E2B Configuration
# ============================================================

# E2B API Key - Generate from https://e2b.dev/docs/getting-started/api-key
# For self-hosted: use your own JWT secret
E2B_API_KEY=your_e2b_api_key_here

# E2B Desktop Authentication Token - Generate with: openssl rand -hex 32
E2B_DESKTOP_AUTH_TOKEN=generate_random_token_here

# E2B MCP Server Token - Generate with: openssl rand -hex 32
E2B_MCP_SERVER_TOKEN=generate_random_token_here

# E2B Sandbox Limits
E2B_MAX_SANDBOXES=5
E2B_SANDBOX_MEMORY_MB=2048
E2B_SANDBOX_CPU_LIMIT=2
E2B_SANDBOX_TIMEOUT_SEC=3600

# E2B Desktop Settings
E2B_DESKTOP_RESOLUTION=1920x1080
E2B_DESKTOP_MAX_DURATION=3600

# E2B Surf Settings
E2B_SURF_PORT=3080
E2B_SURF_CONCURRENT=5
E2B_SURF_TIMEOUT=60

# E2B Spells Settings
E2B_SPELLS_TIMEOUT=300
E2B_SPELLS_MAX_MEMORY=1024
```

#### `pmoves/env.tier-llm` (E2B MCP Server)

```bash
# E2B MCP Server - Agent Zero Integration
E2B_API_KEY=***CHIT_ENCRYPTED***
E2B_MCP_SERVER_TOKEN=***CHIT_ENCRYPTED***
E2B_SANDBOX_URL=http://e2b-sandbox:7070
AGENT_ZERO_URL=http://agent-zero:8080
NATS_URL=nats://nats:4222
```

#### `pmoves/env.tier-api` (E2B Surf)

```bash
# E2B Surf - Web Interface
E2B_API_KEY=***CHIT_ENCRYPTED***
E2B_DESKTOP_AUTH_TOKEN=***CHIT_ENCRYPTED***
NEXT_PUBLIC_API_URL=http://localhost:3080
E2B_SURF_PORT=3000
E2B_SANDBOX_URL=http://e2b-sandbox:7070
E2B_DESKTOP_URL=http://e2b-desktop:6080
```

#### `pmoves/env.tier-worker` (E2B Spells)

```bash
# E2B Spells - Code Execution Patterns
E2B_API_KEY=***CHIT_ENCRYPTED***
E2B_SPELLS_TIMEOUT=300
E2B_SPELLS_MAX_MEMORY=1024
```

### CHIT-Encrypted Secrets

For production deployments, use CHIT (Geometry Bus) encryption for sensitive values:

```python
# CHIT-encoded secrets for E2B
E2B_API_KEY=chit:encrypt:{encoded_key}
E2B_DESKTOP_AUTH_TOKEN=chit:encrypt:{encoded_token}
E2B_MCP_SERVER_TOKEN=chit:encrypt:{encoded_token}
```

See `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` for CHIT usage.

---

## Installation & Setup

### Step 1: Clone E2B Submodules

```bash
cd /home/pmoves/PMOVES.AI

# Initialize E2B submodules (only e2b and agentgym-rl are registered)
git submodule update --init --recursive pmoves/vendor/e2b
git submodule update --init --recursive pmoves/vendor/agentgym-rl

# Checkout PMOVES.AI-Edition-Hardened branches (production standard)
cd pmoves/vendor/e2b && git checkout PMOVES.AI-Edition-Hardened
cd ../agentgym-rl && git checkout PMOVES.AI-Edition-Hardened
```

**Note:** The E2B services (`e2b-mcp-server`, `e2b-surf`, `e2b-desktop`) are **not submodules**. Their Dockerfiles clone directly from PMOVES forks on GitHub with the `PMOVES.AI-Edition-Hardened` branch. See individual Dockerfiles in `pmoves/docker/e2b-*/` for source URLs.

**Production Standard:** All PMOVES.AI services run on the `PMOVES.AI-Edition-Hardened` branch (main repo and all submodules).

### Step 2: Configure Environment Variables

```bash
# Copy example environment files
cp pmoves/.env.example pmoves/.env
cp pmoves/env.tier-api.example pmoves/env.tier-api

# Generate secure tokens
openssl rand -hex 32  # For E2B_DESKTOP_AUTH_TOKEN
openssl rand -hex 32  # For E2B_MCP_SERVER_TOKEN

# Edit pmoves/.env and add generated values
nano pmoves/.env
```

### Step 3: Build Docker Images

```bash
cd pmoves

# Build E2B MCP Server
docker compose build e2b-mcp-server

# Build E2B Surf (Next.js application)
docker compose build e2b-surf

# Build E2B Desktop (NoVNC)
docker compose build e2b-desktop
```

### Step 4: Start Services

```bash
cd pmoves

# Start E2B services with dependencies
docker compose --profile e2b --profile agents up -d

# Verify services are healthy
curl http://localhost:7073/healthz  # E2B MCP Server
curl http://localhost:3080/api/health  # E2B Surf
curl http://localhost:6080/health  # E2B Desktop
```

---

## API Reference

### Authentication

E2B uses **JWT Bearer Tokens** for API authentication:

```bash
# Get API key from E2B (or use self-hosted secret)
export E2B_API_KEY="your_api_key"

# All requests include the API key
curl -H "X-E2B-API-Key: $E2B_API_KEY" \
  http://localhost:7070/api/sandboxes
```

### Endpoints

#### E2B MCP Server (Agent Zero Bridge)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/healthz` | Health check |
| POST | `/mcp/tools/list` | List available MCP tools |
| POST | `/mcp/tools/call` | Execute an MCP tool |
| POST | `/sandbox/create` | Create new sandbox |
| POST | `/sandbox/execute` | Execute code in sandbox |
| DELETE | `/sandbox/{id}` | Terminate sandbox |

**Create Sandbox Example:**
```bash
curl -X POST http://localhost:7073/sandbox/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $E2B_MCP_SERVER_TOKEN" \
  -d '{
    "duration": 3600,
    "memory_mb": 2048,
    "cpu_limit": 2
  }'
```

**Execute Code Example:**
```bash
curl -X POST http://localhost:7073/sandbox/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $E2B_MCP_SERVER_TOKEN" \
  -d '{
    "sandbox_id": "sb-uuid",
    "language": "python",
    "code": "print(\"Hello from E2B!\")"
  }'
```

#### E2B Surf (Web UI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/` | Web UI (Next.js) |
| POST | `/api/surf` | Start web surfing operation |
| GET | `/api/sessions` | List active sessions |
| DELETE | `/api/sessions/{id}` | Terminate session |

**Web Surf Example:**
```bash
curl -X POST http://localhost:3080/api/surf \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "depth": 2,
    "extract_content": true
  }'
```

#### E2B Desktop (NoVNC)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | NoVNC web interface |
| WebSocket | `/websockify` | VNC over WebSocket |

**Desktop Access:**
```bash
# Open in browser
open http://localhost:6080

# Or via curl for health check
curl http://localhost:6080/health
```

### NATS Integration

E2B publishes events to NATS for coordination:

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `e2b.desktop.request.v1` | Publish | Request desktop sandbox |
| `e2b.desktop.ready.v1` | Subscribe | Desktop ready notification |
| `e2b.desktop.completed.v1` | Subscribe | Session completed |
| `e2b.desktop.failed.v1` | Subscribe | Session failed |
| `e2b.spell.execute.v1` | Publish | Execute E2B spell |
| `e2b.spell.completed.v1` | Subscribe | Spell completed |
| `e2b.spell.failed.v1` | Subscribe | Spell failed |

**Publish Example:**
```bash
nats pub "e2b.desktop.request.v1" '{
  "request_id": "uuid-v4",
  "agent_id": "agent-zero",
  "duration": 3600,
  "memory_mb": 2048,
  "cpu_limit": 2
}'
```

---

## Usage Examples

### Basic Usage: Python Code Execution

```python
from e2b_code_interpreter import Sandbox

# Create a sandbox
sandbox = Sandbox(api_key=E2B_API_KEY)

# Execute Python code
result = sandbox.run_code("print('Hello from E2B!')")
print(result.stdout)  # "Hello from E2B!"

# Execute with file operations
result = sandbox.run_code("""
import os
with open('/tmp/test.txt', 'w') as f:
    f.write('E2B file test')
print(os.listdir('/tmp'))
""")

# Clean up
sandbox.kill()
```

### Advanced Usage: Desktop Automation

```python
from e2b_desktop import DesktopSandbox

# Create a desktop sandbox with GUI
desktop = DesktopSandbox(
    api_key=E2B_API_KEY,
    auth_token=E2B_DESKTOP_AUTH_TOKEN
)

# Get NoVNC URL for browser access
desktop_url = desktop.get_url()
print(f"Desktop accessible at: {desktop_url}")

# Execute GUI operations
desktop.run_command("firefox https://example.com")
screenshot = desktop.screenshot()

# Clean up
desktop.kill()
```

### Agent Zero Integration (MCP)

```python
import requests

# Agent Zero requests E2B code execution via MCP
response = requests.post(
    "http://agent-zero:8080/mcp/tools/call",
    headers={"Content-Type": "application/json"},
    json={
        "tool": "e2b_execute_code",
        "arguments": {
            "code": "import math; print(math.pi)",
            "language": "python"
        }
    }
)

result = response.json()
print(result["content"]["stdout"])
```

---

## Monitoring & Observability

### Health Checks

All E2B services expose health endpoints:

```bash
# Check all E2B services
curl http://localhost:7073/healthz  # E2B MCP Server
curl http://localhost:3080/api/health  # E2B Surf
curl http://localhost:6080/health  # E2B Desktop
curl http://localhost:7070/health  # E2B Sandbox (if self-hosted)
```

### Logging

E2B services log to Loki for centralized aggregation:

```bash
# Query E2B logs via Loki API
curl -G "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={job="e2b-mcp-server"}' \
  --data-urlencode 'limit=50'
```

**Log Labels:**
- `job=e2b-mcp-server` - MCP server logs
- `job=e2b-surf` - Surf web UI logs
- `job=e2b-desktop` - Desktop sandbox logs

### Metrics

E2B services expose Prometheus metrics:

```bash
# Query E2B metrics
curl http://localhost:7073/metrics  # E2B MCP Server
curl http://localhost:9090/api/v1/query?query=e2b_sandboxes_active
```

**Available Metrics:**
- `e2b_sandboxes_active` - Currently active sandboxes
- `e2b_sandboxes_created_total` - Total sandboxes created
- `e2b_executions_total` - Total code executions
- `e2b_execution_duration_seconds` - Execution duration histogram

### Grafana Dashboards

Import the E2B dashboard at `pmoves/monitoring/grafana/dashboards/e2b.json`:

```bash
curl -X POST "http://admin:admin@localhost:3000/api/dashboards/import" \
  -H "Content-Type: application/json" \
  -d @pmoves/monitoring/grafana/dashboards/e2b.json
```

---

## Troubleshooting

### Common Issues

#### Issue: "Connection refused" to E2B services

**Symptoms:** `curl: (7) Failed to connect to localhost port 7073`

**Solutions:**
1. Check service status: `docker compose ps e2b-mcp-server`
2. Check logs: `docker logs pmoves-e2b-mcp-server-1`
3. Verify network: `docker network inspect pmoves-net`
4. Restart service: `docker compose restart e2b-mcp-server`

#### Issue: Sandbox creation timeout

**Symptoms:** `TimeoutError: Sandbox creation timed out after 30s`

**Solutions:**
1. Check Docker socket mount: `ls -la /var/run/docker.sock`
2. Verify Firecracker is running (self-hosted): `ps aux | grep firecracker`
3. Increase timeout: Set `E2B_SANDBOX_TIMEOUT_SEC=7200`
4. Check resource limits: `docker stats`

#### Issue: NoVNC desktop not loading

**Symptoms:** Blank screen or "Connection failed" in browser

**Solutions:**
1. Check WebSocket: `wscat -c ws://localhost:6080/websockify`
2. Verify X11 is running: `ps aux | grep Xvfb`
3. Check resolution setting: Set `E2B_DESKTOP_RESOLUTION=1280x720`
4. Restart desktop: `docker compose restart e2b-desktop`

#### Issue: MCP server not connecting to Agent Zero

**Symptoms:** Agent Zero can't find E2B tools

**Solutions:**
1. Verify MCP configuration: `curl http://agent-zero:8080/mcp/tools/list`
2. Check NATS connection: `nats server info`
3. Verify environment: `docker exec pmoves-e2b-mcp-server-1 env | grep AGENT_ZERO`
4. Restart both services: `docker compose restart e2b-mcp-server agent-zero`

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug environment variable
export E2B_DEBUG=true
export RUST_LOG=debug

# Restart services with debug logging
docker compose --profile e2b up -d --force-recreate

# View logs in real-time
docker logs -f pmoves-e2b-mcp-server-1
```

### KVM Deployment Debugging

For self-hosted KVM deployments:

```bash
# Check Firecracker VM status
sudo fc-ctl list-vms

# Check disk image availability
ls -la /var/lib/e2b/images/

# Check Nomad jobs (if using Nomad orchestration)
nomad job status e2b-sandbox

# Check Tailscale connection
tailscale status

# Check RustDesk connection
rustdesk-id
```

---

## Security Considerations

### Sandbox Isolation

E2B uses **Firecracker microVMs** for hardware-level isolation:

- Each sandbox runs in a separate Firecracker VM
- Kernel-level isolation via KVM
- Network namespaces prevent cross-sandbox communication
- Resource limits enforced via cgroups

**Verification:**
```bash
# Check that sandboxes are isolated
docker exec pmoves-e2b-sandbox-1 ps aux
docker exec pmoves-e2b-sandbox-1 ip addr
```

### Network Security

**Tailscale VPN:**
- All KVM hosts connected via Tailscale mesh network
- Traffic encrypted via WireGuard
- ACLs restrict inter-host communication

**RustDesk Remote Access:**
- End-to-end encryption for remote desktop
- Two-factor authentication required
- Session logging for audit trails

### Access Control

**Authentication Methods:**
1. **JWT Bearer Tokens** - For API access (E2B_API_KEY)
2. **Service Role Keys** - For admin operations (E2B_MCP_SERVER_TOKEN)
3. **Desktop Auth Tokens** - For NoVNC access (E2B_DESKTOP_AUTH_TOKEN)

**Best Practices:**
- Rotate tokens regularly (90 days recommended)
- Use CHIT encryption for secrets at rest
- Never commit tokens to git
- Use separate tokens for dev/staging/production

### Data Handling

**Code Execution:**
- Code executed in ephemeral sandboxes (deleted after session)
- No persistent storage within sandboxes
- All artifacts uploaded to MinIO for retention

**Session Management:**
- Session metadata stored in Supabase
- Sandbox IDs are UUID v4 (unguessable)
- Automatic cleanup after timeout

**Resource Limits:**
- CPU: 2 cores max per sandbox
- Memory: 2GB max per sandbox
- Duration: 3600 seconds max per session
- Network: Blocked from external internet (configurable)

---

## KVM Self-Hosting Guide

### Prerequisites

```bash
# Install KVM and virtualization tools
sudo apt-get install \
  qemu-kvm libvirt-daemon-system libvirt-clients \
  bridge-utils virtinst virt-manager

# Enable and start libvirtd
sudo systemctl enable --now libvirtd

# Verify KVM is available
kvm-ok
```

### Tailscale Setup

```bash
# Install Tailscale on KVM host
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate and connect
sudo tailscale up --advertise-tags=kvm-host

# Verify connection
tailscale status
tailscale ip
```

### RustDesk Setup

```bash
# Download and install RustDesk server
wget https://github.com/rustdesk/rustdesk-server/releases/latest/download/rustdesk-server-linux-x64.zip
unzip rustdesk-server-linux-x64.zip
sudo mv rustdesk-server /usr/local/bin/

# Enable and start RustDesk
sudo systemctl enable --now rustdesk-server

# Get RustDesk ID for remote access
rustdesk-id
```

### E2B Infrastructure Deployment

**Option 1: Docker Compose (Recommended for Testing)**

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Start E2B services
docker compose --profile e2b up -d

# Verify deployment
docker compose ps e2b-sandbox e2b-desktop e2b-mcp-server e2b-surf
```

**Option 2: Terraform (Production KVM Deployment)**

```bash
cd /home/pmoves/PMOVES.AI/pmoves/pmoves/vendor/e2b-infra

# Configure Terraform variables
cat > terraform.tfvars <<EOF
provider         = "gcp"  # or "aws"
prefix           = "e2b-"
project_id       = "your-project-id"
region           = "us-west1"
zone             = "us-west1-a"
domain_name      = "your-domain.com"
postgres_connection_string = "postgresql://..."
EOF

# Initialize and apply
terraform init
terraform plan
terraform apply
```

---

## Related Documentation

### PMOVES Documentation
- [Services Catalog](../../.claude/context/services-catalog.md) - Complete service listing
- [NATS Subjects](../../.claude/context/nats-subjects.md) - Event bus integration
- [Network Architecture](../../.claude/context/tier-architecture.md) - PMOVES network tiers
- [CHIT Integration](../PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md) - Secret encryption

### E2B External Documentation
- [E2B Official Docs](https://e2b.dev/docs)
- [E2B Self-Hosting Guide](https://github.com/e2b-dev/infra/blob/main/self-host.md)
- [Firecracker Documentation](https://firecracker-microvm.github.io/)
- [E2B Python SDK](https://github.com/e2b-dev/e2b-code-interpreter)

### Agent Zero Integration
- [MCP API Reference](../../.claude/context/mcp-api.md) - Agent Zero MCP protocol
- [Agent Zero Service Docs](../services/agent-zero/README.md) - Agent Zero configuration

---

## Appendix: Quick Reference

### All E2B Service Ports

| Service | Internal Port | External Port | Protocol |
|---------|---------------|---------------|----------|
| e2b-sandbox | 7070 | 7070 | HTTP |
| e2b-desktop | 6080 | 6080 | HTTP/WebSocket |
| e2b-mcp-server | 7073 | 7073 | HTTP |
| e2b-surf | 3000 | 3080 | HTTP |

### Smoke Testing Commands

```bash
# Test E2B MCP Server
curl -f http://localhost:7073/healthz || echo "E2B MCP Server unhealthy"

# Test E2B Surf
curl -f http://localhost:3080/api/health || echo "E2B Surf unhealthy"

# Test E2B Desktop
curl -f http://localhost:6080/health || echo "E2B Desktop unhealthy"

# Test NATS connectivity
nats pub "test.e2b.v1" "test message"
nats sub "test.e2b.v1" --count 1
```

### Support

For issues or questions:
1. Check logs: `docker logs pmoves-e2b-<service>-1`
2. Check NATS: `nats server report connections`
3. Review Grafana: http://localhost:3000
4. Create issue: [PMOVES.AI Issues](https://github.com/POWERFULMOVES/PMOVES.AI/issues)
