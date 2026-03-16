# TAC Integration Topology Map

> Master document connecting all TAC-documented submodules with their cross-repo integration points, NATS flows, and CHIT Geometry Bus lifecycle.

**Version:** 2.2
**Last Updated:** 2026-03-15
**Scope:** 26 markdown TAC trees + 14 YAML TAC trees + this topology map (~55% coverage)

### TAC Tree Index (v2.1 — 7 new P1 additions)

**Orchestration & Research:**
- `TAC_AGENT_ZERO.md` — Control-plane orchestrator (Mega evolution)
- `TAC_BOTZ.md` — Skills marketplace framework (Stage 1)
- `TAC_SUPASERCH.md` — Multimodal holographic research (NEW)
- `TAC_DEEPRESEARCH.md` — LLM-based research planner (NEW)
- `TAC_GATEWAY_AGENT.md` — MCP tool orchestration gateway (NEW)

**Media & Ingestion:**
- `TAC_PMOVES_YT.md` — YouTube ingestion pipeline (NEW)
- `TAC_FLUTE.md` — Prosodic voice mesh gateway

**CHIT & Evolution:**
- `TAC_TOKENISM.md` — CHIT attribution engine
- `TAC_CONSCIOUSNESS.md` — CGP consciousness mapping (NEW)
- `TAC_EVOSWARM.md` — Evolutionary optimization controller (NEW)

**GPU & Model Infrastructure:**
- `TAC_GPU_ORCHESTRATOR.md` — GPU mesh management (NEW)
- `TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md` — Model registry, personas, readiness

**Agent Ecosystem:**
- `TAC_CIPHER.md` — Knowledge-graph memory
- `TAC_CLAWZ.md` — Multi-channel messaging
- `TAC_A0_PLUGINS.md` — Community plugin index
- `TAC_AUTORESEARCH.md` — Autonomous ML training
- `TAC_DOX.md` — Document intelligence

**Infrastructure:**
- `TAC_INFRASTRUCTURE.md` — Node topology, networking
- `TAC_RUNNERS.md` — CI/CD runner fleet
- `TAC_TAILSCALE.md` — VPN mesh

**Pipelines (Umbrella TACs):**
- `TAC_EMBEDDING_PIPELINE.md` — Extract Worker + LangExtract + PDF Ingest (NEW)
- `TAC_MEDIA_ANALYSIS.md` — Media-Video + Media-Audio analyzers (NEW)
- `TAC_E2B_SANDBOX.md` — E2B code execution ecosystem (NEW)

**Integrations:**
- `TAC_HEALTH.md` — Fitness tracking (wger)
- `TAC_WEALTH.md` — Finance management (Firefly III)
- `TAC_INTEGRATION_TOPOLOGY.md` — This file (master map)

**YAML Audit Trees (14):**
- `agent-zero-customization.tac.yaml`, `archon-agents.tac.yaml`, `botz-mcp.tac.yaml`
- `comfyui-pipeline.tac.yaml`, `dox-intelligence.tac.yaml` (NEW), `firefly-iii.tac.yaml` (UPDATED)
- `health-wger.tac.yaml`, `hirag-retrieval.tac.yaml`, `n8n.tac.yaml`
- `observability.tac.yaml`, `security-posture.tac.yaml`, `soundcloud-ingest.tac.yaml`
- `tensorzero-gpu.tac.yaml`, `tokenism-chit.tac.yaml` (NEW)

---

