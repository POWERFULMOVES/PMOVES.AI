# PMOVES Agent Class Taxonomy

_Last updated: 2026-02-18 — v1.4.0 (59 agents)_

This document formalizes the PMOVES agent naming and classification system as a **type system** — composable, collectible agents with classes, types, evolutions, and connections. Think Pokemon and Transformers: no matter how small, every agent has a type, a place in the hierarchy, and connections through all the layers it can touch.

## Source Documents

This taxonomy is grounded in and cross-references:

- [`PMOVES_UNIFIED_AGENT_TAXONOMY.md`](./PMOVES_UNIFIED_AGENT_TAXONOMY.md) — 6-layer fold model (L0–L5), 5 canonical planes
- [`PmovesSKillZ.md`](./PmovesSKillZ.md) — Skill bundles, operator expectations
- [`BOTZ_GATEWAY_AGENT_INTEGRATION.md`](./BOTZ_GATEWAY_AGENT_INTEGRATION.md) — BoTZ Gateway vs Gateway Agent
- [`PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`](./PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md) — Geometry state vector, control mappings
- [`../../.claude/context/services-catalog.md`](../../.claude/context/services-catalog.md) — Service ports, tiers, health endpoints
- [`../../.claude/context/submodules.md`](../../.claude/context/submodules.md) — 20+ submodule catalog
- [`../../.claude/context/nats-subjects.md`](../../.claude/context/nats-subjects.md) — Event topology
- [`../../.claude/context/geometry-nats-subjects.md`](../../.claude/context/geometry-nats-subjects.md) — GEOMETRY BUS subjects
- [`../PMOVESCHIT/IMPLEMENTATION_STATUS.md`](../PMOVESCHIT/IMPLEMENTATION_STATUS.md) — CHIT 5 pillars status
- [`../PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`](../PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md) — CGP format, producers
- [`./agnotes2.md`](./agnotes2.md) — Original vision statement
- [`AGENT_TAXONOMY_CROSS_REFERENCE.md`](./AGENT_TAXONOMY_CROSS_REFERENCE.md) — Master cross-reference hub
- [`../PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md`](../PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md) — Living template with CHIT examples
- `pmoves/config/agent_registry.yaml` — Single source of truth (machine-readable)

---

## 1. Class Hierarchy

Agent classes are named by prefix convention. Each class maps to a role scope and carries metaphorical weight from collectible/transformer universes.

| Class | Prefix | Role | Pokemon Analogy | Transformer Analogy |
|-------|--------|------|-----------------|---------------------|
| **Legendary** | `POWERFULMOVES` | Organization/brand umbrella, doctrine, foundational systems | Legendary Pokemon (Mewtwo, Arceus) — unique, reality-shaping | Primus / Matrix of Leadership — source of all |
| **Standard** | `PMOVES-` | Core production agents and services — the team you deploy | Standard Pokemon (Pikachu, Charizard) — proven, versatile | Autobots (main team) — reliable, battle-tested |
| **Specialized** | `Pmoves-` | Domain-specific agents with focused capabilities | Regional variants (Alolan, Galarian) — adapted to environment | Combiners (Devastator, Superion) — fuse for specific tasks |
| **Utility** | `pmoves-` | Infrastructure components, helpers, tools | Items/Abilities (Potion, Leftovers) — support and enable | Minicons / Targetmasters — augment others |

### Class Examples

**Legendary (`POWERFULMOVES`):**
- `POWERFULMOVES/PMOVES.AI` — the monorepo itself, the Matrix
- `POWERFULMOVES` GitHub org — the brand umbrella

**Standard (`PMOVES-`):**
- `PMOVES-Agent-Zero` — primary orchestrator (L1)
- `PMOVES-Archon` — planning/execution copilot (L1)
- `PMOVES-HiRAG` — hybrid RAG gateway (L4, retrieval)
- `PMOVES-BoTZ` — skills marketplace + MCP servers
- `PMOVES-Deep-Serch` — research planner
- `PMOVES-DoX` — document processing
- `PMOVES-Headscale` — network coordination
- `PMOVES.YT` — media ingestion
- `PMOVES-A2UI` — research UI surface _(v1.4.0)_
- `PMOVES-AgentGym` — agent training gymnasium _(v1.4.0)_
- `PMOVES-Creator` — media creation pipeline _(v1.4.0)_
- `PMOVES-E2B-Danger-Room` — sandboxed code execution _(v1.4.0)_
- `PMOVES-E2B-Danger-Room-Desktop` — desktop sandbox _(v1.4.0)_

