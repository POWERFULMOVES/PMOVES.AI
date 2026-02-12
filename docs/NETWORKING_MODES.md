# PMOVES.AI Networking Modes

**Last Updated**: 2026-02-12

## Overview

PMOVES.AI services integrate via runtime networking (NATS, gRPC, HTTP) rather than git nesting. This enables a "holographic" architecture where services can team up dynamically in different operational modes.

## Core Principle

```
Git Submodules = Code Ownership
Networking Integrations = Runtime Collaboration
```

## Operational Modes

### Standalone Mode

**Description**: Service runs independently with all local resources.

**Characteristics**:
- Local Ollama for LLM inference
- Local Cipher memory
- Local Qdrant/FAISS for vector storage
- No dependency on parent PMOVES.AI infrastructure

**Example Use Cases**:
- Development and testing
- Single-user deployments
- Offline operation

**Configuration**:
```bash
# All services run locally
OLLAMA_BASE_URL=http://ollama:11434
CIPHER_URL=http://cipher:8080
QDRANT_URL=http://qdrant:6333
```

### Docked Mode

**Description**: Service connects to parent PMOVES.AI infrastructure.

**Characteristics**:
- Shared TensorZero gateway for LLM routing
- Parent NATS bus for event messaging
- Shared Qdrant cluster for vector storage
- Centralized logging and monitoring

**Example Use Cases**:
- Production multi-service deployments
- Resource sharing and optimization
- Unified observability

**Configuration**:
```bash
# Connect to parent infrastructure
TENSORZERO_URL=http://tensorzero:3000
NATS_URL=nats://parent-nats:4222
QDRANT_URL=http://parent-qdrant:6333
```

### Hybrid Mode

**Description**: Service mixes local and parent resources based on configuration.

**Characteristics**:
- Selective use of parent services
- Local fallback for critical operations
- Configurable per-service routing

**Example Use Cases**:
- Gradual migration to docked mode
- Development with partial parent integration
- Edge deployments with selective cloud dependencies

**Configuration**:
```bash
# Mix local and parent
LLM_PROVIDER=tensorzero  # Use parent
VECTOR_STORE=local        # Use local
MEMORY=cipher            # Use local
```

## Networking Protocols

### NATS (Message Bus)

**Purpose**: Event-driven communication between services.

**Subjects Pattern**:
```
geometry.>           # Geometry events
tokenism.cgp.>        # CHIT Geometry Packets
pmoves.>              # PMOVES events
service.>             # Service lifecycle
```

**Connection URLs**:
- **Standalone**: `nats://localhost:4222`
- **Docked**: `nats://parent-nats:4222`
- **WebSocket**: `ws://localhost:9223` (standalone), `ws://localhost:9222` (docked)

### gRPC

**Purpose**: High-performance RPC between services.

**Services**:
- TensorZero gateway
- Cipher memory
- Qdrant vector store

### HTTP/REST

**Purpose**: Public API endpoints and webhooks.

**Examples**:
- Agent Zero MCP endpoint: `http://localhost:50051/mcp/<token>/sse`
- DoX API: `http://localhost:8000`
- Archon API: `http://localhost:8181`

## Service Integration Examples

### PMOVES-Wealth as Host

PMOVES-Wealth hosts other services as "holograms":

```
PMOVES-Wealth (HOST)
├── NATS bus for events
├── gRPC/HTTP APIs
└── Holographic services (NOT git submodules):
    ├── PMOVES-DoX (dockable)
    └── PMOVES-ToKenism-Multi (dockable)
```

**Integration**:
1. Services register via NATS on startup
2. Health checks via HTTP endpoints
3. Data exchange via shared Qdrant cluster
4. No git relationship - pure runtime networking

### PMOVES-DoX Geometry Bus

CHIT Geometry Packets flow via NATS:

```
PMOVES-DoX → NATS → Frontend
└── Publishes: geometry.>
            └── tokenism.cgp.>
```

**Connection**:
- **Standalone**: `ws://localhost:9223`
- **Docked**: `ws://localhost:9222` (parent NATS)

## Docker Networking

### Bridge Networks

Services connect via Docker bridge networks:

```yaml
# docker-compose.yml
networks:
  pmoves:
    driver: bridge
  parent:
    external: true  # Parent network in docked mode

services:
  dox:
    networks:
      - pmoves
      - parent  # Only in docked mode
```

### Service Discovery

Services discover each other via:
1. DNS (Docker internal DNS)
2. NATS service announcements
3. Environment-based configuration

## Configuration Patterns

### Environment Variables

```bash
# Mode selection
PMOVES_MODE=standalone|docked|hybrid

# Service URLs
NATS_URL=nats://...
TENSORZERO_URL=http://...
QDRANT_URL=http://...

# Feature flags
USE_PARENT_NATS=true
USE_PARENT_TENSORZERO=false
```

### Docker Compose Profiles

```yaml
services:
  dox:
    profiles:
      - standalone
      - docked
```

Usage:
```bash
# Standalone
docker compose up

# Docked
docker compose --profile docked up
```

## Migration Paths

### Standalone → Docked

1. Update environment variables to point to parent services
2. Join parent Docker network
3. Verify health checks pass
4. Gradually migrate features

### Docked → Standalone

1. Deploy local versions of dependencies
2. Update environment variables
3. Leave parent Docker network
4. Verify all features work locally

## Troubleshooting

### Service Not Discoverable

```bash
# Check NATS connection
curl http://localhost:8222/varz

# Check Docker network
docker network inspect pmoves

# Check service registration
nats sub "service.>"
```

### Mode Switching Issues

```bash
# Verify environment
env | grep PMOVES

# Reset configuration
docker compose down -v
docker compose up --build
```

### Network Isolation

```bash
# Test connectivity
docker exec dox curl http://tensorzero:3000/health

# Check DNS
docker exec dox nslookup tensorzero
```

## Security Considerations

### Docked Mode

- Requires parent network access
- Service-to-service authentication
- Token-based API access
- Network policies for isolation

### Standalone Mode

- All resources local
- No external dependencies
- Full control over data

## Best Practices

1. **Start in Standalone**: Develop and test locally first
2. **Add Docking Gradually**: Migrate services one at a time
3. **Use Environment Variables**: Control modes via configuration
4. **Health Checks**: Implement `/health` endpoints on all services
5. **Graceful Degradation**: Fall back to local if parent unavailable
6. **Service Registration**: Announce presence via NATS on startup
7. **Observability**: Central logging in docked mode

## References

- [NATS Documentation](https://docs.nats.io/)
- [gRPC Documentation](https://grpc.io/docs/)
- [Docker Networking](https://docs.docker.com/network/)
- [SUBMODULE_ARCHITECTURE.md](./SUBMODULE_ARCHITECTURE.md)
