# PMOVES.AI Fleet Infrastructure Enhancement Report

**Date**: 2026-04-19
**Classification**: Internal Infrastructure
**Scope**: Full fleet analysis — on-prem GPU nodes, VPS fleet, SPARK DGX node
**Sources**: HYBRID_RUNNER_STRATEGY.md, AGNOTE4482_ROADMAP_W1-W5.md, AGNOTE4482PHI.t1.md, docker-compose.base.yml, dgx-spark.tac.yaml, deploy/k8s/, pmoves/services/

---

## Executive Summary

PMOVES.AI operates an 8-node fleet across three tiers (on-prem GPU, VPS compute, DGX ARM64), but the cognitive specialization matrix declared in operational documentation covers only the original 3 on-prem GPU nodes (z890, 5090, 4090). The VPS fleet (KVM4-1, KVM4-2, KVM2) and SPARK DGX node exist in provisioning scripts and TAC trees but have no formal declaration in the specialization matrix. Additionally, the SPARK TAC tree GPU capabilities (GB10 Grace-Blackwell, Ollama, NIM) match the actual hardware — NVIDIA DGX Spark with GB10 Grace-Blackwell superchip, 128GB unified memory, NVIDIA Blackwell GPU — but the TAC tree carries `status: future` on mesh integration items that are actually operational. This report identifies 7 gap categories and provides specific remediation recommendations for each fleet node.

---

## 1. Gaps Between Current Specialization Matrix and Actual Fleet

### 1.1 Declared vs. Actual Fleet

| Node | In Specialization Matrix | In Provisioning Scripts | In TAC Trees | Actual Status |
|------|:-----------------------:|:-----------------------:|:------------:|---------------|
| z890 (RTX 3090Ti) | YES | YES | YES | Active, 20 containers healthy |
| 5090 (RTX 5090) | YES | YES | YES | Active, voice/GPU stack |
| 4090 laptop (RTX 4090) | YES | YES | YES | Active, P7/mobile agent |
| SPARK DGX (GB10 Grace-Blackwell) | NO | YES (runner) | YES (GPU inference) | Active runner, GB10 Grace-Blackwell GPU, 128GB unified, CUDA |
| KVM4-1 (4 vCPU/16GB) | NO | YES (API Gateway) | NO | Docker active, RustDesk only |
| KVM4-2 (4 vCPU/16GB) | NO | YES (Data/Storage) | NO | Docker active, 0 containers |
| KVM2 (2 vCPU/8GB) | NO | YES (Exit Node) | NO | Docker active, 0 containers, fleet-audit-watcher.sh |
| AI Lab (RTX 5090) | NO | YES (GPU runner) | NO | Offline |

### 1.2 Gap Categories

**GAP-1: Matrix Scope Omission** — The specialization matrix was designed when the fleet was 3 on-prem nodes. 5 additional nodes now exist without matrix entries. This creates ambiguity for:
- Agent routing (which node handles which workload class)
- CI/CD label targeting (runners exist but cognitive role is undefined)
- Capacity planning (no formal compute budget per role)

**GAP-2: SPARK TAC Tree Status Tags** — The TAC tree (`dgx-spark.tac.yaml`) accurately describes the actual hardware:
- GB10 Grace-Blackwell 128GB unified memory (correct — NVIDIA DGX Spark superchip)
- Ollama inference at `:11434` (correct — active on CUDA)
- NIM inference API at `:8200` (correct — active)
- NATS GPU mesh with 5 subject namespaces (correct — subjects defined, but TAC tree marks these `status: future`)

The TAC tree's GPU claims are NOT aspirational — they match the actual GB10 Grace-Blackwell hardware. However, the mesh integration items carry `status: future` despite the GPU being operational, which understates SPARK's current capabilities.

**GAP-3: VPS Role Script-Only Declaration** — `hostinger-kvm-setup.sh` defines roles (KVM4-1=API Gateway, KVM4-2=Data/Storage, KVM2=Exit Node) but these exist only in provisioning scripts. No TAC trees, no specialization matrix entries, no agent profile configs reference these roles.

**GAP-4: Runner Persistence Fragility** — All VPS runners use `nohup`, not systemd. They will not survive reboots. The install script has a known bug: `install.sh` fails as root without `RUNNER_ALLOW_RUNASROOT=1`. No systemd unit files exist in `deploy/runners/vps/`.

**GAP-5: Single-Node Compose Assumption** — 37 docker-compose overlay files; docker-compose.yml alone defines 84 services, 303 total across all overlays. No compose overlay exists for per-node distribution. The 5-tier network isolation (data, api, app, bus, monitoring) uses bridge networks with fixed subnets — these do not span hosts.

