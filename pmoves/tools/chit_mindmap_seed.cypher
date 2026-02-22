// CHIT Mindmap Seed - Neo4j Graph
// Thread 7.2: Nodes for 5 CHIT pillars, GEOMETRY BUS subjects, CGP elements, 59 agents
// Edges: encodes, publishes_to, consumes, transforms
// Idempotent: uses MERGE + uniqueness constraints so seed can be re-run safely.

// ============================================================
// Uniqueness Constraints (idempotent — IF NOT EXISTS)
// ============================================================
CREATE CONSTRAINT chit_pillar_id IF NOT EXISTS FOR (p:CHITPillar) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT nats_subject_name IF NOT EXISTS FOR (s:NATSSubject) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT cgp_element_name IF NOT EXISTS FOR (c:CGPElement) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT chit_module_name IF NOT EXISTS FOR (m:CHITModule) REQUIRE m.module IS UNIQUE;

// ============================================================
// CHIT Pillars (Core Concepts)
// ============================================================
MERGE (p1:CHITPillar {id: "dirichlet"}) SET p1.name = "Dirichlet Attribution", p1.description = "Probabilistic contribution weighting via Dirichlet distribution";
MERGE (p2:CHITPillar {id: "hyperbolic"}) SET p2.name = "Hyperbolic Encoding", p2.description = "Poincare disk model for hierarchical data representation";
MERGE (p3:CHITPillar {id: "shape"}) SET p3.name = "Shape Attribution", p3.description = "Merkle tree proofs for verifiable attribution records";
MERGE (p4:CHITPillar {id: "cgp"}) SET p4.name = "CGP Generation", p4.description = "CHIT Geometry Packet document generation (v1.4.0)";
MERGE (p5:CHITPillar {id: "swarm"}) SET p5.name = "Swarm Optimization", p5.description = "EVO SWARM fitness evaluation and population tracking";

// ============================================================
// GEOMETRY BUS Subjects (NATS Event Channels)
// ============================================================
MERGE (s1:NATSSubject {name: "tokenism.attribution.recorded.v1"}) SET s1.domain = "tokenism", s1.type = "event";
MERGE (s2:NATSSubject {name: "tokenism.cgp.weekly.v1"}) SET s2.domain = "tokenism", s2.type = "event";
MERGE (s3:NATSSubject {name: "tokenism.cgp.ready.v1"}) SET s3.domain = "tokenism", s3.type = "event";
MERGE (s4:NATSSubject {name: "tokenism.geometry.event.v1"}) SET s4.domain = "tokenism", s4.type = "event";
MERGE (s5:NATSSubject {name: "tokenism.swarm.population.v1"}) SET s5.domain = "tokenism", s5.type = "event";
MERGE (s6:NATSSubject {name: "tokenism.credential.rotated.v1"}) SET s6.domain = "tokenism", s6.type = "security";
MERGE (s7:NATSSubject {name: "geometry.packet.encoded.v1"}) SET s7.domain = "geometry", s7.type = "event";
MERGE (s8:NATSSubject {name: "hf.model.downloaded.v1"}) SET s8.domain = "hf", s8.type = "event";
MERGE (s9:NATSSubject {name: "hf.model.onboarded.v1"}) SET s9.domain = "hf", s9.type = "event";
MERGE (s10:NATSSubject {name: "research.deepresearch.request.v1"}) SET s10.domain = "research", s10.type = "request";
MERGE (s11:NATSSubject {name: "research.deepresearch.result.v1"}) SET s11.domain = "research", s11.type = "result";
MERGE (s12:NATSSubject {name: "supaserch.request.v1"}) SET s12.domain = "supaserch", s12.type = "request";
MERGE (s13:NATSSubject {name: "supaserch.result.v1"}) SET s13.domain = "supaserch", s13.type = "result";
MERGE (s14:NATSSubject {name: "ingest.file.added.v1"}) SET s14.domain = "ingest", s14.type = "event";
MERGE (s15:NATSSubject {name: "ingest.transcript.ready.v1"}) SET s15.domain = "ingest", s15.type = "event";
MERGE (s16:NATSSubject {name: "skills.pipeline.model-benchmark-viz.v1"}) SET s16.domain = "skills", s16.type = "pipeline";

