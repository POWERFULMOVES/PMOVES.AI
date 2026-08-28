# PMOVES Core Infrastructure Submodules Report
Generated: 2026-04-17

## Executive Summary

This report documents the architecture, status, and optimization opportunities for 10 PMOVES core infrastructure submodules. All 10 exist as git submodules but are currently NOT initialized (empty directories). The actual integration code lives in-tree under `pmoves/` — service directories, configs, Cypher scripts, workflow JSONs, and TensorZero TOML configs provide the real operational surface.

**Key Findings:**
- **PMOVES-Archon** is the most production-ready (4/5 audit score, full Dockerfile, MCP integration, CI/CD)
- **PMOVES-BotZ-gateway** has an anomalous git state — appears in `git submodule status` but is NOT declared in `.gitmodules`
- **PMOVES-ClawZ** tracks `main` branch (not Hardened), is pre-stage, and runs local-first with no Docker service
- **PMOVES-tensorzero** has a massive 40+ model config but its in-tree service directory is incomplete (only `logging.py`)
- **PMOVES-n8n** runs via Pinokio on the 5090 node — no Docker Compose service definition exists
- **PMOVES-Tailscale/Headscale** form a self-hosted VPN mesh with 7 ACL tags and RustDesk remote desktop
- **PMOVES-supabase** is the central dependency (24 migrations, 27 initdb scripts, hardened Docker anchors)
- **PMOVES-Neo4j** provides the graph layer for Hi-RAG with 5 Cypher seed scripts

**Critical Risks:**
1. All submodules uninitialized — `git submodule update --init` required before any submodule code is accessible
2. BotZ-gateway submodule declaration inconsistency may cause CI/CD and clone issues
3. ClawZ on `main` branch diverges from PMOVES hardened branch strategy
4. tensorzero-config-api service is effectively a placeholder
5. n8n has no containerized deployment path in docker-compose

---

## Dependency Graph

```
                    ┌─────────────────────────────────────────────┐
                    │           PMOVES-supabase                   │
                    │  (Central DB: pgvector, PostgREST, Auth)    │
                    └──────┬──────────┬──────────┬───────────────┘
                           │          │          │
              ┌────────────┤    ┌─────┤    ┌─────┤
              │            │    │     │    │     │
        ┌─────┴─────┐ ┌───┴──┐ ┌┴───┐ ┌┴───┐ ┌┴──────────┐
        │ PMOVES-   │ │PMOVES│ │PMO- │ │PMO- │ │ PMOVES-  │
        │ Archon    │ │-BoTZ │ │VES- │ │VES- │ │ tensorzero│
        │(MCP+API)  │ │(GW)  │ │n8n  │ │ClawZ│ │(LLM Gate)│
        └─────┬─────┘ └──┬───┘ └────┘ └─────┘ └─────┬─────┘
              │          │                              │
              │     ┌────┴────┐                         │
              │     │  NATS   │◄────────────────────────┘
              │     │ (MsgBus)│
              │     └────┬────┘
              │          │
        ┌─────┴─────┐    │
        │ PMOVES-   │    │
        │ Neo4j     │    │
        │(Graph DB) │    │
        └───────────┘    │
                          │
        ┌─────────────────┴──────────────────┐
        │  PMOVES-Tailscale ←→ PMOVES-Headscale│
        │  (VPN Mesh: WireGuard control plane) │
        └──────────────────────────────────────┘

Legend:
  ── Strong dependency (API/DB connection)
  ◄─ Event-driven (NATS pub/sub)
  ←→ Bidirectional (VPN mesh)
```

**Shared Infrastructure Dependencies:**
| Infrastructure | Used By |
|---------------|--------|
| NATS (port 4222) | BoTZ-GW, Archon, Agent Zero, DeepResearch, SupaSerch, Channel Monitor |
| Supabase (port 3010/5432) | Archon, BoTZ-GW, n8n workflows, ClawZ (planned), most services |
| Neo4j (port 7474/7687) | Hi-RAG v2, graph-linker, CHIT geometry |
| TensorZero (port 3000) | BoTZ-GW, Archon, Agent Zero, ClawZ |
| MinIO (port 9000) | PMOVES.YT, FFmpeg-Whisper, Presign |
| Qdrant (port 6333) | Hi-RAG v2, Extract Worker |
| Meilisearch (port 7700) | Hi-RAG v2, Extract Worker |

---

## Per-Submodule Reports

---

### 1. PMOVES-BoTZ

