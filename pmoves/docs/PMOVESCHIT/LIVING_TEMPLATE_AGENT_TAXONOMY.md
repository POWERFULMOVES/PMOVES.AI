# Living Template: Agent Taxonomy in CHIT

_Last updated: 2026-02-16_

This living template demonstrates how the PMOVES Agent Class Taxonomy maps through all five CHIT mathematical pillars, with concrete examples, CGP packet samples, and expanded use cases. It serves as both documentation and validation artifact — a working example of PMOVES in action.

## Source Documents

- [`../AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`](../AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md) — Class hierarchy, types, evolution
- [`../AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`](../AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md) — 6-layer fold model
- [`../AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`](../AGENTS/PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md) — Geometry state vector
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — CHIT 5 pillars implementation status
- [`GEOMETRY_BUS_INTEGRATION.md`](./GEOMETRY_BUS_INTEGRATION.md) — CGP format, NATS subjects
- [`CGP_v1.0_SPECIFICATION.md`](./CGP_v1.0_SPECIFICATION.md) — Production CGP spec
- `PMOVES-ToKenism-Multi/integrations/contracts/chit/` — TypeScript implementations

---

## 1. Complete Agent Card (CGP v0.2 Format)

An agent card encodes a single agent's position in the taxonomy as a CGP packet. This is the canonical format for agent topology data flowing through the GEOMETRY BUS.

```json
{
  "spec": "chit.cgp.v0.2",
  "meta": {
    "source": "agent_taxonomy",
    "units_mode": "agents",
    "K": 8,
    "bins": 7,
    "mhep": 85.2,
    "backend": "pmoves/config/agent_registry.yaml"
  },
  "super_nodes": [
    {
      "id": "class_standard",
      "x": 0.0,
      "y": 0.0,
      "r": 400.0,
      "label": "Standard Class (PMOVES-)",
      "constellations": [
        {
          "id": "type_agent",
          "anchor": [0.35, 0.25, 0.15, 0.10, 0.05, 0.05, 0.05],
          "summary": "Agent-type services: orchestration, planning, delegation",
          "radial_minmax": [0.0, 0.95],
          "spectrum": [0.05, 0.10, 0.15, 0.25, 0.20, 0.15, 0.10],
          "points": [
            {
              "id": "agent_zero",
              "magnitude": 0.95,
              "modality": "agent",
              "text_b64": "QWdlbnQgWmVybzogTDEgb3JjaGVzdHJhdG9yLCBNZWdhIEV2b2x1dGlvbiwgNyBsYXllcnM=",
              "layers": ["L0", "L1", "L2", "L2.5", "L3", "L4", "L5"],
              "evolution_stage": "mega",
              "chit_toggles": {
                "delta_sensitive": true,
                "kappa_sensitive": true,
                "hz_sensitive": true,
                "swarm_participant": true,
                "attribution_gated": true
              },
              "nats_subjects": {
                "publishes": ["agent.tool.executed.v1"],
                "subscribes": ["mesh.node.announce.v1"]
              },
              "health_endpoint": "http://localhost:8080/healthz"
            },
            {
              "id": "archon",
              "magnitude": 0.88,
              "modality": "agent",
              "text_b64": "QXJjaG9uOiBMMSBjb3BpbG90LCBTdGFnZSAyLCA2IGxheWVycw==",
              "layers": ["L0", "L1", "L2", "L2.5", "L4", "L5"],
              "evolution_stage": "stage_2",
              "chit_toggles": {
                "delta_sensitive": true,
                "kappa_sensitive": true,
                "hz_sensitive": true,
                "swarm_participant": false,
                "attribution_gated": true
              }
            },
            {
              "id": "supaserch",
              "magnitude": 0.82,
              "modality": "agent",
              "text_b64": "U3VwYVNlcmNoOiBob2xvZ3JhcGhpYyBkZWVwIHJlc2VhcmNoLCBTdGFnZSAy",
              "layers": ["L0", "L2", "L2.5", "L3", "L4"],
              "evolution_stage": "stage_2"
            }
          ]
        },
        {
          "id": "type_worker",
          "anchor": [0.10, 0.10, 0.10, 0.35, 0.15, 0.10, 0.10],
          "summary": "Worker-type services: processing, transformation, embedding",
          "radial_minmax": [0.0, 0.85],
          "spectrum": [0.10, 0.10, 0.10, 0.30, 0.20, 0.10, 0.10],
          "points": [
            {
              "id": "hirag_v2",
              "magnitude": 0.85,
              "modality": "worker",
              "text_b64": "SGktUkFHIHYyOiBoeWJyaWQgUkFHIGdhdGV3YXksIFN0YWdlIDI=",
              "layers": ["L0", "L2", "L2.5", "L4", "L5"],
              "evolution_stage": "stage_2"
            },
            {
              "id": "extract_worker",
              "magnitude": 0.65,
              "modality": "worker",
              "text_b64": "RXh0cmFjdCBXb3JrZXI6IHRleHQgZW1iZWRkaW5nICsgaW5kZXhpbmc=",
              "layers": ["L0", "L2", "L4", "L5"],
              "evolution_stage": "stage_1"
            }
          ]
        }
      ]
    }
  ],
  "nats": {
    "subject": "tokenism.cgp.ready.v1",
    "timestamp": "2026-02-16T00:00:00Z",
    "publisher_id": "agent-taxonomy-publisher"
  }
}
```

