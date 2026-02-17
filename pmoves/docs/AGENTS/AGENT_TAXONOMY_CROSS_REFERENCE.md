# Agent Taxonomy Cross-Reference Hub

_Last updated: 2026-02-16_

Master cross-reference for all documents, concepts, and implementation files involved in the PMOVES Agent Class Taxonomy. When the taxonomy changes, use this document to identify which files need updates.

---

## Document Registry

| # | Document | Location | Key Concepts | Type |
|---|----------|----------|-------------|------|
| 1 | **Agent Class Taxonomy** | `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` | Class hierarchy (Legendary/Standard/Specialized/Utility), 7 types, evolution stages, connections, CHIT toggles | Definition |
| 2 | **Unified Agent Taxonomy** | `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md` | 6-layer fold model (L0-L5), 5 canonical planes, persona anchors | Foundation |
| 3 | **Skills (PmovesSKillZ)** | `pmoves/docs/AGENTS/PmovesSKillZ.md` | 5 skill bundles, operator expectations, open-chat+scout vs focus modes | Skills |
| 4 | **BoTZ Gateway Integration** | `pmoves/docs/AGENTS/BOTZ_GATEWAY_AGENT_INTEGRATION.md` | BoTZ (pull, work distribution) vs Gateway Agent (push, MCP tools), skill levels | Integration |
| 5 | **Hyperdimensions Control Plane** | `pmoves/docs/AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md` | Geometry state vector (delta, kappa, Hz, F, A), control mapping, per-agent CHIT toggles | Control |
| 6 | **CHIT Implementation Status** | `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md` | 5 math pillars status, CGP versions, NATS subjects, module locations | Status |
| 7 | **Geometry Bus Integration** | `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` | CGP format, point modality types, CGP producers/consumers | Integration |
| 8 | **Living Template** | `pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md` | 5 pillars applied to taxonomy, CGP agent card, 4 expanded use cases | Template |
| 9 | **CGP v1.0 Specification** | `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` | Production CGP spec | Spec |
| 10 | **Services Catalog** | `.claude/context/services-catalog.md` | 59+ services, ports, health endpoints, tiers | Catalog |
| 11 | **Submodules Catalog** | `.claude/context/submodules.md` | 20+ git submodules, branches, URLs | Catalog |
| 12 | **NATS Subjects** | `.claude/context/nats-subjects.md` | Research, media, agent, mesh, remote event subjects | Events |
| 13 | **Geometry NATS Subjects** | `.claude/context/geometry-nats-subjects.md` | ToKenism, geometry core, CGP schema subjects | Events |
| 14 | **Original Vision (agnotes2)** | `pmoves/docs/AGENTS/agnotes2.md` | Pokemon/Transformers metaphor, latent space amplification, portal mapping | Vision |
| 15 | **Agent Registry** | `pmoves/config/agent_registry.yaml` | Single source of truth: 35 agents with class, type, tier, layers, NATS, toggles | Data |
| 16 | **CLI Helper Tool** | `pmoves/tools/agent_taxonomy_helper.py` | list/show/connections/types commands | Tool |

---

## Implementation Files

| Component | Location | Language | Purpose |
|-----------|----------|----------|---------|
| Agent Registry | `pmoves/config/agent_registry.yaml` | YAML | Machine-readable agent catalog |
| Taxonomy Helper | `pmoves/tools/agent_taxonomy_helper.py` | Python | CLI query tool |
| CGP Generator | `PMOVES-ToKenism-Multi/integrations/contracts/chit/cgp-generator.ts` | TypeScript | Generates CGP packets |
| Dirichlet Weights | `PMOVES-ToKenism-Multi/integrations/contracts/chit/dirichlet-weights.ts` | TypeScript | Attribution distribution |
| Hyperbolic Encoder | `PMOVES-ToKenism-Multi/integrations/contracts/chit/hyperbolic-encoder.ts` | TypeScript | Poincare disk embedding |
| Zeta Filter | `PMOVES-ToKenism-Multi/integrations/contracts/chit/zeta-filter.ts` | TypeScript | Signal noise reduction |
| Swarm Attribution | `PMOVES-ToKenism-Multi/integrations/contracts/chit/swarm-attribution.ts` | TypeScript | EvoSwarm consensus |
| NATS Publisher | `PMOVES-ToKenism-Multi/integrations/contracts/chit/chit-nats-publisher.ts` | TypeScript | Geometry Bus transport |
| CGP Sample | `PMOVES-ToKenism-Multi/integrations/contracts/chit/samples/agent-taxonomy-cgp.json` | JSON | Agent topology CGP packet |
| Agent Topology Surface | `Pmoves-hyperdimensions/saves/agent_topology.json` | JSON | Poincare disk visualization |
| CHIT Manifold Surface | `Pmoves-hyperdimensions/saves/chit_manifold.json` | JSON | Geometry manifold visualization |

