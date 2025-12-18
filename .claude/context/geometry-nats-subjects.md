# GEOMETRY BUS NATS Subject Catalog

Comprehensive reference for GEOMETRY BUS NATS subjects - the event-driven communication layer for CHIT (Context-Hybrid Information Token) and geometric attribution across PMOVES.AI services.

## Overview

The GEOMETRY BUS is a universal data fabric for multimodal AI communication using geometric representations. It enables:
- **Shape Attribution**: Track and credit contributions via Dirichlet-weighted CGP packets
- **Hierarchical Encoding**: Poincare disk hyperbolic embeddings for knowledge graphs
- **Spectral Analysis**: Zeta-inspired filtering for CGP spectrum processing
- **Cross-Service Integration**: Unified geometric format consumed by Hi-RAG, SupaSerch, and downstream services

## Subject Naming Convention

GEOMETRY subjects follow versioned patterns:
```text
tokenism.<domain>.<event>.v1    # ToKenism economic simulations
geometry.<type>.<event>.v1      # Core geometry events
```

---

## ToKenism Attribution Events

### Weekly CGP Export

**`tokenism.cgp.weekly.v1`**
- **Direction:** Published by ToKenism CGP export → Consumed by publisher-discord, Hi-RAG v2
- **Purpose:** Announce weekly CGP document containing economic simulation attribution
- **Payload:**
  ```json
  {
    "week": 12,
    "cgp": {
      "spec": "chit.cgp.v0.2",
      "summary": "ToKenism Week 12 Economic Simulation",
      "created_at": "2025-12-17T12:00:00Z",
      "super_nodes": [
        {
          "id": "grotoken-week-12",
          "label": "GroToken Distribution",
          "x": 0.0,
          "y": 0.0,
          "r": 0.3,
          "constellations": [...]
        }
      ],
      "meta": {
        "attribution": {
          "dirichlet_alpha": [1.2, 0.8, 0.5, 0.3],
          "merkle_root": "0xabc123..."
        }
      }
    },
    "super_node_count": 7,
    "total_attributions": 150,
    "gini": 0.42,
    "poverty_rate": 0.15
  }
  ```
- **Subscribers:** publisher-discord (formats for Discord embed), Hi-RAG v2 (indexes for retrieval)

### Attribution Recorded

**`tokenism.attribution.recorded.v1`**
- **Direction:** Published by ToKenism services → Consumed by publisher-discord, analytics
- **Purpose:** Real-time notification when an attribution action is recorded
- **Payload:**
  ```json
  {
    "chit_id": "chit-uuid-1234",
    "address": "0xMEMBER0...",
    "action": "spending",
    "amount": 50.0,
    "week": 12,
    "category": "groceries",
    "merkle_root": "0xdef456...",
    "timestamp": "2025-12-17T12:00:00Z"
  }
  ```
- **Subscribers:** publisher-discord, analytics dashboards

### CGP Ready

**`tokenism.cgp.ready.v1`**
- **Direction:** Published by any CGP producer → Consumed by Hi-RAG v2, shape-store
- **Purpose:** Generic CGP packet ready for consumption (used by deepresearch, supaserch, etc.)
- **Payload:**
  ```json
  {
    "spec": "chit.cgp.v0.1",
    "summary": "SupaSerch multimodal aggregation: research query",
    "created_at": "2025-12-17T12:00:00Z",
    "super_nodes": [
      {
        "id": "supaserch:request-123",
        "label": "http",
        "summary": "Multimodal research aggregation",
        "constellations": [
          {
            "id": "supaserch.plan.request-123",
            "summary": "Aggregation pipeline (5 stages)",
            "anchor": [0.5, 0.5, 0.5],
            "spectrum": [1.0, 0.0, 0.0, 1.0, 1.0],
            "points": [
              {
                "id": "stage:seed_intent",
                "modality": "latent",
                "proj": 1.0,
                "conf": 0.9,
                "summary": "Capture user intent..."
              }
            ],
            "meta": {
              "namespace": "supaserch",
              "channel": "http"
            }
          }
        ]
      }
    ],
    "meta": {
      "source": "supaserch.result.v1",
      "tags": ["supaserch", "multimodal", "aggregation"]
    }
  }
  ```
- **Publishers:** deepresearch, supaserch, consciousness-service, ToKenism
- **Subscribers:** Hi-RAG v2 (`/geometry/event` endpoint), shape-store, analytics

### Swarm Population Update

**`tokenism.swarm.population.v1`**
- **Direction:** Published by SwarmAttribution → Consumed by analytics, publisher-discord
- **Purpose:** Swarm optimization population state update
- **Payload:**
  ```json
  {
    "namespace": "pmoves.tokenism",
    "modality": "economic_simulation",
    "pack_id": "sim-12",
    "status": "active",
    "population_id": "pop-uuid",
    "generation": 5,
    "best_fitness": 0.87,
    "metrics": {
      "gini": 0.38,
      "poverty_rate": 0.12,
      "total_wealth": 125000.0
    },
    "timestamp": "2025-12-17T12:00:00Z"
  }
  ```
