# GEOMETRY BUS Integration Guide

**Comprehensive guide for integrating PMOVES.AI services with the GEOMETRY BUS - the universal data fabric for multimodal AI communication using geometric representations.**

## Overview

The GEOMETRY BUS transforms the PMOVES.AI platform from a traditional message-passing system into a **Hyperbolic Manifold Navigator**. By standardizing data into CHIT Geometry Packets (CGPs), services communicate via shape-based attribution, enabling:

- **Holographic Data Representation**: Information encoded on "boundary surfaces" (CGP packets) rather than volumetric redundancy
- **Hierarchical Knowledge Encoding**: Poincare disk geometry for exponential storage capacity
- **Spectral Signal Processing**: Riemann zeta zeros as universal frequency filters
- **Provable Attribution**: Dirichlet-weighted contributions with Merkle proof verification

## Mathematical Foundations

### The Five Mathematical Pillars

| Pillar | Implementation | Purpose |
|--------|----------------|---------|
| **Dirichlet Distributions** | `DirichletWeights` class | Probabilistic attribution weighting |
| **Hyperbolic Geometry** | `HyperbolicEncoder` class | Poincare disk hierarchical encoding |
| **Merkle Proofs** | `ShapeAttribution` class | Verifiable attribution chains |
| **Zeta Spectral Filtering** | `ZetaInspiredFilter` class | Signal/noise separation via Riemann zeros |
| **Swarm Optimization** | `SwarmAttribution` class | Distributed consensus without backpropagation |

### Why Hyperbolic Space?

Standard Euclidean embeddings suffer from **hierarchy collapse** - the "Bank" problem where multiple meanings compete for the same coordinate region. Hyperbolic geometry (Poincare disk) provides:

- **Exponential Volume Expansion**: Space grows exponentially from origin to boundary
- **Natural Hierarchy Mapping**: Abstract concepts at origin, specific instances at boundary
- **Geodesic Reasoning**: Logical inference as shortest-path computation through curved space

```typescript
// Example: Encoding hierarchical data in Poincare disk
import { HyperbolicEncoder } from '@pmoves/chit';

const encoder = new HyperbolicEncoder({ curvature: -1 });

const hierarchy = {
  id: 'logistics',
  label: 'Logistics',
  value: 1.0,
  children: [
    { id: 'shipping', label: 'Shipping', value: 0.6, children: [] },
    { id: 'storage', label: 'Storage', value: 0.4, children: [] }
  ]
};

const points = encoder.encodeHierarchy(hierarchy);
// Points near origin for 'logistics', near boundary for specific children
```

### Zeta-Inspired Spectral Filtering

The Riemann zeta zeros (γ_k ≈ 14.13, 21.02, 25.01, ...) represent intrinsic frequencies of prime number distribution. Using these as filter weights:

1. **Signal Enhancement**: Meaningful patterns often align with zeta resonances
2. **Noise Reduction**: Non-harmonic noise filtered out automatically
3. **Scale Invariance**: Works across different data granularities

```typescript
import { ZetaInspiredFilter } from '@pmoves/chit';

const filter = new ZetaInspiredFilter({ numZeros: 10 });

// Filter CGP spectrum array
const rawSpectrum = [0.8, 0.6, 0.3, 0.1, 0.9];
const filtered = filter.filterSpectrum(rawSpectrum);

// Compute similarity between two spectra
const similarity = filter.spectralSimilarity(spectrum1, spectrum2);

// Full spectral analysis
const analysis = filter.analyzeSpectrum(rawSpectrum);
// Returns: { filtered, dominantIndex, concentration, entropy }
```

## CGP (CHIT Geometry Packet) Format

### CGP v0.1 Core Structure