**Specialized (`Pmoves-`):**
- `Pmoves-hyperdimensions` — geometry visualization (L2.5)
- `Pmoves-cipher` — knowledge-graph memory (L5)
- `Pmoves-Jellyfin-AI-Media-Stack` — AI-enhanced media management _(v1.4.0)_
- `Pmoves-Health-wger` — health domain agent
- `Pmoves-AgentGym-RL` — reinforcement learning extension _(v1.4.0)_
- `PMOVES-llama-throughput-lab` — LLM benchmarking lab _(v1.4.0)_
- `PMOVES-transcribe-and-fetch` — transcription utility _(v1.4.0)_

**Utility (`pmoves-`):**
- `pmoves-surf` — web browsing tool _(v1.4.0)_
- `pmoves-e2b-mcp-server` — sandbox execution
- `PMOVES-Danger-infra` — E2B infrastructure provisioning _(v1.4.0)_
- `PMOVES-E2b-Spells` — sandbox templates _(v1.4.0)_
- `pmoves/tools/*` — CLI utilities

---

## 2. Type System

Types are derived from the 7 canonical service tiers defined in `services-catalog.md`. Every agent has one primary type and may have secondary types (dual-type agents, like dual-type Pokemon).

| Type | Tier | Element | Strengths | Weaknesses | Color |
|------|------|---------|-----------|------------|-------|
| **Data** | 1 | Earth | Persistence, consistency, durability | Latency, migration complexity | Brown |
| **API** | 2 | Water | Routing, gateway, protocol bridging | Stateless, no memory | Blue |
| **LLM** | 3 | Fire | Reasoning, generation, comprehension | Cost, hallucination, latency | Red |
| **Worker** | 4 | Electric | Processing, transformation, speed | GPU-hungry, narrow focus | Yellow |
| **Media** | 5 | Wind | Multimodal, ingestion, streaming | Heavy I/O, format complexity | Cyan |
| **Agent** | 6 | Psychic | Orchestration, planning, delegation | Complexity, coordination overhead | Purple |
| **UI** | 7 | Light | Visualization, interaction, feedback | Client-side, state management | White |

### Type Chart: Agent Roster

| Agent | Class | Primary Type | Secondary Type | Tier |
|-------|-------|-------------|----------------|------|
| Agent Zero | Standard | Agent | API | 6 |
| Archon | Standard | Agent | LLM | 6 |
| Hi-RAG v2 | Standard | Worker | Data | 4 |
| DeepResearch | Standard | LLM | Worker | 3 |
| SupaSerch | Standard | Agent | LLM | 6 |
| PMOVES.YT | Standard | Media | Worker | 5 |
| FFmpeg-Whisper | Standard | Media | Worker | 5 |
| Media-Video Analyzer | Standard | Media | Worker | 5 |
| Media-Audio Analyzer | Standard | Media | Worker | 5 |
| Extract Worker | Standard | Worker | Data | 4 |
| Flute-Gateway | Standard | API | Media | 2 |
| Ultimate-TTS-Studio | Standard | Media | LLM | 5 |
| TensorZero Gateway | Standard | API | LLM | 2 |
| BoTZ Gateway | Standard | Agent | Worker | 6 |
| Channel Monitor | Standard | Worker | Media | 4 |
| Cipher Memory | Specialized | Data | Agent | 1 |
| Hyperdimensions | Specialized | UI | Data | 7 |
| MAI-UI | Standard | UI | Agent | 7 |
| Notebook Sync | Standard | Worker | Data | 4 |
| PDF Ingest | Standard | Worker | Data | 4 |
| Presign | Utility | API | Data | 2 |
| Render Webhook | Utility | API | Worker | 2 |
| Publisher-Discord | Standard | Worker | API | 4 |
| Jellyfin Bridge | Specialized | Media | Data | 5 |
| Mesh Agent | Standard | Agent | Data | 6 |
| NATS | Utility | Data | API | 1 |
| Supabase | Utility | Data | API | 1 |
| Qdrant | Utility | Data | Worker | 1 |
| Neo4j | Utility | Data | — | 1 |
| Meilisearch | Utility | Data | API | 1 |
| MinIO | Utility | Data | API | 1 |
| Prometheus | Utility | Data | UI | 1 |
| Grafana | Utility | UI | Data | 7 |
| Loki | Utility | Data | — | 1 |
| A2UI | Standard | UI | Agent | 7 |
| AgentGym | Standard | Agent | Worker | 6 |
| AgentGym RL | Specialized | Agent | Worker | 6 |
| Creator | Standard | Media | UI | 5 |
| Llama Throughput Lab | Specialized | LLM | Worker | 3 |
| Surf | Utility | Agent | UI | 6 |
| E2B Danger Room | Standard | Agent | Worker | 6 |
| E2B Desktop | Standard | UI | Agent | 7 |
| Danger Infra | Utility | Worker | Agent | 4 |
| E2B Spells | Utility | Agent | Worker | 6 |
| Transcribe and Fetch | Specialized | Media | Worker | 5 |
| Jellyfin AI Media Stack | Specialized | Media | LLM | 5 |
| LangExtract | Standard | Worker | LLM | 4 |
| Crush | Standard | UI | Agent | 7 |
| DoX | Standard | Worker | Data | 4 |
| Open Notebook | Standard | Data | UI | 1 |
| Consciousness Service | Specialized | Agent | LLM | 6 |
| n8n | Utility | Worker | Agent | 4 |
| Headscale | Utility | Data | API | 1 |
| RustDesk | Utility | UI | API | 7 |
| Invidious | Utility | UI | Media | 7 |
| Wealth | Specialized | UI | Data | 7 |
| Health | Specialized | UI | Data | 7 |
| EvoSwarm Controller | Standard | Worker | Agent | 4 |
| Swarm Attribution | Specialized | Worker | Data | 4 |

