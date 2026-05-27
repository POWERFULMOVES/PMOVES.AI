# Tokenism Simulator Integration Guide

**Service:** tokenism-simulator
**Port:** 8103 host / 8100 container
**Status:** Implemented with scope caveats
**Submodule:** PMOVES-ToKenism-Multi
**Repository:** `PMOVES-ToKenism-Multi/`
**Last reviewed:** 2026-05-22

---

## Overview

Tokenism Simulator implements token economy simulations with CHIT geometric attribution. It processes CGP packets from the GEOMETRY BUS, exposes Flask simulation APIs, publishes compatible NATS events, and tracks fitness metadata. It does not run real mutation/crossover/PSO loops; those operators live in the PMOVES EvoSwarm/model-fitness workstream.

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
    POP["Scenario Population<br/>Initialize participants"]:::swarm
    SIM["Economic Simulation<br/>GroToken, GroupPurchase"]:::econ
    ATTR["Attribution Tracking<br/>Dirichlet-weighted"]:::swarm
    FIT["Fitness Tracking<br/>bounded score + metadata"]:::swarm
    NATS["NATS Publish<br/>simulation + CGP events"]:::output

    START --> POP
    POP --> SIM
    SIM --> ATTR
    ATTR --> FIT
    FIT --> NATS
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
  "status": "ok"
}
```

### Run Simulation

```bash
POST /api/v1/simulate
Content-Type: application/json
```

**Request:**
```json
{
  "scenario": "baseline",
  "parameters": {
    "initial_supply": 1000000,
    "initial_price": 1.0,
    "weeks": 52
  }
}
```

**Response:**
```json
{
  "simulation_id": "sim_20260313_120000",
  "scenario": "baseline",
  "weekly_metrics": [],
  "final_avg_wealth": 1234.56,
  "final_gini": 0.42,
  "final_poverty_rate": 0.15
}
```

### Async Simulation

```bash
POST /api/v1/simulate/async
Content-Type: application/json
```

**Request:**
```json
{
  "scenario": "optimistic",
  "parameters": {
    "weeks": 52
  }
}
```

---

## Economic Simulation

### Fitness Tracking Contract

Tokenism records bounded fitness and economic metrics for downstream optimizers:

1. **Simulation Run**
   - Run baseline, optimistic, pessimistic, or stress-test token economy scenarios.
   - Generate weekly wealth, supply, participation, Gini, and poverty metrics.

2. **CHIT Encoding**
   - Convert simulation results into CGP-compatible geometry records.
   - Publish ready/weekly events when the configured NATS path is enabled.

3. **Fitness Metadata**
   - Record scores in the `0..1` range for comparison and routing.
   - Emit population summaries for consumers that perform external optimization.

4. **Optimizer Handoff**
   - Real PSO/evolutionary operators are expected to consume these events from PMOVES EvoSwarm/model-fitness.
   - Tokenism should not claim selection, crossover, mutation, or RL convergence unless those operators are wired and tested.

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `weeks` | 52 | Number of simulated weeks |
| `scenario` | baseline | Scenario profile: baseline, optimistic, pessimistic, stress_test |
| `initial_supply` | model default | Starting token supply |
| `initial_price` | model default | Starting token price |
| `staking_rate` | model default | Token staking participation |
| `weekly_burn_rate` | model default | Weekly burn percentage |
| `weekly_mint_rate` | model default | Weekly mint percentage |

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
| `geometry.cgp.v1` | `nats_consumer.py` | Extract BPM from canonical CGP and republish prosodic event |

### Published Subjects

| Subject | When | Payload |
|---------|------|---------|
| `tokenism.simulation.result.v1` | Simulation complete | Flask simulator result envelope |
| `tokenism.calibration.result.v1` | Calibration complete | Calibration result envelope |
| `tokenism.cgp.ready.v1` | CGP packet ready | CHIT geometry packet envelope |
| `tokenism.prosodic.bpm.v1` | CGP consumed from `geometry.cgp.v1` | Flattened BPM/prosodic event |

The TypeScript CHIT publisher in the ToKenism submodule separately publishes the hardened `tokenism.attribution.recorded.v1`, `tokenism.cgp.weekly.v1`, `tokenism.cgp.ready.v1`, and `tokenism.swarm.population.v1` contracts.

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
| `TOKENISM_PORT` | Container HTTP port | `8100` |
| `TOKENISM_HOST_PORT` | Host HTTP port in compose | `8103` |
| `TENSORZERO_URL` | TensorZero gateway URL | `http://tensorzero-gateway:3000` |
| `SUPABASE_URL` | Supabase URL | `http://supabase_kong_PMOVES.AI:8000` |

---

## Docker Compose

```yaml
tokenism-simulator:
  build: ./services/tokenism-simulator
  ports:
    - "${TOKENISM_HOST_PORT:-8103}:8100"
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
    - TOKENISM_PORT=${TOKENISM_PORT:-8100}
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
async function runSimulation() {
  // Run simulation via HTTP
  const response = await fetch('http://localhost:8103/api/v1/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario: 'baseline',
      parameters: { weeks: 52 }
    })
  });

  return await response.json();
}

// Usage
const result = await runSimulation();
console.log(`Final Gini: ${result.final_gini}`);
```

### cURL

```bash
# Health check
curl http://localhost:8103/healthz

# Run simulation
curl -X POST http://localhost:8103/api/v1/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "baseline",
    "parameters": {"weeks": 12}
  }'

# Async simulation
curl -X POST http://localhost:8103/api/v1/simulate/async \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "stress_test",
    "parameters": {"weeks": 52}
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

EvoController subscribes to `tokenism.swarm.population.v1` for externally implemented optimization:

```python
# EvoController subscriber
async def subscribe_population():
    await nc.subscribe("tokenism.swarm.population.v1", cb=handle_population)

async def handle_population(msg):
    population = json.loads(msg.data)
    # Update external optimizer state from Tokenism fitness metadata
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

**Issue:** No optimizer convergence is visible
```text
Solution: Tokenism only publishes simulation and fitness metadata.
Check the external EvoSwarm/model-fitness consumer for PSO/evolution execution.
```

**Issue:** Attribution records not published
```text
Solution: Check NATS connectivity and publisher schema validation logs.
The Flask /api/v1/simulate route is not the same API as the TypeScript CHIT publisher.
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