```json
{
  "spec": "chit.cgp.v0.1",
  "summary": "Human-readable description (max 200 chars)",
  "created_at": "2025-12-17T12:00:00Z",
  "super_nodes": [
    {
      "id": "unique-node-identifier",
      "label": "semantic-label",
      "summary": "Node description",
      "x": 0.0,
      "y": 0.0,
      "r": 0.3,
      "constellations": [
        {
          "id": "constellation-id",
          "summary": "Constellation description",
          "anchor": [0.5, 0.5, 0.5],
          "spectrum": [0.8, 0.6, 0.3],
          "points": [
            {
              "id": "point-id",
              "modality": "text",
              "proj": 0.95,
              "conf": 0.9,
              "summary": "Point content summary",
              "ref_id": "optional-external-reference"
            }
          ],
          "meta": {
            "namespace": "service-namespace"
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
  "...": "(all v0.1 fields)",
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
        { "id": "p1", "x": 0.2, "y": 0.3, "r": 0.36, "theta": 0.98 }
      ]
    }
  }
}
```

### Point Modality Types

| Modality | Description | Typical Source |
|----------|-------------|----------------|
| `text` | Text-based content | DeepResearch, summaries |
| `latent` | Embedding/latent space | Pipeline stages, internal state |
| `voice` | Voice synthesis | Flute Gateway |
| `economic_transaction` | FoodUSD spending | ToKenism |
| `token_distribution` | GroToken rewards | ToKenism |
| `group_savings` | GroupPurchase outcomes | ToKenism |
| `staking_position` | GroVault locks | ToKenism |
| `governance_vote` | CoopGovernor participation | ToKenism |
| `loyalty_event` | LoyaltyPoints activity | ToKenism |
| `reward_claim` | RewardsPool distributions | ToKenism |

## Service Integration

### Architecture Overview

```
                              GEOMETRY BUS (NATS)
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    │                                │                                │
┌───▼────┐   ┌────────────┐   ┌─────▼─────┐   ┌────────────┐   ┌─────▼─────┐
│ToKenism│   │consciousness│   │  Hi-RAG   │   │deepresearch│   │ supaserch │
│  CHIT  │──▶│   service   │──▶│    v2     │◀──│   +CGP     │◀──│   +CGP    │
│ modules│   │             │   │           │   │            │   │           │
└────────┘   └─────────────┘   └─────┬─────┘   └────────────┘   └───────────┘
    │                                │                                │
    │  tokenism.cgp.ready.v1         │  geometry.event.v1            │
    └────────────────────────────────┼────────────────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │  publisher  │
                              │   discord   │
                              └─────────────┘
```

### CGP Producers

| Service | NATS Subject | Env Var | Default |
|---------|--------------|---------|---------|
| **DeepResearch** | `tokenism.cgp.ready.v1` | `DEEPRESEARCH_CGP_PUBLISH` | `true` |
| **SupaSerch** | `tokenism.cgp.ready.v1` | `SUPASERCH_CGP_PUBLISH` | `true` |
| **Flute Gateway** | `tokenism.geometry.event.v1` | `CHIT_VOICE_ATTRIBUTION` | `false` |
| **Consciousness Service** | `tokenism.cgp.ready.v1` | (always enabled) | `true` |
| **ToKenism** | `tokenism.cgp.weekly.v1` | (always enabled) | `true` |

### CGP Consumers

| Service | Consumed Subjects | Integration Point |
|---------|-------------------|-------------------|
| **Hi-RAG Gateway v2** | `tokenism.cgp.ready.v1`, `geometry.*` | `POST /geometry/event` |
| **Publisher Discord** | `tokenism.*` | Formats as Discord embeds |
| **Shape Store** | `geometry.event.v1` | Persistence layer |

### Implementing CGP Publishing (Python Example)