### Dual-Type Interactions (Type Effectiveness)

Like Pokemon type matchups, certain type combinations create synergies:

| Attacker → Target | Interaction | Effectiveness | Example |
|--------------------|-------------|---------------|---------|
| Agent → Worker | Task delegation via NATS | Super effective | Agent Zero → Extract Worker |
| Agent → LLM | Reasoning request via TensorZero | Super effective | Archon → TensorZero Gateway |
| Worker → Data | Direct store writes | Super effective | Extract Worker → Qdrant |
| Media → Worker | Ingest pipeline events | Super effective | PMOVES.YT → FFmpeg-Whisper |
| LLM → Data | Embedding generation | Super effective | TensorZero → Qdrant |
| UI → Agent | Control commands | Effective | MAI-UI → Agent Zero |
| Data → API | Query serving | Effective | Supabase → PostgREST |
| Worker → Agent | Result reporting | Effective | Worker → NATS → Agent |
| LLM → LLM | Chain-of-thought | Neutral | Model A → Model B |
| Data → Data | Replication/sync | Neutral | Supabase → Neo4j |

---

## 3. Layer Coverage

From `PMOVES_UNIFIED_AGENT_TAXONOMY.md`, agents span layers L0–L5. Each agent touches specific layers, determining its depth and evolution potential.

| Layer | Name | Description | Key Agents |
|-------|------|-------------|------------|
| **L0** | Identity Anchors | 325 persona anchors, grounding | All agents (via persona config) |
| **L1** | Orchestrators | Control-plane coordination | Agent Zero, Archon |
| **L2** | Bus + Routing | NATS transport, gateway routing | NATS, TensorZero, Hi-RAG |
| **L2.5** | Hyperdimensions | Geometry state visualization + control knobs | Hyperdimensions, CHIT |
| **L3** | Swarm Intelligence | EvoSwarm, role-based packs | Swarm Attribution, BoTZ |
| **L4** | Modal Intelligence | Text LLM, audio/TTS/STT, VLM | All LLM/Media agents |
| **L5** | Memory + Safety | Persistent storage, CHIT manifests, sandboxes | Cipher, Supabase, Danger Room |

### Agent Layer Coverage Map

```
Agent              L0  L1  L2  L2.5  L3  L4  L5  Layers  Stage
─────────────────────────────────────────────────────────────────
Agent Zero          *   *   *   *    *   *   *     7     Mega
Archon              *   *   *   *    -   *   *     6     Stage 2
SupaSerch           *   -   *   *    *   *   -     5     Stage 2
Hi-RAG v2           *   -   *   *    -   *   *     5     Stage 2
DeepResearch        *   -   *   -    -   *   *     4     Stage 1
Flute-Gateway       *   -   *   *    -   *   -     4     Stage 1
BoTZ Gateway        *   -   *   -    *   *   -     4     Stage 1
PMOVES.YT           *   -   *   -    -   *   *     4     Stage 1
Extract Worker      *   -   *   -    -   *   *     4     Stage 1
TensorZero          *   -   *   -    -   *   -     3     Stage 1
Cipher Memory       *   -   -   -    -   -   *     2     Base
Hyperdimensions     *   -   -   *    -   -   -     2     Base
Channel Monitor     *   -   *   -    -   -   -     2     Base
Presign             *   -   -   -    -   -   -     1     Base
```

