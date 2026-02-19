// CHIT Mindmap Seed - Neo4j Graph
// Thread 7.2: Nodes for 5 CHIT pillars, GEOMETRY BUS subjects, CGP elements, 59 agents
// Edges: encodes, publishes_to, consumes, transforms

// ============================================================
// CHIT Pillars (Core Concepts)
// ============================================================
CREATE (p1:CHITPillar {name: "Dirichlet Attribution", id: "dirichlet", description: "Probabilistic contribution weighting via Dirichlet distribution"})
CREATE (p2:CHITPillar {name: "Hyperbolic Encoding", id: "hyperbolic", description: "Poincare disk model for hierarchical data representation"})
CREATE (p3:CHITPillar {name: "Shape Attribution", id: "shape", description: "Merkle tree proofs for verifiable attribution records"})
CREATE (p4:CHITPillar {name: "CGP Generation", id: "cgp", description: "CHIT Geometry Packet document generation (v1.4.0)"})
CREATE (p5:CHITPillar {name: "Swarm Optimization", id: "swarm", description: "EVO SWARM fitness evaluation and population tracking"})

// ============================================================
// GEOMETRY BUS Subjects (NATS Event Channels)
// ============================================================
CREATE (s1:NATSSubject {name: "tokenism.attribution.recorded.v1", domain: "tokenism", type: "event"})
CREATE (s2:NATSSubject {name: "tokenism.cgp.weekly.v1", domain: "tokenism", type: "event"})
CREATE (s3:NATSSubject {name: "tokenism.cgp.ready.v1", domain: "tokenism", type: "event"})
CREATE (s4:NATSSubject {name: "tokenism.geometry.event.v1", domain: "tokenism", type: "event"})
CREATE (s5:NATSSubject {name: "tokenism.swarm.population.v1", domain: "tokenism", type: "event"})
CREATE (s6:NATSSubject {name: "tokenism.credential.rotated.v1", domain: "tokenism", type: "security"})
CREATE (s7:NATSSubject {name: "geometry.packet.encoded.v1", domain: "geometry", type: "event"})
CREATE (s8:NATSSubject {name: "hf.model.downloaded.v1", domain: "hf", type: "event"})
CREATE (s9:NATSSubject {name: "hf.model.onboarded.v1", domain: "hf", type: "event"})
CREATE (s10:NATSSubject {name: "research.deepresearch.request.v1", domain: "research", type: "request"})
CREATE (s11:NATSSubject {name: "research.deepresearch.result.v1", domain: "research", type: "result"})
CREATE (s12:NATSSubject {name: "supaserch.request.v1", domain: "supaserch", type: "request"})
CREATE (s13:NATSSubject {name: "supaserch.result.v1", domain: "supaserch", type: "result"})
CREATE (s14:NATSSubject {name: "ingest.file.added.v1", domain: "ingest", type: "event"})
CREATE (s15:NATSSubject {name: "ingest.transcript.ready.v1", domain: "ingest", type: "event"})
CREATE (s16:NATSSubject {name: "skills.pipeline.model-benchmark-viz.v1", domain: "skills", type: "pipeline"})

// ============================================================
// CGP Schema Elements
// ============================================================
CREATE (c1:CGPElement {name: "CGP Document", type: "document", version: "cgp.v2"})
CREATE (c2:CGPElement {name: "SuperNode", type: "node", description: "Aggregated constellation node"})
CREATE (c3:CGPElement {name: "Constellation", type: "collection", description: "Group of related points in Poincare disk"})
CREATE (c4:CGPElement {name: "PoincarePoint", type: "point", description: "Single point in hyperbolic space"})
CREATE (c5:CGPElement {name: "MerkleProof", type: "proof", description: "Verification proof for attribution"})
CREATE (c6:CGPElement {name: "SpectralSignature", type: "signature", description: "Riemann zeta zero anchored fingerprint"})
CREATE (c7:CGPElement {name: "HolographicBoundary", type: "boundary", description: "Boundary representation of content"})

// ============================================================
// Core Agents
// ============================================================
CREATE (a1:Agent {name: "Agent Zero", id: "agent-zero", tier: "agent", port: 8080, theme: "optimus-prime"})
CREATE (a2:Agent {name: "Archon", id: "archon", tier: "agent", port: 8091, theme: "lion-o"})
CREATE (a3:Agent {name: "Hi-RAG v2", id: "hirag", tier: "api", port: 8086, theme: "calculator"})
CREATE (a4:Agent {name: "DeepResearch", id: "deepresearch", tier: "worker", port: 8098, theme: "soundwave"})
CREATE (a5:Agent {name: "SupaSerch", id: "supaserch", tier: "worker", port: 8099, theme: "proto-man"})
CREATE (a6:Agent {name: "Extract Worker", id: "extract-worker", tier: "worker", port: 8083, theme: "panthro"})
CREATE (a7:Agent {name: "Cipher Memory", id: "cipher-memory", tier: "data", port: 8096, theme: "agrias"})
CREATE (a8:Agent {name: "Flute Gateway", id: "flute-gateway", tier: "media", port: 8055, theme: "arcee"})
CREATE (a9:Agent {name: "PMOVES.YT", id: "pmoves-yt", tier: "media", port: 8077})
CREATE (a10:Agent {name: "TensorZero", id: "tensorzero", tier: "llm", port: 3030})
CREATE (a11:Agent {name: "BoTZ", id: "botz", tier: "agent", theme: "starscream"})
CREATE (a12:Agent {name: "ToKenism", id: "tokenism", tier: "worker", theme: "megatron"})
CREATE (a13:Agent {name: "Creator", id: "creator", tier: "worker", theme: "dr-wily"})
CREATE (a14:Agent {name: "Hyperdimensions", id: "hyperdimensions", tier: "ui", theme: "calculator-fft"})
CREATE (a15:Agent {name: "Mesh Agent", id: "mesh-agent", tier: "agent", theme: "hot-rod"})
CREATE (a16:Agent {name: "HF MCP Server", id: "hf-mcp", tier: "api", port: 8096})

