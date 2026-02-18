# CHIT & Geometry Bus - Complete Reference

> **Canonical CHIT documentation:** [pmoves/docs/PMOVESCHIT/README.md](../../pmoves/docs/PMOVESCHIT/README.md) — structured 5-layer documentation suite with reading paths, glossary, and full file index.

**Purpose:** Comprehensive reference for CHIT (Compressed Hierarchical Information Transfer) protocol and the PMOVES Geometry Bus - a universal geometric data fabric enabling hyperbolic encoding, swarm intelligence, and geometric reasoning.

**Last Updated:** 2026-01-31

---

## Quick Start

### For Users

The Geometry Bus is the backbone that connects PMOVES subsystems through geometric intelligence. Most users interact with it indirectly through:
- **Tokenism** - Economic projections visualized as geometry
- **DoX** - Document embeddings in hyperbolic space
- **Voice Agents** - Prosodic speech with geometric properties

### For Developers

1. **Publish CGP packets:**
   ```bash
   nats pub "tokenism.cgp.weekly.v1" '{"cgp": "base64data", "metadata": {...}}'
   ```

2. **Subscribe to geometry events:**
   ```bash
   nats sub "geometry.>" --raw
   ```

3. **Use CHIT contracts:**
   ```typescript
   import { generateCGP } from '@pmoves/chit/contracts';
   const cgp = generateCGP(data);
   ```

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [CHIT Protocol](#chit-protocol)
3. [Geometry Bus (NATS)](#geometry-bus-nats)
4. [Integration Patterns](#integration-patterns)
5. [Contract Reference](#contract-reference)
6. [Mathematical Foundations](#mathematical-foundations)
7. [Implementation Guide](#implementation-guide)
8. [Reference](#reference)

---

## Architecture Overview

### What is CHIT?

**CHIT** (Compressed Hierarchical Information Transfer) is a protocol for encoding complex data structures into compact geometric representations. It enables:
- **Lossless compression** of hierarchical data
- **Geometric reasoning** over encoded information
- **Hyperbolic embeddings** for tree-like structures
- **Swarm intelligence** through geometric attributes

### What is the Geometry Bus?

The **Geometry Bus** is a NATS-based message bus that transports CGP packets between PMOVES subsystems. It provides:
- **Publish/Subscribe** messaging for geometry events
- **Stream persistence** via JetStream
- **Subject-based routing** for different geometry types
- **Cross-subsystem integration**

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PMOVES.AI Ecosystem                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     CGP      ┌──────────────┐                        │
│  │  Tokenism    │─────────────▶│     DoX      │                        │
│  │ (Producer)   │              │  (Consumer)   │                        │
│  └──────┬───────┘              └──────┬───────┘                        │
│         │                              │                                │
│         │ CGP                          │ Geometry Events                │
│         ▼                              ▼                                │
│  ┌────────────────────────────────────────────┐                        │
│  │         CHIT Geometry Bus (NATS)           │                        │
│  │  ┌──────────────────────────────────────┐  │                        │
│  │  │  JetStream: GEOMETRY                 │  │                        │
│  │  │  Subjects:                           │  │                        │
│  │  │  - tokenism.cgp.*                    │  │                        │
│  │  │  - geometry.*                        │  │                        │
│  │  └──────────────────────────────────────┘  │                        │
│  └────────────────────────────────────────────┘                        │
│         │                              │                                │
│         ▼                              ▼                                │
│  ┌──────────────┐              ┌──────────────┐                        │
│  │ Voice Agents │              │   Agent Zero │                        │
│  │ (Consumer)   │              │ (Consumer)   │                        │
│  └──────────────┘              └──────────────┘                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## CHIT Protocol

### CGP Format

**CGP** (Compact Geometry Packet) is the core data structure:

```typescript
interface CGP {
  version: "0.2";           // Protocol version
  type: "attribution" | "hyperbolic" | "dirichlet";
  encoding: "base64";       // Always base64 for transmission
  timestamp: string;        // ISO 8601
  source: string;           // Producer identifier
  geometry: {
    dimension: number;      // 2 (disk) or 3 (manifold)
    curvature: number;      // Negative for hyperbolic
    points: Array<number>;  // Encoded geometry
  };
  metadata: Record<string, unknown>;
}
```

### Encoding Types

| Type | Description | Use Case |
|------|-------------|----------|
| `attribution` | Source attribution with geometric weights | Multi-source data fusion |
| `hyperbolic` | Hyperbolic space encoding (Poincaré disk) | Hierarchical data |
| `dirichlet` | Dirichlet distribution encoding | Probability distributions |

### Compression

CHIT uses lossless compression optimized for:
- **Repeated patterns** - Run-length encoding for sequences
- **Hierarchical structure** - Dictionary encoding for tree nodes
- **Floating-point precision** - Variable precision for coordinates

Typical compression ratios:
- Text documents: 10:1
- Numerical data: 5:1
- Mixed content: 7:1

---

## Geometry Bus (NATS)

### Stream Configuration

```bash
# GEOMETRY stream
Stream: GEOMETRY
Subjects: tokenism.cgp.*, geometry.*
Storage: File
Max Age: 30d
Replicas: 1
```

### Subject Hierarchy

```
geometry.                      # Wildcard for all geometry events
├── geometry.event.v1           # General geometry events
├── geometry.manifold.*         # Manifold operations
├── geometry.zeta.*            # Riemann Zeta operations
└── tokenism.                  # Tokenism namespace
    ├── tokenism.cgp.weekly.v1  # Weekly economic CGP exports
    └── tokenism.cgp.ready.v1   # CGP availability notifications
```

### Message Format

All messages on the Geometry Bus are JSON:

```json
{
  "subject": "tokenism.cgp.weekly.v1",
  "timestamp": "2026-01-31T12:00:00Z",
  "cgp": "base64_encoded_geometry_data",
  "metadata": {
    "source": "tokenism-simulator",
    "week": 52,
    "scenario": "baseline",
    "confidence": "HIGH"
  }
}
```

---

## Integration Patterns

### Producer Pattern (Tokenism)

Tokenism produces CGP packets for economic simulations:

```typescript
import { generateCGP } from '@pmoves/chit/contracts/cgp-generator';
import { encodeHyperbolic } from '@pmoves/chit/contracts/hyperbolic-encoder';

// 1. Run simulation
const simulation = await runSimulation({ weeks: 260 });

// 2. Encode results as hyperbolic geometry
const geometry = encodeHyperbolic(simulation.results);

// 3. Generate CGP packet
const cgp = generateCGP({
  type: 'hyperbolic',
  geometry,
  metadata: {
    source: 'tokenism-simulator',
    week: simulation.week,
    confidence: simulation.confidence
  }
});

// 4. Publish to NATS
await nats.publish('tokenism.cgp.weekly.v1', JSON.stringify(cgp));
```

### Consumer Pattern (DoX)

DoX consumes CGP packets for visualization:

```typescript
// Subscribe to CGP packets
const sub = nats.subscribe('tokenism.cgp.>');

for await (const msg of sub) {
  const cgp = JSON.parse(msg.data);

  // Decode geometry
  const geometry = decodeCGP(cgp.cgp);

  // Visualize in hyperbolic space
  visualizePoincareDisk(geometry);
}
```

### Service Integration

Services integrate via **CHIT Geometry Contracts**:

| Subsystem | Contract Location | Type |
|-----------|-------------------|------|
| Tokenism | `/PMOVES-ToKenism-Multi/integrations/contracts/chit/` | Producer |
| DoX | `/PMOVES-DoX/backend/app/contracts/` | Consumer |
| Voice Agents | `/pmoves/services/flute-gateway/contracts/` | Optional |

---

## Contract Reference

### Tokenism Contracts

Location: `/PMOVES-ToKenism-Multi/integrations/contracts/chit/`

#### cgp-generator.ts

Generates CGP packets from simulation data.

```typescript
export function generateCGP(config: CGPConfig): CGP {
  return {
    version: "0.2",
    type: config.type || "attribution",
    encoding: "base64",
    timestamp: new Date().toISOString(),
    source: config.source,
    geometry: config.geometry,
    metadata: config.metadata
  };
}
```

#### shape-attribution.ts

Attribution analysis using geometric shapes.

```typescript
export function analyzeAttribution(
  data: AttributionData
): ShapeAttribution {
  // Analyzes data distribution
  // Returns geometric shape (sphere, ellipsoid, hyperboloid)
}
```

#### swarm-attribution.ts

Collective intelligence for swarm behavior.

```typescript
export function swarmIntelligence(
  agents: Agent[],
  context: SwarmContext
): SwarmDecision {
  // Aggregates agent decisions
  // Uses geometry for consensus
}
```

#### hyperbolic-encoder.ts

Encodes data into hyperbolic space.

```typescript
export function encodeHyperbolic(
  data: HierarchicalData
): HyperbolicGeometry {
  // Projects data onto Poincaré disk
  // Returns coordinates and curvature
}
```

#### zeta-filter.ts

Riemann Zeta function filtering.

```typescript
export function zetaFilter(
  signal: number[],
  threshold: number
): number[] {
  // Applies Riemann Zeta transform
  // Filters based on spectral properties
}
```

---

## Mathematical Foundations

### Hyperbolic Geometry

PMOVES uses **Poincaré disk model** for hyperbolic space:

- **Space**: Unit disk `{z ∈ ℂ : |z| < 1}`
- **Metric**: `ds² = 4(dx² + dy²) / (1 - x² - y²)²`
- **Curvature**: Constant negative curvature K = -1

**Properties:**
- Exponential growth of space with distance
- Ideal for hierarchical/tree-like data
- Efficient embedding of taxonomies

### Dirichlet Attribution

**Dirichlet distribution** for multi-source attribution:

```
P(θ|α) = (1/B(α)) ∏ θᵢ^(αᵢ - 1)
```

Where:
- `θ` - Probability vector (sums to 1)
- `α` - Concentration parameters
- `B(α)` - Multivariate beta function

**Use cases:**
- Source attribution for blended data
- Confidence scoring
- Mixture modeling

### Riemann Zeta Function

**Zeta function** for spectral filtering:

```
ζ(s) = Σ (1/nˢ) for n = 1 to ∞
```

**Applications:**
- Frequency domain filtering
- Harmonic analysis
- Prime number distributions

### Geometric Intelligence

**Manifold Detection** analyzes embedding distributions:

| Manifold | Property | Detection Method |
|----------|----------|------------------|
| Hyperbolic | K < 0 | Triangular inequality violation |
| Spherical | K > 0 | Uniform angular distribution |
| Euclidean | K = 0 | Linear scaling preserved |

**Curvature Analysis** determines knowledge structure shape:

```python
def detect_manifold(embeddings):
  """Detect geometric properties of embedding space."""
  # Compute curvature
  curvature = compute_curvature(embeddings)

  if curvature < -0.1:
    return "hyperbolic"
  elif curvature > 0.1:
    return "spherical"
  else:
    return "euclidean"
```

---

## Implementation Guide

### Setup

1. **Install dependencies:**
   ```bash
   cd /PMOVES-ToKenism-Multi
   npm install
   ```

2. **Configure NATS:**
   ```bash
   # From PMOVES.AI root
   docker compose up -d nats
   ```

3. **Verify connection:**
   ```bash
   nats server check
   nats stream ls
   ```

### Publish CGP

```bash
# Publish geometry packet
nats pub "tokenism.cgp.weekly.v1" <<EOF
{
  "subject": "tokenism.cgp.weekly.v1",
  "timestamp": "2026-01-31T12:00:00Z",
  "cgp": "base64datahere",
  "metadata": {
    "source": "tokenism-simulator",
    "week": 52
  }
}
EOF
```

### Subscribe to Events

```bash
# Monitor all geometry events
nats sub "geometry.>" --raw

# Monitor Tokenism CGP only
nats sub "tokenism.cgp.>" --raw
```

### TypeScript Integration

```typescript
import { connect } from 'nats';
import { generateCGP } from '@pmoves/chit/contracts';

// Connect to NATS
const nc = await connect({ servers: 'nats://localhost:4222' });

// Generate CGP
const cgp = generateCGP({
  type: 'hyperbolic',
  geometry: { /* ... */ },
  metadata: { source: 'my-service' }
});

// Publish
nc.publish('tokenism.cgp.weekly.v1', JSON.stringify(cgp));
```

### Python Integration

```python
import nats
import json

async def publish_geometry():
    nc = await nats.connect("nats://localhost:4222")

    cgp = {
        "version": "0.2",
        "type": "hyperbolic",
        "encoding": "base64",
        "timestamp": "2026-01-31T12:00:00Z",
        "source": "python-service",
        "geometry": {"points": [...]},
        "metadata": {}
    }

    await nc.publish("tokenism.cgp.weekly.v1", json.dumps(cgp).encode())
```

---

## Reference

### NATS Commands

```bash
# Server status
nats server check

# Stream management
nats stream ls
nats stream info GEOMETRY

# Consumer management
nats consumer ls GEOMETRY
nats consumer info GEOMETRY <consumer>

# Subject monitoring
nats sub "geometry.>" --raw
nats pub "geometry.event.v1" '{"test": "data"}'
```

### Subject Reference

| Subject | Direction | Description |
|---------|-----------|-------------|
| `tokenism.cgp.weekly.v1` | Pub | Weekly economic CGP exports |
| `tokenism.cgp.ready.v1` | Pub | CGP availability notification |
| `geometry.event.v1` | Pub | General geometry events |
| `geometry.manifold.*` | Pub | Manifold operations |
| `geometry.zeta.*` | Pub | Zeta filter operations |
| `tokenism.cgp.>` | Sub | All Tokenism CGP (wildcard) |
| `geometry.>` | Sub | All geometry events (wildcard) |

### Documentation Files

| File | Purpose |
|------|---------|
| `/pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md` | Technical integration |
| `/pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md` | Mathematical foundations |
| `/pmoves/docs/PMOVESCHIT/Human_side.md` | User-facing guide |
| `/.claude/context/geometry-nats-subjects.md` | NATS subject reference |

### Related Documentation

- `/docs/subsystems/SUBSYSTEM_INTEGRATION.md` - Full subsystem guide
- `/docs/subsystems/VOICE_AGENTS.md` - Voice agents integration
- `/PMOVES-ToKenism-Multi/README.md` - Tokenism documentation

### API Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Tokenism Simulator | `POST /cgp/export` | Export CGP packets |
| Tokenism Simulator | `GET /cgp/status` | CGP availability |
| DoX | `POST /geometry/visualize` | Visualize CGP |

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `NATS: connection refused` | NATS not running | Start NATS: `docker compose up -d nats` |
| `Invalid CGP version` | Version mismatch | Update CGP to v0.2 |
| `Base64 decode failed` | Corrupted CGP | Regenerate CGP packet |
| `Stream not found` | GEOMETRY stream missing | Create stream: `nats stream add GEOMETRY` |

---

## Glossary

| Term | Definition |
|------|------------|
| **CGP** | Compact Geometry Packet - encoded geometric data |
| **CHIT** | Compressed Hierarchical Information Transfer - the protocol |
| **Geometry Bus** | NATS-based message bus for CGP transport |
| **Hyperbolic encoding** | Projecting data onto Poincaré disk |
| **Dirichlet attribution** | Multi-source attribution using Dirichlet distribution |
| **Manifold detection** | Determining geometric properties of embeddings |
| **Swarm intelligence** | Collective decision-making via geometry |

---

## Contributing

When adding new geometry features:

1. **Update contracts** in `/PMOVES-ToKenism-Multi/integrations/contracts/chit/`
2. **Add NATS subjects** to `/.claude/context/geometry-nats-subjects.md`
3. **Document in** this reference
4. **Test with** `nats sub "geometry.>"` to verify

---

## Changelog

### v0.2 (2026-01-31)
- Consolidated documentation
- Added contract reference
- Mathematical foundations section
- Implementation guide

### v0.1 (2025-12-15)
- Initial CHIT protocol
- Geometry bus NATS integration
- Tokenism CGP exports