**GAP-6: K8s Manifests Skeletal** — The `deploy/k8s/` directory contains:
- `base/`: namespace, ingress, single pmoves-core deployment (250m-1CPU, 256Mi-1Gi), service
- `kvm4/`: kustomization.yaml (overlay stub only)
- `ai-lab/`: kustomization.yaml (overlay stub only)
- `local/`: kustomization.yaml (overlay stub only)
- `networkpolicies/`: 6 well-structured policies (default-deny + allow DNS/external-api/ingress/monitoring/NATS-mesh)

The NetworkPolicies are production-quality but reference only a single `pmoves-core` workload. No service-specific deployments exist for any of the 70+ services.

**GAP-7: No Infrastructure Plans Document** — `pmoves/docs/PMOVES.AIPLANS/` does not exist — no infrastructure planning directory has been created. Infrastructure planning exists only inline in AGNOTE4482 roadmap (W5 enterprise tier mentions k3s cluster, multi-region) and HYBRID_RUNNER_STRATEGY.md (Phase 3 mentions k3s replacement).

---

## 2. Recommended Role Assignments

### 2.1 Updated Specialization Matrix

| Node | Hardware | Cognitive Role | Workload Class | Priority |
|------|----------|---------------|----------------|----------|
| z890 | RTX 3090Ti, 64GB | Infrastructure Lead | Orchestration, CI coordination, RustDesk server, container builds | P0 |
| 5090 | RTX 5090, 128GB | GPU Inference Primary | Voice TTS/STT, model inference, GPU builds, Ollama CUDA | P0 |
| SPARK | GB10 Grace-Blackwell, 128GB unified, CUDA GPU | GPU Inference Secondary | A2A/MCP relay, GPU inference (Ollama/NIM), Agent Zero sessions, batch processing | P0 |
| AI Lab | RTX 5090, 128GB | GPU Build Farm | CUDA Docker builds, model training, Hi-RAG GPU (when online) | P1 |
| KVM4-1 | 4c/16GB X64 | API Gateway | Public-facing services, TensorZero, Agent Zero API, BoTZ Gateway, SSL termination | P0 |
| KVM4-2 | 4c/16GB X64 | Data Plane | Supabase, Qdrant, Neo4j, Meilisearch, ClickHouse — all data-tier services | P1 |
| KVM2 | 2c/8GB X64 | Exit/Observability | Tailscale exit node, Nginx reverse proxy, Prometheus/Grafana, fleet-audit-watcher, log aggregation | P2 |

### 2.2 Leveraging KVM4's Extra Compute Over KVM2

KVM4-1 and KVM4-2 each have 2x the vCPUs and 2x the RAM of KVM2. The current `hostinger-kvm-setup.sh` correctly assigns data-plane work to KVM4-2, but KVM2's exit-node role underutilizes its compute. Recommended rebalancing:

**KVM4-1 (4c/16GB) — API Gateway Tier**
- Agent Zero API (port 8080) — primary user-facing agent interface
- BoTZ Gateway (port 8054) — agent orchestration
- TensorZero Config API — LLM routing
- Presign service — authentication
- Render Webhook — deployment triggers
- Messaging Gateway (port 8101) — multi-platform bridge
- Publisher Discord (port 8094) — Discord integration
- Nginx reverse proxy + SSL termination
- GitHub Actions runner (existing)

Estimated container count: 8-10. Memory budget: ~8-10GB for services + 2GB runner + 4GB OS/cache.

**KVM4-2 (4c/16GB) — Data Plane Tier**
- Supabase (PostgreSQL + PostgREST + Storage + Vector) — largest memory consumer
- Qdrant — vector search
- Neo4j — graph database
- Meilisearch — full-text search
- ClickHouse (TensorZero) — analytics
- NATS server — message bus (leaf node to z890 hub)
- GitHub Actions runner (existing)

Estimated container count: 7-9. Memory budget: ~10-12GB for databases + 2GB runner + 2GB OS.

**KVM2 (2c/8GB) — Exit/Observability Tier**
- Tailscale exit node (lightweight)
- Nginx (SSL termination for exit traffic)
- Prometheus + AlertManager — metrics collection
- Grafana — dashboards
- fleet-audit-watcher.sh (existing, Python process)
- Loki or vector — log aggregation (lightweight)
- GitHub Actions runner (existing, backup label)

Estimated container count: 5-6. Memory budget: ~4GB for monitoring + 2GB runner + 2GB OS.

