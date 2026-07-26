// data.js — All data is grounded in PMOVES.AI repo docs.
// Path references shown in UI link to the source files in the repo.

const SOURCES = {
  whatIsChit: "pmoves/docs/PMOVESCHIT/01_WHAT_IS_CHIT.md",
  glossary: "pmoves/docs/PMOVESCHIT/00_GLOSSARY.md",
  geometryBus: "pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md",
  evoSwarm: "pmoves/docs/PMOVESCHIT/03_EVO_SWARM.md",
  apiRef: "pmoves/docs/PMOVESCHIT/04_API_REFERENCE.md",
  quickstart: "pmoves/docs/PMOVESCHIT/05_QUICKSTART.md",
  cgpSpec: "pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md",
  livingTemplate: "pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md",
  mof: "pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md",
  grandConvergence: "pmoves/docs/architecture/PMOVES_GRAND_CONVERGENCE.md",
  agentClassTax: "pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md",
  agentTopology: "pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md",
  unifiedTax: "pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md",
  taxXref: "pmoves/docs/AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md",
  skillz: "pmoves/docs/AGENTS/PmovesSKillZ.md",
  agnote4482: "pmoves/docs/AGENTS/AGNOTE4482.md",
  resilience: "pmoves/docs/AGENTS/AGENT_RESILIENCE_PATTERNS.md",
  creator: "pmoves/docs/CREATOR_PIPELINE.md",
  registry: "pmoves/config/agent_registry.yaml",
  tokenomicsProjections: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/5-Year Business Projections_ AI - Tokenomics Model/ai_tokenomics_business_projections.csv",
  tokenomicsBreakeven: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/5-Year Business Projections_ AI - Tokenomics Model/breakeven_analysis.csv",
  tokenomicsScenarios: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/5-Year Business Projections_ AI - Tokenomics Model/scenario_analysis.csv",
  containerScaling: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/Containerized Micro Business Model_ Docker-Like Sc/micro_business_container_scaling.csv",
  communityImpact: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/Community Wealth Building Through Diverse Resident/community_economic_impact.csv",
  implPhases: "CATACLYSM_STUDIOS_INC/L4-PLATFORM/projections/data/Containerized Micro Business Model_ Docker-Like Sc/implementation_phases_timeline.csv",
};

const REPO_BASE = "https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/";
const sourceUrl = (path) => REPO_BASE + path;

// --- CHIT five pillars (01_WHAT_IS_CHIT.md §The Five Pillars) ---
const PILLARS = [
  {
    name: "Dirichlet Distributions",
    role: "Fair weight allocation",
    summary:
      "Bayesian conjugate prior to the multinomial — guarantees every contributor receives non-zero attribution and updates cleanly with new evidence.",
    file: "PMOVES-ToKenism-Multi/integrations/contracts/chit/dirichlet-weights.ts",
    src: SOURCES.whatIsChit,
  },
  {
    name: "Hyperbolic Geometry",
    role: "Hierarchical capacity (Poincaré disk)",
    summary:
      "Curvature K = −1. Distance grows exponentially toward the boundary, giving O(log n) tree distortion — natural fit for taxonomies.",
    file: "PMOVES-ToKenism-Multi/integrations/contracts/chit/hyperbolic-encoder.ts",
    src: SOURCES.whatIsChit,
  },
  {
    name: "Merkle Proofs",
    role: "Tamper-proof attribution",
    summary:
      "SHA-256 leaf hashes with inclusion proofs. Tamper with a weight or remove a contributor and the proof fails.",
    file: "PMOVES-ToKenism-Multi/integrations/contracts/chit/shape-attribution.ts",
    src: SOURCES.whatIsChit,
  },
  {
    name: "Zeta Spectral Filtering",
    role: "Signal from noise",
    summary:
      "Gaussian kernels centered on non-trivial Riemann zeta zeros (14.13, 21.02, 25.01…) act as scale-invariant filters that separate meaningful spectral patterns from noise.",
    file: "PMOVES-ToKenism-Multi/integrations/contracts/chit/zeta-filter.ts",
    src: SOURCES.whatIsChit,
  },
  {
    name: "Swarm Optimization (EVO SWARM)",
    role: "Distributed consensus, no central authority",
    summary:
      "A population of agents proposes attribution weights, mutates with Dirichlet noise, and selects survivors by entropy-reduction fitness. No backprop, no central authority.",
    file: "PMOVES-ToKenism-Multi/integrations/contracts/chit/swarm-attribution.ts",
    src: SOURCES.whatIsChit,
  },
];

// --- MOF component mapping (PMOVES_MOF_ARCHITECTURE.md §Component Mapping & §Appendix) ---
const MOF_COMPONENTS = [
  {
    component: "ClickHouse + Prometheus",
    mofRole: "Squeeze film air gap",
    description:
      "Shared observability data plane — the medium between agents. Pattern density determines framework lift.",
    src: SOURCES.mof,
  },
  {
    component: "NATS",
    mofRole: "Frequency driver + traveling wave",
    description:
      "Maintains protocol resonance and overlays peer-to-peer traveling waves that eliminate hierarchical dead spots.",
    src: SOURCES.mof,
  },
  {
    component: "TensorZero",
    mofRole: "Impedance matcher (the dolphin's melon)",
    description:
      "Dynamic LLM routing matched to task requirements in real time — prevents quality collapse from impedance mismatch.",
    src: SOURCES.mof,
  },
  {
    component: "CHIT",
    mofRole: "Self-stabilizing equilibrium / organic linker",
    description:
      "Signed trail autoregulation — closed-loop correction without supervisor. The bond between framework nodes.",
    src: SOURCES.mof,
  },
  {
    component: "Neo4j",
    mofRole: "Internal framework surface",
    description:
      "Knowledge graph adsorption substrate — where execution patterns land. More edges = more adsorption sites.",
    src: SOURCES.mof,
  },
  {
    component: "Agent Zero",
    mofRole: "Crystalline lattice",
    description:
      "Hierarchical pore geometry — defines which agents exist, communication boundaries, framework periodicity.",
    src: SOURCES.mof,
  },
];

