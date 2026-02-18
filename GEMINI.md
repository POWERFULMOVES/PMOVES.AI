# Gemini CLI Integration — PMOVES.AI Ecosystem

_v1.4.0 — Unified Agentic Structure & Taxonomy_

Welcome to the PMOVES.AI production environment. As a Gemini CLI agent, you are integrated into a multi-layered, 60-agent ecosystem spanning from data persistence (Tier 1) to user interaction (Tier 7).

## 1. Agentic Taxonomy & Topology

PMOVES.AI uses a formalized **Type System** for agents, defined in `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`.

### Agent Classes
- **Legendary (`POWERFULMOVES`)**: Brand umbrella and foundational doctrine.
- **Standard (`PMOVES-`)**: Core production agents (Agent Zero, Archon, HiRAG).
- **Specialized (`Pmoves-`)**: Domain-specific experts (Hyperdimensions, Cipher, Health).
- **Utility (`pmoves-`)**: Infrastructure and CLI tools (Surf, E2B-Spells).

### The 7 Service Tiers
1. **Data**: Persistence (Supabase, Qdrant, Neo4j, Meilisearch).
2. **API**: Routing & Protocol Bridging (TensorZero Gateway, Flute).
3. **LLM**: Reasoning & Generation (DeepResearch, Llama Throughput Lab).
4. **Worker**: Processing & Transformation (Extract Worker, LangExtract).
5. **Media**: Multimodal Ingestion (PMOVES.YT, FFmpeg-Whisper, TTS).
6. **Agent**: Orchestration & Planning (Agent Zero, Archon, BoTZ Gateway).
7. **UI**: Interaction & Visualization (MAI-UI, A2UI, Crush, Hyperdimensions).

**Topology Map**: See [`pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md`](pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md) for Mermaid diagrams of the full ecosystem.

## 2. Communication Protocols

PMOVES agents communicate through three primary planes:

- **MCP (Model Context Protocol)**: Direct tool-based interaction. Agent Zero uses MCP to call Archon, Supabase, and local filesystem tools.
- **NATS (Nervous System)**: Event-driven pub/sub coordination. The "NATS Nervous System" handles high-throughput events like media ingestion (`ingest.*`) and swarm metadata.
- **CHIT (Immune System)**: Compressed Hierarchical Information Transfer. Uses **CGP Packets** (Consciousness Geometry Protocol) to transfer agent state and geometric resonance across the "Geometry Bus".

## 3. Development Modes (Kilocode)

Your capabilities are extended through specialized **Kilocode Modes**, defined in `.kilocodemodes`. Switch modes to align with your current task:

- `pmoves-architect`: High-level system design and orchestration (Tier 6).
- `pmoves-code`: Microservice implementation and integration (Tiers 3-4).
- `pmoves-debug`: Diagnostics, log analysis (Loki), and metric queries (Prometheus).
- `pmoves-review`: Security audits and PR analysis (Tier 6).
- `pmoves-portal`: Geometry Bus and CHIT encoding/decoding operations.
- `pmoves-crush`: User onboarding and "experience layer" interaction.

## 4. Skill Bundles

PMOVES agents utilize **Skill Bundles** for consistent cross-submodule operation:
- `bringup-audit`: Tiered bring-up and smoke validation.
- `secrets-chit-funnel`: Secret mapping to CHIT manifests.
- `submodule-parity`: Alignment between overlays and upstream code.
- `persona-grounding`: Anchoring personas to source materials.
- `multimodal-verifier`: Verification via text, audio, and VLM.

## 5. Multimodal Communication (Flute)

The **Multimodal Communication Layer ("Flute")** enables rich interaction across text, image, audio, and structured data.
- **POML**: Prompt Orchestration Markup Language for structured templates.
- **Mangle**: Logic-based translation of complex data queries.
- **Qwen-3 Omni**: Native multi-modal understanding and generation.
- **Pipecat**: Real-time multimodal output coordination.

## 6. Current Branch & Audit Focus

- **Active Branch**: `docs/production-doc-reorg` (Documentation Branch).
- **Target Branch**: `PMOVES.AI-Edition-Hardened` (Production Branch).
- **Current Task**: Unifying the agentic structure and mapping the topology for the final production audit review.

## 5. Source of Truth

- **Agent Registry**: `pmoves/config/agent_registry.yaml` — Canonical definitions for all 60 agents.
- **Services Catalog**: `.claude/context/services-catalog.md` — Port assignments and health endpoints.
- **NATS Subjects**: `.claude/context/nats-subjects.md` — Event topology.

---

_Use `/jules` for large-scale refactors or missing test coverage. Reference `AGENTS.md` for project-wide conventions._