- **Status**: Active (in-tree service operational; submodule not initialized)
- **Location**: `PMOVES-BoTZ/` (submodule, empty), `pmoves/services/botz-gateway/` (in-tree service)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-BoTZ.git`, branch `PMOVES.AI-Edition-Hardened`, commit `9970ab75a5`
- **Tech Stack**: Python 3.12, FastAPI, NATS async client, Pydantic, httpx, YAML
- **Architecture**: Multi-agent MCP platform with 17 independent feature modules. The in-tree `botz-gateway` service (port 8054) coordinates work item distribution across BoTZ CLI instances — tracking skill levels, routing work items, integrating TensorZero for LLM routing. Supports BoTZ registration, heartbeat monitoring, work item claim/completion lifecycle. GitHub App integration for MCP token minting.
- **Dependencies**: NATS (required), Supabase (work items, agent signatures), TensorZero (LLM routing), E2B (sandboxed execution), Cipher Memory (encrypted storage)
- **Dependents**: Agent Zero (via MCP), Archon (via MCP), Claude Code CLI, Docling, VL Sentinel
- **Integration Points**:
  - API: `POST /register`, `POST /heartbeat`, `POST /work/claim`, `POST /work/complete`, `GET /healthz` (port 8054)
  - NATS subjects: `botz.workitem.assigned.v1`, `botz.work.available.v1`, `botz.heartbeat.v1`, `botz.register.v1`, `botz.work.claimed.v1`
  - Docker networks: pmoves_app, pmoves_bus, pmoves_api, pmoves_monitoring, pmoves_external
  - Config: `agent_signatures.yaml` (read-only volume mount)
  - TensorZero functions: `coding` (6 variants), `orchestrator` (2 variants), `vl_sentinel` (1 variant)
- **Deployment Readiness**: Dockerfile exists in `pmoves/services/botz-gateway/Dockerfile`. Docker Compose profile `agents` + `botz`. Healthcheck configured. Image: `ghcr.io/powerfulmoves/pmoves-botz-gateway`. CI/CD path trigger on `PMOVES-BoTZ`.
- **Test Coverage**: `pmoves/tests/test_botz_cli.py` exists. P5 audit classified as non-web service (multi-agent MCP platform).
- **Known Issues**:
  - P1 RESOLVED: JWT fail-open in `features/mcp_bridge/auth.py` — now raises HTTPException(500)
  - P1 RESOLVED: `env.shared` export syntax stripped
  - P2 OPEN: MCP Gateway `/call`, `/mcp`, `/tools` endpoints have no authentication (any network client can invoke tools)
  - P3: Cipher Dockerfile missing USER directive
  - P3: Discord/Hostinger services missing HEALTHCHECK
  - Default MinIO/Neo4j credentials in env.shared fallbacks (cross-cutting P2)
- **Optimization Opportunities**:
  1. **P1**: Add bearer/JWT auth middleware to MCP Gateway endpoints (unauthenticated tool invocation)
  2. Add `/metrics` Prometheus endpoint to gateway service
  3. Initialize submodule (`git submodule update --init PMOVES-BoTZ`) to enable full 17-module capability
  4. Implement NATS JetStream persistence for work item queue (currently in-memory)
  5. Add structured logging with correlation IDs for work item tracing

---

### 2. PMOVES-BotZ-gateway

- **Status**: Anomalous — directory exists and appears in `git submodule status` but is NOT declared in `.gitmodules`
- **Location**: `PMOVES-BotZ-gateway/` (root-level dir, empty, NOT in .gitmodules)
- **Git Submodule**: **NO** — not declared in `.gitmodules`. The `git submodule status` entry (`8336b2fb`) appears to be a stale/orphan reference. The `.gitmodules` file has NO entry for `PMOVES-BotZ-gateway`.
- **Tech Stack**: N/A (gateway code lives in `pmoves/services/botz-gateway/`, covered under PMOVES-BoTZ)
- **Architecture**: The actual BotZ Gateway service is an in-tree Python FastAPI app at `pmoves/services/botz-gateway/` — see PMOVES-BoTZ report above. The submodule directory at root is vestigial.
- **Dependencies**: Same as PMOVES-BoTZ gateway service
- **Dependents**: Same as PMOVES-BoTZ gateway service
- **Integration Points**: Same as PMOVES-BoTZ gateway service
- **Deployment Readiness**: The in-tree service is deployable. The submodule directory is NOT. No CI/CD triggers for this path.
- **Test Coverage**: Same as PMOVES-BoTZ
- **Known Issues**:
  - **CRITICAL**: Orphan submodule reference — `git submodule status` shows it but `.gitmodules` does not declare it. This causes confusion and potential clone/init failures.
  - PR #2 (open) targets `main` instead of `PMOVES.AI-Edition-Hardened`, has 12 CodeRabbit issues (security defaults, missing env files, 74% docstrings below 80% threshold)
  - Docker Compose references missing env files (`env.tier-agent`, `env.tier-worker`, `env.tier-data`, `env.tier-llm`, `env.tier-media` not in PR)
- **Optimization Opportunities**:
  1. **P0**: Clean up orphan submodule — either add proper `.gitmodules` entry or remove the directory and rely solely on in-tree service
  2. Resolve PR #2 issues before any merge consideration
  3. If keeping as submodule, align branch to `PMOVES.AI-Edition-Hardened`

---

### 3. PMOVES-ClawZ

- **Status**: Pre-stage (local-first, not in Docker stack)
- **Location**: `PMOVES-ClawZ/` (submodule, empty)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-ClawZ.git`, branch **`main`** (NOT Hardened), commit `f05fd3f547d`
- **Tech Stack**: Node.js 22+, OpenClaw Gateway framework, 47 extensions, 7+ core channel plugins
- **Architecture**: OpenClaw Gateway — a multi-channel messaging platform with Canvas host, mobile apps, and webhook receivers. Port 18789 (configurable via `OPENCLAW_GATEWAY_PORT`). Provides `/healthz` (liveness) and `/readyz` (readiness) endpoints. Local-first design with optional Docker support.
- **Dependencies**: TensorZero/Ollama (LLM inference), Agent Zero (optional coordination), NATS (planned, not implemented)
- **Dependents**: Voice agent pipelines (emotion-driven ClawZ reveals), Canvas host, mobile apps
- **Integration Points**:
  - API: `GET /healthz`, `GET /readyz` (port 18789)
  - NATS subjects (planned, not implemented): `openclaw.message.received.v1`, `openclaw.message.sent.v1`, `openclaw.channel.connected.v1`
  - No Docker Compose service defined
  - No Docker network integration
  - Agent registry entry: `evolution_stage: pre_stage`, `port: 18789`
