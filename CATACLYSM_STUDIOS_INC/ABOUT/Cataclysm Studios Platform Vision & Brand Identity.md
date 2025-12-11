# Cataclysm Studios Platform Vision & Brand Identity

_Status review: December 11 2025 (repo branch `feature/youtube-pipeline-config`)_

This document aligns the Cataclysm Studios brand platform with the current PMOVES.AI codebase so product, engineering, and creative teams can work from a single, verifiable blueprint.

## 1. Brand System Overview

### 1.1 Cataclysm Studios Inc.
- Operates the end-to-end platform and infrastructure bundles kept under `CATACLYSM_STUDIOS_INC/`.  
- Hosts provisioning scripts, Jetson/edge images, and Docker stacks that mirror production (`folders.md`, `README.md`, `pmoves/README.md`).
- Stewardship focus: trustworthy operations, reproducible builds, and compliance with internal security policies (`SECURITY.md`, `docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md`).

### 1.2 PMOVES.AI (Powerful Moves AI)
- Primary technical product—a 60+ microservice orchestration platform featuring Agent Zero, Archon, Hi-RAG v2, TensorZero LLM gateway, and EvoSwarm evolutionary optimization (`README.md`, `docs/PMOVES_ARC.md`, `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md`).
- Centralized LLM observability via TensorZero [Port 3030] with ClickHouse metrics storage and UI dashboard [Port 4000]; structured multimodal data exchange via CHIT Geometry Bus.
- Code, compose profiles, and runbooks live under `pmoves/`; developer context for Claude Code CLI is maintained in `.claude/CLAUDE.md` with 43+ slash commands across 12 categories.
- Brand promise: "Local-first autonomy, reproducible provisioning, and self-improving research loops."

### 1.3 DARKXSIDE
- Artistic persona and storytelling lens for Cataclysm’s community activation.  
- Creative workflows, tutorials, and media automation are located in `pmoves/creator/` with plans under `pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE.md`.
- Responsible for the emotional identity, visual direction, and narrative arcs that connect technology to grassroots movements.

### 1.4 POWERFULMOVES / Community Ecosystem
- GitHub organization home for PMOVES.AI source and integrations (`README.md`); migrations to the `CATACLYSM-STUDIOS-INC` org and GHCR namespace are in progress per roadmap stability initiative.
- Community programs (Fordham Hill cooperative pilot, creator collectives) inherit platform guidance from this document and the referenced runbooks.

## 2. Platform Pillars (verified against repository artefacts)

| Pillar | Description | Primary Evidence |
| --- | --- | --- |
| Orchestration Mesh | Agent Zero [8080] + Archon [8091] + Hi-RAG v2 [8086/8087] + TensorZero [3030] + EvoSwarm [8113] + BoTZ Gateway [8054] + Mesh Agent coordinate across Supabase, Neo4j, Qdrant, Meili. | `README.md`, `.claude/CLAUDE.md`, `.claude/context/services-catalog.md` |
| Knowledge & Data Plane | Hi-RAG v2 with cross-encoder reranking, CHIT Geometry Bus for structured multimodal exchange, Supabase CLI stack, retrieval-eval harness. | `.claude/context/chit-geometry-bus.md`, `pmoves/README.md`, `pmoves/docs/services/supabase/README.md` |
| Creative & Media Stack | ComfyUI pipelines, PMOVES.YT [8077] with 10 slash commands, Channel Monitor [8097], FFmpeg-Whisper [8078], media analyzers, Jellyfin Bridge [8093]. | `pmoves/creator/README.md`, `.claude/commands/yt/`, `pmoves/services/pmoves-yt/` |
| LLM Observability Fabric | TensorZero Gateway [3030] for unified LLM API, ClickHouse [8123] metrics storage, TensorZero UI [4000] dashboard, token usage and latency tracking. | `.claude/context/tensorzero.md`, `pmoves/tensorzero/config/tensorzero.toml` |
| Developer Experience Layer | `.claude/` directory with 43+ slash commands across 12 categories, TAC (Tactical Agentic Coding) git worktree patterns, security hooks with NATS observability. | `.claude/CLAUDE.md`, `.claude/README.md`, `.claude/context/git-worktrees.md` |
| Multi-Platform Communications | Messaging Gateway [8101] for Discord/Telegram/WhatsApp, Publisher-Discord [8094] for ingestion notifications, NATS event-driven coordination. | `.claude/context/nats-subjects.md`, `pmoves/services/messaging-gateway/` |
| Health & Finance Integrations | Branded Wger and Firefly stacks with smoke tests and env guidance. | `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`, `pmoves/docs/services/wger/README.md`, `pmoves/docs/services/firefly-iii/README.md` |
| Research & Deep Search | SupaSerch [8099] holographic deep research, DeepResearch [8098] LLM-based planner, Open Notebook sync, notebook-sync bridge. | `.claude/commands/search/`, `pmoves/docs/services/open-notebook/README.md` |
| Governance & Reliability | 5-tier network architecture (api/app/bus/data/monitoring), CI parity, reproducible make targets, Prometheus/Grafana/Loki monitoring. | `docs/LOCAL_CI_CHECKS.md`, `pmoves/docs/MAKE_TARGETS.md`, `.claude/context/services-catalog.md` |

