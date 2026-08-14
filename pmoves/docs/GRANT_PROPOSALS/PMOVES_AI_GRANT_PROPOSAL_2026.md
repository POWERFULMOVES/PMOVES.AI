# PMOVES.AI — Grant Proposal 2026
**Organization:** CATACLYSM STUDIOS, INC. (operating PMOVES.AI)
**Principal:** Russell Richardson (founder, technical director)
**Location:** The Bronx, New York, NY
**Repository:** https://github.com/POWERFULMOVES/PMOVES.AI
**Date:** July 11, 2026
**Version:** v3.1 — Grounded against current repository state (commit/PR counts refreshed; rooms-on-a-stage, the multi-engine voice fleet, and the publishing control plane added)

> **Reviewer note.** This proposal narrates technology that is **publicly developed in the open repository above**. Every architectural claim links to a tracked file on `main`. Repository metrics in §7 are live `git`/`gh` counts as of the date above. Dollar figures in §5 are placeholders (`$X`) intended for budget development with the grantor; they have not been escrowed or independently audited. See §10 *Open questions for reviewers* before negotiating numbers.

---

## Executive Summary

**PMOVES.AI is an open-source, sovereign-by-default multi-agent AI infrastructure that runs on commodity hardware — from Hostinger VPS to NVIDIA Jetson edge devices — and is glued together by a private mesh network and a geometry-based message protocol.** Built by CATACLYSM STUDIOS, INC., a Bronx-based independent technology studio, the platform turns a heterogeneous fleet of consumer-grade machines into a single porous lattice through which autonomous agents flow, share execution patterns, and self-stabilize without central control.

We are seeking grant support to (1) harden the open-source platform for community deployment, (2) extend the edge-AI footprint to additional resilient-connectivity contexts (Jetson + Raspberry Pi-class hardware over Tailscale/Headscale mesh and MANET-style overlays), and (3) field a community pilot at Fordham Hill Oval in the Bronx that demonstrates the public-benefit story: local AI inference, local data ownership, local economic participation.

**Why this is grant-eligible work.** The platform is publicly licensed, openly developed, and explicitly designed to deliver capabilities — private LLM inference, hybrid retrieval, resilient mesh connectivity, voice/multimodal coaching — that are otherwise locked behind enterprise SaaS or proprietary edge stacks. The code, the architecture thesis, and the operational runbooks are already on `main`. Funding accelerates *deployment, hardening, and community uptake*, not invention.

---

## 1. Project Overview

### 1.1 Mission

PMOVES.AI exists to put production-grade AI infrastructure into the hands of community organizations, independent technologists, and edge-deployment contexts that the dominant cloud stack does not serve well. We do this by:

- Treating **every node as a pore in a single distributed lattice** — capacity-class, not expertise-lane — so a Jetson edge device, a Hostinger KVM, and a high-VRAM workstation participate in the same coordination plane.
- Encoding agent-to-agent communication as **geometry** instead of token streams (the CHIT protocol), so meaning compresses and transmits efficiently across constrained links.
- Defaulting to **open weights, open protocols, and open source** — every architectural claim in this proposal links to a file in the public repository.

### 1.2 Architecture (current state)

PMOVES.AI is a **Metal-Organic Framework (MOF) for distributed machine intelligence** (canonical reference: [`pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md), PR #1378). Five layers, one structure ([`PMOVES_GRAND_CONVERGENCE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md), PR #1379):

| Layer | Name | What it is in code |
|---|---|---|
| L1 | **MOF Lattice** | Agent Zero hierarchy + Archon coordination define pore geometry across the fleet |
| L2 | **CHIT** | Cymatic Holographic Information Theory — geometry-encoded packets (CGPs) replace token streams between agents |
| L3 | **GEOMETRY BUS** | NATS JetStream transport for CGPs across nodes; subjects catalogued in [`.claude/context/geometry-nats-subjects.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/context/geometry-nats-subjects.md) |
| L4 | **EVO SWARM** | Evolutionary policy optimization across the agent population ([`EVOSWARM_OPERATIONS_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/EVOSWARM_OPERATIONS_GUIDE.md)) |
| L5 | **ToKenism** | Economic and attribution layer (compute credits, contributor weights, community currency) |

Built on top of these five layers are the user-facing products: the multi-agent runtime, the hybrid retrieval gateway, the multimodal voice layer, the media-ingestion pipeline, and the Pinokio-packaged consumer installers.