**Why KVM2 should NOT host data services**: With 2 vCPUs and 8GB RAM, KVM2 cannot run Supabase (requires ~4GB alone) alongside other databases. The current zero-container state suggests the exit-node role was chosen correctly but the monitoring add-on fills the compute gap without memory pressure.

---

## 3. Services for Distributed Deployment

### 3.1 Service Classification by Deployment Target

The 70+ services in `pmoves/services/` can be classified into deployment tiers based on their network tier assignment, resource requirements, and interdependencies:

#### Tier: API Gateway (KVM4-1)

| Service | Port | Network | Rationale |
|---------|------|---------|-----------|
| `gateway` | 8080 | pmoves_api | Core API server, public-facing |
| `gateway-agent` | — | pmoves_api | Agent-side gateway logic |
| `botz-gateway` | 8054 | pmoves_app | Agent orchestration, theme API |
| `presign` | — | pmoves_api | Authentication endpoint |
| `render-webhook` | — | pmoves_api | Deployment trigger |
| `messaging-gateway` | 8101 | pmoves_api | Multi-platform messaging |
| `publisher-discord` | 8094 | pmoves_app | Discord publishing |
| `publisher` | — | pmoves_app | General publishing |
| `tensorzero-config-api` | — | pmoves_api | LLM routing config |
| `node-registry` | — | pmoves_api | Service discovery |
| `model-registry` | — | pmoves_api | Model metadata |
| `channel-monitor` | — | pmoves_app | Channel state tracking |
| `showtime-api` | — | pmoves_api | Presentation layer |

#### Tier: Data Plane (KVM4-2)

| Service | Port | Network | Rationale |
|---------|------|---------|-----------|
| Supabase suite | 5432/8000/etc | pmoves_data | PostgreSQL + services, heaviest memory consumer |
| Qdrant | 6333 | pmoves_data | Vector DB |
| Neo4j | 7687 | pmoves_data | Graph DB |
| Meilisearch | 7700 | pmoves_data | Full-text search |
| TensorZero + ClickHouse | — | pmoves_data | Analytics storage |
| `notebook-sync` | — | pmoves_data | Notebook persistence |
| `pdf-ingest` | — | pmoves_data | Document processing |
| `langextract` | — | pmoves_data | Language extraction |
| `retrieval-eval` | — | pmoves_data | RAG evaluation |
| `supaserch` | — | pmoves_data | Supabase search extension |

#### Tier: Observability (KVM2)

| Service | Port | Network | Rationale |
|---------|------|---------|-----------|
| Prometheus | 9090 | pmoves_monitoring | Metrics collection |
| AlertManager | — | pmoves_monitoring | Alert routing |
| `alertmanager-discord-bridge` | — | pmoves_monitoring | Discord alerting |
| Grafana | 3000 | pmoves_monitoring | Dashboards |
| `resource-detector` | — | pmoves_monitoring | Fleet resource detection |

#### Tier: GPU-Bound (z890/5090/AI Lab only)

| Service | Port | Network | Rationale |
|---------|------|---------|-----------|
| `hi-rag-gateway` / `hi-rag-gateway-v2` | — | pmoves_api + GPU | Requires CUDA |
| `flute-gateway` | — | pmoves_api | TTS synthesis, requires GPU |
| `cast-tts-gateway` | — | pmoves_api | TTS casting, requires GPU |
| `vibevoice-realtime` | — | pmoves_app | Realtime voice, requires GPU |
| `comfyui` / `comfy-watcher` | — | pmoves_media | Image generation, requires GPU |
| `vllm-orchestrator` | — | pmoves_llm | LLM serving, requires GPU |
| `gpu-orchestrator` | — | pmoves_api | GPU management |
| `ffmpeg-whisper` | — | pmoves_media | STT, benefits from GPU |
#### Tier: SPARK-Suitable (GPU + CPU inference, general compute)


| Service | Port | Network | Rationale |
|---------|------|---------|-----------|
| `agent-zero` / `agent_zero` | 8080 | pmoves_app | Agent runtime, CPU-bound inference |
| `deepresearch` | — | pmoves_agent | Research agent, CPU-intensive |
| `archon` | — | pmoves_agent | Architecture agent |
| `mesh-agent` | — | pmoves_bus | NATS mesh coordination |
| `work-marshaling` | — | pmoves_bus | Task distribution |
| `evo-controller` / `evoswarm` | — | pmoves_agent | Evolutionary agents |
| `agentgym-rl-coordinator` | — | pmoves_agent | RL coordination |
| `benchmark-runner` | — | pmoves_worker | Benchmarking |
| `consciousness-service` | — | pmoves_app | Consciousness mapping |
| `session-context-worker` | — | pmoves_worker | Context management |
| `extract-worker` | — | pmoves_worker | Data extraction |
| `analysis-echo` | — | pmoves_worker | Analysis pipeline |