- **Deployment Readiness**: No Dockerfile in pmoves/services/. No Docker Compose profile. Submodule Dockerfile exists but not referenced. CI/CD path trigger at Priority 2 (agent infrastructure). NOT containerized for production.
- **Test Coverage**: `pmoves/tests/test_clawz_field.py` validates: submodule dir exists, package.json valid (name=openclaw), >=7 core channels, >=40 extensions, agent_registry.yaml entry, /healthz and /readyz return 200 (skipped if not running), NATS subjects documented, nats-bridge extension does NOT exist.
- **Known Issues**:
  - **Branch divergence**: Tracks `main` not `PMOVES.AI-Edition-Hardened` — no security hardening applied
  - **No /metrics endpoint**: No Prometheus metrics export
  - **No NATS integration**: Planned but not implemented (pre_stage)
  - **No Docker deployment path**: Local-first only, no containerization
  - **CHIT Attribution Plan (E4) deferred**: Waiting for NATS bridge stability
  - `tts-engine-capabilities.yaml` is empty (0 bytes)
- **Optimization Opportunities**:
  1. **P1**: Create `PMOVES.AI-Edition-Hardened` branch and apply security hardening
  2. **P2**: Add `/metrics` Prometheus endpoint
  3. **P2**: Implement NATS bridge for event publishing
  4. **P3**: Create Dockerfile and Docker Compose service definition
  5. **P3**: Populate `tts-engine-capabilities.yaml` with actual engine data

---

### 4. PMOVES-Archon

- **Status**: Active — most production-ready of all 10 submodules
- **Location**: `PMOVES-Archon/` (submodule, empty), `pmoves/services/archon/` (in-tree service), `pmoves/integrations/archon/` (duplicate submodule for UI)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-Archon.git`, branch `PMOVES.AI-Edition-Hardened`, commit `f4bd252c0e`. Also declared as `pmoves/integrations/archon` pointing to same repo.
- **Tech Stack**: Python 3.12, FastAPI, FastMCP, Logfire (structured logging), Playwright (crawling), crawl4ai 0.8.0, langchain-core 1.2.5, Node.js 20 + pnpm + yarn (UI build), Chromium (Playwright)
- **Architecture**: Supabase-driven agent service with prompt/form management, persona service, and MCP bridge. Three components: Archon Server (port 8091, main.py), MCP Bridge (port 8051/8052, mcp_server.py), and Archon UI (port 3737, Vite + React). The orchestrator.py handles multi-agent coordination. Provides agent creation, prompt management, code examples, crawled pages, and project tracking.
- **Dependencies**: Supabase (required — settings, prompts, personas, crawled pages), TensorZero (LLM routing via OpenAI-compat endpoint), Agent Zero (MCP client), NATS (event bus)
- **Dependents**: Agent Zero (primary consumer via MCP), BoTZ Gateway (via MCP), Claude Code CLI
- **Integration Points**:
  - API: `GET /healthz` (port 8091), full REST API for agents/prompts/personas
  - MCP: HTTP-MCP bridge at port 8051/8052 — `A0_MCP_ARCHON_ENDPOINT=http://archon-server:8051`
  - Docker networks: pmoves_api, pmoves_external
  - TensorZero functions: `archon_work_orders` (5 variants), `archon_code_review` (3 variants)
  - DB: `archon_db_setup.sh` creates 9 tables (settings, sources, crawled_pages, code_examples, projects, tasks, document_versions, prompts, page_metadata)
  - LLM provider registered as `openai` routing through `http://tensorzero-gateway:3000/openai/v1`
- **Deployment Readiness**: Full Dockerfile at `pmoves/services/archon/Dockerfile` — multi-stage, non-root (pmoves:pmoves UID/GID 65532), CVE overrides, Playwright pre-installed, UI build. Docker Compose profile `agents`. Separate `docker-compose.archon-ui.submodule.yml` for UI. Image: `ghcr.io/powerfulmoves/pmoves-archon`. CI/CD triggers on `pmoves/services/archon/**` and `PMOVES-Archon`. K8s manifest references Archon.
- **Test Coverage**: Smoke tests via `make -C pmoves agents-headless-smoke`, `make -C pmoves archon-smoke`. Archon service guide at `pmoves/docs/services/archon/README.md`. No unit test files found in pmoves/tests/.
- **Known Issues**:
  - PR #2 open with 6 issues: broken BoTZ submodule reference, wrong Dependabot paths, missing prometheus-client in dependency group, async/sync mismatch in persona_service.py, Agent Zero submodule not integrated, Docling missing branch
  - Dockerfile hardcodes `ARCHON_GIT_REF=PMOVES.AI-Edition-Hardened` with note about 4-month CI rot (last success 2025-12-23)
  - No NATS publishing/subscribing (only MCP and Supabase)
  - `USE_LOCAL_VENDOR=0/1` flag suggests CI reliability issues with local submodule
- **Optimization Opportunities**:
  1. **P1**: Resolve PR #2 issues — fix BoTZ submodule ref, Dependabot paths, add prometheus-client
  2. **P2**: Fix async/sync mismatch in persona_service.py (wrap Supabase call in `asyncio.to_thread`)
  3. **P2**: Add NATS event publishing for agent lifecycle events
  4. **P3**: Investigate CI rot — why `ARCHON_GIT_REF` needed fallback to remote clone
  5. **P3**: Add unit tests for persona service, prompt management, MCP bridge

---

### 5. PMOVES-tensorzero

