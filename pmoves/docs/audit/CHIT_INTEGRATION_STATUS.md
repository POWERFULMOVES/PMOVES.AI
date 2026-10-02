# CHIT Integration Status by Service

> **Part of the [PMOVES.AI Integration Layer](../INTEGRATIONS_OVERVIEW.md)** | Category: CHIT & Geometry
>
> **See also:** [CHIT Documentation Suite](../PMOVESCHIT/README.md) for the complete documentation index with reading paths and glossary. | [CHIT Tools Catalog](../CHIT_TOOLS_CATALOG.md) for all Python tools.
> **Re-verified 2026-09-10 (crush-spark):** cipher MCP transport paths are
> `/api/mcp/sse` (the `/mcp/sse` form 404s); persona-thirdref joined the
> geometry bus with durable JetStream (stream `PMOVES-PERSONA`) — the first
> JetStream-persisted subject on SPARK; jellyfin-bridge now publishes playback
> events onto the bus (`persona.consumption.recorded.v1`). Per-service tiers
> below predate this verification; regenerate per-service rows from live
> probes before citing them as current.

**Last Updated:** March 24, 2026 (Neo4j Mind Map re-tiered 2026-10-01)

> **2026-10-01 (B850-CLAUDE, PR #3255):** Neo4j Mind Map moved Full → None,
> measured against the criteria below; reasoning in the "No CHIT Integration"
> section. Counts by section in this file: **4 Full, 11 Partial, 14 None.**
**CHIT Protocol Version:** v0.1 (legacy), v0.2 (stable), v1.0 (current)
**Geometry Bus:** NATS-based event bus for geometric intelligence

---

## Overview

> **Mar 24 CHIT integration wave 1 + context_id correlation.**
> Extract Worker + FFmpeg-Whisper publish CGP v1.0 packets with optional `context_id`
> correlation (body field or `X-Context-ID` header). Enables P7/upstream session tracing.
> Key status changes:
> - **Extract Worker**: None → Partial (CGP v1.0 producer, fire-and-forget NATS, context_id correlation)
> - **FFmpeg-Whisper**: None → Partial (CGP v1.0 producer, persistent NATS client, context_id correlation)
> - **DeepResearch**: Audit doc corrected to reflect v1.0 CGP + dual NATS publishing
>
> Previous: Mar 1 review wave, Mar 4 promotion sync (Agent Zero, BoTZ, DoX fixes)

### What is CHIT?

**CHIT (Compressed Hierarchical Information Transfer)** is PMOVES.AI's protocol for encoding, transmitting, and decoding geometric intelligence across services. It combines:

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

**CHIT (2026-07 P0 completion):** consumer-edge signature gate in
`geometry_handler` via `cgp_passes_signature_gate()` (canonical
`services.common.geometry_decoder.verify_cgp`): tampered packets always
dropped when a key is set; unsigned dropped under `CHIT_REQUIRE_SIGNATURE`;
rejections counted in `a2ui_geometry_events_rejected_total`. Tests:
`tests/test_signature_gate.py`.

**Gap:** Consumer-only, no CGP production (by design — UI edge)

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
**CGP Version:** v1.0

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)
- `research.deepresearch.result.v1` (publish)

**Gap:** Producer only, no geometry consumption

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
**Port:** 8106
**Role:** CHR clustering + persona theory-to-geometry mapping
**Key Files:**
- `pmoves/services/consciousness-service/main.py` (CHR pipeline + NATS publisher)
- `pmoves/services/consciousness-service/chr_algorithm.py` (canonical CHIT signing)
- `pmoves/services/consciousness-service/cgp_mapper.py`
- `pmoves/services/consciousness-service/persona_gate.py`

**NATS Subjects:**
- `geometry.cgp.v1` (publish — signed CHR CGP)
- `tokenism.cgp.ready.v1` (publish)
- `persona.publish.result.v1` (publish)

**CHIT (2026-07 P0 completion):** signs via the canonical
`pmoves.tools.chit_security.sign_cgp` (aligned standalone fallback kept for
images without `pmoves.tools`); key chain `CHIT_SIGNING_KEY` >
`CHIT_PASSPHRASE` (legacy `CHIT_PROD_PASSPHRASE` still honored);
`CHIT_REQUIRE_SIGNATURE` fail-closed; `cgp_mapper.publish_to_hirag` signs at
the publish boundary. Tests: `tests/test_chit_signing.py` (incl.
fallback-parity against the canonical signer).

**Gap:**
- No theory proponent database integration
- No consciousness landscape visualization
- Neo4j signature persistence (CLAUDE.md step 3) deferred — service holds no
  Neo4j client. **Corrected 2026-10-01:** graph persistence does NOT happen
  downstream via Hi-RAG. hi-rag-gateway-v2 has zero Neo4j writes (it only
  reads, `clients/neo4j.py`, `routes/geometry.py`); its `_persist_cgp_to_db`
  writes Postgres, with no `sig` column. Nothing persists this service's
  signed CGP into the graph today.

---

### 10. Evo Controller
**Port:** 8113
**Role:** Evolutionary optimization for parameters
**Key Files:** `pmoves/services/evo-controller/app.py`

**NATS Subjects:**
- `geometry.swarm.meta.v1` (publish, subscribe)

**CHIT (2026-07 P0 completion):** signs the `geometry.swarm.meta.v1` payload
before publish (via Agent Zero events API) and verifies inbound CGP
signatures in `_filter_verified_cgps` (tampered always dropped; unsigned
dropped under `CHIT_REQUIRE_SIGNATURE`); uses the canonical
`services.common.geometry_decoder` wrappers; `/config` exposes
`chit_signing_enabled`/`chit_signature_required`. Tests:
`tests/test_chit_signing.py`.

