# CHIT Integration Status by Service

> **Part of the [PMOVES.AI Integration Layer](../INTEGRATIONS_OVERVIEW.md)** | Category: CHIT & Geometry
>
> **See also:** [CHIT Documentation Suite](../PMOVESCHIT/README.md) for the complete documentation index with reading paths and glossary. | [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) for all Python tools.

**Last Updated:** March 7, 2026
**CHIT Protocol Version:** v0.1 (legacy), v0.2 (stable), v1.0 (current)
**Geometry Bus:** NATS-based event bus for geometric intelligence

---

## Overview

> **Mar 1 review wave completed.** Mar 4 promotion sync merged fix PRs across 5 submodules.
> Key status changes:
> - **Agent Zero**: Phase C P1s fixed (non-root USER, NATS auth hardened)
> - **BoTZ**: JWT `HAS_JOSE` fail-open still present at `auth.py:57-59` (tracked, fix PR merged Mar 4)
> - **DoX**: NATS auth fixed in `nats.conf`

### What is CHIT?

**CHIT (Context-Hybrid Information Token)** is PMOVES.AI's protocol for encoding, transmitting, and decoding geometric intelligence across services. It combines:

- **Hyperbolic Geometry** (Poincaré disk model) for hierarchical data encoding
- **Riemann Zeta Filtering** for spectral similarity analysis
- **Dirichlet Weight Attribution** for probabilistic contribution tracking
- **CGP (CHIT Geometry Packets)** as the data transport format

### Integration Levels

| Level | Description | Criteria |
|-------|-------------|----------|
| **Full** | Complete CHIT producer + consumer | Publishes AND consumes CGP, handles geometry events |
| **Partial** | Either producer OR consumer | Publishes CGP OR subscribes to geometry subjects |
| **None** | No CHIT integration | No geometry operations or NATS geometry subjects |

### CGP Version Support

| Version | Status | Features |
|---------|--------|----------|
| v0.1 | Stable (legacy) | Basic super_nodes/constellations structure |
| v0.2 | Stable | Attribution weights, Merkle proofs, signatures |
| v1.0 | Stable (current) | MACA consensus, hyperbolic encoding, point attribution, NATS metadata, spectrum zeta |

---

## Full CHIT Integration Services

### 1. Tokenism Simulator
**Port:** 8103
**Role:** Economic simulation with geometric attribution
**CGP Version:** v0.2
**Key Files:** `pmoves/services/tokenism-simulator/services/chit_encoder.py`

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)
- `tokenism.simulation.result.v1` (publish)
- `tokenism.calibration.result.v1` (publish)

**Capabilities:**
- Hyperbolic geometry for wealth distribution
- Temporal evolution geometries
- Calibration event encoding
- Multi-contract type handling

---

### 2. Hi-RAG Gateway v2
**Port:** 8086 (CPU), 8087 (GPU)
**Role:** Hybrid RAG with CHIT security verification
**CGP Version:** v0.1/v0.2
**Key Files:** `pmoves/services/hi-rag-gateway-v2/app.py`

**NATS Subjects:**
- `geometry.cgp.v1` (subscribe, publish)
- `geometry.swarm.meta.v1` (subscribe)
- Real-time geometry updates via Supabase

**Capabilities:**
- CHIT security verification via common `geometry_decoder.py` (`verify_cgp`, `decrypt_anchors`)
- Shape store integration for CGP ingestion
- Geometry swarm meta handling (pack activation/deactivate)
- Real-time geometry broadcasting

---

### 3. Gateway Service
**Port:** varies (internal)
**Role:** CHIT API endpoints and validation
**CGP Version:** v0.1/v0.2
**Key Files:** `pmoves/services/gateway/gateway/api/chit.py`

**API Endpoints:**
- `POST /geometry/event` - Ingest geometry events
- `POST /geometry/calibration/report` - Calibration metrics report

**Capabilities:**
- Full CGP ingestion and validation
- HMAC signature verification
- AES-GCM anchor decryption (optional)
- Text decoding via codebook projection
- Spectral calibration metrics (KL, JS divergence)
- ShapeStore integration
- Supabase synchronization

---

### 4. Neo4j Mind Map
**Port:** Gateway (via `/mindmap/{constellation_id}`)
**Role:** Graph-based constellation drill-down and visualization
**Key Files:** `pmoves/services/gateway/gateway/api/mindmap.py`

**Neo4j Graph Model:**
- `Anchor-[:FORMS]->Constellation-[:HAS]->Point-[:LOCATES]->MediaRef`

**API Endpoints:**
- `GET /mindmap/{constellation_id}` - Retrieve points and media for a constellation