#### Tier: Not Yet Distributable (require refactoring)

| Service | Reason |
|---------|--------|
| `n8n` | Requires persistent SQLite/volume, complex dependency tree |
| `invidious` / `invidious-companion-proxy` | YouTube scraping, needs stable IP + cookies |
| `pmoves-yt` / `yt-cookie-writer` / `yt-cookie-refresher` | YouTube auth chain, single-node stateful |
| `jellyfin-bridge` | Media streaming, requires direct GPU access |
| `grayjay-plugin-host` | Plugin isolation sandbox |
| `container-agent` | Docker socket access, host-bound |
| `github-runner-ctl` | Runner management, host-bound |

### 3.2 Cross-Node Communication Requirements

Distributing services across nodes introduces inter-node dependencies that currently do not exist:

**API Gateway (KVM4-1) needs to reach:**
- Data Plane (KVM4-2): Supabase REST, Qdrant, Neo4j, Meilisearch — all on pmoves_data network
- GPU nodes (z890/5090): Hi-RAG, Flute-Gateway — on pmoves_api network
- SPARK: Agent Zero sessions — on pmoves_app network

**Solution options:**
1. Tailscale overlay networking (recommended short-term) — each node gets a Tailscale IP, services bind to Tailscale interface, ACLs enforce tier access
2. WireGuard mesh (alternative) — similar to Tailscale but self-managed
3. Docker Swarm overlay networks (medium-term) — requires Swarm mode on all VPS nodes
4. k3s with CNI (long-term) — full Kubernetes networking

---

## 4. A2A/MCP/Pinokio P7 Fleet Orchestration Capabilities

### 4.1 Current State

**A2A (Agent-to-Agent)**: The `a2a_chat` tool is implemented in the Agent Zero framework and enables cross-node agent communication via HTTP. The PMOVES.AI codebase includes:
- `a2ui-nats-bridge` — A2A-to-NATS bridge service
- `a2ui-renderer` — A2A UI rendering
- `mesh-agent` — NATS mesh coordination agent

**MCP (Model Context Protocol)**: The `pmoves-cipher-mcp/` directory contains 4 MCP servers plus 1 shared library:
- `pmoves_health` — fleet health checking
- `pmoves_announcer` — agent announcement/broadcast
- `pmoves_registry` — service registry
- `cipher_mcp` — encryption/CHIT operations
- `pmoves_common` — shared library (not an MCP server)

Additionally, `hf-mcp-server` provides HuggingFace model access via MCP.

**Pinokio P7**: TAC tree exists (`pinokio-p7.tac.yaml`) with 7 phases. Current status covers Phase 1-2 (upgrade tracking, SKILL.md discovery). Phase 5 (Tailscale routing) and Phase 6 (service registration) are not yet implemented.

### 4.2 What A2A/MCP/P7 Enable for Fleet Orchestration

**A2A Protocol Enables:**
- Cross-node agent delegation: SPARK's Agent Zero can delegate GPU tasks to 5090 via A2A without manual SSH
- Federated research: DeepResearch on SPARK can spawn subtasks on KVM4-1 (API lookups) and z890 (local doc access)
- Load-aware routing: A2A endpoints can expose capacity metadata, enabling intelligent task distribution
- Runtime agent migration: If SPARK is overloaded, A2A handoff can move an agent session to another node

**MCP Protocol Enables:**
- Unified tool access: Any agent on any node can access fleet health, registry, cipher, and model tools via MCP
- Service discovery: `pmoves_registry` MCP server can provide real-time service topology across all nodes
- Secure cross-node operations: `pmoves_cipher` MCP enables CHIT-encrypted handoffs between nodes
- Health-aware orchestration: `pmoves_health` MCP can feed live node health into agent routing decisions

**P7 Pinokio Enables:**
- Room-aware stage management: P7 as the unified entry point that knows which room maps to which node/service
- Tailscale mesh routing (Phase 5): P7 connects users to the correct node based on room/stage context
- Service registration (Phase 6): P7 discovers and registers services across the fleet
- Student/contributor onboarding: P7 SKILL.md files guide users to the right service on the right node

### 4.3 Recommended Orchestration Architecture