---

## 2. Technical Progress (verifiable against `main`)

The following capabilities are merged and live in the repository. Each subsection links to its canonical document so reviewers can verify directly.

### 2.1 Multi-agent runtime — Agent Zero, Archon, Meta-Agent

**Agent Zero** (port 8080) is the orchestration control plane: hierarchical agent system, MCP API at `/mcp/*`, NATS subscriber for cross-node delegation. **Archon** (ports 8091 / 3737) is the Supabase-driven agent service — prompt management, form/skill registry, and the bridge to the Agent Zero MCP. The **Meta-Agent** dispatches tasks, monitors agent health, and performs autonomous self-repair across the lattice — Phase 1 complete and validated ([`META_AGENT_PHASE_1_VALIDATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/META_AGENT_PHASE_1_VALIDATION.md)).

**EvoSwarm** ([`EVOSWARM_OPERATIONS_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/EVOSWARM_OPERATIONS_GUIDE.md)) provides evolutionary RL over agent configurations; **AgentGym RL** ([`AGENTGYM_RL_OPERATIONS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/AGENTGYM_RL_OPERATIONS.md)) is the sandboxed training environment.

### 2.2 Model routing — TensorZero as impedance matcher

All LLM traffic is centralised through **TensorZero** (port 3030, ClickHouse-backed observability at 8123, UI at 4000). TensorZero is treated architecturally as the platform's "melon" — a dynamic impedance matcher between task requirements and model capabilities, routing each call to the most appropriate provider (Anthropic, OpenAI, local Ollama, Venice AI, etc.) with full request/response logging. See [`pmoves/docs/tensorzero/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/docs/tensorzero) and the `.claude/context/tensorzero.md` quick-reference.

The **Model Fabric** contract governs how models are selected, versioned, evaluated, and audited across nodes:
- [`MODEL_REGISTRY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_REGISTRY.md)
- [`MODEL_FABRIC_CONTRACT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_FABRIC_CONTRACT.md)
- [`MODEL_SOURCE_OF_TRUTH.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_SOURCE_OF_TRUTH.md)

**Venice + TensorZero** integration adds a privacy-preserving inference path for users who require sovereign, uncensored model access without cloud data exposure ([`pmoves/docs/venice-tensorzero-integration/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/docs/venice-tensorzero-integration)).

The full per-service open-source model recommendation set — from Agent Zero brain to Whisper transcription to YOLOv8 vision — is catalogued in [`Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/Open-Source%20Model%20Recommendations%20for%20PMOVES%20by%20Service%20%26%20Deployment%20Context.md). This document is itself a public good: a 77 KB, deployment-context-aware survey of which open-source models fit which PMOVES service on which class of hardware (3090/4090/5090, Jetson Orin, CPU).

### 2.3 Retrieval & knowledge — Hi-RAG v2, Cipher Memory, Neo4j

**Hi-RAG Gateway v2** (port 8086 CPU, 8087 GPU) provides hybrid retrieval — Qdrant (vectors, 2560d Qwen3-Embedding-4B) + Neo4j (graph) + Meilisearch (full-text), with cross-encoder reranking. This is the canonical retrieval surface; the legacy v1 path is being retired ([`pmoves/docs/INTEGRATIONS_OVERVIEW.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/INTEGRATIONS_OVERVIEW.md)).

**Cipher Memory** (port 8105) is the agent-side persistent memory layer — Neo4j-backed knowledge graph, exposed both as an HTTP API (`/api/memory`) and as an MCP server (`pmoves-cipher`). The **2nd Brain MCP** (PR #1539) bridges this to Obsidian vaults, Google Workspace, and Gemini/Gemma embedding models, so an agent can read and write to a living institutional knowledge base.

### 2.4 Mesh networking — Tailscale, Headscale, and the Hostinger fleet

The fleet is glued together by **Tailscale** (commercial tailnet) with **Headscale** (open-source self-hosted control plane) as the sovereign fallback. Submodules: [`PMOVES-Tailscale`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/PMOVES-Tailscale), [`PMOVES-Headscale`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/PMOVES-Headscale). Hygiene runbook: [`TAILSCALE_NODE_HYGIENE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TAILSCALE_NODE_HYGIENE.md).

The production substrate is the **Hostinger KVM fleet** ([`pmoves/docs/operations/TOPOLOGY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/operations/TOPOLOGY.md)):