---

## 2. Five Mathematical Pillars Applied to Agent Taxonomy

Each CHIT pillar provides a distinct lens for understanding, validating, and controlling the agent network.

### Pillar 1: Dirichlet Distributions — Attribution Weighting

**Module:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/dirichlet-weights.ts`

**Application:** When multiple agents collaborate on a task, Dirichlet distributions assign fair credit.

**Agent Taxonomy Use Case:** Attribution weighting across agent contributions in a multi-agent pipeline.

```
Task: "Summarize this YouTube video"
Pipeline: PMOVES.YT → FFmpeg-Whisper → Extract Worker → Hi-RAG v2 → DeepResearch

Dirichlet prior α = [1.0, 2.0, 1.5, 2.5, 3.0]
                     ↓     ↓      ↓      ↓      ↓
                    YT  Whisper  Extract Hi-RAG  Deep

Sampled weights: [0.08, 0.18, 0.12, 0.25, 0.37]

Interpretation:
- DeepResearch (0.37) contributed most reasoning value
- Hi-RAG v2 (0.25) provided critical retrieval grounding
- Whisper (0.18) transcription was essential but mechanical
- Extract (0.12) embedding was intermediate
- YT (0.08) ingestion was triggering only
```

The `anchor` arrays in CGP constellation objects are Dirichlet-weighted vectors — they encode the relative contribution of each type within a constellation.

### Pillar 2: Hyperbolic Geometry (Poincare Disk) — Hierarchical Embedding

**Module:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/hyperbolic-encoder.ts`

**Application:** The class → type → tier → layer hierarchy is naturally tree-like. Hyperbolic space embeds trees with minimal distortion.

**Agent Taxonomy Use Case:** Embed the full agent hierarchy on the Poincare disk.

