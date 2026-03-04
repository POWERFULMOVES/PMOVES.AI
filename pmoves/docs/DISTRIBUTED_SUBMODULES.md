# PMOVES.AI Distributed Submodule Deployment

This guide explains how to deploy PMOVES submodules (BoTZ, DoX, Tokenism) across different hardware while maintaining connectivity via local network, Tailscale mesh VPN, or self-hosted VPS.

## Overview

PMOVES.AI supports three deployment modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Standalone** | All services on single host using Docker DNS | Development, single-machine deployment |
| **Docked** | Submodules connect to parent PMOVES.AI services | Production with central infrastructure |
| **Distributed** | Submodules on separate hosts, cross-network connectivity | Hybrid deployments, edge computing, VPS |

## Network Topology Options

### 1. Local Network (192.168.x.x)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Local Network (192.168.1.0/24)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│   │  192.168.1.10    │  │  192.168.1.20    │  │  192.168.1.30    │      │
│   │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │      │
│   │  │ PMOVES-DoX │  │  │  │ PMOVES-BoTZ│  │  │  │ Tokenism   │  │      │
│   │  │   :8484    │  │  │  │   :2091    │  │  │  │   :5000    │  │      │
│   │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │      │
│   │  RTX 4090 GPU    │  │  RTX 5090 GPU    │  │  RTX 3090Ti GPU  │      │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Best for**: AI Lab setups, high-bandwidth workloads, GPU-intensive processing.

### 2. Tailscale Mesh (100.x.x.x)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Tailscale Mesh VPN                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐      ┌─────────────────┐     ┌──────────────────┐    │
│   │ 100.64.1.10     │      │ 100.64.1.20     │     │ 100.64.1.30      │    │
│   │ pmoves-dox      │←────→│ pmoves-botz     │←───→│ pmoves-tokenism  │    │
│   │ Home Network    │      │ Office Network  │     │ Remote Site      │    │
│   └─────────────────┘      └─────────────────┘     └──────────────────┘    │
│           │                         │                       │               │
│           │                         │                       │               │
│   ┌───────▼───────┐        ┌───────▼───────┐      ┌────────▼────────┐     │
│   │ Jetson Orin   │        │ Jetson Orin   │      │ VPS Node        │     │
│   │ 100.64.1.40   │        │ 100.64.1.50   │      │ 100.64.1.60     │     │
│   │ Edge Inference│        │ Edge Inference│      │ API Gateway     │     │
│   └───────────────┘        └───────────────┘      └─────────────────┘     │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

**Best for**: Geographically distributed teams, edge deployments, cross-network connectivity.

### 3. VPS Deployment (Public IPs)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Hostinger KVM Cluster                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐      ┌─────────────────┐     ┌──────────────────┐    │
│   │ KVM4-1          │      │ KVM4-2          │     │ KVM2             │    │
│   │ API Gateway     │      │ Data Services   │     │ Exit Node/Proxy  │    │
│   │ BoTZ MCP        │      │ DoX Backend     │     │ Tailscale Exit   │    │
│   │ :2091, :8100    │      │ :8484, :4222    │     │ WireGuard        │    │
│   └────────┬────────┘      └────────┬────────┘     └────────┬─────────┘    │
│            │                        │                       │               │
│            └────────────────────────┼───────────────────────┘               │
│                                     │                                       │
│                             WireGuard/Tailscale                             │
│                                     │                                       │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                              Home Network                                   │
│                                     │                                       │
│   ┌─────────────────────────────────▼───────────────────────────────────┐  │
│   │              GPU Workstations (RTX 4090/5090/3090Ti)                │  │
│   │              Tokenism, Local Inference, Development                  │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

**Best for**: Public API endpoints, multi-tenant services, cost-effective CPU workloads.

## Port Allocation Matrix

| Service | DoX Standalone | BoTZ Standalone | Docked (Parent) |
|---------|---------------|-----------------|-----------------|
| DoX Backend | 8484 | - | 8484 |
| DoX Frontend | 3001 | - | 3001 |
| BoTZ Gateway | - | 2091 | 2091 |
| BoTZ MCP Bridge | - | 8100 | 8100 |
| NATS Core | 4223 | 4222 | 4222 |
| NATS WebSocket | 9223 | 9222 | 9222 |
| NATS Monitoring | 8223 | 8222 | 8222 |
| Cipher Memory | 8081 | 8081 | 8081 |
| Docling MCP | 3020 | 3020 | 3020 |
| E2B Sandbox | - | 7071 | 7071 |
| VL Sentinel | - | 7072 | 7072 |
| TensorZero | 3030 | 3030 | 3000 |
| Tokenism | - | - | 5000 |

## Quick Start

### Prerequisites

1. Docker and Docker Compose v2 on all hosts
2. Network connectivity between hosts (direct, Tailscale, or WireGuard)
3. TLS certificates for NATS (see `generate-certs.sh`)

### DoX Distributed Deployment