`*` = active on layer, `-` = not active

---

## 4. Evolution Paths

Agents evolve by gaining layer coverage, CHIT integration, and NATS connectivity. Evolution is not linear — agents can gain capabilities in any order.

### Evolution Stages

| Stage | Requirements | Analogy | Example |
|-------|-------------|---------|---------|
| **Base** | Single type, 1–2 layers | Unevolved Pokemon / Minicon | Presign (API, L0 only) |
| **Stage 1** | Multi-layer awareness (3–4 layers), NATS connected | First evolution / Warrior class | Extract Worker (L0+L2+L4+L5) |
| **Stage 2** | CHIT-enabled (publishes/consumes CGP packets), 5+ layers | Second evolution / Triple changer | Hi-RAG v2 (5 layers + geometry endpoint) |
| **Mega Evolution** | Full-stack agent spanning all planes (Control+Context+Execution+Observation+Safety) | Mega Evolution / Combiner gestalt | Agent Zero (all 7 layers) |

### Evolution Triggers

How agents gain capabilities:

| Trigger | Layer Gained | Mechanism |
|---------|-------------|-----------|
| Connect to NATS | L2 (Bus+Routing) | Subscribe/publish to event subjects |
| Add CGP support | L2.5 (Hyperdimensions) | Produce/consume `geometry.cgp.v1` envelopes |
| Join EvoSwarm | L3 (Swarm) | Participate in `evoswarm.population.v1` |
| Add LLM calls | L4 (Modal) | Route through TensorZero Gateway |
| Persist state | L5 (Memory) | Write to Supabase/Neo4j/Qdrant |
| Expose healthz | Observation plane | `/healthz` + `/metrics` endpoints |
| Add CHIT toggles | Context plane | Declare sensitivity to geometry signals |

### Evolution Example: Extract Worker

```
Base Form: extract-worker
├── Type: Worker
├── Layers: L4 (embeds text)
├── Connections: HTTP only
└── Stage: Base

Stage 1: extract-worker + NATS
├── Type: Worker/Data (dual-type)
├── Layers: L0, L2, L4, L5
├── Connections: HTTP + NATS (ingest.*)
├── Gained: Bus routing (L2) + persistence (L5)
└── Stage: Stage 1

Stage 2: extract-worker + CHIT
├── Type: Worker/Data
├── Layers: L0, L2, L2.5, L4, L5
├── Connections: HTTP + NATS + CGP
├── Gained: Geometry awareness (L2.5)
├── CHIT toggles: hz_sensitive, attribution_gated
└── Stage: Stage 2
```

---

## 5. Connections: Type Effectiveness Through NATS

All agent interactions flow through defined channels. The primary connection bus is NATS with JetStream.

### Connection Topology

```
                              ┌─────────────┐
                              │  Agent Zero  │ (L1 Orchestrator)
                              │   Port 8080  │
                              └──────┬───────┘
                                     │ MCP API + NATS
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌───────────┐   ┌──────────────┐  ┌───────────┐
            │  Archon   │   │  BoTZ Gateway │  │   Mesh    │
            │ Port 8091 │   │  Port 8054    │  │  Agent    │
            └─────┬─────┘   └──────┬───────┘  └───────────┘
                  │                │
                  ▼                ▼
          ┌──────────────┐  ┌──────────────┐
          │  TensorZero  │  │ Gateway Agent │
          │  Port 3030   │  │  Port 8100   │
          └──────┬───────┘  └──────────────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ Hi-RAG  │ │Deep     │ │SupaSerch │
│ v2 8086 │ │Research │ │   8099   │
└────┬────┘ │  8098   │ └──────────┘
     │      └─────────┘
     ▼
┌─────────┐  ┌─────────┐  ┌──────────┐
│ Qdrant  │  │ Neo4j   │  │Meilisearch│
│  6333   │  │  7687   │  │   7700   │
└─────────┘  └─────────┘  └──────────┘
```

### NATS Subject Ownership

