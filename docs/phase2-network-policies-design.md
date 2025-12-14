# Phase 2 Task 2.4: Network Policies Design

**Status:** Design complete - Ready for TAC implementation
**Priority:** HIGH (Defense in depth, lateral movement prevention)
**Effort:** 1.5-2 hours with TAC
**Date:** 2025-12-06

> Update (2025-12-14): The runtime stack now uses a **5-tier** segmentation layout (as reflected in `pmoves/docker-compose.yml` and `docs/PMOVES.AI-Edition-Hardened-Full.md`). Treat this file as the original Phase 2 design notes; reconcile any drift by preferring the compose + hardened overlay and updating this document when making further network-policy changes.

## Overview

Network policies implement network segmentation to limit lateral movement, enforce least-privilege networking, and reduce attack surface. This design creates isolated network tiers with explicit allow rules for required communication.

## Current Network Architecture (as of 2025-12-14)

The runtime stack has moved from a flat `pmoves-net` model to a segmented **5-tier** layout implemented directly in `pmoves/docker-compose.yml` (plus optional hardening overlays).

**Source of truth:** `pmoves/docker-compose.yml` `networks:` stanza.

### Implemented Docker Compose networks

```yaml
networks:
  # 5-Tier Network Architecture for Defense in Depth
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

  # Legacy external network (maintain compatibility for jellyfin-bridge only)
  cataclysm:
    external: true
    name: cataclysm-net
```

### Practical meaning

- `internal: true` on `app_tier` / `bus_tier` / `data_tier` prevents direct internet egress from those networks (containers can still reach services on other attached networks).
- Public exposure is controlled via `ports:` mappings on services attached to `api_tier` / `monitoring_tier`.
- The legacy `cataclysm-net` remains for external integrations that historically ran outside the main segmented stack (e.g., Jellyfin bridge compatibility).

## Historical Network Architecture (pre 2025-12-14)

### Previous Network Configuration (historical)

**Networks:** (historical; kept here for context)
```yaml
networks:
  pmoves:
    external: true
    name: pmoves-net
  cataclysm:
    external: true
    name: cataclysm-net
```

**Current State:**
- All services on flat `pmoves-net` network
- No network segmentation
- Any service can communicate with any other service
- Lateral movement possible if one service compromised

**Security Issue:** "Castle and moat" - hard perimeter, soft interior.

## Network Segmentation Strategy

### Tier-Based Architecture

We'll implement a **4-tier network architecture** based on the Zero Trust principle: "Never trust, always verify."

```
┌─────────────────────────────────────────────────────────┐
│  External Networks (Internet, Tailscale)                │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │   API Tier (Public)     │  Port exposure, authentication
         │   - agent-zero          │
         │   - archon              │
         │   - pmoves-yt           │
         │   - supaserch           │
         │   - tensorzero-gateway  │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │ Application Tier        │  Business logic, workers
         │ - hi-rag-gateway-v2     │
         │ - extract-worker        │
         │ - langextract           │
         │ - ffmpeg-whisper        │
         │ - media-video           │
         │ - deepresearch          │
         │ - publisher-discord     │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │ Message Bus Tier        │  Event coordination
         │ - nats                  │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │ Data Tier               │  Persistence, storage
         │ - postgres              │
         │ - qdrant                │
         │ - neo4j                 │
         │ - meilisearch           │
         │ - minio                 │
         │ - clickhouse            │
         └─────────────────────────┘
```

## Service Communication Matrix

### Data Tier Services

**postgres** (Port 5432)
- **Incoming from:** postgrest, archon, channel-monitor
- **Outgoing to:** None
- **Protocol:** PostgreSQL (TCP 5432)

**qdrant** (Port 6333)
- **Incoming from:** hi-rag-gateway-v2, extract-worker
- **Outgoing to:** None
- **Protocol:** HTTP (TCP 6333)

**neo4j** (Ports 7474, 7687)
- **Incoming from:** hi-rag-gateway-v2
- **Outgoing to:** None
- **Protocol:** HTTP (7474), Bolt (7687)

**meilisearch** (Port 7700)
- **Incoming from:** hi-rag-gateway-v2, extract-worker
- **Outgoing to:** None
- **Protocol:** HTTP (TCP 7700)

**minio** (Ports 9000, 9001)
- **Incoming from:** pmoves-yt, ffmpeg-whisper, media-video, media-audio, pdf-ingest, presign
- **Outgoing to:** None
- **Protocol:** S3 HTTP (9000), Console (9001)