---

## Concept → Document Mapping

| Concept | Primary Document | Supporting Documents |
|---------|-----------------|---------------------|
| **Class hierarchy** (Legendary/Standard/Specialized/Utility) | #1 Agent Class Taxonomy | #14 agnotes2, #15 Registry |
| **7 service types** (data/api/llm/worker/media/agent/ui) | #1 Agent Class Taxonomy | #10 Services Catalog |
| **6-layer fold** (L0-L5) | #2 Unified Taxonomy | #1 Class Taxonomy, #5 Control Plane |
| **5 canonical planes** (Control/Context/Execution/Observation/Safety) | #2 Unified Taxonomy | #1 Class Taxonomy |
| **Geometry state vector** (delta, kappa, Hz, F, A) | #5 Control Plane | #8 Living Template, #6 CHIT Status |
| **CHIT toggles** (per-agent sensitivity flags) | #5 Control Plane, #1 Class Taxonomy | #15 Registry, #8 Living Template |
| **Evolution stages** (Base/Stage 1/Stage 2/Mega) | #1 Agent Class Taxonomy | #15 Registry |
| **5 math pillars** (Dirichlet/Hyperbolic/Merkle/Zeta/Swarm) | #6 CHIT Status | #8 Living Template, #7 Geometry Bus |
| **CGP packet format** (v0.1/v0.2/v1.0) | #9 CGP v1.0 Spec | #6 CHIT Status, #7 Geometry Bus |
| **NATS event topology** | #12 NATS Subjects | #13 Geometry NATS, #7 Geometry Bus |
| **Skill bundles** | #3 PmovesSKillZ | #4 BoTZ Integration |
| **Type effectiveness** | #1 Agent Class Taxonomy | #16 CLI Helper |
| **Poincare disk rendering** | Agent Topology Surface | #5 Control Plane, #8 Living Template |
| **Latent space amplification** | #14 agnotes2 | #8 Living Template (Use Case 2) |
| **Deployment readiness score** | #5 Control Plane | #8 Living Template (Use Case 4) |

---

## Change Impact Matrix

When you change one of these concepts, update the listed documents:

| Changed | Update These |
|---------|-------------|
| Add/remove an agent | #15 Registry, #1 Class Taxonomy, #10 Services Catalog |
| Change agent type/tier | #15 Registry, #1 Class Taxonomy |
| Change agent layers | #15 Registry, #1 Class Taxonomy, #2 Unified Taxonomy |
| Add NATS subject | #12 NATS Subjects (or #13), #15 Registry, #1 Class Taxonomy |
| Change CHIT toggle | #15 Registry, #5 Control Plane, #8 Living Template |
| New CHIT pillar | #6 CHIT Status, #8 Living Template, #7 Geometry Bus |
| CGP spec version | #9 CGP Spec, #6 CHIT Status, #8 Living Template |
| New submodule | #11 Submodules Catalog, possibly #15 Registry |
| Port change | #10 Services Catalog, #15 Registry |
| Geometry state vector change | #5 Control Plane, #8 Living Template, Agent Topology Surface |

---

## Verification Checklist

After taxonomy changes, verify:

- [ ] `python -m pmoves.tools.agent_taxonomy_helper list` shows correct agent count
- [ ] `python -m pmoves.tools.agent_taxonomy_helper show <changed_agent>` reflects changes
- [ ] `python -m pmoves.tools.agent_taxonomy_helper connections` shows expected edges
- [ ] All document cross-references resolve (no broken links)
- [ ] CGP sample packet in `samples/agent-taxonomy-cgp.json` reflects current agents
- [ ] `agent_topology.json` surface renders without errors in Hyperdimensions
- [ ] Layer assignments align between Registry (#15) and Unified Taxonomy (#2)
- [ ] NATS subjects align between Registry (#15) and NATS catalogs (#12, #13)

---

## Related

- [Agent Class Taxonomy](./PMOVES_AGENT_CLASS_TAXONOMY.md)
- [Living Template](../PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md)
- [Hyperdimensions Control Plane](./PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md)