## 3. Implementation Snapshot (as of December 11 2025)

### 3.1 Infrastructure Evolution
- **60+ Microservices** – Platform expanded from initial Agent Zero/Archon core to comprehensive orchestration ecosystem with Docker Compose profiles: `agents`, `workers`, `orchestration`, `yt`, `gpu`, `monitoring`, `tensorzero`.
- **5-Tier Network Architecture** – Defense-in-depth isolation: `api_tier` (172.30.1.0/24), `app_tier` (172.30.2.0/24), `bus_tier` (172.30.3.0/24), `data_tier` (172.30.4.0/24), `monitoring_tier` (172.30.5.0/24).
- **TensorZero Stack** – Operational LLM gateway at port 3030 with ClickHouse metrics storage [8123] and UI dashboard [4000]. Supports OpenAI, Anthropic, Venice, Ollama model routing with full observability.

### 3.2 Advanced AI Services
- **Hi-RAG v2** [8086/8087] – Hybrid RAG with cross-encoder reranking (BAAI/bge-reranker-base or Qwen3-Reranker-4B), combining Qdrant vectors + Neo4j graph + Meilisearch full-text.
- **SupaSerch** [8099] – Multimodal holographic deep research orchestrator coordinating DeepResearch, Agent Zero MCP tools, and Hi-RAG.
- **DeepResearch** [8098] – LLM-based research planner (Alibaba Tongyi DeepResearch) with auto-publishing to Open Notebook.
- **EvoSwarm Controller** [8113] – Evolutionary test-time optimization for CHIT Geometry parameters using genetic algorithms.
- **CHIT Geometry Bus** – Production-ready structured multimodal data exchange format across services.

### 3.3 Agent Coordination
- **Agent Zero** [8080/8081] – Central orchestrator with MCP API at `/mcp/*`, NATS JetStream integration for task coordination.
- **Archon** [8091/3737] – Supabase-driven agent service with prompt/form management, optional Work Orders service [8053].
- **BoTZ Gateway** [8054] – Agent orchestration gateway with heartbeat-based health tracking.
- **Mesh Agent** – Distributed node announcer publishing host capabilities every 15 seconds via NATS.

### 3.4 Media & Communications
- **PMOVES.YT** [8077] – YouTube ingestion with yt-dlp, transcript extraction, MinIO storage; 10 dedicated slash commands in `.claude/commands/yt/`.
- **Channel Monitor** [8097] – External content watcher triggering ingestion on new YouTube/RSS content.
- **Messaging Gateway** [8101] – Multi-platform notifications for Discord, Telegram, WhatsApp.
- **Publisher-Discord** [8094] – Ingestion event notifications via NATS subjects.
- **FFmpeg-Whisper** [8078] – GPU-accelerated transcription with Faster-Whisper backend.

### 3.5 Developer Experience
- **Claude Code CLI Integration** – `.claude/` directory with 43+ slash commands across 12 categories (agents, botz, crush, db, deploy, github, health, k8s, search, workitems, worktree, yt).
- **TAC Patterns** – Tactical Agentic Coding via git worktrees enabling multiple Claude instances working simultaneously.
- **Security Hooks** – `pre-tool.sh` blocks dangerous operations; `post-tool.sh` publishes tool executions to NATS `claude.code.tool.executed.v1`.
- **Context Documentation** – 7 reference files in `.claude/context/` covering services, TensorZero, EvoSwarm, CHIT, NATS, MCP, git worktrees.

### 3.6 Monitoring & Observability
- **Prometheus** [9090] – Metrics scraping from all service `/metrics` endpoints.
- **Grafana** [3000] – Dashboard visualization with pre-configured "Services Overview" dashboard.
- **Loki** [3100] – Centralized log aggregation with Promtail collector.
- **cAdvisor** – Container metrics for Prometheus integration.

