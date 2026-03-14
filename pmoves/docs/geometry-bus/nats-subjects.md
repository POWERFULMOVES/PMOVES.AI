# GEOMETRY BUS NATS Subject Catalog

**Last Updated:** 2026-03-13
**NATS Server:** `nats://nats:pmoves@nats:4222` (authenticated)
**WebSocket Ports:** 9222 (standalone), 9223 (docked)

---

## Subject Taxonomy

```
geometry.>
├── geometry.cgp.v1              # Core CGP publishing
├── geometry.cgp.calibration.v1  # CGP calibration data
├── geometry.event.v1            # Generic geometric events
├── geometry.swarm.meta.v1       # Swarm metadata
├── geometry.packet.encoded.v1   # Encoded CGP packets
└── geometry.*.v1                # Versioned extensions

tokenism.>
├── tokenism.cgp.ready.v1        # CGP ready signal
├── tokenism.cgp.weekly.v1       # Weekly CGP aggregation
├── tokenism.swarm.population.v1 # Swarm population snapshot
├── tokenism.attribution.recorded.v1  # Attribution records
└── tokenism.*.v1                # Versioned extensions

agentgym.>
├── agentgym.train.completed.v1  # RL training completion
└── agentgym.*.v1                # Versioned extensions
```

---

## Core Geometry Subjects

### `geometry.cgp.v1`

**Purpose:** Publish CGP packets to the geometry bus for consumption by Hi-RAG v2, hyperdimensions, BoTZ, and other subscribers.

**Publishers:**
- consciousness-service (8096) - CHR algorithm results
- tokenism-simulator (8103) - Weekly CGP aggregations
- flute-gateway (8055) - Prosodic CGP from voice

**Subscribers:**
- hi-rag-gateway-v2 (8086/8087) - Hybrid RAG indexing
- hyperdimensions - Three.js WebGL rendering (via Portal)
- botz-skills - CHIT tools: encode, tokenism, render

**Payload Schema:** [CGP v1.0](schemas/cgp-v1.0.md)