// --- Geometry Bus topology (02_GEOMETRY_BUS.md) ---
const BUS_NODES = [
  { id: "agent-zero", name: "Agent Zero", group: "node", role: "Lattice / orchestrator", layers: 7, layer: "L1" },
  { id: "chit", name: "CHIT", group: "linker", role: "Signed trail / linker", layer: "L2.5" },
  { id: "nats", name: "NATS JetStream", group: "bus", role: "Frequency driver", layer: "L2" },
  { id: "deepresearch", name: "DeepResearch", group: "producer", role: "Producer", layer: "L4" },
  { id: "supaserch", name: "SupaSerch", group: "producer", role: "Producer", layer: "L6" },
  { id: "flute", name: "Flute Gateway", group: "producer", role: "Producer (voice)", layer: "L2" },
  { id: "tokenism", name: "ToKenism", group: "producer", role: "Producer (attribution)", layer: "L3" },
  { id: "hi-rag", name: "Hi-RAG v2", group: "consumer", role: "Consumer (retrieval)", layer: "L4" },
  { id: "discord", name: "Publisher-Discord", group: "consumer", role: "Consumer (notify)", layer: "L4" },
  { id: "hyperdim", name: "Hyperdimensions", group: "consumer", role: "Consumer (3D viz)", layer: "L2.5" },
  { id: "shapestore", name: "ShapeStore", group: "both", role: "Persistence", layer: "L5" },
  { id: "neo4j", name: "Neo4j", group: "surface", role: "Adsorption surface", layer: "L5" },
  { id: "clickhouse", name: "ClickHouse + Prometheus", group: "gap", role: "Squeeze-film gap", layer: "L*" },
  { id: "tensorzero", name: "TensorZero", group: "matcher", role: "Impedance matcher", layer: "L4" },
];

const BUS_LINKS = [
  { source: "deepresearch", target: "nats", subject: "tokenism.cgp.ready.v1" },
  { source: "supaserch", target: "nats", subject: "tokenism.cgp.ready.v1" },
  { source: "flute", target: "nats", subject: "tokenism.geometry.event.v1" },
  { source: "tokenism", target: "nats", subject: "tokenism.cgp.weekly.v1" },
  { source: "nats", target: "hi-rag", subject: "tokenism.cgp.ready.v1" },
  { source: "nats", target: "discord", subject: "tokenism.attribution.recorded.v1" },
  { source: "nats", target: "hyperdim", subject: "geometry.event.v1" },
  { source: "nats", target: "shapestore", subject: "geometry.cgp.v1" },
  { source: "agent-zero", target: "nats", subject: "agent.tool.executed.v1" },
  { source: "chit", target: "agent-zero", subject: "binds lattice" },
  { source: "chit", target: "neo4j", subject: "binds graph" },
  { source: "chit", target: "clickhouse", subject: "binds gap" },
  { source: "chit", target: "tensorzero", subject: "binds matcher" },
  { source: "agent-zero", target: "tensorzero", subject: "MCP route" },
  { source: "tensorzero", target: "hi-rag", subject: "embed/route" },
  { source: "hi-rag", target: "neo4j", subject: "graph index" },
  { source: "hi-rag", target: "clickhouse", subject: "trace read" },
];

// --- Agent classes (PMOVES_AGENT_CLASS_TAXONOMY.md §1) ---
const AGENT_CLASSES = [
  {
    cls: "Legendary",
    prefix: "POWERFULMOVES",
    role: "Org/brand umbrella, doctrine, foundational systems",
    pokemon: "Mewtwo, Arceus",
    examples: ["POWERFULMOVES/PMOVES.AI"],
  },
  {
    cls: "Standard",
    prefix: "PMOVES-",
    role: "Core production agents — the team you deploy",
    pokemon: "Pikachu, Charizard",
    examples: [
      "PMOVES-Agent-Zero",
      "PMOVES-Archon",
      "PMOVES-HiRAG",
      "PMOVES-BoTZ",
      "PMOVES-Deep-Serch",
      "PMOVES.YT",
    ],
  },
  {
    cls: "Specialized",
    prefix: "Pmoves-",
    role: "Domain-specific agents with focused capabilities",
    pokemon: "Alolan / Galarian regional variants",
    examples: ["Pmoves-hyperdimensions", "Pmoves-cipher", "Pmoves-Health-wger"],
  },
  {
    cls: "Utility",
    prefix: "pmoves-",
    role: "Infrastructure components, helpers, tools",
    pokemon: "Items, Minicons",
    examples: ["pmoves-surf", "pmoves-e2b-mcp-server", "pmoves/tools/*"],
  },
];

// --- 7 service types (§2) ---
const AGENT_TYPES = [
  { type: "Data", tier: 1, element: "Earth", color: "#6E522B", strengths: "Persistence, durability", weaknesses: "Latency, migration complexity" },
  { type: "API", tier: 2, element: "Water", color: "#006494", strengths: "Routing, gateway, protocol bridging", weaknesses: "Stateless, no memory" },
  { type: "LLM", tier: 3, element: "Fire", color: "#A13544", strengths: "Reasoning, generation, comprehension", weaknesses: "Cost, hallucination, latency" },
  { type: "Worker", tier: 4, element: "Electric", color: "#D19900", strengths: "Processing, transformation, speed", weaknesses: "GPU-hungry, narrow focus" },
  { type: "Media", tier: 5, element: "Wind", color: "#A78BFA", strengths: "Multimodal, ingestion, streaming", weaknesses: "Heavy I/O, format complexity" },
  { type: "Agent", tier: 6, element: "Psychic", color: "#7A39BB", strengths: "Orchestration, planning, delegation", weaknesses: "Coordination overhead" },
  { type: "UI", tier: 7, element: "Light", color: "#BCE2E7", strengths: "Visualization, interaction, feedback", weaknesses: "Client-side state" },
];