// ============================================================
// CGP Schema Elements
// ============================================================
MERGE (c1:CGPElement {name: "CGP Document"}) SET c1.type = "document", c1.version = "cgp.v2";
MERGE (c2:CGPElement {name: "SuperNode"}) SET c2.type = "node", c2.description = "Aggregated constellation node";
MERGE (c3:CGPElement {name: "Constellation"}) SET c3.type = "collection", c3.description = "Group of related points in Poincare disk";
MERGE (c4:CGPElement {name: "PoincarePoint"}) SET c4.type = "point", c4.description = "Single point in hyperbolic space";
MERGE (c5:CGPElement {name: "MerkleProof"}) SET c5.type = "proof", c5.description = "Verification proof for attribution";
MERGE (c6:CGPElement {name: "SpectralSignature"}) SET c6.type = "signature", c6.description = "Riemann zeta zero anchored fingerprint";
MERGE (c7:CGPElement {name: "HolographicBoundary"}) SET c7.type = "boundary", c7.description = "Boundary representation of content";

// ============================================================
// Core Agents
// ============================================================
MERGE (a1:Agent {id: "agent-zero"}) SET a1.name = "Agent Zero", a1.tier = "agent", a1.port = 8080, a1.theme = "optimus-prime";
MERGE (a2:Agent {id: "archon"}) SET a2.name = "Archon", a2.tier = "agent", a2.port = 8091, a2.theme = "lion-o";
MERGE (a3:Agent {id: "hirag"}) SET a3.name = "Hi-RAG v2", a3.tier = "api", a3.port = 8086, a3.theme = "calculator";
MERGE (a4:Agent {id: "deepresearch"}) SET a4.name = "DeepResearch", a4.tier = "worker", a4.port = 8098, a4.theme = "soundwave";
MERGE (a5:Agent {id: "supaserch"}) SET a5.name = "SupaSerch", a5.tier = "worker", a5.port = 8099, a5.theme = "proto-man";
MERGE (a6:Agent {id: "extract-worker"}) SET a6.name = "Extract Worker", a6.tier = "worker", a6.port = 8083, a6.theme = "panthro";
MERGE (a7:Agent {id: "cipher-memory"}) SET a7.name = "Cipher Memory", a7.tier = "data", a7.port = 8096, a7.theme = "agrias";
MERGE (a8:Agent {id: "flute-gateway"}) SET a8.name = "Flute Gateway", a8.tier = "media", a8.port = 8055, a8.theme = "arcee";
MERGE (a9:Agent {id: "pmoves-yt"}) SET a9.name = "PMOVES.YT", a9.tier = "media", a9.port = 8077;
MERGE (a10:Agent {id: "tensorzero"}) SET a10.name = "TensorZero", a10.tier = "llm", a10.port = 3030;
MERGE (a11:Agent {id: "botz"}) SET a11.name = "BoTZ", a11.tier = "agent", a11.theme = "starscream";
MERGE (a12:Agent {id: "tokenism"}) SET a12.name = "ToKenism", a12.tier = "worker", a12.theme = "megatron";
MERGE (a13:Agent {id: "creator"}) SET a13.name = "Creator", a13.tier = "worker", a13.theme = "dr-wily";
MERGE (a14:Agent {id: "hyperdimensions"}) SET a14.name = "Hyperdimensions", a14.tier = "ui", a14.theme = "calculator-fft";
MERGE (a15:Agent {id: "mesh-agent"}) SET a15.name = "Mesh Agent", a15.tier = "agent", a15.theme = "hot-rod";
MERGE (a16:Agent {id: "hf-mcp"}) SET a16.name = "HF MCP Server", a16.tier = "api", a16.port = 8096;

