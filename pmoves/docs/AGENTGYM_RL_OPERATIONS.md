# AgentGym-RL Operations Guide

**Layer:** L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> Operational guide for the AgentGym-RL Coordinator — the reinforcement learning training system that optimizes LLM agents on geometry-aware retrieval tasks within the PMOVES.AI ecosystem.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Service Configuration](#service-configuration)
3. [Training Operations](#training-operations)
4. [Reward Configuration](#reward-configuration)
5. [Progressive Horizon Scaling](#progressive-horizon-scaling)
6. [Model Management](#model-management)
7. [Monitoring](#monitoring)
8. [Database Schema](#database-schema)
9. [Troubleshooting](#troubleshooting)
10. [Cross-References](#cross-references)

---

## Architecture

```
┌──────────────────────────────┐
│  AgentGym-RL Coordinator     │
│       (Port 8114)            │
│                              │
│  Training Job Manager        │
│  Model Checkpoint Manager    │
│  Evaluation Runner           │
└──────────┬───────────────────┘
           │
     ┌─────┼─────────────────┐
     │     │                 │
     ▼     ▼                 ▼
┌─────────┐ ┌─────────────┐ ┌────────────┐
│ PMOVES  │ │ TensorZero  │ │  MinIO     │
│ HiRAG   │ │ Gateway     │ │            │
│ Env     │ │ (LLM)      │ │ Checkpoints│
│ :36000  │ │ :3030      │ │ :9000      │
└─────────┘ └─────────────┘ └────────────┘
```

### Components

| Component | Port | Role |
|-----------|------|------|
| AgentGym-RL Coordinator | 8114 | Training orchestration, job management |
| PMOVES-HiRAG Environment | 36000 | Agent interaction engine, task generation |
| Hi-RAG v2 Gateway | 8086 | Knowledge retrieval backend |
| TensorZero Gateway | 3030 | LLM inference for agent actions |
| MinIO | 9000 | Model checkpoint storage |
| Supabase | 8000 | Trajectory and metadata storage |
| NATS | 4222 | Event coordination |

---

## Service Configuration

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTGYM_ENABLE` | `true` | Master enable switch |
| `AGENTGYM_BASE_MODEL` | `Qwen2.5-7B-Instruct` | Base model for training |
| `AGENTGYM_MODEL_PATH` | `/models` | Model checkpoint directory |

### Training Defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTGYM_DEFAULT_ALGORITHM` | `ppo` | RL algorithm (ppo, grpo) |
| `AGENTGYM_DEFAULT_HORIZON` | `10` | Max interaction steps per episode |
| `AGENTGYM_DEFAULT_EPOCHS` | `25` | Training epochs per run |
| `AGENTGYM_DEFAULT_BATCH_SIZE` | `32` | Batch size for gradient updates |
| `AGENTGYM_DEFAULT_LR` | `1e-6` | Learning rate |
| `AGENTGYM_DEFAULT_KL_COEF` | `0.001` | KL divergence penalty coefficient |

### Environment Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTGYM_ENV_MAX_TURNS` | `15` | Max turns per episode |
| `AGENTGYM_ENV_TIMEOUT` | `600` | Episode timeout (seconds) |
| `AGENTGYM_ENV_NAMESPACE` | `pmoves.consciousness` | Constellation namespace |
| `AGENTGYM_ENV_URL` | `http://agentgym-env-pmoves:36000` | Environment server URL |

### GPU Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTGYM_GPU_MEMORY_UTILIZATION` | `0.7` | GPU memory fraction |
| `AGENTGYM_TENSOR_PARALLEL_SIZE` | `1` | Tensor parallelism degree |
| `USE_CUDA` | `true` | Enable CUDA acceleration |

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 8G
    reservations:
      cpus: '2.0'
      memory: 4G
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

## Training Operations

### Start a Training Run

```bash
curl -X POST http://localhost:8114/agentgym/train/start \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "pmoves-hirag",
    "base_model": "Qwen2.5-7B-Instruct",
    "population_id": "pop-42",
    "training_config": {
      "algorithm": "ppo",
      "num_epochs": 25,
      "horizon": 10,
      "batch_size": 32,
      "learning_rate": 1e-6,
      "kl_coef": 0.001
    },
    "geometry_config": {
      "task_success_weight": 0.4,
      "retrieval_quality_weight": 0.3,
      "cgp_fitness_weight": 0.2,
      "efficiency_weight": 0.1
    }
  }'
```

Response:
```json
{
  "run_id": "run-abc123",
  "status": "started",
  "environment": "pmoves-hirag",
  "estimated_duration_minutes": 45
}
```

### Check Training Status

```bash
curl http://localhost:8114/agentgym/train/run-abc123/status
```

Response:
```json
{
  "run_id": "run-abc123",
  "status": "training",
  "current_epoch": 10,
  "total_epochs": 25,
  "current_horizon": 10,
  "metrics": {
    "avg_reward": 0.72,
    "success_rate": 0.68,
    "avg_episode_length": 8.3,
    "geometry_fitness": 0.81,
    "kl_divergence": 0.003
  },
  "started_at": "2026-03-11T12:00:00Z",
  "elapsed_minutes": 15
}
```

### Stop a Training Run

```bash
curl -X POST http://localhost:8114/agentgym/train/run-abc123/stop
```

### Run Evaluation

```bash
curl -X POST http://localhost:8114/agentgym/eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_checkpoint": "checkpoints/run-abc123/best",
    "environment": "pmoves-hirag",
    "num_episodes": 100
  }'
```

### List Models

```bash
curl http://localhost:8114/agentgym/models/list
```

---

## Reward Configuration

### Multi-Component Reward Function

```
reward = (
    task_success_weight     * task_reward          +
    retrieval_quality_weight * retrieval_quality    +
    cgp_fitness_weight      * geometry_alignment   -
    efficiency_weight       * efficiency_penalty
)
```

### Default Weights

| Weight | Default | Description |
|--------|---------|-------------|
| `AGENTGYM_TASK_SUCCESS_WEIGHT` | 0.4 | Did the agent answer correctly? |
| `AGENTGYM_RETRIEVAL_QUALITY_WEIGHT` | 0.3 | Relevance of retrieved information |
| `AGENTGYM_CGP_FITNESS_WEIGHT` | 0.2 | Geometry coherence of retrieval path |
| `AGENTGYM_EFFICIENCY_WEIGHT` | 0.1 | Penalty for excess steps |

### Reward Components

**Task Success (0 or 1):**
- Binary: did the agent produce a correct answer?
- Evaluated against ground-truth from task generator

**Retrieval Quality (0 to 1):**
- Cosine similarity between retrieved chunks and ideal chunks
- Weighted by constellation membership

**Geometry Alignment (0 to 1):**
- Do retrieved chunks belong to the same constellation?
- Does the retrieval path follow graph edges?
- Are queries constellation-relevant?
- Centrality of retrieved nodes

**Efficiency Penalty (0 to 1):**
- `penalty = steps_taken / max_steps`
- Fewer steps = lower penalty = higher reward

### Tuning Rewards

For **exploration** tasks (finding novel information):
```bash
AGENTGYM_TASK_SUCCESS_WEIGHT=0.2
AGENTGYM_RETRIEVAL_QUALITY_WEIGHT=0.2
AGENTGYM_CGP_FITNESS_WEIGHT=0.5
AGENTGYM_EFFICIENCY_WEIGHT=0.1
```

For **precision** tasks (answering specific questions):
```bash
AGENTGYM_TASK_SUCCESS_WEIGHT=0.6
AGENTGYM_RETRIEVAL_QUALITY_WEIGHT=0.3
AGENTGYM_CGP_FITNESS_WEIGHT=0.05
AGENTGYM_EFFICIENCY_WEIGHT=0.05
```

---

## Progressive Horizon Scaling

Training complexity increases gradually as the agent learns.

### Configuration

```bash
AGENTGYM_HORIZON_SCHEDULE=5,10,15
AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,10,20
```

### Schedule

| Epochs | Horizon | Rationale |
|--------|---------|-----------|
| 0-9 | 5 | Simple tasks, learn basic retrieval |
| 10-19 | 10 | Medium complexity, multi-step reasoning |
| 20+ | 15 | Full complexity, long-chain reasoning |

### Custom Schedules

For faster ramp-up:
```bash
AGENTGYM_HORIZON_SCHEDULE=3,7,10,15
AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,5,10,15
```

For conservative training:
```bash
AGENTGYM_HORIZON_SCHEDULE=5,8,10
AGENTGYM_HORIZON_EPOCH_THRESHOLDS=0,15,25
```

---

## Model Management

### Checkpoints

Model checkpoints are saved to MinIO:

```bash
# List checkpoints
curl http://localhost:8114/agentgym/models/list

# Checkpoint path format
# s3://agentgym-models/run-{run_id}/epoch-{N}/model/
```

### Best Model Selection

Each training run tracks the best-performing checkpoint:

```sql
SELECT run_id, epoch, avg_reward, model_path
FROM agentgym_checkpoints
WHERE is_best = true
ORDER BY avg_reward DESC
LIMIT 5;
```

### Model Deployment

After training, deploy the best model:

```bash
# Copy best checkpoint for serving
mc cp minio/agentgym-models/run-abc123/best/ /models/latest/

# Restart inference service with new model
# (TensorZero picks up models from /models/)
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8114/healthz
# {"ok": true}
```

### Prometheus Metrics

```
# Training metrics
agentgym_training_runs_total{status="completed"}
agentgym_training_duration_seconds{run_id="run-abc123"}
agentgym_current_epoch{run_id="run-abc123"}

# Reward metrics
agentgym_avg_reward{run_id="run-abc123"}
agentgym_success_rate{run_id="run-abc123"}

# Episode metrics
agentgym_episodes_total{run_id="run-abc123"}
agentgym_avg_episode_length{run_id="run-abc123"}
```

### NATS Events

```bash
# Watch all training events
nats sub "agentgym.train.*"

# Watch checkpoint saves
nats sub "agentgym.checkpoint.saved.v1"

# Watch episode completions
nats sub "agentgym.trajectory.completed.v1"
```

### Event Payloads

**Training Started:**
```json
{
  "topic": "agentgym.train.started.v1",
  "source": "evo-controller",
  "payload": {
    "training_run_id": "run-abc123",
    "environment": "pmoves-hirag",
    "trigger_reason": "fitness_plateau",
    "algorithm": "ppo",
    "horizon": 10,
    "num_epochs": 25
  }
}
```

**Training Completed:**
```json
{
  "topic": "agentgym.train.completed.v1",
  "payload": {
    "training_run_id": "run-abc123",
    "final_metrics": {
      "avg_reward": 0.85,
      "success_rate": 0.78,
      "best_epoch": 18
    }
  }
}
```

### Grafana Dashboard

Access at `http://localhost:3000/d/agentgym-rl`:
- Training progress (reward over epochs)
- Episode length distribution
- Geometry alignment over time
- Resource utilization

---

## Database Schema

### Training Runs

```sql
SELECT run_id, environment, algorithm, status,
       current_epoch, total_epochs, metrics
FROM agentgym_training_runs
ORDER BY created_at DESC
LIMIT 10;
```

### Trajectories

```sql
-- Average reward by run
SELECT run_id,
       COUNT(*) as episodes,
       AVG(total_reward) as avg_reward,
       AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate
FROM agentgym_trajectories
GROUP BY run_id
ORDER BY run_id DESC;
```

### Checkpoints

```sql
-- Best checkpoints across all runs
SELECT c.run_id, c.epoch, c.avg_reward, c.model_path,
       r.algorithm, r.status
FROM agentgym_checkpoints c
JOIN agentgym_training_runs r ON c.run_id = r.run_id
WHERE c.is_best = true
ORDER BY c.avg_reward DESC
LIMIT 10;
```

---

## Troubleshooting

### Training Not Starting

```bash
# 1. Check coordinator health
curl http://localhost:8114/healthz

# 2. Check environment server
curl http://localhost:36000/healthz

# 3. Check Hi-RAG v2 (required by environment)
curl http://localhost:8086/healthz

# 4. Check NATS
nats pub test "ping"

# 5. Check logs
docker compose logs agentgym-rl-coordinator --tail 50
```

### Low Reward Scores

```bash
# Check reward weight configuration
docker compose exec agentgym-rl-coordinator env | grep AGENTGYM_.*WEIGHT

# Verify Hi-RAG has indexed content
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}'

# Check task generation mode
docker compose exec agentgym-env-pmoves env | grep TASK_GENERATOR_MODE
```

### GPU Memory Issues

```bash
# Reduce GPU memory utilization
# Set AGENTGYM_GPU_MEMORY_UTILIZATION=0.5

# Reduce batch size
# Set AGENTGYM_DEFAULT_BATCH_SIZE=16

# Check GPU status
nvidia-smi

# Check container GPU allocation
docker inspect agentgym-rl-coordinator | jq '.[0].HostConfig.DeviceRequests'
```

### No Trajectories Recorded

```bash
# Check Supabase tables exist
docker compose exec supabase-db psql -U postgres -d postgres \
  -c "\dt agentgym*"

# Check environment connectivity
curl http://localhost:36000/healthz

# Enable debug logging
# Set LOG_LEVEL=DEBUG and restart
```

### Geometry Rewards Always Zero

```bash
# Verify CGPs exist in Supabase
curl "$SUPA_REST_URL/geometry_cgp_v1?limit=5" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | jq length

# Check constellation namespace matches
docker compose exec agentgym-env-pmoves env | grep NAMESPACE
docker compose exec evo-controller env | grep NAMESPACE

# Both should match (e.g., "pmoves.consciousness" or "default")
```

---

## Cross-References

- [EVOSWARM_OPERATIONS_GUIDE.md](EVOSWARM_OPERATIONS_GUIDE.md) — EvoSwarm controller operations
- [EVOSWARM_PARAMETER_CATALOG.md](EVOSWARM_PARAMETER_CATALOG.md) — Parameter genome reference
- [evoswarm-agentgym-rl-integration.md](architecture/evoswarm-agentgym-rl-integration.md) — Architecture design
- [evoswarm-agentgym-rl-quickstart.md](architecture/evoswarm-agentgym-rl-quickstart.md) — 3-phase roadmap
- [docker-compose.agentgym.yml](../docker-compose.agentgym.yml) — Service definitions

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
