# PMOVES.AI-Edition-Hardened-Full.md Implementation Plan

**Created:** 2026-02-04
**Purpose:** Comprehensive update plan for PMOVES.AI-Edition-Hardened-Full.md to align with latest Docker documentation, current docker-compose.yml configuration, and self-hosted AI laptop + VPS with 3 KVMs deployment architecture.

---

## Executive Summary

The PMOVES.AI-Edition-Hardened-Full.md document requires significant updates to align with:
1. **Current Docker Compose v5.0.2** features and best practices
2. **Actual docker-compose.yml configuration** including integrated Supabase stack
3. **Self-hosted AI laptop + VPS deployment architecture** with 3 KVMs
4. **Model runners and profile management** for AI workload orchestration
5. **GitHub Runner Controller** for self-hosted CI/CD
6. **n8n-runners** for workflow automation
7. **Dynamic port publishing** and namespace publishing features
8. **Container hardening reality** vs documentation

---

## Priority Order of Updates

### Phase 1: Critical Security & Accuracy Updates (HIGH PRIORITY)
- [ ] Update status date to 2026-02-04
- [ ] Document integrated Supabase stack (7 services)
- [ ] Correct network architecture to show actual `internal: true` flags
- [ ] Update container hardening status to reflect reality
- [ ] Add missing `env.tier-supabase` tier
- [ ] Document image pinning violations (8 images using `:latest`)

### Phase 2: Docker Compose V5 & New Features (HIGH PRIORITY)
- [ ] Update Docker Compose V5 section to reflect v5.0.2
- [ ] Document Compose Bridge GA features
- [ ] Add watch mode documentation (`docker compose watch`)
- [ ] Document namespace publishing features
- [ ] Add dynamic port publishing documentation
- [ ] Update health check patterns to use `curl -sf` instead of `wget --spider`

### Phase 3: Model Runners & Profile Management (MEDIUM PRIORITY)
- [ ] Document model profile management (`make model-profiles`, `make model-apply`)
- [ ] Document model sync functionality (`make models-sync`)
- [ ] Document model swap functionality (`make model-swap`)
- [ ] Document Ollama model seeding (`make models-seed-ollama`)
- [ ] Document model registry service at `pmoves/model-registry/`
- [ ] Add model runner configuration examples

### Phase 4: GitHub Runner Controller (MEDIUM PRIORITY)
- [ ] Document GitHub Runner Controller API endpoints
- [ ] Document runner label conventions
- [ ] Document NATS events for runner status
- [ ] Document runner health checks and monitoring
- [ ] Document auto-scaling based on queue depth
- [ ] Document runner offline detection and alerting

### Phase 5: n8n-Runners & Workflow Automation (MEDIUM PRIORITY)
- [ ] Document n8n-runners sidecar configuration
- [ ] Document SQLite vs Postgres DB modes
- [ ] Document flow watcher for automatic workflow reloading
- [ ] Document integration with health-wger for fitness data
- [ ] Add n8n workflow examples

### Phase 6: Port Allocation & Service Catalog (LOW PRIORITY)
- [x] Add Supabase stack ports to port allocation table
- [x] Update service catalog to reflect 71 services (65 main + 6 monitoring)
- [ ] Add GitHub Runner Controller ports
- [ ] Add n8n-runners ports
- [ ] Update port binding recommendations

### Phase 7: Self-Hosted AI Laptop + VPS Architecture (LOW PRIORITY)
- [ ] Document hybrid deployment architecture (laptop + VPS)
- [ ] Document KVM node roles (media processing, workers, publisher)
- [ ] Document service placement across nodes
- [ ] Add network configuration for multi-node setup
- [ ] Document resource allocation per node
- [ ] Add failover and redundancy strategies

---

## Detailed Implementation Tasks

### 1. CVE Section Update

**Location:** Lines 1911-1943

**Required Changes:**

