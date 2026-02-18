# CHIT Documentation

**CHIT (Cymatic-Holographic Information Transfer)** encodes meaning as geometry instead of token streams. A compact "shape packet" (CGP) captures the direction, density, and hierarchy of information — and that shape is enough to reconstruct meaning on the receiving end.

CHIT is the encoding. The **GEOMETRY BUS** is the transport. **EVO SWARM** is the fairness optimizer. Together they form the geometric communication backbone of PMOVES.AI.

---

## Reading Paths

**Understand it** (no code required):
> [01 What Is CHIT?](01_WHAT_IS_CHIT.md) → [02 GEOMETRY BUS](02_GEOMETRY_BUS.md) → [03 EVO SWARM](03_EVO_SWARM.md)

**Use it** (developer quickstart):
> [05 Quickstart](05_QUICKSTART.md) → [04 API Reference](04_API_REFERENCE.md) → [GEOMETRY BUS Integration Guide](GEOMETRY_BUS_INTEGRATION.md)

**Go deep** (math and architecture):
> [CGP v1.0 Specification](CGP_v1.0_SPECIFICATION.md) → [Integrating Math into PMOVES.AI](Integrating%20Math%20into%20PMOVES.AI.md)

---

## Document Index

| File | Audience | Description |
|------|----------|-------------|
| [00_GLOSSARY.md](00_GLOSSARY.md) | Everyone | 25+ terms defined: anchor, spectrum, CGP, Shape ID, and more |
| [01_WHAT_IS_CHIT.md](01_WHAT_IS_CHIT.md) | Everyone → Developer | Plain-English explainer: the problem, the insight, the Five Pillars, a worked example |
| [02_GEOMETRY_BUS.md](02_GEOMETRY_BUS.md) | Technical PM → Developer | How CGPs travel between services via NATS. Architecture diagram, 6-step walkthrough |
| [03_EVO_SWARM.md](03_EVO_SWARM.md) | Technical PM → Developer | Distributed attribution optimization. Evolutionary loop, cooperative metrics |
| [04_API_REFERENCE.md](04_API_REFERENCE.md) | Developer | All 13 gateway endpoints with curl examples, schemas, and error codes |
| [05_QUICKSTART.md](05_QUICKSTART.md) | Developer | 6 runnable examples — ingest, visualize, decode, mix, demo pipeline, NATS publish |
| [CGP_v1.0_SPECIFICATION.md](CGP_v1.0_SPECIFICATION.md) | Developer / Architect | Canonical protocol specification: schema, encoding pipeline, security layer, NATS integration |
| [GEOMETRY_BUS_INTEGRATION.md](GEOMETRY_BUS_INTEGRATION.md) | Developer | Code examples for producing and consuming CGPs in Python and TypeScript |
| [Integrating Math into PMOVES.AI.md](Integrating%20Math%20into%20PMOVES.AI.md) | Architect / Researcher | Deep mathematical foundations: hyperbolic geometry, zeta dynamics, holographic principle |
| [Human_side.md](Human_side.md) | End User | How CHIT attribution works for ToKenism cooperative members |
| [PMOVESCHIT.md](PMOVESCHIT.md) | Historical | Original v0.1 CHIT specification (superseded by CGP v1.0 spec) |
| [PMOVESSHIFTEST.md](PMOVESSHIFTEST.md) | Everyone | Accessible one-minute explainer and shareable blurbs |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Developer | Implementation matrix, known gaps, roadmap |

---

## Quick Links

- **Gateway base URL:** `http://localhost:8086`
- **NATS subjects:** See [GEOMETRY BUS NATS Subject Catalog](../../.claude/context/geometry-nats-subjects.md)
- **TypeScript modules:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
- **Python tools:** `pmoves/tools/chit/`
- **CLI commands:** `/chit:encode`, `/chit:decode`, `/chit:visualize`, `/chit:bus`