// --- Roster (subset from §2 Type Chart) used for the type-graph ---
const AGENT_ROSTER = [
  { name: "Agent Zero", cls: "Standard", primary: "Agent", secondary: "API", tier: 6, stage: "Mega", layers: 7 },
  { name: "Archon", cls: "Standard", primary: "Agent", secondary: "LLM", tier: 6, stage: "Stage 2", layers: 6 },
  { name: "Hi-RAG v2", cls: "Standard", primary: "Worker", secondary: "Data", tier: 4, stage: "Stage 2", layers: 5 },
  { name: "DeepResearch", cls: "Standard", primary: "LLM", secondary: "Worker", tier: 3, stage: "Stage 1", layers: 4 },
  { name: "SupaSerch", cls: "Standard", primary: "Agent", secondary: "LLM", tier: 6, stage: "Stage 2", layers: 5 },
  { name: "PMOVES.YT", cls: "Standard", primary: "Media", secondary: "Worker", tier: 5, stage: "Stage 1", layers: 4 },
  { name: "Flute-Gateway", cls: "Standard", primary: "API", secondary: "Media", tier: 2, stage: "Stage 1", layers: 4 },
  { name: "TensorZero Gateway", cls: "Standard", primary: "API", secondary: "LLM", tier: 2, stage: "Stage 1", layers: 3 },
  { name: "ClaWZ", cls: "Standard", primary: "Agent", secondary: "API", tier: 6, stage: "Stage 1", layers: 4 },
  { name: "Cipher Memory", cls: "Specialized", primary: "Data", secondary: "Agent", tier: 1, stage: "Base", layers: 2 },
  { name: "Hyperdimensions", cls: "Specialized", primary: "UI", secondary: "Data", tier: 7, stage: "Base", layers: 2 },
  { name: "Extract Worker", cls: "Standard", primary: "Worker", secondary: "Data", tier: 4, stage: "Stage 1", layers: 4 },
  { name: "EvoSwarm Controller", cls: "Standard", primary: "Worker", secondary: "Agent", tier: 4, stage: "Stage 1", layers: 4 },
  { name: "Swarm Attribution", cls: "Specialized", primary: "Worker", secondary: "Data", tier: 4, stage: "Stage 1", layers: 4 },
  { name: "Mesh Agent", cls: "Standard", primary: "Agent", secondary: "Data", tier: 6, stage: "Stage 1", layers: 4 },
  { name: "Channel Monitor", cls: "Standard", primary: "Worker", secondary: "Media", tier: 4, stage: "Base", layers: 2 },
  { name: "BoTZ Gateway", cls: "Standard", primary: "Agent", secondary: "Worker", tier: 6, stage: "Stage 1", layers: 4 },
  { name: "MAI-UI", cls: "Standard", primary: "UI", secondary: "Agent", tier: 7, stage: "Stage 1", layers: 3 },
];

// --- Evolution stages (§4) ---
const EVOLUTION_STAGES = [
  { stage: "Base", req: "Single type, 1–2 layers", analogy: "Unevolved Pokémon / Minicon", example: "Presign (API, L0 only)" },
  { stage: "Stage 1", req: "Multi-layer (3–4), NATS connected", analogy: "First evolution / Warrior", example: "Extract Worker (L0+L2+L4+L5)" },
  { stage: "Stage 2", req: "CHIT-enabled (CGP packets), 5+ layers", analogy: "Second evolution / Triple-changer", example: "Hi-RAG v2 (5 layers + geometry endpoint)" },
  { stage: "Mega", req: "Full-stack across all 5 planes", analogy: "Mega evolution / Combiner gestalt", example: "Agent Zero (all 7 layers)" },
];

// --- Layers L0–L5 (PMOVES_AGENT_CLASS_TAXONOMY.md §3; unified taxonomy deprecated) ---
const LAYERS = [
  { id: "L0", name: "Identity Anchors", desc: "325 persona anchors, grounding", agents: "All agents (via persona config)" },
  { id: "L1", name: "Orchestrators", desc: "Control-plane coordination", agents: "Agent Zero, Archon" },
  { id: "L2", name: "Bus + Routing", desc: "NATS transport, gateway routing", agents: "NATS, TensorZero, Hi-RAG" },
  { id: "L2.5", name: "Hyperdimensions", desc: "Geometry state visualization + control knobs", agents: "Hyperdimensions, CHIT" },
  { id: "L3", name: "Swarm Intelligence", desc: "EvoSwarm, role-based packs", agents: "Swarm Attribution, BoTZ (legacy)" },
  { id: "L4", name: "Modal / LLM Routing", desc: "Embeddings, TensorZero gateway routing", agents: "Hi-RAG, TensorZero" },
  { id: "L5", name: "Memory + Safety", desc: "Persistent storage, CHIT manifests, sandboxes", agents: "Cipher, Supabase, Danger Room" },
];

// --- Skill bundles (PmovesSKillZ.md) ---
const SKILLS = [
  { id: "bringup-audit", purpose: "Tiered bring-up, smoke validation, evidence capture", input: "Make targets, health endpoints, CI logs", output: "Pass/fail matrix + remediation queue" },
  { id: "secrets-chit-funnel", purpose: "Map secrets stores into CHIT manifests without cleartext commits", input: "GitHub secrets, vault labels, Supabase runtime values", output: "Synced manifest + verification report" },
  { id: "submodule-parity", purpose: "Ensure PMOVES overlays align with upstream submodule capabilities", input: ".gitmodules, integration contracts, overlay docs", output: "Parity audit + missing-mapping report" },
  { id: "persona-grounding", purpose: "Transform source materials into grounded persona anchors", input: "pmoves/docs/context artifacts + approved ingest sources", output: "Anchor mappings + persona policy metadata" },
  { id: "multimodal-verifier", purpose: "Verify tool execution using text + audio + VLM checks", input: "Logs, metrics, screenshots/video frames, service outputs", output: "Verification evidence bound to task/run id" },
];