```
Poincare Disk Embedding:

Center (0,0) = POWERFULMOVES (Legendary class)
├── Ring 1 (r≈0.3): PMOVES- Standard class
│   ├── Sector NE: Agent type (Agent Zero, Archon, SupaSerch)
│   ├── Sector E:  Worker type (Hi-RAG, Extract, Channel Monitor)
│   ├── Sector SE: Media type (PMOVES.YT, Whisper, Analyzers)
│   ├── Sector S:  LLM type (DeepResearch, TensorZero)
│   ├── Sector SW: API type (Flute-Gateway, Presign)
│   └── Sector W:  UI type (MAI-UI)
├── Ring 2 (r≈0.6): Pmoves- Specialized class
│   ├── Cipher Memory (Data/Agent)
│   ├── Hyperdimensions (UI/Data)
│   └── Jellyfin Bridge (Media/Data)
└── Ring 3 (r≈0.85): pmoves- Utility class
    ├── NATS, Supabase, Qdrant, Neo4j (Data infra)
    └── Prometheus, Grafana, Loki (Observation)

Key property: Distance on disk ∝ taxonomic distance
- Agent Zero ↔ Archon: small distance (same class, same type)
- Agent Zero ↔ Extract Worker: medium distance (same class, different type)
- Agent Zero ↔ Prometheus: large distance (different class, different type)
```

The `x`, `y` coordinates in CGP `super_nodes` are Poincare disk coordinates. Radius `r` indicates the boundary of the class region.

### Pillar 3: Merkle Proofs — Capability Integrity

**Module:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/cgp-generator.ts`

**Application:** Each agent's claimed capabilities (layers, CHIT toggles, evolution stage) are Merkle-provable.

**Agent Taxonomy Use Case:** Tamper-proof verification that an agent actually has the capabilities it claims.

```
Agent Zero Capability Merkle Tree:

                    Root Hash
                   /          \
          H(layers)         H(toggles)
         /        \        /          \
    H(L0,L1)  H(L2,L2.5)  H(delta,kappa)  H(hz,swarm,attr)
    /    \     /      \      /      \        /     |     \
  H(L0) H(L1) H(L2) H(L2.5) H(δ=T) H(κ=T)  H(Hz=T) H(F=T) H(A=T)

Verification:
1. External agent claims "I support L2.5 (Hyperdimensions)"
2. Provide Merkle proof: [H(L2), H(L0,L1), H(toggles)] + leaf H(L2.5)
3. Verify root hash matches registry → capability confirmed
4. If root hash mismatch → capability claim is fraudulent

Use case: BoTZ Gateway verifying a worker's claimed skill level
before delegating agentic tasks (skill_level: agentic requires
L3+L4+L5 verified via Merkle proof)
```

### Pillar 4: Zeta-Inspired Filtering — Signal Noise Reduction

**Module:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/zeta-filter.ts`

**Application:** Agent health signals (`/healthz`, `/metrics`) are noisy. Zeta filtering extracts the true signal.

**Agent Taxonomy Use Case:** Filter noisy health/performance metrics to determine true agent fitness.

```
Raw health signals for Hi-RAG v2 over 1 hour:

Metric: response_time_ms
Raw:    [45, 52, 48, 312, 47, 51, 49, 287, 46, 50, 48, 53, 295, 47]
         │                │              │                │
         └── spikes = NATS reconnects (noise, not degradation)

Zeta filter (using Riemann zero distribution as filter kernel):
- Identify spectral components aligned with zeta zeros
- These correspond to structural patterns (real signal)
- Components NOT aligned with zeros = transient noise

Filtered: [45, 52, 48, 48, 47, 51, 49, 49, 46, 50, 48, 53, 49, 47]
                        ↑              ↑                 ↑
                     spikes removed (noise at non-zero frequencies)

Result: True mean response time = 48.7ms (healthy)
Without filter: Apparent mean = 92.1ms (falsely alarming)

Application to CHIT toggle:
- Hz (spectral entropy) signal uses zeta-filtered metrics
- High Hz after filtering → genuine entropy → increase consensus passes
- High Hz before filtering, low after → noise → no action needed
```

### Pillar 5: Swarm Optimization (EvoSwarm) — Consensus Configuration

**Module:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/swarm-attribution.ts`

**Application:** Multiple agents vote on optimal configuration through evolutionary fitness.

**Agent Taxonomy Use Case:** Consensus on which agent combination best handles a given task type.

```
EvoSwarm Population for Task: "Research and summarize a topic"

