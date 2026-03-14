# Consciousness Service Integration Guide

**Service:** consciousness-service
**Port:** 8096
**Status:** Production Ready
**Repository:** `pmoves/services/consciousness-service`

---

## Overview

The consciousness-service implements the CONCH (Consciousness Harvest) pipeline with CHR (Constellation Harvest Regularization) algorithm for geometric clustering of text embeddings into CHIT Geometry Packets (CGP).

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
sequenceDiagram
    autonumber
    participant Client as Client
    participant CHR as consciousness-service
    participant ST as sentence-transformers
    participant NATS as NATS
    participant HIRAG as Hi-RAG v2

    Client->>CHR: POST /chr/run<br/>units[]
    CHR->>ST: Generate embeddings
    ST-->>CHR: vector[384]
    loop CHR Iterations
        CHR->>CHR: Assign points to anchors
        CHR->>CHR: Update anchors
    end
    CHR->>CHR: Calculate MHEP
    CHR->>CHR: Build CGP packet
    CHR->>NATS: Publish geometry.cgp.v1
    CHR->>NATS: Publish tokenism.cgp.ready.v1
    NATS->>HIRAG: Consume CGP
    CHR-->>Client: CHRResult + CGP
```

> **📊 Diagram Source:** [diagrams/chr-algorithm.mmd](../diagrams/chr-algorithm.mmd)

---

## API Endpoints

### Health Check

```bash
GET /healthz
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

### CHR Run

```bash
POST /chr/run
Content-Type: application/json
```

**Request:**
```json
{
  "units": [
    {
      "id": "unit-001",
      "text": "Physicalism is the theory that everything is physical...",
      "namespace": "pmoves.consciousness",
      "metadata": {"category": "materialism"}
    }
  ],
  "config": {
    "K": 8,
    "iters": 30,
    "bins": 8,
    "beta": 12.0,
    "seed": 42
  },
  "encrypt_anchors": false,
  "publish_to_nats": true
}
```

**Response:**
```json
{
  "status": "success",
  "chr_result": {
    "K": 8,
    "MHEP": 0.85,
    "Hg": 2.3,
    "constellations": [...]
  },
  "cgp_packet": {
    "spec": "chit.cgp.v1.0",
    "super_nodes": [...]
  },
  "nats_published": true
}
```

### CHR from Supabase

```bash
POST /chr/from-supabase?namespace=pmoves.consciousness&limit=100
```

**Response:** Same as `/chr/run` with data fetched from Supabase.

### CGP Generate

```bash
POST /cgp/generate
Content-Type: application/json
```

**Request:**
```json
{
  "name": "Materialism",
  "category": "materialism",
  "subcategory": "physicalism",
  "description": "Physicalism is the theory...",
  "proponents": ["David Chalmers", "Daniel Dennett"]
}
```

---

## CHR Algorithm

### Constellation Harvest Regularization

The CHR algorithm performs geometric clustering on text embeddings:

1. **Embedding Generation**
   - Primary: sentence-transformers (all-MiniLM-L6-v2)
   - Fallback: HashingVectorizer (sklearn)

2. **Softmax Clustering**
   - Initialize K anchors with softmax
   - Iterate: assign points → update anchors
   - Temperature parameter (beta) controls softness

3. **Quality Metrics**
   - MHEP: Helmoltz Entropy Profile (0-1, higher is better)
   - Hg: Global entropy
   - Hs: Slab entropy per constellation

4. **CGP Construction**
   - Format constellations as CGP v1.0
   - Sign with CHIT_PROD_PASSPHRASE (if available)
   - Add metadata (namespace, tags)

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `K` | 8 | Number of constellations |
| `iters` | 30 | Optimization iterations |
| `bins` | 8 | Entropy histogram bins |
| `beta` | 12.0 | Softmax temperature (higher = softer) |
| `seed` | 42 | Random seed for reproducibility |

---

## NATS Integration

### Published Subjects

| Subject | When | Payload |
|---------|------|---------|
| `geometry.cgp.v1` | After CHR run | CGP v1.0 packet |
| `tokenism.cgp.ready.v1` | After CHR run | CGP ready signal |

### Connection Configuration

```bash
# Environment variables
NATS_URL=nats://nats:pmoves@nats:4222
NATS_CONNECTED=true  # Health check status
```

### Publish Flow

```python
async def publish_cgp(self, cgp: Dict[str, Any]) -> bool:
    """Publish CGP to NATS geometry bus."""
    if not self.nc or not self.nc.is_connected:
        logger.error("NATS not connected")
        return False

    try:
        await self.nc.publish("geometry.cgp.v1", json.dumps(cgp).encode())
        await self.nc.publish("tokenism.cgp.ready.v1", json.dumps(cgp).encode())
        return True
    except Exception as e:
        logger.error(f"NATS publish failed: {e}")
        return False
```

---

## Database Integration

### Supabase

**Purpose:** Fetch consciousness theories for processing

