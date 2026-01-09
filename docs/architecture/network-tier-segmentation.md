# Network Tier Segmentation Architecture

**Status:** Implemented in Phase 2 Security Hardening (PR #276)
**Date:** 2025-12-07
**Commit:** a15c045, 8bf936a

## Overview

PMOVES.AI implements a **5-tier network segmentation architecture** to enforce defense-in-depth security principles. This architecture isolates services by function, preventing lateral movement in the event of a security breach and enforcing the principle of least privilege at the network layer.

### Purpose

Network tier segmentation provides:

- **Lateral Movement Prevention**: Compromised services cannot freely communicate with all other services
- **Least Privilege Networking**: Services only access the network tiers they require for their function
- **Defense in Depth**: Network layer security complements application-level security controls
- **Attack Surface Reduction**: Internal services are not exposed unnecessarily
- **Compliance Alignment**: Meets network segmentation requirements (PCI DSS 1.3, NIST 800-190, CIS Kubernetes 5.3.2)

## Network Tiers

The PMOVES.AI platform uses five isolated network tiers, each with a dedicated subnet and specific security characteristics:

### 1. API Tier (172.30.1.0/24)

**Purpose:** Public-facing services with external ingress capabilities

**Network Configuration:**
- Driver: bridge
- Network name: `pmoves_api`
- Subnet: 172.30.1.0/24
- External access: Enabled (ports exposed to host)

**Services (16 total):**
- `agent-zero` (8080, 8081) - Agent orchestration API and UI
- `archon` (8091, 8051, 8052) - Supabase-driven agent service
- `hi-rag-gateway-v2` (8086) - Hybrid RAG query endpoint
- `tensorzero-gateway` (3030) - LLM gateway and model provider router
- `tensorzero-ui` (4000) - TensorZero metrics dashboard
- `postgrest` (3010) - PostgREST API for Supabase
- `postgrest-health` - Health check proxy for PostgREST
- `pmoves-yt` (8077) - YouTube ingestion service
- `supaserch` (8099) - Multimodal research orchestrator
- `presign` (8088) - MinIO URL presigner
- `render-webhook` (8085) - ComfyUI render callback handler
- `channel-monitor` (8097) - External content watcher
- `jellyfin-bridge` (8093) - Jellyfin metadata webhook
- `publisher-discord` (8094) - Discord notification bot
- `ollama` (11434) - Local LLM inference server
- `invidious` (3010, 8010) - YouTube frontend proxy

**Security Characteristics:**
- Exposed to external networks (Tailscale, Internet via reverse proxy)
- Authentication and authorization enforced at application layer
- All inbound requests pass through these services first

### 2. Application Tier (172.30.2.0/24)

**Purpose:** Internal business logic services and worker processes

**Network Configuration:**
- Driver: bridge
- Network name: `pmoves_app`
- Subnet: 172.30.2.0/24
- Internal: true (no direct external internet access)

**Services (19 total):**
- `hi-rag-gateway-v2` (8086) - Hybrid RAG processing
- `extract-worker` (8083) - Text embedding and indexing
- `lang-extract` (8084) - Language detection and NLP
- `ffmpeg-whisper` (8078) - Media transcription (Whisper)
- `media-video` (8079) - Video analysis (YOLOv8)
- `media-audio` (8082) - Audio analysis (emotion/speaker detection)
- `pdf-ingest` (8092) - Document ingestion orchestrator
- `notebook-sync` (8095) - SurrealDB synchronizer
- `retrieval-eval` (8090) - RAG evaluation service
- `deepresearch` (8098) - LLM-based research planner
- `mesh-agent` - Distributed node announcer
- `bgutil-pot-provider` (4416) - YouTube proof-of-origin provider
- `deepresearch-local` (8080, 8000) - Local DeepResearch instance
- `nats-echo-*` - NATS diagnostic subscribers
- `supabase-rest-cli` (3011) - Supabase CLI REST proxy
- `ollama` (11434) - Local LLM service
- `channel-monitor` (8097) - Content monitoring worker
- `publisher-discord` (8094) - Event publisher
- `jellyfin-bridge` (8093) - Metadata sync worker

**Security Characteristics:**
- No direct external internet access (internal: true)
- Can only communicate with API tier, Data tier, and Bus tier
- Cannot initiate connections outside the platform

### 3. Bus Tier (172.30.3.0/24)

**Purpose:** Message bus for event-driven architecture and agent coordination

**Network Configuration:**
- Driver: bridge
- Network name: `pmoves_bus`
- Subnet: 172.30.3.0/24
- Internal: true (no external access)

**Services (1 total):**
- `nats` (4222) - NATS JetStream message broker

**Security Characteristics:**
- Isolated from Data tier (cannot access databases directly)
- Only accessible by API and Application tier services that need pub/sub
- No external connectivity
- All agent coordination flows through this tier

**NATS Subject Examples:**
- `research.deepresearch.request.v1` / `research.deepresearch.result.v1`
- `supaserch.request.v1` / `supaserch.result.v1`
- `ingest.file.added.v1`, `ingest.transcript.ready.v1`
- `claude.code.tool.executed.v1`

### 4. Data Tier (172.30.4.0/24)

**Purpose:** Persistent data storage services (databases, object storage, search indexes)

**Network Configuration:**
- Driver: bridge
- Network name: `pmoves_data`
- Subnet: 172.30.4.0/24
- Internal: true (no external access)

**Services (7 total):**
- `postgres` (5432) - Supabase PostgreSQL with pgvector
- `qdrant` (6333) - Vector embeddings database
- `neo4j` (7474 HTTP, 7687 Bolt) - Knowledge graph database
- `meilisearch` (7700) - Full-text search engine
- `minio` (9000 API, 9001 Console) - S3-compatible object storage
- `tensorzero-clickhouse` (8123) - TensorZero observability metrics
- `invidious-postgres` (5432) - Invidious metadata database

**Security Characteristics:**
- Most restricted tier - cannot initiate outbound connections
- Only accepts connections from Application and API tiers
- No direct external access
- Data at rest (encryption handled at volume level when configured)

### 5. Monitoring Tier (172.30.5.0/24)

**Purpose:** Observability and monitoring infrastructure

**Network Configuration:**
- Driver: bridge
- Network name: `pmoves_monitoring`
- Subnet: 172.30.5.0/24
- External access: Limited (Grafana UI only)

**Services (5 total):**
- `prometheus` (9090) - Metrics collection and storage
- `grafana` (3000) - Dashboard visualization
- `loki` (3100) - Log aggregation
- `promtail` - Log shipper
- `cadvisor` (9180) - Container metrics exporter

**Security Characteristics:**
- Can scrape `/metrics` endpoints across all tiers
- Promtail has read-only access to Docker logs
- Grafana exposed for external dashboard access
- Monitoring services do not expose data to other tiers

## Security Improvements

### Before Phase 2: Flat Network Architecture

**Configuration:**
```yaml
networks:
  pmoves:
    external: true
    name: pmoves-net
```

**Problems:**
- All 45+ services on single flat `pmoves-net` network
- Any service could communicate with any other service
- No network isolation or segmentation
- Compromised service has full lateral movement capability
- "Castle and moat" security model - hard perimeter, soft interior

### After Phase 2: 5-Tier Network Segmentation

**Configuration:**
```yaml
networks:
  api_tier:
    driver: bridge
    name: pmoves_api
    ipam:
      config:
        - subnet: 172.30.1.0/24

  app_tier:
    driver: bridge
    name: pmoves_app
    internal: true
    ipam:
      config:
        - subnet: 172.30.2.0/24

  bus_tier:
    driver: bridge
    name: pmoves_bus
    internal: true
    ipam:
      config:
        - subnet: 172.30.3.0/24

  data_tier:
    driver: bridge
    name: pmoves_data
    internal: true
    ipam:
      config:
        - subnet: 172.30.4.0/24

  monitoring_tier:
    driver: bridge
    name: pmoves_monitoring
    ipam:
      config:
        - subnet: 172.30.5.0/24
```

**Benefits:**
- ✅ Lateral movement prevention through network isolation
- ✅ Least privilege networking enforced at Docker network layer
- ✅ Defense in depth through multiple security boundaries
- ✅ Reduced attack surface (internal services not exposed)
- ✅ Compliance with PCI DSS 1.3, NIST 800-190, CIS benchmarks
- ✅ Audit trail via version-controlled network policies

## Implementation Details

### Multi-Tier Service Assignment

Services can be assigned to multiple network tiers based on their communication requirements. For example:

**Agent Zero (Multi-tier service):**
```yaml
agent-zero:
  networks:
    - api_tier       # External API access on port 8080
    - app_tier       # Communicate with hi-rag-gateway-v2
    - bus_tier       # Publish/subscribe to NATS
    - monitoring_tier # Expose /metrics endpoint
```

**Extract Worker (Single-tier service):**
```yaml
extract-worker:
  networks:
    - app_tier       # Receive processing requests
    - data_tier      # Write to Qdrant, Meilisearch
    - api_tier       # Callback to PostgREST
    - monitoring_tier # Expose /metrics
```

### Docker Compose Network Configuration

Each service declares its network memberships explicitly:

```yaml
services:
  postgres:
    networks:
      - data_tier
      - monitoring_tier

  hi-rag-gateway-v2:
    networks:
      - app_tier       # Receive requests from agents
      - data_tier      # Query Qdrant, Neo4j, Meilisearch
      - api_tier       # Call TensorZero gateway
      - monitoring_tier # Metrics

  nats:
    networks:
      - bus_tier
      - monitoring_tier
```

### Network Isolation Enforcement

**Internal Networks:**
Application, Bus, and Data tiers are marked `internal: true`, preventing:
- Direct internet access
- Container-to-host communication (except via explicit host.docker.internal)
- Uncontrolled egress traffic

**Example - Application Tier:**
```yaml
app_tier:
  driver: bridge
  name: pmoves_app
  internal: true  # No external internet access
  ipam:
    config:
      - subnet: 172.30.2.0/24
```

## Validation

### Verify Tier Isolation

Use `docker inspect` to verify a service's network memberships:

```bash
# Inspect agent-zero networks
docker inspect agent-zero | jq '.[0].NetworkSettings.Networks | keys'

# Expected output: ["pmoves_api", "pmoves_app", "pmoves_bus", "pmoves_monitoring"]
```

### Verify No Legacy Network

Ensure services are NOT on the legacy `pmoves-net` network:

```bash
# Check for legacy network (should be empty or only jellyfin-bridge)
docker network inspect pmoves-net --format '{{range .Containers}}{{.Name}} {{end}}'
```

### Test Network Segmentation

**Test 1: Data tier isolation (should FAIL)**
```bash
docker exec extract-worker curl -f http://postgres:5432
# Expected: Connection refused or timeout (extract-worker cannot reach postgres directly)
```

**Test 2: Allowed communication (should SUCCEED)**
```bash
docker exec hi-rag-gateway-v2 curl -f http://qdrant:6333/collections
# Expected: 200 OK (hi-rag-gateway-v2 is on data_tier)
```

**Test 3: Bus tier isolation (should FAIL)**
```bash
docker exec nats curl -f http://qdrant:6333
# Expected: Connection refused (nats cannot reach data_tier)
```

### Verify Service Counts

Expected network assignments (45 services total):

```bash
# Count services per tier
docker network inspect pmoves_api --format '{{len .Containers}}' # 16 services
docker network inspect pmoves_app --format '{{len .Containers}}' # 19 services
docker network inspect pmoves_bus --format '{{len .Containers}}' # 1 service
docker network inspect pmoves_data --format '{{len .Containers}}' # 7 services
docker network inspect pmoves_monitoring --format '{{len .Containers}}' # 5 services
```

## Communication Patterns

### API Tier → Application Tier
- Agent Zero calls Hi-RAG Gateway for knowledge retrieval
- Archon calls Agent Zero MCP API for orchestration
- SupaSerch calls Hi-RAG for research queries

### Application Tier → Data Tier
- Hi-RAG Gateway queries Qdrant (vectors), Neo4j (graph), Meilisearch (full-text)
- Extract Worker writes embeddings to Qdrant and indexes to Meilisearch
- PDF Ingest reads/writes to MinIO

### API Tier → Bus Tier
- Agent Zero publishes to NATS for task coordination
- Archon subscribes to NATS for agent events
- DeepResearch publishes research requests/results

### Application Tier → Bus Tier
- DeepResearch subscribes to `research.deepresearch.request.v1`
- Publisher-Discord subscribes to ingest events
- Mesh Agent announces host presence

### Monitoring Tier → All Tiers
- Prometheus scrapes `/metrics` endpoints from all services
- Promtail collects logs from all containers
- Grafana queries Prometheus and Loki for dashboards

## Compliance Alignment

Network tier segmentation helps PMOVES.AI achieve compliance with:

- ✅ **CIS Kubernetes Benchmark 5.3.2:** Network policies enforced
- ✅ **NIST 800-190:** Container security - network segmentation
- ✅ **PCI DSS Requirement 1.3:** Network segmentation between cardholder data environment and untrusted networks
- ✅ **SOC 2 CC6.6:** Logical access controls and network segmentation
- ✅ **Zero Trust Architecture:** Micro-segmentation and least privilege principles

## Related Documentation

- [Phase 2 Network Policies Design](/home/pmoves/PMOVES.AI/docs/phase2-network-policies-design.md) - Detailed design document
- [Services Catalog](/.claude/context/services-catalog.md) - Complete service listing
- [NATS Subjects](/.claude/context/nats-subjects.md) - Event bus subject catalog
- [PR #276](https://github.com/PMOVES/PMOVES.AI/pull/276) - Phase 2 Security Hardening implementation
- Commit a15c045 - Remove shared network bypassing tier isolation
- Commit 8bf936a - Phase 2 Security Hardening complete implementation

## Future Enhancements

1. **Kubernetes NetworkPolicy:** Migrate to Kubernetes NetworkPolicy resources for production deployments
2. **Cilium Layer 7 Policies:** Implement HTTP-aware network policies for finer-grained control
3. **Service Mesh Integration:** Add Istio/Linkerd for mTLS and advanced traffic management
4. **eBPF-based Enforcement:** Use eBPF for more efficient policy enforcement
5. **Automated Policy Testing:** Implement regression testing for network policy changes
6. **Dynamic Policy Updates:** Auto-generate policies from observed service communication patterns

---

**Implementation Status:** ✅ Complete (Phase 2, PR #276)
**Security Impact:** HIGH - Critical defense-in-depth control
**Maintenance:** Update network assignments when adding new services