- **Subscribers:** publisher-discord, optimization dashboards

### Geometry Event (Voice)

**`tokenism.geometry.event.v1`**
- **Direction:** Published by flute-gateway → Consumed by Hi-RAG v2
- **Purpose:** Voice synthesis attribution events from flute-gateway
- **Payload:**
  ```json
  {
    "modality": "voice_synthesis",
    "provider": "kokoro",
    "text_length": 150,
    "voice": "af_sky",
    "ts": "2025-12-17T12:00:00Z"
  }
  ```
- **Env Var:** `CHIT_VOICE_ATTRIBUTION=true` enables publishing
- **Subscribers:** Hi-RAG v2 (voice attribution tracking)

---

## Geometry Core Events

### Swarm Meta

**`geometry.swarm.meta.v1`**
- **Direction:** Published by swarm services → Consumed by Hi-RAG v2
- **Purpose:** Decoder pack metadata for swarm optimization
- **Payload:**
  ```json
  {
    "namespace": "pmoves.swarm",
    "modality": "decoder_pack",
    "pack_id": "pack-123",
    "status": "active",
    "population_id": "pop-456",
    "best_fitness": 0.92,
    "metrics": {
      "loss": 0.05,
      "accuracy": 0.95
    },
    "ts": "2025-12-17T12:00:00Z"
  }
  ```
- **Schema:** `swarm.meta.v1` (compatible with PMOVES swarm infrastructure)

### Geometry CGP Direct

**`geometry.cgp.v1`**
- **Direction:** Published via Supabase Realtime → Consumed by Hi-RAG v2
- **Purpose:** CGP packets via Supabase Realtime channel
- **Note:** Used for real-time geometry updates to connected clients
- **Subscribers:** Hi-RAG v2 WebSocket consumers

### Geometry Event Raw

**`geometry.event.v1`**
- **Direction:** Published by CGP producers → Consumed by shape-store
- **Purpose:** Raw geometry events for persistent storage
- **Payload:** Any valid CGP v0.1/v0.2 document
- **Subscribers:** shape-store (geometry persistence layer)

---

## Research Events (CGP-Enhanced)

### DeepResearch Result with CGP

**`research.deepresearch.result.v1`** *(CGP-enhanced)*
- **Direction:** Published by DeepResearch → Consumed by supaserch, analytics
- **Purpose:** Research results with geometric attribution
- **CGP Enhancement:** When `DEEPRESEARCH_CGP_PUBLISH=true`, also publishes to `tokenism.cgp.ready.v1`
- **CGP Payload Structure:**
  ```json
  {
    "spec": "chit.cgp.v0.1",
    "summary": "DeepResearch: <query>",
    "super_nodes": [
      {
        "id": "research:<request_id>",
        "label": "deepresearch",
        "constellations": [
          {
            "id": "research.steps.<request_id>",
            "summary": "Research iteration steps",
            "spectrum": [<quality_metrics>],
            "points": [
              {
                "id": "step:0",
                "modality": "text",
                "proj": 1.0,
                "summary": "<step_summary>",
                "ref_id": "<source_url>"
              }
            ],
            "meta": {
              "namespace": "research",
              "query": "<original_query>",
              "duration_ms": 5000
            }
          }
        ]
      }
    ],
    "meta": {
      "source": "research.deepresearch.result.v1",
      "mode": "comprehensive",
      "tags": ["deepresearch", "ai-research"]
    }
  }
  ```
- **Env Var:** `DEEPRESEARCH_CGP_PUBLISH=true` (default: true)

### SupaSerch Result with CGP

**`supaserch.result.v1`** *(CGP-enhanced)*
- **Direction:** Published by SupaSerch → Consumed by clients
- **Purpose:** Comprehensive research results with geometric attribution
- **CGP Enhancement:** When `SUPASERCH_CGP_PUBLISH=true`, also publishes to `tokenism.cgp.ready.v1`
- **CGP Fields:** Includes `geometry_cgp` stage tracking pipeline success
- **Env Var:** `SUPASERCH_CGP_PUBLISH=true` (default: true)

---

## CGP Schema Reference

### CGP v0.1 Core Structure

```json
{
  "spec": "chit.cgp.v0.1",
  "summary": "Human-readable description",
  "created_at": "ISO-8601 timestamp",
  "super_nodes": [
    {
      "id": "unique-node-id",
      "label": "node-label",
      "summary": "node description",
      "x": 0.0,
      "y": 0.0,
      "r": 0.3,
      "constellations": [
        {
          "id": "constellation-id",
          "summary": "constellation description",
          "anchor": [0.5, 0.5, 0.5],
          "spectrum": [0.8, 0.6, 0.3],
          "points": [
            {
              "id": "point-id",
              "modality": "text|latent|voice|economic_transaction",
              "proj": 0.95,
              "conf": 0.9,
              "summary": "point summary",
              "ref_id": "optional-reference"
            }
          ],
          "meta": {
            "namespace": "service-namespace",
            "custom_key": "custom_value"
          }
        }
      ]
    }
  ],
  "meta": {
    "source": "publishing-service.event.v1",
    "tags": ["tag1", "tag2"]
  }
}
```

