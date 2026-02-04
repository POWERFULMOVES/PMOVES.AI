# PMOVES.AI Documentation Index

**Last Updated:** 2026-02-04
**Phase:** Phase 2.5 - Container Hardening Complete (92/100 Security)

## Quick Navigation

| I want to... | Go to |
|--------------|-------|
| Get started quickly | [First Run Guide](#first-run) |
| Deploy to production | [Production Deployment](#production-deployment) |
| Deploy to Hostinger VPS | [Hostinger VPS Guide](#hostinger-vps) |
| Understand security hardening | [Security Hardening](#security-hardening) |
| Troubleshoot issues | [Troubleshooting](#troubleshooting) |
| Find a specific service | [Service Catalog](#service-catalog) |
| Deploy on multiple hosts | [Multi-Host Deployment](#multi-host-deployment) |

---

## Getting Started

### First Run Guide
**File:** `docs/FIRST_RUN.md`

One-command full stack startup:
```bash
make first-run
```

Covers:
- Environment bootstrap (`make bootstrap`)
- Supabase backend setup
- Core services startup
- Agent mesh initialization
- Smoke test validation

### Development Setup
**File:** `docs/LOCAL_DEV.md`

- Conda environment setup
- Python 3.11 configuration
- Windows/macOS/Linux compatibility
- Local service debugging

---

## Production Deployment

### Production Getting Started
**File:** `docs/PRODUCTION_GETTING_STARTED.md`

Prerequisites:
- `make check-tools` - Verify required tools
- `make check-tier-envs` - Validate environment files
- Docker with BuildKit enabled
- 16GB RAM minimum (32GB recommended)

### Production Single Host
**File:** `docs/PRODUCTION_SINGLE_HOST.md`

7-Phase deployment:
1. Pre-deployment validation
2. Observability stack (Prometheus, Grafana, Loki)
3. Data tier (Supabase, Qdrant, Neo4j, Meilisearch, MinIO)
4. Message bus (NATS)
5. Worker services
6. TensorZero Gateway
7. Agent services

### Production Multi Host
**File:** `docs/PRODUCTION_MULTI_HOST.md`

Distributed deployment across multiple hosts:
- Tailscale networking
- Service placement by tier
- Cross-host communication
- Resource optimization

### Production Environment
**File:** `docs/PRODUCTION_ENVIRONMENT.md`

Environment configuration:
- Tier-based secrets architecture
- Network isolation (6-tier model)
- Resource limits
- Monitoring configuration

### Production Hardened
**File:** `docs/PRODUCTION_HARDENED.md`

**Security Score: 92/100** (Phase 2.5 Complete)

Container hardening applied to all 63 services:
- `x-hardening`: Stateless services (read-only rootfs)
- `x-hardening-rw`: Read-write services
- `x-hardening-database`: Database services with extended capabilities
- `x-hardening-external`: Services needing internet access
- `x-hardening-media`: Media processors with larger tmpfs

### Production Validation
**File:** `docs/PRODUCTION_VALIDATION.md`

Health checks and validation:
- `make verify-all` - Full verification
- Smoke tests by tier
- Dependency validation
- Network connectivity tests

### Production Troubleshooting
**File:** `docs/PRODUCTION_TROUBLESHOOTING.md`

Common issues and solutions:
- Container startup failures
- Network connectivity
- Resource constraints
- Database migration errors

### Production Supabase
**File:** `docs/PRODUCTION_SUPABASE.md`

Supabase integration:
- 7-service stack
- Migration management
- RLS policies
- JWT configuration
- Connection pooling

---

## Hostinger VPS Deployment

### Deployment Guide
**File:** `docs/HOSTINGER_VPS_DEPLOYMENT.md`

Complete VPS deployment:
- Hardware requirements (8-16GB RAM)
- Docker installation
- Tailscale VPN setup
- Incremental build and deployment
- Resource optimization
- Monitoring and backups
- Cost optimization strategies

**Location:** `deploy/runners/vps/`
- `install.sh` - Standard runner setup
- `install-hardened.sh` - Hardened setup with rootless Docker
- `QUICKSTART.md` - Quick start guide
- `README.md` - Full documentation

**Environment variables:**
- `HOSTINGER_API_TOKEN` - API access
- `HOSTINGER_SSH_*` - SSH credentials
- `HOSTINGER_PROJECT_ID` - Project identifier

### VPS Docker Compose Override
**File:** `docker-compose.vps.override.yml`

CPU-optimized configuration for VPS environments.

---

## Security Hardening

### Security Overview
**Current Score:** 92/100 (+34 from baseline)

| Category | Score | Notes |
|----------|-------|-------|
| Container Hardening | 20/20 | All 63 services hardened |
| Image Pinning | 13/15 | 11/11 :latest pinned, 4 pmoves-latest remain |
| Network Isolation | 20/20 | 6-tier model with internal flags |
| Secrets Management | 15/15 | 8-tier isolation |
| Monitoring | 10/10 | All systems operational |
| RBAC | 10/10 | Service-tier based |
| Compliance | 4/5 | Hardening complete |

### Network Architecture (6-Tier)
1. **pmoves_data** - Data tier (internal)
2. **pmoves_api** - API tier (internal)
3. **pmoves_app** - Application tier (internal)
4. **pmoves_bus** - Message bus (internal)
5. **pmoves_monitoring** - Observability (internal)
6. **pmoves_external** - External access (non-internal)

### Container Hardening Templates
**File:** `pmoves/docker-compose.yml` (lines 164-238)

```yaml
x-hardening: &hardening          # Stateless, read-only
x-hardening-rw: &hardening-rw    # Read-write access
x-hardening-database: &hardening-database  # Databases
x-hardening-external: &hardening-external  # Internet access
x-hardening-media: &hardening-media        # Media processors
```

### Incremental Build Plan
**File:** `docs/INCREMENTAL_BUILD_PLAN.md**

Build services in waves to avoid Docker resource exhaustion:
- Wave 1: Core infrastructure (NATS, databases)
- Wave 2-9: Incremental service builds

---

## Service Catalog

### By Tier

#### Data Tier (7 services)
| Service | Port | Purpose |
|---------|------|---------|
| qdrant | 6333 | Vector database |
| neo4j | 7474/7687 | Graph database |
| meilisearch | 7700 | Full-text search |
| minio | 9000/9001 | Object storage |
| supabase-db | 54322 | PostgreSQL |
| tensorzero-clickhouse | 8123 | Metrics storage |

#### API Tier (15 services)
| Service | Port | Purpose |
|---------|------|---------|
| supabase-postgrest | 3010 | REST API |
| supabase-gotrue | 9999 | Auth |
| hi-rag-gateway-v2 | 8086/8087 | RAG API |
| presign | 8088 | MinIO presigner |
| render-webhook | 8085 | ComfyUI webhook |
| model-registry | 8110 | Model catalog |
| tensorzero-gateway | 3030 | LLM gateway |
| tensorzero-ui | 4000 | Metrics UI |
| agent-zero | 8080/8081 | Agent orchestrator |
| archon | 8091/3737 | Agent service |
| flute-gateway | 8055/8056 | TTS gateway |
| deepresearch | 8098 | Research planner |
| supaserch | 8099 | Multimodal search |
| pmoves-ui | 4482 | Main dashboard |

#### Application Tier (20 services)
| Service | Port | Purpose |
|---------|------|---------|
| extract-worker | 8083 | Embedding indexer |
| langextract | 8084 | NLP preprocessing |
| pdf-ingest | 8092 | PDF processing |
| notebook-sync | 8095 | Note synchronization |
| ffmpeg-whisper | 8078 | Transcription |
| media-video | 8079 | Video analysis |
| media-audio | 8082 | Audio analysis |
| pmoves-yt | 8077 | YouTube ingestion |
| channel-monitor | 8097 | Channel monitoring |
| retrieval-eval | 8090 | RAG evaluation |
| session-context-worker | 8100 | Context worker |

### By Function

#### Agent Services (4 services)
- **agent-zero** (8080/8081) - Control-plane orchestrator
- **archon** (8091/3737) - Supabase-driven agent service
- **mesh-agent** - Multi-host announcer
- **gateway-agent** - Mesh gateway

#### Media Services (7 services)
- **ffmpeg-whisper** (8078) - Whisper transcription
- **media-video** (8079) - YOLOv8 analysis
- **media-audio** (8082) - Audio analysis
- **pmoves-yt** (8077) - YouTube ingestion
- **channel-monitor** (8097) - Channel monitoring
- **ultimate-tts-studio** (7861) - Multi-engine TTS
- **flute-gateway** (8055/8056) - Voice gateway

#### Knowledge Services (5 services)
- **hi-rag-gateway** - Legacy RAG (v1)
- **hi-rag-gateway-v2** (8086/8087) - RAG v2 with reranking
- **hi-rag-gateway-gpu** - GPU-accelerated RAG
- **hi-rag-gateway-v2-gpu** - GPU RAG v2
- **retrieval-eval** (8090) - RAG evaluation dashboard

---

## Multi-Host Deployment

### Architecture
**File:** `docs/PRODUCTION_MULTI_HOST.md`

Supported deployment patterns:
- **Laptop + VPS** - Development + production
- **Laptop + 3 KVMs** - Full homelab
- **VPS Cluster** - Cloud-only deployment

### Tailscale Integration
All hosts connect via Tailscale VPN:
- Automatic peer discovery
- NAT traversal
- Mesh networking

---

## Troubleshooting

### Common Issues

#### Container Won't Start
1. Check logs: `docker compose logs <service>`
2. Verify environment: `make env-check`
3. Check dependencies: `docker compose ps`
4. See: `docs/PRODUCTION_TROUBLESHOOTING.md`

#### Build Failures
1. Clean build cache: `docker builder prune -f`
2. Check disk space: `df -h`
3. Verify BuildKit: `docker buildx version`
4. See: `docs/INCREMENTAL_BUILD_PLAN.md`

#### Network Issues
1. Verify networks: `docker network ls`
2. Check isolation: `docker network inspect pmoves_data`
3. Test connectivity: `docker compose exec <service> ping <other>`

---

## Additional Documentation

### Make Targets
**File:** `docs/MAKE_TARGETS.md` (if exists)

Complete list of make targets:
- `make up` - Start main stack
- `make down` - Stop all services
- `make ps` - Show running services
- `make logs` - Show logs
- `make verify-all` - Run all checks

### Smoke Tests
**File:** `docs/COMPREHENSIVE_SMOKE_TESTS.md`

Test coverage:
- Service health endpoints
- Database connectivity
- API functionality
- Agent operations

### Submodule Architecture
**File:** `docs/SUBMODULE_ARCHITECTURE.md`

20+ submodules:
- Agent frameworks
- Integration services
- UI components
- Tools and utilities

---

## Change Log

### 2026-02-04 - Phase 2.5 Complete
- Container hardening applied to all 63 services
- Security score improved from 58/100 to 92/100
- 6-tier network model implemented
- Legacy networks removed (pmoves-net, cataclysm-net, supabase_net)
- Image pinning: 11/11 :latest images pinned
- Documentation index consolidated

### Previous Changes
See Git commit history for detailed change log.

---

## Contributing

### Documentation Standards
- Use Markdown format
- Include code examples
- Cross-reference related docs
- Update date on each modification

### Documentation Location
All documentation lives in `pmoves/docs/`

### Pull Requests
1. Update relevant docs
2. Run smoke tests
3. Verify links work
4. Update this index

---

**For questions or issues, see:**
- GitHub Issues: `https://github.com/POWERFULMOVES/PMOVES.AI/issues`
- Troubleshooting: `docs/PRODUCTION_TROUBLESHOOTING.md`