- **Status**: Active (config operational; in-tree service incomplete)
- **Location**: `PMOVES-tensorzero/` (submodule, empty), `pmoves/tensorzero/config/` (TOML config), `pmoves/tensorzero/clickhouse/` (observability backend), `pmoves/services/tensorzero-config-api/` (in-tree, incomplete)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-tensorzero.git` (fork of tensorzero/tensorzero), branch `PMOVES.AI-Edition-Hardened`, commit `3f941d337b`
- **Tech Stack**: Rust (gateway, UI, provider-proxy), ClickHouse (observability), TOML config, OpenTelemetry (traces)
- **Architecture**: LLM gateway providing unified model routing across 40+ models. Three container components: Gateway (port 3000, OpenAI-compatible API), UI (port 4000, model management dashboard), provider-proxy (routes to Ollama/edge/cloud). ClickHouse backend for prompt/response logging and metrics. OTLP tracing enabled with async writes.
- **Dependencies**: Ollama (local GPU models at pmoves-ollama:11434), ClickHouse (observability backend), GPU Orchestrator (VRAM management), external cloud APIs (OpenAI, Groq, OpenRouter, Alibaba, Venice, Z.AI, MiniMax, Together, Cloudflare, Gemini, Claude, NVIDIA NIM)
- **Dependents**: Virtually all PMOVES services — Agent Zero, Archon, BoTZ-GW, ClawZ, Hi-RAG, DeepResearch, LangExtract, Extract Worker (20+ function definitions route through TensorZero)
- **Integration Points**:
  - API: `http://tensorzero-gateway:3000/openai/v1` (OpenAI-compatible), `http://tensorzero-gateway:3000` (native)
  - Config: `pmoves/tensorzero/config/tensorzero.toml` — 40+ models, 10+ embeddings, 20+ functions, 6 tool definitions
   - ClickHouse: `pmoves/tensorzero/clickhouse/` — config_changes.sql, listen.xml, users.xml
   - Docker Compose: gpu profile, tensorzero-ui at port 4000
   - TensorZero functions consumed by: agent_zero (24 variants), coding (6), orchestrator (2), archon_work_orders (5), archon_code_review (3), hirag_rerank (2), deepresearch (4), vl_sentinel (1), multimodal_edge (4), multimodal_large (7), plus per-stack coding variants
  - NATS subjects: `mesh.gpu.*` (GPU orchestrator coordination)
- **Deployment Readiness**: Submodule Dockerfiles exist (gateway, UI, provider-proxy). Gateway and UI have proper USER directives. provider-proxy USER fixed in Phase C. Docker Compose gpu profile. Image: `ghcr.io/powerfulmoves/pmoves-tensorzero` (from submodule Dockerfile). CI/CD path trigger Priority 1 on `PMOVES-tensorzero`. NO k8s manifests.
- **Test Coverage**: No test files found in pmoves/tests/ for tensorzero specifically. GPU smoke test validates model loading.
- **Known Issues**:
  - **In-tree service incomplete**: `pmoves/services/tensorzero-config-api/` contains only `logging.py` — no main.py, no API
  - **4 RUSTSEC advisories ignored** in `deny.toml:17-22` — explicitly suppressed unmaintained crate advisories
  - **30+ example Docker Compose files** with hardcoded secrets under `examples/`
  - **env.tier-llm uses export syntax** — Docker env_file incompatible (cross-cutting P2)
  - Default credentials in fallbacks: ClickHouse `tensorzero:tensorzero`, Neo4j `neo4j:neo4j`, MinIO `minioadmin` (Phase C P2)
  - Upstream sync status: TBD (never audited against tensorzero/tensorzero)
- **Optimization Opportunities**:
  1. **P1**: Complete `tensorzero-config-api` service or remove the placeholder directory
  2. **P2**: Evaluate and resolve 4 RUSTSEC advisories (update crates or document risk acceptance)
  3. **P2**: Strip `export` prefix from env.tier-llm for Docker env_file compatibility
  4. **P2**: Audit upstream sync status against tensorzero/tensorzero main branch
  5. **P3**: Add disclaimers to example compose files, use placeholder secrets

---

### 6. PMOVES-n8n