### 3.7 Retained from Previous Snapshot
- **UI platform** – `pmoves/ui` on Next 16 + React 19 with Supabase auth gating and Playwright/Jest harnesses.
- **External services** – Wger and Firefly stacks with branding defaults and smoke targets.
- **Security posture** – Supabase RLS, Django Axes rate limiting, Redis cache expectations documented.

## 4. Brand & Experience Guidelines

### 4.1 Core Narrative
- **Promise:** empower communities to self-govern creative, economic, and knowledge work using accessible AI + cooperative tooling (reinforced by `README.md` and roadmap positioning).
- **Tone:** confident, community-first, rebellious optimism (anchored by DARKXSIDE persona).
- **Mantra:** “Powerful Moves for everyday creators”—use across UI hero copy, onboarding, and media kits (`pmoves/ui/app/(marketing)/` assets forthcoming).

### 4.2 Touchpoints & Implementation Hooks
- **Web UI:** adopt Supabase auth gating, enforce owner-prefixed object keys, and surface branded onboarding text pulled from this document (`pmoves/ui/app/dashboard/*`).  
- **External services:** run `make wger-brand-defaults` after bootstrap to set site name, admin identity, and default gym descriptors; keep `OPEN_NOTEBOOK_PASSWORD` and `OPEN_NOTEBOOK_API_TOKEN` in lockstep for branded deployments (`pmoves/env.shared`, `pmoves/docs/services/open-notebook/README.md`).  
- **Docs:** when updating workflows, cross-link relevant runbooks under `docs/` or `pmoves/docs/` and note rationale/decisions per repo guidance (see root `README.md` documentation expectations).  
- **Security defaults:** highlight Axes rate limiting in onboarding docs, recommend Redis cache wiring, and include Supabase RLS examples in UI documentation.

### 4.3 Visual & Messaging Anchors (to be expanded)
- Logo lockups and color references live in `CATACLYSM_STUDIOS_INC/ABOUT/notes/` (pending vector cleanup).  
- Future design system should reference Next.js app tokens once `pmoves/ui` design tokens land.

## 5. Blueprint Backlog (cross-reference with ROADMAP & NEXT_STEPS)

### 5.1 Now (December 2025 Sprint)
1. **EvoSwarm → CHIT calibration loop** – Complete integration of evolutionary optimization with CHIT Geometry parameters; validate production telemetry feedback.
2. **BoTZ Gateway work item distribution** – Finalize work item claiming and completion flow for multi-instance Claude Code CLI coordination.
3. **WhatsApp Business API integration** – Extend Messaging Gateway [8101] with WhatsApp webhook handlers and template messaging.
4. **YouTube pipeline configuration** – Complete Channel Monitor trigger rules and PMOVES.YT batch processing optimizations.

### 5.2 Next
1. **Multi-population EvoSwarm evolution** – Implement island model for diverse parameter exploration across GPU clusters.
2. **GAN Sidecar validation** – Deploy adversarial quality validation for Hi-RAG v2 retrieval results in production.
3. **Kubernetes deployment automation** – Operationalize `/k8s:deploy` slash command with Kustomize overlays for cloud deployment.
4. **Playwright scenarios expansion** – Add authenticated upload + presign E2E tests (`pmoves/ui/e2e/`) covering TensorZero API flows.

### 5.3 Later
1. **DAO / Tokenomics implementation** – Move conceptual token suite (Food-USD, GroToken, Fame/$WORK) from research into actionable specs: generate contracts, define Supabase schemas, and author enforcement docs.
2. **Design system & brand kit** – Build shared component library for `pmoves/ui`, Figma token export, and printable brand book referencing this document.
3. **Community pilot playbook** – Translate Fordham Hill prototype steps into a repeatable guide under `docs/PMOVES_COMMUNITY_PILOT.md` (new file).
4. **ShapeStore integration** – Persist EvoSwarm evolved shapes for cross-session parameter inheritance.

## 6. Governance & Token Strategy (Research Track)

- Prototype smart contracts now live under [`pmoves/contracts/solidity/`](../../pmoves/contracts/solidity), delivering the Food-USD stablecoin, GroToken governance asset, GroVault staking, CoopGovernor quadratic voting, and GroupPurchase pooling flows described in the v2.0 tokenomics brief. Automated Hardhat tests model representative staking and buying scenarios; see [`pmoves/docs/contracts/README.md`](../../pmoves/docs/contracts/README.md) for deployment and audit guidance.
- Actions required before launch:
  1. Commission external audits covering vault math, governance griefing vectors, and supplier payout flows; document findings alongside remediation commits.
  2. Align DAO constitution drafts with `pmoves/docs/` formatting and reference the new on-chain modules (supply policies, quorum thresholds, emergency pauses).
  3. Implement Supabase telemetry ingestion for CoopGovernor and GroupPurchase events so dashboards can reconcile on-chain voting with community analytics (see the Supabase integration plan in `pmoves/docs/contracts/README.md`).