// --- 5 canonical planes (§7) ---
const PLANES = [
  { plane: "Control", function: "Governance, orchestration, task routing", agents: "Agent Zero, Archon, BoTZ", layers: "L1, L3" },
  { plane: "Context", function: "CHIT packets, geometry, persona anchors", agents: "Hyperdimensions, CHIT modules, all CGP producers", layers: "L0, L2.5" },
  { plane: "Execution", function: "Gateway tools, service adapters, work", agents: "TensorZero, Hi-RAG, workers, media pipeline", layers: "L2, L4" },
  { plane: "Observation", function: "Logs, metrics, traces, VLM verification", agents: "Prometheus, Grafana, Loki, cAdvisor", layers: "all" },
  { plane: "Safety", function: "Secrets, signed artifacts, sandboxes", agents: "Danger Room, CHIT manifests, damage-control hooks", layers: "L5" },
];

// --- Seven design principles (PMOVES_MOF_ARCHITECTURE.md §Seven Design Principles) ---
const PRINCIPLES = [
  { id: "P1", name: "Maximize Surface Area", body: "Every execution trace should generate maximal Neo4j edges. More edges = more adsorption sites = faster skill transfer." },
  { id: "P2", name: "Tune Pore Size", body: "CHIT signature scopes provide selective permeability. A code-review agent doesn't need voice-processing visibility." },
  { id: "P3", name: "Maintain Resonance", body: "Validate NATS event schemas at ingestion. Off-resonance agents contribute noise without receiving lift." },
  { id: "P4", name: "Enable Traveling Waves", body: "Every agent gets direct NATS pub/sub beyond hierarchical parent-child. Eliminates dead spots." },
  { id: "P5", name: "Match Impedance Dynamically", body: "TensorZero fallback chains, not single-model assignments. Route to the model whose impedance matches the task." },
  { id: "P6", name: "Preserve Reversibility", body: "Every adopted skill must be git-tracked and CHIT-signed. Reversible adsorption is non-negotiable." },
  { id: "P7", name: "Optimize the Gap", body: "Tune observability retention so the gap is neither too thin (isolation) nor too thick (noise). Narrow operational window." },
];

// --- Tour steps (narrative) ---
const TOUR_STEPS = [
  {
    n: 1,
    title: "Information has shape",
    body:
      "CHIT names two things at once. As a theory — Cymatic Holographic Information Theory — it describes meaning as geometry instead of token streams: embed sentences → harvest cluster anchors → measure energy spectra → ship a tiny CGP packet, and the receiver reconstructs meaning from the shape alone. As a mechanism — Compressed Hierarchical Information Transfer — it is the signing/secrets layer that stamps every adopted skill and trail. This tour is about the theory; the mechanism shows up wherever signing does.",
    src: SOURCES.whatIsChit,
  },
  {
    n: 2,
    title: "The CGP is a star chart",
    body:
      "A CGP (CHIT Geometry Packet, spec chit.cgp.v1.0) is JSON: super_nodes ▶ constellations ▶ {anchor, spectrum, radial_minmax, points}. Two decode modes: exact (raw text in points[].text) and geometry-only (project a shared codebook onto the anchor and match the spectrum).",
    src: SOURCES.cgpSpec,
  },
  {
    n: 3,
    title: "Five mathematical pillars",
    body:
      "CHIT rests on Dirichlet attribution, hyperbolic (Poincaré) geometry, Merkle proofs, Zeta spectral filters, and EVO SWARM evolutionary consensus. You don't need the math to use CHIT — but each pillar has a reference implementation you can audit.",
    src: SOURCES.whatIsChit,
  },
  {
    n: 4,
    title: "Shapes flow on the GEOMETRY BUS",
    body:
      "CGPs ride NATS JetStream. Producers (DeepResearch, SupaSerch, Flute, ToKenism) publish to tokenism.cgp.ready.v1. Consumers (Hi-RAG v2, Discord, Hyperdimensions) subscribe and react. ShapeStore caches every CGP under a Shape ID (truncated SHA-256 hash) for 30 days of replay.",
    src: SOURCES.geometryBus,
  },
  {
    n: 5,
    title: "PMOVES is a Metal-Organic Framework",
    body:
      "ClickHouse + Prometheus = squeeze-film air gap. NATS = ultrasonic frequency driver + traveling-wave overlay. TensorZero = the dolphin's melon (impedance matcher). Neo4j = high-surface-area internal framework. Agent Zero = crystalline lattice. CHIT = the organic linker that binds them all into a framework.",
    src: SOURCES.mof,
  },
  {
    n: 6,
    title: "Agents are Pokémon",
    body:
      "Four classes by prefix: POWERFULMOVES (Legendary), PMOVES- (Standard), Pmoves- (Specialized), pmoves- (Utility). Seven types from the service catalog (Data/API/LLM/Worker/Media/Agent/UI). Dual-types create synergies — Agent Zero is Agent/API, Hi-RAG v2 is Worker/Data.",
    src: SOURCES.agentClassTax,
  },
  {
    n: 7,
    title: "Evolution by capability gain",
    body:
      "Agents level up by gaining layers: connect to NATS → L2; add CGP support → L2.5; join EvoSwarm → L3; route through TensorZero → L4; persist state → L5. Stages: Base → Stage 1 → Stage 2 → Mega. Agent Zero is Mega — all 7 layers, all 5 planes.",
    src: SOURCES.agentClassTax,
  },
  {
    n: 8,
    title: "Skill bundles operate the framework",
    body:
      "Five named skills: bringup-audit, secrets-chit-funnel, submodule-parity, persona-grounding, multimodal-verifier. Operators prefer open-chat+scout while requirements are uncertain, then switch to focus for implementation and validation.",
    src: SOURCES.skillz,
  },
  {
    n: 9,
    title: "Living docs render through Remotion + PreTeXt",
    body:
      "The A2UI Renderer consumes A2UI specs through Remotion. Text/heading blocks may opt into text_layout.engine=pretext for deterministic wrap, caption fit, and living-doc overlays. Pmoves tracks the POWERFULMOVES/Pmoves-pretext fork for ongoing alignment.",
    src: SOURCES.creator,
  },
  {
    n: 10,
    title: "The framework is the intelligence",
    body:
      "Halve the context distance between agents → quartering of flow resistance → 4× skill transfer per cycle. A fleet of small models inside a properly-architected MOF beats a single large model in isolation — not because they are smarter, but because the framework gives each one a multiplicative skill-transfer effect that no individual model can access alone.",
    src: SOURCES.mof,
  },
];