```
P7 Pinokio (User Entry)
    |
    | Room/Stage routing
    v
MCP Registry Server (on SPARK or KVM4-1)
    |
    | Service discovery + health
    v
A2A Mesh (cross-node agent protocol)
    |
    +---> SPARK (Agent Zero sessions, CPU inference, A2A relay)
    +---> KVM4-1 (API Gateway, BoTZ, public services)
    +---> KVM4-2 (Data Plane queries via MCP)
    +---> z890/5090 (GPU inference via A2A delegation)
    +---> KVM2 (Observability data via MCP health)
```

**Implementation priority:**
1. Deploy `pmoves_registry` MCP on SPARK (central, always-on, 119GB RAM)
2. Deploy `pmoves_health` MCP on each VPS node
3. Configure A2A endpoints on SPARK and KVM4-1
4. Implement P7 Phase 5 (Tailscale routing) to use MCP registry for node selection

---

## 5. K8s Manifests Assessment

### 5.1 Current State

| Component | Maturity | Notes |
|-----------|----------|-------|
| Namespace | Production-ready | Standard `pmoves-ai` namespace |
| Ingress | Skeleton | Exists, needs backend service mapping |
| pmoves-core Deployment | Skeleton | Single pod, 250m-1CPU, generic healthz |
| pmoves-core Service | Skeleton | ClusterIP on port 8080 |
| NetworkPolicies | Production-quality | default-deny + 5 allow rules matching compose tiers |
| KVM4 overlay | Stub | kustomization.yaml only, no workload definitions |
| AI Lab overlay | Stub | kustomization.yaml only, no workload definitions |
| Local overlay | Stub | kustomization.yaml only |

### 5.2 Assessment

The K8s manifests are a well-structured foundation but represent approximately 5% of what would be needed to run PMOVES.AI on Kubernetes. Key gaps:

- No per-service Deployments for any of the 70+ services
- No StatefulSets for databases (Supabase, Neo4j, Qdrant, ClickHouse)
- No ConfigMaps or Secrets manifests
- No PersistentVolumeClaims for data volumes
- No HorizontalPodAutoscaler definitions
- KVM4 overlay has no node selectors or taints/tolerations for VPS-specific placement
- No Helm charts or Kustomize components for reusable service templates

### 5.3 Recommendation: Docker Compose is the Path (Near-Term)

**For VPS nodes, docker-compose remains the correct path for the following reasons:**

1. **Resource constraints**: 4 vCPU/16GB nodes cannot afford Kubernetes overhead (kubelet ~100MB, kube-proxy ~50MB, etcd if control plane)
2. **Operational complexity**: k3s on 3 separate VPS nodes requires either a single control plane (on KVM4-1, consuming ~1GB RAM) or separate clusters (defeating the purpose)
3. **Existing investment**: The 5-tier network isolation, hardening anchors, and env-file tier system are mature in docker-compose and would need complete reimplementation for K8s
4. **NetworkPolicies as inspiration**: The existing K8s NetworkPolicies should be translated to docker-compose internal networks + Tailscale ACLs rather than deployed as-is

**When to revisit K8s:**
- When VPS nodes are upgraded to 8+ vCPU / 32GB+ RAM
- When the fleet exceeds 5 distributed nodes requiring automated scheduling
- When workloads need horizontal auto-scaling (currently all services are single-instance)
- Phase 3 roadmap target (Q2-Q3 2026) for k3s evaluation

---

## 6. Specific Deployment Recommendations Per VPS Node

### 6.1 KVM4-1: API Gateway Node

**Docker Compose overlay**: `docker-compose.kvm4-1.yml`

**Services to deploy:**

~~~yaml
# Pseudo-structure — actual overlay would reference base anchors
services:
 nginx:                    # SSL termination, reverse proxy
   <<: *tier-api-hardened
   ports: ["443:443", "80:80"]
 gateway:                   # Core API
   <<: *tier-api-hardened
 botz-gateway:              # Agent orchestration
   <<: *tier-app-hardened
 presign:                   # Auth
   <<: *tier-api-hardened
 tensorzero-config-api:     # LLM routing
   <<: *tier-api-hardened
 node-registry:             # Service discovery
   <<: *tier-api-hardened
 model-registry:            # Model metadata
   <<: *tier-api-hardened
 publisher-discord:         # Discord integration
   <<: *tier-app-hardened
 messaging-gateway:         # Multi-platform
   <<: *tier-api-hardened
~~~

**Memory budget**: 10GB services + 2GB runner + 4GB OS = 16GB (tight fit)
**Action**: Add swap (4GB) as safety margin. Monitor with Prometheus on KVM2.

