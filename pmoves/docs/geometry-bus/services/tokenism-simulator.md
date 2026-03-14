# Tokenism Simulator Integration Guide

**Service:** tokenism-simulator
**Port:** 8103
**Status:** Production Ready
**Submodule:** PMOVES-ToKenism-Multi
**Repository:** `PMOVES-ToKenism-Multi/`

---

## Overview

Tokenism Simulator implements economic simulations with CHIT geometric attribution. It processes CGP packets from the GEOMETRY BUS, runs EVO SWARM population simulations, and publishes attribution records.

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
    classDef init fill:#3ecf8e,stroke:#2db380,color:#000
    classDef swarm fill:#9333ea,stroke:#7c2d12,color:#fff
    classDef econ fill:#fbbf24,stroke:#d97706,color:#000
    classDef output fill:#404040,stroke:#525252,color:#ededed

    START["Week Start"]:::init
    POP["Swarm Population<br/>Initialize agents"]:::swarm
    SIM["Economic Simulation<br/>GroToken, GroupPurchase"]:::econ
    ATTR["Attribution Tracking<br/>Dirichlet-weighted"]:::swarm
    OPT["EvoSwarm RL<br/>Optimization"]:::swarm
    NATS["NATS Publish<br/>tokenism.cgp.weekly.v1"]:::output

    START --> POP
    POP --> SIM
    SIM --> ATTR
    ATTR --> OPT
    OPT --> NATS
```

> **📊 Diagram Source:** [diagrams/tokenism-simulation.mmd](../diagrams/tokenism-simulation.mmd)

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
  "service": "tokenism-simulator",
  "version": "1.0.0",
  "nats_connected": true,
  "simulator_ready": true
}
```

### Run Simulation

```bash
POST /simulation/run
Content-Type: application/json
```

**Request:**
```json
{
  "cgps": [
    {"cgp_id": "cgp_001", "weight": 0.5},
    {"cgp_id": "cgp_002", "weight": 0.3}
  ],
  "config": {
    "population_size": 100,
    "generations": 50,
    "mutation_rate": 0.1,
    "crossover_rate": 0.8
  },
  "publish_attribution": true
}
```

**Response:**
```json
{
  "status": "completed",
  "simulation_id": "sim_20260313_120000",
  "generations": 50,
  "final_fitness": 0.92,
  "best_genome": {
    "id": "genome_050",
    "fitness": 0.92,
    "genes": [0.1, 0.2, 0.3, 0.4, 0.5]
  },
  "attribution_published": true
}
```

### Weekly CGP Aggregation

```bash
POST /cgp/weekly
Content-Type: application/json
```

**Request:**
```json
{
  "week_id": "2026-W11",
  "cgps": [...],
  "aggregation_method": "weighted_average"
}
```

---

## Economic Simulation

### EVO SWARM Algorithm

Tokenism implements an evolutionary swarm optimization for economic simulation:

1. **Population Initialization**
   - Generate initial genomes from CGP weights
   - Population size configurable (default: 100)

2. **Fitness Evaluation**
   - Evaluate each genome against economic objectives
   - Fitness: 0-1 scale (higher is better)

3. **Selection**
   - Tournament selection (size: 3)
   - Elitism: top 10% preserved

4. **Crossover & Mutation**
   - Crossover: arithmetic blend
   - Mutation: Gaussian noise

5. **Termination**
   - Max generations (default: 50)
   - Fitness threshold (default: 0.95)

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `population_size` | 100 | Swarm population size |
| `generations` | 50 | Maximum generations |
| `mutation_rate` | 0.1 | Mutation probability |
| `crossover_rate` | 0.8 | Crossover probability |
| `tournament_size` | 3 | Selection tournament size |
| `elitism_pct` | 0.1 | Elite preservation percentage |

---

## CHIT Attribution

### Attribution Record

Tokenism tracks agent contributions using geometric attribution:

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
    "source": "tokenism-simulator.attribution.v1",
    "simulation_id": "sim_20260313_120000"
  }
}
```

### Attribution Types

| Type | Description | Weight Calculation |
|------|-------------|-------------------|
| `theory_generation` | Generated consciousness theory | Text embedding similarity |
| `cgp_construction` | Built CGP packet | Anchor proximity |
| `calibration` | Optimized CGP parameters | Fitness improvement |

---

## NATS Integration

### Subscribed Subjects

| Subject | Handler | Action |
|---------|---------|--------|
| `tokenism.cgp.ready.v1` | `on_cgp_ready` | Queue CGP for processing |
| `geometry.cgp.v1` | `on_cgp_received` | Process CGP directly |

### Published Subjects

| Subject | When | Payload |
|---------|------|---------|
| `tokenism.cgp.weekly.v1` | Weekly aggregation | Weekly CGP packet |
| `tokenism.swarm.population.v1` | Each generation | Population snapshot |
| `tokenism.attribution.recorded.v1` | After attribution | Attribution record |
| `geometry.swarm.meta.v1` | Simulation complete | Swarm metadata |

### Connection Configuration

```typescript
// NATS connection (TypeScript)
const nc = await NATS.connect({
  servers: "nats://nats:pmoves@nats:4222"
});

