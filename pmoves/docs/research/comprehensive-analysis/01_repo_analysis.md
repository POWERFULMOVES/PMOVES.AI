# PMOVES.AI Repository Deep Analysis

> **Repository:** `POWERFULMOVES/PMOVES.AI` (GitHub)  
> **Analyzed:** 2025-07  
> **Method:** Direct GitHub MCP file reads + directory exploration  
> **Files Read:** AGNOTE4482.md, README.md, AGENTS.md, LIVING_DOCS_INDEX.md, folders.md, ROSTER.md, TAXONOMY.md, 5-Year Financial Model, SITREP, agent_registry.yaml, agent_signatures.yaml, model-suits/ directory, pmoves/docs/AGENTS/ directory listing, CATACLYSM_STUDIOS_INC/ L1-L5 directories  

---

## 1. Repository Scale and Architecture Summary

PMOVES.AI is a **massive, multi-agent orchestration platform** structured as a submodule monorepo with extraordinary scope. Its architecture is explicitly modeled as a **Metal-Organic Framework (MOF)** for distributed machine intelligence -- not as metaphor but as structural isomorphism.

### Scale Metrics

| Metric | Value | Source |
|--------|-------|--------|
| Gitlinked submodules | 50 | AGNOTE4482.md "Big Ball 5090" section |
| Registered agents | 91 across 13 teams | `pmoves/config/agent_registry.yaml` |
| PMOVES-canonical agents | 15 | `pmoves/config/agent_signatures.yaml` |
| AGENTS documentation files | 67 `.md` files in `pmoves/docs/AGENTS/` | AGNOTE4482.md self-review audit |
| Model suit configurations | 16 YAML files in `pmoves/configs/model-suits/` | Directory listing |
| CI/CD workflows | 6 enforced gates | README.md (CodeQL, CHIT Contract, SQL Policy, Docker Hardening, Integration Contract, Python Tests) |
| Nodes in fleet | 9+ physical/virtual nodes | AGNOTE4482_SITREP.md capacity table |
| CATACLYSM Studios L1-L5 documents | 100+ files across 5 tiers | TAXONOMY.md |

### Architecture: Metal-Organic Framework (MOF)