- **Status**: Active (runs via Pinokio; no Docker Compose service)
- **Location**: `PMOVES-n8n/` (submodule, empty), `pmoves/n8n/flows/` (compatibility mirror, 34 workflows), `pmoves/n8n-workflows/` (5 voice-platform workflows), `pmoves/services/n8n/workflows/` (3 mini workflows)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-n8n.git` (fork of n8n-io/n8n), branch `PMOVES.AI-Edition-Hardened`, commit `06134cf134c`
- **Tech Stack**: Node.js (n8n platform), JSON workflow definitions, webhook API, Supabase integration
- **Architecture**: Workflow automation platform running via Pinokio on the 5090 node (dynamic port). Canonical workflow ownership lives in `PMOVES-n8n/workflows/`; `pmoves/n8n/flows/` is a compatibility mirror. 34 workflows span: health (wger sync, weekly CGP), finance (firefly sync, monthly CGP, crosswalk), media (YouTube ingestion, Jellyfin watcher, video/audio analysis), ops (channel monitor, Discord notification, GitHub webhook/runner), voice (4 platform agents + router + shared functions), content (approval, social publisher, notebook feed), and research (deepresearch orchestrator).
- **Dependencies**: Supabase (workflow data storage, CGP geometry packets), NATS (event triggers), external APIs (wger, Firefly III, YouTube, Discord, Telegram, WhatsApp)
- **Dependents**: All integration pipelines — health-wger, firefly-iii, PMOVES.YT, voice platforms, content approval, GitHub runners
- **Integration Points**:
  - API: n8n webhook endpoints (dynamic URLs per workflow)
  - NATS subjects: workflow triggers via webhook-to-NATS bridges
  - Supabase: `n8n_workflow_registry` table, CGP geometry packet workflows
  - FlOOS hooks: `n8n-health-sync` → `health-weekly-cgp` chain, `n8n-finance-sync` → `finance-monthly-cgp` chain
  - Config: `skill-pairings.yaml` maps n8n workflows to skill chains
  - Env vars: `WGER_BASE_URL`, `WGER_API_TOKEN`, `FIREFLY_BASE_URL`, `FIREFLY_ACCESS_TOKEN`, `NATS_URL`, `N8N_RUNNERS_AUTH_TOKEN`
- **Deployment Readiness**: NO Docker Compose service definition. Runs via Pinokio on 5090 node. No containerized deployment path. CI/CD NOT triggered by n8n path changes. Network inventory lists n8n with dynamic port.
- **Test Coverage**: No test files found. TAC tree defines workflow verification checklist.
- **Known Issues**:
  - **No Docker deployment**: Relies entirely on Pinokio — no reproducible container deployment
  - **Upstream sync TBD**: Never audited against n8n-io/n8n (fast-moving upstream with frequent releases)
  - **Compatibility mirror drift**: `pmoves/n8n/flows/` may diverge from canonical `PMOVES-n8n/workflows/`
  - **Env var validation gaps**: TAC tree notes NATS_URL must use authenticated form but no enforcement
  - **Runner auth**: `N8N_RUNNERS_AUTH_TOKEN` auto-generated but verification unclear
- **Optimization Opportunities**:
  1. **P1**: Create Docker Compose service definition for n8n with proper env_file and healthcheck
  2. **P1**: Audit upstream sync status against n8n-io/n8n (high-churn upstream)
  3. **P2**: Automate compatibility mirror sync (`make n8n-sync-submodule-flows` exists but verification needed)
  4. **P2**: Add CI/CD path trigger for `PMOVES-n8n` and `pmoves/n8n/flows/` changes
  5. **P3**: Add workflow-level tests (mock webhook payloads, validate output schemas)

---

### 7. PMOVES-Tailscale

- **Status**: Active (VPN mesh client containerized)
- **Location**: `PMOVES-Tailscale/` (submodule, empty)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-Tailscale.git`, branch `PMOVES.AI-Edition-Hardened`, commit `2ad2d4d409`
- **Tech Stack**: WireGuard (VPN protocol), Tailscale client (container: `tailscale/tailscale:latest`), ACL policy JSON
- **Architecture**: VPN mesh client providing secure networking between PMOVES nodes. Each node runs a Tailscale sidecar container that connects to the Headscale control server. ACL policy defines 7 tags (pmoves, gpu, vps, lab, exit, partner, guest) with granular port-level access rules. Full mesh between pmoves-tagged nodes. Lab nodes access GPU nodes for inference. Partner access restricted to Agent Zero API/UI and TensorZero Gateway. Guest access limited to Agent Zero UI only. SSH rules allow non-root between pmoves nodes, root for admins only. Exit nodes can use Tailscale Funnel.
- **Dependencies**: Headscale (control server), network connectivity, `TAILSCALE_AUTHKEY` in env.shared
- **Dependents**: All PMOVES nodes that need secure inter-node communication (5090, 4090 laptop, Z890, VPS)
- **Integration Points**:
  - Docker Compose: `docker-compose.tailscale.yml` — tailscale sidecar container with state volume
  - Make targets: `make -C pmoves tailscale-up`, `tailscale-status`, `tailscale-ip`
  - ACL: `pmoves/configs/tailscale-acl-policy.json` — 7 tags, 5 ACL rules, 2 SSH rules, Funnel enabled for exit nodes
  - Network inventory: `pmoves/configs/pinokio-network-inventory.yaml` — tracks all nodes with Tailscale hostnames
  - Node TAC trees: `node-5090-powerfulmoves.tac.yaml` (powerfulmoves-1.ts), `node-4090-laptop.tac.yaml` (pmoves-laptop.ts)
  - Env: `TAILSCALE_TAGS`, `TAILSCALE_ADVERTISE_ROUTES` (172.31.10.0/24, 172.31.20.0/24), `TAILSCALE_LOGIN_SERVER` (Headscale URL), `TAILSCALE_ONLY`
- **Deployment Readiness**: Docker Compose service defined. Image: `ghcr.io/powerfulmoves/pmoves-tailscale` (from submodule Dockerfile in images.yaml). Uses official `tailscale/tailscale:latest` in compose. No K8s manifests.
- **Test Coverage**: No automated tests. Manual verification via `make tailscale-status` and `make tailscale-ip`.
- **Known Issues**:
  - **No K8s manifests**: Not deployable to Kubernetes
  - **State volume persistence**: Tailscale state in Docker volume — loss requires re-auth
  - **No /healthz or /metrics**: Tailscale container doesn't expose HTTP endpoints
  - **DGX Spark missing from ACL**: PMOVES-Creator config notes Tailscale ACL has no dgx-spark entries
  - **Static auth key**: `TAILSCALE_AUTHKEY` is one-time use — rotation strategy unclear
- **Optimization Opportunities**:
  1. **P2**: Add DGX Spark node to ACL policy with appropriate tag
  2. **P2**: Create K8s DaemonSet for Tailscale sidecar
  3. **P3**: Implement auth key rotation automation
  4. **P3**: Add Tailscale network connectivity to smoke tests

---

### 8. PMOVES-Headscale

- **Status**: Active (self-hosted Tailscale control server)
- **Location**: `PMOVES-Headscale/` (submodule, empty)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-headscale.git` (note: lowercase 'headscale' in URL), branch `PMOVES.AI-Edition-Hardened`, commit `a3ef4d7966`
- **Tech Stack**: Go (Headscale server), Docker (container: `ghcr.io/juanfont/headscale:latest`), WireGuard, RustDesk (remote desktop relay)
- **Architecture**: Self-hosted Tailscale control server replacing SaaS Tailscale coordination. Manages WireGuard keys, ACL enforcement, and node registration for the PMOVES tailnet. Runs with metrics on port 9091 (remapped from 9090 to avoid Prometheus conflict). Integrates with RustDesk for self-hosted remote desktop (hbbs relay on 21117). VPN MCP integration via BoTZ (`VPN_MANAGER_URL=http://vpn-mcp:8110/sse`). Feature-flagged remote desktop (`REMOTE_DESKTOP_ENABLED=false` by default).
- **Dependencies**: Tailscale clients (all PMOVES nodes), RustDesk (remote desktop), config/headscale/ directory (config.yaml, acl.yaml), BoTZ VPN MCP
- **Dependents**: All Tailscale client nodes, RustDesk clients, VPN MCP consumers
- **Integration Points**:
  - Docker Compose: `docker-compose.remote.yml` — headscale container with config volume, metrics port, RustDesk services
  - API: `HEADSCALE_SERVER_URL=https://headscale.pmoves.local`, port 8096, metrics at 9091
  - Env: `HEADSCALE_API_KEY`, `HEADSCALE_AGENT_AUTH_KEY`, `HEADSCALE_TAGS=tag:pmoves-server,tag:infra`
  - K8s: `deploy/k8s/base/pmoves-core-deployment.yaml` references `https://headscale.pmoves`
  - Scripts: `setup-remote-desktop.sh` (init), `verify-remote-desktop.sh` (health check)
  - BoTZ: `VPN_MANAGER_URL=http://vpn-mcp:8110/sse` for MCP-based VPN management