**tensorzero-clickhouse** (Port 8123)
- **Incoming from:** tensorzero-gateway, tensorzero-ui
- **Outgoing to:** None
- **Protocol:** HTTP (TCP 8123)

### Message Bus Tier

**nats** (Port 4222)
- **Incoming from:** agent-zero, archon, mesh-agent, deepresearch, supaserch, publisher-discord, channel-monitor, pmoves-yt
- **Outgoing to:** None
- **Protocol:** NATS (TCP 4222)

### Application Tier Services

**hi-rag-gateway-v2** (Port 8086)
- **Incoming from:** supaserch, pmoves-yt, retrieval-eval, agent-zero
- **Outgoing to:** qdrant, neo4j, meilisearch, ollama, tensorzero-gateway
- **Protocol:** HTTP (TCP 8086)

**extract-worker** (Port 8083)
- **Incoming from:** pdf-ingest, notebook-sync, pmoves-yt
- **Outgoing to:** qdrant, meilisearch, postgrest
- **Protocol:** HTTP (TCP 8083)

**langextract** (Port 8084)
- **Incoming from:** notebook-sync
- **Outgoing to:** None
- **Protocol:** HTTP (TCP 8084)

**ffmpeg-whisper** (Port 8078)
- **Incoming from:** pmoves-yt
- **Outgoing to:** minio
- **Protocol:** HTTP (TCP 8078)

**media-video** (Port 8079)
- **Incoming from:** pmoves-yt
- **Outgoing to:** minio
- **Protocol:** HTTP (TCP 8079)

**media-audio** (Port 8082)
- **Incoming from:** pmoves-yt
- **Outgoing to:** minio
- **Protocol:** HTTP (TCP 8082)

**deepresearch** (Port 8098)
- **Incoming from:** nats (subscriber)
- **Outgoing to:** nats, external (OpenRouter)
- **Protocol:** HTTP (TCP 8098)

**publisher-discord** (Port 8094)
- **Incoming from:** nats (subscriber)
- **Outgoing to:** external (Discord webhooks)
- **Protocol:** HTTP (TCP 8094)

### API Tier Services

**agent-zero** (Ports 8080, 8081)
- **Incoming from:** External (API), archon
- **Outgoing to:** nats, hi-rag-gateway-v2
- **Protocol:** HTTP (TCP 8080, 80)

**archon** (Ports 8091, 8051, 8052)
- **Incoming from:** External (API), agent-zero
- **Outgoing to:** nats, postgrest, agent-zero
- **Protocol:** HTTP (TCP 8091, 8051, 8052)

**pmoves-yt** (Port 8077)
- **Incoming from:** channel-monitor, external (manual ingest)
- **Outgoing to:** minio, nats, hi-rag-gateway-v2, bgutil-pot-provider
- **Protocol:** HTTP (TCP 8077)

**supaserch** (Port 8099)
- **Incoming from:** External (API), nats
- **Outgoing to:** nats, hi-rag-gateway-v2, postgrest
- **Protocol:** HTTP (TCP 8099)

**tensorzero-gateway** (Port 3030)
- **Incoming from:** hi-rag-gateway-v2, deepresearch, agent-zero, external
- **Outgoing to:** tensorzero-clickhouse, ollama, external (OpenAI, Anthropic, etc.)
- **Protocol:** HTTP (TCP 3000)

**postgrest** (Port 3010)
- **Incoming from:** extract-worker, archon, supaserch, render-webhook
- **Outgoing to:** postgres
- **Protocol:** HTTP (TCP 3000)

## Network Policy Design

### Docker Compose Network Configuration

**Historical target (pre-2025-12-14):** the section below reflects the original plan draft (dashed network names + external `pmoves-net`). The active implementation is documented in **Current Network Architecture (as of 2025-12-14)** above; prefer that stanza when reconciling changes.