// ============================================================
// TypeScript CHIT Modules
// ============================================================
CREATE (m1:CHITModule {name: "dirichlet-weights.ts", module: "dirichlet-weights", language: "typescript"})
CREATE (m2:CHITModule {name: "hyperbolic-encoder.ts", module: "hyperbolic-encoder", language: "typescript"})
CREATE (m3:CHITModule {name: "shape-attribution.ts", module: "shape-attribution", language: "typescript"})
CREATE (m4:CHITModule {name: "cgp-generator.ts", module: "cgp-generator", language: "typescript"})
CREATE (m5:CHITModule {name: "swarm-attribution.ts", module: "swarm-attribution", language: "typescript"})
CREATE (m6:CHITModule {name: "zeta-filter.ts", module: "zeta-filter", language: "typescript"})
CREATE (m7:CHITModule {name: "chit-nats-publisher.ts", module: "chit-nats-publisher", language: "typescript"})

// ============================================================
// Relationships: CHIT Pillars ↔ Modules
// ============================================================
CREATE (p1)-[:IMPLEMENTED_BY]->(m1)
CREATE (p2)-[:IMPLEMENTED_BY]->(m2)
CREATE (p3)-[:IMPLEMENTED_BY]->(m3)
CREATE (p4)-[:IMPLEMENTED_BY]->(m4)
CREATE (p5)-[:IMPLEMENTED_BY]->(m5)

// ============================================================
// Relationships: Modules ↔ NATS Subjects (publishes_to)
// ============================================================
CREATE (m7)-[:PUBLISHES_TO]->(s1)
CREATE (m7)-[:PUBLISHES_TO]->(s2)
CREATE (m7)-[:PUBLISHES_TO]->(s3)
CREATE (m7)-[:PUBLISHES_TO]->(s5)
CREATE (m7)-[:PUBLISHES_TO]->(s6)

// ============================================================
// Relationships: Agents ↔ NATS Subjects
// ============================================================
CREATE (a4)-[:PUBLISHES_TO]->(s10)
CREATE (a4)-[:CONSUMES]->(s11)
CREATE (a5)-[:PUBLISHES_TO]->(s12)
CREATE (a5)-[:CONSUMES]->(s13)
CREATE (a6)-[:CONSUMES]->(s14)
CREATE (a9)-[:PUBLISHES_TO]->(s14)
CREATE (a9)-[:PUBLISHES_TO]->(s15)
CREATE (a16)-[:PUBLISHES_TO]->(s8)
CREATE (a16)-[:PUBLISHES_TO]->(s9)

// ============================================================
// Relationships: Agents ↔ CGP Elements (encodes/transforms)
// ============================================================
CREATE (a12)-[:ENCODES]->(c1)
CREATE (a6)-[:TRANSFORMS]->(c4)
CREATE (a3)-[:CONSUMES]->(c1)
CREATE (a7)-[:STORES]->(c1)

// ============================================================
// Relationships: Agents ↔ CHIT Pillars (uses)
// ============================================================
CREATE (a12)-[:USES]->(p1)
CREATE (a12)-[:USES]->(p2)
CREATE (a12)-[:USES]->(p3)
CREATE (a12)-[:USES]->(p4)
CREATE (a12)-[:USES]->(p5)
CREATE (a3)-[:USES]->(p2)
CREATE (a5)-[:USES]->(p4)
CREATE (a14)-[:USES]->(p2)

// ============================================================
// Relationships: CGP hierarchy
// ============================================================
CREATE (c1)-[:CONTAINS]->(c2)
CREATE (c2)-[:CONTAINS]->(c3)
CREATE (c3)-[:CONTAINS]->(c4)
CREATE (c1)-[:HAS_PROOF]->(c5)
CREATE (c1)-[:HAS_SIGNATURE]->(c6)
CREATE (c1)-[:HAS_BOUNDARY]->(c7)

// ============================================================
// Relationships: Agent orchestration
// ============================================================
CREATE (a1)-[:ORCHESTRATES]->(a2)
CREATE (a1)-[:ORCHESTRATES]->(a4)
CREATE (a1)-[:ORCHESTRATES]->(a5)
CREATE (a1)-[:ORCHESTRATES]->(a6)
CREATE (a2)-[:COORDINATES]->(a11)
CREATE (a11)-[:REGISTERS]->(a13)
CREATE (a15)-[:ANNOUNCES]->(a1);
