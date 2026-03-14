# EvoController Integration Guide

**Service:** evo-controller
**Port:** 8113
**Status:** Production Ready
**Repository:** `pmoves/services/evo-controller`

---

## Overview

EvoController implements swarm optimization for CGP calibration. It coordinates with AgentGym for RL training, publishes swarm metadata, and optimizes CGP parameters based on fitness feedback.

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
    participant AG as AgentGym
    participant EVO as EvoController
    participant SWARM as EvoSwarm
    participant CHIT as CHIT Module
    participant NATS as NATS

    AG->>NATS: agentgym.train.completed.v1
    NATS->>EVO: Training complete event
    EVO->>SWARM: Fetch population state
    SWARM-->>EVO: PopulationSnapshot
    EVO->>CHIT: Create calibration CGP
    CHIT-->>EVO: calibration_cgp
    EVO->>NATS: geometry.cgp.calibration.v1
    EVO->>NATS: geometry.swarm.meta.v1
```

> **📊 Diagram Source:** [diagrams/evo-calibration.mmd](../diagrams/evo-calibration.mmd)

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
  "service": "evo-controller",
  "version": "1.0.0",
  "nats_connected": true,
  "swarm_ready": true
}
```

### Run Calibration

```bash
POST /calibration/run
Content-Type: application/json
```

**Request:**
```json
{
  "target_cgp_id": "cgp_001",
  "fitness_function": "mhep_optimization",
  "config": {
    "population_size": 50,
    "generations": 30,
    "mutation_rate": 0.15,
    "crossover_rate": 0.75
  }
}
```

**Response:**
```json
{
  "status": "completed",
  "calibration_id": "calib_20260313_120000",
  "best_fitness": 0.95,
  "calibrated_params": {
    "anchor_weights": [0.4, 0.3, 0.3],
    "spectrum_bins": 8,
    "entropy_threshold": 0.7
  },
  "generations": 30
}
```

### Get Swarm Status

```bash
GET /swarm/status
```

**Response:**
```json
{
  "swarm_id": "swarm_20260313_weekly",
  "generation": 42,
  "population_size": 100,
  "fitness_mean": 0.85,
  "fitness_std": 0.12,
  "best_fitness": 0.95,
  "converged": false
}
```

---

## Swarm Optimization Algorithm

### Genetic Algorithm Flow

1. **Initialization**
   - Generate initial population from CGP parameters
   - Random variation around current values

2. **Fitness Evaluation**
   - Apply parameters to CGP generation
   - Evaluate using fitness function (MHEP, entropy, etc.)

3. **Selection**
   - Tournament selection (size: 3)
   - Elitism: top 10% preserved

4. **Crossover**
   - Arithmetic blend for continuous parameters
   - Uniform crossover for discrete parameters

5. **Mutation**
   - Gaussian noise for continuous parameters
   - Random reset for discrete parameters

6. **Termination**
   - Max generations reached
   - Fitness threshold achieved
   - Convergence detected (no improvement for N generations)

### Fitness Functions

| Function | Description | Target |
|----------|-------------|--------|
| `mhep_optimization` | Maximize Helmoltz Entropy Profile | > 0.85 |
| `entropy_balance` | Balance global and slab entropy | Ratio: 0.8-1.2 |
| `anchor_separation` | Maximize inter-anchor distance | Maximize |
| `spectrum_smoothness` | Minimize spectrum variance | < 0.1 |

---

## CGP Calibration

### Calibrated Parameters

EvoController optimizes the following CGP parameters:

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `anchor_weights` | float[3] | [0, 1] | Weight for x, y, z anchors |
| `spectrum_bins` | int | [4, 16] | Number of spectrum bins |
| `entropy_threshold` | float | [0, 1] | Minimum entropy threshold |
| `constellation_count` | int | [2, 16] | Number of constellations |
| `softmax_beta` | float | [1, 20] | Softmax temperature |

### Calibration Output

```json
{
  "calibration_id": "calib_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "swarm_generation": 42,
  "fitness_score": 0.95,
  "calibration_params": {
    "anchor_weights": [0.4, 0.3, 0.3],
    "spectrum_bins": 8,
    "entropy_threshold": 0.7,
    "constellation_count": 8,
    "softmax_beta": 12.0
  },
  "fitness_history": [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95],
  "meta": {
    "source": "evo-controller.swarm.v1",
    "converged": true
  }
}
```

---

## NATS Integration

### Subscribed Subjects

| Subject | Handler | Action |
|---------|---------|--------|
| `agentgym.train.completed.v1` | `on_training_complete` | Trigger calibration |
| `tokenism.swarm.population.v1` | `on_population_update` | Sync swarm state |