**Example:**
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
      "points": [...]
    }]
  }],
  "meta": {
    "source": "consciousness-service.chr.run.v1",
    "tags": ["chr", "consciousness", "clustering"]
  }
}
```

---

### `geometry.cgp.calibration.v1`

**Purpose:** Publish CGP calibration data from swarm optimization runs.

**Publishers:**
- evo-controller (8113) - Swarm optimization results

**Subscribers:**
- hi-rag-gateway-v2 (8086) - Calibration for geometric indexing
- tokenism-simulator (8103) - Calibration for economic simulations

**Payload Schema:**
```json
{
  "calibration_id": "calib_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "swarm_generation": 42,
  "fitness_score": 0.95,
  "calibration_params": {
    "anchor_weights": [0.4, 0.3, 0.3],
    "spectrum_bins": 8,
    "entropy_threshold": 0.7
  },
  "meta": {
    "source": "evo-controller.swarm.v1"
  }
}
```

---

### `geometry.event.v1`

**Purpose:** Generic geometric event for tracking and analytics.

**Publishers:**
- All GEOMETRY BUS services

**Subscribers:**
- shape-store - Persistent storage
- analytics - Metrics and monitoring

**Payload Schema:**
```json
{
  "event_type": "cgp_published|cgp_consumed|calibration_applied",
  "timestamp": "2026-03-13T12:00:00Z",
  "source_service": "consciousness-service",
  "cgp_id": "cgp_20260313_120000",
  "metadata": {}
}
```

---

### `geometry.swarm.meta.v1`

**Purpose:** Publish swarm metadata for EVO SWARM coordination.

**Publishers:**
- evo-controller (8113) - Swarm orchestrator

**Subscribers:**
- AgentGym - RL training coordination
- tokenism-simulator (8103) - Economic simulation sync

**Payload Schema:**
```json
{
  "swarm_id": "swarm_20260313_weekly",
  "timestamp": "2026-03-13T12:00:00Z",
  "generation": 42,
  "population_size": 100,
  "fitness_mean": 0.85,
  "fitness_std": 0.12,
  "best_genome": {
    "id": "genome_042",
    "fitness": 0.95,
    "genes": [...]
  },
  "meta": {
    "source": "evo-controller.swarm.v1"
  }
}
```

---

### `geometry.packet.encoded.v1`

**Purpose:** Publish encoded CGP packets (post-CHIT encoding).

**Publishers:**
- BoTZ CHIT tools - `/chit:encode` skill

**Subscribers:**
- All GEOMETRY BUS consumers

**Payload Schema:**
```json
{
  "encoded_packet": "base64-encoded-json",
  "encoding": "chit",
  "original_spec": "chit.cgp.v1.0",
  "timestamp": "2026-03-13T12:00:00Z",
  "meta": {
    "source": "botz.chit.encode.v1"
  }
}
```

---

## Tokenism Subjects

### `tokenism.cgp.ready.v1`

**Purpose:** Signal that a CGP packet is ready for Tokenism processing.

**Publishers:**
- consciousness-service (8096) - After CHR completes

**Subscribers:**
- tokenism-simulator (8103) - Economic simulation trigger
- hi-rag-gateway-v2 (8086) - Indexing trigger

**Payload Schema:**
```json
{
  "cgp_id": "cgp_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "source": "consciousness-service",
  "ready_for": ["tokenism", "hirag"],
  "meta": {}
}
```

---

### `tokenism.cgp.weekly.v1`

**Purpose:** Publish weekly CGP aggregation for economic simulations.

**Publishers:**
- tokenism-simulator (8103) - Weekly aggregation

**Subscribers:**
- hi-rag-gateway-v2 (8086) - Historical indexing
- analytics - Economic metrics

**Payload Schema:**
```json
{
  "week_id": "2026-W11",
  "timestamp": "2026-03-13T12:00:00Z",
  "cgps": [
    {"cgp_id": "cgp_001", "weight": 0.5},
    {"cgp_id": "cgp_002", "weight": 0.3}
  ],
  "aggregation_params": {
    "method": "weighted_average",
    "normalization": "l2"
  },
  "meta": {
    "source": "tokenism-simulator.weekly.v1"
  }
}
```

---

### `tokenism.swarm.population.v1`

**Purpose:** Publish swarm population snapshot for EVO SWARM coordination.

**Publishers:**
- tokenism-simulator (8103) - Population tracking

**Subscribers:**
- evo-controller (8113) - Swarm orchestration input
- AgentGym - RL environment setup

**Payload Schema:**
```json
{
  "population_id": "pop_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "genomes": [
    {
      "id": "genome_001",
      "fitness": 0.85,
      "genes": [0.1, 0.2, 0.3, 0.4],
      "meta": {"generation": 42}
    }
  ],
  "statistics": {
    "mean_fitness": 0.82,
    "std_fitness": 0.08,
    "best_fitness": 0.95
  },
  "meta": {
    "source": "tokenism-simulator.population.v1"
  }
}
```

---

### `tokenism.attribution.recorded.v1`

**Purpose:** Publish attribution records for CHIT geometric attribution.

**Publishers:**
- tokenism-simulator (8103) - Attribution tracking

**Subscribers:**
- analytics - Attribution metrics
- audit - Compliance tracking

**Payload Schema:**
```json
{
  "attribution_id": "attr_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "agent_id": "claude-opus-4-6",
  "cgp_id": "cgp_20260313_120000",
  "contribution_type": "theory_generation|cgp_construction|calibration",
  "contribution_weight": 0.35,
  "geometry_hash": "sha256:abc123...",
  "meta": {
    "source": "tokenism-simulator.attribution.v1"
  }
}
```

---

## AgentGym Subjects

### `agentgym.train.completed.v1`

**Purpose:** Signal RL training completion to EvoController.

**Publishers:**
- AgentGym - RL training orchestrator

**Subscribers:**
- evo-controller (8113) - Calibration trigger

**Payload Schema:**
```json
{
  "training_id": "train_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "agent_id": "agent_001",
  "episode_count": 1000,
  "final_reward": 0.95,
  "converged": true,
  "meta": {
    "source": "agentgym.rl.v1"
  }
}
```

---

## Subject Naming Convention

**Pattern:** `<domain>.<entity>.<action>.<version>`

- **domain:** `geometry`, `tokenism`, `agentgym`
- **entity:** `cgp`, `swarm`, `attribution`, `train`
- **action:** `v1` (default), `calibration`, `ready`, `completed`
- **version:** `v1` (current), `v2` (future)

**Legacy Aliases:**
- `cgp.v1` → `geometry.cgp.v1`
- `geometry.cgp.v1` → `geometry.cgp.v1` (canonical)

---

## JetStream Streams

### GEOMETRY_CGP

```bash
nats stream add GEOMETRY_CGP \
  --subjects "geometry.cgp.>" \
  --storage file \
  --max-age 720h \
  --replication 1
```

### TOKENISM_CGP

```bash
nats stream add TOKENISM_CGP \
  --subjects "tokenism.cgp.>" \
  --storage file \
  --max-age 2160h \
  --replication 1
```

### GEOMETRY_EVENTS

```bash
nats stream add GEOMETRY_EVENTS \
  --subjects "geometry.event.>" \
  --storage file \
  --max-age 168h \
  --replication 1
```

---

## Monitoring Commands

```bash
# Monitor all geometry subjects
nats sub "geometry.>" --raw

# Monitor all tokenism subjects
nats sub "tokenism.>" --raw

# Publish test CGP
nats pub "geometry.cgp.v1" '{"spec":"chit.cgp.v1.0","summary":"test","super_nodes":[],"meta":{}}'

# Check stream info
nats stream info GEOMETRY_CGP
nats stream info TOKENISM_CGP

# List consumers
nats consumer list GEOMETRY_CGP
```

---

## References

- **Main Documentation:** [README.md](README.md)
- **CGP Schema:** [schemas/cgp-v1.0.md](schemas/cgp-v1.0.md)
- **NATS Context:** `.claude/context/nats-subjects.md`
- **Geometry NATS:** `.claude/context/geometry-nats-subjects.md`