```python
import json
from datetime import datetime, timezone

# Constants
CGP_SUBJECT = "tokenism.cgp.ready.v1"
CGP_PUBLISH_ENABLED = os.getenv("MY_SERVICE_CGP_PUBLISH", "true").lower() in {"1", "true", "yes", "on"}

def build_cgp_packet(result, request_id: str) -> dict:
    """Build CGP v0.1 compliant packet from service results."""

    # Build points from result data
    points = []
    for i, item in enumerate(result.items or []):
        points.append({
            "id": f"item:{i}",
            "modality": "text",  # or appropriate modality
            "proj": item.get("confidence", 1.0),
            "conf": item.get("quality", 0.9),
            "summary": item.get("summary", "")[:200],
            "ref_id": item.get("source_url", "")
        })

    # Compute spectrum from quality metrics
    spectrum = [
        result.quality_score if hasattr(result, 'quality_score') else 0.5,
        len(points) / 10.0,  # Normalized item count
        1.0 if result.status == "success" else 0.0
    ]

    return {
        "spec": "chit.cgp.v0.1",
        "summary": f"MyService: {result.query[:100]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": [
            {
                "id": f"myservice:{request_id}",
                "label": "myservice",
                "summary": result.summary or "Service result",
                "x": 0.0,
                "y": 0.0,
                "r": 0.3,
                "constellations": [
                    {
                        "id": f"myservice.results.{request_id}",
                        "summary": f"Results ({len(points)} items)",
                        "anchor": [0.5, 0.5, 0.5],
                        "spectrum": spectrum,
                        "points": points,
                        "meta": {
                            "namespace": "myservice",
                            "query": result.query,
                            "duration_ms": result.duration_ms
                        }
                    }
                ]
            }
        ],
        "meta": {
            "source": "myservice.result.v1",
            "tags": ["myservice", "automation"]
        }
    }

# In your result handler:
async def publish_result(result, request_id: str, nats_client):
    """Publish result to NATS, optionally with CGP."""

    # Standard result publishing
    await nats_client.publish(
        "myservice.result.v1",
        json.dumps(result.to_dict()).encode("utf-8")
    )

    # CGP publishing (if enabled)
    if CGP_PUBLISH_ENABLED:
        cgp_packet = build_cgp_packet(result, request_id)
        await nats_client.publish(
            CGP_SUBJECT,
            json.dumps(cgp_packet).encode("utf-8")
        )
```

### Implementing CGP Publishing (TypeScript Example)

```typescript
import { CGPGenerator, createCHITSystem } from '@pmoves/chit';

const chit = createCHITSystem({
  cgp: { namespace: 'myservice' }
});

// Build CGP from service result
function buildCGP(result: ServiceResult, requestId: string): CGPDocument {
  const points = result.items.map((item, i) => ({
    id: `item:${i}`,
    modality: 'text' as const,
    proj: item.confidence ?? 1.0,
    conf: item.quality ?? 0.9,
    summary: item.summary?.slice(0, 200) ?? '',
    ref_id: item.sourceUrl
  }));

  return {
    spec: 'chit.cgp.v0.1',
    summary: `MyService: ${result.query.slice(0, 100)}`,
    created_at: new Date().toISOString(),
    super_nodes: [{
      id: `myservice:${requestId}`,
      label: 'myservice',
      summary: result.summary ?? 'Service result',
      x: 0, y: 0, r: 0.3,
      constellations: [{
        id: `myservice.results.${requestId}`,
        summary: `Results (${points.length} items)`,
        anchor: [0.5, 0.5, 0.5],
        spectrum: [result.qualityScore ?? 0.5, points.length / 10, 1.0],
        points,
        meta: {
          namespace: 'myservice',
          query: result.query
        }
      }]
    }],
    meta: {
      source: 'myservice.result.v1',
      tags: ['myservice', 'automation']
    }
  };
}
```

## NATS Subject Reference

### ToKenism Attribution Events

| Subject | Purpose | Payload |
|---------|---------|---------|
| `tokenism.cgp.ready.v1` | CGP packet ready for consumption | CGP v0.1/v0.2 document |
| `tokenism.cgp.weekly.v1` | Weekly CGP export from ToKenism | CGP + metrics summary |
| `tokenism.attribution.recorded.v1` | Real-time attribution notification | Attribution record |
| `tokenism.swarm.population.v1` | Swarm population state update | SwarmMeta document |
| `tokenism.geometry.event.v1` | Voice/modality attribution | Geometry event |

### Geometry Core Events

| Subject | Purpose | Payload |
|---------|---------|---------|
| `geometry.swarm.meta.v1` | Decoder pack metadata | SwarmMeta document |
| `geometry.cgp.v1` | CGP via Supabase Realtime | CGP document |
| `geometry.event.v1` | Raw geometry events | Any CGP |

### Monitoring Commands