### Published Subjects

| Subject | When | Payload |
|---------|------|---------|
| `geometry.swarm.meta.v1` | Each generation | Swarm metadata |
| `geometry.cgp.calibration.v1` | Calibration complete | Calibrated CGP params |
| `mesh.gpu.command.v1` | Model load/unload | GPU commands |

### Connection Configuration

```python
import asyncio
import nats

async def connect_to_nats():
    nc = await nats.connect("nats://nats:pmoves@nats:4222")

    # Subscribe to training completion
    await nc.subscribe("agentgym.train.completed.v1", cb=handle_training)

    # Subscribe to population updates
    await nc.subscribe("tokenism.swarm.population.v1", cb=handle_population)

    return nc
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
| `SERVICE_NAME` | Service identifier | `evo-controller` |
| `SERVICE_PORT` | HTTP port | `8113` |
| `POPULATION_SIZE` | Swarm population | `50` |
| `MAX_GENERATIONS` | Calibration limit | `30` |
| `MUTATION_RATE` | Mutation probability | `0.15` |
| `TARGET_FITNESS` | Convergence threshold | `0.95` |

---

## Docker Compose

```yaml
evo-controller:
  build: ./services/evo-controller
  ports:
    - "${EVO_CONTROLLER_PORT:-8113}:8113"
  environment:
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
    - POPULATION_SIZE=${EVO_POPULATION:-50}
    - MAX_GENERATIONS=${EVO_GENERATIONS:-30}
    - TARGET_FITNESS=${EVO_TARGET_FITNESS:-0.95}
  depends_on:
    nats-init:
      condition: service_completed_successfully
  profiles:
    - agents
    - botz
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8113/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

## Integration with AgentGym

### Training Completion Trigger

AgentGym publishes `agentgym.train.completed.v1` when RL training completes:

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

EvoController responds by running CGP calibration:

```python
async def handle_training_complete(msg):
    training = json.loads(msg.data)

    if training['converged']:
        # Run calibration with converged agent
        result = await run_calibration(
            target_cgp_id=training['agent_id'],
            fitness_function='mhep_optimization'
        )

        # Publish calibration results
        await nc.publish(
            "geometry.cgp.calibration.v1",
            json.dumps(result).encode()
        )
```

---

## Integration with Tokenism

### Population Sync

Tokenism publishes `tokenism.swarm.population.v1` each generation:

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
  }
}
```

EvoController uses this for swarm synchronization:

```python
async def handle_population_update(msg):
    population = json.loads(msg.data)

    # Update internal swarm state
    await sync_swarm_state(population)

    # Publish updated metadata
    await publish_swarm_meta()
```

---

## Usage Examples

### Python Client

```python
import httpx
import asyncio

async def run_calibration(cgp_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8113/calibration/run",
            json={
                "target_cgp_id": cgp_id,
                "fitness_function": "mhep_optimization",
                "config": {
                    "population_size": 50,
                    "generations": 30
                }
            }
        )
        return response.json()

# Usage
result = asyncio.run(run_calibration("cgp_001"))
print(f"Best fitness: {result['best_fitness']}")
print(f"Calibrated params: {result['calibrated_params']}")
```

### cURL

```bash
# Health check
curl http://localhost:8113/healthz

# Run calibration
curl -X POST http://localhost:8113/calibration/run \
  -H "Content-Type: application/json" \
  -d '{
    "target_cgp_id": "cgp_001",
    "fitness_function": "mhep_optimization"
  }'

# Get swarm status
curl http://localhost:8113/swarm/status
```

---

## Troubleshooting

### Common Issues

**Issue:** Calibration not converging
```
Solution: Increase population_size or max_generations
Check fitness function is appropriate for target CGP
```

**Issue:** NATS subscription fails
```
Solution: Verify NATS_URL includes credentials
Check: nats://nats:pmoves@nats:4222
```

**Issue:** Port 8113 conflicts
```
Solution: Use docker compose profiles
docker compose --profile agents up evo-controller
```

### Debug Commands

```bash
# Check service health
curl http://localhost:8113/healthz

# Monitor NATS subjects
nats sub "geometry.swarm.meta.v1"
nats sub "geometry.cgp.calibration.v1"

# View logs
docker logs evo-controller --tail 100 -f

# Check swarm status
curl http://localhost:8113/swarm/status
```

---

## References

- **Main Docs:** [README.md](../README.md)
- **NATS Subjects:** [nats-subjects.md](../nats-subjects.md)
- **AgentGym:** `.claude/context/submodules.md`
- **Tokenism:** [tokenism-simulator.md](tokenism-simulator.md)
