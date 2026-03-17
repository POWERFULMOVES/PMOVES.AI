# TAC_GPU_ORCHESTRATOR
_Last updated: 2026-03-15_

## Mission

Coordinate GPU model lifecycle across the multi-host mesh. The GPU Orchestrator tracks VRAM usage, manages model load/unload operations, handles queuing, and publishes status to the NATS bus for consumption by TensorZero, Model Registry, and observability.

## Current State

- **Port:** 8200
- **Health:** `GET http://localhost:8200/healthz`
- **Team:** Infrastructure (agent-teams.yaml)
- **Dependencies:** Ollama (11434), vLLM, NATS (4222), Model Registry
- **Config:** `pmoves/config/gpu-models.yaml` (203 lines, RTX 5090/4090/3090 Ti/Jetson)

## Architecture

```
                GPU Orchestrator (8200)
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
       Ollama        vLLM      NVIDIA SMI
      (:11434)    (models.yml)  (hardware)
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
                   NATS Bus
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    mesh.gpu.     model.registry   Prometheus
    status.v1     .updated.v1      /metrics
```

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `mesh.gpu.status.v1` | Publish (5s) | Periodic GPU status (VRAM, utilization) |
| `mesh.gpu.model.loaded.v1` | Publish | Model successfully loaded |
| `mesh.gpu.model.unloaded.v1` | Publish | Model unloaded |
| `mesh.gpu.command.v1` | Subscribe | Load/unload/optimize commands |
| `mesh.gpu.command.result.v1` | Publish | Command execution result |
| `model.registry.updated.v1` | Publish | Catalog mutation notification |

## GPU Inventory (from `gpu-models.yaml`)

| Hardware | VRAM | CUDA Cores |
|----------|------|-----------|
| RTX 5090 | 32 GB | 21,760 |
| RTX 4090 | 24 GB | 16,384 |
| RTX 3090 Ti | 24 GB | 10,752 |
| Jetson Orin Nano | 8 GB (shared) | 1,024 |

## Thresholds

| Metric | Value |
|--------|-------|
| VRAM warning | 80% |
| VRAM critical | 95% |
| Idle timeout | 300s |
| Max queued | 10 |

## Make Targets

| Target | Description |
|--------|-------------|
| `make up-ollama` | Start Ollama service |
| `make up-gpu-orchestrator` | Start GPU Orchestrator (gpu profile) |
| `make up-vllm` | Start vLLM model servers |
| `make model-pull MODEL=...` | Pull an Ollama model |
| `make gpu-status` | Show VRAM usage and loaded models |

## Production Readiness

| Check | Status |
|-------|--------|
| `/healthz` endpoint | Present |
| NATS integration | Active (6 subjects) |
| Prometheus `/metrics` | Present |
| Docker Compose | Profile: `gpu` |
| Multi-host | Via Mesh Agent + Tailscale |

## Verification

```bash
make -C pmoves gpu-status
curl -s http://localhost:8200/healthz
nats sub "mesh.gpu.>" --count=3
```