Generation 0 (random packs):
  Pack A: [DeepResearch, Hi-RAG v2, Extract Worker]           Fitness: 0.72
  Pack B: [SupaSerch, DeepResearch, Flute-Gateway]            Fitness: 0.81
  Pack C: [Agent Zero, Hi-RAG v2, TensorZero]                 Fitness: 0.68
  Pack D: [SupaSerch, Hi-RAG v2, DeepResearch, Extract Worker] Fitness: 0.89

Generation 1 (crossover + mutation):
  Pack E: [SupaSerch, Hi-RAG v2, DeepResearch] (from D×B)     Fitness: 0.91
  Pack F: [SupaSerch, DeepResearch, Extract Worker] (from D×B) Fitness: 0.85
  ...

Generation 5 (converged):
  Optimal Pack: [SupaSerch, Hi-RAG v2, DeepResearch]          Fitness: 0.94

NATS subject: evoswarm.population.v1
Published by: Swarm Attribution module
Consumed by: Agent Zero (pack selection), Hyperdimensions (visualization)

The F (swarm fitness) signal in the geometry state vector
reflects the converged pack's fitness score (0.94).
Low F → switch to safer/default pack.
```

---

## 3. Expanded Use Cases

### Use Case 1: Network Topology Discovery

**Question:** "Which agents are connected right now?"

**Implementation:** Query `agent_registry.yaml` for NATS subject overlaps, generate connection graph.

```python
# Using agent_taxonomy_helper.py
$ python -m pmoves.tools.agent_taxonomy_helper connections

{
  "nodes": [
    {"id": "agent_zero", "class": "Standard", "type": "Agent", "layers": 7},
    {"id": "pmoves_yt", "class": "Standard", "type": "Media", "layers": 4},
    {"id": "extract_worker", "class": "Standard", "type": "Worker", "layers": 4}
  ],
  "edges": [
    {
      "source": "pmoves_yt",
      "target": "extract_worker",
      "via": "ingest.file.added.v1",
      "type": "nats_event"
    },
    {
      "source": "agent_zero",
      "target": "pmoves_yt",
      "via": "MCP API",
      "type": "http_rpc"
    }
  ]
}
```

**CHIT application:** The connection graph IS a CGP packet — super_nodes are agent classes, constellations are types, points are individual agents, and edges are NATS subjects.

### Use Case 2: Dream Realization (Latent Space Amplification)

**Question:** "I want to build a system that automatically researches topics and creates voice summaries."

**Implementation:** Map the dream to agent combinations, find the optimal pack via EvoSwarm.

```
User dream: "Research → Voice Summary"

Latent space mapping:
  User intent vector:  [research=0.9, voice=0.8, automation=0.7]
  Agent capability vectors:
    DeepResearch:  [research=0.95, voice=0.0, automation=0.6]
    Flute-Gateway: [research=0.0,  voice=0.95, automation=0.8]
    SupaSerch:     [research=0.85, voice=0.0, automation=0.9]

Amplification (user × agents):
  Portal = User ⊗ [SupaSerch, DeepResearch, Flute-Gateway]
         = [research=0.9×0.95, voice=0.8×0.95, automation=0.7×0.9]
         = [0.855, 0.76, 0.63]

Pipeline emerges:
  SupaSerch → DeepResearch → Extract Worker → Flute-Gateway
  (search)    (reason)       (embed)          (speak)

As this portal is used, the mapping gets smoother:
- EvoSwarm refines pack fitness
- Dirichlet priors update with each successful run
- Hyperdimensions surface shows the portal stabilizing
```

### Use Case 3: Problem Solving (Optimal Agent Routing)

**Question:** "This PDF analysis is taking too long. What's the bottleneck?"

**Implementation:** Use CHIT toggles + health metrics to diagnose.

```
Diagnostic flow:
1. Query agent_registry for PDF pipeline:
   pdf-ingest → extract-worker → hi-rag-v2