## 1. Integration Topology Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                   AGENT ZERO (8080)                     │
                    │              Primary Orchestrator (Mega)                │
                    │              MCP API + Subordinate Model               │
                    └──┬──────┬──────────┬──────────┬──────────┬────────────┘
                       │      │          │          │          │
              ┌────────▼──┐   │   ┌──────▼──┐ ┌────▼────┐ ┌──▼───┐ ┌───────────┐
              │ a0-plugins│   │   │  BoTZ   │ │  DoX    │ │Flute │ │ Research  │
              │  (index)  │   │   │ Gateway │ │  Intel  │ │Voice │ │ (HiRAG,   │
              │ 13 plugins│   │   │  :8054  │ │  (TBD)  │ │:8055 │ │ SupaSerch)│
              └───────────┘   │   │ 100+MCP │ │ GeoViz  │ │ BPM  │ │ :8086/99  │
                              │   └──┬──┬──┘ └──┬──┬───┘ └──┬───┘ └───────────┘
                     ┌────────▼──┐   │  │       │  │         │
                     │  ClawZ    │   │  │       │  │         │
                     │ OpenClaw  │   │  │       │  │         │
                     │  :18789   │   │  │       │  │         │
                     │ 47 exts  │   │  │       │  │         │
                     └───────────┘   │  │       │  │         │
                                     │  │       │  │         │
         ┌───────────────────────────┘  │       │  │         │
         │               ┌─────────────┘       │  │         │
         │               │                      │  │         │
    ┌────▼─────┐    ┌────▼──▼──┐   ┌────────┐  ┌▼──▼────┐   ┌▼──────────────┐
    │ Docling  │    │ToKenism  │   │autores.│  │Hyper-  │   │  NATS Bus     │
    │  :3020   │    │ Multi    │   │  CLI   │  │dimens  │   │  :4222        │
    │ PDF proc │    │ CHIT Eng │   │  GPU   │  │  Viz   │   │  JetStream    │
    └──────────┘    │ 9 TS mods│   └────────┘  └────────┘   └───┬───┬──────┘
                    └──┬──┬────┘                                │   │
                       │  │                                     │   │
              ┌────────┘  └────────┐                    ┌──────┘   └──────┐
              │                    │                    │                  │
         ┌────▼─────┐        ┌────▼────┐          ┌──▼──────┐   ┌─────▼────┐
         │ Health   │        │ Wealth  │          │Publisher │   │ Cipher   │
         │ (wger)   │◄──────►│(Firefly)│          │ Discord  │   │ Memory   │
         │ Fitness  │ Health │ Finance │          │  :8094   │   │  :8096   │
         │          │↔Spend  │         │          └──────────┘   │ Neo4j    │
         └──────────┘ correl └─────────┘                        └──────────┘
```

---

## 2. NATS Subject Flow Diagram

```
 Agent Zero          BoTZ                    ToKenism                  Flute
  │                   │                        │                        │
  ├─► agent.tool.     ├─► botz.workitem.       ├─► tokenism.cgp.        ├─► tokenism.geometry.
  │   executed.v1     │   assigned.v1          │   weekly.v1            │   event.v1
  │                   │                        │                        │
  ◄── mesh.node.      ├─► botz.work.           ├─► tokenism.attribution.├─► tokenism.prosodic.
  │   announce.v1     │   available.v1         │   recorded.v1          │   bpm.v1
  │                   │                        │                        │
                      ◄── botz.heartbeat.v1   ├─► tokenism.cgp.        ◄── geometry.packet.
                      ◄── botz.register.v1    │   ready.v1             │   decoded.v1
                      ◄── botz.work.claimed.v1│                        │
                                               ├─► tokenism.swarm.      │
                                               │   population.v1        │

 Health (planned)    Wealth (planned)     Cipher (planned)         ClawZ (planned)
  │                   │                    │                        │
  ├─► health.metrics.  ├─► finance.trans.   ├─► cipher.memory.       ├─► openclaw.message.
  │   updated.v1       │   ingested.v1     │   stored.v1            │   received.v1
  │                   │                    │                        │
  ├─► health.workout.  ├─► finance.budget.  ├─► cipher.memory.       ├─► openclaw.message.
  │   completed.v1     │   alert.v1        │   searched.v1          │   sent.v1
  │                   │                    │                        │
  ├─► health.weekly.   ├─► finance.monthly.                         ├─► openclaw.channel.
  │   summary.v1       │   summary.v1                               │   connected.v1

 autoresearch (planned)
  │
  ├─► research.autoresearch.experiment.v1
  ├─► research.autoresearch.result.v1

                    ┌──────────────────────────────────────────────────────────────────────────────┐
                    │                           NATS JetStream (:4222)                             │
                    │                                                                              │
                    │  Consumers: Hi-RAG v2, Publisher-Discord, EvoSwarm, Swarm Attribution,       │
                    │             Hyperdimensions, Agent Zero, Cipher Memory (planned)              │
                    └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CHIT Geometry Bus Flow (CGP Packet Lifecycle)

```
    ┌─────────────┐
    │  GENERATION  │  Any CHIT-enabled service generates a CGP packet
    │              │  Sources: ToKenism, Flute, DeepResearch, SupaSerch
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  ENCODING    │  ToKenism CHIT modules encode the packet:
    │              │  chitEncoder.ts → CGP v0.1 or v0.2
    │              │  dirichletAttribution.ts → weighted contributions
    │              │  merkleAttribution.ts → verification hash
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  TRANSPORT   │  NATS subjects carry encoded packets:
    │              │  tokenism.cgp.ready.v1 (generic)
    │              │  tokenism.prosodic.bpm.v1 (voice-specific)
    │              │  geometry.packet.encoded.v1 (Hi-RAG)
    └──────┬──────┘
           │
           ├──────────────┬──────────────┬──────────────┐
           ▼              ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
    │  Hi-RAG v2 │ │ EvoSwarm   │ │  Swarm     │ │ Publisher  │
    │  Indexing  │ │ Controller │ │ Attribution│ │  Discord   │
    │  + Search  │ │  Fitness   │ │  Consensus │ │  Notify    │
    └──────┬─────┘ └──────┬─────┘ └──────┬─────┘ └────────────┘
           │              │              │
           ▼              ▼              ▼
    ┌─────────────┐
    │VISUALIZATION│  Hyperdimensions renders geometry:
    │              │  Poincare disk, manifold3D, Zeta spectrum
    │              │  DoX geometric intelligence layer
    └─────────────┘
```