**Capabilities:**
- Multi-modal point retrieval (text, video, audio, doc, image)
- Projection and confidence filtering
- Media reference resolution

---

### 5. Agent Zero
**Port:** 8080 (API), 8081 (UI)
**Role:** Agent orchestration with CHIT commands
**CGP Version:** v0.1/v0.2
**Key Files:** `pmoves/services/agent-zero/mcp_server.py`

**MCP Commands:**
- `geometry.publish_cgp` - Publish CGP to Hi-RAG
- `geometry.jump` - Navigate by geometry point ID
- `geometry.decode_text` - Extract text from geometry
- `geometry.calibration.report` - Get calibration metrics

**Capabilities:**
- CGP publishing to Hi-RAG gateway
- Geometry text decoding with embeddings
- Jump functionality by geometry point ID
- Calibration reporting integration

---

## Partial CHIT Integration Services

### 6. A2UI NATS Bridge
**Port:** 9224
**Role:** Bridge A2UI events to geometry bus
**Key Files:** `pmoves/services/a2ui-nats-bridge/bridge.py`

**NATS Subjects:**
- `geometry.>` (subscribe - wildcard)

**Gap:** Consumer-only, no CGP production

---

### 7. PMOVES.YT
**Port:** 8077
**Role:** YouTube ingestion with video CGP
**Key Files:** `pmoves/services/pmoves-yt/yt.py`

**NATS Subjects:**
- `geometry.cgp.v1` (publish)

**Gap:** Video CGP only, no audio geometry

---

### 8. DeepResearch Worker
**Port:** 8098
**Role:** LLM-based research planning
**Key Files:** `pmoves/services/deepresearch/worker.py`

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)

**Gap:** v0.1 packets only, no geometry consumption

---

### 9. SupaSerch
**Port:** 8099
**Role:** Multimodal search orchestration
**Key Files:** `pmoves/services/supaserch/app.py`

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)

**Gap:** CGP for search results only, no geometry consumption

---

### 10. Consciousness Service
**Port:** 8096
**Role:** Persona theory-to-geometry mapping
**Key Files:**
- `pmoves/services/consciousness-service/cgp_mapper.py`
- `pmoves/services/consciousness-service/persona_gate.py`

**NATS Subjects:**
- `persona.publish.result.v1` (publish)

**Gap:**
- CGP mapper exists but CHR pipeline not connected
- No theory proponent database integration
- No consciousness landscape visualization

---

### 11. Evo Controller
**Port:** 8113
**Role:** Evolutionary optimization for parameters
**Key Files:** `pmoves/services/evo-controller/app.py`

**NATS Subjects:**
- `geometry.swarm.meta.v1` (publish, subscribe)

**Gap:** Fitness landscape geometry incomplete

---

### 12. AgentGym RL Coordinator
**Port:** varies
**Role:** Reinforcement learning trajectory analysis
**Key Files:** `pmoves/services/agentgym-rl-coordinator/coordinator/trajectory.py`

**Gap:** Internal CGP consumption only, no NATS publishing

---

### 13. Flute Gateway
**Port:** 8055 (HTTP), 8056 (WebSocket)
**Role:** Voice prosodic synthesis
**Key Files:** `pmoves/services/flute-gateway/main.py`

**NATS Subjects:**
- `tokenism.geometry.event.v1` (publish)

**Gap:** Voice geometry only, no geometry consumption

---

## No CHIT Integration Services

| Service | Port | Purpose | Priority |
|---------|------|---------|----------|
| **Extract Worker** | 8083 | Text embedding & indexing | MEDIUM |
| **PDF Ingest** | 8092 | Document processing | LOW |
| **FFmpeg Whisper** | 8078 | Media transcription | MEDIUM |
| **Media Video Analyzer** | 8079 | YOLO object detection | MEDIUM |
| **Media Audio Analyzer** | 8082 | Emotion detection | MEDIUM |
| **Channel Monitor** | 8097 | Content watching | LOW |
| **Presign** | 8088 | MinIO URL signing | LOW |
| **Render Webhook** | 8085 | ComfyUI callbacks | LOW |
| **Publisher Discord** | 8094 | Discord notifications | LOW |
| **Publisher** | - | General publishing | LOW |
| **Chat Relay** | - | Message relay | LOW |
| **Mesh Agent** | - | Host announcement | LOW |
| **N8N** | - | Workflow automation | LOW |
| **GPU Orchestrator** | - | GPU management | LOW |
| **MCP YouTube Adapter** | - | YouTube adapter | LOW |

---

## Integration Guide

### Step 1: Add CGP Production to Your Service