- Supabase alignment: instrument Hardhat deployments (or follow-on indexers) to stream `ProposalCreated`, `VoteCast`, `ProposalExecuted`, `OrderCreated`, `OrderExecuted`, and `RefundClaimed` events into Supabase tables consumed by Agent Zero and publisher services. This keeps DAO decisions observable in the existing telemetry fabric and satisfies the governance transparency promises in Sections 2 and 5.
  - Map CoopGovernor events to `dao_proposals` and `dao_votes` with raw vs quadratic vote deltas so Supabase dashboards can highlight the $5,000 / $3,000 stake distributions validated in the Hardhat suite.
  - Land GroupPurchase events in `group_orders` / `group_order_contributions` tables to expose supplier disbursements and refund telemetry for Fordham Hill-style pilots.
- Messaging should continue labeling tokenomics as “pilot” until audits, treasury multi-sig configuration, and Supabase telemetry wiring are complete.

## 7. Reference Map

| Domain | Key Files (repo-relative) | Purpose |
| --- | --- | --- |
| Architecture & Ops | `README.md`; `.claude/CLAUDE.md`; `.claude/context/services-catalog.md`; `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` | System overview, service inventory, roadmap status |
| LLM & AI Fabric | `.claude/context/tensorzero.md`; `.claude/context/evoswarm.md`; `pmoves/tensorzero/config/tensorzero.toml` | TensorZero gateway, EvoSwarm optimization |
| Data Exchange | `.claude/context/chit-geometry-bus.md`; `.claude/context/nats-subjects.md`; `.claude/context/mcp-api.md` | CHIT format, NATS events, MCP API |
| Developer Tools | `.claude/README.md`; `.claude/hooks/README.md`; `.claude/context/git-worktrees.md` | Claude Code CLI, TAC patterns, hooks |
| Integrations | `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`; `pmoves/docs/services/{wger,firefly-iii,open-notebook}/README.md` | Runbooks and automation helpers |
| Security & CI | `SECURITY.md`; `docs/LOCAL_CI_CHECKS.md`; `pmoves/docs/MAKE_TARGETS.md`; `.claude/hooks/pre-tool.sh` | Policies, required checks, security hooks |
| Creative Stack | `pmoves/creator/README.md`; `.claude/commands/yt/`; `pmoves/services/pmoves-yt/` | DARKXSIDE media, YouTube pipeline |
| UI & Frontend | `pmoves/ui/README.md`; `pmoves/ui/app/api/uploads/*`; `pmoves/ui/e2e/`; `pmoves/ui/__tests__/` | Next.js platform kit, test suites |
| Notebook & Knowledge | `.claude/commands/search/`; `pmoves/docs/services/open-notebook/README.md`; `pmoves/scripts/hirag_search_to_notebook.py` | Research workspace, Hi-RAG queries |

## 8. Change Log

- **2025-12-11:** Major platform evolution update—expanded from 6 to 9 platform pillars reflecting 60+ microservices. Added TensorZero LLM gateway stack, CHIT Geometry Bus, EvoSwarm evolutionary optimization, Messaging Gateway, BoTZ Gateway, and comprehensive `.claude/` directory documentation. Updated all platform pillars, implementation snapshot, blueprint backlog, and reference map to reflect current architecture. Added new Section 9 documenting Claude Code CLI integration with 43+ slash commands.
- **2025-10-26:** Rebuilt document to match repository state, removed external-only references, and established blueprint backlog linked to `pmoves/docs/`.

## 9. Claude Code CLI Integration (.claude/ Directory)

The `.claude/` directory provides always-on context for Claude Code CLI when working in the PMOVES.AI repository. It enables Claude to understand and leverage existing infrastructure without duplicating services.

### 9.1 Directory Tree