| Host | Role | Key services |
|------|------|---------------|
| `pmoves-kvm4-1` | API gateway | TensorZero `:3030`, Agent Zero `:8080`, Hi-RAG v2 `:8086`, Archon `:8091`, Mesh Agent, Extract Worker |
| `pmoves-kvm4-2` | Data hub | **NATS `:4222` fleet hub**, Supabase 13-svc stack, Qdrant, Neo4j, Meilisearch, Prometheus, Grafana, Loki, MinIO |
| `pmoves-kvm2` | Reverse proxy + relay | nginx SSL termination, RustDesk `hbbs/hbbr` rendezvous + relay |

GPU and edge nodes (`pmoves-5090`, `pmoves-4090`, `pmoves-z890`, `pmoves-b850`, Jetson Orin, DGX Spark) join the tailnet and connect to the NATS hub at `nats://…@pmoves-kvm4-2:4222` for cross-node fan-out. This is the architectural foundation for MANET / resilient-connectivity work in §3.

### 2.5 Event bus & coordination — NATS JetStream

**NATS JetStream** is the message backbone — always authenticated (`NATS_URL=nats://${NATS_USER}:${NATS_PASS}@…`). Subject taxonomy and configuration:
- [`CLAW_NATS_SUBJECTS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/CLAW_NATS_SUBJECTS.md)
- [`NATS_CONFIGURATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/NATS_CONFIGURATION.md)
- [`.claude/context/nats-subjects.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/context/nats-subjects.md) (comprehensive)
- [`.claude/context/geometry-nats-subjects.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/context/geometry-nats-subjects.md) (GEOMETRY BUS `tokenism.*`, `geometry.*`, `a2ui.*` subjects)

The `pmoves-nats-fleet` MCP server exposes NATS publish/subscribe directly to operator tooling and IDE agents.

### 2.6 Voice, multimodal, and media pipeline

The platform ingests, transcribes, and analyses long-form media end-to-end. Component services:
- **Flute-Gateway** (`:8055` HTTP + WS) — multimodal voice via Pipecat, prosodic TTS API (`/v1/voice/synthesize/prosodic`).
- **Ultimate-TTS-Studio** (`:7860` native) — 14-engine GPU-accelerated TTS, runs natively via Pinokio.
- **PMOVES.YT** (`:8077`) — YouTube ingestion with MinIO persistence.
- **FFmpeg-Whisper** (`:8078`) — Faster-Whisper transcription with Jetson/GPU auto-detect.
- **Media-Video Analyzer** (`:8079`) — YOLOv8 frame analysis with Supabase output.
- **Media-Audio Analyzer** (`:8082`) — emotion/speaker detection (HuBERT).
- **DeepResearch** (`:8098`) / **SupaSerch** (`:8099`) — autonomous research workers that fan out across Archon, Hi-RAG, and MCP tools.