2. Check CHIT toggles:
   pdf-ingest:     hz_sensitive=true, current Hz=HIGH
   extract-worker: hz_sensitive=true, current Hz=HIGH
   hi-rag-v2:      hz_sensitive=true, current Hz=NORMAL

3. Zeta-filter the Hz signal:
   pdf-ingest Hz after filter:     STILL HIGH → real entropy
   extract-worker Hz after filter: LOW → was noise (NATS reconnects)

4. Diagnosis: pdf-ingest has genuinely high spectral entropy
   → input PDFs have mixed modalities (text + images + tables)
   → increase filtering passes before sending to extract-worker

5. Action: Geometry state vector update
   Hz: 0.85 → triggers "increase consensus passes" control mapping
   Published to: geometry.cgp.v1
   Consumed by: Hyperdimensions (shows hotspot on pdf-ingest node)
```

### Use Case 4: Validation Metric (Deployment Readiness)

**Question:** "Is this agent pack ready for production?"

**Implementation:** Aggregate CHIT check pass/fail per agent as a readiness score.

```
Deployment Readiness Check for Pack: [Agent Zero, Hi-RAG v2, Flute-Gateway]

Per-agent CHIT scores:
  Agent Zero:
    ✅ delta_sensitive: delta=0.42 (normal range 0.2-0.8)     PASS
    ✅ kappa_sensitive: kappa=-0.3 (hierarchy present)         PASS
    ✅ hz_sensitive: Hz=0.15 (low entropy, clean signal)       PASS
    ✅ swarm_participant: F=0.91 (high fitness)                PASS
    ✅ attribution_gated: A=0.88 (strong proof)                PASS
    Score: 5/5 = 1.00 ██████████ GREEN

  Hi-RAG v2:
    ✅ delta_sensitive: delta=0.55                             PASS
    ✅ kappa_sensitive: kappa=-0.15                            PASS
    ⚠️ hz_sensitive: Hz=0.72 (elevated, needs attention)       WARN
    ✅ swarm_participant: F=0.85                               PASS
    — attribution_gated: not applicable                        SKIP
    Score: 3.5/4 = 0.88 ████████░░ YELLOW

  Flute-Gateway:
    — delta_sensitive: not applicable                          SKIP
    — kappa_sensitive: not applicable                          SKIP
    ✅ hz_sensitive: Hz=0.20 (clean)                           PASS
    — swarm_participant: not applicable                        SKIP
    ✅ attribution_gated: A=0.92                               PASS
    Score: 2/2 = 1.00 ██████████ GREEN

Pack Aggregate Score: (1.00 + 0.88 + 1.00) / 3 = 0.96

