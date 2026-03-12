# PMOVES.AI Documentation Map

**Living Document** | **CHIT Layer Taxonomy** | **Last Updated:** 2026-02-19

> Master crosslinked index organized by CHIT's 5-layer taxonomy. Each entry is classified, crosslinked, and tracked for freshness. This document is the entry point for navigating the entire PMOVES.AI documentation corpus.

---

## Layer Taxonomy

| Layer | Name | Scope | Audience |
|-------|------|-------|----------|
| **L1** | Protocol | CGP spec, schemas, NATS subjects, API reference | Developer / Architect |
| **L2** | Conceptual | Three-Body Doctrine, math foundations, glossary | Everyone / Researcher |
| **L3** | Applied | Service integration guides, tool catalog, quickstart | Developer / Integrator |
| **L4** | Vision | Cataclysm Studios, human-side docs, brand identity | Everyone / Stakeholder |
| **L5** | Operations | Audit trails, evidence, CI config, hardening tracker | DevOps / Security |

---

## CHIT Namespace Topology (Cellular Model)

PMOVES services follow a **cellular topology** where each service has:
- A **namespace** (publish/subscribe identity on the GEOMETRY BUS)
- An **inside** (container internals, local state) and **outside** (exposed APIs, NATS subjects)
- A **cellular membrane** (healthcheck endpoint, auth layer, network policy)
- **Dynamic port allocation** with CHIT-signed service announcements
- **Cross-container validation** via CGP signatures on NATS messages

Services broadcast their name and listen for their identity. The NATS subject hierarchy encodes the namespace tree: `<domain>.<service>.<action>.<version>`.

---

## L1: Protocol

Core protocol specifications, encoding schemas, transport definitions, and API references.

| Document | Path | Status | Cross-links |
|----------|------|--------|-------------|
| CGP v1.0 Specification | `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` | Current | L1:API Ref, L1:GEOMETRY BUS |
| What Is CHIT? | `pmoves/docs/PMOVESCHIT/01_WHAT_IS_CHIT.md` | Current | L2:Three-Body, L2:Glossary |
| GEOMETRY BUS | `pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md` | Current | L1:NATS Subjects, L3:Integration Guide |
| EVO SWARM | `pmoves/docs/PMOVESCHIT/03_EVO_SWARM.md` | Current | L1:CGP Spec, L3:Agent Taxonomy |
| API Reference | `pmoves/docs/PMOVESCHIT/04_API_REFERENCE.md` | Current | L1:CGP Spec, L3:Quickstart |
| Quickstart | `pmoves/docs/PMOVESCHIT/05_QUICKSTART.md` | Current | L1:API Ref, L3:Tools Catalog |
| GEOMETRY BUS Integration | `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` | Current | L1:NATS Subjects, L3:Service Catalog |
| NATS Subject Catalog | `.claude/context/nats-subjects.md` | Current | L1:GEOMETRY BUS, L3:Service Catalog |
| GEOMETRY NATS Subjects | `.claude/context/geometry-nats-subjects.md` | Current | L1:GEOMETRY BUS, L3:CHIT Tools |
| MCP API Reference | `.claude/context/mcp-api.md` | Current | L1:Agent Zero, L3:Agent Taxonomy |
| CHIT Gateway API | `pmoves/docs/PMOVESCHIT/CHIT_GATEWAY_API.md` | Current | L1:API Ref, L3:Tools Catalog |
| Original CHIT Spec (v0.1) | `pmoves/docs/PMOVESCHIT/PMOVESCHIT.md` | Superseded | L1:CGP v1.0 |
| Decoder v0.1 | `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md` | Current | L1:CGP Spec |
| Multi-Modal Decoder | `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODER_MULTIv0.1.md` | Current | L1:Decoder v0.1 |
| Math Pipeline Walkthrough | `pmoves/docs/PMOVESCHIT/MATH_PIPELINE_WALKTHROUGH.md` | Current | L1:CGP Spec, L2:Math, L3:Calibration |
| CGP Encoding Reference | `pmoves/docs/PMOVESCHIT/CGP_ENCODING_REFERENCE.md` | Current | L1:CGP Spec, L1:Math Pipeline |
| Calibration Guide | `pmoves/docs/PMOVESCHIT/CALIBRATION_GUIDE.md` | Current | L1:CGP Spec, L3:EvoSwarm Ops |
| Graphiti Protocol Reference | `pmoves/docs/GRAPHITI_PROTOCOL_REFERENCE.md` | Current | L1:NATS, L3:Agent Registry |
| EvoSwarm Parameter Catalog | `pmoves/docs/EVOSWARM_PARAMETER_CATALOG.md` | Current | L1:CGP Spec, L3:EvoSwarm Ops |