---

## 4. Data Flow: External → Internal

```
External Data Sources
        │
        ├── YouTube videos ──────► PMOVES.YT ──► Whisper ──► Transcripts
        ├── PDF documents ───────► PDF Ingest ──► Extract Worker ──► Embeddings
        ├── Web research ────────► SupaSerch ──► DeepResearch ──► Findings
        ├── Financial records ───► Wealth (Firefly III) ──► finance.transactions.ingested.v1
        ├── Health metrics ──────► Health (wger) ──► health.metrics.updated.v1
        ├── Smart contracts ─────► ToKenism ──► tokenism.attribution.recorded.v1
        ├── Chat messages ───────► ClawZ ──► Agent Zero ──► Task execution
        └── ML experiments ──────► autoresearch ──► Agent Zero (planned)
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  CHIT Attribution │
                              │  CGP v0.2 packets │
                              └────────┬──────────┘
                                       │
                              ┌────────▼──────────┐
                              │   Hi-RAG v2        │
                              │   Qdrant + Neo4j   │
                              │   + Meilisearch    │
                              └────────┬──────────┘
                                       │
                              ┌────────▼──────────┐
                              │ Agent Zero         │
                              │ Orchestration      │
                              │ + MCP tools        │
                              └────────┬──────────┘
                                       │
                              ┌────────▼──────────┐
                              │ Flute Gateway      │
                              │ Voice + BPM output │
                              │ → Any device       │
                              └───────────────────┘
```

---

## 5. Integration Contract Table

What each repo expects from and provides to each other:

| Provider | Consumer | Contract | Transport | Status |
|----------|----------|----------|-----------|--------|
| **ToKenism** → Hi-RAG v2 | CGP packets for indexing | `tokenism.cgp.ready.v1` | NATS | Active |
| **ToKenism** → Publisher-Discord | Attribution embeds | `tokenism.*` | NATS | Active |
| **Flute** → ToKenism | Voice events for attribution | `tokenism.geometry.event.v1` | NATS | Active |
| **Flute** → ToKenism | BPM-encoded prosodics | `tokenism.prosodic.bpm.v1` | NATS | Active |
| **DoX** → Hyperdimensions | Geometry visualization | WebSocket | Active |
| **DoX** → Extract Worker | Document text | NATS | Active |
| **BoTZ** → Agent Zero | MCP tool execution | MCP (:2091) | Active |
| **BoTZ** → BoTZ CLI instances | Work distribution | `botz.*` NATS | Active |
| **Agent Zero** → All agents | Tool execution events | `agent.tool.executed.v1` NATS | Active |
| **Agent Zero** → Cipher Memory | Checkpoint/resume | HTTP (:8096) | Active |
| **Cipher** → All agents | Plan/checkpoint/completion | HTTP API | Active |
| **ClawZ** → Agent Zero | Chat-to-agent delegation | MCP / NATS | **Planned** |
| **ClawZ** → Flute | Voice TTS via channels | HTTP | **Planned** |
| **ClawZ** → Cipher | Conversation persistence | HTTP | **Planned** |
| **autoresearch** → Agent Zero | Experiment orchestration | NATS | **Planned** |
| **autoresearch** → AgentGym RL | Training pipeline | Shared storage | **Planned** |
| **a0-plugins** → Agent Zero | Plugin loading | File-based index | Active |
| **Health** → Agent Zero | Health metrics | `health.*.v1` NATS | **Planned** |
| **Health** → Wealth | Health-spend correlation | Cross-domain API | **Planned** |
| **Wealth** → ToKenism | Real spending data | `finance.*.v1` NATS | **Planned** |
| **Wealth** → Agent Zero | Finance alerts | `finance.budget.alert.v1` | **Planned** |

---

## 6. Maturity Matrix