Readiness: ✅ DEPLOY (threshold: 0.80)
Advisory: Monitor Hi-RAG v2 Hz signal — elevated spectral entropy
```

---

## 4. CGP Sample Packet: Agent Topology

This is the canonical sample showing a full agent network topology encoded in CGP v0.2 format. Store at `PMOVES-ToKenism-Multi/integrations/contracts/chit/samples/agent-taxonomy-cgp.json`.

```json
{
  "spec": "chit.cgp.v0.2",
  "meta": {
    "source": "agent_taxonomy",
    "units_mode": "agents",
    "K": 7,
    "bins": 7,
    "mhep": 85.2,
    "backend": "pmoves/config/agent_registry.yaml",
    "taxonomy_version": "1.0.0"
  },
  "super_nodes": [
    {
      "id": "class_legendary",
      "x": 0.0,
      "y": 0.0,
      "r": 50.0,
      "label": "Legendary (POWERFULMOVES)"
    },
    {
      "id": "class_standard",
      "x": 0.0,
      "y": 0.0,
      "r": 400.0,
      "label": "Standard (PMOVES-)",
      "constellations": [
        {
          "id": "type_agent",
          "anchor": [0.05, 0.05, 0.10, 0.05, 0.05, 0.60, 0.10],
          "summary": "Agent-type: orchestration and planning",
          "radial_minmax": [0.10, 0.40],
          "spectrum": [0.05, 0.10, 0.15, 0.05, 0.05, 0.50, 0.10],
          "points": [
            {"id": "agent_zero", "magnitude": 0.95, "modality": "agent"},
            {"id": "archon", "magnitude": 0.88, "modality": "agent"},
            {"id": "supaserch", "magnitude": 0.82, "modality": "agent"},
            {"id": "botz_gateway", "magnitude": 0.75, "modality": "agent"},
            {"id": "mesh_agent", "magnitude": 0.60, "modality": "agent"}
          ]
        },
        {
          "id": "type_worker",
          "anchor": [0.15, 0.05, 0.05, 0.50, 0.10, 0.05, 0.10],
          "summary": "Worker-type: processing and transformation",
          "radial_minmax": [0.10, 0.40],
          "spectrum": [0.10, 0.05, 0.05, 0.50, 0.15, 0.05, 0.10],
          "points": [
            {"id": "hirag_v2", "magnitude": 0.85, "modality": "worker"},
            {"id": "extract_worker", "magnitude": 0.65, "modality": "worker"},
            {"id": "channel_monitor", "magnitude": 0.55, "modality": "worker"},
            {"id": "notebook_sync", "magnitude": 0.50, "modality": "worker"},
            {"id": "pdf_ingest", "magnitude": 0.50, "modality": "worker"},
            {"id": "publisher_discord", "magnitude": 0.45, "modality": "worker"}
          ]
        },
        {
          "id": "type_media",
          "anchor": [0.05, 0.05, 0.05, 0.15, 0.55, 0.05, 0.10],
          "summary": "Media-type: multimodal ingestion and processing",
          "radial_minmax": [0.10, 0.40],
          "spectrum": [0.05, 0.05, 0.05, 0.15, 0.55, 0.05, 0.10],
          "points": [
            {"id": "pmoves_yt", "magnitude": 0.80, "modality": "media"},
            {"id": "ffmpeg_whisper", "magnitude": 0.70, "modality": "media"},
            {"id": "media_video", "magnitude": 0.60, "modality": "media"},
            {"id": "media_audio", "magnitude": 0.55, "modality": "media"},
            {"id": "ultimate_tts", "magnitude": 0.75, "modality": "media"}
          ]
        },
        {
          "id": "type_llm",
          "anchor": [0.05, 0.05, 0.60, 0.15, 0.05, 0.05, 0.05],
          "summary": "LLM-type: reasoning and generation",
          "radial_minmax": [0.10, 0.35],
          "spectrum": [0.05, 0.05, 0.60, 0.15, 0.05, 0.05, 0.05],
          "points": [
            {"id": "deep_research", "magnitude": 0.80, "modality": "llm"},
            {"id": "tensorzero", "magnitude": 0.90, "modality": "api"}
          ]
        },
        {
          "id": "type_api",
          "anchor": [0.10, 0.50, 0.10, 0.10, 0.10, 0.05, 0.05],
          "summary": "API-type: routing and gateway services",
          "radial_minmax": [0.10, 0.35],
          "spectrum": [0.10, 0.50, 0.10, 0.10, 0.10, 0.05, 0.05],
          "points": [
            {"id": "flute_gateway", "magnitude": 0.78, "modality": "api"},
            {"id": "presign", "magnitude": 0.40, "modality": "api"},
            {"id": "render_webhook", "magnitude": 0.35, "modality": "api"}
          ]
        },
        {
          "id": "type_ui",
          "anchor": [0.05, 0.10, 0.05, 0.05, 0.05, 0.10, 0.60],
          "summary": "UI-type: visualization and interaction",
          "radial_minmax": [0.10, 0.30],
          "spectrum": [0.05, 0.10, 0.05, 0.05, 0.05, 0.10, 0.60],
          "points": [
            {"id": "mai_ui", "magnitude": 0.70, "modality": "ui"}
          ]
        }
      ]
    },
    {
      "id": "class_specialized",
      "x": 0.0,
      "y": 0.0,
      "r": 600.0,
      "label": "Specialized (Pmoves-)",
      "constellations": [
        {
          "id": "type_specialized_mixed",
          "anchor": [0.30, 0.10, 0.05, 0.05, 0.15, 0.05, 0.30],
          "summary": "Specialized domain agents",
          "radial_minmax": [0.50, 0.70],
          "spectrum": [0.25, 0.10, 0.05, 0.05, 0.20, 0.05, 0.30],
          "points": [
            {"id": "cipher_memory", "magnitude": 0.72, "modality": "data"},
            {"id": "hyperdimensions", "magnitude": 0.80, "modality": "ui"},
            {"id": "jellyfin_bridge", "magnitude": 0.50, "modality": "media"},
            {"id": "health_wger", "magnitude": 0.45, "modality": "data"}
          ]
        }
      ]
    },
    {
      "id": "class_utility",
      "x": 0.0,
      "y": 0.0,
      "r": 800.0,
      "label": "Utility (pmoves-)",
      "constellations": [
        {
          "id": "type_data_infra",
          "anchor": [0.80, 0.10, 0.00, 0.00, 0.00, 0.00, 0.10],
          "summary": "Data infrastructure: persistence layer",
          "radial_minmax": [0.75, 0.95],
          "spectrum": [0.80, 0.10, 0.00, 0.00, 0.00, 0.00, 0.10],
          "points": [
            {"id": "nats", "magnitude": 0.95, "modality": "data"},
            {"id": "supabase", "magnitude": 0.90, "modality": "data"},
            {"id": "qdrant", "magnitude": 0.80, "modality": "data"},
            {"id": "neo4j", "magnitude": 0.80, "modality": "data"},
            {"id": "meilisearch", "magnitude": 0.75, "modality": "data"},
            {"id": "minio", "magnitude": 0.85, "modality": "data"}
          ]
        }
      ]
    }
  ],
  "nats": {
    "subject": "tokenism.cgp.ready.v1",
    "timestamp": "2026-02-16T00:00:00Z",
    "publisher_id": "agent-taxonomy-publisher"
  }
}
```

---

## 5. Hyperdimensions Visualization

The agent topology CGP packet maps directly to the Hyperdimensions Poincare disk renderer:

| CGP Field | Hyperdimensions Mapping | Visual |
|-----------|------------------------|--------|
| `super_nodes[].r` | Ring radius on Poincare disk | Class boundary circles |
| `constellations[].anchor` | Type-weighted position within ring | Sector placement |
| `points[].magnitude` | Node size | Larger = more capable |
| `points[].evolution_stage` | Node glow intensity | Mega = bright, Base = dim |
| `points[].chit_toggles` | Node color | All pass=green, partial=yellow, blocked=red |
| NATS subject overlaps | Edge connections | Lines between connected nodes |

Save surface: `Pmoves-hyperdimensions/saves/agent_topology.json`

---

## 6. Validation

This living template is valid when:

1. All 5 CHIT pillars are demonstrated with agent taxonomy examples
2. CGP sample packet conforms to `chit.cgp.v0.2` spec
3. Agent names match `pmoves/config/agent_registry.yaml`
4. NATS subjects match `.claude/context/nats-subjects.md` and `geometry-nats-subjects.md`
5. Layer assignments match `PMOVES_UNIFIED_AGENT_TAXONOMY.md`
6. Control mappings match `PMOVES_HYPERDIMENSIONS_CONTROL_PLANE.md`

Update this template whenever the agent registry or CHIT pillars change.

---

## Related Documents

- [`../AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`](../AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md) — Full class taxonomy
- [`../AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md`](../AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md) — Master cross-reference
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — CHIT implementation matrix
- `pmoves/config/agent_registry.yaml` — Machine-readable registry
- `pmoves/tools/agent_taxonomy_helper.py` — CLI query tool