The voice layer has since matured into a **multi-engine voice-agent fabric** ([`docs/subsystems/VOICE_AGENTS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/subsystems/VOICE_AGENTS.md)): a unified `voice_profiles` registry drives engine selection, **host-affinity routing** maps each persona to an engine to a node (so GPU-heavy engines land on GPU nodes while a **CPU Kokoro** deploy unit keeps voice available on GPU-less hosts), and per-engine license/attribution is tracked for self-host transparency. Expressive utterance can be triggered directly by an agent's CHIT trail-sign — governance-by-flow rather than a separate speak call.

Quick reference: [`.claude/CATALOG.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/CATALOG.md).

### 2.7 Observability and security posture

Every service exposes `/healthz` and `/metrics`. **Prometheus** (`:9090`), **Grafana** (`:3000`), **Loki** (`:3100`) + Promtail provide the full metrics+logs stack. The TensorZero ClickHouse layer is the authoritative LLM observability surface (full request/response logging, token tracking, cost-per-model attribution).

The **security hardened deployment guide** ([`Hardened Agentic AI Services Catalog`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/PMOVES.AI-Edition-Hardened-Full.md)) is the operator-facing playbook for ephemeral CI runners, multi-stage Docker hardening, BuildKit secret mounts, RustDesk + Tailscale zero-trust networking, and CIS-aligned posture. CHIT-signed provenance trails are the cryptographic spine: [`pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md) tracks per-service signing coverage (Full / Partial / None).

### 2.8 Distribution — Pinokio one-click packaging

Major user-facing services are packaged as **Pinokio manifests** so a community member with a consumer GPU can install and run the stack locally with no cloud subscription. Guides: [`PINOKIO_PACKAGING_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PINOKIO_PACKAGING_GUIDE.md), [`PINOKIO_EXAMPLE_MANIFESTS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PINOKIO_EXAMPLE_MANIFESTS.md), [`PINOKIO_TESTING_DEPLOYMENT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PINOKIO_TESTING_DEPLOYMENT.md). The P7 stage manager ([`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/ROOM_MANIFEST_CONTRACT.md)) coordinates rooms-on-a-stage lifecycle (rehearsal → live → review → archive) across Pinokio-packaged services.

### 2.9 Rooms-on-a-stage and the publishing control plane

The "rooms-on-a-stage" model is now concrete: **10 room manifests** are live on `main` ([`pmoves/config/rooms/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/config/rooms)) — community, studio, control, and fabric rooms — each a declarative interface validated against a JSON-Schema contract by a CI gate ([`pmoves/scripts/validate_room_manifests.py`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/scripts/validate_room_manifests.py), catalogued in [`pmoves/config/rooms/catalog.json`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/config/rooms/catalog.json)). A room selects a workload profile, loads its apps and skill-bindings, and manages its own lifecycle. The design is documented in [`pmoves/docs/ROOMS_ON_A_STAGE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/ROOMS_ON_A_STAGE.md).

On top of this sits an emerging **publishing control plane**: the geometry state vector carries a dedicated publish-authorization dimension ([`pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md)), so autonomous publishing is governed by an explicit, operator-controllable gate with a fail-closed egress floor — nothing crosses to a public surface without passing a redaction/PII floor and, where required, human final-say. This is the accountability substrate for the community-pilot work in §3: local models can operate autonomously under "village rules" while every outbound publication remains gated and auditable.

---

## 3. Public-Benefit Roadmap (grant-funded work)

This section is the *new* work this grant would directly accelerate. Each item builds on the merged-on-`main` foundation in §2.

### 3.1 Resilient connectivity — Tailscale, Headscale, MANET overlays

**Status:** Tailscale + Headscale fleet is operational; MANET/mesh extensions to off-grid contexts are scoped but not yet built.

The grant would fund:
- A **community-deployable Headscale appliance** packaged as a Pinokio manifest, so a community group can stand up its own sovereign control plane without commercial Tailscale.
- A **MANET / OpenMANET-style overlay** for Jetson and Raspberry Pi-class devices, enabling PMOVES nodes to keep coordinating when WAN connectivity is unreliable or absent (community emergency response, rural deployment, disaster-recovery scenarios). The submodule scaffolding lives at [`PMOVES-Tailscale`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/PMOVES-Tailscale) and [`PMOVES-Headscale`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/PMOVES-Headscale); the integration target is to make any Jetson or Pi node a first-class participant in the lattice over commodity mesh radio.
- Field documentation and an operator playbook for community technologists who are not full-time SRE.

### 3.2 Edge AI on Jetson and Pi-class hardware

**Status:** Jetson Orin already runs `ffmpeg-whisper` and quantised LLMs (Phi-3-mini, Qwen-1.8B, 4-bit GGUF). Multi-node Jetson swarming is on the roadmap.

The grant would fund:
- Hardening the **edge inference profile** (`pmoves/docs/NODE_PROFILES/`) for Jetson Orin Nano Super and Raspberry Pi 5-class boards, with auto-detected fallbacks documented in [`MODEL_REGISTRY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_REGISTRY.md).
- TensorRT-optimised vision pipelines (YOLOv8/v11) for community use cases identified in §4.
- A reproducible **bring-up image** for a Jetson + Pi mixed cluster, so an organisation can buy commodity hardware and replicate the lattice.

### 3.3 Sovereign inference — private LLM access for community users

**Status:** Venice + TensorZero integration is in active development; the privacy framing is real but operational hardening remains.

The grant would fund:
- Production hardening of the Venice + TensorZero path so community users get private inference (no cloud data exposure) routed transparently behind the same TensorZero gateway already used internally.
- An **open access-control model** layered on Supabase / GoTrue so community pilots can grant inference quota to participants without exposing the underlying provider keys.

### 3.4 Community pilot — Fordham Hill Oval (Bronx)

**Status:** Charter, DAO constitution, and proposal drafts exist under [`CATACLYSM_STUDIOS_INC/L2-DESIGN/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/CATACLYSM_STUDIOS_INC/L2-DESIGN) and [`L3-PILOT/fordham/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/CATACLYSM_STUDIOS_INC/L3-PILOT/fordham). The Fordham Hill cooperative model is the canonical public-benefit deployment context for PMOVES.AI.

The grant would fund:
- A **physical pilot node** at Fordham Hill Oval — a small Jetson + KVM-class deployment that residents can use directly (OCR/RAG over local documents, AI-assisted small-business tooling, voice agents for accessibility).
- Operator training and a transparent KPI dashboard (residents trained, vendor onboarding, jobs served, GPU-hours allocated) following the structure already drafted in [`Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/CATACLYSM_STUDIOS_INC/L2-DESIGN/proposals/Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md).
- Cooperative-economics governance scaffolding (proof-of-service rewards, two-house voting) drawn from the existing DAO constitution draft.