// Subscribe to CGP ready signal
const sub = nc.subscribe("tokenism.cgp.ready.v1");
for await (const msg of sub) {
  const cgp = JSON.parse(msg.data.toString());
  await processCGP(cgp);
}
```

---

## Environment Variables

### Required

| Variable | Purpose | Default |
|----------|---------|---------|
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `SERVICE_NAME` | Service identifier | `tokenism-simulator` |
| `SERVICE_PORT` | HTTP port | `8103` |
| `POPULATION_SIZE` | Swarm population | `100` |
| `MAX_GENERATIONS` | Simulation limit | `50` |
| `MUTATION_RATE` | Mutation probability | `0.1` |

---

## Docker Compose

```yaml
tokenism-simulator:
  build: ./PMOVES-ToKenism-Multi
  ports:
    - "${TOKENISM_PORT:-8103}:8103"
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
    - POPULATION_SIZE=${TOKENISM_POPULATION:-100}
    - MAX_GENERATIONS=${TOKENISM_GENERATIONS:-50}
  depends_on:
    nats-init:
      condition: service_completed_successfully
  profiles:
    - agents
    - botz
```

---

## Usage Examples

### JavaScript/TypeScript Client

```typescript
import { NATS } from 'nats';

async function runSimulation(cgps: any[]) {
  const nc = await NATS.connect({ servers: "localhost:8103" });

  // Run simulation via HTTP
  const response = await fetch('http://localhost:8103/simulation/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cgps, publish_attribution: true })
  });

  return await response.json();
}

// Usage
const cgps = [
  { cgp_id: 'cgp_001', weight: 0.5 },
  { cgp_id: 'cgp_002', weight: 0.3 }
];
const result = await runSimulation(cgps);
console.log(`Final fitness: ${result.final_fitness}`);
```

### cURL

```bash
# Health check
curl http://localhost:8103/healthz

# Run simulation
curl -X POST http://localhost:8103/simulation/run \
  -H "Content-Type: application/json" \
  -d '{
    "cgps": [{"cgp_id": "cgp_001", "weight": 0.5}],
    "publish_attribution": true
  }'

# Weekly aggregation
curl -X POST http://localhost:8103/cgp/weekly \
  -H "Content-Type: application/json" \
  -d '{
    "week_id": "2026-W11",
    "cgps": [],
    "aggregation_method": "weighted_average"
  }'
```

---

## Integration with Other Services

### Hi-RAG v2

Tokenism publishes `tokenism.cgp.weekly.v1` which Hi-RAG v2 consumes for historical indexing:

```python
# Hi-RAG v2 subscriber
async def subscribe_weekly_cgp():
    await nc.subscribe("tokenism.cgp.weekly.v1", cb=handle_weekly_cgp)

async def handle_weekly_cgp(msg):
    weekly_cgp = json.loads(msg.data)
    # Index to Hi-RAG v2
    await hirag_client.index(weekly_cgp)
```

### EvoController

EvoController subscribes to `tokenism.swarm.population.v1` for swarm optimization:

```python
# EvoController subscriber
async def subscribe_population():
    await nc.subscribe("tokenism.swarm.population.v1", cb=handle_population)

async def handle_population(msg):
    population = json.loads(msg.data)
    # Update swarm optimization
    await update_swarm(population)
```

### AgentGym

AgentGym publishes `agentgym.train.completed.v1` which Tokenism consumes for calibration updates:

```python
# Tokenism subscriber
async def subscribe_training_complete():
    await nc.subscribe("agentgym.train.completed.v1", cb=handle_training)

async def handle_training(msg):
    training = json.loads(msg.data)
    # Update calibration based on RL results
    await update_calibration(training)
```

---

## Troubleshooting

### Common Issues

**Issue:** TypeScript NATS client defaults to unauthenticated
```
Solution: Always provide credentials in connection string:
servers: "nats://nats:pmoves@nats:4222"
```

**Issue:** Swarm population not converging
```
Solution: Check mutation_rate and population_size
Increase generations or adjust fitness function
```

**Issue:** Attribution records not published
```
Solution: Verify publish_attribution=true in request
Check NATS connection status in health endpoint
```

### Debug Commands

```bash
# Check service health
curl http://localhost:8103/healthz

# Monitor NATS subjects
nats sub "tokenism.cgp.weekly.v1"
nats sub "tokenism.swarm.population.v1"
nats sub "tokenism.attribution.recorded.v1"

# View logs
docker logs tokenism-simulator --tail 100 -f
```

---

## References

- **Main Docs:** [README.md](../README.md)
- **NATS Subjects:** [nats-subjects.md](../nats-subjects.md)
- **Submodule:** `PMOVES-ToKenism-Multi/`
- **CHIT Contracts:** `PMOVES-ToKenism-Multi/integrations/contracts/chit/`