```python
import asyncio
import nats
from pmoves.services.common.cgp_mappers import (
    map_health_weekly_summary_to_cgp,   # health domain
    map_finance_monthly_summary_to_cgp, # finance domain
)
# NOTE: There is no generic map_data_to_cgp. Use the domain-specific mapper
# that matches your data, or write a new one following the existing patterns.

async def publish_cgp(data: dict, subject: str = "geometry.cgp.v1"):
    """Publish CGP to NATS geometry bus"""
    nc = await nats.connect("nats://nats:pmoves@nats:4222")

    # Create CGP from your data using the appropriate domain mapper
    cgp = map_health_weekly_summary_to_cgp(data)  # or build custom CGP

    # Publish
    await nc.publish(subject, json.dumps(cgp).encode())
    await nc.close()
```

### Step 2: Subscribe to Geometry Subjects

```python
async def subscribe_geometry():
    """Subscribe to geometry bus events"""
    nc = await nats.connect("nats://nats:pmoves@nats:4222")

    async def handle_geometry(msg):
        cgp = json.loads(msg.data.decode())
        # Process incoming CGP
        await process_geometry(cgp)

    await nc.subscribe("geometry.>", cb=handle_geometry)
```

### Step 3: Use the Common Decoder

```python
from pmoves.services.common.geometry_decoder import GeometryDecoder, detect_cgp_version

decoder = GeometryDecoder()

# Detect version automatically
cgp = load_cgp_from_somewhere()
version = detect_cgp_version(cgp)  # "0.1" or "0.2"

# Extract text
texts = decoder.extract_text(cgp)

# Parse geometry
geometry = decoder.extract_geometry(cgp)

# Validate
valid = decoder.validate_cgp(cgp)
```

---

## NATS Subjects Reference

### Core Geometry Subjects
```text
geometry.cgp.v1              - Direct CGP transport
geometry.swarm.meta.v1       - Swarm optimization metadata
geometry.event.v1            - General geometry events
geometry.>                   - Wildcard for all geometry
```

### Tokenism Subjects
```text
tokenism.cgp.ready.v1        - CGP ready for consumption
tokenism.simulation.result.v1 - Simulation results
tokenism.calibration.result.v1 - Calibration metrics
tokenism.attribution.recorded.v1 - Attribution events
tokenism.geometry.event.v1   - Voice/audio geometry
```

### Service-Specific Subjects
```text
persona.publish.result.v1    - Consciousness service
research.deepresearch.*      - Deep research coordination
supaserch.*                  - Multimodal search
```

---

## CGP Structure Reference

### v0.1 Structure
```json
{
  "super_nodes": [
    {
      "label": "string",
      "constellations": [
        {
          "summary": "string",
          "points": [
            {"x": 0.5, "y": 0.3, "text": "content", "conf": 0.9}
          ]
        }
      ]
    }
  ]
}
```

### v0.2 Structure
```json
{
  "version": "0.2",
  "super_nodes": [...],
  "attribution": {
    "dirichlet_weights": [...],
    "merkle_proof": "..."
  },
  "signature": "HMAC..."
}
```

---

## Related Documentation

- **PMOVESCHIT Core Spec:** `pmoves/docs/PMOVESCHIT/PMOVESCHIT.md`
- **Geometry Bus Integration:** `pmoves/docs/PMOVESCHIT/GEOMETRY_BUS_INTEGRATION.md`
- **NATS Subjects Reference:** `.claude/context/geometry-nats-subjects.md`
- **CHIT Context:** `.claude/context/chit-geometry-bus.md`

---

## CGP Schema Version Naming Standardization

> **P0 documentation fix** — added 2026-02-25

Three naming schemes exist across the codebase:
- `cgp.v1` (legacy shorthand)
- `geometry.cgp.v1` (NATS subject namespace)
- `chit.cgp.v0.2` / `chit.cgp.v1.0` (KRISS KROSS ACK attestation)

**Canonical format:** `chit.cgp.v{major}.{minor}`

| Legacy Name | Canonical Name | Notes |
|-------------|----------------|-------|
| `cgp.v1` | `chit.cgp.v1.0` | Used in early integration code |
| `geometry.cgp.v1` | `chit.cgp.v1.0` | NATS subject retains `geometry.cgp.v1` for transport; schema `version` field should use `chit.cgp.v1.0` |
| `chit.cgp.v0.2` | `chit.cgp.v0.2` | Already canonical |

**Migration:** Services should set the JSON `version` field to `chit.cgp.vX.X` format. NATS subject names (`geometry.cgp.v1`) are transport identifiers and do not change.

---

**Document Owner:** PMOVES.AI Infrastructure Team
**Last Updated:** 2026-03-07