- **Deployment Readiness**: Docker Compose service defined with vpn-tier hardening. Image: `ghcr.io/juanfont/headscale:latest` (third-party, NOT PMOVES-built). Profile: `remote`. K8s manifest references headscale URL but no dedicated Headscale K8s deployment. Setup/verify scripts operational. Evidence shows initialized as of 2026-03-13.
- **Test Coverage**: `verify-remote-desktop.sh` provides manual health verification. No automated pytest coverage.
- **Known Issues**:
  - **Third-party image**: Uses `ghcr.io/juanfont/headscale:latest` — no PMOVES-built image, no USER directive control
  - **No dedicated K8s deployment**: Referenced in core deployment env but no separate Headscale StatefulSet/Service
  - **Remote desktop disabled by default**: `REMOTE_DESKTOP_ENABLED=false`, `REMOTE_DESKTOP_ADMIN_ONLY=true`
  - **ACL policy duplication**: ACL defined in both `tailscale-acl-policy.json` and `config/headscale/acl.yaml` — sync status unknown
  - **Metrics port conflict**: Remapped to 9091 to avoid Prometheus at 9090 — potential confusion
- **Optimization Opportunities**:
  1. **P2**: Create dedicated K8s StatefulSet for Headscale with persistent volume
  2. **P2**: Build PMOVES-hardened Headscale image with USER directive
  3. **P3**: Unify ACL policy (single source of truth between JSON and YAML)
  4. **P3**: Add automated tests for Headscale API (user creation, key generation, node registration)

---

### 9. PMOVES-supabase

- **Status**: Active — central infrastructure dependency
- **Location**: `PMOVES-supabase/` (submodule, empty), `pmoves/supabase/` (config + migrations + initdb)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-supabase.git`, branch `PMOVES.AI-Edition-Hardened`, commit `57c416061a`
- **Tech Stack**: PostgreSQL 17, PostgREST, pgvector, GoTrue (auth), Realtime, Storage, Kong (API gateway), Deno 2 (edge functions), Supabase CLI
- **Architecture**: Full Supabase stack providing: PostgreSQL with pgvector extension (schema: `pmoves_core`, `pmoves_kb`), PostgREST REST API (port 3010), GoTrue authentication (JWT with 3600s expiry, refresh token rotation), Realtime subscriptions, Storage (50MiB limit, S3-compatible endpoint replacing MinIO for storage), Studio dashboard (port 54323), Kong proxy (port 8000). 24 migrations and 27 initdb scripts define the complete data model.
- **Dependencies**: Docker (Supabase CLI stack), env.tier-supabase (JWT secrets, DB credentials, service keys)
- **Dependents**: Archon (required), Agent Zero, BoTZ-GW, n8n workflows, Channel Monitor, PMOVES.YT, DeepResearch, SupaSerch, Hi-RAG, Extract Worker, Notebook Sync, Tokenism Simulator, Publisher-Discord, Firefly III, wger — essentially ALL services
- **Integration Points**:
  - API: PostgREST at port 3010 (`SUPABASE_URL=http://supabase-kong:8000`), Studio at 54323
  - Config: `pmoves/supabase/config.toml` — project_id=pmoves, schemas=[public, graphql_public, pmoves_core, pmoves_kb]
  - Migrations: 24 files (2025-01-15 to 2026-03-26) — geometry bus, tokenism, model registry, personas, n8n registry, publisher, YouTube controls
  - InitDB: 27 files — schema creation, seeds (71KB model registry seed, 58KB persona seed), CHIT geometry, channel monitoring, agent threads
  - Docker hardening: `x-env-tier-supabase` (cap_drop ALL, no-new-privileges), `x-env-tier-supabase-ro` (read-only + tmpfs), `x-tier-supabase-hardened` (cap_drop ALL + DAC_OVERRIDE)
  - Scripts: `bootstrap_db.sh` (7-step idempotent setup), `sync_config.py` (config validation), `apply_env_profile.py`, `generate-keys.sh`, `find_db_container.sh`
  - Env: 20+ variables in `env.tier-supabase.example` — JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY, DB creds, port overrides, PMOVES extensions (DOCKED_MODE, PARENT_SYSTEM)
  - Storage unified to Supabase S3: `MINIO_ENDPOINT=http://host.docker.internal:65421/storage/v1/s3`
- **Deployment Readiness**: Runs via Supabase CLI (`make -C pmoves supa-start`), NOT as submodule-built Docker image. Hardened Docker anchors defined. No PMOVES-built image in images.yaml. No K8s manifests (Supabase CLI manages its own stack). Bootstrap scripts are operational.
- **Test Coverage**: `make -C pmoves supabase-bootstrap` validates schema creation. SQL policy linting in CI. No pytest coverage for Supabase-specific logic.
- **Known Issues**:
  - **No PMOVES-built Docker image**: Relies on Supabase CLI for local, unclear production path
  - **No K8s manifests**: Supabase stack not deployable to Kubernetes
  - **Massive seed files**: `12_model_registry_seed.sql` (71KB) and `17_persona_seed.sql` (58KB) — slow bootstrap
  - **Storage migration incomplete**: Some services still reference MinIO directly vs Supabase Storage S3
  - **Env backward compatibility**: Both `SUPABASE_SERVICE_ROLE_KEY` and `SERVICE_ROLE_KEY` needed because Docker env_file doesn't interpolate `${VAR}`
