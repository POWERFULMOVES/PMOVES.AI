# Distributed Compute Services

Comprehensive documentation for PMOVES.AI distributed compute orchestration services.

## Overview

The distributed compute services enable **P2P resource discovery** and **dynamic LLM deployment** across a mesh of GPU and CPU nodes. These services allow:

- **Automatic node discovery** - Nodes announce capabilities via NATS
- **Hardware-aware resource allocation** - VRAM/RAM tracking prevents OOM
- **Dynamic parallelism configuration** - vLLM instances configured per available GPUs
- **Work marshaling** - NATS-based task distribution with retry and blacklisting
- **Performance benchmarking** - llama-throughput-lab integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PMOVES.AI Distributed Compute                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Node       │    │   vLLM       │    │   Work       │                  │
│  │  Registry    │◄──►│ Orchestrator │◄──►│ Marshaling   │                  │
│  │   :8115      │    │   :8117      │    │   :8118      │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                   │                          │
│         └───────────────────┴───────────────────┘                          │
│                                 │                                          │
│                                 ▼                                          │
│                     ┌──────────────────┐                                  │
│                     │     NATS         │                                  │
│                     │   :4222          │                                  │
│                     └──────────────────┘                                  │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  Resource    │    │   GPU        │    │  Benchmark   │                  │
│  │  Detector    │    │ Orchestrator │    │   Runner     │                  │
│  │   :8116      │    │   :8098      │    │   :8119      │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Services

### 1. Node Registry [Port 8115]

**Purpose:** P2P node discovery and capability tracking via NATS.

**Features:**
- NATS-based node announcements
- Supabase-backed persistent storage
- REST API for queries
- Health checks for NATS + storage

**API Endpoints:**

```bash
# Health check
GET http://localhost:8115/healthz

# Query for available nodes
POST http://localhost:8115/api/v1/nodes/query
{
  "requires_gpu": true,
  "min_tier": "gpu_peer",
  "online_only": true
}

# Get specific node
GET http://localhost:8115/api/v1/nodes/{node_id}

# Register node (internal)
POST http://localhost:8115/api/v1/nodes/register
```

**Node Tiers:**

| Tier | Description | Example Hardware |
|------|-------------|-------------------|
| `AI_FACTORY` | High-end GPU nodes | H100, RTX 5090 |
| `GPU_PEER` | Mid-range GPU nodes | RTX 4090, 3090 |
| `GPU_INFRA` | Low-end GPU nodes | RTX 4070, 3060 |
| `CPU_ONLY` | CPU-only nodes | High core count, no GPU |

**NATS Subjects:**
- `compute.nodes.announce.v1` - Node announcements (pub by nodes)
- `compute.nodes.query.v1` - Node queries (request-response)
- `compute.nodes.heartbeat.v1` - Heartbeat updates

### 2. vLLM Orchestrator [Port 8117]

**Purpose:** Dynamic vLLM deployment with optimal parallelism configuration.

**Features:**
- Automatic parallelism strategy selection (TP, PP, TP+PP)
- Resource-aware configuration based on available GPUs
- TensorZero integration for model registration
- Docker Compose generation

**API Endpoints:**

```bash
# Deploy vLLM instance
POST http://localhost:8117/api/v1/vllm/deploy
{
  "model_name": "meta-llama/Llama-3-70B",
  "instance_name": "llama-3-70b-main",
  "auto_start": true
}

# Stop instance
DELETE http://localhost:8117/api/v1/vllm/instances/{instance_name}

# List instances
GET http://localhost:8117/api/v1/vllm/instances

# Get instance status
GET http://localhost:8117/api/v1/vllm/instances/{instance_name}
```

**Parallelism Strategies:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `SINGLE_GPU` | One GPU, no parallelism | Models fitting in single GPU VRAM |
| `TENSOR_PARALLEL` | Split across GPUs | Large models, high throughput |
| `PIPELINE_PARALLEL` | Sequential GPU stages | Very large models |
| `HYBRID_TP_PP` | Combined TP + PP | Largest models (70B+) |

### 3. Work Marshaling [Port 8118]

**Purpose:** NATS-based work allocation with retry and blacklisting.

**Features:**
- Work item state machine (pending → assigned → completed/failed)
- Automatic retry with exponential backoff
- Node blacklisting for repeated failures
- Priority queuing

**API Endpoints:**

```bash
# Submit work
POST http://localhost:8118/api/v1/work/submit
{
  "work_type": "inference",
  "model_name": "llama-3-70b",
  "priority": 1,
  "payload": {...}
}

# Get work status
GET http://localhost:8118/api/v1/work/{work_id}

# Cancel work
DELETE http://localhost:8118/api/v1/work/{work_id}

# List active work
GET http://localhost:8118/api/v1/work?status=assigned
```

