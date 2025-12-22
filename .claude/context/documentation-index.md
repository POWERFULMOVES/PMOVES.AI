# PMOVES.AI Documentation Index

**Last Updated:** December 2025
**Purpose:** Cross-reference navigation for PMOVES.AI documentation

---

## Quick Navigation Matrix

| Topic | Primary Doc | Implementation | NATS Subjects |
|-------|-------------|----------------|---------------|
| **CHIT/CGP** | `PMOVESCHIT.md` | `IMPLEMENTATION_STATUS.md` | `geometry-nats-subjects.md` |
| **Flute Voice** | `flute-gateway.md` | `FLUTE_PROSODIC_ARCHITECTURE.md` | `nats-subjects.md` |
| **Personas** | `PERSONAS.md` | `voice-personas.md` | `voice.persona.*` |
| **Services** | `services-catalog.md` | CLAUDE.md | `nats-subjects.md` |
| **Brand** | `CATACLYSM_STUDIOS_INC.md` | Services | N/A |

---

## PMOVESCHIT / GEOMETRY BUS

### Specifications

| Document | Path | Purpose |
|----------|------|---------|
| Core Specification | `pmoves/docs/PMOVESCHIT/PMOVESCHIT.md` | CGP v0.1 packet format |
| Implementation Status | `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md` | What's implemented vs. spec |
| GEOMETRY BUS Guide | `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` | Service integration |
| NATS Subjects | `.claude/context/geometry-nats-subjects.md` | `tokenism.*`, `geometry.*` subjects |

### Decoder Specifications

| Document | Path | Status |
|----------|------|--------|
| Decoder v0.1 | `PMOVESCHIT_DECODERv0.1.md` | Spec only |
| Multi-Modal Decoder | `PMOVESCHIT_DECODER_MULTIv0.1.md` | Not implemented |
| SHIFT Test | `PMOVESSHIFTEST.md` | Conceptual |

### TypeScript Implementation

```
PMOVES-ToKenism-Multi/integrations/contracts/chit/
├── cgp-generator.ts        # CGP packet generation
├── dirichlet-weights.ts    # Dirichlet attribution
├── hyperbolic-encoder.ts   # Poincaré disk embedding
├── shape-attribution.ts    # Multi-modal shapes
├── swarm-attribution.ts    # EvoSwarm consensus
├── zeta-filter.ts          # Riemann zeta filtering
├── chit-nats-publisher.ts  # NATS integration
└── index.ts                # Unified exports
```

### TAC Commands

| Command | Description |
|---------|-------------|
| `/chit:encode` | Encode content to CGP |
| `/chit:decode` | Decode CGP packet |
| `/chit:visualize` | Render as geometry |
| `/chit:bus` | GEOMETRY BUS operations |
| `/hyperdim:render` | Three.js surfaces |
| `/hyperdim:animate` | Animated visualizations |
| `/hyperdim:export` | Export to 3D formats |

---

## Voice & Flute

### Architecture

| Document | Path | Purpose |
|----------|------|---------|
| Flute API Reference | `.claude/context/flute-gateway.md` | Operational API |
| Full Architecture | `pmoves/docs/context/PMOVES Multimodal Communication Layer (Flute)...md` | Design spec |
| Prosodic Sidecar | `pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md` | TTFS optimization |
| Voice Personas | `.claude/context/voice-personas.md` | Persona system |

### Deprecated Locations

| Document | Status |
|----------|--------|
| `docs/PMOVES Multimodal Communication Layer ("Flute")...md` | DEPRECATED → use `.claude/context/flute-gateway.md` |
| `pmoves/docs/context/PMOVES Multimodal Communication Layer ("Flute")...md` | DEPRECATED → duplicate |

### NATS Subjects

```
voice.tts.request.v1     # TTS synthesis request
voice.tts.chunk.v1       # Audio chunk streaming
voice.tts.completed.v1   # Synthesis complete
voice.stt.completed.v1   # Transcription complete
voice.persona.created.v1 # Persona events
agent.voice.speaking.v1  # Agent voice state
```

---

## Persona Framework

| Document | Path | Purpose |
|----------|------|---------|
| Persona Framework | `pmoves/docs/PERSONAS.md` | 325+ persona architecture |
| Voice Personas | `.claude/context/voice-personas.md` | Voice/TTS integration |
| CATACLYSM Brand | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | Brand alignment |

---

## Services Catalog

| Document | Path | Purpose |
|----------|------|---------|
| Services Catalog | `.claude/context/services-catalog.md` | All 60+ services |
| NATS Subjects | `.claude/context/nats-subjects.md` | Event subjects |
| MCP API | `.claude/context/mcp-api.md` | Agent Zero MCP |
| Submodules | `.claude/context/submodules.md` | 20+ submodules |
| TensorZero | `.claude/context/tensorzero.md` | LLM gateway |

---

## Brand & Platform

| Document | Path | Purpose |
|----------|------|---------|
| CATACLYSM Overview | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | Platform vision |
| Platform Vision | `CATACLYSM_STUDIOS_INC/ABOUT/` | Brand identity |
| Fordham Pilot | (embedded in CATACLYSM docs) | Real-world deployment |

---

## Mathematical Foundations

| Document | Path | Purpose |
|----------|------|---------|
| Math Integration | `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md` | Five pillars |
| UI Design Spec | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Design_Specification.md` | Visual math |
| Implementation Plan | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Implementation_Plan.md` | Roadmap |
| Human Side | `pmoves/docs/PMOVESCHIT/Human_side.md` | User-facing docs |

### Five Mathematical Pillars

1. **Dirichlet Distributions** → Fair attribution
2. **Hyperbolic Geometry** → Hierarchical embedding
3. **Merkle Proofs** → Integrity verification
4. **Zeta Functions** → Signal filtering
5. **Swarm Optimization** → Distributed consensus

---

## Research & Evaluation

| Document | Path | Purpose |
|----------|------|---------|
| A2UI Evaluation | `research/A2UI_EVALUATION_REPORT.md` | UI framework analysis |
| CHR Pipeline | `pmoves/docs/PMOVESCHIT/Constellation-Harvest-Regularization/` | Entropy analysis |
| Doc2Structure | `pmoves/docs/PMOVESCHIT/doc2structure.py` | Document processing |

---

## Cross-Reference: Services ↔ NATS

| Service | Port | Key NATS Subjects |
|---------|------|-------------------|
| Hi-RAG v2 | 8086 | `geometry.packet.encoded.v1` |
| Flute-Gateway | 8055/8056 | `voice.tts.*`, `voice.stt.*` |
| Agent Zero | 8080 | `agent.*`, `claude.code.*` |
| SupaSerch | 8099 | `supaserch.request.v1` |
| DeepResearch | 8098 | `research.deepresearch.*` |

---

## Cross-Reference: CGP Specs ↔ TypeScript

| CGP Field | TypeScript Module | Function |
|-----------|-------------------|----------|
| `super_nodes` | `cgp-generator.ts` | `generateCGP()` |
| `dirichlet_alpha` | `dirichlet-weights.ts` | `computeWeights()` |
| `hyperbolic_coords` | `hyperbolic-encoder.ts` | `embedPoincare()` |
| `swarm_consensus` | `swarm-attribution.ts` | `evolvePopulation()` |
| `zeta_filter` | `zeta-filter.ts` | `filterSignal()` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Dec 2025 | Initial index, PR #343 alignment |

---

## Related

- Main CLAUDE.md: `.claude/CLAUDE.md`
- Testing Strategy: `.claude/context/testing-strategy.md`
- Learnings: `.claude/learnings/`
