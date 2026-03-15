# CONCH Pipeline Integration Map

**Last Updated:** 2026-03-13
**PR:** #905 - CONCH Pipeline Implementation

## Overview

The CONCH (Consciousness Harvest) pipeline implements CHR (Constellation Harvest Regularization) algorithm for geometric clustering of text embeddings into CGP (CHIT Geometry Packets). It integrates with multiple PMOVES.AI services via NATS event bus, REST APIs, and database connections.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONCH Pipeline Architecture                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Supabase  │───▶│consciousness│───▶│    NATS     │───▶│  Hi-RAG v2  │  │
│  │  (Theories) │    │  Service    │    │ Geometry Bus│    │  (Indexer)  │  │
│  └─────────────┘    │   (8096)    │    └─────────────┘    └─────────────┘  │
│           │          └──────┬──────┘           │                              │
│           │                 │                  │                              │
│           ▼                 ▼                  ▼                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │   Neo4j    │    │ Tokenism    │    │  SupaSerch  │                      │
│  │ (Entities) │    │ Simulator   │    │            │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Dependencies

### Upstream Data Sources

| Service | Purpose | Integration Type | Endpoint/Method |
|---------|---------|------------------|-----------------|
| **Supabase** | Theory storage | REST API | `GET /rest/v1/pmoves_core.consciousness_theories` |
| **Neo4j** | Entity graph | Cypher queries | `POST /db/neo4j/tx/commit` |
| **Hi-RAG v2** | Embeddings (optional) | HTTP API | `POST /hirag/embed` |

### Downstream Consumers

| Service | Purpose | NATS Subject | Integration Type |
|---------|---------|--------------|------------------|
| **Hi-RAG v2** | CGP indexing | `geometry.cgp.v1`, `tokenism.cgp.ready.v1` | NATS subscribe |
| **Tokenism Simulator** | CGP processing | `tokenism.cgp.ready.v1` | NATS subscribe |
| **SupaSerch** | Research attribution | `geometry.cgp.v1` | NATS subscribe |
| **Cipher Memory** | Persistent storage | `geometry.event.v1` | NATS subscribe |

---

## NATS Subject Usage

### Published Subjects

| Subject | Payload | Frequency | Subscribers |
|---------|---------|-----------|-------------|
| `geometry.cgp.v1` | CGP packet | On CHR run | Hi-RAG v2, SupaSerch |
| `tokenism.cgp.ready.v1` | CGP packet | On CHR run | Tokenism, Hi-RAG v2 |

### CGP Packet Structure

```json
{
  "spec": "chit.cgp.v1.0",
  "summary": "CHR clustering with K=8 constellations, MHEP=0.85",
  "created_at": "2026-03-13T12:00:00Z",
  "super_nodes": [{
    "id": "consciousness-super",
    "label": "pmoves.consciousness",
    "summary": "CHR clustering results",
    "constellations": [{
      "id": "constellation-0",
      "summary": "Materialist theories",
      "anchor": [0.5, 0.3, 0.8],
      "spectrum": [0.8, 0.6, 0.4, 0.2, 0.1],
      "points": [{
        "id": "chunk-001",
        "modality": "text",
        "proj": 0.95,
        "conf": 0.9,
        "summary": "Physicalism is the theory..."
      }],
      "meta": {
        "namespace": "pmoves.consciousness",
        "mhep": 0.85
      }
    }]
  }],
  "sig": {
    "alg": "HMAC-SHA256",
    "hmac": "base64-encoded-signature",
    "key_id": "CHIT_PROD_PASSPHRASE"
  },
  "meta": {
    "source": "consciousness-service.chr.run.v1",
    "tags": ["chr", "consciousness", "clustering"]
  }
}
```

---

## API Endpoints

### CHR Endpoints