#### 1.1 Update CVE Status to Current Patched State
\`\`\`markdown
### Docker Security Advisories

**Status:** All documented CVEs from 2025 are now patched in current environment.

#### CVE-2025-9074 (CRITICAL) - Docker Desktop API Exposure
- **Status:** ✅ **PATCHED**
- **Previously Affected:** Docker Desktop < 4.44.3
- **Current Version:** Docker Desktop 4.59.0
- **Risk:** Containers can access Docker Engine API via default subnet (192.168.65.7:2375)
- **Impact:** Container escape, host compromise
- **Fix:** Upgrade Docker Desktop to 4.44.3+ (COMPLETED)
- **Verification:** \`docker version --format '{{.Server.Version}}'\` → 29.2.0 ✅

#### CVE-2025-62725 (HIGH) - Compose Path Traversal
- **Status:** ✅ **PATCHED**
- **Previously Affected:** Docker Compose < 2.40.2
- **Current Version:** Docker Compose v5.0.2
- **Risk:** Path traversal in OCI artifact support (CVSS 8.9)
- **Impact:** Arbitrary file read during build
- **Fix:** Upgrade to Compose v2.40.2+ or v5.0+ (COMPLETED)
- **Verification:** \`docker compose version\` → v5.0.2 ✅

#### CVE-2025-32434 (HIGH) - PyTorch torch.load
- **Status:** ⚠️ **NEEDS VERIFICATION**
- **Affected:** PyTorch < 2.6.0
- **Risk:** Arbitrary code execution via malicious model files
- **Impact:** RCE when loading untrusted .pt/.pth files
- **Fix:** Upgrade PyTorch to 2.6.0+, use \`weights_only=True\`
- **Services affected:** ffmpeg-whisper, media-video, hi-rag-gateway-v2
- **Action Required:** Verify PyTorch versions in requirements.lock files

#### CVE-2025-55182 (CRITICAL) - Next.js RSC Remote Code Execution
- **Status:** ⚠️ **NEEDS VERIFICATION**
- **Affected:** Next.js App Router deployments (versions before patched releases)
- **Risk:** Remote Code Execution via React Server Components (RSC) unsafe deserialization
- **Impact:** Pre-auth RCE - attackers can execute arbitrary code on server
- **Fix:** Upgrade Next.js to one of patched versions: 15.0.5, 15.1.9, 15.2.6, 15.3.6+, 15.4.8+, 15.5.7+, or 16.0.7+
- **Services affected:** pmoves-ui, archon-ui, tensorzero-ui
- **Warning:** Versions 15.3.0-15.3.5 are NOT patched despite being newer than 15.2.6
- **Note:** Pages Router and Edge Runtime have reduced exposure; App Router is primary attack surface
\`\`\`

#### 1.2 Add Image Pinning Status Table
\`\`\`markdown
### Image Pinning Status (PR #355)

**Policy:** All production images MUST use specific version tags, NOT \`latest\`.

| Image | Current Tag | Required Tag | Status |
|-------|--------------|--------|--------|
| nats | latest | nats:2.10-alpine | ⚠️ **VIOLATION** |
| minio/minio | latest | minio/minio:RELEASE.2024-12-18T13-15-44Z | ⚠️ **VIOLATION** |
| tensorzero/gateway | latest | tensorzero/gateway:2024.12.18 | ⚠️ **VIOLATION** |
| tensorzero/ui | latest | tensorzero/ui:2024.12.18 | ⚠️ **VIOLATION** |
| supabase/studio | latest | supabase/studio:v2024.12.18 | ⚠️ **VIOLATION** |
| invidious | latest | quay.io/invidious/invidious:2024.12.18 | ⚠️ **VIOLATION** |
| invidious-companion | latest | quay.io/invidious/invidious-companion:2024.12.18 | ⚠️ **VIOLATION** |
| grayjay | latest | registry.gitlab.futo.org/videostreaming/grayjay/grayjay:2024.12.18 | ⚠️ **VIOLATION** |
| qdrant/qdrant | v1.10.0 | v1.10.0 | ✅ OK |
| neo4j | 5.22 | 5.22 | ✅ OK |
| meilisearch | v1.8 | v1.8 | ✅ OK |
| clickhouse | 24.12-alpine | 24.12-alpine | ✅ OK |
| ollama/ollama | 0.12.6 | 0.12.6 | ✅ OK |
| cloudflared | 2024.8.0 | 2024.8.0 | ✅ OK |
| supabase/postgres | 17.6.1.079 | 17.6.1.079 | ✅ OK |
| supabase/gotrue | v2.186.0 | v2.186.0 | ✅ OK |
| postgrest/postgrest | v12.2.0 | v12.2.0 | ✅ OK |
| kong | 3.7.1 | 3.7.1 | ✅ OK |
| supabase/realtime | v2.30.26 | v2.30.26 | ✅ OK |
| supabase/storage-api | v1.36.2 | v1.36.2 | ✅ OK |

**Verification Command:**
\`\`\`bash
# Check for :latest violations
grep ':latest' pmoves/docker-compose.yml

# Expected: Should return nothing (8 violations)
\`\`\`
\`\`\`
---

### 2. Tier-Based Secrets Architecture Update

**Location:** Lines 1238-1288

**Required Changes:**

#### 2.1 Add env.tier-supabase Tier
\`\`\`markdown
### Tier-Based Secrets Architecture (env.tier-*)

PMOVES implements **principle of least privilege** via 7 specialized environment tiers. This is a **hidden strength** – fully implemented in docker-compose.yml but previously undocumented:

| Tier File | Services | Secrets Scope |
|-----------|----------|---------------|
| \`env.tier-data\` | postgres, qdrant, neo4j, minio | Infrastructure only, NO API keys |
| \`env.tier-api\` | postgrest, hi-rag-v2, presign | Data tier + internal TensorZero (NO external keys) |
| \`env.tier-worker\` | extract-worker, langextract | Processing credentials |
| \`env.tier-agent\` | agent-zero, archon, nats | Agent coordination |
| \`env.tier-media\` | pmoves-yt, whisper, media-* | Media processing |
| \`env.tier-llm\` | **tensorzero-gateway ONLY** | **External LLM API keys** |
| \`env.tier-supabase\` | **NEW** - supabase-db, supabase-gotrue, supabase-postgrest, supabase-kong, supabase-realtime, supabase-storage, supabase-studio | Supabase service keys and JWT configuration |

**Implementation in docker-compose.yml:**
\`\`\`yaml
x-env-tier-supabase: &env-tier-supabase
  env_file: [ env.tier-supabase, .env.local ]
\`\`\`

**Security Benefits:**
1. **Blast Radius Reduction:** Compromised worker cannot access LLM API keys
2. **Audit Simplicity:** Only one file (\`env.tier-llm\`) needs external key rotation
3. **TensorZero as Secrets Fence:** All services call internal \`http://tensorzero:3000\`, not external providers
4. **Supabase Isolation:** Dedicated tier for Supabase service keys and JWT configuration
\`\`\`
\`\`\`
---

### 3. Docker Compose V5 Section Update

**Location:** Lines 1945-1978

**Required Changes:**

#### 3.1 Update to Docker Compose v5.0.2
\`\`\`markdown
### Docker Compose V5 (Current: v5.0.2)

**Key changes affecting PMOVES.AI:**

1. **Version field deprecated:**
\`\`\`yaml
# Old (generates warning)
version: '3.8'
services:
  ...

# New (V5+)
services:
  ...
\`\`\`

2. **New AI/ML support:**
\`\`\`yaml
# New top-level models key for LLM integration
models:
  llama:
    provider: ollama
    model: llama3.2:latest
\`\`\`

3. **Compose Bridge GA:**
- Convert Compose files to Kubernetes manifests or Helm charts
- Command: \`docker compose bridge convert\`
- Documentation: [Docker Compose Bridge](https://docs.docker.com/compose/bridge/)

4. **Watch mode for development:**
\`\`\`bash
docker compose watch  # Real-time code updates
\`\`\`

**Current Version:** Docker Compose v5.0.2 (released December 2025)
**Key Features:**
- Compose Bridge for Kubernetes conversion (GA)
- Improved dependency management with \`wait\` and \`wait_dependencies_on\`
- Watch mode for hot-reload during development
- Namespace publishing for service discovery
- Dynamic port publishing with \`publish_all_ports\`
- Port range configuration for multi-service deployments
\`\`\`
\`\`\`
---

### 4. Production Deployment Checklist Update

**Location:** Lines 2018-2066

**Required Changes:**

#### 4.1 Add Image Pinning Verification
\`\`\`markdown
- [ ] **Image pinning verified**
  - All images use specific version tags (no \`latest\`)
  - Verify: \`grep ':latest' pmoves/docker-compose.yml\`
  - Expected: 8 violations to be fixed
\`\`\`

#### 4.2 Update Health Check Patterns
\`\`\`markdown
- [ ] **Health checks configured**
  - All services have healthcheck definitions
  - Dependencies use \`condition: service_healthy\`
  - Verify: \`docker compose ps\` shows "(healthy)" status
  - **Updated pattern:** Use \`curl -sf\` instead of \`wget --spider\` for silent failure detection

**Old Pattern:**
\`\`\`yaml
healthcheck:
  test: ["CMD-SHELL", "wget --spider http://localhost:8080/health"]
\`\`\`

**New Pattern:**
\`\`\`yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:8080/health || exit 1"]
\`\`\`

**Benefits:**
- \`curl -sf\` fails silently on network errors (no output)
- \`wget --spider\` outputs error messages to logs
- Better for automated health checks in CI/CD pipelines
\`\`\`
\`\`\`
---

### 5. Port Allocation Table Update

**Location:** Lines 274-326

**Required Changes:**

#### 5.1 Add Supabase Stack Ports
\`\`\`markdown
| Port | Service | Tier | Current Binding | Production Binding | Notes |
|------|---------|------|-----------------|-------------------|-------|
| **Supabase Stack** | | | |
| 54322 | supabase-db | data | 0.0.0.0 | 127.0.0.1 | PostgreSQL 17.6.1.079 with pgvector |
| 9999 | supabase-gotrue | data | 0.0.0.0 | 127.0.0.1 | Authentication service v2.186.0 |
| 3000 | supabase-postgrest | api | 0.0.0.0 | 127.0.0.1 | REST API v12.2.0 |
| 8000 | supabase-kong (HTTP) | api | 0.0.0.0 | 127.0.0.1 | API Gateway 3.7.1 (HTTP) |
| 8001 | supabase-kong (HTTPS) | api | 0.0.0.0 | 127.0.0.1 | API Gateway 3.7.1 (HTTPS) |
| 4000 | supabase-realtime | data | 0.0.0.0 | 127.0.0.1 | Realtime subscriptions v2.30.26 |
| 5000 | supabase-storage | data | 0.0.0.0 | 127.0.0.1 | S3-compatible storage v1.36.2 |
| 54323 | supabase-studio | app | 0.0.0.0 | 127.0.0.1 | Admin console |
\`\`\`
\`\`\`