### 3.5 Open documentation and community onboarding

**Status:** The repository ships a comprehensive `.claude/` developer-context tree, an `AGENTS.md` universal coding-agent contract, a living-docs registry, and CLAUDE.md guidance for AI-assisted contributors. The public-benefit work is to make this approachable for non-AI-developer contributors.

The grant would fund:
- Plain-language operator guides for each major component, mapped to the existing technical docs.
- A **community contributor onboarding path** (good-first-issue triage, mentor pairing, contribution incentives via ToKenism credits).
- Video walkthroughs of the bring-up, the mesh, the voice layer, and the pilot pattern.

---

## 4. Who PMOVES.AI Serves

### 4.1 Target communities

| Community | What PMOVES.AI gives them |
|-----------|----------------------------|
| **Under-resourced urban neighborhoods** (starting with the Bronx / Fordham Hill) | Locally-run AI assistance, document RAG over community records, voice accessibility, cooperative economics scaffolding |
| **Independent technologists and small studios** | A reproducible multi-agent stack that does not require cloud-vendor lock-in |
| **Edge / resilient-connectivity contexts** | Jetson- and Pi-class nodes that coordinate over mesh, including when WAN is unreliable |
| **Open-source AI researchers** | A real testbed for multi-agent coordination, CHIT-geometry encoding, EvoSwarm RL, and Hi-RAG retrieval |
| **Creators and movement-focused practitioners** | The Creator Pipeline (themes, motion, remotion) and Flute-Gateway voice synthesis for accessible content production |

### 4.2 Accessibility-first design principles