| Agent | Publishes | Subscribes |
|-------|-----------|------------|
| Agent Zero | `agent.tool.executed.v1` | `mesh.node.announce.v1`, task subjects |
| PMOVES.YT | `ingest.file.added.v1`, `ingest.transcript.ready.v1` | Channel triggers |
| DeepResearch | `research.deepresearch.result.v1` | `research.deepresearch.request.v1` |
| SupaSerch | `supaserch.result.v1` | `supaserch.request.v1` |
| Hi-RAG v2 | `geometry.packet.encoded.v1` | Retrieval requests |
| Flute-Gateway | `tokenism.geometry.event.v1` | `geometry.packet.decoded.v1` |
| Extract Worker | — | `ingest.file.added.v1` |
| Publisher-Discord | — | `ingest.*.v1`, summary/chapter events |
| BoTZ Gateway | `botz.workitem.*` | `botz.heartbeat.v1`, `botz.register.v1` |
| Mesh Agent | `mesh.node.announce.v1` | — |
| Swarm Attribution | `evoswarm.population.v1` | `evoswarm.population.v1` |

---

## 6. CHIT Toggle Integration

Each agent can declare sensitivity to geometry state vector signals. These toggles determine whether an agent responds to control-plane changes from Hyperdimensions.

### Toggle Schema

```yaml
chit_toggles:
  delta_sensitive: true       # responds to tree-likeness changes
  kappa_sensitive: false      # not affected by hierarchy pressure
  hz_sensitive: true          # filters on spectral entropy
  swarm_participant: true     # participates in EvoSwarm fitness
  attribution_gated: true     # blocked when attribution proof weak
```

### Toggle Matrix

| Agent | delta | kappa | Hz | F (swarm) | A (attribution) |
|-------|-------|-------|-----|-----------|-----------------|
| Agent Zero | yes | yes | yes | yes | yes |
| Archon | yes | yes | yes | no | yes |
| Hi-RAG v2 | yes | yes | yes | yes | no |
| DeepResearch | yes | no | yes | no | yes |
| SupaSerch | yes | no | yes | yes | yes |
| Flute-Gateway | no | no | yes | no | yes |
| Extract Worker | no | no | yes | no | no |
| TensorZero | yes | no | no | no | no |
| BoTZ Gateway | no | no | no | yes | no |
| Hyperdimensions | yes | yes | yes | yes | yes |

Toggle state feeds into the Hyperdimensions visualization surface. See [`PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`](./PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md) for control mapping details.

---

## 7. Canonical Planes Mapping

From `PMOVES_UNIFIED_AGENT_TAXONOMY.md`, the 5 canonical planes map to agent capabilities:

| Plane | Function | Agents Active | Layer(s) |
|-------|----------|---------------|----------|
| **Control** | Governance, orchestration, task routing | Agent Zero, Archon, BoTZ | L1, L3 |
| **Context** | CHIT packets, geometry, persona anchors | Hyperdimensions, CHIT modules, all CGP producers | L0, L2.5 |
| **Execution** | Gateway tools, service adapters, work | TensorZero, Hi-RAG, workers, media pipeline | L2, L4 |
| **Observation** | Logs, metrics, traces, VLM verification | Prometheus, Grafana, Loki, cAdvisor | all |
| **Safety** | Secrets, signed artifacts, sandboxes | Danger Room, CHIT manifests, damage-control hooks | L5 |

---

## 8. Single Source of Truth

The machine-readable agent registry lives at `pmoves/config/agent_registry.yaml`. This file encodes every agent's class, type(s), tier, layers, NATS subjects, health endpoint, CHIT toggles, and evolution stage.

Query it with:

```bash
python -m pmoves.tools.agent_taxonomy_helper list          # all agents, table format
python -m pmoves.tools.agent_taxonomy_helper show <name>   # single agent card
python -m pmoves.tools.agent_taxonomy_helper connections    # network graph (JSON)
python -m pmoves.tools.agent_taxonomy_helper types          # type effectiveness chart
```

See [`AGENT_TAXONOMY_CROSS_REFERENCE.md`](./AGENT_TAXONOMY_CROSS_REFERENCE.md) for the full document dependency graph.

---

## 9. Design Principles

1. **Composability over monoliths** — Every agent is a discrete, collectible unit with clear type boundaries
2. **Evolution over replacement** — Agents gain capabilities incrementally; don't rebuild, evolve
3. **NATS as the nervous system** — All inter-agent communication flows through the event bus
4. **CHIT as the immune system** — Geometry toggles gate agent behavior, providing runtime safety
5. **Hyperdimensions as the mirror** — Visualization is not passive; it informs and controls
6. **Latent space amplification** — Agent + user together open portals that map smoother over time
7. **Known Roads** — Dangerous operations have canonical paths; all others ask permission

