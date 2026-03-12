# EvoSwarm Operations Guide

**Layer:** L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> Operational guide for deploying, configuring, monitoring, and troubleshooting the EvoSwarm Controller — the evolutionary optimization engine that continuously tunes CGP encoding parameters across the PMOVES.AI platform.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Configuration](#service-configuration)
3. [Startup & Deployment](#startup--deployment)
4. [NATS Subjects](#nats-subjects)
5. [API Endpoints](#api-endpoints)
6. [Evolution Cycle](#evolution-cycle)
7. [Parameter Packs](#parameter-packs)
8. [AgentGym-RL Integration](#agentgym-rl-integration)
9. [Monitoring](#monitoring)
10. [Troubleshooting](#troubleshooting)
11. [Cross-References](#cross-references)

---

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │   EvoSwarm Controller   │
                    │       (Port 8113)       │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │ Evolution Loop    │  │
                    │  │ (every 5 min)     │  │
                    │  └────────┬──────────┘  │
                    │           │              │
                    │  ┌────────▼──────────┐  │
                    │  │ AgentGym Mixin    │  │
                    │  │ (training trigger)│  │
                    │  └──────────────────┘  │
                    └───────┬───────┬────────┘
                            │       │
              ┌─────────────┘       └──────────────┐
              ▼                                    ▼
    ┌─────────────────┐                  ┌────────────────────┐
    │   Supabase DB   │                  │     NATS Bus       │
    │                 │                  │                    │
    │ geometry_cgp_v1 │                  │ geometry.swarm.    │
    │ parameter_packs │                  │   meta.v1          │
    └─────────────────┘                  │ geometry.cgp.      │
                                         │   calibration.v1   │
                                         └────────────────────┘
```

### Role in the Platform

EvoSwarm sits between the encoding pipeline (which produces CGPs) and the consuming services (which use CGPs). It:

1. **Reads** CGP telemetry from Supabase (calibration metrics)
2. **Evaluates** fitness of current parameters
3. **Evolves** parameters using genetic algorithms
4. **Publishes** optimized parameter packs via NATS
5. **Triggers** AgentGym-RL training when fitness plateaus

---

## Service Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPA_REST_URL` | `http://supabase-kong:8000/rest/v1` | Supabase REST endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | (required) | Supabase auth key |
| `EVOSWARM_POLL_SECONDS` | `300` | Evolution cycle interval (seconds) |
| `EVOSWARM_SAMPLE_LIMIT` | `25` | CGPs sampled per iteration |
| `EVOSWARM_NAMESPACE` | `default` | Optional namespace filter |
| `NVML_ENABLED` | `true` | Enable GPU power monitoring |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection string |
| `AGENTGYM_ENABLE` | `true` | Enable RL integration |
| `AGENT_ZERO_BASE_URL` | `http://agent-zero:8080` | Agent Zero for event publishing |

### Docker Compose

```yaml
evo-controller:
  build:
    context: .
    dockerfile: services/evo-controller/Dockerfile
  ports:
    - "${EVOSWARM_PORT:-8113}:8113"
  environment:
    - SUPA_REST_URL=${SUPA_REST_URL:-http://supabase-kong:8000/rest/v1}
    - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
    - EVOSWARM_POLL_SECONDS=${EVOSWARM_POLL_SECONDS:-300}
    - EVOSWARM_SAMPLE_LIMIT=${EVOSWARM_SAMPLE_LIMIT:-25}
    - NATS_URL=${NATS_URL:-nats://nats:pmoves@nats:4222}
  depends_on:
    nats:
      condition: service_healthy
    supabase-db:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8113/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

### Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2 cores |
| Memory | 512MB | 1GB |
| GPU | Not required | Optional (NVML monitoring) |
| Disk | Minimal | 100MB for logs |

---

## Startup & Deployment

### Using Make Targets

```bash
# Start EvoSwarm with dependencies
make -C pmoves up-evo-controller

# Or as part of agent profile
docker compose --profile agents up -d evo-controller

# With AgentGym-RL stack
docker compose -f docker-compose.yml -f docker-compose.agentgym.yml \
  --profile agents --profile agentgym up -d
```

### Startup Sequence

1. Connect to NATS
2. Announce service via `announce_service()` (metadata: version, publishes)
3. Verify Supabase connectivity
4. Start evolution loop (polls every `EVOSWARM_POLL_SECONDS`)
5. Health endpoint becomes available

### Shutdown

1. Stop evolution loop
2. Emit final status to NATS
3. Close NATS connection
4. Exit

---

## NATS Subjects

### Published Subjects

| Subject | Frequency | Payload |
|---------|-----------|---------|
| `geometry.swarm.meta.v1` | Every evolution cycle | Parameter pack with fitness |
| `geometry.cgp.calibration.v1` | On calibration events | Calibration metrics |

### Subscribed Subjects

| Subject | Action |
|---------|--------|
| `tokenism.swarm.population.v1` | Attribution fairness metrics feedback |
| `tokenism.cgp.ready.v1` | New CGP available for evaluation |

### Example: Swarm Meta Publication

```json
{
  "namespace": "default",
  "modality": "text_encoding",
  "pack_id": "pack-12345",
  "status": "active",
  "population_id": "pop-67",
  "generation": 42,
  "best_fitness": 0.94,
  "parameters": {
    "cg_builder": {
      "K": 8,
      "bins": 8,
      "tau": 0.1,
      "beta": 0.01,
      "spectrum_mode": "fft"
    },
    "decoder": {
      "mode": "swarm",
      "hrm_halt_thresh": 0.95,
      "hrm_mmax": 5,
      "gan_weight": 0.3
    }
  },
  "metrics": {
    "gini": 0.38,
    "poverty_rate": 0.12,
    "total_wealth": 125000.0
  },
  "provenance": {
    "controller_version": "0.1.0",
    "sample_size": 25,
    "evolution_cycles": 42
  },
  "timestamp": "2026-03-11T12:00:00Z"
}
```

---

## API Endpoints

### Health

```bash
# Basic health
curl http://localhost:8113/healthz
# {"ok": true}

# Detailed health (includes loop status)
curl http://localhost:8113/health
# {"ok": true, "loop_running": true}
```

### Configuration

```bash
curl http://localhost:8113/config
# {
#   "poll_seconds": 300,
#   "sample_limit": 25,
#   "namespace": "default",
#   "rest_url_configured": true,
#   "agentgym": {
#     "enabled": true,
#     "coordinator_url": "http://agentgym-rl-coordinator:8114"
#   }
# }
```

### Swarm Status

```bash
curl http://localhost:8113/swarm/status
# {
#   "status": "evolving",
#   "current_generation": 42,
#   "population_size": 50,
#   "best_fitness": 0.94,
#   "last_evolution": "2026-03-11T12:00:00Z",
#   "active_packs": 3
# }
```

### Force Evolution

```bash
curl -X POST http://localhost:8113/swarm/force-evolution
# {"status": "evolution_triggered"}
```

---

## Evolution Cycle

### Cycle Steps

```
1. SAMPLE: Fetch latest N CGPs from Supabase
2. EVALUATE: Compute fitness for each CGP
3. SELECT: Tournament selection of best parameter sets
4. CROSSOVER: Combine parameters from top performers
5. MUTATE: Apply random perturbations
6. PUBLISH: Emit new parameter pack to NATS
7. STORE: Save parameter pack to Supabase
8. TRIGGER: Check if AgentGym-RL training needed
```

### Fitness Evaluation

```
fitness = weighted_sum(
  reconstruction_quality,    // KL divergence (lower = better)
  compression_ratio,         // CGP size vs content (higher = better)
  attribution_fairness,      // Gini coefficient (lower = better)
  energy_efficiency          // GPU watts * time (lower = better)
)
```

### Selection & Mutation

| Strategy | Description |
|----------|-------------|
| **Tournament** | Pick best of 3 random candidates |
| **Crossover** | Uniform crossover between two parents |
| **Mutation** | Gaussian noise (sigma = 0.1 * parameter range) |
| **Elitism** | Top 10% survive unchanged |

---

## Parameter Packs

### Structure

See [EVOSWARM_PARAMETER_CATALOG.md](EVOSWARM_PARAMETER_CATALOG.md) for the complete parameter reference.

### Lifecycle

```
Testing → Active → Archived

Testing:  New pack, being evaluated
Active:   Current best, consumed by encoding services
Archived: Superseded by better pack
```

### Supabase Storage

```sql
-- Query active parameter packs
SELECT pack_id, best_fitness, parameters, created_at
FROM geometry_parameter_packs
WHERE status = 'active'
ORDER BY best_fitness DESC
LIMIT 5;
```

---

## AgentGym-RL Integration

When EvoSwarm detects fitness stagnation, it triggers AgentGym-RL training.

### Trigger Conditions

| Condition | Detection | Algorithm Used |
|-----------|-----------|---------------|
| Fitness plateau | Low variance in last N windows | GRPO (exploration) |
| New constellation | Novel CGP constellation IDs | PPO (standard) |
| Scheduled | Every N evolution cycles | PPO (standard) |
| Fitness degradation | Current < old * 0.9 | PPO (standard) |

### Configuration

```bash
AGENTGYM_ENABLE=true
AGENTGYM_TRIGGER_ON_PLATEAU=true
AGENTGYM_PLATEAU_WINDOW=5
AGENTGYM_TRIGGER_ON_NEW_CONSTELLATION=true
AGENTGYM_PERIODIC_TRAINING_INTERVAL=100
```

### Training Launch

```bash
# Manual trigger via EvoSwarm
curl -X POST http://localhost:8113/swarm/force-evolution
# If trigger conditions met, training starts automatically

# Direct training via AgentGym coordinator
curl -X POST http://localhost:8114/agentgym/train/start \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "pmoves-hirag",
    "base_model": "Qwen2.5-7B-Instruct",
    "training_config": {
      "algorithm": "ppo",
      "num_epochs": 25,
      "horizon": 10,
      "batch_size": 32
    }
  }'
```

See [AGENTGYM_RL_OPERATIONS.md](AGENTGYM_RL_OPERATIONS.md) for detailed training operations.

---

## Monitoring

### Prometheus Metrics

EvoSwarm exposes metrics at `/metrics`:

```
# Evolution cycle timing
evoswarm_evolution_duration_seconds{namespace="default"}

# Fitness tracking
evoswarm_best_fitness{namespace="default"}
evoswarm_generation_count{namespace="default"}

# Parameter pack counts
evoswarm_active_packs{namespace="default"}

# AgentGym training triggers
evoswarm_training_triggers_total{reason="fitness_plateau"}
```

### Grafana Dashboard

Default dashboard at `http://localhost:3000/d/evoswarm`:
- Fitness over time
- Evolution cycle duration
- Parameter pack distribution
- AgentGym training events

### Log Aggregation

Logs collected by Promtail and sent to Loki:

```bash
# View recent logs
docker compose logs -f evo-controller --tail 50

# Query Loki
curl -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={service="evo-controller"}' \
  --data-urlencode 'limit=100'
```

### NATS Monitoring

```bash
# Watch evolution events
nats sub "geometry.swarm.meta.v1"

# Watch calibration feedback
nats sub "geometry.cgp.calibration.v1"

# Watch training events
nats sub "agentgym.train.*"
```

---

## Troubleshooting

### Evolution Loop Not Running

```bash
# Check health
curl http://localhost:8113/health
# If loop_running: false, check logs:
docker compose logs evo-controller | tail -50

# Common causes:
# 1. Supabase not reachable
curl http://supabase-kong:8000/rest/v1/ -H "apikey: $SUPABASE_SERVICE_ROLE_KEY"

# 2. NATS not connected
nats pub test "ping" && echo "NATS OK"

# 3. No CGPs to sample
curl "$SUPA_REST_URL/geometry_cgp_v1?limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY"
```

### Fitness Not Improving

```bash
# Check parameter pack history
curl "$SUPA_REST_URL/geometry_parameter_packs?order=created_at.desc&limit=10" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | jq '.[].best_fitness'

# If plateau detected, force evolution with wider mutation
curl -X POST http://localhost:8113/swarm/force-evolution

# Check if AgentGym training is triggering
docker compose logs evo-controller | grep -i agentgym
```

### High Resource Usage

```bash
# Check sample limit (reduce for lower CPU)
curl http://localhost:8113/config | jq .sample_limit

# Increase poll interval
# Set EVOSWARM_POLL_SECONDS=600 and restart

# Check GPU monitoring overhead
# Set NVML_ENABLED=false if not needed
```

### NATS Connection Issues

```bash
# Verify NATS credentials in URL
echo $NATS_URL  # Should contain nats://nats:pmoves@...

# Test connection
nats pub test "ping" --server "$NATS_URL"

# Check NATS server health
curl http://localhost:8222/varz | jq .connections
```

---

## Cross-References

- [AGENTGYM_RL_OPERATIONS.md](AGENTGYM_RL_OPERATIONS.md) — AgentGym-RL training operations
- [EVOSWARM_PARAMETER_CATALOG.md](EVOSWARM_PARAMETER_CATALOG.md) — Complete parameter genome reference
- [.claude/context/evoswarm.md](../.claude/context/evoswarm.md) — Architecture design document
- [evoswarm-agentgym-rl-integration.md](architecture/evoswarm-agentgym-rl-integration.md) — Integration design
- [evoswarm-agentgym-rl-quickstart.md](architecture/evoswarm-agentgym-rl-quickstart.md) — 3-phase roadmap
- [03_EVO_SWARM.md](PMOVESCHIT/03_EVO_SWARM.md) — Protocol specification
- [CALIBRATION_GUIDE.md](PMOVESCHIT/CALIBRATION_GUIDE.md) — CGP calibration procedures

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
