# CHIT Integration Status by Service

**Last Updated:** December 30, 2025
**CHIT Protocol Version:** v0.1 (legacy), v0.2 (current)
**Geometry Bus:** NATS-based event bus for geometric intelligence

---

## Overview

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
| v0.2 | Stable (current) | Attribution weights, Merkle proofs, signatures |

---

## Full CHIT Integration Services

### 1. Tokenism Simulator
**Port:** 8103
**Role:** Economic simulation with geometric attribution
**CGP Version:** v0.2
**Key Files:** `pmoves/services/tokenism-simulator/chit_encoder.py`

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
- CHIT security verification (`verify_cgp`, `decrypt_anchors`)
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
- `POST /geometry/calibrate` - Calibrate geometry parameters

**Capabilities:**
- Full CGP ingestion and validation
- HMAC signature verification
- AES-GCM anchor decryption (optional)
- Text decoding via codebook projection
- Spectral calibration metrics (KL, JS divergence)
- ShapeStore integration
- Supabase synchronization

---

### 4. Agent Zero
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

### 5. A2UI NATS Bridge
**Port:** 9224
**Role:** Bridge A2UI events to geometry bus
**Key Files:** `pmoves/services/a2ui-nats-bridge/bridge.py`

**NATS Subjects:**
- `geometry.>` (subscribe - wildcard)

**Gap:** Consumer-only, no CGP production

---

### 6. PMOVES.YT
**Port:** 8077
**Role:** YouTube ingestion with video CGP
**Key Files:** `pmoves/services/pmoves-yt/yt.py`

**NATS Subjects:**
- `geometry.cgp.v1` (publish)

**Gap:** Video CGP only, no audio geometry

---

### 7. DeepResearch Worker
**Port:** 8098
**Role:** LLM-based research planning
**Key Files:** `pmoves/services/deepresearch/worker.py`

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)

**Gap:** v0.1 packets only, no geometry consumption

---

### 8. SupaSerch
**Port:** 8099
**Role:** Multimodal search orchestration
**Key Files:** `pmoves/services/supaserch/app.py`

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)

**Gap:** CGP for search results only, no geometry consumption

---

### 9. Consciousness Service
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

### 10. Evo Controller
**Port:** 8113
**Role:** Evolutionary optimization for parameters
**Key Files:** `pmoves/services/evo-controller/app.py`

**NATS Subjects:**
- `geometry.swarm.meta.v1` (publish, subscribe)

**Gap:** Fitness landscape geometry incomplete

---

### 11. AgentGym RL Coordinator
**Port:** varies
**Role:** Reinforcement learning trajectory analysis
**Key Files:** `pmoves/services/agentgym-rl-coordinator/coordinator/trajectory.py`

**Gap:** Internal CGP consumption only, no NATS publishing

---

### 12. Flute Gateway
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
from pmoves.services.common.cgp_mappers import map_data_to_cgp

async def publish_cgp(data: dict, subject: str = "geometry.cgp.v1"):
    """Publish CGP to NATS geometry bus"""
    nc = await nats.connect("nats://nats:4222")

    # Create CGP from your data
    cgp = map_data_to_cgp(data)  # or build custom CGP

    # Publish
    await nc.publish(subject, json.dumps(cgp).encode())
    await nc.close()
```

### Step 2: Subscribe to Geometry Subjects

```python
async def subscribe_geometry():
    """Subscribe to geometry bus events"""
    nc = await nats.connect("nats://nats:4222")

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

**Document Owner:** PMOVES.AI Infrastructure Team
**Last Updated:** 2025-12-30