// --- NATS subjects table ---
const NATS_SUBJECTS = [
  { subject: "tokenism.cgp.ready.v1", dir: "Pub → Hi-RAG, Discord, ShapeStore", purpose: "Generic CGP packet ready" },
  { subject: "tokenism.cgp.weekly.v1", dir: "Pub → Discord, Hi-RAG", purpose: "Weekly ToKenism attribution export" },
  { subject: "tokenism.attribution.recorded.v1", dir: "Pub → Discord, analytics", purpose: "Real-time attribution notification" },
  { subject: "tokenism.geometry.event.v1", dir: "Pub → Hi-RAG", purpose: "Voice/modality attribution events" },
  { subject: "tokenism.swarm.population.v1", dir: "Pub → analytics, Discord", purpose: "EVO SWARM population state" },
  { subject: "geometry.cgp.v1", dir: "Pub → Hi-RAG (Supabase RT)", purpose: "CGP via Supabase Realtime" },
  { subject: "geometry.event.v1", dir: "Pub → ShapeStore", purpose: "Raw geometry events" },
  { subject: "geometry.swarm.meta.v1", dir: "Pub → Hi-RAG", purpose: "Decoder pack metadata for swarm" },
];

// --- assumptions / coverage ---
const COVERAGE_NOTES = [
  "The CHIT two-meaning split used throughout this tour — concept = 'Cymatic Holographic Information Theory', mechanism = 'Compressed Hierarchical Information Transfer' — is BRAND-OWNER CANON (DARKXSIDE, 2026-06-09): the deliberate reconciliation of 7 historically conflicting expansions found across the docs. The PMOVESCHIT source files still carry the older single expansion 'Cymatic-Holographic Information Transfer' pending the fleet-wide doc sweep; where this tour states the split, that is the canon speaking, not the cited file.",
  "Version currency: the CGP spec is v1.0 production-ready (CGP_v1.0_SPECIFICATION.md, 2026-02-08), but documented example payloads in geometry-nats-subjects.md still show chit.cgp.v0.1/v0.2 traffic — the spec is ahead of the recorded examples, not the other way around.",
  "Definitions and terminology are taken verbatim from pmoves/docs/PMOVESCHIT/00_GLOSSARY.md and 01_WHAT_IS_CHIT.md (CHIT, CGP, CHR, EVO SWARM, Five Pillars, GEOMETRY BUS, Poincaré Disk).",
  "MOF mappings, the Seven Design Principles, the gap-size formula, and meta-agent vs. standard-agent typology come from pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md (canonical reference, v1.0.0).",
  "Agent classes (Legendary/Standard/Specialized/Utility), 7 service types, evolution stages, CHIT toggles, and the dual-type table come from pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md (v1.5.0, 76 agents).",
  "Layer model L0–L5 (+ L2.5) and the 5 canonical planes come from pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md §3 (canonical); PMOVES_UNIFIED_AGENT_TAXONOMY.md is a deprecated historical reference.",
  "GEOMETRY BUS topology, NATS subjects, producer/consumer split, and the 30-day JetStream retention come from pmoves/docs/PMOVESCHIT/02_GEOMETRY_BUS.md.",
  "Skill bundles come from pmoves/docs/AGENTS/PmovesSKillZ.md (five skills: bringup-audit, secrets-chit-funnel, submodule-parity, persona-grounding, multimodal-verifier).",
  "Remotion + PreTeXt + Living Docs references come from pmoves/docs/CREATOR_PIPELINE.md (A2UI Renderer, @chenglou/pretext, POWERFULMOVES/Pmoves-pretext fork).",
  "AGNOTE4482.md was treated as situational/log context, not a definitional source. Definitive CHIT and taxonomy claims are taken from PMOVESCHIT/* and AGENTS/* docs.",
  "The agent roster shown in the type graph is a representative subset (~18 of 76 agents). The single source of truth is pmoves/config/agent_registry.yaml. Numeric layer counts shown in the roster are read from the §3 Agent Layer Coverage Map.",
  "Visualisations: the D3 force graph is a hand-curated topology derived from the Geometry Bus diagram and §5 Connection Topology. The Three.js Poincaré disk is illustrative — it shows hyperbolic-disk hierarchy semantics from Pillar 2; coordinates are not a literal export of Pmoves-hyperdimensions/saves/agent_topology.json.",
];

// =============================================================================
// TOKENOMICS LAYER — finance/business projections data
// All values copied verbatim from the projection CSVs in CATACLYSM_STUDIOS_INC/
// L4-PLATFORM/projections/data/. See SOURCES.tokenomics* for exact paths.
// =============================================================================

// 5-year cumulative profit per business model (from ai_tokenomics_business_projections.csv).
// Years 2025–2029. We keep four representative archetypes — the four other models
// (Local Food Network, AI Tutoring, Digital Art/NFT, Urban Agriculture) share the
// same Community-Token base trajectory in the source CSV, so we collapse them
// into the "Community Token Pre-Order System" series and call out the duplication
// in the assumptions panel.
const TOKENOMICS_PROJECTIONS = [
  {
    model: "AI-Enhanced Local Service Business",
    investment: 5000,
    successProb: 0.75,
    cumulative: [7750, 19241, 35791, 59053, 91050],
    revenue: [25000, 35688, 50142, 69321, 94277],
    netProfit: [7750, 11491, 16550, 23262, 31997],
    roiPct: [155.0, 384.8, 715.8, 1181.1, 1821.0],
  },
  {
    model: "Sustainable Energy AI Consulting",
    investment: 4000,
    successProb: 0.6,
    cumulative: [5200, 12566, 22725, 36423, 54529],
    revenue: [20000, 27220, 36529, 48328, 63020],
    netProfit: [5200, 7366, 10159, 13698, 18106],
    roiPct: [130.0, 314.2, 568.1, 910.6, 1363.2],
  },
  {
    model: "Community Token Pre-Order System",
    investment: 3000,
    successProb: 0.4,
    cumulative: [3150, 7191, 12276, 18568, 26239],
    revenue: [15000, 18562, 22738, 27570, 33084],
    netProfit: [3150, 4041, 5085, 6292, 7671],
    roiPct: [105.0, 239.7, 409.2, 618.9, 874.6],
  },
  {
    model: "Creative Content + Token Rewards",
    investment: 3000,
    successProb: 0.4,
    cumulative: [3150, 7191, 12276, 18568, 26239],
    revenue: [15000, 18562, 22738, 27570, 33084],
    netProfit: [3150, 4041, 5085, 6292, 7671],
    roiPct: [105.0, 239.7, 409.2, 618.9, 874.6],
  },
];
const TOKENOMICS_YEARS = [2025, 2026, 2027, 2028, 2029];