| Endpoint | Method | Purpose | Request | Response |
|----------|--------|---------|---------|----------|
| `/chr/run` | POST | Run CHR algorithm | `CHRRequest` | `CHRResponse` |
| `/chr/from-supabase` | POST | Fetch theories and run CHR | Namespace, limit | `CHRResponse` |
| `/healthz` | GET | Health check | - | `HealthResponse` |
| `/metrics` | GET | Prometheus metrics | - | Metrics object |

### CHRRequest Model

```python
class CHRRequest(BaseModel):
    units: List[TextUnit]          # Text units to cluster
    config: Optional[Dict[str, Any]]  # CHR parameters
    encrypt_anchors: bool = False   # Encrypt constellation anchors
    publish_to_nats: bool = True   # Publish to NATS
```

### TextUnit Model

```python
class TextUnit(BaseModel):
    id: str                        # Unique identifier
    text: str                      # Text content (max 500 chars)
    namespace: str = "pmoves.consciousness"
    metadata: Dict[str, Any] = {}  # Optional metadata
```

---

## CHR Configuration

### Default Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `K` | 8 | Number of constellations |
| `iters` | 30 | Optimization iterations |
| `bins` | 8 | Entropy histogram bins |
| `beta` | 12.0 | Softmax temperature |
| `seed` | 42 | Random seed |

### Quality Metrics

| Metric | Formula | Range |
|--------|---------|-------|
| MHEP | Helmoltz Entropy Profile | 0.0 - 1.0 (higher is better) |
| Hg | Global entropy | 0.0 - ∞ |
| Hs | Slab entropy | 0.0 - ∞ |

---

## Environment Variables

### Required

| Variable | Purpose | Default |
|----------|---------|---------|
| `CHIT_PROD_PASSPHRASE` | CGP signing key | `pmoves-chit-default` (dev only) |
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |
| `SUPABASE_URL` | Supabase API | `http://supabase-kong:8000` |
| `SUPABASE_ANON_KEY` | Supabase auth | - |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `SERVICE_NAME` | Service identifier | `consciousness-service` |
| `SERVICE_PORT` | HTTP port | `8096` |
| `MEILI_API_KEY` | Meilisearch auth | (from MEILI_MASTER_KEY) |

---

## Integration Scripts

### Data Loading

| Script | Purpose | Target |
|--------|---------|--------|
| `load_neo4j_consciousness.sh` | Create Entity nodes | Neo4j |
| `load_supabase_chunks.py` | Load theory chunks | Supabase |
| `ingest_hirag.py` | Index to Hi-RAG | Hi-RAG v2 |

### CGP Utilities

| Script | Purpose | Target |
|--------|---------|--------|
| `create_cgp.py` | Manual CGP generation | Hi-RAG v2 |
| `verify_chr_conch.sh` | Pipeline verification | All services |

---

## Data Flow

### CHR Run Flow

```
1. User Request (POST /chr/run)
   └─> TextUnit[] with theory texts

2. Embedding Generation
   ├─> Try: sentence-transformers (all-MiniLM-L6-v2)
   └─> Fallback: HashingVectorizer (sklearn)

3. CHR Clustering
   ├─> Initialize K anchors (softmax)
   ├─> Iterate: assign points → update anchors
   ├─> Calculate MHEP quality metric
   └─> Generate constellations

4. CGP Construction
   ├─> Format constellations as CGP
   ├─> Sign with CHIT_PROD_PASSPHRASE
   └─> Add metadata

5. NATS Publishing
   ├─> Publish to geometry.cgp.v1
   └─> Publish to tokenism.cgp.ready.v1

6. Response
   └─> Return CHRResult + CGP
```

### Supabase Integration Flow

```
1. POST /chr/from-supabase?namespace=x&limit=y

2. Fetch from Supabase
   └─> GET /rest/v1/pmoves_core.consciousness_theories
       └─> Filter by namespace, limit

3. Transform to TextUnits
   └─> Extract id, text, metadata

4. Run CHR (see above flow)

5. Return results
```

---

## Deployment

### Docker Compose

