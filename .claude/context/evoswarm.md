# EvoSwarm - Evolutionary Test-Time Optimization for PMOVES.AI

**EvoSwarm** is PMOVES.AI's evolutionary optimization system for continuously tuning CHIT Geometry parameters using real-world performance feedback. It implements test-time optimization for LLM agents and geometry encoding/decoding pipelines.

## Purpose

Traditional hyperparameter tuning happens at training time. EvoSwarm enables **continuous evolution** of system parameters based on production telemetry:

- **Geometry generation** - Optimize CGP (CHIT Geometry Packet) construction
- **Decoding quality** - Improve text/media reconstruction from geometry
- **Energy efficiency** - Balance quality vs. GPU power consumption
- **Multi-objective optimization** - Pareto-optimal parameter sets

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  EvoSwarm Controller                         │
│                  (Port 8113)                                 │
│  - Polls recent CGPs from Supabase                          │
│  - Evaluates fitness metrics                                │
│  - Evolves parameter genomes                                │
│  - Publishes parameter packs                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
            Publishes to: geometry.swarm.meta.v1 (NATS)
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Geometry Services (Consumers)                   │
│  - PMOVES.YT (video ingestion)                              │
│  - LangExtract (text processing)                            │
│  - Media-Video Analyzer                                     │
│  - Hi-RAG v2 Gateway                                        │
│  All consume parameter packs for CGP building/decoding      │
└─────────────────────────────────────────────────────────────┘
                            ↓
           Emit telemetry → Supabase geometry tables
                            ↓
                  Feedback loop to Controller
```

## Evo Controller Service

**Location:** `pmoves/services/evo-controller/`
**Port:** 8113
**Purpose:** Orchestrate EvoSwarm tuning for CHIT geometry services

### Key Features

- **Continuous polling** - Every 5 minutes (configurable via `EVOSWARM_POLL_SECONDS`)
- **Fitness evaluation** - Analyzes calibration metrics, energy telemetry
- **Parameter evolution** - Genetic algorithm for hyperparameter optimization
- **Publishing** - Distributes evolved parameters via NATS and Supabase

### Environment Configuration

```bash
# Supabase connection
SUPA_REST_URL=http://localhost:3010              # PostgREST endpoint
SUPABASE_SERVICE_ROLE_KEY=your-service-key       # Authentication

# EvoSwarm tunables
EVOSWARM_POLL_SECONDS=300                        # Loop cadence (default 5min)
EVOSWARM_SAMPLE_LIMIT=25                         # CGPs to sample per iteration
EVOSWARM_NAMESPACE=default                       # Optional namespace filter

