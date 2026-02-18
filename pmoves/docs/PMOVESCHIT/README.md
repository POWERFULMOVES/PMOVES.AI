# CHIT Documentation

**CHIT (Cymatic-Holographic Information Transfer)** encodes meaning as geometry instead of token streams. A compact "shape packet" (CGP) captures the direction, density, and hierarchy of information — and that shape is enough to reconstruct meaning on the receiving end.

CHIT is the encoding. The **GEOMETRY BUS** is the transport. **EVO SWARM** is the fairness optimizer. Together they form the geometric communication backbone of PMOVES.AI.

---

## The CHIT Iceberg

Most documentation focuses on the protocol — the "tip" of the iceberg. Beneath it sit the conceptual frameworks that explain *why*, the applied systems that show *where*, and the vision that frames *who it serves*.

### Layer 1: Protocol (How it works)

Core protocol documents — encoding, transport, optimization, and implementation.

| File | Audience | Description |
|------|----------|-------------|
| [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md) | Everyone / Developer | Plain-English explainer: the problem, the insight, the Five Pillars, a worked example |
| [02_GEOMETRY_BUS.md](02_GEOMETRY_BUS.md) | Technical PM / Developer | How CGPs travel between services via NATS. Architecture diagram, 6-step walkthrough |
| [03_EVO_SWARM.md](03_EVO_SWARM.md) | Technical PM / Developer | Distributed attribution optimization. Evolutionary loop, cooperative metrics |
| [04_API_REFERENCE.md](04_API_REFERENCE.md) | Developer | All 13 gateway endpoints with curl examples, schemas, and error codes |
| [05_QUICKSTART.md](05_QUICKSTART.md) | Developer | 6 runnable examples — ingest, visualize, decode, mix, demo pipeline, NATS publish |
| [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) | Developer / Architect | Canonical protocol specification: schema, encoding pipeline, security layer, NATS integration |
| [GEOMETRY_BUS_INTEGRATION.md](GEOMETRY_BUS_INTEGRATION.md) | Developer | Code examples for producing and consuming CGPs in Python and TypeScript |
| [PMOVESCHIT.md](PMOVESCHIT.md) | Historical | Original v0.1 CHIT specification (superseded by CGP v1.0 spec) |

### Layer 2: Conceptual Frameworks (Why it exists)

The theoretical foundations that motivate CHIT's design.

| File | Audience | Description |
|------|----------|-------------|
| [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md) | Everyone / Architect | Human/AI/System three-body problem — why stabilization requires geometric encoding |
| [PMOVESSHIFTEST.md](PMOVESSHIFTEST.md) | Everyone | Shape Harmonic Intelligence — accessible, shareable introduction to CHIT |
| [Integrating Math into PMOVES.AI.md](Integrating%20Math%20into%20PMOVES.AI.md) | Architect / Researcher | Deep mathematical foundations: hyperbolic geometry, zeta dynamics, holographic principle |

### Layer 3: Applied Systems (Where it's used)

Concrete applications of CHIT in PMOVES.AI subsystems.

| File | Audience | Description |
|------|----------|-------------|
| [LIVING_TEMPLATE_AGENT_TAXONOMY.md](LIVING_TEMPLATE_AGENT_TAXONOMY.md) | Developer / Architect | Agents encoded as CGP packets ("Agent Cards") through all Five Pillars |
| [PMOVES-CONCHexecution_guide.md](PMOVES-CONCHexecution_guide.md) | Developer | Consciousness Harvest pipeline — encoding research datasets into grounded personas |
| [Mathematical_UI_Design_Specification.md](Mathematical_UI_Design_Specification.md) | Developer / Designer | Visualizing CHIT geometry in the UI: hyperbolic navigation, spectral displays |
| [Mathematical_UI_Implementation_Plan.md](Mathematical_UI_Implementation_Plan.md) | Developer | Research roadmap for implementing the Mathematical UI spec |

### Layer 4: Vision & Business (Who it serves)

Platform vision and user-facing documentation.

| File | Audience | Description |
|------|----------|-------------|
| [CATACLYSM_STUDIOS_INC.md](CATACLYSM_STUDIOS_INC.md) | Everyone | Platform vision: three-entity model (Cataclysm Studios / PMOVES.AI / DARKXSIDE) |
| [Human_side.md](Human_side.md) | End User | How CHIT attribution works for ToKenism cooperative members |

### Layer 5: Reference & Operations

Glossary, status tracking, audits, legacy specs, and deployment guides.

