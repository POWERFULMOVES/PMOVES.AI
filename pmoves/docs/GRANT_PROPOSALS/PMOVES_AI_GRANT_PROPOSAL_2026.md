# PMOVES.AI — Grant Proposal 2026
**Organization:** CATACLYSM STUDIOS, INC. (dba PMOVES.AI)  
**Location:** The Bronx, New York, NY  
**Repository:** https://github.com/POWERFULMOVES/PMOVES.AI  
**Date:** May 20, 2026  
**Version:** v2.0 — Updated to reflect current platform state

---

## Executive Summary

PMOVES.AI is an open-architecture, AI-native platform built to democratize access to embodied intelligence — fusing movement science, reinforcement learning, multi-modal AI, and decentralized infrastructure to serve creators, athletes, coaches, educators, and underserved communities worldwide. Developed by CATACLYSM STUDIOS, INC., a Bronx-based independent technology studio, the platform has evolved from a concept into a production-grade, multi-agent AI system with over 1,550 pull requests merged as of May 2026.

We are seeking grant funding to accelerate community deployment, support open research contributions, and expand infrastructure capacity for our growing distributed node network.

---

## 1. Project Overview

### 1.1 Mission

PMOVES.AI exists to make AI-powered movement intelligence accessible to everyone — from professional athletes to youth programs in under-resourced communities — without requiring proprietary hardware or expensive subscriptions. Our platform encodes human movement as structured mathematical geometry (the **CHIT** protocol), routes it through a sovereign AI inference network, and returns actionable coaching intelligence in real time.

### 1.2 What We Build

The platform is organized into four interlocking layers:

| Layer | Name | Function |
|---|---|---|
| L1 | **PMOVES-CHIT** | Movement encoding protocol — compresses biomechanical data into geometry vectors |
| L2 | **Geometry Bus** | Real-time transport layer for CHIT payloads across agents and nodes |
| L3 | **NEXUS / TensorZero** | Model routing fabric — selects optimal AI model per task with cost/latency optimization |
| L4 | **CATACLYSM Platform** | Infrastructure layer — GPU fleet, Docker MCP Toolkit, PBNJ node fleet, Pinokio packaging |

Built on top of these layers are user-facing products including **PMOVES-BoTZ** (AI coaching agents), **PMOVES-CONCH** (conversational intelligence), the **BOTZ Skills Marketplace**, and the **Creator Pipeline** for athletes and content producers.

---

## 2. Technical Progress (As of May 2026)

The following capabilities have been built, validated, and merged to `main` in the POWERFULMOVES/PMOVES.AI repository. This section reflects the current state of the codebase.

### 2.1 Agent Intelligence — Meta-Agent & EvoSwarm

**Meta-Agent Phase 1** is complete and validated. The meta-agent orchestrates all sub-agents, assigns tasks from the NATS message bus, monitors health, and performs autonomous self-repair. Documentation: [`META_AGENT_PHASE_1_VALIDATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/META_AGENT_PHASE_1_VALIDATION.md).

**EvoSwarm** implements evolutionary reinforcement learning across the agent fleet. Rather than training a single model, EvoSwarm continuously mutates, evaluates, and selects top-performing agent configurations — enabling the platform to improve without human intervention. The parameter catalog and operations guide are fully documented in [`EVOSWARM_OPERATIONS_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/EVOSWARM_OPERATIONS_GUIDE.md).

**AgentGym RL** provides a sandboxed reinforcement learning training environment for developing new agent skills, described in [`AGENTGYM_RL_OPERATIONS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/AGENTGYM_RL_OPERATIONS.md).

### 2.2 Model Intelligence — TensorZero & Model Fabric

The platform now routes inference requests through **TensorZero**, an open-source model gateway that enables real-time A/B testing, cost-aware model selection, and feedback-driven learning across providers. This is documented in [`pmoves/docs/tensorzero/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/docs/tensorzero).