**NATS Subjects:**
- `compute.work.submit.v1` - Submit work items
- `compute.work.assigned.v1` - Work assigned to node
- `compute.work.completed.v1` - Work completed
- `compute.work.failed.v1` - Work failed

### 4. Resource Detector [Port 8116]

**Purpose:** Hardware detection and tier classification.

**Features:**
- CPU, GPU, RAM detection
- Automatic tier classification
- Platform-specific optimizations

**Detected Resources:**
- **CPU:** Cores, threads, frequency, model
- **GPU:** Name, VRAM, CUDA compute capability
- **RAM:** Total, available, swap
- **Platform:** CUDA, ROCm, CPU-only

### 5. GPU Orchestrator [Port 8098]

**Purpose:** VRAM reservation and system RAM tracking.

**Features:**
- Per-GPU VRAM reservation
- RAM trend analysis with OOM prediction
- Reservation expiration and cleanup

**API Endpoints:**

```bash
# Reserve VRAM
POST http://localhost:8098/api/v1/gpu/reserve
{
  "gpu_indices": [0, 1],
  "required_mb": 24576,
  "timeout_seconds": 300
}

# Release reservation
DELETE http://localhost:8098/api/v1/gpu/reservations/{reservation_id}

# Get GPU states
GET http://localhost:8098/api/v1/gpu/states

# Check if workload fits
POST http://localhost:8098/api/v1/gpu/can-fit
{
  "required_mb": 24576,
  "gpu_count": 2,
  "prefer_nvlink": true
}
```

### 6. Benchmark Runner [Port 8119]

**Purpose:** LLM performance testing via llama-throughput-lab.

**Features:**
- Automated benchmark execution
- Configurable batch sizes and context lengths
- TensorZero metrics publishing
- Background execution support

**API Endpoints:**

```bash
# Run benchmark
POST http://localhost:8119/api/v1/benchmark/run
{
  "model_name": "meta-llama/Llama-3-70B",
  "model_path": "/models/llama-3-70b",
  "gpu_count": 2,
  "batch_sizes": [1, 8, 16],
  "context_lengths": [512, 2048, 4096],
  "background": true
}

# Get benchmark status
GET http://localhost:8119/api/v1/benchmark/{benchmark_id}

# Cancel benchmark
DELETE http://localhost:8119/api/v1/benchmark/{benchmark_id}

# List benchmarks
GET http://localhost:8119/api/v1/benchmarks
```

## Environment Configuration

Add to your `env.shared`:

```bash
# Distributed Compute Services

# Node Registry
NODE_REGISTRY_URL=http://node-registry:8115
NODE_REGISTRY_NATS_URL=nats://nats:4222

# vLLM Orchestrator
VLLM_ORCHESTRATOR_URL=http://vllm-orchestrator:8117
VLLM_MODEL_PATH=/models

# GPU Orchestrator
GPU_ORCHESTRATOR_URL=http://gpu-orchestrator:8098
GPU_RESERVATION_TIMEOUT=300

# Work Marshaling
WORK_MARSHALING_URL=http://work-marshaling:8118
WORK_RETRY_MAX=3
WORK_RETRY_DELAY=5

# Benchmark Runner
BENCHMARK_RUNNER_URL=http://benchmark-runner:8119
BENCHMARK_OUTPUT_DIR=/data/benchmarks

# Standalone mode (connect from external node)
# Use host.docker.internal to reach PMOVES.AI services
NODE_REGISTRY_URL=http://host.docker.internal:8115
VLLM_ORCHESTRATOR_URL=http://host.docker.internal:8117
NATS_URL=nats://host.docker.internal:4222
```

## Standalone Integration

### For Submodules Running Undocked

When a PMOVES submodule runs outside the main docker-compose, it can still access distributed compute services:

```bash
# In your submodule's .env or docker-compose.yml
NODE_REGISTRY_URL=http://host.docker.internal:8115
VLLM_ORCHESTRATOR_URL=http://host.docker.internal:8117
NATS_URL=nats://host.docker.internal:4222

# For Linux, ensure host.docker.internal is defined in docker-compose.yml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### Registering as a Compute Node

To register your submodule as a compute node:

```python
import asyncio
import httpx

async def register_as_compute_node():
    """Register with PMOVES.AI node registry."""

    # Detect local resources
    capabilities = detect_capabilities()  # Your detection logic

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{os.environ['NODE_REGISTRY_URL']}/api/v1/nodes/register",
            json={
                "node_id": "my-submodule-node",
                "hostname": "submodule-host",
                "tier": "GPU_PEER",
                "cpu": {...},
                "memory": {...},
                "gpus": [...],
            }
        )
        return response.json()