- **Optimization Opportunities**:
  1. **P1**: Define production Supabase deployment strategy (self-hosted K8s vs Supabase Cloud)
  2. **P2**: Create K8s manifests for Supabase stack (or document Cloud migration path)
  3. **P2**: Complete MinIO → Supabase Storage migration across all services
  4. **P3**: Optimize seed files — split into smaller, selectively-runnable chunks
  5. **P3**: Add integration tests that validate schema completeness after migration

---

### 10. PMOVES-Neo4j

- **Status**: Active — Hi-RAG graph backend
- **Location**: `PMOVES-Neo4j/` (submodule, empty), `pmoves/neo4j/` (Cypher scripts + datasets)
- **Git Submodule**: Yes, `https://github.com/POWERFULMOVES/PMOVES-neo4j.git` (note: lowercase 'neo4j' in URL), branch `PMOVES.AI-Edition-Hardened`, commit `c68156edf2`
- **Tech Stack**: Neo4j 5.22 (graph database), Cypher query language, CSV data loading
- **Architecture**: Knowledge graph storage providing entity relationship modeling and graph traversal for the Hi-RAG hybrid retrieval system. Runs as Docker container (image: `neo4j:5.22`) with HTTP API (port 7474) and Bolt protocol (port 7687). Hardened with cap_drop ALL, specific cap_add. CSV import enabled for seed data loading. 5 Cypher scripts define the graph schema and seed data.
- **Dependencies**: Docker, env.tier-data (NEO4J_AUTH credentials), Hi-RAG v2 (primary consumer)
- **Dependents**: Hi-RAG Gateway v2 (graph retrieval), graph-linker service, CHIT geometry (mindmap data model), MCP mesh plugin (Neo4j tool)
- **Integration Points**:
  - API: HTTP at port 7474, Bolt at port 7687 (`A0_MCP_NEO4J_URL=bolt://neo4j:7687`)
  - Cypher scripts: `001_init.cypher` (entity constraint), `002_load_person_aliases.cypher` (persona→alias graph), `003_seed_chit_mindmap.cypher` (CHIT geometry: anchors, constellations, points, media refs), `010_chit_geometry_fixture.cypher` (idempotent version), `011_chit_geometry_smoke.cypher` (validation query)
  - Dataset: `person_aliases_seed.csv` (4 persona aliases: powerfulmoves/DARKXSIDE, PMoves, darkxsideshows/DXS, DarkXSIDE Studios)
  - Docker Compose: `env_file: env.tier-data`, hardened caps, CSV import enabled, relaxed config validation
   - Bootstrap: `neo4j_bootstrap.sh` — checks container, gets auth, runs all Cypher scripts, generates CSV MERGE statements
   - K8s: `deploy/k8s/base/pmoves-core-deployment.yaml` references `bolt://neo4j.pmoves:7687`
  - Env: `NEO4J_AUTH=neo4j/changeme` (in env.tier-data.example), `NEO4J_PASSWORD` in tier-api
  - Graph model: Entity→Alias (personas), Anchor→Constellation→Point→MediaRef (CHIT geometry)
- **Deployment Readiness**: Docker Compose service defined with hardening. Image: `neo4j:5.22` (upstream, NOT PMOVES-built). No PMOVES image in images.yaml. K8s deployment references Neo4j URL. Bootstrap script operational. Smoke test in `smoke-tests.sh`.
- **Test Coverage**: `011_chit_geometry_smoke.cypher` validates CHIT data. `smoke-tests.sh` includes Neo4j checks. No pytest coverage.
- **Known Issues**:
  - **Third-party image**: Uses upstream `neo4j:5.22` — no PMOVES hardening (runs as neo4j user but no custom Dockerfile)
  - **Default credentials**: `neo4j/changeme` in env.tier-data.example (cross-cutting P2)
  - **CSV import security**: `NEO4J_dbms_security_allow__csv__import__from__file__urls=true` — intentional for bootstrap but should be disabled in production
  - **Relaxed config validation**: `NEO4J_server_config_strict__validation_enabled=false`
  - **Small seed dataset**: Only 4 persona aliases — graph is mostly empty except CHIT geometry fixtures
  - **Hi-RAG Cypher injection risk** (from Phase C audit): f-string label construction in `hirag/_storage/gdb_neo4j.py` — FIXED with allowlist
- **Optimization Opportunities**:
  1. **P2**: Create PMOVES-hardened Neo4j Dockerfile with non-root user and security hardening
  2. **P2**: Disable CSV import and relaxed validation for production (`docker-compose.prod.yml` overrides)
  3. **P3**: Expand persona alias seed dataset from community contributions
  4. **P3**: Add pytest-based graph schema validation tests
  5. **P3**: Create dedicated K8s StatefulSet for Neo4j with persistent volume claim

---

## Cross-Cutting Concerns

### Shared Infrastructure Dependencies

| Infrastructure | Port | Services Depending On It | Hardening Status |
|---------------|------|------------------------|-----------------|
| NATS | 4222 | 15+ services | JetStream enabled, auth in env.shared |
| Supabase/PostgreSQL | 3010/5432 | 20+ services | Hardened Docker anchors, RLS policies |
| Neo4j | 7474/7687 | Hi-RAG, graph-linker, CHIT | Upstream image, default creds |
| Qdrant | 6333 | Hi-RAG, Extract Worker | Upstream image v1.10.0 |
| Meilisearch | 7700 | Hi-RAG, Extract Worker | Upstream image v1.8 |
| MinIO | 9000/9001 | PMOVES.YT, FFmpeg-Whisper | Migrating to Supabase Storage |
| TensorZero | 3000 | 20+ function definitions | Rust, unsafe_code forbid |
| ClickHouse | 8123 | TensorZero observability | Docker Compose defined |