```yaml
networks:
  # Public API tier - exposed to external traffic
  api-tier:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.1.0/24
    driver_opts:
      com.docker.network.bridge.name: pmoves-api
      com.docker.network.bridge.enable_icc: "false"  # Disable inter-container communication by default

  # Application worker tier
  app-tier:
    driver: bridge
    internal: true  # No external internet access
    ipam:
      config:
        - subnet: 172.30.2.0/24
    driver_opts:
      com.docker.network.bridge.name: pmoves-app

  # Message bus tier (isolated)
  bus-tier:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.30.3.0/24
    driver_opts:
      com.docker.network.bridge.name: pmoves-bus

  # Data tier (most restricted)
  data-tier:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.30.4.0/24
    driver_opts:
      com.docker.network.bridge.name: pmoves-data

  # Monitoring tier (separate for observability)
  monitoring-tier:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.5.0/24
    driver_opts:
      com.docker.network.bridge.name: pmoves-mon

  # Legacy external networks (maintain compatibility)
  pmoves:
    external: true
    name: pmoves-net
  cataclysm:
    external: true
    name: cataclysm-net
```

### Service Network Assignments

#### Data Tier (Most Restricted)

```yaml
postgres:
  networks:
    - data-tier

qdrant:
  networks:
    - data-tier

neo4j:
  networks:
    - data-tier

meilisearch:
  networks:
    - data-tier

minio:
  networks:
    - data-tier

tensorzero-clickhouse:
  networks:
    - data-tier
```

#### Message Bus Tier

```yaml
nats:
  networks:
    - bus-tier
```

#### Application Tier

Services need multiple network connections for communication:

```yaml
hi-rag-gateway-v2:
  networks:
    - app-tier     # Receive requests
    - data-tier    # Access qdrant, neo4j, meilisearch
    - api-tier     # Communicate with tensorzero-gateway

extract-worker:
  networks:
    - app-tier     # Receive requests
    - data-tier    # Access qdrant, meilisearch

langextract:
  networks:
    - app-tier

ffmpeg-whisper:
  networks:
    - app-tier
    - data-tier    # Access minio

media-video:
  networks:
    - app-tier
    - data-tier    # Access minio

media-audio:
  networks:
    - app-tier
    - data-tier    # Access minio

deepresearch:
  networks:
    - app-tier
    - bus-tier     # Access nats

publisher-discord:
  networks:
    - app-tier
    - bus-tier     # Access nats
```

#### API Tier (External Facing)

```yaml
agent-zero:
  networks:
    - api-tier
    - bus-tier     # Access nats
    - app-tier     # Access hi-rag

archon:
  networks:
    - api-tier
    - bus-tier     # Access nats
    - data-tier    # Access postgres via postgrest

pmoves-yt:
  networks:
    - api-tier
    - app-tier     # Access workers
    - bus-tier     # Access nats
    - data-tier    # Access minio

supaserch:
  networks:
    - api-tier
    - app-tier     # Access hi-rag
    - bus-tier     # Access nats

tensorzero-gateway:
  networks:
    - api-tier     # External access
    - data-tier    # Access clickhouse

postgrest:
  networks:
    - api-tier     # Receive API requests
    - data-tier    # Access postgres
```

#### Monitoring Tier

```yaml
prometheus:
  networks:
    - monitoring-tier
    - api-tier     # Scrape /metrics endpoints
    - app-tier
    - data-tier

grafana:
  networks:
    - monitoring-tier
    - api-tier     # Access UI externally

loki:
  networks:
    - monitoring-tier

promtail:
  networks:
    - monitoring-tier
    # Needs access to all tiers to collect logs
    - api-tier
    - app-tier
    - data-tier
    - bus-tier
```

## Kubernetes NetworkPolicy Manifests

For Kubernetes deployments, we'll use native NetworkPolicy resources:

### Data Tier Policy

```yaml
# File: deploy/k8s/base/network-policies/data-tier-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: data-tier-policy
  namespace: pmoves
spec:
  podSelector:
    matchLabels:
      tier: data
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from application tier
    - from:
        - podSelector:
            matchLabels:
              tier: application
      ports:
        - protocol: TCP
          port: 5432  # postgres
        - protocol: TCP
          port: 6333  # qdrant
        - protocol: TCP
          port: 7474  # neo4j http
        - protocol: TCP
          port: 7687  # neo4j bolt
        - protocol: TCP
          port: 7700  # meilisearch
        - protocol: TCP
          port: 9000  # minio
        - protocol: TCP
          port: 8123  # clickhouse

    # Allow from API tier for postgrest and tensorzero-gateway
    - from:
        - podSelector:
            matchLabels:
              tier: api
      ports:
        - protocol: TCP
          port: 5432  # postgres (via postgrest)
        - protocol: TCP
          port: 8123  # clickhouse (via tensorzero)

    # Allow from monitoring tier
    - from:
        - podSelector:
            matchLabels:
              tier: monitoring

  egress:
    # Data tier should not initiate outbound connections
    # Allow DNS only
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
        - podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

### Message Bus Tier Policy

```yaml
# File: deploy/k8s/base/network-policies/bus-tier-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: bus-tier-policy
  namespace: pmoves