```

### Connecting to NATS for Work

To receive work items from the marshaling service:

```python
import nats
import json

async def connect_to_work_marshal():
    nc = await nats.connect(os.environ["NATS_URL"])

    async def on_work(msg):
        work = json.loads(msg.data)
        # Process work
        result = await process_work(work)

        # Publish result
        await nc.publish(
            f"compute.work.completed.v1",
            json.dumps({"work_id": work["work_id"], "result": result}).encode()
        )

    await nc.subscribe("compute.work.assigned.v1", cb=on_work)
```

## Deployment

### Start All Compute Services

```bash
# Using docker compose
cd /home/pmoves/PMOVES.AI
docker compose --profile compute up -d

# Services included:
# - node-registry
# - vllm-orchestrator
# - gpu-orchestrator
# - work-marshaling
# - benchmark-runner
# - resource-detector
```

### Verify Services

```bash
# Check all health endpoints
curl http://localhost:8115/healthz  # Node Registry
curl http://localhost:8117/healthz  # vLLM Orchestrator
curl http://localhost:8098/healthz  # GPU Orchestrator
curl http://localhost:8118/healthz  # Work Marshaling
curl http://localhost:8119/healthz  # Benchmark Runner

# Query available nodes
curl -X POST http://localhost:8115/api/v1/nodes/query \
  -H "Content-Type: application/json" \
  -d '{"requires_gpu": true, "online_only": true}'
```

## Usage Examples

### Deploy a vLLM Instance

```bash
curl -X POST http://localhost:8117/api/v1/vllm/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "meta-llama/Llama-3-70B",
    "instance_name": "llama-3-70b"
  }'
```

### Submit Work for Distributed Execution

```bash
curl -X POST http://localhost:8118/api/v1/work/submit \
  -H "Content-Type: application/json" \
  -d '{
    "work_type": "inference",
    "model_name": "llama-3-70b",
    "priority": 1,
    "payload": {
      "prompt": "Explain quantum computing",
      "max_tokens": 500
    }
  }'
```

### Run Benchmark

```bash
curl -X POST http://localhost:8119/api/v1/benchmark/run \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "meta-llama/Llama-3-70B",
    "model_path": "/models/llama-3-70b",
    "gpu_count": 2,
    "batch_sizes": [1, 8, 16],
    "context_lengths": [512, 2048, 4096],
    "background": true
  }'
```

## Monitoring

### Prometheus Metrics

All services expose metrics at `/metrics`:

```bash
# Node Registry
curl http://localhost:8115/metrics

# GPU Orchestrator
curl http://localhost:8098/metrics

# Work Marshaling
curl http://localhost:8118/metrics
```

### Grafana Dashboards

Access pre-configured dashboards:
- **Distributed Compute Overview:** http://localhost:3000/d/compute-overview
- **GPU Utilization:** http://localhost:3000/d/gpu-utilization
- **Work Queue:** http://localhost:3000/d/work-queue

## Troubleshooting

### Node Not Discoverable

```bash
# Check NATS connection
nats server info

# Verify node announcement
nats sub "compute.nodes.announce.v1"

# Check registry health
curl http://localhost:8115/healthz
```

### vLLM Deployment Failed

```bash
# Check available GPU resources
curl http://localhost:8098/api/v1/gpu/states

# Verify model exists
ls /models/

# Check vLLM orchestrator logs
docker logs vllm-orchestrator
```

### Work Not Processing

```bash
# Check work queue
curl http://localhost:8118/api/v1/work?status=pending

# Verify NATS connectivity
nats pub "compute.work.test.v1" '{"test": true}'

# Check worker node status
curl http://localhost:8115/api/v1/nodes
```

## NATS Subjects Reference

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `compute.nodes.announce.v1` | Pub | Node capability announcements |
| `compute.nodes.query.v1` | Req/Res | Query available nodes |
| `compute.nodes.heartbeat.v1` | Pub | Node heartbeat updates |
| `compute.work.submit.v1` | Pub | Submit work items |
| `compute.work.assigned.v1` | Pub | Work assigned to node |
| `compute.work.completed.v1` | Pub | Work completed |
| `compute.work.failed.v1` | Pub | Work failed |
| `compute.vllm.request.v1` | Req/Res | Request vLLM deployment |

## See Also

- [Distributed Compute Roadmap](./DISTRIBUTED_COMPUTE_ROADMAP.md)
- [Architecture Diagram](../architecture/distributed-compute.md)
- [NATS Subjects Catalog](../../.claude/context/nats-subjects.md)
- [CLAUDE.md - Integration Points](../../.claude/CLAUDE.md)
