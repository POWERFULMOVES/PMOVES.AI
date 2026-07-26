# CHIT Mirror Patterns

**Thread 7.3: How CHIT concepts mirror across the PMOVES.AI repository**

The CHIT (Cymatic Holographic Information Theory) system creates a coherent mathematical fabric woven through multiple layers of the platform. Each concept has mirror representations in TypeScript modules, NATS subjects, Neo4j graph, CGP schema, and agent taxonomy.

## The Five Mirrors

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  TypeScript   │────▶│ NATS Subject  │────▶│   Neo4j      │
│  Module       │     │ (Event Bus)   │     │   Graph      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  CGP Schema   │────▶│    Agent     │
│  (Document)   │     │  Taxonomy    │
└──────────────┘     └──────────────┘
```

## Mirror Map

### Dirichlet Attribution

| Mirror | Location | Purpose |
|--------|----------|---------|
| TS Module | `PMOVES-ToKenism-Multi/integrations/contracts/chit/dirichlet-weights.ts` | Probabilistic weight calculation |
| NATS Subject | `tokenism.attribution.recorded.v1` | Attribution events |
| Neo4j Node | `(:CHITPillar {id: "dirichlet"})` | Knowledge graph anchor |
| CGP Element | `payload.dirichlet_weights.alphas[]` | Document encoding |
| Agent | ToKenism (Megatron) | Agent that produces weights |

### Hyperbolic Encoding

| Mirror | Location | Purpose |
|--------|----------|---------|
| TS Module | `hyperbolic-encoder.ts` | Poincare disk coordinate mapping |
| NATS Subject | `tokenism.geometry.event.v1` | Geometry transformation events |
| Neo4j Node | `(:CGPElement {type: "point"})` | Coordinate storage |
| CGP Element | `payload.hyperbolic_coords` | Spatial embedding |
| Agent | Hi-RAG (Calculator) + Hyperdimensions | Retrieval + visualization |

### Shape Attribution

| Mirror | Location | Purpose |
|--------|----------|---------|
| TS Module | `shape-attribution.ts` | Merkle tree proof generation |
| NATS Subject | `tokenism.attribution.recorded.v1` | Proof events |
| Neo4j Edge | `(:Agent)-[:ENCODES]->(:CGPElement)` | Provenance tracking |
| CGP Element | `merkle_proof`, `attribution_records` | Verifiable proofs |
| Agent | Cipher Memory (Agrias) | Proof storage and verification |

### CGP Generation

| Mirror | Location | Purpose |
|--------|----------|---------|
| TS Module | `cgp-generator.ts` | Document assembly |
| NATS Subject | `tokenism.cgp.weekly.v1`, `tokenism.cgp.ready.v1` | Document lifecycle events |
| Neo4j Structure | `(:CGPElement)-[:CONTAINS]->(:CGPElement)` | Document hierarchy |
| CGP Schema | Full `cgp.v2` document | The document itself |
| Agent | Agent Zero (Optimus Prime) orchestrates assembly |

### EVO SWARM

| Mirror | Location | Purpose |
|--------|----------|---------|
| TS Module | `swarm-attribution.ts` | Fitness calculation |
| NATS Subject | `tokenism.swarm.population.v1` | Population updates |
| Neo4j | `(:Agent)-[:ORCHESTRATES]->(:Agent)` | Swarm topology |
| CGP Element | `swarm_meta` block | Optimization metrics |
| Agent | All agents (population members) | Swarm participants |
| Supabase | `pmoves_core.swarm_attribution` | Persistent tracking |

## Cross-Cutting Patterns

### Content Ingestion Flow

```
Content → Extract Worker → CHIT Encode Hook → CGP Packet
                                ↓
                    Dirichlet weights + Hyperbolic coords
                                ↓
                    Qdrant (vector) + Neo4j (graph) + Meilisearch (text)
                                ↓
                    NATS: geometry.packet.encoded.v1
```

### Agent Task Completion Flow

```
Agent Zero assigns task → Agent executes → EVO SWARM updates
                                               ↓
                                   swarm-attribution.ts calculates fitness
                                               ↓
                                   NATS: tokenism.swarm.population.v1
                                               ↓
                                   Supabase: pmoves_core.swarm_attribution
```

### Model Onboarding Flow

```
HF Hub → hf_model_onboard.py → Agent Card Fragment (CGP)
                                         ↓
                              Supabase: model_bindings
                                         ↓
                              NATS: hf.model.onboarded.v1
                                         ↓
                              Benchmark Runner → A2UI Chart → Remotion
```

## Verification

Each mirror can be verified independently:

```bash
# TS modules compile
cd PMOVES-ToKenism-Multi && npx tsc --noEmit

# NATS subjects have publishers
make -C pmoves geometry-bus-status

# Neo4j graph is seeded
cat pmoves/tools/chit_mindmap_seed.cypher | cypher-shell

# CGP packets validate
python -c "from pmoves.tools.chit_encode_hook import chit_encode_content; print(chit_encode_content('test').to_dict())"

# Agent taxonomy is consistent
python pmoves/tools/docs_content_audit.py --json | jq '.findings[] | select(.category == "undocumented_service")'
```