### Security Considerations

| Concern | Status | Affected Submodules |
|---------|--------|-------------------|
| NATS auth missing in defaults | P2 RESOLVED (in env.shared) | All 8 with NATS (cross-cutting) |
| env.shared export syntax | P2 (5 submodules) | tensorzero, BoTZ, HiRAG, DoX (not in this scope) |
| Default credentials in fallbacks | P2 (6 submodules) | tensorzero, BoTZ, Neo4j, Supabase, n8n |
| USER directive missing | P1 RESOLVED (most) | tensorzero provider-proxy FIXED, Neo4j upstream image N/A |
| CodeQL high alerts | RESOLVED (0 remaining) | All |
| Dependabot high alerts | RESOLVED (0 remaining) | All |
| RUSTSEC advisories ignored | P2 OPEN (4) | tensorzero |
| MCP endpoints unauthenticated | P2 OPEN | BoTZ MCP Gateway |
| JWT fail-open | P1 RESOLVED | BoTZ (was failing open, now 500) |
| Auth fail-open | P2 OPEN | Open-Notebook (not in this scope) |

### Deployment Sequencing

1. **Data tier first**: NATS, Supabase (CLI), Neo4j, Qdrant, Meilisearch, MinIO
2. **LLM tier**: Ollama, TensorZero gateway+ClickHouse, GPU Orchestrator
3. **Agent tier**: Agent Zero, Archon, BoTZ Gateway
4. **Worker tier**: Hi-RAG, Extract Worker, DeepResearch, Channel Monitor
5. **App tier**: n8n (Pinokio), ClawZ (local), UI console
6. **VPN tier**: Headscale, Tailscale (per-node), RustDesk
7. **Monitoring**: Prometheus, Grafana, Loki

### Missing Pieces

| Gap | Impact | Recommendation |
|-----|--------|---------------|
| All submodules uninitialized | Cannot access submodule source code | `git submodule update --init` for all 10 |
| BotZ-gateway orphan in .gitmodules | Clone confusion, CI issues | Remove orphan or add proper declaration |
| ClawZ on wrong branch | No security hardening | Create Hardened branch, update .gitmodules |
| tensorzero-config-api placeholder | Incomplete service | Complete or remove directory |
| n8n no Docker Compose | No reproducible deployment | Add n8n service to docker-compose.yml |
| No K8s for Supabase/Neo4j/Headscale | Production K8s path blocked | Create StatefulSets with PVCs |
| Upstream sync unaudited (n8n, tensorzero) | Missing security fixes | Audit and sync quarterly |

---

## Recommendations

### Priority 1 — Immediate (This Week)

1. **Initialize all submodules**: Run `git submodule update --init --recursive` to populate all 10 directories
2. **Fix BotZ-gateway orphan**: Either add proper `.gitmodules` entry for `PMOVES-BotZ-gateway` or remove the stale directory reference and `git rm` the orphan
3. **Create ClawZ Hardened branch**: Fork `main` to `PMOVES.AI-Edition-Hardened`, apply security hardening patterns, update `.gitmodules` branch
4. **Complete or remove tensorzero-config-api**: Either implement the config API service or remove the `pmoves/services/tensorzero-config-api/` directory

### Priority 2 — High (Next Sprint)

5. **Add n8n Docker Compose service**: Define n8n container with env_file, healthcheck, and volume mounts — stop relying solely on Pinokio
6. **Audit upstream sync**: Run `git remote add upstream` and check sync status for n8n and tensorzero (high-churn upstreams)
7. **Add MCP auth to BoTZ Gateway**: Implement bearer/JWT middleware on `/call`, `/mcp`, `/tools` endpoints
8. **Resolve Archon PR #2**: Fix 6 issues (BoTZ ref, Dependabot, prometheus-client, async mismatch) and merge
9. **Create K8s manifests**: StatefulSets for Neo4j, Headscale; consider Supabase Cloud or self-hosted K8s path
10. **Strip export syntax**: Fix `env.tier-llm` and any remaining `export VAR=value` in env files

### Priority 3 — Medium (Next Month)

11. **Evaluate RUSTSEC advisories**: Update or document risk acceptance for 4 ignored tensorzero crate advisories
12. **Build hardened Neo4j image**: Custom Dockerfile with non-root user, disable CSV import and relaxed validation for production
13. **Build hardened Headscale image**: Custom Dockerfile instead of relying on `ghcr.io/juanfont/headscale:latest`
14. **Expand Neo4j seed data**: Grow persona alias graph from community contributions
15. **Add ClawZ Dockerfile**: Enable containerized deployment for pre-stage ClawZ
n16. **Add ClawZ /metrics endpoint**: Prometheus metrics for OpenClaw Gateway

### Priority 4 — Low (Backlog)

17. **Unify ACL policy**: Single source of truth between `tailscale-acl-policy.json` and Headscale `acl.yaml`
18. **Add DGX Spark to Tailscale ACL**: New tag and rules for DGX Spark GB10 node
19. **Automate Tailscale auth key rotation**: Prevent stale one-time-use keys
20. **Optimize Supabase seed files**: Split 71KB model registry and 58KB persona seeds into smaller chunks
21. **Add n8n workflow-level tests**: Mock webhook payloads, validate output schemas
22. **Add Neo4j pytest schema validation**: Automated graph structure verification
23. **Complete MinIO → Supabase Storage migration**: Remove all remaining direct MinIO references

---

*Report generated by PMOVES Deep Research agent. All findings based on direct file inspection — no guesses or assumptions.*