| File | Audience | Description |
|------|----------|-------------|
| [00_GLOSSARY.md](00_GLOSSARY.md) | Everyone | 35+ terms defined: anchor, spectrum, CGP, Shape ID, Three-Body, CONCH, and more |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Developer | Implementation matrix, known gaps, roadmap |
| [CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md](CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md) | Developer | Point-in-time audit of CHIT/GEOMETRY BUS completeness |
| [PMOVESCHIT_DECODERv0.1.md](PMOVESCHIT_DECODERv0.1.md) | Developer | Decoder spec (v0.1) — exact and geometry-only decode modes. Implemented: `chit_decoder.py` |
| [PMOVESCHIT_DECODER_MULTIv0.1.md](PMOVESCHIT_DECODER_MULTIv0.1.md) | Developer | Multi-modal decoder — CLIP/CLAP implemented (`chit_decoder_mm.py`), T5 generator future |
| [PMOVES-CONCHexecution_guideb.md](PMOVES-CONCHexecution_guideb.md) | — | Legacy pointer to canonical execution guide |
| [LOCAL_MODEL_SETUP.md](LOCAL_MODEL_SETUP.md) | DevOps | Local model deployment: Ollama integration, VRAM sizing, TensorZero roles |

---

## Reading Paths

Pick the path that matches your goal:

**Understand the vision** (non-technical):
> [CATACLYSM_STUDIOS_INC.md](CATACLYSM_STUDIOS_INC.md) → [THREE_BODY_DOCTRINE.md](THREE_BODY_DOCTRINE.md) → [01 What Is CHIT?](01_WHAT_IS_CHIT.md) → [02 GEOMETRY BUS](02_GEOMETRY_BUS.md) → [03 EVO SWARM](03_EVO_SWARM.md)

**Understand it** (no code required):
> [01 What Is CHIT?](01_WHAT_IS_CHIT.md) → [02 GEOMETRY BUS](02_GEOMETRY_BUS.md) → [03 EVO SWARM](03_EVO_SWARM.md)

**Use it** (developer quickstart):
> [05 Quickstart](05_QUICKSTART.md) → [04 API Reference](04_API_REFERENCE.md) → [GEOMETRY BUS Integration Guide](GEOMETRY_BUS_INTEGRATION.md) → [Agent Taxonomy](LIVING_TEMPLATE_AGENT_TAXONOMY.md)

**Go deep** (math and architecture):
> [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) → [Integrating Math into PMOVES.AI](Integrating%20Math%20into%20PMOVES.AI.md) → [Mathematical UI Spec](Mathematical_UI_Design_Specification.md)

**Run consciousness harvest** (requires Layer 1):
> [PMOVES-CONCHexecution_guide.md](PMOVES-CONCHexecution_guide.md) (prerequisites: complete Layer 1 protocol docs)

---

## Quick Links

- **Gateway base URL:** `http://localhost:8086`
- **NATS subjects:** See [GEOMETRY BUS NATS Subject Catalog](../../.claude/context/geometry-nats-subjects.md)
- **TypeScript modules:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- **Python tools:** `pmoves/tools/chit/` --- see [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) for full documentation
- **CLI commands:** `/chit:encode`, `/chit:decode`, `/chit:visualize`, `/chit:bus`
- **Integration Layer:** [PMOVES.AI Integration Overview](../INTEGRATIONS_OVERVIEW.md) --- master entry point for all integration docs

## Cross-References

Documents outside this directory that reference CHIT:

| External Document | Relationship |
|-------------------|-------------|
| [docs/subsystems/CHIT_GEOMETRY_BUS.md](../../docs/subsystems/CHIT_GEOMETRY_BUS.md) | Complete CHIT & Geometry Bus reference |
| [docs/PLAN_Geometric_Intelligence.md](../../docs/PLAN_Geometric_Intelligence.md) | Integration planning for geometric intelligence |
| [pmoves/docs/CHIT_INTEGRATION_STATUS.md](../CHIT_INTEGRATION_STATUS.md) | Service-by-service CHIT integration status |
| [pmoves/docs/CHIT_USER_GUIDE.md](../CHIT_USER_GUIDE.md) | CHIT encoding/decoding user guide (secrets focus) |
| [pmoves/docs/CHIT_AUDIT_TRACKING.md](../CHIT_AUDIT_TRACKING.md) | Code presence audit across branches |
| [pmoves/docs/FLUTE_PROSODIC_ARCHITECTURE.md](../FLUTE_PROSODIC_ARCHITECTURE.md) | Flute voice layer — uses GEOMETRY BUS for transport |
