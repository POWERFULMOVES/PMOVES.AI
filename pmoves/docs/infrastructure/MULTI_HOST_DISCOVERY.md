# Multi-Host Service Discovery Guide

This guide covers setting up multi-host service discovery for PMOVES.AI, enabling services running on different machines to discover and communicate with each other.

## Overview

Multi-host discovery allows PMOVES.AI to:
- Run services across multiple machines (e.g., main PC + Jetson)
- Discover services dynamically without hardcoded IPs
- Maintain service health monitoring across hosts
- Scale horizontally by adding more nodes

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PMOVES.AI Mesh Network                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐         ┌─────────────┐         ┌─────┐  │
│  │   Main PC   │         │   Jetson    │         │ ... │  │
│  │  (docked)   │         │ (standalone)│         │     │  │
│  │             │         │             │         │     │  │
│  │ Agent Zero  │◄───────►│  PMOVES-DoX │◄───────►│     │  │
│  │ Archon      │  NATS   │   Jellyfin  │  Mesh   │     │  │
│  │ Hi-RAG v2   │  + TLS  │   Whisper   │ Network│     │  │
│  │ Service     │         │  Service    │         │     │  │
│  │ Registry    │         │  Registry   │         │     │  │
│  └─────────────┘         └─────────────┘         └─────┘  │
│         │                       │                      │      │
│         └───────────────────────┴──────────────────────┘      │
│                          Tailscale Mesh                        │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Setup Tailscale Mesh Network

On **each machine** that will be part of the mesh:

```bash
cd /path/to/PMOVES.AI/pmoves

# Run the mesh setup
make mesh-setup
```

This will:
1. Install Tailscale (if not installed)
2. Connect to the PMOVES mesh network
3. Generate a mesh configuration file
4. Show the Tailscale IP for this node

### 2. Configure Service Mode

Set the service mode in `pmoves/env.shared`:

```bash
# On main PC (docked mode - all services integrated)
SERVICE_MODE=docked

# On Jetson/standalone machines
SERVICE_MODE=standalone
```

### 3. Start Services

On each machine:
```bash
# Start services
make up

# Check service registry
make registry-status
```

### 4. Verify Discovery

```bash
# Show all discovered services
curl http://localhost:8100/api/services | jq

# Check specific service
curl http://localhost:8100/api/services/pmoves-dox | jq
```

## Network Configuration

### Tailscale (Primary)

Tailscale provides a zero-config VPN mesh:
- Automatic NAT traversal
- Stable 100.x.x.x IPs
- Built-in mDNS for discovery
- Works across different networks

**Get Tailscale Auth Key:**
1. Go to https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Set key as `TAILSCALE_AUTHKEY` in `env.shared`

**Mesh Configuration:**
```bash
# env.shared
PMOVES_MESH_NAME=pmoves-mesh
MESH_HOSTNAME=${HOSTNAME:-pmoves-node}
TAILSCALE_AUTHKEY=tskey-auth-...
```

### NATS TLS (Fallback)

If Tailscale is unavailable, NATS TLS provides direct encrypted connection:

```bash
# Generate TLS certificates
make nats-tls-setup

# This creates:
# - pmoves/nats/tls/ca.crt
# - pmoves/nats/tls/server.crt
# - pmoves/nats/tls/server.key
# - pmoves/nats/tls/client.crt
# - pmoves/nats/tls/client.key
```

**External NATS URL:**
```bash
# env.shared (on main PC)
NATS_EXTERNAL_URL=nats://100.100.100.1:4222
```

## Service Registry

The service registry is the central discovery hub:

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/services` | GET | List all services |
| `/api/services` | POST | Register/update service |
| `/api/services/{name}` | GET | Get specific service |
| `/api/discover` | POST | Discover by capabilities |
| `/api/status` | GET | Registry status |
| `/healthz` | GET | Health check |

### Registration Example

```python
import requests

# Register a service
response = requests.post("http://localhost:8100/api/services", json={
    "name": "my-service",
    "host": "100.100.100.5",  # Tailscale IP
    "port": 8080,
    "mode": "standalone",
    "capabilities": ["rag", "search"],
    "health_url": "http://100.100.100.5:8080/healthz"
})