// Breakeven analysis — months to recoup initial investment under three scenarios
// Source: breakeven_analysis.csv
const BREAKEVEN = [
  { model: "AI-Enhanced Local Service",     investment: 5000, optimistic: 3.3, realistic: 4.7, conservative:  8.2, p: 0.75 },
  { model: "Sustainable Energy AI",         investment: 4000, optimistic: 4.4, realistic: 6.3, conservative: 11.0, p: 0.60 },
  { model: "Community Token Pre-Order",     investment: 3000, optimistic: 6.9, realistic: 9.8, conservative: 17.2, p: 0.40 },
  { model: "Creative Content + Tokens",     investment: 3000, optimistic: 6.9, realistic: 9.8, conservative: 17.2, p: 0.40 },
];

// Risk-weighted scenario expected value (from scenario_analysis.csv).
// Each row collapses four scenarios into a single Expected_Value (sum of
// scenario_probability × adjusted_roi × success_rate × investment).
const SCENARIOS = [
  {
    model: "AI-Enhanced Local Service",
    investment: 5000,
    rows: [
      { name: "Bull market + high AI adoption",   p: 0.25, adjROI: 2731.5, succ: 0.95, riskAdj: 2594.9, ev: 648.7 },
      { name: "Normal growth",                    p: 0.50, adjROI: 1821.0, succ: 0.75, riskAdj: 1365.8, ev: 682.9 },
      { name: "Economic downturn",                p: 0.20, adjROI: 1092.6, succ: 0.50, riskAdj:  546.3, ev: 109.3 },
      { name: "Crypto winter + AI skepticism",    p: 0.05, adjROI:  728.4, succ: 0.40, riskAdj:  291.4, ev:  14.6 },
    ],
  },
  {
    model: "Sustainable Energy AI",
    investment: 4000,
    rows: [
      { name: "Bull market + high AI adoption",   p: 0.25, adjROI: 2044.8, succ: 0.80, riskAdj: 1635.8, ev: 409.0 },
      { name: "Normal growth",                    p: 0.50, adjROI: 1363.2, succ: 0.60, riskAdj:  817.9, ev: 409.0 },
      { name: "Economic downturn",                p: 0.20, adjROI:  817.9, succ: 0.35, riskAdj:  286.3, ev:  57.3 },
      { name: "Crypto winter + AI skepticism",    p: 0.05, adjROI:  545.3, succ: 0.25, riskAdj:  136.3, ev:   6.8 },
    ],
  },
  {
    model: "Community Token Pre-Order",
    investment: 3000,
    rows: [
      { name: "Bull market + high AI adoption",   p: 0.25, adjROI: 1311.9, succ: 0.60, riskAdj:  787.1, ev: 196.8 },
      { name: "Normal growth",                    p: 0.50, adjROI:  874.6, succ: 0.40, riskAdj:  349.8, ev: 174.9 },
      { name: "Economic downturn",                p: 0.20, adjROI:  524.8, succ: 0.15, riskAdj:   78.7, ev:  15.7 },
      { name: "Crypto winter + AI skepticism",    p: 0.05, adjROI:  349.8, succ: 0.10, riskAdj:   35.0, ev:   1.7 },
    ],
  },
  {
    model: "Creative Content + Tokens",
    investment: 3000,
    rows: [
      { name: "Bull market + high AI adoption",   p: 0.25, adjROI: 1311.9, succ: 0.60, riskAdj:  787.1, ev: 196.8 },
      { name: "Normal growth",                    p: 0.50, adjROI:  874.6, succ: 0.40, riskAdj:  349.8, ev: 174.9 },
      { name: "Economic downturn",                p: 0.20, adjROI:  524.8, succ: 0.15, riskAdj:   78.7, ev:  15.7 },
      { name: "Crypto winter + AI skepticism",    p: 0.05, adjROI:  349.8, succ: 0.10, riskAdj:   35.0, ev:   1.7 },
    ],
  },
];

// Containerized "Docker-style" micro-business scaling.
// Source: micro_business_container_scaling.csv. ROI grows with replication
// because fixed costs are diluted across copies.
const CONTAINER_SCALING = [
  { container: "Token-Rewards-Platform",      scales: [1, 3, 5, 10], roi: [216.0, 421.2, 576.0, 922.9], invest: [12000, 24000, 36000,  66000], payback: [5.6, 2.8, 2.1, 1.3] },
  { container: "Community-Shuttle-Network",   scales: [1, 3, 5, 10], roi: [164.6, 299.5, 400.7, 629.6], invest: [35000, 75000, 115000, 215000], payback: [7.3, 4.0, 3.0, 1.9] },
  { container: "Neighborhood-Food-Hub",       scales: [1, 3, 5, 10], roi: [190.0, 317.6, 414.5, 637.9], invest: [18000, 42000,  66000, 126000], payback: [6.3, 3.8, 2.9, 1.9] },
  { container: "Security-Delivery-Hub",       scales: [1, 3, 5, 10], roi: [142.8, 253.1, 336.0, 524.3], invest: [25000, 55000,  85000, 160000], payback: [8.4, 4.7, 3.6, 2.3] },
  { container: "Bulk-Purchase-Cooperative",   scales: [1, 3, 5, 10], roi: [124.0, 234.0, 316.6, 502.4], invest: [15000, 31000,  47000,  87000], payback: [9.7, 5.1, 3.8, 2.4] },
];

