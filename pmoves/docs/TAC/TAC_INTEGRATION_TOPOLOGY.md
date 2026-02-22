# TAC Integration Topology Map

> Master document connecting BoTZ, DoX, ToKenism, Health, and Wealth submodules with their cross-repo integration points, NATS flows, and CHIT Geometry Bus lifecycle.

**Version:** 1.0
**Last Updated:** 2026-02-20
**Scope:** 5 target submodules + Flute prosodic bridge

---

## 1. Integration Topology Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                   AGENT ZERO (8080)                     │
                    │              Primary Orchestrator                       │
                    └───────┬──────────┬──────────┬──────────┬───────────────┘
                            │          │          │          │
                   ┌────────▼───┐ ┌────▼────┐ ┌──▼───┐ ┌───▼────────┐
                   │   BoTZ     │ │  DoX    │ │Flute │ │  Research   │
                   │  Gateway   │ │  Intel  │ │Voice │ │  (HiRAG,   │
                   │  :8054     │ │  (TBD)  │ │:8055 │ │  SupaSerch) │
                   │  100+ MCP  │ │ GeoViz  │ │ BPM  │ │  :8086/99  │
                   └──┬──┬──┬──┘ └──┬──┬───┘ └──┬───┘ └────────────┘
                      │  │  │       │  │         │
         ┌────────────┘  │  │       │  │         │
         │               │  │       │  │         │
    ┌────▼─────┐    ┌────▼──▼──┐   ┌▼──▼────┐   ┌▼──────────────┐
    │ Docling  │    │ToKenism  │   │Hyper-  │   │  NATS Bus     │
    │  :3020   │    │ Multi    │   │dimens  │   │  :4222        │
    │ PDF proc │    │ CHIT Eng │   │  Viz   │   │  JetStream    │
    └──────────┘    │ 9 TS mods│   └────────┘   └───┬───┬──────┘
                    └──┬──┬────┘                     │   │
                       │  │                          │   │
              ┌────────┘  └────────┐         ┌──────┘   └──────┐
              │                    │         │                  │
         ┌────▼─────┐        ┌────▼────┐  ┌──▼──────┐   ┌─────▼────┐
         │ Health   │        │ Wealth  │  │Publisher │   │ Cipher   │
         │ (wger)   │◄──────►│(Firefly)│  │ Discord  │   │ Memory   │
         │ Fitness  │ Health │ Finance │  │  :8094   │   │  :8096   │
         │          │↔Spend  │         │  └──────────┘   └──────────┘
         └──────────┘ correl └─────────┘
```

---

## 2. NATS Subject Flow Diagram

```
 BoTZ                    ToKenism                  Flute                 Health (planned)    Wealth (planned)
  │                        │                        │                        │                   │
  ├─► botz.workitem.       ├─► tokenism.cgp.        ├─► tokenism.geometry.   ├─► health.metrics.  ├─► finance.transactions.
  │   assigned.v1          │   weekly.v1            │   event.v1            │   updated.v1       │   ingested.v1
  │                        │                        │                        │                   │
  ├─► botz.work.           ├─► tokenism.attribution.├─► tokenism.prosodic.   ├─► health.workout.  ├─► finance.budget.
  │   available.v1         │   recorded.v1          │   bpm.v1 (NEW)        │   completed.v1     │   alert.v1
  │                        │                        │                        │                   │
  ◄── botz.heartbeat.v1   ├─► tokenism.cgp.        ◄── geometry.packet.     ├─► health.weekly.   ├─► finance.monthly.
  ◄── botz.register.v1    │   ready.v1             │   decoded.v1           │   summary.v1       │   summary.v1
  ◄── botz.work.claimed.v1│                        │                        │                   │
                           ├─► tokenism.swarm.      │                        │                   │
                           │   population.v1        │                        │                   │
                           │                        │                        │                   │
                           │         ┌──────────────┼────────────────────────┼───────────────────┤
                           │         │              │                        │                   │
                           ▼         ▼              ▼                        ▼                   ▼
                    ┌──────────────────────────────────────────────────────────────────────────────┐
                    │                           NATS JetStream (:4222)                             │
                    │                                                                              │
                    │  Consumers: Hi-RAG v2, Publisher-Discord, EvoSwarm, Swarm Attribution,       │
                    │             Hyperdimensions, Agent Zero                                       │
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
        └── Smart contracts ─────► ToKenism ──► tokenism.attribution.recorded.v1
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
| **Flute** → ToKenism | BPM-encoded prosodics | `tokenism.prosodic.bpm.v1` | NATS | **NEW** |
| **DoX** → Hyperdimensions | Geometry visualization | WebSocket | Active |
| **DoX** → Extract Worker | Document text | NATS | Active |
| **BoTZ** → Agent Zero | MCP tool execution | MCP (:2091) | Active |
| **BoTZ** → BoTZ CLI instances | Work distribution | `botz.*` NATS | Active |
| **Health** → Agent Zero | Health metrics | `health.*.v1` NATS | **Planned** |
| **Health** → Wealth | Health-spend correlation | Cross-domain API | **Planned** |
| **Wealth** → ToKenism | Real spending data | `finance.*.v1` NATS | **Planned** |
| **Wealth** → Agent Zero | Finance alerts | `finance.budget.alert.v1` | **Planned** |

