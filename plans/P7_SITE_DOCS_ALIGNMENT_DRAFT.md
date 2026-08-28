# P7 Site/Docs Language Alignment Draft

**Purpose**: Close AGNOTE4482 signoff checklist item 1.4 — P7, Discord, and site/docs language pointing at the same frame.
**Date**: 2026-05-02
**Status**: Draft — operator review required
**Canonical truth sources**: AGNOTE4482.md L25-27, AGNOTE_P7_PLAYGROUND.md L338-368, ROOM_MANIFEST_CONTRACT.md

---

## 1. Current State

### What the internal docs say (the truth)

From AGNOTE4482.md L25-27:
> Pinokio 7 (P7) is the PMOVES runtime launcher and fleet orchestrator. In the rooms-on-a-stage model, P7 is not just a process spawner — it is the **room-aware stage manager**: it knows which rooms exist (via `pmoves/config/rooms/catalog.json`), selects the appropriate room profile for a given workload, and manages the transition between rehearsal -> live -> review -> archive states.

From AGNOTE_P7_PLAYGROUND.md L344-358 (the prospectus frame):
> - **Rooms** are the audience-facing entrypoints: foyer, review-room, voice-room, media-room, war-room
> - **Stage** is the state model for each room: rehearsal, live, review, archive
> - **Suits** are the runtime/persona bindings: upstream Agent Zero as the external baseline, PMOVES hardened overlays as the custom fit, voice/theme/persona as the visible styling layer

From ROOM_MANIFEST_CONTRACT.md L26:
> A room is the audience-facing topology — the entrypoint through which users (human or agent) access the platform's capabilities.

### What Discord says

From S14_DRAFTS.md (deployed channel descriptions):

**OBSERVATION**: The deployed Discord channel descriptions use **MOF/crystalline lattice** language, NOT rooms-on-a-stage language. Example from #general:
> PMOVES.AI — a Metal-Organic Framework for distributed machine intelligence. The crystalline lattice through which autonomous agents flow.

No Discord channel description mentions rooms, stages, rehearsals, foyer, or war-room. The rooms-on-a-stage frame has NOT been applied to Discord despite the signoff checklist implying it was.

### What site/docs currently say about P7, rooms, stages

| File | Mentions P7 | Mentions rooms-on-a-stage | Mentions stage states | Mentions stage manager |
|------|-----------|------------------------|--------------------|--------------------|
| `README.md` L62 | No | Section header only | No | No |
| `CLAUDE.md` | No | No | No | No |
| `AGENTS.md` | No | No | No | No |
| `PMOVES-Archon/CLAUDE.md` | No | No | No | No |
| `PMOVES-Archon/README.md` | No | No | No | No |
| `PMOVES-Archon/AGENTS.md` | No | No | No | No |
| `PMOVES-BotZ-gateway/README.md` | No | No | No | No |
| `docs/PMOVES.md` | No | No | No | No |
| `docs/PMOVES_ARC.md` | No | No | No | No |
| `pmoves/docs/NEXT_STEPS.md` | No (references 'room/stage prospectus') | Section header only | No | No |
| `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` | No | Yes (full contract) | Yes | No |

**Summary**: The rooms-on-a-stage model is fully documented in internal agent notes (pmoves/docs/AGENTS/) and the Room Manifest Contract, but is almost entirely absent from every site-facing or developer-facing entry point. README.md has the section header but no substance behind it.

---

## 2. Gap Analysis

### 2.1 `README.md`

**Gap A — Opening paragraph (L9)**
- Current: "A local-first, multi-agent orchestration platform that coordinates autonomous agents (Agent Zero, Archon), hybrid retrieval (Hi-RAG v2), voice synthesis, media processing, and knowledge graphs — all wired together with NATS event-driven messaging and full Prometheus/Grafana/Loki observability."
- What's missing: No mention of rooms, stages, or P7. The opening frame is a flat service inventory, not the rooms-on-a-stage topology.