**Pre-deployment checklist:**
- [ ] Create `env.shared` and `env.tier-api` with KVM4-1-specific values
- [ ] Configure Nginx upstream blocks pointing to Tailscale IPs for data-plane services on KVM4-2
- [ ] Set up Let's Encrypt or import SSL certificates
- [ ] Convert GitHub Actions runner to systemd service
- [ ] Configure firewall (ufw): allow 80, 443, 22 only from Tailscale/GitHub IPs

### 6.2 KVM4-2: Data Plane Node

**Docker Compose overlay**: `docker-compose.kvm4-2.yml`

**Services to deploy:**

~~~yaml
services:
 supabase-db:              # PostgreSQL
   <<: *tier-data-hardened
 supabase-rest:             # PostgREST
   <<: *tier-api-hardened
 supabase-storage:          # Object storage
   <<: *tier-api-hardened
 supabase-vector:           # pgvector
   <<: *tier-data-hardened
 qdrant:                    # Vector search
   <<: *tier-data-hardened
 neo4j:                     # Graph DB
   <<: *tier-data-hardened
 meilisearch:               # Full-text search
   <<: *tier-data-hardened
 nats:                      # NATS leaf node (connects to z890 hub)
   <<: *tier-data-hardened
 clickhouse:                # TensorZero analytics
   <<: *tier-data-hardened
~~~

**Memory budget**: 12GB databases + 2GB runner + 2GB OS = 16GB (tight fit)
**Critical risk**: Supabase + Qdrant + Neo4j + Meilisearch simultaneously may exceed 16GB under load.
**Action**: Consider moving Meilisearch or ClickHouse to SPARK (119GB RAM available) to relieve memory pressure.

**Pre-deployment checklist:**
- [ ] Create `env.shared` and `env.tier-data` with KVM4-2-specific values
- [ ] Configure NATS as leaf node connecting to z890 hub (`--leafnodes --leafnode.remotes=nats://z890-tailscale-ip:7422`)
- [ ] Set up volume persistence (bind mounts to host, not tmpfs)
- [ ] Convert GitHub Actions runner to systemd service
- [ ] Configure firewall: allow only Tailscale subnet + NATS leaf node port

### 6.3 KVM2: Exit/Observability Node

**Docker Compose overlay**: `docker-compose.kvm2.yml`

**Services to deploy:**

~~~yaml
services: 
 tailscale-exit:            # Exit node (containerized or host)
 nginx-exit:                # Exit proxy
   <<: *tier-api-hardened
 prometheus:                # Metrics scrape
   <<: *tier-worker-hardened
 alertmanager:              # Alert routing
   <<: *tier-worker-hardened
 alertmanager-discord-bridge:  # Discord alerts
   <<: *tier-worker-hardened
 grafana:                   # Dashboards
   <<: *tier-ui-hardened
 resource-detector:         # Fleet resource detection
   <<: *tier-worker-hardened
~~~

**Memory budget**: 4GB monitoring + 2GB runner + 2GB OS = 8GB (adequate)
**Advantage**: KVM2 has spare capacity for log aggregation (Loki/vector) if needed.

**Pre-deployment checklist:**
- [ ] Create `env.shared` and `env.tier-worker` with KVM2-specific values
- [ ] Configure Prometheus scrape targets pointing to Tailscale IPs of all nodes
- [ ] Set up Grafana datasource connections to Prometheus on localhost and ClickHouse on KVM4-2
- [ ] Configure `fleet-audit-watcher.sh` as a cron job or systemd timer
- [ ] Convert GitHub Actions runner to systemd service
- [ ] Enable Tailscale exit node feature (`tailscale up --advertise-exit-node`)

### 6.4 SPARK Node: Compute Backbone

See Section 7 below for detailed SPARK recommendations.

---

## 7. SPARK Node Role in the Fleet

### 7.1 Current State vs. TAC Tree

| Aspect | TAC Tree | Actual State |
|--------|----------|--------------|
| Hardware | GB10 Grace-Blackwell, 128GB unified, GPU | ✅ Matches — NVIDIA DGX Spark, GB10 Grace-Blackwell, 128GB unified, CUDA GPU |
| Ollama | gemma4:31b, nemotron-super-49b at :11434 | ✅ Active on CUDA at :11434 |
| NIM API | OpenAI-compatible at :8200 | ✅ Active at :8200 |
| NATS GPU Mesh | 5 subjects, 10s heartbeat | ⚠️ Subjects defined but TAC marks `status: future` — understates actual capability |
| GitHub Runner | Not mentioned in TAC | Active (self-hosted, spark, Linux, ARM64) |
| Agent Zero | Not mentioned in TAC | Active (this container) |