---

## 10. Resilience Attributes

Agents operating as background tasks (via Claude Code `Task` tool or NATS-dispatched workers) can hit context limits or fail mid-operation. Each agent declares resilience attributes to enable structured recovery.

### Resilience Schema

```yaml
resilience:
  context_budget: small | medium | large
  checkpoint_frequency: per_file | per_wave | per_submodule
  recovery_strategy: cipher_resumable | idempotent_replay | manual_handoff
  cipher_categories: [agent_plan, agent_checkpoint]
```

### Context Budget Classes

| Class | Budget | Use Case |
|-------|--------|----------|
| **small** | ~25K tokens | Single-file fixes, health checks |
| **medium** | ~50K tokens | Multi-file changes within one repo |
| **large** | ~100K+ tokens | Cross-repo orchestration, complex refactors |

### Recovery Strategies

| Strategy | Description | Example Agents |
|----------|-------------|----------------|
| `cipher_resumable` | Full plan + checkpoints in Cipher Memory; new agent reads and continues | Agent Zero, Archon |
| `idempotent_replay` | Work is idempotent; re-run from scratch is safe | Extract Worker, Notebook Sync |
| `manual_handoff` | Produces structured handoff doc for human completion | SupaSerch, DeepResearch |

### Failure Modes

| Mode | Trigger | Recovery |
|------|---------|----------|
| **Graceful** | Budget pressure detected | Commit, push, Cipher snapshot, stop |
| **Hard** | Context wall mid-operation | Check branch git log, reconstruct |
| **Blocked** | External dependency failure | Cipher blocker entry, human resolves |

See [`AGENT_RESILIENCE_PATTERNS.md`](./AGENT_RESILIENCE_PATTERNS.md) for the full resilience protocol, including Cipher Memory API usage and practical patterns.

---

## 11. Invocation Discipline

Agents are **explicitly invoked, never implicitly triggered**. This is the "no teleportation" rule — an agent cannot jump into action without being actually called.

### Rules

1. **No transitive calls**: Agent A cannot call Agent B which silently calls Agent C. Agent C must be explicitly invoked by the orchestrator (Agent Zero). The call chain is always visible and auditable.

2. **NATS subject ownership**: Each agent declares which subjects it publishes and subscribes to (see `agent_registry.yaml`). An agent MUST NOT publish to subjects it doesn't own. Cross-cutting events flow through the orchestrator.

3. **MCP tool gating**: MCP tools require explicit `call_tool` invocations. Agents cannot inject tool calls into other agents' contexts. Each MCP call is logged via Agent Zero.

4. **Damage-control enforcement**: The `patterns.yaml` hook system blocks unauthorized operations via `ask:true` patterns, requiring human confirmation. This is the Known Roads principle applied to invocation.

5. **Audit trail**: All invocations flow through observable channels:
   - NATS events (traceable subjects with JetStream replay)
   - MCP tool calls (logged via Agent Zero `/mcp/*`)
   - Claude Code hooks (pre/post execution logging)
   - Cipher Memory snapshots (durable invocation records)

### Registry Schema Extension

Each agent in `agent_registry.yaml` may declare an `invocation_policy`:

```yaml
invocation_policy:
  explicit_only: true          # must be directly called
  nats_trigger_allowed: true   # can be triggered by NATS events
  mcp_callable: true           # can be called via MCP
  transitive_call: false       # cannot be silently chained
```

### Naming Connection

The invocation discipline mirrors the naming principle: every agent name carries semantic alignment with its technical function. "Cipher Memory" encrypts and stores. "DoX" processes documents. "BoTZ" orchestrates bots. The name IS the invocation contract — you know what you're calling by what it's called.

---

## Related Documents

- [`AGENT_TAXONOMY_CROSS_REFERENCE.md`](./AGENT_TAXONOMY_CROSS_REFERENCE.md) — Master cross-reference
- [`AGENT_RESILIENCE_PATTERNS.md`](./AGENT_RESILIENCE_PATTERNS.md) — Resilience protocol and patterns
- [`../PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md`](../PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md) — Living template with CHIT examples
- `pmoves/config/agent_registry.yaml` — Machine-readable registry
- `pmoves/tools/agent_taxonomy_helper.py` — CLI query tool
- [`../MODEL_SOURCE_OF_TRUTH.md`](../MODEL_SOURCE_OF_TRUTH.md) — Model-agnostic role names (no concrete model IDs in architecture docs)
