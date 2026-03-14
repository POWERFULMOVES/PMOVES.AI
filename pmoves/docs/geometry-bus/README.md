# GEOMETRY BUS Integration Documentation

**Last Updated:** 2026-03-13
**Status:** Production Ready
**Schema Version:** `chit.cgp.v1.0`

---

## Overview

The GEOMETRY BUS is PMOVES.AI's event-driven architecture for CHIT Geometry Packets (CGP). It enables real-time geometric data flow between services, supporting consciousness theory representation, economic simulations, shape rendering, and agent attribution.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor': '#3ecf8e',
  'primaryBorderColor': '#3ecf8e',
  'secondaryColor': '#9333ea',
  'secondaryBorderColor': '#a855f7',
  'tertiaryColor': '#fbbf24',
  'tertiaryBorderColor': '#d97706',
  'background': 'transparent'
}}}%%
flowchart TD
    classDef publisher fill:#3ecf8e,stroke:#2db380,color:#000
    classDef subscriber fill:#9333ea,stroke:#7c2d12,color:#fff
    classDef bus fill:#fbbf24,stroke:#d97706,color:#000

    subgraph Publishers["Publishers"]
        CS["consciousness-service<br/>:8096"]:::publisher
        TS["Tokenism Simulator<br/>:8103"]:::publisher
        EC["EvoController<br/>:8113"]:::publisher
    end

    subgraph Subscribers["Subscribers"]
        HR["Hi-RAG v2<br/>:8086"]:::subscriber
        HD["Hyperdimensions"]:::subscriber
        BS["BoTZ CHIT Tools"]:::subscriber
    end

    NATS["NATS Geometry Bus"]:::bus

    CS -->|"geometry.cgp.v1"| NATS
    TS -->|"tokenism.cgp.weekly.v1"| NATS
    EC -->|"geometry.swarm.meta.v1"| NATS

    NATS --> HR
    NATS --> HD
    NATS --> BS
```

> **📊 Diagram Source:** [diagrams/architecture.mmd](diagrams/architecture.mmd)

---

## CGP Schema Version

**Canonical Reference:** `pmoves/chit/__init__.py` → `CGP_SPEC_VERSION = "chit.cgp.v1.0"`

All GEOMETRY BUS participants MUST use this canonical version. Legacy aliases (`cgp.v1`, `geometry.cgp.v1`) are resolved to this format.

### Version Naming Convention

- **Format:** `chit.cgp.v{major}.{minor}`
- **Current:** `chit.cgp.v1.0`
- **Legacy Aliases:** `cgp.v1` → `chit.cgp.v1.0`, `geometry.cgp.v1` → `chit.cgp.v1.0`

---

## Service Integration Map

### Publishers (CGP Producers)

| Service | Port | NATS Subjects | Purpose | Documentation |
|---------|------|---------------|---------|---------------|
| **consciousness-service** | 8096 | `geometry.cgp.v1`, `tokenism.cgp.ready.v1` | CHR algorithm → theory clustering | [consciousness-service.md](services/consciousness-service.md) |
| **tokenism-simulator** | 8103 | `tokenism.cgp.weekly.v1`, `tokenism.swarm.population.v1` | Economic simulations + attribution | [tokenism-simulator.md](services/tokenism-simulator.md) |
| **evo-controller** | 8113 | `geometry.swarm.meta.v1`, `geometry.cgp.calibration.v1` | CGP calibration via swarm optimization | [evo-controller.md](services/evo-controller.md) |
| **flute-gateway** | 8055 | `geometry.event.v1` (prosodic CGP) | Voice → geometric encoding | [flute-gateway.md](services/flute-gateway.md) |

### Subscribers (CGP Consumers)

| Service | Port | NATS Subjects | Purpose | Documentation |
|---------|------|---------------|---------|---------------|
| **hi-rag-gateway-v2** | 8086/8087 | `geometry.cgp.v1`, `tokenism.cgp.*` | Hybrid RAG with geometric indexing | [Hi-RAG v2](../../PMOVES-HiRAG/CLAUDE.md) |
| **hyperdimensions** | - | `geometry.cgp.v1` (via Portal) | Three.js WebGL shape rendering | [hyperdimensions.md](services/hyperdimensions.md) |
| **botz-skills** | - | `geometry.cgp.v1`, `geometry.packet.encoded.v1` | CHIT tools: encode, tokenism, render | [botz-skills.md](services/botz-skills.md) |
| **cipher-memory** | 8096 | `geometry.event.v1` | Persistent agent memory storage | [Cipher Memory](../../.claude/context/credentials-workflow.md) |

---

## NATS Subject Taxonomy

### Core Geometry Subjects

| Subject | Publisher | Subscribers | Payload Schema |
|---------|-----------|-------------|----------------|
| `geometry.cgp.v1` | consciousness-service, tokenism-simulator | Hi-RAG v2, hyperdimensions, BoTZ | [CGP v1.0](schemas/cgp-v1.0.md) |
| `geometry.event.v1` | All producers | shape-store, analytics | Generic geometric event |
| `geometry.swarm.meta.v1` | evo-controller | AgentGym, analytics | Swarm metadata |
| `geometry.cgp.calibration.v1` | evo-controller | Hi-RAG v2 | CGP calibration data |

### Tokenism Subjects

| Subject | Publisher | Subscribers | Payload Schema |
|---------|-----------|-------------|----------------|
| `tokenism.cgp.ready.v1` | consciousness-service | Hi-RAG v2, Tokenism | CGP ready signal |
| `tokenism.cgp.weekly.v1` | tokenism-simulator | Hi-RAG v2, Tokenism | Weekly CGP aggregation |
| `tokenism.swarm.population.v1` | tokenism-simulator | evo-controller, AgentGym | Swarm population snapshot |
| `tokenism.attribution.recorded.v1` | tokenism-simulator | analytics, audit | Attribution record |

### Integration Subjects

| Subject | Publisher | Subscribers | Purpose |
|---------|-----------|-------------|---------|
| `agentgym.train.completed.v1` | AgentGym | evo-controller | RL training completion |
| `geometry.packet.encoded.v1` | BoTZ CHIT tools | All consumers | Encoded CGP packet |

---

## Data Flow Examples

### CHR to Shapes Pipeline

```
1. User Request → POST /chr/run
   └─> TextUnit[] (theory texts)