---

## 6. Maturity Matrix

| Submodule | Healthz | Metrics | Auth | NATS | Docker Hardening | CHIT | Overall |
|-----------|---------|---------|------|------|-----------------|------|---------|
| **BoTZ** | Partial | Yes | P1 fail-open | Active | Yes | Partial | Stage 1 |
| **DoX** | Planned | Planned | GREEN | P1 missing | Yes | Partial | Stage 1 |
| **ToKenism** | N/A (library) | None | Partial | Active | Yes | **Full** | Stage 1 |
| **Health** | MISSING | MISSING | MISSING | MISSING | Template | None | **Pre-Stage** |
| **Wealth** | MISSING | MISSING | Partial | MISSING | Partial | None | **Pre-Stage** |
| **Flute** | GREEN | GREEN | Partial | Active | GREEN | Active | Stage 1 |

---

## 7. Priority Actions

### Immediate (P1)
1. **BoTZ:** Fix JWT fail-open in `auth.py:59` — must fail-closed
2. **DoX:** Add NATS auth block to `nats.conf`
3. **ToKenism:** Fix `export` syntax in `env.shared`

### Short-term (P2)
4. **Health:** Add `/healthz` endpoint (Django middleware)
5. **Wealth:** Add `/healthz` endpoint (Laravel health check)
6. **BoTZ:** Authenticate MCP Gateway endpoint

### Medium-term (P3)
7. **Health:** NATS integration for health events
8. **Wealth:** NATS integration for finance events
9. **Wealth→ToKenism:** Bridge real spending to FoodUSD simulation

### Long-term (P4)
10. **Health↔Wealth:** Cross-domain correlation analytics
11. **All:** CHIT integration for all 5 submodules
12. **Flute BPM:** Production deployment of prosodic BPM encoding

---

## Related Documents

- [`TAC_BOTZ.md`](./TAC_BOTZ.md) — BoTZ skills marketplace
- [`TAC_DOX.md`](./TAC_DOX.md) — DoX document intelligence
- [`TAC_TOKENISM.md`](./TAC_TOKENISM.md) — ToKenism CHIT engine
- [`TAC_HEALTH.md`](./TAC_HEALTH.md) — Health fitness tracking
- [`TAC_WEALTH.md`](./TAC_WEALTH.md) — Wealth finance management
- [`TAC_FLUTE.md`](./TAC_FLUTE.md) — Flute voice gateway
- [`../FLUTE_PROSODIC_ARCHITECTURE.md`](../FLUTE_PROSODIC_ARCHITECTURE.md) — Prosodic architecture + BPM bridge
- [`../AGENTS/PMOVES_AGENT_TOPOLOGY.md`](../AGENTS/PMOVES_AGENT_TOPOLOGY.md) — Master agent topology
- `.claude/context/geometry-nats-subjects.md` — GEOMETRY BUS subject catalog
- `.claude/context/nats-subjects.md` — Main NATS subject catalog

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