---

## L2: Conceptual

Theoretical foundations explaining *why* CHIT exists and the mathematical principles that drive it.

| Document | Path | Status | Cross-links |
|----------|------|--------|-------------|
| Three-Body Doctrine | `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md` | Current | L1:CHIT Explainer, L4:Cataclysm |
| SHIFT Test | `pmoves/docs/PMOVESCHIT/PMOVESSHIFTEST.md` | Current | L2:Three-Body, L1:CHIT Explainer |
| Integrating Math into PMOVES.AI | `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md` | Current | L2:Three-Body, L3:Math UI |
| Glossary (35+ terms) | `pmoves/docs/PMOVESCHIT/00_GLOSSARY.md` | Current | All layers |
| Mathematical UI Design Spec | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Design_Specification.md` | Current | L2:Math Integration, L3:Math UI Plan |
| Mathematical UI Implementation Plan | `pmoves/docs/PMOVESCHIT/Mathematical_UI_Implementation_Plan.md` | Current | L2:Math UI Spec |
| Constellation-Harvest-Regularization | `pmoves/docs/PMOVESCHIT/Constellation-Harvest-Regularization/` | Current | L2:Math Integration |
| Asimov Governor for LLMs | `pmoves/docs/PMOVESCHIT/An Asimov Governor for LLMs/` | Research | L2:Three-Body |
| Latent Geometry Control Knob | `pmoves/docs/PMOVESCHIT/Latent_Geometry_Is_a_Control_Knob/` | Research | L2:Math Integration |
| ToKenism Economic Model | `pmoves/docs/TOKENISM_ECONOMIC_MODEL.md` | Current | L3:Dev Guide, L4:Cataclysm |

---

## L3: Applied

Concrete implementation guides, service catalogs, tool references, and integration patterns.

| Document | Path | Status | Cross-links |
|----------|------|--------|-------------|
| Services Catalog | `.claude/context/services-catalog.md` | Current | L1:NATS, L5:Hardening |
| Tier Architecture | `.claude/context/tier-architecture.md` | Current | L3:Secrets Pipeline, L5:Env Audit |
| Submodules Catalog | `.claude/context/submodules.md` | Current | L5:Submodule Audit |
| Integration Layer Overview | `pmoves/docs/INTEGRATIONS_OVERVIEW.md` | Current | L3:All integration docs |
| CHIT Tools Catalog | `pmoves/docs/CHIT_TOOLS_CATALOG.md` | Current | L1:API Ref, L3:Quickstart |
| Secrets Pipeline Reference | `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` | Current | L3:Tier Architecture |
| GPU Orchestration Guide | `pmoves/docs/GPU_ORCHESTRATION_GUIDE.md` | Current | L3:Services Catalog |
| Service Integration Guide | `pmoves/docs/INTEGRATIONS.md` | Current | L3:Services Catalog |
| Submodule Integration Guide | `pmoves/docs/PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md` | Current | L3:Submodules Catalog |
| Submodule Integration Contract | `pmoves/docs/SUBMODULE_INTEGRATION_CONTRACT.md` | Current | L3:Submodule Guide |
| Agent Taxonomy (Living Template) | `pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md` | Current | L1:CGP Spec, L3:Services |
| CONCH Execution Guide | `pmoves/docs/PMOVESCHIT/PMOVES-CONCHexecution_guide.md` | Current | L1:Protocol, L3:Agent Taxonomy |
| Documentation Index | `.claude/context/documentation-index.md` | Current | All layers |
| Testing Strategy | `.claude/context/testing-strategy.md` | Current | L5:CI Config |
| Flute Gateway API | `.claude/context/flute-gateway.md` | Current | L3:Services Catalog |
| Voice Personas | `.claude/context/voice-personas.md` | Current | L3:Flute, L4:Personas |
| TensorZero Reference | `.claude/context/tensorzero.md` | Current | L3:Services Catalog |
| Hardware Profiles | `.claude/context/hardware-profiles.md` | Current | L3:GPU Guide |
| Python Patterns | `.claude/context/python-patterns.md` | Current | L3:Testing |
| UI Patterns | `.claude/context/ui-patterns.md` | Current | L3:Services |
| Hooks README | `.claude/hooks/README.md` | Current | L5:Damage Control |
| BoTZ Skills Marketplace | `pmoves/docs/BOTZ_SKILLS_MARKETPLACE.md` | Current | L3:Services |
| Skills Registry | `pmoves/configs/submodule_skill_registry.json` | Current | L3:Submodules |
| CHIT User Guide | `pmoves/docs/PMOVESCHIT/CHIT_USER_GUIDE.md` | Current | L1:CGP Spec, L3:Secrets |
| Local Model Setup | `pmoves/docs/PMOVESCHIT/LOCAL_MODEL_SETUP.md` | Current | L3:TensorZero |
| Service Docs Matrix | `pmoves/docs/SERVICE_DOCS_MATRIX.md` | Current | L3:Services Catalog |
| ToKenism Developer Guide | `pmoves/docs/TOKENISM_DEVELOPER_GUIDE.md` | Current | L2:Economic Model, L1:CGP Spec |
| EvoSwarm Operations Guide | `pmoves/docs/EVOSWARM_OPERATIONS_GUIDE.md` | Current | L1:Parameter Catalog, L3:AgentGym |
| AgentGym-RL Operations | `pmoves/docs/AGENTGYM_RL_OPERATIONS.md` | Current | L3:EvoSwarm Ops, L1:CGP Spec |
| Graphiti Agent Registry | `pmoves/docs/GRAPHITI_AGENT_REGISTRY.md` | Current | L1:Graphiti Protocol |
| Graphiti Integration Guide | `pmoves/docs/GRAPHITI_INTEGRATION_GUIDE.md` | Current | L1:Graphiti Protocol, L3:Agent Registry |

---

## L4: Vision

Platform vision, brand identity, and user-facing documentation.

| Document | Path | Status | Cross-links |
|----------|------|--------|-------------|
| Cataclysm Studios Inc. | `pmoves/docs/PMOVESCHIT/CATACLYSM_STUDIOS_INC.md` | Current | L2:Three-Body, L4:Human Side |
| Human Side | `pmoves/docs/PMOVESCHIT/Human_side.md` | Current | L4:Cataclysm, L1:CHIT |
| Personas Framework | `pmoves/docs/PERSONAS.md` | Current | L3:Voice Personas |
| Roadmap | `pmoves/docs/ROADMAP.md` | Current | All layers |
| Branch Strategy | `pmoves/docs/BRANCH_STRATEGY.md` | Current | L5:CI |
| Cataclysm Crosslinks | `pmoves/docs/CATACLYSM_CROSSLINKS.md` | Current | L2:Economic Model, L3:Dev Guide |

---

## L5: Operations

Audit trails, evidence artifacts, CI configuration, security hardening, and operational documentation.

| Document | Path | Status | Cross-links |
|----------|------|--------|-------------|
| Production Audit Dashboard | `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` | Current | L5:All audits |
| CHIT Implementation Audit | `pmoves/docs/PMOVESCHIT/CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md` | Current | L1:CGP Spec |
| Implementation Status | `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md` | Current | L1:CGP Spec, L5:Audit |
| CHIT Integration Status | `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` | Current | L3:Services |
| CHIT Audit Tracking | `pmoves/docs/audit/CHIT_AUDIT_TRACKING.md` | Current | L5:Integration Status |
| Submodule Alignment SITREP | `pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` | Current | L3:Submodules |
| Submodule Docs Dossier | `pmoves/docs/SUBMODULE_DOCS_DOSSIER.md` | Current | L3:Submodules |
| Submodule Layer Validation | `pmoves/docs/SUBMODULE_LAYER_VALIDATION.md` | Current | L5:Evidence |
| CHIT Change Tracker | `pmoves/docs/CHIT_CHANGE_TRACKER.md` | Current | All layers |
| Submodule Docs Audit | `pmoves/docs/evidence/SUBMODULE_DOCS_AUDIT.md` | Current | L3:Submodules |
| CI Runners Config | `.claude/context/ci-runners.md` | Current | L5:CI |
| Submodule Workflow | `.claude/context/submodule-workflow.md` | Current | L3:Submodules |
| Git Worktrees | `.claude/context/git-worktrees.md` | Current | L5:Workflow |
| CODEX Operator Home | `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md` | Current | L5:Ops |
| CODEX Claude Parity Map | `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md` | Current | L5:Ops |
| Tooling Script Audit | `pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md` | Current | L5:Ops |
| Evidence Directory | `pmoves/docs/evidence/` | Current | L5:All audits |

---

## Reading Paths

### New Developer
1. L2: [Glossary](PMOVESCHIT/00_GLOSSARY.md)
2. L1: [What Is CHIT?](PMOVESCHIT/01_WHAT_IS_CHIT.md)
3. L3: [Integration Overview](INTEGRATIONS_OVERVIEW.md)
4. L3: [Services Catalog](../.claude/context/services-catalog.md)
5. L3: [Quickstart](PMOVESCHIT/05_QUICKSTART.md)

### CHIT Protocol Developer
1. L1: [CGP v1.0 Spec](PMOVESCHIT/CGP_v1.0_SPECIFICATION.md)
2. L1: [API Reference](PMOVESCHIT/04_API_REFERENCE.md)
3. L1: [GEOMETRY BUS Integration](PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md)
4. L3: [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md)
5. L5: [Implementation Status](PMOVESCHIT/IMPLEMENTATION_STATUS.md)

### Security Auditor
1. L5: [Production Audit Dashboard](PRODUCTION_AUDIT_DASHBOARD.md)
2. L5: [Evidence Directory](evidence/)
3. L3: [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md)
4. L3: [Hooks README](../.claude/hooks/README.md)
5. L5: [CHIT Change Tracker](CHIT_CHANGE_TRACKER.md)

### Researcher / Mathematician
1. L2: [Three-Body Doctrine](PMOVESCHIT/THREE_BODY_DOCTRINE.md)
2. L2: [Integrating Math into PMOVES.AI](PMOVESCHIT/Integrating%20Math%20into%20PMOVES.AI.md)
3. L2: [Mathematical UI Spec](PMOVESCHIT/Mathematical_UI_Design_Specification.md)
4. L1: [CGP v1.0 Spec](PMOVESCHIT/CGP_v1.0_SPECIFICATION.md)
5. L4: [Cataclysm Studios](PMOVESCHIT/CATACLYSM_STUDIOS_INC.md)

---

## Companion Documents

| Document | Purpose |
|----------|---------|
| [SERVICE_DOCS_MATRIX.md](SERVICE_DOCS_MATRIX.md) | Service-to-documentation cross-reference |
| [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md) | Living change audit trail with CGP metadata |
| [evidence/SUBMODULE_DOCS_AUDIT.md](evidence/SUBMODULE_DOCS_AUDIT.md) | Submodule documentation completeness |
| [PMOVESCHIT/README.md](PMOVESCHIT/README.md) | CHIT Documentation Suite (5-layer iceberg) |
| [INTEGRATIONS_OVERVIEW.md](INTEGRATIONS_OVERVIEW.md) | Six integration systems overview |

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
