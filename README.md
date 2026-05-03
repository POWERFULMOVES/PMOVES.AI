# PMOVES.AI

[![Integration Contract](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/integration-contract.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/integration-contract.yml)
[![CodeQL Advanced](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/codeql.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/codeql.yml)
[![CHIT Contract Check](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/chit-contract.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/chit-contract.yml)
[![Docker Hardening Validation](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/hardening-validation.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/hardening-validation.yml)
[![Python Tests](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/python-tests.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/python-tests.yml)

A local-first, multi-agent orchestration platform that coordinates autonomous agents (Agent Zero, Archon), hybrid retrieval (Hi-RAG v2), voice synthesis, media processing, and knowledge graphs — all wired together with NATS event-driven messaging and full Prometheus/Grafana/Loki observability.

PMOVES is structured as a **Metal-Organic Framework (MOF)** for distributed machine intelligence — the crystalline lattice through which autonomous agents flow. Operationally, this translates to a **rooms-on-a-stage** model: P7 (Pinokio 7) is the evolving room-aware stage manager that selects rooms, loads suits, and manages stage transitions (rehearsal → live → review → archive). This model grows with the platform — new rooms, stage states, and suit types are added as the topology evolves.

## Quick Start

```bash
make first-run
```

This single command orchestrates the full onboarding sequence: environment prompts, Supabase CLI bring-up, data/service seeding, core + agent + external stacks, and the 12-step smoke harness. When it finishes successfully every bundled integration (Wger, Firefly, Jellyfin, Open Notebook, Agent mesh) is online with branded defaults. See the [First-Run Bootstrap Overview](pmoves/docs/FIRST_RUN.md) for a detailed breakdown of each step.

## Key Directories

- **`CATACLYSM_STUDIOS_INC/`** – Provisioning bundles and infrastructure automations for homelab and field hardware, including unattended OS installs, Jetson bootstrap scripts, and ready-to-run Docker stacks that mirror the production mesh topology.
- **`docs/`** – High-level strategy, architecture, and integration guides for the overall PMOVES ecosystem. See also `pmoves/docs/ENVIRONMENT_POLICY.md` for the single-file environment policy and Jellyfin host-mount instructions.
- **`pmoves/`** – The primary application stack with docker-compose definitions, service code, datasets, Supabase schema, and in-depth runbooks for daily operations and advanced workflows.
- **`pmoves/contracts/solidity/`** – Hardhat workspace prototyping Food-USD / GroToken governance flows with automated tests that model staking, quadratic voting, and group-buy execution.
- **`pmoves/ui/`** – Next.js + Supabase Platform Kit workspace for the upcoming web UI; reuses `pmoves/.env.local` so frontend hooks can target the same Supabase CLI stack.

## Essential Documentation

- **[Claude Code CLI Integration](.claude/README.md)** – TAC integration with custom slash commands, security hooks, and PMOVES-aware context for AI-assisted development.
- **[Testing Strategy](docs/testing/TESTING.md)** – Comprehensive testing guide covering smoke tests, functional tests, and end-to-end validation workflows.
- [PMOVES Stack README](pmoves/README.md) – Quickstart environment setup, service inventory, and Codex bootstrap steps for running the orchestration mesh locally.
- [Local Tooling Reference](pmoves/docs/LOCAL_TOOLING_REFERENCE.md) – One-stop index for environment scripts, Make targets, Supabase workflows, smoke tests, and provisioning helpers.
- [Supabase Service Guide](pmoves/docs/services/supabase/README.md) – CLI vs compose expectations, realtime wiring (`supabase start --network-id pmoves-net`), and how PMOVES consumes PostgREST/Realtime in both local and self-hosted deployments.
- [PMOVES Docs Index](pmoves/docs/README_DOCS_INDEX.md) – Curated entry points into the pmoves-specific runbooks covering Creator Pipeline, ComfyUI flows, reranker configurations, and smoke tests.
- [UI workspace bring-up](pmoves/docs/LOCAL_DEV.md#ui-workspace-nextjs--supabase-platform-kit) – Next.js + Supabase quickstart (npm/yarn commands, env loading from `pmoves/.env.local`, Supabase CLI prerequisites).
- [Service Docs Index](pmoves/docs/services/README.md) – Per-service guides (overview, compose/ports, runbooks, smoke tests, and roadmap alignment).
- [External Integrations Bring-Up](pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md) – Wger, Firefly III, Open Notebook, and Jellyfin commands, token wiring, and port overrides for `make up-external`.
- [Architecture Primer](docs/PMOVES_ARC.md) – Deep dive into mesh topology, service responsibilities, and evolution of the orchestration layers.
- [Complete Architecture Map](pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md) – Full-fidelity view of the latest integration mesh, including data planes and edge deployments.
- [Multi-Agent Integration Guidelines](docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md) – Operational patterns for coordinating Agent Zero, Archon, and automation hubs across environments.
- [Archon Updates for PMOVES](pmoves/docs/PMOVES.AI%20PLANS/archonupdateforpmoves.md) – What changed in the October 2025 Archon bundle, how to wire the Supabase CLI stack, and the MCP/NATS expectations.
- [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) – Command catalog for starting, stopping, and tailoring compose profiles (core data plane, media analyzers, Supabase modes, and agent bundles).
- [Single-User (Owner) Mode](pmoves/docs/SECURITY_SINGLE_USER.md) – Personal-first operation without login prompts; boot-JWT auto-auth, owner chip in the UI, and security notes.
- [Production Readiness Report](pmoves/docs/PRODUCTION_READINESS_REPORT_2026-02-07.md) – Feb 2026 audit of service health, security posture, and deployment readiness.
- [Codex + Copilot Review Workflow](docs/COPILOT_REVIEW_WORKFLOW.md) – How to combine the Codex CLI reviewer with GitHub Copilot's PR assistant, including token setup and evidence logging expectations.

## CHIT & Geometry Documentation

Compressed Hierarchical Information Transfer (CHIT) and the Geometry Bus are core to how PMOVES.AI encodes, routes, and decodes structured knowledge across the agent mesh.

- **[CHIT Gateway API Reference](pmoves/docs/PMOVESCHIT/CHIT_GATEWAY_API.md)** – Full endpoint reference (encode/decode, calibration, HMAC signatures)
- **[CGP v1.0 Specification](pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md)** – Compressed Geometry Packet wire format
- **[Geometry Bus Integration](pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md)** – How services publish/subscribe geometry events via NATS
- **[PMOVESCHIT Overview](pmoves/docs/PMOVESCHIT/PMOVESCHIT.md)** – Compressed Hierarchical Information Transfer concepts
- **[Implementation Status](pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md)** – Current status of CHIT endpoints and security posture
- **[Local Model Setup](pmoves/docs/PMOVESCHIT/LOCAL_MODEL_SETUP.md)** – Running CHIT encoding/decoding with local models
- **[Three Body Doctrine](pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md)** – Foundational constraints governing geometry state propagation
- **[Integrating Math into PMOVES.AI](pmoves/docs/PMOVESCHIT/Integrating%20Math%20into%20PMOVES.AI.md)** – Mathematical foundations behind the geometry encoding

See [`pmoves/docs/PMOVESCHIT/`](pmoves/docs/PMOVESCHIT/) for the full 19-document collection including decoder specifications, neural-network notebooks, audit reports, and UI design specs.

## Rooms on a Stage

PMOVES' **Metal-Organic Framework** architecture manifests operationally as **rooms on a stage** — a living topology (not a frozen specification) with three layers:

- **Rooms** are the agent-owned entrypoints: infra fabric, field control, voice studio, workstation. Each room binds services, skills, and notebook state.
- **Stage** is the lifecycle state per room: `rehearsal` → `live` → `review` → `archive`. Rooms transition through these states as work progresses.
- **Suits** are the runtime/persona bindings layered onto rooms — upstream Agent Zero as the external baseline, PMOVES hardened overlays as the custom fit, voice/theme/persona as the visible styling layer.

**P7 (Pinokio 7)** is the evolving room-aware stage manager: it reads the room catalog, selects the appropriate room profile for a given workload, loads the correct suit, and manages stage transitions. P7's NATS subjects (`p7.nats.launch`, `p7.nats.session`) are the control plane for room entry and lifecycle. As the platform grows, P7's tree adds new rooms, stage states, and suit types — the topology is designed to expand.

Rooms own presentation and session ergonomics; the notebook plane owns durable memory. The [Room Manifest Contract](pmoves/docs/ROOM_MANIFEST_CONTRACT.md) defines the interface; [`pmoves/config/rooms/catalog.json`](pmoves/config/rooms/catalog.json) is the canonical seed catalog. See [AGNOTE4482](pmoves/docs/AGENTS/AGNOTE4482.md) for the full P7 specification.

### Room Index

#### 🏗️ Z890 Infra Fabric Room
**Purpose:** Infrastructure room for topology, service health, secrets discipline, and operator bring-up.
**Profile:** `z890-infra` · **Agent:** `z890-claude` · **Manifest:** [`z890-infra.room.fabric.json`](pmoves/config/rooms/z890-infra.room.fabric.json)

- `pmoves/services/node-registry/` — Multi-host node discovery and health reporting
- `pmoves/services/resource-detector/` — Hardware capability detection (GPU, CPU, memory)
- `pmoves/services/work-marshaling/` — Distributed task scheduling and work queue management
- `pmoves/services/gpu-orchestrator/` — GPU resource allocation and scheduling
- `pmoves/services/vllm-orchestrator/` — vLLM inference server lifecycle management
- `pmoves/services/model-registry/` — Central model catalog with version tracking
- `pmoves/services/tensorzero-config-api/` — Dynamic TensorZero model configuration API
- `pmoves/services/benchmark-runner/` — Automated performance benchmarking harness
- `pmoves/services/nats-echo/` — NATS message debugging and replay tool
- `pmoves/services/analysis-echo/` — Analysis pipeline event echo and auditing
- `pmoves/services/evoswarm/` — Evolutionary swarm optimization coordinator

#### 🔭 4090 Field Control Room
**Purpose:** Scout/control room for review, topology, handoff, and notebook-backed triage.
**Profile:** `4090-field` · **Agent:** `4090-claude` · **Manifest:** [`4090-field.room.control.json`](pmoves/config/rooms/4090-field.room.control.json)

- `pmoves/services/agent-zero/` — MCP bridge + decision engine (ingests Supabase + CHIT events)
- `pmoves/services/archon/` — Agent builder/knowledge management with Supabase CLI realtime + NATS clients
- `pmoves/services/deepresearch/` — Tongyi DeepResearch bridge with OpenRouter/local modes plus Open Notebook mirroring
- `pmoves/services/supaserch/` — Multimodal holographic deep research orchestrator
- `pmoves/services/graph-linker/` — Knowledge graph linking and entity relationship management
- `pmoves/services/session-context-worker/` — Session context aggregation for multi-turn agent conversations
- `pmoves/services/gateway-agent/` — Unified API gateway with agent-aware routing
- `pmoves/services/botz-gateway/` — Skills marketplace gateway for BoTZ agent capabilities
- `pmoves/services/agentgym-rl-coordinator/` — Reinforcement learning coordinator for agent skill training
- `pmoves/services/consciousness-service/` — Agent self-model and meta-cognitive state tracking
- `pmoves/services/chat-relay/` — Agent-to-agent and agent-to-user chat relay
- `pmoves/services/messaging-gateway/` — Multi-channel messaging gateway
- `pmoves/services/a2ui-nats-bridge/` — Agent Zero UI to NATS event bridge
- `pmoves/services/open-notebook/` — Streamlit UI + SurrealDB API (container ports 8502/5055 per upstream; host defaults map to `:8503` UI and `:5055` API, override with `OPEN_NOTEBOOK_*_PORT`) for research assets and MCP notebooks. Doc: [`pmoves/docs/services/open-notebook/`](pmoves/docs/services/open-notebook/)
- `pmoves/services/notebook-sync/` — Bridges Open Notebook datasets into Supabase and LangExtract flows
- `pmoves/services/retrieval-eval/` — Retrieval benchmarking, relies on Supabase + hi-rag

#### 🎙️ 5090 Voice Studio
**Purpose:** Voice-first room for TTS, media pipelines, notebook-backed iteration, and audition workflows.
**Profile:** `5090-voice` · **Agent:** `5090-claude` · **Manifest:** [`5090-voice.room.studio.json`](pmoves/config/rooms/5090-voice.room.studio.json)

- `pmoves/services/flute-gateway/` — Multimodal voice communication layer (HTTP `:8055`, WebSocket `:8056`) with Pipecat integration and prosodic synthesis
- `pmoves/services/vibevoice-realtime/` — Real-time voice synthesis service
- `pmoves/services/pmoves-yt/` — YouTube ingest; publishes geometry packets after segmentation
- `pmoves/services/channel-monitor/` — External content watcher; triggers ingestion on new uploads
- `pmoves/services/publisher/` — Discord & Jellyfin publisher with geometry-aware payloads
- `pmoves/services/publisher-discord/` — Dedicated Discord notification bot for ingest/summary events
- `pmoves/services/jellyfin-bridge/` + `pmoves/docs/services/jellyfin-ai/` — Media sync bridging Jellyfin metadata into Supabase + Discord publisher
- `pmoves/services/{presign,render-webhook,extract-worker,langextract,media-audio,media-video,pdf-ingest,comfy-watcher,comfyui}` — Supporting ingestion, extraction, and media tooling

#### 💻 5090 KiloCode GLM Workstation
**Purpose:** GPU inference specialist node running KiloCode GLM on the GLM Coding Plan. Shares the 5090 with Claude Code and Codex.
**Profile:** `5090-kilocode` · **Agent:** `5090-kilocode` · **Manifest:** [`5090-kilocode.room.studio.json`](pmoves/config/rooms/5090-kilocode.room.studio.json)

- `pmoves/services/tensorzero-config-api/` — Dynamic TensorZero model configuration API (shared with Infra room)
- `pmoves/services/gpu-orchestrator/` — GPU resource allocation and scheduling (shared with Infra room)
- `pmoves/services/model-registry/` — Central model catalog with version tracking (shared with Infra room)
- `pmoves/services/retrieval-eval/` — Retrieval benchmarking (shared with Field Control room)

### Cross-Cutting: Geometry & CHIT Fabric

These services form the knowledge and geometry substrate available to **all rooms** via the NATS event bus:

- `pmoves/services/hi-rag-gateway-v2/` — v2 gateway (CPU `:8086`, GPU `:8087`). Handles `/geometry/*`, jump, decode, calibration, Supabase realtime warmups, and CGP persistence.
- `pmoves/services/hi-rag-gateway/` — v1 legacy gateway (host `:8089`). Minimal CHIT endpoints for backward compatibility.
- `pmoves/services/gateway/` — Experimental CHIT UI/API for live geometry visualisation and WebRTC broadcast.
- `pmoves/services/mesh-agent/` — Geometry mesh bridge; signs and republishes `geometry.cgp.v1` across deployments.
- `pmoves/services/evo-controller/` — Geometry tuning controller; reads CGPs from Supabase, emits tuning capsules back into the bus.
- `pmoves/services/tokenism-simulator/` — Token geometry simulation and visualization.

### Cross-Cutting: Orchestration & External Data

- `pmoves/services/n8n/` — Workflow orchestrator; health/finance webhooks emit CGPs via hi-rag v2.
- `pmoves/services/wger/` — Health metrics ingest (paired with Supabase tables + `health.weekly.summary.v1` CGPs).
- `pmoves/services/firefly-iii/` — Personal finance ingest; finance flows create `finance.monthly.summary.v1` CGPs.

See each directory's README for ports, Make targets, and geometry notes. New integrations reference external repositories under `integrations-workspace/` and the setup steps captured in `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`.

## Dashboards & UIs (local defaults)

### By Room

**Z890 Infra Fabric Room:**
- TensorZero UI: http://localhost:4000 (after `make up-tensorzero`).
- TensorZero Gateway: http://localhost:3030 (proxy to 3000 in-container).

**4090 Field Control Room:**
- Supabase Studio: http://127.0.0.1:65433 (CLI stack) — created by `make supa-start`.
- Agent Zero UI: http://localhost:8080 (after `make up-agents`).
- Archon Health: http://localhost:8091/healthz (after `make up-agents`).
  - If your forks use non-standard health endpoints, set `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` / `NEXT_PUBLIC_ARCHON_HEALTH_PATH`. See `pmoves/docs/SERVICE_HEALTH_ENDPOINTS.md`.
- Open Notebook: http://localhost:8503 (after `make -C pmoves notebook-up`).
- n8n: http://localhost:5678 (after `make -C pmoves up-n8n`).

**5090 Voice Studio:**
- Jellyfin: http://localhost:8096 (after `make -C pmoves up-jellyfin-ai`).
- Jellyfin API Dashboard: http://localhost:8400; Gateway: http://localhost:8300.
- Invidious: http://127.0.0.1:3000 (companion at http://127.0.0.1:8282).

**5090 KiloCode GLM Workstation:**
- Hi-RAG v2 Geometry Console (GPU): http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/geometry/ (after `make up`).

### Default access and operator credentials

- Supabase operator is provisioned by `make supabase-boot-user` (also run by `make first-run`). The command writes values to `pmoves/env.shared` and `pmoves/.env.local`:
  - `SUPABASE_BOOT_USER_EMAIL`, `SUPABASE_BOOT_USER_PASSWORD`, `SUPABASE_BOOT_USER_JWT`.
  - The PMOVES UI auto-authenticates with `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` so most routes won't prompt for a password. If you need to log in manually, use the email/password above from your env files.
- Jellyfin uses the LinuxServer image defaults. After first boot, confirm the admin user and API key in `pmoves/env.jellyfin-ai` or via the Jellyfin UI (Settings → Dashboard). Update `JELLYFIN_API_KEY` and `JELLYFIN_USER_ID` in `pmoves/env.shared` if you rotate.
- Wger and Firefly are brought up with PMOVES-branded defaults sourced from `pmoves/env.shared` (see `pmoves/docs/FIRST_RUN.md` "Seeded & Branded Defaults" for the exact initial usernames and emails).
- Open Notebook's UI password also serves as its API bearer token; keep `OPEN_NOTEBOOK_API_TOKEN` identical to `OPEN_NOTEBOOK_PASSWORD` so CLI helpers and agents work against the same branded login (see `pmoves/docs/services/open-notebook/README.md`).
- For a full list of seeded branded logins and where they come from, see:
  - `pmoves/docs/FIRST_RUN.md` (Seeded & Branded Defaults)
  - `docs/SECRETS.md` (Secret Management Playbook)

- **Creator bundle:** see [`pmoves/creator/`](pmoves/creator/README.md) for installers, tutorials, and ComfyUI workflows supporting WAN Animate, Qwen Image Edit+, and VibeVoice TTS. Key guides include:
  - [WAN Animate 2.2 Tutorial](pmoves/creator/tutorials/wan_animate_2.2_tutorial.md)
  - [Qwen Image Edit+ Tutorial](pmoves/creator/tutorials/qwen_image_edit_plus_tutorial.md)
  - [VibeVoice TTS Tutorial](pmoves/creator/tutorials/vibevoice_tts_tutorial.md)
  - [WAN Animate Installation Scripts](pmoves/creator/tutorials/waninstall%20guide.md)
- [Creator Pipeline Runbook](pmoves/docs/PMOVES.AI%20PLANS/CREATOR_PIPELINE.md) – Current status of n8n automations (health/finance live, creative flows staging) plus geometry mapping and persona playback prep.

## Developer Tools & Testing

### Claude Code CLI Integration (TAC)

PMOVES.AI integrates deeply with **Claude Code CLI** through the `.claude/` directory, providing context-aware development assistance:

**Key Features:**
- **Always-on context** (`.claude/CLAUDE.md`) - Makes Claude aware of PMOVES architecture, services, and patterns
- **Custom slash commands** - Quick access to production services:
  - `/health:check-all` - Verify all services are running
  - `/search:hirag "query"` - Query Hi-RAG v2 knowledge base
  - `/agents:status` - Check Agent Zero orchestration status
  - `/deploy:smoke-test` - Run integration test suite
- **Security hooks** - Pre-tool validation blocks dangerous operations (rm -rf /, DROP DATABASE, etc.)
- **Observability hooks** - Post-tool events published to NATS (`claude.code.tool.executed.v1`)

**Quick Start:**
```bash
# Use Claude Code CLI with PMOVES context
claude

# Try a custom command
/health:check-all

# Query knowledge base
/search:hirag "How does Agent Zero work?"
```

**Learn more:** [.claude/README.md](.claude/README.md) | [Developer Context](.claude/CLAUDE.md)

### Testing Infrastructure

PMOVES.AI employs comprehensive testing from smoke tests to end-to-end workflows:

**1. Smoke Tests** (30-60 seconds) - Quick health validation:
```bash
cd pmoves
make verify-all          # Full smoke test suite
make smoke               # Core services only
make smoke-gpu           # GPU-enabled services
make archon-smoke        # Archon agent services
make deepresearch-smoke  # Research orchestration
```

**2. Functional Tests** (2-5 minutes) - Feature validation:
```bash
# Run all functional tests
cd pmoves/tests
./run-functional-tests.sh

# Individual test categories
./run-functional-tests.sh --category retrieval
./run-functional-tests.sh --category agents
./run-functional-tests.sh --category ingestion
```

**3. Integration Tests** - End-to-end workflows:
```bash
# NATS event flow validation
make test-nats-flow

# Media pipeline validation
make test-media-pipeline

# Agent coordination validation
make test-agent-mesh
```

**Coverage Map:**
- Service health endpoints (Qdrant, Neo4j, Meilisearch, Supabase)
- Retrieval accuracy (Hi-RAG v2 reranking, embedding generation)
- Agent coordination (Agent Zero MCP, Archon prompts, NATS routing)
- Media processing (YouTube ingestion, Whisper transcription, YOLO analysis)
- Observability (Prometheus metrics, Grafana dashboards, Loki logs)

**Learn more:** [docs/testing/TESTING.md](docs/testing/TESTING.md)

### Development Workflow

**Typical developer flow:**
1. **Environment setup** - `make first-run` or `make bootstrap`
2. **Service verification** - `make verify-all` (smoke tests)
3. **Development** - Use Claude Code CLI with custom commands
4. **Testing** - `./run-functional-tests.sh` before commits
5. **Monitoring** - Grafana dashboard at http://localhost:3000

**Best practices:**
- Use `/health:check-all` before starting work to verify service status
- Leverage existing services (Hi-RAG, SupaSerch, Agent Zero) - don't duplicate
- Publish events to NATS for async coordination
- Follow observability patterns (expose `/healthz` and `/metrics`)
- Run smoke tests after infrastructure changes
- Use security hooks to prevent dangerous operations

## Build Status & Security

**Security posture:** 29 open CodeQL alerts (2 critical, 22 high, 5 medium) — triaged into 7 remediation groups. PRs #651/#653/#654 resolved 36 alerts, but the Hardened branch scope re-surfaced 29 on a broader CodeQL scan. The 2 critical alerts are SSRF findings in Hi-RAG gateway services requiring URL allowlisting.

> **Pre-production blockers (6 remaining):** AB-1 (A2UI nested gitlink), AB-3 (GHCR triggers), AB-4 (real credentials), AB-5/AB-6 (runtime validation, deferred until AB-4), AB-7 (PBKDF2 iteration bump). See the [Production Audit Dashboard](pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md) for full details and resolution sequence.

**CI gates (all enforced on PRs to main):**
- **CodeQL Advanced** — Static analysis for JS/Python/Go vulnerabilities
- **CHIT Contract Check** — Schema validation for geometry packet contracts
- **SQL Policy Lint** — Migration and policy validation
- **Docker Hardening Validation** — Container security baseline enforcement
- **Integration Contract** — Cross-service API contract verification
- **Python Tests** — Unit and integration test suite

**Key security PRs:**
- [#651](https://github.com/POWERFULMOVES/PMOVES.AI/pull/651) – Initial CodeQL alert triage (36 → 12)
- [#653](https://github.com/POWERFULMOVES/PMOVES.AI/pull/653) – Remaining CodeQL fixes (12 → 6)
- [#654](https://github.com/POWERFULMOVES/PMOVES.AI/pull/654) – Final 6 alerts resolved across gateway and YT services
- *Note: 29 alerts re-surfaced on the Hardened branch due to expanded CodeQL scan scope*

**Docker build reliability:** All core services build successfully. See [Build Fixes Documentation](docs/build-fixes-2025-12-07.md) for historical context on DeepResearch, FFmpeg-Whisper, and environment file fixes.

**Production readiness:** See the [Production Audit Dashboard](pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md) for the consolidated audit covering active blockers, CodeQL triage, static audit layers, and resolution sequence. Historical context: [Feb 2026 Readiness Report](pmoves/docs/PRODUCTION_READINESS_REPORT_2026-02-07.md).

## Getting Started

1. **Bootstrap the stack** – For brand-new machines run `make first-run`. For incremental setup follow the environment and container launch instructions in the [pmoves/README.md](pmoves/README.md): place overrides in `pmoves/.env.local`, run `make bootstrap` to capture credentials, `make up` to start the core services, and `make bootstrap-data` to apply Supabase SQL, seed Neo4j, and load the demo Qdrant/Meili corpus before smoke testing.
2. **Review orchestration flows** – Use the [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) for day-to-day compose control, and consult the architecture and multi-agent guides in `/docs` for how Agent Zero, Archon, and supporting services communicate across the mesh.

### Initial Setup & Tooling Flow (manual path)

1. **Environment bootstrap** – Walk through [pmoves/README.md](pmoves/README.md) to provision runtime prerequisites, seed `pmoves/env.shared`, and populate secrets. Use `make bootstrap` (wrapping `python -m pmoves.scripts.bootstrap_env`) when you need finer control, or invoke `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` to script the same flow alongside the provisioning bundle. Both paths update `env.shared`, `.env.generated`, `.env.local`, and the auxiliary `env.*.additions` files consumed by Compose and the UI launcher.
2. **Supabase realtime alignment** – Follow the [Supabase Service Guide](pmoves/docs/services/supabase/README.md) to start the CLI stack with `supabase start --network-id pmoves-net` (run this before accepting Supabase prompts in `make bootstrap`) and mirror the websocket endpoint (`SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`). This matches our self-hosted Supabase deployments.
3. **UI workspace bring-up** – `cd pmoves/ui` then `npm install` (or `yarn install`). The Next.js app loads Supabase creds from `pmoves/.env.local` and expects the Supabase CLI stack (`make supa-start` + `make supa-status`) before running `npm run dev`.
4. **Tooling cheatsheet** – Keep [Local Tooling Reference](pmoves/docs/LOCAL_TOOLING_REFERENCE.md) handy for Make targets, smoke tests, and environment scripts (`env_setup`, `flight-check`, `smoke`).
5. **Provisioning & hardware targets** – Browse `CATACLYSM_STUDIOS_INC/` for automated OS images, Jetson bootstrap bundles, and pmoves-net Docker stacks ready for edge hardware.