**Gap:** Fitness landscape geometry incomplete

---

### 11. AgentGym RL Coordinator
**Port:** varies
**Role:** Reinforcement learning trajectory analysis
**Key Files:** `pmoves/services/agentgym-rl-coordinator/coordinator/trajectory.py`

**Gap:** Internal CGP consumption only, no NATS publishing

---

### 12. Flute Gateway
**Port:** 8055 (HTTP + WebSocket — a single uvicorn bind; 8056 is published by compose but nothing listens on it)
**Role:** Voice prosodic synthesis
**Key Files:** `pmoves/services/flute-gateway/main.py`

**NATS Subjects:**
- `tokenism.geometry.event.v1` (publish)

**Gap:** Voice geometry only, no geometry consumption

---

### 13. Cast TTS Gateway
**Port:** 8060
**Role:** Chromecast/Google Home TTS routing with voice attribution
**Key Files:** `pmoves/services/cast-tts-gateway/service.py`

**NATS Subjects:**
- `voice.cast.completed.v1` (publish)
- `voice.cast.failed.v1` (publish)
- `voice.cast.health_alert.v1` (publish)
- `device.cast.discovered.v1` (publish)

**Attribution Chain:** voice profile → TTS provider (Flute/Ultimate-TTS/Google) → Cast device. CHIT env vars present (`CHIT_REQUIRE_SIGNATURE`, `CHIT_DECRYPT_ANCHORS`, `CHIT_PASSPHRASE`); `attribution_gated: true`.

**Gap:** Attribution decisions are made but not yet encoded as CGP packets. Next step: encode voice→provider→device provenance as CGP points with Dirichlet weights across providers. TAC tree: `pmoves/configs/tac_trees/cast-gateway.tac.yaml`.

---

### 14. Extract Worker
**Port:** 8083
**Role:** Text embedding & indexing to Qdrant + Meilisearch
**Key Files:** `pmoves/services/extract-worker/worker.py`
**CGP Version:** v1.0

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)
- `skills.step.extract-worker.done.v1` (publish)

**Correlation:** Accepts optional `context_id` via request body or `X-Context-ID` header. Propagated to CGP `meta.context_id` and NATS hook payload.

**Gap:** Producer only, no geometry consumption

---

### 15. FFmpeg-Whisper
**Port:** 8078
**Role:** Media transcription (Whisper, Qwen2-Audio)
**Key Files:** `pmoves/services/ffmpeg-whisper/server.py`
**CGP Version:** v1.0

**NATS Subjects:**
- `tokenism.cgp.ready.v1` (publish)
- `ingest.transcript.ready.v1` (publish)

**Correlation:** Accepts optional `context_id` via request body or `X-Context-ID` header (both `/transcribe` and `/transcribe_file`). Propagated to CGP `meta.context_id` and NATS hook payload.

**Gap:** Producer only, no geometry consumption

---

## No CHIT Integration Services

| Service | Port | Purpose | Priority |
|---------|------|---------|----------|
| **PDF Ingest** | 8092 | Document processing | LOW |
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
| **Neo4j Mind Map** | gateway `/mindmap` | Graph read of Constellation/Point (re-tiered from Full, see below) | MEDIUM |

### Neo4j Mind Map — re-tiered Full → None (2026-10-01)

Measured against this document's own criteria (Integration Levels table):
**Full** needs "Publishes AND consumes CGP, handles geometry events";
**Partial** needs "Publishes CGP OR subscribes to geometry subjects". The mind
map does neither:

- `GET /mindmap/{constellation_id}` (`services/gateway/gateway/api/mindmap.py`)
  is a plain Cypher read. It publishes nothing and subscribes to nothing.
- `services/gateway` has no stanza in any compose file, so that endpoint is not
  deployed. The live read is the hi-rag v2 route, also a plain read.
- No node in the graph carries a CHIT signature. The model this section used
  to cite, `Anchor-[:FORMS]->Constellation`, is never written by any writer
  (the seed files create FORMS only between unlabeled nodes).
- The gateway's CGP writer (`api/workflow.py` `_upsert_neo4j`) ingests an
  UNSIGNED `chit.cgp.v0.1` document and is undeployed.

graph-linker (PR #3255) now persists `chit_sig` / `chit_kid` /
`chit_signed_at` on the `Asset`, `Generation`, `Media`, `Topic`, `Namespace` and `KBItem` nodes and the `HAS_TOPIC` edge (NOT `Agent`, `Workflow`, or the `EMITTED`/`PRODUCED`/`USED_WORKFLOW`/`CONTAINS` edges), and refuses unsigned writes. A stored signature is verifiable only against the source event: the MAC covers the write's Cypher parameter dict, and the node keeps a transformed subset of it (e.g. `ts` is stored as `datetime()`), so `chit_signer.verify_write()` needs the original event parameters, not just the node. That is
signature persistence on Neo4j writes, not CGP flow: graph-linker consumes
`gen.image.result.v1`, `analysis.extract_topics.result.v1` and
`kb.upsert.request.v1`, none of which is a geometry subject. It therefore does
NOT meet the Partial criterion, and the mind map stays **None** until a
deployed writer consumes geometry subjects (the gateway CGP writer, once
deployed and signing) or the reader verifies signatures. The signatures use
the deployment-wide key, so they attribute a writer; they do not authenticate
one (`verify_cgp_detailed` reports OK_UNPINNED).

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
**Last Updated:** 2026-03-24