### 7.2 Recommended SPARK Role: GPU Inference Secondary + Compute Hub

SPARK has a GB10 Grace-Blackwell superchip with CUDA GPU — it IS a GPU inference node, not aspirational. Its role should be "GPU Inference Secondary" (behind 5090 as primary) plus general compute hub. With 20 ARM64 cores, 128GB unified memory, and CUDA GPU, SPARK is the most capable node in the fleet:

- **vs. KVM4-1**: 5x cores, 8x RAM, +CUDA GPU
- **vs. KVM4-2**: 5x cores, 8x RAM, +CUDA GPU
- **vs. KVM2**: 10x cores, 16x RAM, +CUDA GPU
- **vs. z890**: Superior unified memory (128GB vs 64GB), comparable GPU (Blackwell vs 3090Ti)

### 7.3 Specific Role Assignments for SPARK

**Role 1: A2A/MCP Relay Hub**
- Deploy `pmoves_registry` MCP server — central service registry for the entire fleet
- Deploy `pmoves_health` MCP server — aggregate health from all nodes
- Deploy `pmoves_announcer` MCP server — agent broadcast coordination
- Deploy A2A relay endpoint — cross-node agent communication hub
- Rationale: SPARK is always-on (DGX hardware), has excess capacity, and is centrally positioned in Tailscale mesh

**Role 2: GPU + CPU Agent Sessions**
- Agent Zero deep research sessions (this workload — CPU-bound, memory-intensive)
- DeepResearch agent (long-running analysis tasks)
- Archon agent (architecture analysis)
- EvoController/EvoSwarm (evolutionary computation)
- AgentGym RL coordinator
- Rationale: 128GB unified memory + CUDA GPU allows GPU-accelerated inference and multiple concurrent agent sessions with large context windows

**Role 3: Data Offload for Memory-Pressured Nodes**
- Meilisearch (moved from KVM4-2 to relieve 16GB constraint)
- ClickHouse (moved from KVM4-2)
- Notebook-sync storage
- Rationale: SPARK has 119GB RAM with no GPU contention — ideal for memory-heavy but CPU-light services

**Role 4: NATS Super-Connector**
- NATS server (not leaf node — full hub) connecting all VPS leaf nodes
- Replaces z890 as NATS hub for VPS fleet (z890 retains hub for on-prem GPU nodes)
- Rationale: Always-on, centrally located, excess network capacity

**Role 5: Secondary GPU Inference**
- Ollama with GPU-accelerated models (gemma4:31b, nemotron-super-49b, qwen3-coder-480b)
- NIM API at :8200 for OpenAI-compatible inference
- Handles overflow from 5090 primary GPU and batch inference jobs
- Rationale: GB10 Grace-Blackwell GPU with 128GB unified memory can run large models that exceed 5090's VRAM

**Role 6: GitHub Actions Runner (Existing)**
- ARM64-specific builds and tests
- Docker multi-arch builds (ARM64 layer)
- CPU-intensive CI workflows (lint, test, build)
- Rationale: Already active, leverages 20 cores for parallel builds

### 7.4 SPARK TAC Tree Remediation

The current `dgx-spark.tac.yaml` should be updated:

1. **Remove `status: future` from GPU inference phases** — Ollama and NIM are active, not aspirational. The GPU claims are accurate.
2. **Update NATS GPU mesh phases** — If mesh subjects are active, change from `status: future` to `status: active`. If not yet wired, keep `future` but add a note that GPU hardware is operational.
3. **Add A2A/MCP hub phases** — Document SPARK's role as fleet relay hub.

### 7.5 SPARK Memory Budget

| Component | Estimated RAM |
|-----------|--------------|
| Agent Zero (this session) | 2-4GB |
| Ollama (GPU models) | 20-40GB |
| NIM API | 4-8GB |
| MCP Registry + Health + Announcer | 1GB |
| A2A relay | 0.5GB |
| NATS hub | 0.5GB |
| Meilisearch (relocated) | 2-4GB |
| ClickHouse (relocated) | 2-4GB |
| GitHub Actions runner | 1-2GB |
| OS + overhead | 4GB |
| Total | 37-70GB of 128GB |

SPARK has ~58-91GB of unallocated RAM — substantial headroom for growth.

---

## 8. Implementation Priority Matrix