spec:
  podSelector:
    matchLabels:
      tier: bus
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from API tier
    - from:
        - podSelector:
            matchLabels:
              tier: api
      ports:
        - protocol: TCP
          port: 4222  # nats

    # Allow from application tier
    - from:
        - podSelector:
            matchLabels:
              tier: application
      ports:
        - protocol: TCP
          port: 4222

    # Allow from monitoring
    - from:
        - podSelector:
            matchLabels:
              tier: monitoring

  egress:
    # NATS can communicate with API and app tiers for pub/sub
    - to:
        - podSelector:
            matchLabels:
              tier: api
    - to:
        - podSelector:
            matchLabels:
              tier: application
    # DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

### Application Tier Policy

```yaml
# File: deploy/k8s/base/network-policies/app-tier-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: app-tier-policy
  namespace: pmoves
spec:
  podSelector:
    matchLabels:
      tier: application
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from API tier
    - from:
        - podSelector:
            matchLabels:
              tier: api

    # Allow from other application services
    - from:
        - podSelector:
            matchLabels:
              tier: application

    # Allow from monitoring
    - from:
        - podSelector:
            matchLabels:
              tier: monitoring

  egress:
    # Allow to data tier
    - to:
        - podSelector:
            matchLabels:
              tier: data
      ports:
        - protocol: TCP
          port: 5432
        - protocol: TCP
          port: 6333
        - protocol: TCP
          port: 7474
        - protocol: TCP
          port: 7687
        - protocol: TCP
          port: 7700
        - protocol: TCP
          port: 9000
        - protocol: TCP
          port: 8123

    # Allow to bus tier
    - to:
        - podSelector:
            matchLabels:
              tier: bus
      ports:
        - protocol: TCP
          port: 4222

    # Allow to API tier (for callbacks)
    - to:
        - podSelector:
            matchLabels:
              tier: api

    # Allow to other app tier services
    - to:
        - podSelector:
            matchLabels:
              tier: application

    # DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53

    # Allow external for specific services (deepresearch, publisher-discord)
    # Controlled via podSelector with specific labels
```

### API Tier Policy

```yaml
# File: deploy/k8s/base/network-policies/api-tier-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-tier-policy
  namespace: pmoves
spec:
  podSelector:
    matchLabels:
      tier: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from anywhere (external traffic)
    - {}

    # Allow from monitoring
    - from:
        - podSelector:
            matchLabels:
              tier: monitoring

  egress:
    # Allow to application tier
    - to:
        - podSelector:
            matchLabels:
              tier: application

    # Allow to bus tier
    - to:
        - podSelector:
            matchLabels:
              tier: bus
      ports:
        - protocol: TCP
          port: 4222

    # Allow to data tier (postgrest, tensorzero)
    - to:
        - podSelector:
            matchLabels:
              tier: data
      ports:
        - protocol: TCP
          port: 5432
        - protocol: TCP
          port: 8123

    # Allow to API tier (inter-service)
    - to:
        - podSelector:
            matchLabels:
              tier: api

    # Allow external (for LLM providers)
    - to:
        - namespaceSelector: {}

    # DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

### Monitoring Tier Policy

```yaml
# File: deploy/k8s/base/network-policies/monitoring-tier-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: monitoring-tier-policy
  namespace: pmoves
spec:
  podSelector:
    matchLabels:
      tier: monitoring
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from anywhere for Grafana UI
    - ports:
        - protocol: TCP
          port: 3000

  egress:
    # Allow to all tiers for metrics scraping and log collection
    - to:
        - podSelector:
            matchLabels:
              tier: api
    - to:
        - podSelector:
            matchLabels:
              tier: application
    - to:
        - podSelector:
            matchLabels:
              tier: data
    - to:
        - podSelector:
            matchLabels:
              tier: bus

    # DNS
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

## Service Label Updates

Update all Kubernetes deployments with tier labels:

```yaml
# Example: postgres deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: pmoves
spec:
  template:
    metadata:
      labels:
        app: postgres
        tier: data  # Add this label
```