# Optional GPU energy tracking
NVML_ENABLED=true                                # Enable NVIDIA power monitoring
```

### API Endpoints

**`GET /healthz`**
- Health check for Evo Controller

**`GET /swarm/status`**
- Current swarm status, population info, best fitness

**`POST /swarm/force-evolution`**
- Manually trigger evolution cycle (for testing)

## Genome Definition

EvoSwarm evolves parameters across multiple domains:

### CG Builder Genome (Geometry Construction)

```json
{
  "cg_builder": {
    "K": 128,                    // Embedding dimensions
    "bins": 64,                  // Quantization bins
    "tau": 0.1,                  // Temperature parameter
    "beta": 0.01,                // Regularization weight
    "spectrum_mode": "fft",      // Transform mode: fft|wavelet|hybrid
    "mf_rank": 32                // Matrix factorization rank (optional)
  }
}
```

### Decoder Genome (Geometry → Text/Media)

```json
{
  "decoder": {
    "mode": "swarm",             // Decoding mode: swarm|hrm|direct
    "hrm_halt_thresh": 0.95,     // HRM (Hierarchical Refinement) stop threshold
    "hrm_mmax": 5,               // Max HRM iterations
    "gan_weight": 0.3            // GAN sidecar influence weight
  }
}
```

### Energy Genome (Multi-Objective Optimization)

```json
{
  "energy": {
    "nvml_avg_watts": 250.0,     // Average GPU power consumption
    "duration_ms": 1234,         // Decode duration
    "quality_score": 0.92        // Reconstruction quality
  }
}
```

## Parameter Pack Distribution

Evolved parameters are distributed via two channels:

### 1. NATS Publication

Subject: `geometry.swarm.meta.v1`

```json
{
  "pack_id": "pack-12345",
  "timestamp": "2025-12-06T12:00:00Z",
  "population_id": "pop-67",
  "best_fitness": 0.94,
  "namespace": "default",
  "parameters": {
    "cg_builder": {...},
    "decoder": {...}
  },
  "provenance": {
    "controller_version": "1.0",
    "sample_size": 25,
    "evolution_cycles": 100
  }
}
```

### 2. Supabase Storage

Table: `geometry_parameter_packs`

```sql
CREATE TABLE geometry_parameter_packs (
  pack_id TEXT PRIMARY KEY,
  namespace TEXT DEFAULT 'default',
  status TEXT DEFAULT 'active',  -- active|archived|testing
  parameters JSONB NOT NULL,
  fitness_score NUMERIC,
  created_at TIMESTAMP DEFAULT NOW(),
  provenance JSONB
);
```

Services query for latest active pack:
```sql
SELECT * FROM geometry_parameter_packs
WHERE namespace = $1 AND status = 'active'
ORDER BY created_at DESC
LIMIT 1;
```

## Consumer Pattern

Services consume parameter packs using shared helper:

**Location:** `pmoves/services/common/geometry_params.py`

```python
from services.common.geometry_params import get_latest_pack

# In your service (e.g., PMOVES.YT)
def _build_cgp(content):
    # Fetch latest pack (cached for 10min TTL)
    pack = get_latest_pack(namespace="default")

    if pack:
        # Use evolved parameters
        K = pack["cg_builder"]["K"]
        bins = pack["cg_builder"]["bins"]
        tau = pack["cg_builder"]["tau"]
        # ...
    else:
        # Fallback to static defaults
        K = 128
        bins = 64
        tau = 0.1

    cgp = build_geometry_packet(content, K=K, bins=bins, tau=tau)

    # Persist pack_id for traceability
    cgp["meta"]["pack_id"] = pack["pack_id"] if pack else "default"

    return cgp
```

## Fitness Evaluation

EvoSwarm evaluates parameter packs using multiple metrics:

### Calibration Metrics

From `/geometry/calibration/report` endpoint:
- **Reconstruction accuracy** - How well geometry decodes to original
- **Semantic preservation** - Embedding similarity scores
- **Format compliance** - Valid JSON, no corruption

### Energy Telemetry

From NVML (NVIDIA Management Library):
- **GPU power consumption** - Average watts during decode
- **Decode latency** - Time to reconstruct from geometry
- **Throughput** - CGPs processed per second

### Multi-Objective Fitness

Pareto optimization balancing:
```
fitness = alpha * quality_score - beta * (energy / baseline_energy) - gamma * (latency / baseline_latency)
```

Where:
- `alpha = 1.0` - Quality weight
- `beta = 0.3` - Energy penalty
- `gamma = 0.2` - Latency penalty

## GAN Sidecar Integration

**GAN (Generative Adversarial Network) Sidecar** validates and refines decoded outputs.

**Location:** `pmoves/services/hi-rag-gateway-v2/sidecars/gan_checker.py`

### Purpose

- **Quality gatekeeper** - Rejects low-quality decodes
- **Automatic refinement** - Suggests improvements for marginal outputs
- **Safety enforcement** - Validates content policy compliance

### Usage in Decoding

```python
from sidecars.gan_checker import validate_decode

decoded_text = geometry_to_text(cgp)

critique = validate_decode(
    decoded_text,
    mode="swarm",
    max_edits=1
)

if critique["format_ok"] and critique["safety_score"] > 0.9:
    return decoded_text
elif critique["hint"]:
    # Optional HRM refinement pass
    refined = hrm_refine(decoded_text, hint=critique["hint"])
    return refined