```yaml
consciousness-service:
  build: ./services/consciousness-service
  ports:
    - "${CONSCIOUSNESS_PORT:-8096}:8096"
  environment:
    - CHIT_PROD_PASSPHRASE=${CHIT_PROD_PASSPHRASE}
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
  depends_on:
    nats-init:
      condition: service_completed_successfully
  profiles:
    - agents
    - botz
```

### Health Check

```bash
curl http://localhost:8096/healthz
```

**Response:**
```json
{
  "status": "healthy",
  "service": "consciousness-service",
  "version": "0.2.0",
  "nats_connected": true,
  "chr_available": true
}
```

---

## Verification

Run the verification script:

```bash
bash pmoves/scripts/verify_chr_conch.sh
```

**Checks:**
1. Environment variables configured
2. Neo4j Entity nodes exist
3. CHR algorithm file structure
4. API endpoints defined
5. Docker Compose configuration
6. Service health (if running)

---

## GEOMETRY BUS Documentation

**NEW:** Comprehensive GEOMETRY BUS ecosystem documentation is now available:

- **[GEOMETRY BUS Overview](geometry-bus/README.md)** - Architecture, service integration map, CGP schema
- **[NATS Subject Catalog](geometry-bus/nats-subjects.md)** - Complete subject taxonomy and payload schemas
- **[Service Integration Guides](geometry-bus/services/)**
  - [Consciousness Service](geometry-bus/services/consciousness-service.md)
  - [Tokenism Simulator](geometry-bus/services/tokenism-simulator.md)
  - [Hyperdimensions](geometry-bus/services/hyperdimensions.md)
  - [EvoController](geometry-bus/services/evo-controller.md)
  - [BoTZ CHIT Skills](geometry-bus/services/botz-skills.md)
- **[Pipeline Documentation](geometry-bus/pipelines/)**
  - [YouTube to Persona](geometry-bus/pipelines/youtube-to-persona.md)
  - [CHR to Shapes](geometry-bus/pipelines/chr-to-shapes.md)

---

## Known Issues

### Resolved (Fixed 2026-03-13)

1. ✅ **Missing imports**: `cgp_mapper.py`, `persona_gate.py` - **FIXED**: Modules exist in service directory
2. ✅ **Timezone import**: `datetime.now(timezone.utc)` - **FIXED**: Added `from datetime import datetime, timezone`
3. ✅ **NATS publish logging**: Silent failures - **FIXED**: Added connection check and error logging
4. ✅ **CGP spec version**: Now uses canonical `chit.cgp.v1.0` from `pmoves/chit/__init__.py`

### Remaining

1. **Port 8096 conflict**: consciousness-service conflicts with cipher-memory
   - **Workaround:** Use `docker compose --profile agents up consciousness-service`
   - **Note:** Services can run simultaneously if properly configured

---

## Future Enhancements

1. **WebSocket support** for real-time CHR results
2. **Batch processing** for large theory sets
3. **Persistent storage** of CHR results in Supabase
4. **Advanced metrics** with Prometheus integration
5. **Integration tests** for NATS publishing
6. **CGP calibration** via EvoController swarm optimization

---

## References

- **GEOMETRY BUS**: [geometry-bus/README.md](geometry-bus/README.md)
- **NATS Catalog**: [geometry-bus/nats-subjects.md](geometry-bus/nats-subjects.md)
- **Service Guides**: [geometry-bus/services/](geometry-bus/services/)
- **Pipelines**: [geometry-bus/pipelines/](geometry-bus/pipelines/)
- **Context Docs**: `.claude/context/geometry-nats-subjects.md`
- **Hi-RAG v2**: `PMOVES-HiRAG/CLAUDE.md`
- **CHIT Module**: `pmoves/chit/__init__.py`
- **CHIT Schema**: `pmoves/contracts/schemas/chit/cgp.v1.schema.json`
- **NATS Context**: `.claude/context/nats-subjects.md`
- **Skill Pairings**: `pmoves/configs/skill-pairings.yaml`