2. CHR Clustering
   ├─> sentence-transformers embeddings
   ├─> Softmax-based clustering (K constellations)
   └─> MHEP quality metric

3. CGP Construction
   ├─> spec: "chit.cgp.v1.0"
   ├─> constellations[] with anchors
   └─> CHIT HMAC signing

4. NATS Publishing
   ├─> geometry.cgp.v1 → Hi-RAG v2, hyperdimensions
   └─> tokenism.cgp.ready.v1 → Tokenism

5. Shape Rendering (hyperdimensions)
   ├─> CGP → Three.js WebGL
   ├─> Prosodic mapping (bpm → geometry)
   └─> Interactive visualization
```

### YouTube to Persona Pipeline

```
1. PMOVES.YT (8077)
   ├─> YouTube download → MinIO
   └─> Transcript retrieval

2. Media Processing
   ├─> FFmpeg-Whisper (8078) → transcription
   ├─> Media-Video Analyzer (8079) → YOLOv8 frames
   └─> Extract Worker (8083) → embeddings

3. Hi-RAG v2 (8086)
   ├─> Vector + Graph + Full-text search
   └─> Theory extraction

4. consciousness-service (8096)
   ├─> CHR clustering on extracted theories
   └─> CGP generation

5. Persona Building
   ├─> PersonaGateService threshold evaluation
   ├─> Tokenism attribution tracking
   └─> NATS: geometry.cgp.v1 publication
```

### Ingest → CHIT Encode → Index Pipeline

```
1. Document Ingest (PDF Ingest 8092)
   └─> MinIO storage

2. Extract Worker (8083)
   ├─> Text embeddings (all-MiniLM-L6-v2)
   └─> Qdrant + Meilisearch indexing

3. CHIT Encoding (BoTZ /chit:encode)
   ├─> Geometry packet construction
   ├─> CHIT signing (if passphrase available)
   └─> geometry.packet.encoded.v1

4. Hi-RAG v2 Indexing (8086)
   ├─> Vector search integration
   ├─> Neo4j graph traversal
   └─> Full-text keyword matching
