# Cataclysm Studios Crosslinks

**Layer:** L4 Vision
**Status:** Current
**Last Updated:** 2026-03-11

> Bridge document linking PMOVES.AI technical documentation to the Cataclysm Studios Inc. business vision (L1-L4 taxonomy). Maps from cooperative economics concepts to their technical implementations.

---

## Vision → Technology Map

### L1: The Idea (Foundation)

| Vision Concept | Technical Implementation | Documentation |
|---------------|------------------------|---------------|
| Cooperative economy | ToKenism economic model | [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md) |
| Token-based incentives | GroToken via Dirichlet attribution | [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md) |
| Community-owned assets | CGP-proven ownership via Merkle proofs | [CGP_ENCODING_REFERENCE.md](PMOVESCHIT/CGP_ENCODING_REFERENCE.md) |
| Transparent accounting | CHIT Geometry Packets (publicly auditable) | [MATH_PIPELINE_WALKTHROUGH.md](PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md) |

### L2: The Vision (Strategy)

| Vision Concept | Technical Implementation | Documentation |
|---------------|------------------------|---------------|
| Multi-cooperative federation | NATS-based event fabric (GEOMETRY BUS) | [GEOMETRY_BUS_INTEGRATION.md](PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md) |
| Cross-border participation | Hyperbolic encoding (language-agnostic geometry) | [MATH_PIPELINE_WALKTHROUGH.md](PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md) |
| Fair attribution | Dirichlet distributions (non-zero guarantee) | [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md) |
| Evolutionary optimization | EvoSwarm parameter evolution | [EVOSWARM_OPERATIONS_GUIDE.md](EVOSWARM_OPERATIONS_GUIDE.md) |

### L3: The Implementation (Engineering)

| Vision Concept | Technical Implementation | Documentation |
|---------------|------------------------|---------------|
| GroToken currency | `dirichlet-weights.ts` + `cgp-generator.ts` | [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md) |
| FoodUSD economy | Contract type super-nodes in CGP | [CGP_ENCODING_REFERENCE.md](PMOVESCHIT/CGP_ENCODING_REFERENCE.md) |
| Group buying | GroupPurchase constellation | [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md) |
| Staking (GroVault) | `shape-attribution.ts` staking records | [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md) |
| Governance (CoopGovernor) | Voting action attribution | [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md) |
| Agent orchestration | Agent Zero MCP + Graphiti trails | [GRAPHITI_PROTOCOL_REFERENCE.md](GRAPHITI_PROTOCOL_REFERENCE.md) |
| AI training | AgentGym-RL on geometry-aware retrieval | [AGENTGYM_RL_OPERATIONS.md](AGENTGYM_RL_OPERATIONS.md) |

### L4: The Impact (Metrics)

| Vision Metric | Technical Measurement | Target |
|--------------|----------------------|--------|
| Wealth redistribution | Gini coefficient via `swarm-attribution.ts` | < 0.40 |
| Poverty alleviation | Poverty rate (4x food budget threshold) | < 10% |
| Participation growth | Active members / total members | > 85% |
| Wealth gap | Top-20% / Bottom-20% mean wealth | < 3.0x |
| Community autonomy | Local currency multiplier (GroToken value) | $2.00+ |

---

## Document Cross-Reference Index

### Cataclysm Studios Source Documents

| Document | Location | Layer |
|----------|----------|-------|
| Cataclysm Studios Inc. | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | L4 |
| Human Side | `pmoves/docs/PMOVESCHIT/Human_side.md` | L4 |
| Three-Body Doctrine | `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md` | L2 |

### CHIT Technical Documents

| Document | Location | Layer |
|----------|----------|-------|
| What Is CHIT? | `pmoves/docs/PMOVESCHIT/01_WHAT_IS_CHIT.md` | L1 |
| GEOMETRY BUS | `pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md` | L1 |
| EVO SWARM | `pmoves/docs/PMOVESCHIT/03_EVO_SWARM.md` | L1 |
| CGP v1.0 Specification | `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` | L1 |
| Glossary | `pmoves/docs/PMOVESCHIT/00_GLOSSARY.md` | L2 |

### ToKenism Implementation

| Document | Location | Layer |
|----------|----------|-------|
| TypeScript Modules | `PMOVES-ToKenism-Multi/integrations/contracts/chit/` | L3 |
| Integration Status | `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` | L5 |
| NATS Subjects | `.claude/context/geometry-nats-subjects.md` | L1 |

### New Documentation (This Branch)

| Document | Location | Layer |
|----------|----------|-------|
| Economic Model | `pmoves/docs/TOKENISM_ECONOMIC_MODEL.md` | L2/L4 |
| Developer Guide | `pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md` | L3 |
| This Crosslinks Doc | `pmoves/docs/CATACLYSM_CROSSLINKS.md` | L4 |

---

## Reading Path: Vision to Implementation

For stakeholders wanting to understand the complete picture:

1. **Start with vision**: [CATACLYSM_STUDIOS_INC.md](PMOVESCHIT/CATACLYSM_STUDIOS_INC.md)
2. **Understand the philosophy**: [Three-Body Doctrine](PMOVESCHIT/THREE_BODY_DOCTRINE.md)
3. **See the economic model**: [TOKENISM_ECONOMIC_MODEL.md](TOKENISM_ECONOMIC_MODEL.md)
4. **Learn the math**: [MATH_PIPELINE_WALKTHROUGH.md](PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md)
5. **Integrate as developer**: [TOKENISM_DEVELOPER_GUIDE.md](TOKENISM_DEVELOPER_GUIDE.md)
6. **Verify fairness**: [CALIBRATION_GUIDE.md](PMOVESCHIT/CALIBRATION_GUIDE.md)

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