```bash
cd PMOVES-DoX

# Copy distributed config
cp env.distributed.example .env.distributed

# Edit for your network topology
# - Set service hosts (local IPs, Tailscale IPs, or hostnames)
# - Configure TLS if required
nano .env.distributed

# Generate NATS TLS certificates (for distributed mode)
chmod +x backend/nats-config/generate-certs.sh
./backend/nats-config/generate-certs.sh

# Start with distributed overlay
docker compose -f docker-compose.yml -f docker-compose.distributed.yml --env-file .env.distributed up -d
```

### BoTZ Distributed Deployment

```bash
cd PMOVES-BoTZ

# Copy distributed config
cp env.distributed.example .env

# Edit for your network topology
nano .env

# Start with distributed overlay
docker compose -f docker-compose.yml -f docker-compose.distributed.yml up -d

# With optional profiles
docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --profile cipher --profile tools up -d
```

### With Tailscale

```bash
# Set Tailscale auth key
export TAILSCALE_AUTHKEY=tskey-auth-xxxxx

# Start with Tailscale sidecar
docker compose -f docker-compose.yml -f docker-compose.distributed.yml \
  --profile tailscale up -d
```

## Security Requirements

### 1. NATS TLS (Required for Distributed)

All distributed deployments **must** use TLS for NATS connections:

```bash
# Generate certificates
./backend/nats-config/generate-certs.sh

# Enable in environment
export NATS_TLS_ENABLED=true
```

### 2. JWT Authentication (Required for BoTZ Gateway)

The MCP Gateway requires JWT authentication in distributed mode:

```bash
# Set in environment
export SUPABASE_JWT_SECRET=your-secure-jwt-secret
```

Protected endpoints:
- `/call` - Tool execution
- `/mcp` - MCP JSON-RPC
- `/tools/*` - Tool management
- `/servers/*` - Server management

### 3. Network Segmentation

PMOVES uses 5-tier network segmentation:

| Tier | Purpose | Subnet (DoX) | Subnet (BoTZ) |
|------|---------|--------------|---------------|
| API | External access | 172.31.1.0/24 | 172.32.1.0/24 |
| App | Internal services | 172.31.2.0/24 | 172.32.2.0/24 |
| Bus | Message bus | 172.31.3.0/24 | 172.32.3.0/24 |
| Data | Databases | 172.31.4.0/24 | 172.32.4.0/24 |
| Monitor | Observability | 172.31.5.0/24 | 172.32.5.0/24 |

## Environment Variables

### Common Variables

```bash
# Deployment mode
PMOVES_NETWORK_MODE=distributed
DISTRIBUTED_SERVICES=true

# NATS with TLS
NATS_TLS_ENABLED=true
NATS_HOST=100.64.1.20  # Tailscale IP or hostname
NATS_PORT=4222

# Cross-service URLs
BOTZ_GATEWAY_URL=http://100.64.1.10:2091
DOX_BACKEND_URL=http://100.64.1.20:8484
TOKENISM_URL=http://100.64.1.30:5000

# TensorZero (central LLM gateway)
TENSORZERO_URL=http://100.64.1.10:3030
```

### Tailscale Variables

```bash
TAILSCALE_ENABLED=true
TAILSCALE_AUTHKEY=tskey-auth-xxxxx
TAILSCALE_HOSTNAME=pmoves-dox
TAILSCALE_ADVERTISE_ROUTES=172.31.0.0/16
```

## Health Checks

### Per-Service Health Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| DoX Backend | `GET /healthz` | `{"status": "ok"}` |
| DoX Frontend | `GET /api/health` | `200 OK` |
| BoTZ Gateway | `GET /health` | `{"status": "healthy"}` |
| BoTZ MCP Bridge | `GET /healthz` | `200 OK` |
| NATS | `GET :8222/healthz` | `{"status": "ok"}` |

### Cross-Service Connectivity Test

```bash
# Test from DoX to BoTZ
curl -f http://$BOTZ_HOST:2091/health

# Test from BoTZ to DoX
curl -f http://$DOX_HOST:8484/healthz

# Test NATS connectivity (with TLS)
nats-cli --tlscert=certs/client.crt --tlskey=certs/client.key \
  --tlsca=certs/ca.crt pub test.ping "hello"
```

## Troubleshooting

### Connection Refused

1. Check firewall rules allow the required ports
2. Verify service is listening on 0.0.0.0 (not 127.0.0.1)
3. Check Docker network mode (should not be internal for distributed)

### TLS Handshake Failed

1. Verify certificates are mounted correctly
2. Check certificate validity dates
3. Ensure SANs include the hostname being used

### NATS WebSocket Connection Failed

1. For TLS, frontend must use `wss://` (not `ws://`)
2. Check CORS settings allow the origin
3. Verify WebSocket port is exposed

### Tailscale Not Connecting

1. Verify auth key is valid and not expired
2. Check `TS_EXTRA_ARGS` for correct routes
3. Ensure `/dev/net/tun` is mounted

## Related Documentation

- [DoX Distributed Deployment](../integrations/PMOVES-DoX/docs/DISTRIBUTED_DEPLOYMENT.md)
- [BoTZ Distributed Deployment](../integrations/PMOVES-BoTZ/docs/DISTRIBUTED_DEPLOYMENT.md)
- [Supabase Distributed Setup](./services/supabase/SUPABASE_DISTRIBUTED.md)
- [Tailscale Setup Script](../scripts/tailscale_setup.sh)