**Gap B — "Rooms on a Stage" section (L62-64)**
- Current: "PMOVES organizes its platform as rooms on a stage — each room is an agent-owned workspace with bound services, skills, and notebook state."
- What's missing: No P7 stage manager role. No stage states (rehearsal, live, review, archive). No room type vocabulary (foyer, review-room, voice-room, media-room, war-room). No suits concept. Reads like a folder listing, not a topology model.

**Gap C — Room index entries (L68-126)**
- Current: Rooms described as service inventories ("Infrastructure room for topology, service health, secrets discipline").
- What's missing: No stage context. No indication of which stage each room is typically in. No P7 as the entry mechanism.

**Gap D — Dashboards section (L146-168)**
- Current: "By Room" subheadings list URLs per room.
- What's missing: No stage banner concept. No indication that rooms transition between states.

### 2.2 `CLAUDE.md`

**Gap E — Entire file (L1-473)**
- Current: This is a pure Pinokio launcher development guide ("Development Guide for Pinokio Projects"). It contains zero PMOVES architecture content, zero rooms/stage language, and zero P7 references.
- What's missing: This file is the first thing Claude Code reads when entering the repo. It should contain a PMOVES architecture summary including the rooms-on-a-stage model and P7's role. The Pinokio launcher guide should either be moved to a dedicated file or reduced to a brief section with a pointer.

### 2.3 `AGENTS.md`

**Gap F — Project Structure section (L1-15)**
- Current: "PMOVES.AI is a modular AI agent platform organized as a submodule monorepo."
- What's missing: No rooms/stage topology frame. No mention of P7 or room catalog.

**Gap G — Canonical Documentation table (L17-34)**
- Current: Lists 15 documentation references. None point to rooms-on-a-stage model docs.
- What's missing: ROOM_MANIFEST_CONTRACT.md, AGNOTE4482.md (P7 section), AGNOTE_P7_PLAYGROUND.md (prospectus frame) are all missing from the canonical docs table.

### 2.4 `PMOVES-Archon/CLAUDE.md`

**Gap H — PMOVES.AI Skill Hints section (L350-356)**
- Current: Lists skills, context files, domain tags. Domain tags: `orchestration`, `agents`, `mcp`, `chit`.
- What's missing: No `rooms` or `stage` domain tag. No reference to which room Archon belongs to (4090 Field Control Room). No indication that Archon operates within a room context.

### 2.5 `PMOVES-Archon/README.md`

**Gap I — Entire file (L1-517)**
- Current: Pure upstream Archon README ("Archon is the command center for AI coding assistants").
- What's missing: No PMOVES overlay section explaining Archon's role within the rooms-on-a-stage model. No mention of which room it belongs to, how P7 launches it, or how it fits the stage lifecycle.

### 2.6 `PMOVES-Archon/AGENTS.md`

**Gap J — Entire file (L1-302)**
- Current: Duplicate of CLAUDE.md content (upstream Archon dev guide, older version without PMOVES skill hints).
- What's missing: Same as Gap H. Additionally, this file should not be a stale duplicate — it should either be updated to match CLAUDE.md or replaced with a symlink.

### 2.7 `PMOVES-BotZ-gateway/README.md`

**Gap K — Entire file (L1-613)**
- Current: Pure upstream Microsoft MCP Gateway README.
- What's missing: No PMOVES overlay section. No mention of BotZ's role in the rooms model (skills marketplace within voice/media rooms), P7 integration, or stage lifecycle.

### 2.8 `docs/PMOVES.md`

**Gap L — Opening framing (L1-10)**
- Current: "Central Brain (Primary Orchestration): Agent Zero acts as the core decision-maker... Support Systems: Archon serves as the specialized agent builder... Specialized AI Muscles: LangExtract, HiRAG..."
- What's missing: This is the old "Central Brain / Support Systems / Muscles" framing from pre-rooms-on-a-stage era. No rooms, no stages, no P7, no suits. This file is the most stale framing in the repo.