```bash
# Subscribe to all GEOMETRY events
nats sub "tokenism.>" "geometry.>"

# Monitor specific service CGP output
nats sub "tokenism.cgp.ready.v1" --max 10

# Verify service is publishing
docker logs deepresearch 2>&1 | grep CGP
docker logs supaserch 2>&1 | grep geometry_cgp
```

## Attribution System

### Dirichlet-Weighted Attribution

Attribution uses Dirichlet distributions to fairly weight contributions:

```typescript
import { DirichletWeights } from '@pmoves/chit';

const weights = new DirichletWeights({
  smoothingAlpha: 0.1,  // Spikiness (0.1 = spiky, 10 = uniform)
  concentrationK: 10,
  decayHalfLife: 4      // Weeks for contribution decay
});

// Record contributions
weights.addContribution('0xAlice', 100, 'spending', 1);
weights.addContribution('0xBob', 50, 'spending', 1);
weights.addContribution('0xAlice', 30, 'spending', 2);

// Get attribution weights (sums to 1.0)
const attribution = weights.getExpectedAttribution();
// [{ address: '0xAlice', weight: 0.72, ... }, { address: '0xBob', weight: 0.28, ... }]
```

### Merkle Proof Verification

All attributions are backed by Merkle proofs for auditability:

```typescript
import { ShapeAttribution } from '@pmoves/chit';

const attribution = new ShapeAttribution({
  merkle: { strategy: 'per_week', hashAlgorithm: 'sha256' }
});

// Record action
const chitId = attribution.recordAction({
  address: '0xAlice',
  action: 'spending',
  amount: 100,
  week: 12,
  category: 'groceries'
});

// Generate proof
const proof = attribution.generateProof(chitId);
// { merkleRoot, leafHash, path: [...] }

// Verify later
const isValid = attribution.verifyAttribution(record);
```

### Entropy-Based Value Assessment

Value is measured by **entropy reduction** - how much a contribution reduces uncertainty:

$$\Delta S = S_{\text{initial}} - S_{\text{final}}$$

- **High Value**: Contribution collapses uncertainty (drastic entropy reduction)
- **Low Value**: Redundant data confirming known information (minimal entropy change)

## Environment Variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `DEEPRESEARCH_CGP_PUBLISH` | deepresearch | `true` | Enable CGP publishing |
| `SUPASERCH_CGP_PUBLISH` | supaserch | `true` | Enable CGP publishing |
| `CHIT_VOICE_ATTRIBUTION` | flute-gateway | `false` | Enable voice attribution |
| `CHIT_NAMESPACE` | flute-gateway | `pmoves.voice` | Namespace for voice CGP |

## Testing & Validation

### CGP Schema Validation

```typescript
import { validateCGPDocument } from '@pmoves/chit';

const cgp = buildMyCGP();
const { valid, errors } = validateCGPDocument(cgp);

if (!valid) {
  console.error('CGP validation failed:', errors);
}
```

### Integration Test

```bash
# 1. Start NATS subscriber
nats sub "tokenism.cgp.ready.v1" --max 1 &

# 2. Trigger service that produces CGP
curl -X POST http://localhost:8099/v1/search?q=test

# 3. Verify CGP was published
# Subscriber should receive the CGP packet
```

## Related Documentation

- **NATS Subject Reference**: See "NATS Subject Reference" section above
- **Networking Guide**: `../multi-stack-networking-guide-2025.md`
- **Services Index**: `../services/README.md`
- **Mathematical Vision**: `Integrating Math into PMOVES.AI.md`
- **Human-Readable Guide**: `Human_side.md`
- **Integration Status**: `IMPLEMENTATION_STATUS.md`

## References

1. "Integrating Math into PMOVES.AI" - Architectural synthesis document
2. "Visionary AI: Global Network, Local Power" - Strategic vision
3. "Hyperbolic Computing vs Standard Computing" - Mathematical foundations
4. "The Human Construct Neural Network" - ZetaInspiredFilter origins
5. CGP v0.1/v0.2 Schema - `PMOVES-ToKenism-Multi/integrations/contracts/schemas/`