// ============================================================
// TypeScript CHIT Modules
// ============================================================
MERGE (m1:CHITModule {module: "dirichlet-weights"}) SET m1.name = "dirichlet-weights.ts", m1.language = "typescript";
MERGE (m2:CHITModule {module: "hyperbolic-encoder"}) SET m2.name = "hyperbolic-encoder.ts", m2.language = "typescript";
MERGE (m3:CHITModule {module: "shape-attribution"}) SET m3.name = "shape-attribution.ts", m3.language = "typescript";
MERGE (m4:CHITModule {module: "cgp-generator"}) SET m4.name = "cgp-generator.ts", m4.language = "typescript";
MERGE (m5:CHITModule {module: "swarm-attribution"}) SET m5.name = "swarm-attribution.ts", m5.language = "typescript";
MERGE (m6:CHITModule {module: "zeta-filter"}) SET m6.name = "zeta-filter.ts", m6.language = "typescript";
MERGE (m7:CHITModule {module: "chit-nats-publisher"}) SET m7.name = "chit-nats-publisher.ts", m7.language = "typescript";

// ============================================================
// Relationships: CHIT Pillars <-> Modules
// ============================================================
MERGE (p1)-[:IMPLEMENTED_BY]->(m1);
MERGE (p2)-[:IMPLEMENTED_BY]->(m2);
MERGE (p3)-[:IMPLEMENTED_BY]->(m3);
MERGE (p4)-[:IMPLEMENTED_BY]->(m4);
MERGE (p5)-[:IMPLEMENTED_BY]->(m5);

// ============================================================
// Relationships: Modules <-> NATS Subjects (publishes_to)
// ============================================================
MERGE (m7)-[:PUBLISHES_TO]->(s1);
MERGE (m7)-[:PUBLISHES_TO]->(s2);
MERGE (m7)-[:PUBLISHES_TO]->(s3);
MERGE (m7)-[:PUBLISHES_TO]->(s5);
MERGE (m7)-[:PUBLISHES_TO]->(s6);

// ============================================================
// Relationships: Agents <-> NATS Subjects
// ============================================================
MERGE (a4)-[:PUBLISHES_TO]->(s10);
MERGE (a4)-[:CONSUMES]->(s11);
MERGE (a5)-[:PUBLISHES_TO]->(s12);
MERGE (a5)-[:CONSUMES]->(s13);
MERGE (a6)-[:CONSUMES]->(s14);
MERGE (a9)-[:PUBLISHES_TO]->(s14);
MERGE (a9)-[:PUBLISHES_TO]->(s15);
MERGE (a16)-[:PUBLISHES_TO]->(s8);
MERGE (a16)-[:PUBLISHES_TO]->(s9);

// ============================================================
// Relationships: Agents <-> CGP Elements (encodes/transforms)
// ============================================================
MERGE (a12)-[:ENCODES]->(c1);
MERGE (a6)-[:TRANSFORMS]->(c4);
MERGE (a3)-[:CONSUMES]->(c1);
MERGE (a7)-[:STORES]->(c1);

// ============================================================
// Relationships: Agents <-> CHIT Pillars (uses)
// ============================================================
MERGE (a12)-[:USES]->(p1);
MERGE (a12)-[:USES]->(p2);
MERGE (a12)-[:USES]->(p3);
MERGE (a12)-[:USES]->(p4);
MERGE (a12)-[:USES]->(p5);
MERGE (a3)-[:USES]->(p2);
MERGE (a5)-[:USES]->(p4);
MERGE (a14)-[:USES]->(p2);

// ============================================================
// Relationships: CGP hierarchy
// ============================================================
MERGE (c1)-[:CONTAINS]->(c2);
MERGE (c2)-[:CONTAINS]->(c3);
MERGE (c3)-[:CONTAINS]->(c4);
MERGE (c1)-[:HAS_PROOF]->(c5);
MERGE (c1)-[:HAS_SIGNATURE]->(c6);
MERGE (c1)-[:HAS_BOUNDARY]->(c7);

// ============================================================
// Relationships: Agent orchestration
// ============================================================
MERGE (a1)-[:ORCHESTRATES]->(a2);
MERGE (a1)-[:ORCHESTRATES]->(a4);
MERGE (a1)-[:ORCHESTRATES]->(a5);
MERGE (a1)-[:ORCHESTRATES]->(a6);
MERGE (a2)-[:COORDINATES]->(a11);
MERGE (a11)-[:REGISTERS]->(a13);
MERGE (a15)-[:ANNOUNCES]->(a1);