### 2.9 `docs/PMOVES_ARC.md`

**Gap M — Opening framing (L1-10)**
- Current: Same "Central Brain" framing as docs/PMOVES.md with Mermaid diagrams.
- What's missing: Same as Gap L. The architecture diagram itself uses the old three-layer model.

### 2.10 `pmoves/docs/` landing pages

**Gap N — No rooms-on-a-stage model overview exists**
- Current: ROOM_MANIFEST_CONTRACT.md defines the interface but assumes the reader already knows the model. NEXT_STEPS.md references "room/stage prospectus" as a section header but doesn't explain it. README_DOCS_INDEX.md does not list a rooms-on-a-stage overview document.
- What's missing: A dedicated `pmoves/docs/ROOMS_ON_A_STAGE.md` that explains the model end-to-end for new contributors — rooms, stages, suits, P7's role, and how to navigate the room catalog.

---

## 3. Proposed Language

### 3.1 `README.md` — Opening paragraph (replace L9)

**Replace:**
```
A local-first, multi-agent orchestration platform that coordinates autonomous agents (Agent Zero, Archon), hybrid retrieval (Hi-RAG v2), voice synthesis, media processing, and knowledge graphs — all wired together with NATS event-driven messaging and full Prometheus/Grafana/Loki observability.
```

**With:**
```
A local-first, multi-agent orchestration platform built on a rooms-on-a-stage model. P7 (Pinokio 7) is the room-aware stage manager that selects rooms, loads suits, and manages stage transitions (rehearsal, live, review, archive). Each room is an agent-owned workspace with bound services, skills, and notebook state — wired together with NATS event-driven messaging and full Prometheus/Grafana/Loki observability.
```

### 3.2 `README.md` — "Rooms on a Stage" section (replace L62-64)

**Replace:**
```
## Rooms on a Stage

PMOVES organizes its platform as **rooms on a stage** — each room is an agent-owned workspace with bound services, skills, and notebook state. Rooms own presentation and session ergonomics; the notebook plane owns durable memory. The [Room Manifest Contract](pmoves/docs/ROOM_MANIFEST_CONTRACT.md) defines the interface; [`pmoves/config/rooms/catalog.json`](pmoves/config/rooms/catalog.json) is the canonical seed catalog.
```

**With:**
```
## Rooms on a Stage

PMOVES organizes its platform as **rooms on a stage** — a topology model with three layers:

- **Rooms** are the audience-facing entrypoints: foyer, review-room, voice-room, media-room, war-room. Each room is an agent-owned workspace with bound services, skills, and notebook state.
- **Stage** is the state model for each room: `rehearsal` (setup and testing), `live` (active operation), `review` (audit and approval), `archive` (completed or dormant).
- **Suits** are the runtime/persona bindings layered onto rooms — upstream Agent Zero as the external baseline, PMOVES hardened overlays as the custom fit, voice/theme/persona as the visible styling layer.

**P7 (Pinokio 7)** is the room-aware stage manager: it knows which rooms exist, selects the appropriate room profile for a given workload, loads the correct suit, and manages stage transitions. P7's NATS subjects (`p7.nats.launch`, `p7.nats.session`) are the control plane for room entry and lifecycle.

Rooms own presentation and session ergonomics; the notebook plane owns durable memory. The [Room Manifest Contract](pmoves/docs/ROOM_MANIFEST_CONTRACT.md) defines the interface; [`pmoves/config/rooms/catalog.json`](pmoves/config/rooms/catalog.json) is the canonical seed catalog.

See [AGNOTE4482](pmoves/docs/AGENTS/AGNOTE4482.md) for the full P7 specification and [Rooms on a Stage Overview](pmoves/docs/ROOMS_ON_A_STAGE.md) for the end-to-end model description.
```

### 3.3 `README.md` — Room index entries (add stage context to each room header)

**For each room entry, add a `Stage` line after the `Profile` line.** Example for Z890:

**Replace:**
```
#### Z890 Infra Fabric Room
**Purpose:** Infrastructure room for topology, service health, secrets discipline, and operator bring-up.
**Profile:** `z890-infra` · **Agent:** `z890-claude` · **Manifest:** [`z890-infra.room.fabric.json`](pmoves/config/rooms/z890-infra.room.fabric.json)
```

**With:**
```
#### Z890 Infra Fabric Room
**Purpose:** Infrastructure room for topology, service health, secrets discipline, and operator bring-up.
**Profile:** `z890-infra` · **Agent:** `z890-claude` · **Stage:** `live` · **Manifest:** [`z890-infra.room.fabric.json`](pmoves/config/rooms/z890-infra.room.fabric.json)
```

Apply the same pattern to all four rooms (4090: `live`, 5090 Voice: `live`, 5090 KiloCode: `rehearsal` — adjust per actual state).

### 3.4 `CLAUDE.md` — Add PMOVES architecture header (insert before L1)

**Insert at the very top of the file, before the existing Pinokio guide:**

```
# PMOVES.AI Architecture Context

PMOVES.AI is built on a **rooms-on-a-stage** model:
- **P7 (Pinokio 7)** is the room-aware stage manager — it selects rooms, loads suits, and manages stage transitions (rehearsal, live, review, archive).
- **Rooms** are agent-owned workspaces (infra, field control, voice studio, workstation) defined in `pmoves/config/rooms/catalog.json`.
- **Suits** are runtime/persona bindings (Agent Zero, ClaWZ, voice personas) layered onto rooms.
- **Stage** is the lifecycle state per room: `rehearsal` -> `live` -> `review` -> `archive`.

Key references:
- [Room Manifest Contract](pmoves/docs/ROOM_MANIFEST_CONTRACT.md) — room interface specification
- [AGNOTE4482](pmoves/docs/AGENTS/AGNOTE4482.md) — P7 stage manager definition
- [Rooms on a Stage Overview](pmoves/docs/ROOMS_ON_A_STAGE.md) — end-to-end model
- [Roadmap](pmoves/docs/ROADMAP.md) — prospectus and wave planning

---

# Pinokio Launcher Development Guide

> The section below governs Pinokio launcher development. For PMOVES platform architecture, see above.
```

### 3.5 `AGENTS.md` — Update Project Structure (replace L1-15)

**Replace:**
```
## Project Structure

PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**.

- **`pmoves/`** — Core platform: Makefile, docker-compose, configs, services, tools, tests, docs
- **`PMOVES-*/`** — Git submodules (Agent-Zero, Archon, ClaWZ, Creator, HiRAG, YT, supabase, etc.)
- **`pmoves/config/`** — Agent registry (`agent_registry.yaml`), model configs, TAC trees
- **`pmoves/docs/`** — Documentation (agents, operations, services, plans, security)
- **`pmoves/services/`** — Service forks and local service code
- **`pmoves/tests/`** — Unit, smoke, integration, and hardening tests
- **`deploy/`** — Deployment configs (sidecar, K8s, cloudflare, provision)
- **`.claude/`** — Claude Code context, commands, hooks, MCP config
- **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
```