```

---

## CGP Packet Structure

### Canonical Schema (chit.cgp.v1.0)

```json
{
  "spec": "chit.cgp.v1.0",
  "summary": "Human-readable description",
  "created_at": "2026-03-13T12:00:00Z",
  "super_nodes": [{
    "id": "unique-super-node-id",
    "label": "Display label",
    "summary": "Description",
    "x": 0.5,
    "y": 0.3,
    "r": 10.0,
    "constellations": [{
      "id": "constellation-id",
      "summary": "Constellation description",
      "anchor": [0.25, 0.50, 0.25],
      "spectrum": [0.33, 0.33, 0.34],
      "points": [{
        "id": "point-id",
        "modality": "text|image|audio",
        "proj": 0.95,
        "conf": 0.9,
        "summary": "Point content"
      }],
      "meta": {
        "namespace": "pmoves.consciousness",
        "custom_field": "value"
      }
    }]
  }],
  "sig": {
    "alg": "HMAC-SHA256",
    "hmac": "base64-encoded-signature",
    "key_id": "CHIT_PROD_PASSPHRASE"
  },
  "meta": {
    "source": "service.name.version",
    "tags": ["tag1", "tag2"]
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec` | string | Yes | Schema version: `chit.cgp.v1.0` |
| `summary` | string | Yes | Human-readable description |
| `created_at` | string | Yes | ISO 8601 timestamp |
| `super_nodes` | array | Yes | Array of super nodes |
| `sig` | object | No | CHIT signature (if signed) |
| `meta` | object | No | Metadata (source, tags) |

---

## Environment Variables

### Required for Publishers

| Variable | Purpose | Default |
|----------|---------|---------|
| `NATS_URL` | NATS connection URL | `nats://nats:pmoves@nats:4222` |
| `CHIT_PROD_PASSPHRASE` | CGP signing key | Required for signing |
| `SERVICE_NAME` | Service identifier | `<service-name>` |
| `SERVICE_PORT` | HTTP port | Service-specific |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `ZETA_FILTER_ENABLED` | Enable zeta spectral filtering | `true` |
| `ZETA_NUM_ZEROS` | Number of zeta zeros | `10` |
| `HIRAG_V2_URL` | Hi-RAG v2 endpoint | `http://hi-rag-gateway-v2:8086` |

---

## Health & Monitoring

### Service Health Checks

All GEOMETRY BUS services expose:

```bash
# Standard health check
GET /healthz

# Response
{
  "status": "healthy",
  "service": "service-name",
  "version": "1.0.0",
  "nats_connected": true
}
```

### Prometheus Metrics

```bash
# Standard metrics endpoint
GET /metrics

# Common metrics
geometry_cgp_packets_published_total
geometry_cgp_publish_errors_total
geometry_nats_connection_status
```

### NATS Monitoring

```bash
# Monitor GEOMETRY BUS subjects
nats sub "geometry.>"
nats sub "tokenism.>"

# Check JetStream streams
nats stream info GEOMETRY_CGP
nats stream info TOKENISM_CGP
```

---

## Integration Guides

- [Consciousness Service](services/consciousness-service.md) - CHR algorithm and CGP generation
- [Tokenism Simulator](services/tokenism-simulator.md) - Economic simulations with attribution
- [Hyperdimensions](services/hyperdimensions.md) - Three.js shape rendering
- [Evo Controller](services/evo-controller.md) - CGP calibration via swarm optimization
- [BoTZ CHIT Skills](services/botz-skills.md) - CHIT tools and skills

---

## Pipeline Documentation

- [YouTube to Persona](pipelines/youtube-to-persona.md) - End-to-end persona building
- [CHR to Shapes](pipelines/chr-to-shapes.md) - Theory clustering to visualization
- [Ingest CHIT Index](pipelines/ingest-chit-index.md) - Document ingestion pipeline

---

## Schema Reference

- [CGP v1.0 Schema](schemas/cgp-v1.0.md) - Complete CGP packet specification
- [Swarm Meta Schema](schemas/swarm-meta.md) - Swarm metadata format
- [Attribution Schema](schemas/attribution.md) - Attribution record format

---

## Troubleshooting

### Common Issues

**Issue:** NATS connection failed
```
Solution: Verify NATS_URL includes credentials: nats://nats:pmoves@nats:4222
Check: nats server info
```

**Issue:** CGP spec version mismatch
```
Solution: Use canonical version "chit.cgp.v1.0"
Check: from pmoves.chit import CGP_SPEC_VERSION
```

**Issue:** Port conflicts
```
Solution: consciousness-service (8096) conflicts with cipher-memory
Use: docker compose --profile agents up consciousness-service
```

### Debug Commands

```bash
# Check NATS connectivity
nats pub "geometry.cgp.v1" '{"test": true}'

# Monitor all geometry subjects
nats sub "geometry.>" --raw

# Check service health
curl http://localhost:8096/healthz
curl http://localhost:8103/healthz
curl http://localhost:8113/healthz
```

---

## References

- **Geometry Bus Subjects:** `.claude/context/geometry-nats-subjects.md`
- **NATS Subjects:** `.claude/context/nats-subjects.md`
- **CHIT Module:** `pmoves/chit/__init__.py`
- **CGP Schema:** `pmoves/contracts/schemas/chit/cgp.v1.schema.json`
- **Hi-RAG v2:** `PMOVES-HiRAG/CLAUDE.md`
- **CONCH Integration:** `pmoves/docs/CONCH_INTEGRATION_MAP.md`