// Aggregated community-economic-impact projections at three participation rates.
// Source: community_economic_impact.csv.
const COMMUNITY_IMPACT = [
  { scenario: "Conservative · 10% participation", participants:  5500, totalInvest:  8250000, incomeIncrease:  49293675, multiplier: 2.24, totalImpact: 110417832, communityROI: 1338.4 },
  { scenario: "Moderate · 25% participation",     participants: 13750, totalInvest: 20625000, incomeIncrease: 123234187, multiplier: 2.24, totalImpact: 276044580, communityROI: 1338.4 },
  { scenario: "Optimistic · 40% participation",   participants: 22000, totalInvest: 33000000, incomeIncrease: 197174700, multiplier: 2.24, totalImpact: 441671328, communityROI: 1338.4 },
];

// Roll-out timeline. Source: implementation_phases_timeline.csv.
const ROLLOUT_PHASES = [
  { phase: "Phase 1 — MVP (M1–3)",            months: "1–3",   container: "Token-Rewards-Platform",       invest:  12000, cumulative:  12000, residents:  150 },
  { phase: "Phase 2 — Service Integration (M4–8)",  months: "4–8",   container: "Security-Delivery-Hub",        invest:  25000, cumulative:  37000, residents:  450 },
  { phase: "Phase 3 — Network Effects (M9–15)",     months: "9–15",  container: "Community-Shuttle-Network",    invest:  35000, cumulative:  72000, residents:  950 },
  { phase: "Phase 4 — Ecosystem Expansion (M16–24)", months: "16–24", container: "Multi-Container-Orchestration", invest:  50000, cumulative: 122000, residents: 1700 },
];