- **Local-first.** Pinokio packaging means consumer GPUs are sufficient; no mandatory cloud subscription.
- **Sovereign by default.** Tailscale + Headscale offers commercial convenience with a sovereign fallback path.
- **Open weights, open protocols.** CHIT is published; agent skills and prompt forms are openly licensed; the full model-selection rationale is in [`Open-Source Model Recommendations…`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/Open-Source%20Model%20Recommendations%20for%20PMOVES%20by%20Service%20%26%20Deployment%20Context.md).
- **Auditable provenance.** CHIT-signed trails on critical services give every operation a cryptographic receipt ([`pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md)).
- **Bronx-first deployment.** The first community pilot is local to where the founder lives; the architecture is designed for replication elsewhere.

### 4.3 Open-source commitment

PMOVES.AI is developed publicly at https://github.com/POWERFULMOVES/PMOVES.AI. Architecture, runbooks, the CHIT protocol, the model registry, NATS subject taxonomy, and the deployment topology are all on `main`. The repository carries 53 git submodules representing the platform's component services and a separately versioned skills constellation under [`skills/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/skills) (Anthropic skills, agent-sandbox, fork-repository, awesome-agent-skills, claude-d3js — see [`skills/README.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/skills/README.md)).

---

## 5. Budget Narrative

> **Reviewer note.** Dollar figures are placeholders pending negotiation with the grantor. Numbers below are intentionally left as `$X` because we will not commit to amounts we cannot defend.

### 5.1 Infrastructure capacity — `$X`
- Additional Jetson Orin and Raspberry Pi 5 nodes for the community pilot (§3.4) and edge-AI hardening (§3.2).
- Hardening of the NATS JetStream hub on `pmoves-kvm4-2` for sustained pilot load.
- Headscale appliance Pinokio packaging and signing infrastructure.
- Tailscale / mesh radio interface work for MANET overlay (§3.1).

### 5.2 Open-source engineering & documentation — `$X`
- Hardening Venice + TensorZero sovereign-inference path (§3.3).
- Pinokio packaging hardening for Windows / macOS / Linux parity.
- Plain-language operator documentation aligned to the existing `.claude/` developer-context tree.
- Living-docs registry expansion (`pmoves/configs/living_docs_registry.yaml`) so the public docs stay accurate as the code moves.

### 5.3 Community deployment — `$X`
- Physical pilot at Fordham Hill Oval (hardware, on-site training, KPI dashboard).
- Onboarding events and mentor pairing for community contributors.
- Cooperative-economics governance scaffolding (multisig, on-chain attribution per draft DAO constitution).

### 5.4 Research and roadmap continuity — `$X`
- SPARK Model Strategy ([`SPARK_MODEL_STRATEGY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/SPARK_MODEL_STRATEGY.md)) — domain-tuned models trained on CHIT-encoded data.
- Constellation-Harvest Regularization research (`pmoves/docs/Constellation-Harvest-Regularization/`).
- EvoSwarm v2 cross-node federated reward experiments.

> **Defensibility note.** The 5-year financial projection at [`CATACLYSM_STUDIOS_INC/PMOVES-5-Year-Financial-Model.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/CATACLYSM_STUDIOS_INC/PMOVES-5-Year-Financial-Model.md) is *illustrative*. It is not audited and does not constitute a financial commitment. We do not cite it as a grant deliverable.

---

## 6. Milestones & Timeline

| Quarter | Milestone |
|---|---|
| Q3 2026 | Headscale community appliance v0.1 — Pinokio-installable sovereign control plane |
| Q3 2026 | Jetson + Pi edge-AI bring-up image v1 — reproducible commodity-hardware lattice |
| Q3 2026 | Fordham Hill pilot node online — physical install, KPI dashboard live |
| Q4 2026 | MANET / mesh overlay v0.1 — Jetson nodes coordinate when WAN is unreliable |
| Q4 2026 | Venice + TensorZero sovereign-inference GA |
| Q4 2026 | Plain-language operator guides for all major components |
| Q1 2027 | Community contributor onboarding path live (good-first-issue triage, mentor pairing) |
| Q1 2027 | EvoSwarm v2 — federated reward across pilot nodes |
| Q2 2027 | Second community pilot site identified and scoped |

Milestones map to the public roadmap in [`pmoves/docs/NEXT_STEPS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/NEXT_STEPS.md); grant-funded items will be tagged in commit metadata for transparent reporting.

---

## 7. Team

**Russell Richardson — Founder, Technical Director (CATACLYSM STUDIOS, INC.)**
Bronx-based builder. Architect of the PMOVES.AI platform, the CHIT protocol, and the Grand Convergence five-layer thesis. Also active as the artist persona DARKXSIDE; the cultural and technical work are deliberately joined ([`pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md)).

**Multi-agent collaborators (in-repo)**
PMOVES.AI uses an explicit Three-Body coordination model ([`pmoves/docs/AGENTS/AGNOTE4482.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/AGENTS/AGNOTE4482.md)) with a Delivery body (implementation), Control body (review & merge sequencing), and Memory body (CHIT signing, Cipher Memory, provenance). This is not metaphor — it is enforced at the agent-frontmatter level so AI-assisted contributions are auditable.

**Community contributors**
Open-source contributors are tracked at https://github.com/POWERFULMOVES/PMOVES.AI/graphs/contributors. As of July 11, 2026 the repository has accumulated **3,864 commits** on `main` and **1,791 merged pull requests** over its development arc (`git rev-list --count origin/main`; `gh pr list --state merged` — refresh both at submission time).

---

## 8. Reference Documents

Every claim in this proposal is verifiable against a tracked file in the repository. Primary reference docs:

| Topic | Document |
|-------|----------|
| Architecture thesis | [`PMOVES_MOF_ARCHITECTURE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md) |
| Five-layer unification | [`PMOVES_GRAND_CONVERGENCE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md) |
| CHIT protocol | [`PMOVESCHIT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/PMOVESCHIT.md), [`CGP_v1.0_SPECIFICATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md) |
| Company / platform overview | [`CATACLYSM_STUDIOS_INC.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md) |
| Fordham Hill pilot proposal | [`Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/CATACLYSM_STUDIOS_INC/L2-DESIGN/proposals/Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md) |
| Service catalog | [`.claude/CATALOG.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/CATALOG.md) |
| Bootstrap context | [`.claude/BOOTSTRAP.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/.claude/BOOTSTRAP.md) |
| Service topology (Hostinger fleet) | [`pmoves/docs/operations/TOPOLOGY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/operations/TOPOLOGY.md) |
| Hardened deployment playbook | [`docs/PMOVES.AI-Edition-Hardened-Full.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/docs/PMOVES.AI-Edition-Hardened-Full.md) |
| Open-source model recommendations | [`Open-Source Model Recommendations for PMOVES by Service & Deployment Context.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/Open-Source%20Model%20Recommendations%20for%20PMOVES%20by%20Service%20%26%20Deployment%20Context.md) |
| Production audit dashboard | [`PRODUCTION_AUDIT_DASHBOARD.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md) |
| Active roadmap | [`NEXT_STEPS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/NEXT_STEPS.md) |
| SPARK research roadmap | [`SPARK_MODEL_STRATEGY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/SPARK_MODEL_STRATEGY.md) |
| ToKenism economic model | [`TOKENISM_ECONOMIC_MODEL.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TOKENISM_ECONOMIC_MODEL.md), [`TOKENISM_DEVELOPER_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md) |
| Integration map | [`INTEGRATIONS_OVERVIEW.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/INTEGRATIONS_OVERVIEW.md) |
| Tailscale node hygiene | [`TAILSCALE_NODE_HYGIENE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TAILSCALE_NODE_HYGIENE.md) |

---

## 9. Contact

**Organization:** CATACLYSM STUDIOS, INC.
**Operating platform:** PMOVES.AI
**Principal:** Russell Richardson
**GitHub:** https://github.com/POWERFULMOVES/PMOVES.AI
**Location:** The Bronx, New York, USA

---

## 10. Open questions for reviewers

These are items Russell should confirm or refine before the proposal is submitted to a specific grantor:

1. **Target grantor / programme.** This proposal is grantor-agnostic. Tailor §1.1 (mission), §3 (roadmap), and §5 (budget) to the specific RFP. NSF, NTIA, MacArthur, Mozilla Foundation, Internet Society / OTF (mesh/connectivity), and city-level Bronx economic-development RFPs all imply different framings.
2. **Budget figures.** §5 leaves `$X` placeholders intentionally. Plug in numbers grounded in actual hardware quotes (Jetson Orin Nano Super list price, Pi 5 kits, Hostinger annual VPS spend) and FTE estimates before submission.
3. **Pilot scope at Fordham Hill.** §3.4 references the existing DAO proposal but does not commit to a specific resident headcount, vendor list, or token-economic structure. Confirm what is in-scope for *this* grant cycle vs. a follow-on.
4. **MANET vs. OpenMANET specifics.** §3.1 references both as user task framing. Pick a concrete protocol family (B.A.T.M.A.N.-adv, Babel, custom OLSR variant, Wi-Fi HaLow, LoRa-mesh) once hardware is finalised.
5. **Defensibility of the repository metrics.** The §7 numbers (3,864 commits / 1,791 merged PRs as of 2026-07-11) are live counts. Note the repo squash-merges, so `git log --grep "Merge pull request"` undercounts — use `git rev-list --count origin/main` for commits and `gh pr list --state merged` (or the GitHub API) for merged PRs. Refresh both at submission time.
6. **Letters of support.** Fordham Hill resident leaders, Bronx community organisations, partner labs, or open-source maintainers — line these up early; grantors weight them heavily.
7. **Fiscal sponsor vs. direct grant.** CATACLYSM STUDIOS, INC. is the operating entity. Confirm 501(c)(3) status (or fiscal sponsor arrangement) matches the grantor's eligibility requirements.
8. **DARKXSIDE persona framing.** The technical and cultural identities are intentionally joined in internal documents. Some grantors will read this as an asset (authentic community grounding); some will read it as scope sprawl. Decide whether to foreground it in §7 or leave it as a reference under §8.

---

*This grant proposal reflects the live state of the PMOVES.AI repository as of July 11, 2026. All technical claims link to tracked files on `main` and are verifiable against https://github.com/POWERFULMOVES/PMOVES.AI. Version history is preserved via the repository commit log; prior versions of this proposal can be retrieved with `git log -- pmoves/docs/GRANT_PROPOSALS/PMOVES_AI_GRANT_PROPOSAL_2026.md`.*