The **Model Fabric (MoF)** contract governs how models are selected, versioned, and evaluated. MoF integration with the PBNJ fleet expansion was merged May 19, 2026 (PR #1545). The model registry, alignment review, and source-of-truth documents are live at:
- [`MODEL_REGISTRY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_REGISTRY.md)
- [`MODEL_FABRIC_CONTRACT.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_FABRIC_CONTRACT.md)
- [`MODEL_SOURCE_OF_TRUTH.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MODEL_SOURCE_OF_TRUTH.md)

**Minimax** integration adds state-of-the-art video/audio generation capabilities for the creator pipeline, documented in [`MINIMAX_INTEGRATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/MINIMAX_INTEGRATION.md).

### 2.3 Memory & Knowledge — Graphiti + 2nd Brain MCP

**Graphiti** provides a temporal knowledge graph layer backed by Neo4j, giving agents persistent, queryable memory of all interactions, entities, and events. The agent registry, integration guide, and protocol reference are documented in detail. Agents can now remember athlete profiles, coaching history, and performance trends across sessions.

The **2nd Brain MCP** (merged May 19, 2026, PR #1539) connects the agent layer to:
- **Obsidian** — local vault (DARKXSIDE Documents, synced to Google Drive)
- **Google Workspace** — Docs, Sheets, Calendar, Gmail edit access
- **Gemini / Gemma4** — embedding models for geometry bus operations

This gives PMOVES.AI agents the ability to read and write to a living knowledge base, dramatically improving context retention and institutional memory.

### 2.4 Infrastructure — GPU Fleet & Docker MCP Toolkit

The **PBNJ fleet** (bare-metal provisioning network) has been expanded with MoF integration (PR #1545). Supported node types include `kvm4`, `gpu-5090`, `rdna4-workstation`, `dgx-spark`, and `pve-member` clusters. GPU orchestration documentation is at [`GPU_ORCHESTRATION_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/GPU_ORCHESTRATION_GUIDE.md).

The **Docker MCP Toolkit** fleet foundation (Lanes 0/H/I) was merged May 19, 2026 (PR #1553). This enables any PMOVES-compatible node to run containerized MCP server fleets, unlocking edge inference and distributed agent deployment without cloud dependency.

**Tailscale** provides zero-config private mesh networking across all nodes, documented in [`TAILSCALE_NODE_HYGIENE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TAILSCALE_NODE_HYGIENE.md).

**NATS JetStream** is the message backbone for all agent-to-agent communication. Subject taxonomy and configuration are documented in [`CLAW_NATS_SUBJECTS.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/CLAW_NATS_SUBJECTS.md) and [`NATS_CONFIGURATION.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/NATS_CONFIGURATION.md).

### 2.5 Distribution — Pinokio Packaging

The platform packages all major services as **Pinokio** manifests — enabling one-click local installation on consumer hardware. This is central to our accessibility mission: a youth coach in the Bronx can run PMOVES.AI locally with no cloud subscription. Packaging guides and deployment docs: [`PINOKIO_PACKAGING_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PINOKIO_PACKAGING_GUIDE.md).

### 2.6 PMOVES-BoTZ — JWT Sunset & Security Hardening

**PMOVES-BoTZ** (the agent coaching interface) completed JWT sunset on May 20, 2026, transitioning to a more secure, stateless authentication model. The BOTZ Skills Marketplace, documented at [`BOTZ_SKILLS_MARKETPLACE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/BOTZ_SKILLS_MARKETPLACE.md), enables third-party skill developers to publish, monetize, and distribute coaching modules.

### 2.7 Creator Pipeline & TOKENISM Economy

The **Creator Pipeline** connects athletes, coaches, and content producers to the AI layer, enabling automated highlight generation, coaching report production, and audience engagement tools — powered by Minimax video/audio generation. See [`CREATOR_PIPELINE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/CREATOR_PIPELINE.md).

**TOKENISM** is the platform's internal economic model governing how compute credits, coaching units, and creator earnings are allocated. The developer guide and economic model are documented at:
- [`TOKENISM_DEVELOPER_GUIDE.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md)
- [`TOKENISM_ECONOMIC_MODEL.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TOKENISM_ECONOMIC_MODEL.md)

### 2.8 Venice + TensorZero Integration

The Venice AI privacy-preserving inference layer is being integrated with TensorZero to offer users sovereign, uncensored inference without cloud data exposure. Documentation: [`pmoves/docs/venice-tensorzero-integration/`](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/docs/venice-tensorzero-integration).

---

## 3. SPARK Model Strategy

The **SPARK Model Strategy** is PMOVES.AI's long-term AI research roadmap, documented in [`SPARK_MODEL_STRATEGY.md`](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/SPARK_MODEL_STRATEGY.md). It outlines a path from current commercial model routing toward fine-tuned, domain-specific movement intelligence models trained on CHIT-encoded biomechanical data.

Key research directions include:
- **Latent Geometry Control** — using the geometry bus as a control knob for steering model behavior (see `Latent_Geometry_Is_a_Control_Knob` research directory)
- **Constellation-Harvest Regularization** — a novel training regularization technique for movement sequence learning
- **IWM + Self-Reflection** — internal world model architectures with self-correcting inference loops
- **Human Construct Neural Network** — a biologically-inspired architecture for modeling human kinematic sequences

---

## 4. Community Impact

### 4.1 Who We Serve

PMOVES.AI was founded with a mandate to serve communities that traditional sports tech ignores:

- **Youth athletes in under-resourced neighborhoods** — particularly in the Bronx, where access to professional coaching is limited by cost and geography
- **Independent coaches and trainers** — who cannot afford enterprise SaaS tools but need AI assistance to scale their practice
- **Open-source researchers** — contributing to movement AI, reinforcement learning, and embodied intelligence
- **Creators and content producers** — in the athlete/fitness space, who need production-quality AI tools at consumer prices

### 4.2 Accessibility-First Design

Every architectural decision in PMOVES.AI prioritizes accessibility:

- **Pinokio local packaging** — runs on consumer GPUs, no cloud required
- **Open weights, open protocols** — CHIT is a public protocol; agent skills are openly licensed
- **TOKENISM credits** — community contributors earn compute credits through platform participation
- **Bronx-first deployment** — pilot programs with local schools and community athletic centers

### 4.3 Open Source Commitment

The PMOVES.AI platform is publicly developed at https://github.com/POWERFULMOVES/PMOVES.AI. All agent skill specifications, the CHIT protocol, API documentation, and architecture guides are published openly. Over 1,550 pull requests have been processed with full review history preserved.

---

## 5. Budget Narrative

Grant funding will be allocated across the following priorities:

### 5.1 Infrastructure Capacity ($X)
- GPU node expansion for the PBNJ fleet (additional `kvm4` and `gpu-5090` nodes)
- NATS JetStream cluster hardening for production load
- Tailscale ACL management tooling for multi-org node federation

### 5.2 Research & Development ($X)
- SPARK Model Strategy — fine-tuning movement foundation models on CHIT data
- Constellation-Harvest Regularization research experiments
- EvoSwarm parameter exploration and benchmarking against standard RL baselines
- AgentGym environment expansion (new sport domains: basketball, dance, martial arts)

### 5.3 Community Deployment ($X)
- Pinokio distribution hardening for Windows/Mac/Linux parity
- Community onboarding documentation and video guides
- Pilot program development with Bronx youth athletic organizations
- BOTZ Skills Marketplace developer grants for third-party skill authors

### 5.4 Operations & Documentation ($X)
- Technical writing for grant-facing and public-facing documentation
- Agent-Zero-Sidecar operations (automated CI/CD, dependency management)
- Security hardening (Playwright E2E redesign, secrets pipeline review)

---

## 6. Milestones & Timeline

| Quarter | Milestone |
|---|---|
| Q3 2026 | SPARK v0.1 fine-tuned movement model — first domain (basketball) |
| Q3 2026 | Pinokio v2 packaging — full Windows/Mac/Linux installer with auto-update |
| Q3 2026 | Bronx pilot launch — 3 partner organizations, 50+ youth athletes |
| Q4 2026 | BOTZ Skills Marketplace public launch — open to third-party developers |
| Q4 2026 | TensorZero + Venice integration complete — sovereign inference GA |
| Q4 2026 | EvoSwarm v2 — cross-node swarm evolution with federated reward |
| Q1 2027 | CHIT v2.0 specification — expanded encoding for 3D pose and velocity fields |
| Q1 2027 | Graphiti temporal memory — full coaching history persistence across seasons |
| Q2 2027 | SPARK v0.3 — multi-sport model with 10K+ CHIT-encoded training sequences |

---

## 7. Team

**POWERFULMOVES (Founder, Technical Director)**  
Bronx-based builder with deep expertise in AI systems architecture, movement science, and open-source development. Leads all technical direction for PMOVES.AI and CATACLYSM STUDIOS, INC.

**Agent-Zero-Sidecar (AI Engineering Agent)**  
Autonomous CI/CD and code review agent embedded in the PMOVES.AI development pipeline. Handles dependency management, security patching, documentation commits, and agent skill development.

**Community Contributors**  
Open-source contributors to the PMOVES.AI codebase, documented in the GitHub contributor graph at https://github.com/POWERFULMOVES/PMOVES.AI/graphs/contributors.

---

## 8. References & Documentation

All technical claims in this proposal are backed by documentation in the public repository. Key reference documents:

- [CATACLYSM_STUDIOS_INC.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md) — Full company and platform overview
- [PMOVESCHIT.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVESCHIT/PMOVESCHIT.md) — CHIT protocol specification
- [PRODUCTION_AUDIT_DASHBOARD.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md) — Live production audit
- [NEXT_STEPS.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/NEXT_STEPS.md) — Active development roadmap
- [SPARK_MODEL_STRATEGY.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/SPARK_MODEL_STRATEGY.md) — AI research roadmap
- [TOKENISM_ECONOMIC_MODEL.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/TOKENISM_ECONOMIC_MODEL.md) — Platform economy
- [INTEGRATIONS_OVERVIEW.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/INTEGRATIONS_OVERVIEW.md) — All third-party integrations
- [PMOVES_SERVICE_TOPOLOGY.md](https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/pmoves/docs/PMOVES_SERVICE_TOPOLOGY.md) — Full service topology map

---

## 9. Contact

**Organization:** CATACLYSM STUDIOS, INC.  
**Platform:** PMOVES.AI  
**GitHub:** https://github.com/POWERFULMOVES/PMOVES.AI  
**Location:** The Bronx, New York, USA

---

*This grant proposal was generated from the live state of the PMOVES.AI repository as of May 20, 2026. All technical claims are verifiable against the public GitHub repository at https://github.com/POWERFULMOVES/PMOVES.AI.*