**Required labels:**
- `tier: data` - postgres, qdrant, neo4j, meilisearch, minio, clickhouse
- `tier: bus` - nats
- `tier: application` - hi-rag-gateway-v2, extract-worker, ffmpeg-whisper, etc.
- `tier: api` - agent-zero, archon, pmoves-yt, supaserch, tensorzero-gateway, postgrest
- `tier: monitoring` - prometheus, grafana, loki, promtail

## Testing Procedure

### Docker Compose Testing

**Test 1: Verify Network Isolation**

```bash
# Start services with new network configuration
docker compose --profile agents --profile workers up -d

# Verify network creation
docker network ls | grep pmoves

# Test data tier isolation - should FAIL
docker compose exec extract-worker curl -f http://postgres:5432 && \
  echo "❌ FAIL: Extract worker can reach postgres directly" || \
  echo "✅ PASS: Data tier isolated"

# Test allowed communication - should SUCCEED
docker compose exec hi-rag-gateway-v2 curl -f http://qdrant:6333/collections && \
  echo "✅ PASS: Hi-RAG can reach Qdrant" || \
  echo "❌ FAIL: Allowed communication blocked"
```

**Test 2: Verify Service Communication**

```bash
# Test API → Application tier
docker compose exec agent-zero curl -f http://hi-rag-gateway-v2:8086/health && \
  echo "✅ PASS: Agent Zero → Hi-RAG" || \
  echo "❌ FAIL"

# Test Application → Data tier
docker compose exec extract-worker curl -f http://qdrant:6333/collections && \
  echo "✅ PASS: Extract worker → Qdrant" || \
  echo "❌ FAIL"

# Test API → Bus tier
docker compose exec archon curl -f http://nats:4222 && \
  echo "✅ PASS: Archon → NATS" || \
  echo "❌ FAIL"
```

**Test 3: Verify Blocked Communication**

```bash
# Data tier should not initiate outbound (except DNS)
docker compose exec postgres curl -f http://agent-zero:8080 && \
  echo "❌ FAIL: Postgres can reach API tier" || \
  echo "✅ PASS: Outbound blocked from data tier"

# Bus tier isolation
docker compose exec nats wget -q -O- http://qdrant:6333 && \
  echo "❌ FAIL: NATS can reach data tier" || \
  echo "✅ PASS: Bus tier isolated"
```

### Kubernetes Testing

**Test 1: Verify NetworkPolicy Enforcement**

```bash
# Apply policies
kubectl apply -f deploy/k8s/base/network-policies/

# Verify policies created
kubectl get networkpolicies -n pmoves

# Test from test pod in application tier
kubectl run test-app --image=curlimages/curl --rm -it \
  --labels="tier=application" \
  -- curl -f http://postgres:5432

# Should succeed (allowed)

# Test from test pod in data tier
kubectl run test-data --image=curlimages/curl --rm -it \
  --labels="tier=data" \
  -- curl -f http://agent-zero:8080

# Should fail (blocked)
```

**Test 2: Metrics Collection**

```bash
# Verify Prometheus can scrape all tiers
kubectl port-forward svc/prometheus 9090:9090 -n pmoves

# Open http://localhost:9090/targets
# All targets should be UP
```

**Test 3: Application Functionality**

```bash
# Run full smoke tests
make verify-all

# Should pass - network policies shouldn't break functionality
```

## Rollback Procedure

### Docker Compose Rollback

```bash
# Restore original docker-compose.yml
git checkout HEAD -- pmoves/docker-compose.yml

# Restart services on original network
docker compose down
docker compose --profile agents --profile workers up -d
```

### Kubernetes Rollback

```bash
# Delete network policies
kubectl delete networkpolicies --all -n pmoves

# Verify services still work
kubectl get pods -n pmoves -o wide
```

## Migration Steps (TAC-Assisted)

### Step 1: Backup Configuration

```bash
cp /home/pmoves/PMOVES.AI/pmoves/docker-compose.yml \
   /home/pmoves/PMOVES.AI/pmoves/docker-compose.yml.backup-$(date +%Y%m%d)
```

### Step 2: Create New Networks

Add network definitions to docker-compose.yml (lines 994-1000):

```yaml
networks:
  api-tier:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.1.0/24

  app-tier:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.30.2.0/24

  bus-tier:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.30.3.0/24

  data-tier:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.30.4.0/24

  monitoring-tier:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.5.0/24

  # Maintain existing networks for compatibility
  pmoves:
    external: true
    name: pmoves-net
  cataclysm:
    external: true
    name: cataclysm-net
```

### Step 3: Update Service Network Assignments