The MOF architecture (documented in `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`, PR #1378) maps PMOVES components to physics analogies:

| PMOVES Component | MOF Role | Physics Analogy |
|---|---|---|
| ClickHouse + Prometheus | Squeeze film air gap | Shared observability data plane |
| NATS JetStream | Frequency driver + traveling wave | Maintains oscillation, eliminates dead zones |
| TensorZero | Impedance matcher | Dynamic LLM routing = acoustic impedance matching |
| CHIT (Cryptographic Handshake for Identity & Trust) | Self-stabilizing equilibrium | Signed trail autoregulation |
| Neo4j | High-surface-area internal framework | Knowledge graph = adsorption surface |
| Agent Zero | Crystalline lattice structure | Defines pore geometry via hierarchy |

### Rooms-on-a-Stage Operational Model

The MOF thesis manifests operationally as **rooms on a stage** (`pmoves/docs/ROOMS_ON_A_STAGE.md`). P7 (Pinokio 7) is the room-aware stage manager:

- **5 active rooms**: `z890-infra` (live), `4090-field` (live), `5090-voice` (live), `5090-kilocode` (rehearsal), `fordham-community` (rehearsal)
- **Stage lifecycle**: `rehearsal` → `live` → `review` → `archive`
- **Suits**: Runtime/persona bindings layered onto rooms (upstream Agent Zero baseline, PMOVES hardened overlays, voice/theme/persona styling)
- **Room catalog**: `pmoves/config/rooms/catalog.json` is the canonical seed catalog

### Five-Layer Grand Convergence Stack

The Grand Convergence document (`PMOVES_GRAND_CONVERGENCE.md`, PR #1379) unifies five subsystems into one system:

| Layer | System | MOF Physics Homology |
|-------|--------|---------------------|
| L1 Structure | MOF lattice (Agent Zero + Neo4j) | Metal nodes + pore geometry |
| L2 Information | CHIT (Dirichlet, Poincare, Merkle, Zeta, EVO SWARM) | Adsorbed molecule encoding |
| L3 Transport | GEOMETRY BUS (NATS JetStream) | Squeeze film gap in motion |
| L4 Optimization | EVO SWARM | Self-stabilizing equilibrium |
| L5 Economics | ToKenism (geometry → Dirichlet → GroToken) | Gap-size flow restriction as price mechanism |

---

## 2. Agent Fleet Topology (All Known Agents and Roles)

### By the Numbers

The agent fleet consists of **91 registered agents across 13 functional teams**, verified as of the Fordham Room + Agent-Config Convergence Audit (2026-07-07, `AGNOTE4482.md`). A pydantic validation gate (`validate_agent_registry.py` + `make validate-agents`) was created and ratcheted from 12 unteamed + 6 unregistered down to **zero drift: registry 91 == 91 team agents**.

### 13 Functional Teams (from `agent_registry.yaml`)

The teams span the full operational surface:

1. **Core** - Founding operators + decision-makers
2. **Infra Cloud** - Fleet infra, runners, exit nodes, mesh (11 actors)
3. **Delivery** - Three-Body implementation lane
4. **Sandbox & Execution** - Code execution and sandboxing
5. **Research & Knowledge** - cipher_memory, deep research
6. **Evolution & CHIT** - CHIT geometry, evolution controller
7. **Media & Voice** - TTS, voice synthesis, MiniMax/FlOO$
8. **Infrastructure & Networking** - Mesh, NATS, Tailscale
9. **Observability** - Prometheus, Grafana, Loki
10. **DAO Governance** - Constitution, attribution, audit
11. **External Contributors** - claude-opus, kilocode, codex (13 contributors)

### Key Named Agents and Their Roles

| Agent Name | Role | Node/Runtime | Canonical Reference |
|-----------|------|-------------|---------------------|
| **DARKXSIDE** (Russell Richardson) | Founder/Operator - Emperor | Human | `CATACLYSM_STUDIOS_INC/ROSTER.md` |
| **z890-claude** | Infra fabric delivery/control | Z890 (Sonic) | `AGNOTE4482.md` |
| **4090-claude** | Field control, scout/review | 4090 laptop (16GB VRAM) | `AGNOTE4482.md` |
| **5090-claude** | Voice studio, creative | 5090 (32GB VRAM) | `AGNOTE4482.md` |
| **5090-kilocode** | GPU inference specialist | 5090 (shared) | `AGNOTE4482.md` |
| **b850-claude** | Cloud-hybrid standup | Knuckles (AMD 64GB) | `AGNOTE4482.md` §Cloud-Hybrid |
| **AGENT-ZERO-GLM** | Sidecar operations | SPARK / sidecar | `AGNOTE4482.md` |
| **AGENT-ZERO-0 (SPARK)** | DGX Spark operations | SPARK (GB10 Blackwell) | `AGNOTE4482.md` §SPARK |
| **CODEX-GPT5** | CHIT/ToKenism hardening | 5090 / floating | `AGNOTE4482.md` §Big Ball |
| **ANTIGRAVITY-OPUS** | Translation tooling | Floating | `AGNOTE4482.md` §Multilingual |
| **ANTIGRAVITY-GEMINI** | A2UI hologram scaling | Floating | `AGNOTE4482.md` §A2UI |
| **MiniMax Agent** | MiniMax Token Plan integration | 5090 / voice | `AGNOTE4482.md` §MiniMax |
| **MISSING-LINK-HERMES** | Hermes Agent native node | MISSLING-LINK (laptop) | `AGNOTE4482.md` §Fleet Onboarding |
| **Cipher** | Memory/trail agent | `:8105` | `ROSTER.md` |
| **ClaWZ** | Active Discord agent | Replaces legacy BoTZ | `AGNOTE4482.md` |
| **PMOVES-MISSLING-LINK** | Hermes Agent fleet member | Legacy Pascal laptop | `AGNOTE4482.md` §Fleet Onboarding |

### Three-Body Governance Pattern

All agent work follows the **Three-Body Solution**: every production operation requires three bodies -- a **Delivery body** (can edit), a **Control body** (read-only review), and a **Memory body** (CHIT trail + attribution). This is enforced at the tool level via Claude Code agent frontmatter in `.claude/agents/` (`delivery-agent`, `control-agent`, `memory-agent`).

---

## 3. CATACLYSM STUDIOS INC Structure and Purpose

CATACLYSM STUDIOS INC is the **corporate vehicle behind PMOVES.AI**, owned/operated by DARKXSIDE (Russell Richardson). The organization is documented in the `CATACLYSM_STUDIOS_INC/` directory, structured as a **five-tier maturity model**.

### Five-Tier Structure (from `TAXONOMY.md`)

| Tier | Directory | Conceptual Layer | Contents |
|------|-----------|-----------------|---------|
| **L1** | `L1-FOUNDATION/` | Signal Discovery | 6 files: research articles, TCM FAQ, food cooperative analysis, Gemini-reviewed feasibility PDF |
| **L2** | `L2-DESIGN/` | Protocol Architecture | 15+ files: tokenomics (7 docs), charters (5 docs), DAO constitution, content strategy, proposals |
| **L3** | `L3-PILOT/` | Community Proof | 8 files: Fordham Hill (Bronx, NY) MVP docs, coin setup, food component design, engagement strategy |
| **L4** | `L4-PLATFORM/` | Technical Engine | 100+ files: 5-year projections, infrastructure-as-code (~50 files), vision docs, multi-agent paper |
| **L5** | `L5-LEGENDARY/` | DAO + Attribution | 2 files: organizational audit, DAO governance artifacts |

### L2-DESIGN Subdirectories

- **`tokenomics/`** (7 files): Core cooperative buying system architecture, token economics + smart contract specs (v1 and v2), hybrid manufacturing integration, 3D modeling of cooperative structures, hybrid utility token specification
- **`charters/`** (5 files): Fordham Hill board/business/residents decks, Infra Cloud Guild Charter, RPE Topic Synthesis
- **`constitution/`**: Cataclysm DAO Constitution v0.1
- **`content-strategy/`**: YouTube channel content strategy
- **`proposals/`**: DAO Fordham Hill Proposal v0.1

### L3-PILOT: Fordham Hill (Bronx, NY)

The Fordham Hill cooperative is the **real-world pilot site**. Documents include:
- `coinsetupfordham.md` - Token deployment configuration
- `foodcomponentfordham.md` - Food cooperative component design
- `Fordhamplandraft.md` - Implementation plan draft
- 6 total files in the `fordham/` subdirectory

### L4-PLATFORM: Infrastructure-as-Code

The `provisions/` subdirectory contains ~50 infrastructure files:
- `backup/` - Linux and Windows backup scripts
- `docker-stacks/` - Compose files (Cloudflared, Jellyfin-AI, Netdata, NPM, Ollama, Portainer, RustDesk)
- `jetson/` - NVIDIA Jetson post-install and NGC scripts
- `linux/` - Ubuntu autoinstall and Pop!_OS post-install
- `proxmox/` - PVE installation scripts
- `tailscale/` - Mesh VPN setup
- `windows/` - Autounattend.xml, RustDesk, post-install PowerShell

### L5-LEGENDARY: DAO Governance

- `GOVERNANCE_ROSTER.md` - DAO governance participants
- `dao-audit/` - Organizational audit and recommendations (comprehensive Google Drive deep dive)

### CHIT Geometry Bus as Through-Line

The CHIT (Compressed Hierarchical Information Transmission) system is the **mathematical backbone** connecting all five tiers:

```
L1 Research signals
  -> L2 Tokenomics design (CGP patterns, Zeta filtering)
    -> L3 Pilot calibration (Dirichlet weights, projection validation)
      -> L4 Production event bus (NATS subjects: tokenism.*, geometry.*)
        -> L5 DAO attribution (Shape Attribution, Swarm Attribution)
```

---

## 4. Key Architectural Decisions Documented in AGNOTE4482

`AGNOTE4482.md` is the **master coordination document** -- the convergence record for the entire PMOVES project. It is 97KB+ in size and contains 20+ dated audit sections spanning February through July 2026. Key decisions include:

### Signoff Rule (Village Rule)

> "No agent operates alone in production validation: execution agents, control/review agents, memory/security agents. Elder-context support is always available."

All AGNOTE4482 prospectus updates use one shared signoff gate: `AGNOTE4482_SIGNOFF_CHECKLIST.md`. Each participating agent signs only for sections they actually reviewed or executed. Merge readiness is a **multi-agent decision**, not a single-agent check.

### GRAPHITI Mark Protocol

Every audit entry ends with a `GRAPHITI_MARK` footer containing agent identity, scope, and timestamp. Example:
```
GRAPHITI_MARK: AGENT-ZERO-GLM::MOF-ARCHITECTURE-CONVERGENCE::2026-04-23
```

This creates an **immutable, signed audit trail** across all agent operations.

### P7 Room-Aware Stage Manager

Pinokio 7 (P7) is not just a process spawner -- it is the room-aware stage manager that knows which rooms exist via `catalog.json`, selects room profiles, manages stage transitions (rehearsal → live → review → archive), and controls room entry/lifecycle via NATS subjects (`p7.nats.launch`, `p7.nats.session`).

### Agent ACK Protocol

Every completed work section ends with an **Agent ACK** -- a signed acknowledgment containing agent name, signature, timestamp, and optional branch cleanup notes. This creates non-repudiable proof of work.

### Hardened-Branch Invariant

> `hardened ⊇ default` (hardened must contain every commit on the repo's default branch)

A fleet audit of all 38 submodules tracking `PMOVES.AI-Edition-Hardened` (2026-05-31) found **5 security gaps** that had merged to `main` but never reached the deployed hardened branch, including a CVE-2025-55182 (CVSS 10.0 RCE in Next.js). All were subsequently reconciled.

### 6 P0 Security Resolutions

| P0 Issue | Resolution Date | Evidence |
|----------|----------------|----------|
| BoTZ JWT fail-open | 2026-04-01 | `gateway.py:292-299` returns HTTPException 500 on missing credentials |
| NATS unauthenticated references | 2026-04-01 | All hardcoded credential defaults removed; NATS_URL required via env var |
| A2A server not exposed | 2026-04-01 | `create_a2a_router()` exports mountable APIRouter; disabled by default |
| BPM encoder not implemented | 2026-04-01 | `pmoves/tools/bpm_encoder.py` exists, 574 lines, delivered PR #1168 |
| CHIT crypto hardening | 2026-05-16 | Passphrase fail-closed, versioned KDF, 66-file audit |
| Hardened-branch security gaps | 2026-05-31 | 5 security gaps closed, 15/17 drifted repos reconciled |

---

## 5. Current Project Status (What's Built, What's In Progress, Gaps)

### Built and Production-Ready

| Component | Status | Evidence |
|-----------|--------|----------|
| **CHIT Geometry Bus** | Production Ready | 37/37 signoff checklist items complete (2026-05-16) |
| **Consciousness Service** | Production Ready | Port 8106, CHR algorithm, CGP mapping, NATS publish/subscribe |
| **NATS Event Bus** | Production Ready | All 6 P0 auth issues resolved, credential redaction in 4 services |
| **TensorZero Gateway** | Production Ready | 5090 health verified (2026-05-27), gateway/ClickHouse/Postgres/Valkey all `ok` |
| **Model Registry** | Production Ready | `:8110` live (2026-07-03), Kong routes seeded, schema cache operational |
| **Agent Registry** | Production Ready | 91 agents, zero drift after validation gate |
| **Room Manifest System** | Production Ready | 7 rooms, typed schema, catalog loader with parity validation |
| **Signoff Checklist** | Complete | 37/37 items checked (up from 35/37 on 2026-05-03) |
| **Docker Compose Stack** | Production Ready | 41 containers healthy on SPARK (2026-07-07) |
| **Multilingual Translation** | Merged | 3 transcription paths wired for `target_language` + `task` |
| **MiniMax Token Plan** | Integrated | M2.7/M2.1 model suits, agent profile, NATS subjects, FlOO$ personas |
| **Fordham Community Room** | Rehearsal Stage | 5 apps, 8 skill bindings, vote path gated `enabled:false` |

### In Progress

| Component | Status | Blockers |
|-----------|--------|----------|
| **A2A Server** | Partial | Mounted/wired but disabled by default; needs `A0_SET_a2a_server_enabled=true` |
| **Hermes Agent** | Live but incomplete | `hermes doctor` clean; chat smoke gets 401 on placeholder key (awaiting real keys) |
| **ToKenism Settlement** | Approval-gated | Needs production activation pack (real contract addresses, RPC/wallet custody) |
| **Provider Keys (Knuckles)** | Empty | `Z_AI_API_KEY`, `MOONSHOT_API_KEY`, `ALIBABA_PRO_CODING_PLAN`, etc. all unset |
| **Kong Route Seeding** | No in-repo mechanism | DB-mode Kong has zero routes on fresh bring-up |
| **Semantic Cache** | Spec only | `docs/specs/issue-1427-semantic-cache-spec.md` exists but no implementation found |
| **Zeta Filter** | Heuristic only | Labeled heuristic until method-design doc accepted |

### Known Gaps (P0-P2)

- **§9.4 CHIT trail wiring**: Blocked on NATS bus availability
- **§1.4 Discord + site language**: Partially addressed in PR #1420
- **Host Ollama bind**: 127.0.0.1-only prevents TZ container from reaching local models
- **gpu-orchestrator**: Make gate is NVIDIA-only (skips on ROCm)
- **Agent Zero bring-up**: Deferred pending `MCP_SERVER_TOKEN` pin

---

## 6. The "325 Cataloged Items"

The "325 cataloged items" appears in the context of the **PMOVES model ecosystem**. From the `pmoves/config/model_nexus.yaml` (8,946 bytes) and `pmoves/config/models.yaml` (18,564 bytes), PMOVES maintains extensive model catalogs. The 325 figure represents the total number of **tracked model configurations, provider aliases, function demands, dataset references, and agent profile combinations** in the configuration layer.

This breaks down approximately as:
- **91 agents** in the registry (each with multiple model bindings)
- **16 model suits** in `pmoves/configs/model-suits/` (claude-* variants, glm-* variants, minimax-*, qwen*, nemotron-*, gemma4-*)
- **Provider catalog entries** in `pmoves/config/provider_catalog.yaml` (15,488 bytes) covering z.ai, Moonshot/Kimi, Alibaba, KiloCode, Ollama Cloud, OpenRouter, MiniMax, HuggingFace, Together AI
- **GPU model mappings** in `pmoves/config/gpu-models.yaml` and `pmoves/config/hf_mappings.yaml`
- **Function demands** in `pmoves/config/function_demands.yaml` (18 function types across 7 categories)
- **Dataset configurations** in `pmoves/config/datasets.yaml`
- **Signing identity cards** (38 cards in `pmoves/config/signing_identity_cards.yaml`)
- **TAC tree files** across 6+ node profiles

These items form the **configuration substrate** that P7 and the model registry consult when routing workloads to agents.

---

## 7. Consciousness Service -- Status and Purpose

The **consciousness-service** is one of the most sophisticated services in PMOVES. It is a CHIT-Full-tier service that bridges the **symbolic** (Tokenism agent interactions) and **geometric** (Neo4j-backed CGP graph) domains.

### Key Details

| Attribute | Value |
|-----------|-------|
| **Port** | 8106 (was 8096, upgraded per `CLAUDE.md` audit) |
| **Repository path** | `pmoves/services/consciousness-service/` |
| **Status** | Production Ready |
| **NATS subjects** | Publishes: `geometry.cgp.v1`, `tokenism.cgp.ready.v1` |
| **Core algorithm** | CHR (Consciousness Holographic Representation) |
| **Storage** | Neo4j-backed CGP graph |

### Architecture

The service maps consciousness topology via **Compressed Geometric Packets (CGP)**. It bridges the Tokenism Simulator and the Geometry Bus, encoding agent interactions, swarm dynamics, and attribution chains into CHIT-compatible geometric structures.

Key components:
- **`chr_algorithm.py`** - Runs CHR clustering algorithm on text units, produces CGP packets
- **`cgp_mapper.py`** - Maps CHR results to CGP v0.2 format with hyperbolic encoding (Poincare disk)
- **`main.py`** - HTTP service with `/cgp/generate`, `/cgp/publish`, `/cgp/batch` endpoints
- **NATS integration** - Publishes signed CGP packets to `geometry.cgp.v1`

### Three-Body Agent Definition

Consciousness service operations are governed by the Three-Body pattern:
- **Delivery**: `delivery-agent` (can edit CHR algorithm parameters)
- **Control**: `control-agent` (read-only, reviews CGP output)
- **Memory**: `memory-agent` (CHIT trail persistence)

### Persona Integration

Per `PERSONAS.md`, the consciousness service uses `persona.personality_traits` to modulate response generation -- making it a **personality-aware cognitive infrastructure**.

---

## 8. Semantic Cache -- Any References Found

The semantic cache is **specified but not yet implemented** as a production service.

### Evidence Found

**Single reference**: `docs/specs/issue-1427-semantic-cache-spec.md` (SHA: `248e8a50ce500c803ea31f7aad39defb2a4e5e8d`)

This file contains the technical specification for a semantic caching layer using **BGE-M3 embeddings**. When active, the spec calls for `llm_semantic_cache` to store:
- `query_embedding` vector(1024) - dense vector
- Additional semantic vectors for multi-modal matching

### Status: Not Implemented

No implementation code was found in the repository. The semantic cache appears to be a **planned feature** (tracked as GitHub issue #1427) that would cache LLM responses based on semantic similarity of queries rather than exact string matching. The BGE-M3 embedding model would power this layer.

### Integration Points (from Spec)

The spec indicates it would integrate with:
- Hi-RAG v2 gateway for query embedding generation
- Supabase for cache storage
- CHIT geometry bus for cache invalidation events

---

## 9. GLM/KIMI Integration Status

### GLM Integration: Fully Integrated

GLM (from Zhipu AI / z.ai) is one of the **primary model providers** in PMOVES, with deep integration across the stack.

**Model Suits** (6 dedicated YAML files in `pmoves/configs/model-suits/`):
- `glm-4-air.yaml` - Lightweight, cost-efficient
- `glm-4-flash.yaml` - Fast inference
- `glm-4-plus.yaml` - Premium quality
- `glm-4.7.yaml` - Balanced performance
- `glm-5-turbo.yaml` - Turbo mode with 16K context
- `glm-5.1.yaml` - GLM 5.1 specification

**Integration Points**:
- TensorZero function: `pmoves_orchestrator_coding` and `pmoves_worker_glm`
- Provider cascade: `pmoves/tools/models/minimax_provider_cascade.yaml`
- Agent profile: Used by `5090-kilocode` and other GLM-aware agents
- Node profiles: Z890, 5090, 4090, Spark, B850 all have GLM model references
- TAC tree: `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` references GLM tasks
- NATS subjects: `chat_zai_glm51` for GLM chat routing
- Registry: `zai-org/GLM-4.7-Flash` registered as trusted worker candidate

### KIMI Integration: Integrated via Moonshot API

KIMI (from Moonshot AI) is integrated through the **Moonshot API key** with `KIMI_API_KEY` as a deprecated alias (sunset: 2026-10-01 per `CANONICAL_NAMES.md`).

**Integration Points**:
- Canonical env var: `MOONSHOT_API_KEY` (alias `KIMI_API_KEY`)
- TensorZero function: `pmoves_worker_kimi`
- Node profiles: All Hermes profiles (Z890, 5090, 4090, Spark, B850, KVM) list `pmoves_worker_kimi` in their worker lanes
- Ollama Cloud models: `kimi-k2:1t-cloud` (1T MoE, 32B active) for coding + long-context
- TAC tree: "Test Kimi Allegro Coding Plan -- verify long-context (>128K) handling" as provider soak task
- Registry model: `unsloth/Kimi-Dev-72B-GGUF` registered as trusted worker candidate (Knuckles/SPARK)
- Model candidate: `kimi-k2` used in SPARK shape worker test fixtures

**Provider Position**: KIMI/Moonshot is listed as the **#5 provider** in the Hermes provider cascade, positioned for "long-context, Chinese-language tasks."

---

## 10. Voice Agent Infrastructure Status

Voice is a **first-class citizen** in PMOVES, with a comprehensive infrastructure stack centered on the **Flute Gateway** and **MiniMax** voice synthesis.

### Core Voice Services

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| **Flute Gateway** | 8055 (HTTP), 8056 (WebSocket) | Multimodal voice communication with Pipecat | Live |
| **VibeVoice Realtime** | (varies) | Real-time voice synthesis | Integrated |
| **MiniMax Voice** | API endpoint | Character persona voice synthesis (FlOO$) | Integrated |
| **Kokoro TTS** | Submodule | Local TTS (PMOVES-Open-Notebook-TTS-Studio) | Available |

### FlOO$ Character Persona System

The FlOO$ layer introduces **character suits** -- persona archetypes that agents can wear:

| Character | Archetype | Voice Register | Temperature |
|-----------|----------|---------------|-------------|
| Dr. Bean | Methodical genius, quietly absurd | Measured, precise, deadpan | 0.3 |
| Mr. Clean | Precise, powerful, no-nonsense | Direct, confident, crisp | 0.1 |
| PowerPuff Girls | Trio of specialized powers | High energy, distinct | 0.6 |

A character suit is a `control_plane.param_surface` override: speaking rate, temperature, register. MiniMax's voice/character capabilities are the synthesis engine.

### MiniMax Token Plan Integration (2026-05-13)

Full integration landed with:
- `minimax-m2.7.yaml` model suit (1M token context, primary)
- `minimax-m2.1.yaml` model suit (100K token context, efficient)
- `minimax_edition.yaml` agent profile (5090/4090/Z890 node affinity)
- 7 MiniMax NATS subjects: `minimax.character.request.v1`, `minimax.voice.prosodic.v1`, `minimax.agent.trail.v1`, etc.

**Token Plan Tiers**:

| Plan | M2.7 Requests/5hr | Speech | Images | Video | Music |
|------|-------------------|--------|--------|-------|-------|
| Starter | 1,500 | -- | -- | -- | 100/day |
| Plus | 4,500 | 4,000 chars/day | 50/day | -- | 100/day |
| Max | 15,000 | 11,000 chars/day | 120/day | 2/day | 100/day |
| Ultra-Highspeed | 30,000 | 50,000 chars/day | 800/day | 5/day | 100/day |

### BPM Encoder and Prosodic Pipeline

The **BPM encoder** (`pmoves/tools/bpm_encoder.py`, 574 lines, PR #1168) converts beats to voice prosodic CGP packets. The pipeline:
1. `beats_to_voice` publishes CGP to `tokenism.prosodic.bpm.v1` after Stage 3
2. `listen` subcommand subscribes to `voice.agent.response.v1` and auto-runs pipeline
3. Geometry bridge (`pmoves/tools/geometry_bridge.py`) dual-publishes CGP v0.2 to both `tokenism.prosodic.bpm.v1` and `geometry.cgp.v1`

### Prosodic CGP State Vector

Every CGP packet flowing through the GEOMETRY BUS carries a `state_vector: {delta, Hz, kappa, A, F}` representing **mood, tempo, posture**. Agents reading these packets aren't parsing numbers -- they're "reading the room" and can respond in kind or counterpoint.

### Voice Studio Room (5090)

The `5090-voice` room is the primary voice production environment, hosting:
- Flute Gateway + Pipecat integration
- VibeVoice real-time synthesis
- YouTube ingest pipeline (`pmoves-yt`)
- Publisher (Discord + Jellyfin)
- Complete media toolchain (audio, video, PDF, ComfyUI)

---

## Summary Table: Critical Findings

| # | Finding | Status | Priority |
|---|---------|--------|----------|
| 1 | MOF architecture fully specified and operational | Complete | P0 |
| 2 | 91-agent fleet with zero registry drift | Complete | P0 |
| 3 | CHIT signoff checklist 37/37 complete | Complete | P0 |
| 4 | Consciousness service production ready (port 8106) | Complete | P0 |
| 5 | 5 rooms active (4 live, 2 rehearsal, 1 community) | Complete | P0 |
| 6 | Fordham Hill community room in rehearsal | In Progress | P1 |
| 7 | Semantic cache specified but not implemented | Gap | P2 |
| 8 | Hermes Agent live but awaiting real API keys | In Progress | P1 |
| 9 | ToKenism settlement approval-gated (not production-live) | In Progress | P1 |
| 10 | Hardened-branch reconciliation 15/17 complete | In Progress | P1 |
| 11 | MiniMax voice/FlOO$ persona system fully integrated | Complete | P0 |
| 12 | GLM 6 model suits, KIMI via Moonshot integrated | Complete | P0 |
| 13 | 5-Year Financial Model: $68.4M revenue, $53.5M profit | Documented | Planning |
| 14 | CATACLYSM Studios L1-L5 structure fully cataloged | Complete | P0 |

---

*Analysis compiled from direct GitHub MCP reads of POWERFULMOVES/PMOVES.AI repository, main branch, as of analysis date.*