| Priority | Action | Effort | Impact | Dependencies | Status |
|----------|--------|--------|--------|-------------|--------|
| P0-1 | Convert VPS runners to systemd services | Low | High (reboot resilience) | None | Open |
| P0-2 | Fix runner install.sh root bug | Low | High (prevents future failures) | None | Open |
| P0-3 | Create per-node docker-compose overlays | Medium | High (enables distribution) | Env files, Tailscale IPs | Open |
| P0-4 | Deploy KVM4-1 as API Gateway | Medium | High (public services online) | P0-3, SSL certs | Open |
| P1-1 | Deploy KVM4-2 as Data Plane | Medium | High (data services online) | P0-3, NATS leaf config | Open |
| P1-2 | Deploy KVM2 as Observability | Low | Medium (visibility) | P0-3, Prometheus config | Open |
| P1-3 | Deploy MCP registry on SPARK | Low | High (fleet discovery) | None | Open |
| P1-4 | Remap SPARK TAC tree to actual role | Low | Medium (documentation accuracy) | None | Partially addressed — GPU hardware confirmed; TAC tree status tags still need updating |
| P2-1 | Move Meilisearch/ClickHouse to SPARK | Low | Medium (KVM4-2 memory relief) | P1-1, SPARK NATS hub | Open |
| P2-2 | Configure SPARK as NATS hub for VPS fleet | Low | Medium (message bus reliability) | Tailscale ACLs | Open |
| P2-3 | Deploy A2A relay on SPARK | Medium | High (cross-node agents) | P1-3, A2A endpoint config | Partially done — PR #1293 added A2A to compose but no standalone endpoint |
| P3-1 | Implement P7 Phase 5 Tailscale routing | High | High (unified entry point) | P1-3, P2-3 | Open |
| P3-2 | Update specialization matrix document | Low | Medium (operational clarity) | All above | Open |
| P3-3 | Create PMOVES.AIPLANS/infrastructure-enhancement.md | Low | Medium (planning record) | All above | Open |

*Status updated 2026-04-19 post-PR review (#1293, #1294, #1295, #1296, #1299)*

---

## 9. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|------------|
| KVM4-1 memory exhaustion under load | Medium | High | Add 4GB swap; offload low-priority services; monitor with Prometheus |
| KVM4-2 database memory contention | High | High | Move Meilisearch/ClickHouse to SPARK; set DB memory limits |
| Tailscale latency between VPS nodes | Low | Medium | VPS nodes are in same Hostinger DC; verify with ping tests |
| NATS leaf node disconnect | Medium | Medium | Configure reconnect with backoff; SPARK hub always-on |
| SPARK ARM64 compatibility issues | Low | Medium | Test all services on ARM64 before deployment; some services may need x64 emulation |
| Docker Compose cross-host networking gaps | High | High | Use Tailscale for service-to-service communication, not Docker networks |
| Runner nohup crash before systemd fix | Medium | Medium | Document manual restart procedure; prioritize P0-1 |
| SPARK TAC tree understates GPU capability (status: future on active features) | Medium | Low | Update TAC tree status tags (P1-4) to reflect operational GPU state |

---

## 10. Appendix: Source File References

| Document | Path | Key Findings Used |
|----------|------|-------------------|
| Hybrid Runner Strategy | `deploy/HYBRID_RUNNER_STRATEGY.md` | Runner fleet table, routing logic, Phase 3 k3s plan, cost model |
| Roadmap W1-W5 | `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` | P7 phases, Discord classrooms, enterprise tier, A2A/P7 integration points |
| PHI Claim Register | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Active claims, fleet networking session results, agent handoff patterns |
| Docker Compose Base | `pmoves/docker-compose.base.yml` | 5-tier networks (data/api/app/bus/monitoring + external), 18 volume definitions, hardening anchors |
| SPARK TAC Tree | `pmoves/configs/tac_trees/dgx-spark.tac.yaml` | GPU capabilities match actual hardware (GB10 Grace-Blackwell), NATS mesh subjects (status tags need updating), Ollama/NIM endpoints active |
| K8s Base | `deploy/k8s/base/pmoves-core-deployment.yaml` | Skeletal deployment (single pod), resource limits, health probes |
| K8s NetworkPolicies | `deploy/k8s/networkpolicies/` | 6 policies (default-deny + 5 allow), tier-matched to compose networks |
| Services Directory | `pmoves/services/` | 70+ service folders classified into 6 deployment tiers |
| KVM Setup Script | `deploy/provision/hostinger-kvm-setup.sh` | VPS role definitions (API Gateway, Data/Storage, Exit Node) |

---

*Report generated by Deep Research agent for PMOVES.AI infrastructure planning.*
*All infrastructure identifiers use generic placeholders per operational security policy.*