**With:**
```
## Project Structure

PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**, built on a rooms-on-a-stage topology. P7 (Pinokio 7) is the room-aware stage manager that selects rooms and manages stage transitions.

- **`pmoves/config/rooms/`** — Room catalog (`catalog.json`) and per-room manifest files — the canonical room topology
- **`pmoves/`** — Core platform: Makefile, docker-compose, configs, services, tools, tests, docs
- **`PMOVES-*/`** — Git submodules (Agent-Zero, Archon, ClaWZ, Creator, HiRAG, YT, supabase, etc.)
- **`pmoves/config/`** — Agent registry (`agent_registry.yaml`), model configs, TAC trees
- **`pmoves/docs/`** — Documentation (agents, operations, services, plans, security)
- **`pmoves/services/`** — Service forks and local service code
- **`pmoves/tests/`** — Unit, smoke, integration, and hardening tests
- **`deploy/`** — Deployment configs (sidecar, K8s, cloudflare, provision)
- **`.claude/`** — Claude Code context, commands, hooks, MCP config
- **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`
```

### 3.6 `AGENTS.md` — Add rooms-on-a-stage rows to Canonical Documentation table

**Add after the existing table rows (after L34, before L36):**

```
| **Rooms on a Stage** | `pmoves/docs/ROOMS_ON_A_STAGE.md` — end-to-end model: rooms, stages, suits, P7 role |
| **Room Manifest Contract** | `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — room/notebook interface specification |
| **P7 Stage Manager** | `pmoves/docs/AGENTS/AGNOTE4482.md` — P7 room-aware stage manager definition |
| **Room/Stage Prospectus** | `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md` — prospectus frame, foyer/war-room/voice-room model |
| **Room/Stage Roadmap** | `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` — W1-W5 prospectus alignment |
```

### 3.7 `PMOVES-Archon/CLAUDE.md` — Update PMOVES.AI Skill Hints (replace L350-356)

**Replace:**
```
<!-- PMOVES.AI-CONTEXT-TAGS -->
## PMOVES.AI Skill Hints

**Primary Skills:** `/agents:status`, `/agents:mcp-query`, `/deploy:up`, `/deploy:services`, `/health:quick`, `/botz:profile`
**Context Files:** `mcp-api.md`, `nats-subjects.md`, `services-catalog.md`, `geometry-nats-subjects.md`
**Domain Tags:** `orchestration`, `agents`, `mcp`, `chit`
**Context Tier:** 2 (On-Demand (Major Subsystem))
<!-- /PMOVES.AI-CONTEXT-TAGS -->
```

**With:**
```
<!-- PMOVES.AI-CONTEXT-TAGS -->
## PMOVES.AI Skill Hints

**Room Assignment:** Archon operates within the **4090 Field Control Room** — the review/triage workspace. P7 launches Archon into this room context.
**Primary Skills:** `/agents:status`, `/agents:mcp-query`, `/deploy:up`, `/deploy:services`, `/health:quick`, `/botz:profile`
**Context Files:** `mcp-api.md`, `nats-subjects.md`, `services-catalog.md`, `geometry-nats-subjects.md`
**Domain Tags:** `orchestration`, `agents`, `mcp`, `chit`, `rooms`, `stage`
**Context Tier:** 2 (On-Demand (Major Subsystem))
<!-- /PMOVES.AI-CONTEXT-TAGS -->
```

### 3.8 `PMOVES-Archon/README.md` — Add PMOVES integration section (append before License section, before L513)

**Insert before "## License":**

```
## PMOVES.AI Integration

Archon is deployed within the PMOVES.AI rooms-on-a-stage model as a core service of the **4090 Field Control Room**. In this context:

- **P7 (Pinokio 7)** launches Archon as part of the Field Control Room's service bundle.
- **Room context**: Archon provides knowledge management, task tracking, and MCP tool serving for the review/triage workflow.
- **Stage lifecycle**: Archon transitions through `rehearsal` (development), `live` (active agent use), `review` (audit), and `archive` (completed work orders) alongside the room.
- **CHIT integration**: Archon is a CHIT-aware form consumer — it receives CGP packets via Agent Zero's MCP interface.

See [PMOVES.AI Room Manifest Contract](../pmoves/docs/ROOM_MANIFEST_CONTRACT.md) for the room interface specification.
```

### 3.9 `PMOVES-Archon/AGENTS.md` — Sync with CLAUDE.md

**Action**: Replace the entire content of `PMOVES-Archon/AGENTS.md` with the content of `PMOVES-Archon/CLAUDE.md` (which includes the PMOVES skill hints from 3.7). The current AGENTS.md is a stale duplicate missing the PMOVES context tags.