// CHIT linkage: how the agent registry + CHIT primitives map to each tokenomics
// primitive. These mappings come directly from the agent_registry.yaml service
// catalog (Worker/Agent/Data tiers) and the CHIT pillar definitions in
// PMOVESCHIT/01_WHAT_IS_CHIT.md.
const CHIT_TOKENOMICS_LINK = [
  { primitive: "Pre-order tokens",        chitRole: "Dirichlet weights split future revenue across pre-order contributors with non-zero attribution.", agent: "tokenism.cgp.ready.v1 (CHIT) → Hi-RAG v2" },
  { primitive: "Container replication",   chitRole: "Each container publishes a CGP shape; ShapeStore caches it; replicas inherit the same Shape ID.",  agent: "Token-Rewards-Platform agent → ShapeStore" },
  { primitive: "Cross-business synergy",  chitRole: "Hyperbolic embedding (Pillar 2) keeps related containers near each other in the agent topology.",  agent: "Pmoves-hyperdimensions" },
  { primitive: "Attribution settlement",  chitRole: "Merkle proofs (Pillar 3) make every weekly attribution export tamper-evident before payout.",      agent: "tokenism.cgp.weekly.v1 → Discord/analytics" },
  { primitive: "Risk-adjusted scoring",   chitRole: "Zeta spectral filter (Pillar 4) separates persistent revenue signals from one-off spikes.",        agent: "EVO SWARM consensus" },
];
// REAL agent taxonomy tree — extracted verbatim from pmoves/config/agent_registry.yaml
// (taxonomy_version 1.5.0, 96 agents, extracted 2026-07-26). NOT hand-curated.
const AGENT_TREE = {
 "taxonomyVersion": "1.5.0",
 "agentCount": 96,
 "source": "pmoves/config/agent_registry.yaml",
 "extractedUtc": "2026-07-26",
 "tree": {
  "standard": {
   "agent": [
    {
     "id": "agent_zero",
     "name": "Agent Zero"
    },
    {
     "id": "kilocode_glm",
     "name": "KiloCode GLM"
    },
    {
     "id": "space_agent",
     "name": "PMOVES Space-Agent"
    },
    {
     "id": "archon",
     "name": "Archon"
    },
    {
     "id": "supaserch",
     "name": "SupaSerch"
    },
    {
     "id": "botz_gateway",
     "name": "BoTZ Gateway"
    },
    {
     "id": "botz_architect",
     "name": "BoTZ Architect"
    },
    {
     "id": "botz_builder",
     "name": "BoTZ Builder"
    },
    {
     "id": "botz_auditor",
     "name": "BoTZ Auditor"
    },
    {
     "id": "gateway_agent",
     "name": "Gateway Agent"
    },
    {
     "id": "p7_room_orchestrator",
     "name": "P7 Room Orchestrator"
    },
    {
     "id": "mesh_agent",
     "name": "Mesh Agent"
    },
    {
     "id": "agentgym",
     "name": "AgentGym"
    },
    {
     "id": "e2b_danger_room",
     "name": "E2B Danger Room"
    },
    {
     "id": "notebooklm_agent",
     "name": "NotebookLM Agent"
    }
   ],
   "worker": [
    {
     "id": "hirag_v2",
     "name": "Hi-RAG v2"
    },
    {
     "id": "extract_worker",
     "name": "Extract Worker"
    },
    {
     "id": "channel_monitor",
     "name": "Channel Monitor"
    },
    {
     "id": "notebook_sync",
     "name": "Notebook Sync"
    },
    {
     "id": "pdf_ingest",
     "name": "PDF Ingest"
    },
    {
     "id": "publisher_discord",
     "name": "Publisher-Discord"
    },
    {
     "id": "langextract",
     "name": "LangExtract"
    },
    {
     "id": "dox",
     "name": "DoX"
    },
    {
     "id": "evoswarm_controller",
     "name": "EvoSwarm Controller"
    }
   ],
   "llm": [
    {
     "id": "deep_research",
     "name": "DeepResearch"
    }
   ],
   "api": [
    {
     "id": "tensorzero",
     "name": "TensorZero Gateway"
    },
    {
     "id": "flute_gateway",
     "name": "Flute-Gateway"
    }
   ],
   "media": [
    {
     "id": "cast_tts_gateway",
     "name": "Cast TTS Gateway"
    },
    {
     "id": "pmoves_yt",
     "name": "PMOVES.YT"
    },
    {
     "id": "ffmpeg_whisper",
     "name": "FFmpeg-Whisper"
    },
    {
     "id": "media_video",
     "name": "Media-Video Analyzer"
    },
    {
     "id": "media_audio",
     "name": "Media-Audio Analyzer"
    },
    {
     "id": "ultimate_tts",
     "name": "Ultimate-TTS-Studio"
    },
    {
     "id": "creator",
     "name": "Creator"
    },
    {
     "id": "podcast_producer",
     "name": "Podcast Producer"
    },
    {
     "id": "remotion_renderer",
     "name": "Remotion Renderer"
    },
    {
     "id": "youtube_publisher",
     "name": "YouTube Publisher"
    }
   ],
   "ui": [
    {
     "id": "mai_ui",
     "name": "MAI-UI"
    },
    {
     "id": "crush",
     "name": "Crush"
    },
    {
     "id": "a2ui",
     "name": "A2UI"
    },
    {
     "id": "e2b_desktop",
     "name": "E2B Desktop"
    },
    {
     "id": "clawz",
     "name": "ClawZ (OpenClaw)"
    }
   ],
   "data": [
    {
     "id": "open_notebook",
     "name": "Open Notebook"
    }
   ]
  },
  "specialized": {
   "agent": [
    {
     "id": "darkxside_persona",
     "name": "DARKXSIDE Persona"
    },
    {
     "id": "consciousness_service",
     "name": "Consciousness Service"
    },
    {
     "id": "agentgym_rl",
     "name": "AgentGym RL"
    },
    {
     "id": "fordham_steward",
     "name": "Fordham Steward"
    },
    {
     "id": "fordham_onboarding",
     "name": "Fordham Onboarding"
    },
    {
     "id": "fordham_transaction",
     "name": "Fordham Transaction"
    },
    {
     "id": "fordham_creator",
     "name": "Fordham Creator"
    },
    {
     "id": "fordham_voice",
     "name": "Fordham Voice"
    },
    {
     "id": "nemoclaw",
     "name": "NeMo Claw"
    },
    {
     "id": "nemotron_claw",
     "name": "Nemotron Claw"
    },
    {
     "id": "hf_agent",
     "name": "HF Agent"
    },
    {
     "id": "hf_research_agent",
     "name": "HF Research Agent"
    }
   ],
   "media": [
    {
     "id": "jellyfin_bridge",
     "name": "Jellyfin Bridge"
    },
    {
     "id": "transcribe_and_fetch",
     "name": "Transcribe and Fetch"
    },
    {
     "id": "jellyfin_ai",
     "name": "Jellyfin AI Media Stack"
    },
    {
     "id": "cipher_beats_analyst",
     "name": "Cipher Beats Analyst"
    }
   ],
   "data": [
    {
     "id": "cipher_memory",
     "name": "Cipher Memory"
    },
    {
     "id": "metrics_specialist",
     "name": "Prometheus Metrics Specialist"
    },
    {
     "id": "logs_specialist",
     "name": "Loki Logs Specialist"
    },
    {
     "id": "tracing_specialist",
     "name": "Jaeger Tracing Specialist"
    }
   ],
   "ui": [
    {
     "id": "hyperdimensions",
     "name": "Hyperdimensions"
    },
    {
     "id": "wealth",
     "name": "Wealth (Firefly III)"
    },
    {
     "id": "health",
     "name": "Health (wger)"
    },
    {
     "id": "dashboard_specialist",
     "name": "Grafana Dashboard Specialist"
    }
   ],
   "worker": [
    {
     "id": "swarm_attribution",
     "name": "Swarm Attribution"
    }
   ],
   "llm": [
    {
     "id": "llama_lab",
     "name": "Llama Throughput Lab"
    },
    {
     "id": "autoresearch",
     "name": "autoresearch"
    },
    {
     "id": "llm_observability",
     "name": "TensorZero LLM Observability Specialist"
    }
   ]
  },
  "utility": {
   "api": [
    {
     "id": "presign",
     "name": "Presign"
    },
    {
     "id": "render_webhook",
     "name": "Render Webhook"
    },
    {
     "id": "vps_fleet_manager",
     "name": "VPS Fleet Manager"
    }
   ],
   "worker": [
    {
     "id": "pr_hedge_trim",
     "name": "PR Hedge Trim"
    },
    {
     "id": "n8n",
     "name": "n8n"
    },
    {
     "id": "danger_infra",
     "name": "Danger Infra"
    }
   ],
   "data": [
    {
     "id": "nats",
     "name": "NATS"
    },
    {
     "id": "supabase",
     "name": "Supabase"
    },
    {
     "id": "qdrant",
     "name": "Qdrant"
    },
    {
     "id": "neo4j",
     "name": "Neo4j"
    },
    {
     "id": "meilisearch",
     "name": "Meilisearch"
    },
    {
     "id": "minio",
     "name": "MinIO"
    },
    {
     "id": "prometheus",
     "name": "Prometheus"
    },
    {
     "id": "loki",
     "name": "Loki"
    },
    {
     "id": "headscale",
     "name": "Headscale"
    }
   ],
   "ui": [
    {
     "id": "grafana",
     "name": "Grafana"
    },
    {
     "id": "rustdesk",
     "name": "RustDesk"
    },
    {
     "id": "invidious",
     "name": "Invidious"
    }
   ],
   "agent": [
    {
     "id": "surf",
     "name": "Surf"
    },
    {
     "id": "e2b_spells",
     "name": "E2B Spells"
    },
    {
     "id": "a0_plugins",
     "name": "a0-plugins"
    },
    {
     "id": "pmoves_e2b_mcp_server",
     "name": "E2B MCP Server"
    },
    {
     "id": "hermes_agent",
     "name": "HERMES Agent"
    },
    {
     "id": "container_agent",
     "name": "Container Agent"
    }
   ]
  },
  "ci": {
   "ci": [
    {
     "id": "pmoves_ci_bot",
     "name": "PMOVES CI Bot"
    }
   ]
  }
 }
};