For each service, update the `networks:` section according to the Service Network Assignments table above.

**Example (postgres):**
```yaml
postgres:
  # ... existing config
  networks:
    - data-tier  # Changed from: networks: [pmoves]
```

### Step 4: Test Incremental Migration

**Phase 1:** Migrate data tier only
**Phase 2:** Migrate bus tier
**Phase 3:** Migrate application tier
**Phase 4:** Migrate API tier
**Phase 5:** Migrate monitoring tier

Between each phase:
```bash
docker compose down
docker compose --profile agents --profile workers up -d
make verify-all
```

### Step 5: Create Kubernetes Policies

```bash
# Create directory structure
mkdir -p /home/pmoves/PMOVES.AI/deploy/k8s/base/network-policies

# Create policy files (as shown above)
# - data-tier-policy.yaml
# - bus-tier-policy.yaml
# - app-tier-policy.yaml
# - api-tier-policy.yaml
# - monitoring-tier-policy.yaml

# Create kustomization.yaml
cat > /home/pmoves/PMOVES.AI/deploy/k8s/base/network-policies/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - data-tier-policy.yaml
  - bus-tier-policy.yaml
  - app-tier-policy.yaml
  - api-tier-policy.yaml
  - monitoring-tier-policy.yaml
EOF
```

### Step 6: Update Deployment Labels

For all Kubernetes deployments in `deploy/k8s/base/`, add tier labels:

```yaml
spec:
  template:
    metadata:
      labels:
        tier: <appropriate-tier>
```

### Step 7: Deploy and Test

```bash
# Deploy policies
kubectl apply -k deploy/k8s/base/network-policies/

# Verify
kubectl get networkpolicies -n pmoves
kubectl describe networkpolicy data-tier-policy -n pmoves

# Test
make verify-all
```

## Security Benefits

✅ **Lateral Movement Prevention** - Compromised service can't reach all others
✅ **Least Privilege Networking** - Services only access what they need
✅ **Defense in Depth** - Network layer security complements application security
✅ **Attack Surface Reduction** - Internal services not exposed unnecessarily
✅ **Compliance** - Meets network segmentation requirements (PCI DSS, NIST)
✅ **Audit Trail** - Network policies are version controlled and documented

## Compliance Alignment

Network policies help achieve:

- ✅ **CIS Kubernetes Benchmark:** 5.3.2 - Network policies enforced
- ✅ **NIST 800-190:** Network segmentation for containers
- ✅ **PCI DSS:** Requirement 1.3 - Network segmentation
- ✅ **SOC 2:** CC6.6 - Logical access controls
- ✅ **Zero Trust:** Micro-segmentation principles

## Monitoring & Alerting

### Prometheus Alerts for Network Policies

```yaml
# File: deploy/k8s/overlays/production/prometheus-rules.yaml
groups:
  - name: network-policy-alerts
    rules:
      - alert: NetworkPolicyDeniedConnections
        expr: rate(network_policy_drops_total[5m]) > 10
        annotations:
          summary: "High rate of network policy denials"
          description: "{{ $labels.pod }} is experiencing {{ $value }} denied connections/sec"

      - alert: UnauthorizedDataTierAccess
        expr: network_policy_drops_total{destination_tier="data"} > 0
        annotations:
          summary: "Attempted unauthorized access to data tier"
```

### Logging Dropped Connections

Enable iptables logging for dropped packets:

```bash
# On Docker host
iptables -A FORWARD -m conntrack --ctstate INVALID -j LOG --log-prefix "NETPOL-DROP: "

# Monitor
tail -f /var/log/syslog | grep NETPOL-DROP
```

## Future Enhancements

1. **Cilium Network Policies** - Layer 7 (HTTP) aware policies
2. **Service Mesh Integration** - Istio/Linkerd for mTLS and fine-grained policies
3. **eBPF-based Enforcement** - Faster, more efficient policy enforcement
4. **Dynamic Policy Updates** - Automated policy generation from service communication patterns
5. **Network Policy Testing** - Automated regression testing for policy changes

## Related Documentation

- [Phase 2 Security Hardening Plan](./phase2-security-hardening-plan.md) (when created)
- [Docker Network Security](https://docs.docker.com/network/network-security/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [NIST Container Security Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-190.pdf)

---

**Status:** Ready for TAC implementation
**Effort:** 1.5-2 hours with AI assistance
**Security Impact:** HIGH - Critical defense-in-depth control
**Maintenance:** Policies updated when new services added