print(response.json())
```

## Service Modes

### Docked Mode (Main PC)

All services run integrated:
- Shared Supabase database
- Shared MinIO storage
- Central NATS message bus
- Full observability stack

```yaml
# docker-compose.yml profiles
agents:      # Agent Zero, Archon, Mesh Agent
workers:     # Extract, Media Analyzers
orchestration:  # SupaSerch, DeepResearch
data:        # Qdrant, Neo4j, Meilisearch
monitoring:  # Prometheus, Grafana, Loki
```

### Standalone Mode (Edge Devices)

Selective services run independently:
- Local SQLite/database
- Service registry for discovery
- NATS for cross-host communication

```yaml
# docker-compose.yml profiles (standalone)
standalone:  # Service-specific services
discovery:   # Mesh Agent, Service Registry
```

## NATS Subjects

Cross-host communication uses NATS subjects:

| Subject | Purpose |
|---------|---------|
| `mesh.node.announce.v1` | Service announcements |
| `service.registry.*` | Registry events |
| `ingest.file.added.v1` | File ingestion events |
| `ingest.transcript.ready.v1` | Transcript ready |
| `claude.code.tool.executed.v1` | Claude CLI events |

## Common Scenarios

### Scenario 1: Jetson as Media Processor

**Jetson** (standalone):
- Runs FFmpeg-Whisper (transcription)
- Runs Media-Video Analyzer (YOLO)
- Announces on `mesh.node.announce.v1`

**Main PC** (docked):
- Receives transcript events
- Stores in Supabase
- Processes with RAG

### Scenario 2: Distributed RAG

**Multiple nodes** with Hi-RAG:
- Node 1: Qdrant (vectors)
- Node 2: Neo4j (graph)
- Node 3: Meilisearch (full-text)
- Node 4: Coordinator (aggregation)

### Scenario 3: GPU Offloading

**Main PC** (no GPU):
- Runs Agent Zero, Archon
- Orchestrates tasks

**GPU Node**:
- Runs Hi-RAG GPU variant
- Runs Ultimate TTS Studio
- Processes GPU-heavy workloads

## Troubleshooting

### Services not discovering each other

**Check Tailscale status:**
```bash
make mesh-status

# Or directly
tailscale status
```

**Verify NATS connection:**
```bash
# Check NATS is running
docker ps | grep nats

# Check NATS logs
docker logs nats
```

**Check service registry:**
```bash
make registry-status

curl http://localhost:8100/api/services
```

### Cannot access services on other host

**Verify Tailscale IP:**
```bash
# Get Tailscale IP
tailscale ip -4

# Ping other host
ping 100.100.100.x
```

**Check firewall:**
```bash
# Allow Tailscale
sudo ufw allow from 100.64.0.0/10

# Allow NATS
sudo ufw allow 4222
```

### Service health checks failing

**Verify health URL is accessible:**
```bash
# Test health endpoint
curl http://service-host:port/healthz

# Check from service container
docker exec <container> curl http://service-host:port/healthz
```

## Advanced Configuration

### Custom Mesh Name

```bash
# env.shared
PMOVES_MESH_NAME=my-custom-mesh
```

### Custom Capabilities

```bash
# env.shared
NODE_CAPABILITIES=rag,search,clip,whisper,video
```

### Service Filtering

Discover services by capability:
```bash
curl -X POST http://localhost:8100/api/discover -d '{
  "capabilities": ["rag", "search"]
}'
```

## Security Considerations

1. **Tailscale ACLs**: Configure access control lists
2. **NATS TLS**: Always use TLS for external connections
3. **Service Authentication**: Implement service-to-service auth
4. **Network Segmentation**: Separate guest/production mesh

## Monitoring

### Service Registry Metrics

```bash
# Registry status
curl http://localhost:8100/api/status | jq

# Service count
curl http://localhost:8100/api/status | jq '.registry.services'

# Health status
curl http://localhost:8100/api/services | jq '.services[] | select(.health_status != "healthy")'
```

### Mesh Node Monitoring

```bash
# Show all mesh nodes
make mesh-status

# Check specific node
tailscale ping <hostname>

# Show recent connections
tailscale status --peers
```

## See Also

- `docs/DOCKING_ARCHITECTURE.md` - Docking architecture details
- `docs/DYNAMIC_PORTS_GUIDE.md` - Port management
- `pmoves/scripts/tailscale_setup.sh` - Mesh setup script
- `pmoves/services/service-registry/` - Registry implementation