| Submodule | Healthz | Metrics | Auth | NATS | Docker Hardening | CHIT | Overall |
|-----------|---------|---------|------|------|-----------------|------|---------|
| **Agent Zero** | GREEN | GREEN | Partial | Active | GREEN | **Full** | **Mega** |
| **BoTZ** | Partial | Yes | Fail-closed (fixed) | Active | Yes | Partial | Stage 1 |
| **DoX** | Planned | Planned | GREEN | P1 missing | Yes | Partial | Stage 1 |
| **ToKenism** | N/A (library) | None | Partial | Active | Yes | **Full** | Stage 1 |
| **Flute** | GREEN | GREEN | Partial | Active | GREEN | Active | Stage 1 |
| **Cipher** | GREEN | MISSING | MISSING | MISSING | Partial | None | Base |
| **ClawZ** | GREEN | Optional (OTEL) | Partial | MISSING | Partial | None | **Pre-Stage** |
| **autoresearch** | N/A (CLI) | N/A | N/A | MISSING | N/A | None | **Pre-Stage** |
| **a0-plugins** | N/A (index) | N/A | N/A (GitHub) | N/A | N/A | None | Base |
| **Health** | MISSING | MISSING | MISSING | MISSING | Template | None | **Pre-Stage** |
| **Wealth** | MISSING | MISSING | Partial | MISSING | Partial | None | **Pre-Stage** |

---

## 7. Priority Actions

### Immediate (P1)
1. ~~**BoTZ:** Fix JWT fail-open in `auth.py:59`~~ → **Fixed** (`auth.py:63-67` now raises HTTPException 500)
2. **DoX:** Add NATS auth block to `nats.conf`
3. **ToKenism:** Fix `export` syntax in `env.shared`
4. ~~**Cipher:** Fix `CIPHER_URL` default mismatch~~ → **Fixed** (now `cipher-api:8096`)

### Short-term (P2)
5. **Health:** Add `/healthz` endpoint (Django middleware)
6. **Wealth:** Add `/healthz` endpoint (Laravel health check)
7. **BoTZ:** Authenticate MCP Gateway endpoint
8. **ClawZ:** Add Prometheus `/metrics` endpoint (currently OTEL-only)
9. **Cipher:** Add API authentication (currently relies on network isolation)

### Medium-term (P3)
10. **Health:** NATS integration for health events
11. **Wealth:** NATS integration for finance events
12. **Wealth→ToKenism:** Bridge real spending to FoodUSD simulation
13. **Cipher:** Add NATS publishing for memory events
14. **ClawZ:** Add NATS integration for channel events
15. **autoresearch:** Add NATS integration for experiment events

### Long-term (P4)
16. **Health↔Wealth:** Cross-domain correlation analytics
17. **All:** CHIT integration for remaining submodules
18. **Flute BPM:** Production deployment of prosodic BPM encoding
19. **ClawZ↔Flute:** Voice TTS via messaging channels
20. **autoresearch↔AgentGym:** Training pipeline integration

---

## 8. Related Documents

### TAC Trees (13 total)
- [`TAC_AGENT_ZERO.md`](./TAC_AGENT_ZERO.md) — Agent Zero control-plane orchestrator
- [`TAC_BOTZ.md`](./TAC_BOTZ.md) — BoTZ skills marketplace
- [`TAC_DOX.md`](./TAC_DOX.md) — DoX document intelligence
- [`TAC_TOKENISM.md`](./TAC_TOKENISM.md) — ToKenism CHIT engine
- [`TAC_HEALTH.md`](./TAC_HEALTH.md) — Health fitness tracking
- [`TAC_WEALTH.md`](./TAC_WEALTH.md) — Wealth finance management
- [`TAC_FLUTE.md`](./TAC_FLUTE.md) — Flute voice gateway
- [`TAC_CIPHER.md`](./TAC_CIPHER.md) — Cipher Memory knowledge graph
- [`TAC_CLAWZ.md`](./TAC_CLAWZ.md) — ClawZ multi-channel gateway
- [`TAC_AUTORESEARCH.md`](./TAC_AUTORESEARCH.md) — autoresearch ML training loop
- [`TAC_A0_PLUGINS.md`](./TAC_A0_PLUGINS.md) — Agent Zero plugin index
- [`TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md`](./TAC_MODEL_INFRA_PERSONA_PROD_READINESS.md) — Model infrastructure

### Other References
- [`../FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md) — Prosodic architecture + BPM bridge
- [`../AGENTS/PMOVES_AGENT_TOPOLOGY.md`](../AGENTS/PMOVES_AGENT_TOPOLOGY.md) — Master agent topology
- [`../AGENTS/DEEP_DIVE_ALIGNMENT_2026-03-15.md`](../AGENTS/DEEP_DIVE_ALIGNMENT_2026-03-15.md) — Cross-submodule alignment analysis
- `.claude/context/geometry-nats-subjects.md` — GEOMETRY BUS subject catalog
- `.claude/context/nats-subjects.md` — Main NATS subject catalog

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE::2026-03-15 -->