### 3.10 `PMOVES-BotZ-gateway/README.md` — Add PMOVES integration section (append before Contributing section, before L592)

**Insert before "## Contributing":**

```
## PMOVES.AI Integration

The MCP Gateway is deployed within PMOVES.AI as a skills routing layer, primarily serving the **5090 Voice Studio** and **4090 Field Control Room**. In this context:

- **P7 (Pinokio 7)** manages the gateway's lifecycle as part of room service bundles.
- **Room context**: BotZ provides dynamic tool registration and session-aware routing for MCP tools across rooms.
- **Stage lifecycle**: The gateway follows room stage transitions — tools are registered during `rehearsal`, available during `live`, audited during `review`.
- **Skills marketplace**: BotZ enables agents to discover and invoke skills registered from any room in the topology.

See [PMOVES.AI Room Manifest Contract](../pmoves/docs/ROOM_MANIFEST_CONTRACT.md) for the room interface specification.
```

### 3.11 `docs/PMOVES.md` — Add rooms-on-a-stage framing note (insert at top, before L1)

**Insert at the very top:**

```
> **Note**: This document uses the original "Central Brain / Support Systems / Muscles" framing. PMOVES.AI has since adopted the **rooms-on-a-stage** model where P7 (Pinokio 7) is the room-aware stage manager, services are organized into rooms (infra, field control, voice studio, workstation), and each room transitions through stage states (rehearsal, live, review, archive). For the current architecture, see [Rooms on a Stage Overview](../pmoves/docs/ROOMS_ON_A_STAGE.md) and [Room Manifest Contract](../pmoves/docs/ROOM_MANIFEST_CONTRACT.md). The content below is retained for historical reference.

---
```

### 3.12 `docs/PMOVES_ARC.md` — Add rooms-on-a-stage framing note (insert at top, before L1)

**Insert at the very top:**

```
> **Note**: The architecture diagrams below use the original three-layer model (Central Brain / Support Systems / Muscles). PMOVES.AI now uses the **rooms-on-a-stage** topology where services are organized into rooms with P7 as the stage manager. For the current architecture, see [Rooms on a Stage Overview](../pmoves/docs/ROOMS_ON_A_STAGE.md). The diagrams below are retained for historical reference.

---
```

### 3.13 `pmoves/docs/ROOMS_ON_A_STAGE.md` — New file (create)

**Create this file:**