else:
    raise ValueError("Decode quality below threshold")
```

### Critique Schema

```json
{
  "format_ok": true,
  "safety_score": 0.95,
  "hint": "Consider rephrasing for clarity",
  "categories": {
    "coherence": 0.92,
    "factuality": 0.88,
    "safety": 0.95
  }
}
```

### Feature Flag

```bash
GAN_SIDECAR_ENABLED=true  # Enable sidecar validation
```

## Database Schema

### geometry_cgp_v1

Stores CHIT Geometry Packets with telemetry:

```sql
CREATE TABLE geometry_cgp_v1 (
  cgp_id TEXT PRIMARY KEY,
  namespace TEXT DEFAULT 'default',
  content_hash TEXT,
  geometry_data JSONB NOT NULL,
  meta JSONB,  -- Includes pack_id, calibration metrics
  created_at TIMESTAMP DEFAULT NOW()
);
```

### geometry_swarm_runs

Tracks evolution cycles:

```sql
CREATE TABLE geometry_swarm_runs (
  run_id TEXT PRIMARY KEY,
  population_id TEXT,
  generation INT,
  best_fitness NUMERIC,
  average_fitness NUMERIC,
  parameters JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Monitoring EvoSwarm

### Check Controller Status

```bash
curl http://localhost:8113/swarm/status
```

Response:
```json
{
  "status": "evolving",
  "current_generation": 42,
  "population_size": 50,
  "best_fitness": 0.94,
  "last_evolution": "2025-12-06T12:00:00Z",
  "active_packs": 3
}
```

### View Recent Parameter Packs

```sql
SELECT pack_id, namespace, fitness_score, created_at
FROM geometry_parameter_packs
WHERE status = 'active'
ORDER BY created_at DESC
LIMIT 10;
```

### NATS Monitoring

```bash
# Subscribe to parameter pack updates
nats sub "geometry.swarm.meta.v1"

# Monitor CGP telemetry
nats sub "geometry.cgp.calibration.v1"
```

## Development Workflow

### Local Development

```bash
cd pmoves/services/evo-controller
uvicorn app:app --reload --port 8113
```

### Testing Evolution

```bash
# Force evolution cycle
curl -X POST http://localhost:8113/swarm/force-evolution

# Check results
curl http://localhost:8113/swarm/status
```

### Integration Testing

```python
# Test parameter pack consumption
from services.common.geometry_params import get_latest_pack

pack = get_latest_pack(namespace="test")
assert pack is not None
assert "cg_builder" in pack
assert pack["cg_builder"]["K"] > 0
```

## Best Practices

1. **Namespace separation** - Use different namespaces for production vs. testing
2. **Pack versioning** - Always include `pack_id` in CGP metadata
3. **Fallback defaults** - Services must work if no pack available
4. **Telemetry consistency** - All services emit calibration data
5. **Security** - Sign parameter packs when `CHIT_REQUIRE_SIGNATURE=true`

## Future Enhancements

Planned EvoSwarm features:
- **Multi-population evolution** - Separate populations for different modalities
- **Transfer learning** - Share genomes across namespaces
- **A/B testing** - Deploy competing packs to measure real-world impact
- **Distributed evolution** - Multi-host swarm coordination
- **ShapeStore integration** - Evolve shape cache parameters

## References

- EvoSwarm paper: `docs/context/py_and_collabs/evoswarm_evolutionary_test_time_optimization_for_llm_agents.py`
- Integration plan: `docs/notes/chit_evoswarm_gan_plan.md`
- Database schema: `db/v5_13_geometry_swarm.sql`
- Evo Controller: `services/evo-controller/`
- GAN Sidecar: `services/hi-rag-gateway-v2/sidecars/gan_checker.py`

## Developer Notes

**For Claude Code CLI users:**
- EvoSwarm runs automatically in the background
- Parameter packs are consumed transparently by geometry services
- Monitor evolution via `/swarm/status` endpoint
- Use test namespace for development: `namespace="test"`
- Check CGP metadata to see which pack was used
- Telemetry feeds back to controller automatically