### CGP v0.2 Attribution Extension

```json
{
  "spec": "chit.cgp.v0.2",
  "...": "...base v0.1 fields...",
  "meta": {
    "attribution": {
      "dirichlet_alpha": [1.2, 0.8, 0.5],
      "contributors": [
        {
          "address": "0xABC...",
          "weight": 0.32,
          "raw_contribution": 5.2,
          "action_type": "spending"
        }
      ],
      "merkle_root": "0xabc123...",
      "timestamp": "2025-12-17T12:00:00Z"
    },
    "hyperbolic_encoding": {
      "space": "poincare_disk",
      "curvature": -1,
      "points": [
        {"id": "p1", "x": 0.2, "y": 0.3, "r": 0.36, "theta": 0.98}
      ]
    }
  }
}
```

### Point Modality Types

| Modality | Description | Used By |
|----------|-------------|---------|
| `text` | Text-based content | DeepResearch, summaries |
| `latent` | Embedding/latent space | SupaSerch pipeline stages |
| `voice` | Voice synthesis | Flute Gateway |
| `economic_transaction` | FoodUSD spending | ToKenism |
| `token_distribution` | GroToken rewards | ToKenism |
| `group_savings` | GroupPurchase outcomes | ToKenism |
| `staking_position` | GroVault locks | ToKenism |
| `governance_vote` | CoopGovernor participation | ToKenism |
| `loyalty_event` | LoyaltyPoints activity | ToKenism |
| `reward_claim` | RewardsPool distributions | ToKenism |

---

## Service Integration Map

### CGP Producers

| Service | Subject | Env Var | Default |
|---------|---------|---------|---------|
| DeepResearch | `tokenism.cgp.ready.v1` | `DEEPRESEARCH_CGP_PUBLISH` | `true` |
| SupaSerch | `tokenism.cgp.ready.v1` | `SUPASERCH_CGP_PUBLISH` | `true` |
| Flute Gateway | `tokenism.geometry.event.v1` | `CHIT_VOICE_ATTRIBUTION` | `false` |
| Consciousness Service | `tokenism.cgp.ready.v1` | n/a | always |
| ToKenism | `tokenism.cgp.weekly.v1` | n/a | always |

### CGP Consumers

| Service | Subjects | Endpoint |
|---------|----------|----------|
| Hi-RAG Gateway v2 | `tokenism.cgp.ready.v1`, `geometry.*` | `POST /geometry/event` |
| Publisher Discord | `tokenism.*` | Formats as Discord embeds |
| Shape Store | `geometry.event.v1` | Persistence layer |

---

## Monitoring & Debugging

### Subscribe to All GEOMETRY Events

```bash
# All ToKenism events
nats sub "tokenism.>"

# All geometry events
nats sub "geometry.>"

# Both families
nats sub "tokenism.>" "geometry.>"
```

### Verify CGP Publishing

```bash
# Check deepresearch logs
docker logs deepresearch 2>&1 | grep -E "(CGP|tokenism)"

# Check supaserch logs
docker logs supaserch 2>&1 | grep -E "(CGP|geometry_cgp)"

# Monitor real-time CGP events
nats sub "tokenism.cgp.ready.v1" --max 5
```

### Test CGP Event Manually

```bash
# Publish test CGP packet
nats pub "tokenism.cgp.ready.v1" '{
  "spec": "chit.cgp.v0.1",
  "summary": "Test CGP packet",
  "created_at": "2025-12-17T12:00:00Z",
  "super_nodes": [],
  "meta": {"source": "test.manual.v1"}
}'
```

---

## Best Practices

### Publishing CGP Events

1. **Always include `spec` version** - `chit.cgp.v0.1` or `chit.cgp.v0.2`
2. **Use meaningful summaries** - Human-readable, max 200 chars
3. **Include source in meta** - Identifies the publishing service
4. **Add timestamps** - ISO 8601 format (UTC) via `created_at`
5. **Use appropriate modality** - Match point types to content

### Consuming CGP Events

1. **Validate spec version** - Handle v0.1 and v0.2 gracefully
2. **Index super_nodes** - Each super_node is a distinct knowledge unit
3. **Process constellations** - Extract spectrum for similarity matching
4. **Store points** - Points contain the actual content references

### Environment Variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `DEEPRESEARCH_CGP_PUBLISH` | deepresearch | `true` | Enable CGP publishing |
| `SUPASERCH_CGP_PUBLISH` | supaserch | `true` | Enable CGP publishing |
| `CHIT_VOICE_ATTRIBUTION` | flute-gateway | `false` | Enable voice attribution |
| `CHIT_NAMESPACE` | flute-gateway | `pmoves.voice` | Namespace for voice CGP |

---

## Related Documentation

- **Main NATS Catalog:** `.claude/context/nats-subjects.md`
- **CHIT Geometry Bus:** `.claude/context/chit-geometry-bus.md`
- **Services Catalog:** `.claude/context/services-catalog.md`
- **ToKenism CHIT Integration:** `PMOVES-ToKenism-Multi/docs/CHIT_INTEGRATION.md`