```
# Rooms on a Stage — Model Overview
_Last updated: 2026-05-02_

## What This Is

PMOVES.AI organizes its platform as rooms on a stage — a topology model with three layers: rooms, stages, and suits. This document explains the model end-to-end.

## The Three Layers

### Rooms (audience-facing topology)

Rooms are the entrypoints through which users (human or agent) access the platform's capabilities. Each room is an agent-owned workspace with bound services, skills, and notebook state.

| Room | Purpose | Agent | Typical Stage |
|------|---------|-------|--------------|
| **Z890 Infra Fabric** | Topology, service health, secrets, operator bring-up | z890-claude | live |
| **4090 Field Control** | Review, triage, notebook-backed analysis | 4090-claude | live |
| **5090 Voice Studio** | TTS, media pipelines, audition workflows | 5090-claude | live |
| **5090 KiloCode GLM Workstation** | GPU inference specialist, GLM Coding Plan | 5090-kilocode | rehearsal |

Planned rooms (from the prospectus frame):
- **foyer** — first P7 screen, room selection
- **review-room** — Graphiti trails, notebooks, approval state
- **voice-room** — Flute/TTS/Pipecat as instrument rack
- **media-room** — beats, Jellyfin, creator publishing, Discord cards
- **war-room** — enterprise, fleet, Hostinger/KVM posture

### Stage (lifecycle state model)

Every room has a stage state that describes its current lifecycle position:

| Stage | Meaning |
|-------|---------|
| `rehearsal` | Setup, testing, configuration — not yet serving production work |
| `live` | Active operation — serving real workloads |
| `review` | Audit, approval, inspection — paused for evaluation |
| `archive` | Completed or dormant — preserved but inactive |

Stage transitions are managed by P7. A room in `rehearsal` should show a rehearsal banner; a room in `live` should show a live indicator.

### Suits (runtime/persona bindings)

Suits are layered onto rooms — they are NOT the platform itself, they are the visible styling and runtime binding:

- **Base suit**: upstream Agent Zero (external baseline)
- **Custom suit**: PMOVES hardened overlays (security, CHIT, NATS wiring)
- **Styling suit**: voice, theme, persona (visible layer)

A room can switch suits without changing rooms. Suit selection is profile-governed, not raw-env governed.

## P7 — The Stage Manager

P7 (Pinokio 7) is the room-aware stage manager. It:
1. Knows which rooms exist (via `pmoves/config/rooms/catalog.json`)
2. Selects the appropriate room profile for a given workload
3. Loads the correct suit for the room
4. Manages stage transitions (rehearsal -> live -> review -> archive)
5. Provides NATS control plane subjects (`p7.nats.launch`, `p7.nats.session`) for room entry and lifecycle

P7 is not just a process spawner — it is the context that agents launch into.

## What Rooms Own vs. Don't Own

Rooms own:
- Shell theme and layout
- Installed apps and default routes
- Room-local policy decisions
- Bindings between skills and surfaces

Rooms do NOT own:
- Durable memory (that's the notebook plane)
- Cross-room infrastructure (that's the geometry/CHIT fabric)
- Orchestration data planes (that's NATS/observability)

## References

- [Room Manifest Contract](ROOM_MANIFEST_CONTRACT.md) — interface specification
- [AGNOTE4482](AGENTS/AGNOTE4482.md) — P7 stage manager definition (L25-27)
- [P7 Playground — Prospectus Frame](AGENTS/AGNOTE_P7_PLAYGROUND.md) — rooms/stage/suits model (L338-368)
- [Roadmap W1-W5](AGENTS/AGNOTE4482_ROADMAP_W1-W5.md) — prospectus alignment
- [Signoff Checklist](AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) — 1.4 coherence gate
- [CnC Architecture](architecture/PMOVES_CnC.md) — P7 as stage manager in command-and-control context
```

### 3.14 Discord channel descriptions — rooms-on-a-stage alignment (optional, operator decision)

**Note**: The current deployed Discord descriptions (from S14_DRAFTS.md) use MOF/crystalline lattice language. If the operator wants Discord to also reflect rooms-on-a-stage, the following channel description updates are proposed. This is a **separate decision** from the site/docs alignment — MOF language and rooms-on-a-stage language can coexist if intentional (MOF = structural isomorphism, rooms = operational topology).

If rooms-on-a-stage is desired for Discord:

**#general**: `PMOVES.AI — rooms on a stage. P7 is the stage manager. Agents enter rooms, wear suits, and transition through rehearsal, live, review, archive. The crystalline lattice is the structure; the stage is how you experience it.`

**Decision required from operator**: Keep MOF-frame for Discord, add rooms-on-a-stage overlay, or replace?

---

## 4. Priority Order

### P0 — Immediate (unblocks 1.4 signoff)

| # | File | Change | Effort |
|---|------|--------|--------|
| 1 | `README.md` | Replace opening paragraph (3.1) + rewrite Rooms on a Stage section (3.2) + add stage to room index (3.3) | 15 min |
| 2 | `CLAUDE.md` | Add PMOVES architecture header (3.4) | 5 min |
| 3 | `AGENTS.md` | Update Project Structure (3.5) + add rooms rows to canonical docs table (3.6) | 10 min |

### P1 — High (submodule docs that agents read)