**Endpoint:**
```bash
GET /rest/v1/pmoves_core.consciousness_theories?namespace=eq.pmoves.consciousness&limit=100
```

**Schema:**
```sql
create table pmoves_core.consciousness_theories (
  id text primary key,
  name text not null,
  category text not null,
  subcategory text,
  description text,
  proponents text[],
  namespace text default 'pmoves.consciousness',
  created_at timestamptz default now()
);
```

### Neo4j

**Purpose:** Store Entity nodes for graph_match integration

**Schema:**
```cypher
CREATE (theory:Entity:Theory {
  id: 'materialism',
  name: 'Materialism',
  category: 'materialism',
  namespace: 'pmoves.consciousness'
})

CREATE (proponent:Entity:Proponent {
  id: 'chalmers',
  name: 'David Chalmers',
  namespace: 'pmoves.consciousness'
})

CREATE (theory)-[:PROPOSED_BY]->(proponent)
```

---

## Environment Variables

### Required

| Variable | Purpose | Default |
|----------|---------|---------|
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |
| `SUPABASE_URL` | Supabase API | `http://supabase-kong:8000` |
| `SUPABASE_ANON_KEY` | Supabase auth | - |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `SERVICE_NAME` | Service identifier | `consciousness-service` |
| `SERVICE_PORT` | HTTP port | `8096` |
| `CHIT_PROD_PASSPHRASE` | CGP signing key | (optional) |
| `MEILI_API_KEY` | Meilisearch auth | (from MEILI_MASTER_KEY) |
| `HIRAG_V2_URL` | Hi-RAG v2 endpoint | `http://hi-rag-gateway-v2:8086` |

### Zeta Filter (Optional)

| Variable | Purpose | Default |
|----------|---------|---------|
| `ZETA_FILTER_ENABLED` | Enable spectral filtering | `true` |
| `ZETA_NUM_ZEROS` | Riemann zeta zeros count | `10` |
| `ZETA_DECAY_FACTOR` | Decay factor for filtering | `0.9` |

---

## Docker Compose

```yaml
consciousness-service:
  build: ./services/consciousness-service
  ports:
    - "${CONSCIOUSNESS_PORT:-8096}:8096"
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
    - CHIT_PROD_PASSPHRASE=${CHIT_PROD_PASSPHRASE}
    - MEILI_API_KEY=${MEILI_MASTER_KEY}
  depends_on:
    nats-init:
      condition: service_completed_successfully
  profiles:
    - agents
    - botz
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8096/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

## Prometheus Metrics

```bash
GET /metrics
```

**Available Metrics:**
```
consciousness_cgp_packets_published_total
consciousness_cgp_publish_errors_total
consciousness_chr_runs_total
consciousness_chr_mhep_bucket
consciousness_nats_connection_status
```

---

## Usage Examples

### Python Client

```python
import httpx
import asyncio

async def run_chr(text_units: list):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8096/chr/run",
            json={"units": text_units, "publish_to_nats": True}
        )
        return response.json()

# Usage
units = [
    {
        "id": "001",
        "text": "Physicalism is the theory...",
        "namespace": "pmoves.consciousness"
    }
]
result = asyncio.run(run_chr(units))
print(f"MHEP: {result['chr_result']['MHEP']}")
```

### cURL

```bash
# Health check
curl http://localhost:8096/healthz

# Run CHR
curl -X POST http://localhost:8096/chr/run \
  -H "Content-Type: application/json" \
  -d '{
    "units": [{"id": "001", "text": "Physicalism is..."}],
    "publish_to_nats": true
  }'

# From Supabase
curl -X POST "http://localhost:8096/chr/from-supabase?namespace=pmoves.consciousness&limit=50"
```

---

## Troubleshooting

### Common Issues

**Issue:** `ImportError: timezone not found`
```
Solution: Fixed in persona_gate.py by importing from datetime:
from datetime import datetime, timezone
```

**Issue:** NATS publish fails silently
```
Solution: Check health endpoint for nats_connected status
Verify NATS_URL includes credentials: nats://nats:pmoves@nats:4222
```

**Issue:** sentence-transformers import error
```
Solution: Service falls back to HashingVectorizer
Check logs for "sentence-transformers unavailable" warning
Install: pip install sentence-transformers
```

### Debug Commands

```bash
# Check service health
curl http://localhost:8096/healthz

# Check NATS connectivity
docker exec consciousness-service nc -zv nats 4222

# View logs
docker logs consciousness-service --tail 100 -f

# Monitor NATS subjects
nats sub "geometry.cgp.v1"
nats sub "tokenism.cgp.ready.v1"
```

---

## References

- **Main Docs:** [README.md](../README.md)
- **NATS Subjects:** [nats-subjects.md](../nats-subjects.md)
- **CONCH Integration:** [../../CONCH_INTEGRATION_MAP.md](../../CONCH_INTEGRATION_MAP.md)
- **CHIT Module:** `pmoves/chit/__init__.py`