```
.claude/
├── CLAUDE.md                     # Always-on context (12KB) - loaded automatically
├── README.md                     # Guide to .claude/ directory
├── settings.local.json           # 131 allowed bash command patterns
├── test-self-hosting.sh          # NATS + Hi-RAG integration test
│
├── commands/                     # 43 custom slash commands
│   ├── agents/ (2)               # Agent Zero orchestration
│   │   ├── status.md             # /agents:status - service health
│   │   └── mcp-query.md          # /agents:mcp-query - MCP API calls
│   ├── botz/ (4)                 # Bot configuration & CHIT
│   │   ├── init.md               # /botz:init - initialize bot
│   │   ├── profile.md            # /botz:profile - CHIT profiles
│   │   ├── secrets.md            # /botz:secrets - secret management
│   │   └── mcp.md                # /botz:mcp - MCP integration
│   ├── crush/ (2)                # Compression utilities
│   ├── db/ (3)                   # Database operations (backup, migrate, query)
│   ├── deploy/ (3)               # Service deployment (up, services, smoke)
│   ├── github/ (4)               # GitHub integration (actions, issues, PR, security)
│   ├── health/ (2)               # Health monitoring (check-all, metrics)
│   ├── k8s/ (3)                  # Kubernetes operations (deploy, logs, status)
│   ├── search/ (3)               # Knowledge retrieval
│   │   ├── hirag.md              # /search:hirag - Hi-RAG v2 queries
│   │   ├── supaserch.md          # /search:supaserch - holographic research
│   │   └── deepresearch.md       # /search:deepresearch - LLM planner
│   ├── workitems/ (3)            # BoTZ work tracking (claim, complete, list)
│   ├── worktree/ (4)             # Git worktree / TAC patterns
│   │   ├── create.md             # /worktree:create - new worktree
│   │   ├── switch.md             # /worktree:switch - change context
│   │   ├── list.md               # /worktree:list - show all
│   │   └── cleanup.md            # /worktree:cleanup - remove stale
│   └── yt/ (10)                  # YouTube pipeline
│       ├── ingest.md             # /yt:ingest - download + transcript
│       ├── status.md             # /yt:status - pipeline health
│       ├── channels.md           # /yt:channels - monitored channels
│       └── ... (7 more)          # Additional YT operations
│
├── context/                      # Reference documentation (7 files)
│   ├── services-catalog.md       # Complete service listing with ports
│   ├── tensorzero.md             # TensorZero LLM gateway deep dive
│   ├── evoswarm.md               # Evolutionary optimization system
│   ├── chit-geometry-bus.md      # Structured multimodal data format
│   ├── nats-subjects.md          # NATS event subject catalog
│   ├── mcp-api.md                # Agent Zero MCP API reference
│   └── git-worktrees.md          # TAC (Tactical Agentic Coding) workflows
│
└── hooks/                        # Security & observability (4 files)
    ├── pre-tool.sh               # Security validation gate
    │                             # Blocks: rm -rf /, DROP DATABASE, etc.
    ├── post-tool.sh              # NATS observability publisher
    │                             # Publishes: claude.code.tool.executed.v1
    ├── README.md                 # Hook configuration guide
    └── TEST_RESULTS.md           # Validation test results
```

### 9.2 Integration Philosophy

- **Leverage, Don't Duplicate**: Use existing services (Hi-RAG, TensorZero, NATS) via APIs
- **NATS for Coordination**: All tool executions published to `claude.code.tool.executed.v1`
- **Observability by Default**: Post-tool hooks stream events for monitoring
- **Security by Design**: Pre-tool hooks block dangerous operations (disk wipes, DROP DATABASE)

### 9.3 TAC (Tactical Agentic Coding) Patterns

Git worktrees enable multiple Claude Code CLI instances working simultaneously:

```bash
# Create isolated worktree for parallel development
/worktree:create feature/new-api

# Each worktree has:
# - Independent file state
# - Separate Docker Compose environment
# - Isolated branch context
```

**Use cases:**
- A/B testing different implementation approaches
- Parallel feature development across team
- Safe experimentation without affecting main workspace

Reference: `.claude/context/git-worktrees.md`

### 9.4 Slash Command Categories

| Category | Commands | Primary Use |
| --- | --- | --- |
| `/agents:*` | 2 | Agent Zero health and MCP queries |
| `/botz:*` | 4 | CHIT profile management, secrets |
| `/search:*` | 3 | Hi-RAG, SupaSerch, DeepResearch |
| `/yt:*` | 10 | YouTube ingestion pipeline |
| `/deploy:*` | 3 | Service deployment and smoke tests |
| `/worktree:*` | 4 | TAC parallel development |
| `/health:*` | 2 | Platform-wide health checks |
| `/k8s:*` | 3 | Kubernetes operations |

---

_Maintainers: update this file alongside roadmap or branding updates. Reference specific commits in PR descriptions to keep brand, product, and engineering aligned._