| # | File | Change | Effort |
|---|------|--------|--------|
| 4 | `PMOVES-Archon/CLAUDE.md` | Update PMOVES skill hints (3.7) | 5 min |
| 5 | `PMOVES-Archon/README.md` | Add PMOVES integration section (3.8) | 10 min |
| 6 | `PMOVES-Archon/AGENTS.md` | Sync with CLAUDE.md (3.9) | 5 min |
| 7 | `PMOVES-BotZ-gateway/README.md` | Add PMOVES integration section (3.10) | 10 min |
| 8 | `pmoves/docs/ROOMS_ON_A_STAGE.md` | Create new overview doc (3.13) | 20 min |

### P2 — Cleanup (stale framing, historical docs)

| # | File | Change | Effort |
|---|------|--------|--------|
| 9 | `docs/PMOVES.md` | Add rooms-on-a-stage framing note (3.11) | 5 min |
| 10 | `docs/PMOVES_ARC.md` | Add rooms-on-a-stage framing note (3.12) | 5 min |
| 11 | Discord descriptions | Operator decision on MOF vs rooms-on-a-stage (3.14) | 15 min |

### Total estimated effort: ~105 minutes

---

## Appendix: File-by-File Change Summary

| File | Gaps Addressed | Proposed Sections |
|------|---------------|------------------|
| `README.md` | A, B, C, D | 3.1, 3.2, 3.3 |
| `CLAUDE.md` | E | 3.4 |
| `AGENTS.md` | F, G | 3.5, 3.6 |
| `PMOVES-Archon/CLAUDE.md` | H | 3.7 |
| `PMOVES-Archon/README.md` | I | 3.8 |
| `PMOVES-Archon/AGENTS.md` | J | 3.9 |
| `PMOVES-BotZ-gateway/README.md` | K | 3.10 |
| `docs/PMOVES.md` | L | 3.11 |
| `docs/PMOVES_ARC.md` | M | 3.12 |
| `pmoves/docs/ROOMS_ON_A_STAGE.md` (new) | N | 3.13 |
| Discord descriptions (decision) | — | 3.14 |

## Appendix: Pre-Existing Aligned Language (no changes needed)

These files already use rooms-on-a-stage vocabulary correctly and need no modification:

- `pmoves/docs/AGENTS/AGNOTE4482.md` — P7 room-aware stage manager definition
- `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md` — Prospectus frame (rooms, stage, suits)
- `pmoves/docs/AGENTS/AGNOTE4482_ROADMAP_W1-W5.md` — Prospectus implications
- `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md` — Coherence checks
- `pmoves/docs/AGENTS/AGNOTE4482_CLAWZ_CODING_PLAN_ALIGNMENT.md` — P7 stage manager reference
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — Full contract (rooms as audience-facing topology, stage field)
- `pmoves/docs/architecture/PMOVES_CnC.md` — P7 stage manager in CnC context
- `deploy/HYBRID_RUNNER_STRATEGY.md` — P7 stage manager in runner context
- `research/LONGBOW_COMPARATIVE_ANALYSIS.md` — Rooms-on-a-stage in comparative analysis
- `research/SIDECAR_PROMOTION_PLAN.md` — P7 stage manager in sidecar context

## Appendix: Signoff Checklist Update

Once all P0 changes are applied, update AGNOTE4482_SIGNOFF_CHECKLIST.md L31:

**Replace:**
```
- [ ] P7, Discord, and site/docs language point at the same frame. <!-- FAIL: ROADMAP and NEXT_STEPS explicitly state this alignment has NOT happened yet. Requires Discord channel descriptions + site updates (SIDECAR-SPARK research 2026-04-23). -->
```

**With:**
```
- [ ] P7, Discord, and site/docs language point at the same frame. <!-- PARTIAL: README.md, CLAUDE.md, AGENTS.md, Archon/BotZ submodule docs updated 2026-05-02 with rooms-on-a-stage vocabulary. Discord descriptions still use MOF-frame (operator decision pending — see plans/P7_SITE_DOCS_ALIGNMENT_DRAFT.md 3.14). -->
```

Full pass requires operator decision on Discord MOF vs rooms-on-a-stage framing.