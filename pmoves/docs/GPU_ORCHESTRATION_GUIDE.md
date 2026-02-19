# GPU Orchestration Guide

> **Part of the [PMOVES.AI Integration Layer](INTEGRATIONS_OVERVIEW.md)** | Category: GPU & Hardware

This guide documents GPU resource management in PMOVES.AI: the GPU Orchestrator API, CLI skills, make targets, smoke tests, hardware profiles, and monitoring.

---

## GPU Orchestrator Service

| Field | Value |
|-------|-------|
| **Port** | 8200 (API), 8100 (admin/metrics) |
| **Health** | `GET http://localhost:8200/healthz` |
| **Metrics** | `GET http://localhost:8200/metrics` (Prometheus) |
| **Profile** | `gpu` (Docker Compose) |
| **Image** | `ghcr.io/powerfulmoves/pmoves-gpu-orchestrator:latest` |

**Capabilities:** Priority-based model load queue, session-based lifecycle tracking, automatic idle model unloading, VRAM-aware loading with auto-eviction, NATS event publishing.

---

## API Endpoints

Base URL: `http://localhost:8200/api/gpu`

### Status & Metrics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Full GPU status: VRAM breakdown, running processes, loaded models |
| `/metrics/summary` | GET | Lightweight: VRAM, temperature, utilization |
| `/processes` | GET | GPU processes with memory usage |
| `/healthz` | GET | Health check (503 if GPU unavailable) |
| `/metrics` | GET | Prometheus metrics |

### Model Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/models` | GET | All models (loaded + registry). Filter: `?provider=ollama&include_unloaded=true` |
| `/models/loaded` | GET | Currently loaded models only |
| `/models/load` | POST | Load a model. Body: `{"model_id": "...", "provider": "...", "priority": 5}` |
| `/models/unload/{provider}/{model_id}` | POST | Unload a model. Query: `?force=true` |

### Queue, Sessions & Registry

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/queue` | GET | Load queue status |
| `/sessions` | GET | Active model sessions |
| `/registry` | GET | Full model registry configuration |
| `/optimize` | POST | Auto-optimize: unload idle models |

---

## CLI Skills

### `/gpu:status`

Show GPU metrics and loaded models.

```bash
/gpu:status        # Summary
/gpu:status full   # Detailed with processes
```

**Data sources:** Glancer (port 9105) > nvidia-smi fallback > GPU Orchestrator (port 8200)

### `/gpu:models`

List models and memory requirements.

```bash
/gpu:models all       # Loaded + registry
/gpu:models loaded    # Currently loaded only
/gpu:models registry  # Known models (VRAM requirements)
```

### `/gpu:optimize`

Auto-optimize GPU by unloading idle models.

```bash
/gpu:optimize              # Unload idle models
/gpu:optimize dry-run      # Preview without changes
/gpu:optimize aggressive   # Force unload all except active
```

### `/model:load`

Load a model into GPU.

```bash
/model:load qwen3:8b
/model:load ollama/qwen3:32b --priority high
/model:load tts/kokoro --priority normal
```

### `/model:unload`

Unload a model to free VRAM.

```bash
/model:unload qwen3:8b
/model:unload ollama/qwen3:32b --force
```

---

## Make Targets

| Target | Purpose | Command |
|--------|---------|---------|
| `up-gpu` | Start stack with GPU profile | `make -C pmoves up-gpu` |
| `up-gpu-gateways` | Bring up Hi-RAG v2 & v1 GPU gateways | `make -C pmoves up-gpu-gateways` |
| `up-both-gateways` | Ensure both CPU and GPU gateways up | `make -C pmoves up-both-gateways` |
| `smoke-gpu` | Validate Hi-RAG v2 GPU rerank (strict) | `make -C pmoves smoke-gpu` |
| `smoke-gpu GPU_SMOKE_STRICT=false` | Relaxed GPU smoke test | `make -C pmoves smoke-gpu GPU_SMOKE_STRICT=false` |
| `smoke-qwen-rerank` | Enforce Qwen reranker + strict smoke | `make -C pmoves smoke-qwen-rerank` |
| `gpu-rerank-evidence` | Strict smoke + save evidence to logs | `make -C pmoves gpu-rerank-evidence` |
| `recreate-v2-gpu` | Force-recreate v2-gpu container | `make -C pmoves recreate-v2-gpu` |

---

## Tools

### `smoke_gpu.py`

GPU smoke harness for Hi-RAG v2 rerank validation.

```bash
python -m pmoves.tools.smoke_gpu \
  [--require-qwen] [--stats-only] [--timeout <sec>]
```

| Field | Description |
|-------|-------------|
| **Validates** | GPU gateway health, `/hirag/admin/stats`, rerank query |
| **Strict mode** | `GPU_SMOKE_STRICT=true` (default) --- fails if rerank not used |
| **Port** | 8087 (or `HIRAG_GPU_PORT` / `HIRAG_V2_GPU_HOST_PORT`) |

### `profile_loader.py`

Hardware profile loader for PMOVES mini CLI. Loads YAML profiles from `pmoves/config/profiles/`.

| Field | Description |
|-------|-------------|
| **Functions** | `load_profiles(dir)`, `get_profile(id)`, `save_state(profile)` |
| **State** | `~/.pmoves/profile.json` |

### `runner_lane_map.py`

Map GitHub Actions runner lanes to host assignments with live status queries.

```bash
python -m pmoves.tools.runner_lane_map \
  [--workflows-dir .github/workflows] \
  [--mapping lane_hosts.json] \
  [--repo OWNER/REPO] [--live] [--json]
```

### `local_cert_runners.py`

Manage local-certification GitHub runners via Docker containers.

```bash
python -m pmoves.tools.local_cert_runners \
  [start|stop|status|logs|update] \
  [--lane ai-lab|vps] [--token GHA_TOKEN]
```

---

## Model Registry

Models and VRAM requirements are defined in `pmoves/config/gpu-models.yaml`.

### Ollama Models

| Model | VRAM (MB) | Priority |
|-------|-----------|----------|
| `qwen3:1.7b` | 1536 | 3 |
| `llama3.2:3b` | 2048 | 4 |
| `codellama:7b` | 4096 | 5 |
| `deepseek-coder:6.7b` | 4608 | 5 |
| `qwen3:8b` | 6144 | 5 |
| `qwen3:32b` | 20480 | 7 |
| `nomic-embed-text` | 512 | 3 |

### TTS Models

| Model | VRAM (MB) | Priority |
|-------|-----------|----------|
| `piper` | 512 | 2 |
| `melo-tts` | 1024 | 3 |
| `kitten-tts` | 1536 | 3 |
| `kokoro` | 2048 | 4 |
| `voxcpm` | 2560 | 4 |
| `f5-tts` | 3072 | 4 |

### vLLM Models

| Model | VRAM (MB) | Priority |
|-------|-----------|----------|
| `default` | 16384 | 8 |

---

## Model Lifecycle

### Priority Levels

| Range | Level | Use |
|-------|-------|-----|
| 1--2 | Background | Lowest priority |
| 3--4 | Normal | Background tasks |
| 5 | Standard | Default priority |
| 6--7 | High | Priority tasks |
| 8+ | Critical | Reserved for system |

### Idle Timeout

Models unused for >5 minutes (configurable via `GPU_ORCHESTRATOR_IDLE_TIMEOUT_SECONDS`) are auto-unloaded when VRAM is needed.

### Provider Limitations

| Provider | Dynamic Load | Dynamic Unload |
|----------|-------------|----------------|
| **Ollama** | Yes | Yes |
| **vLLM** | Yes | No (requires container restart) |
| **TTS** | Yes | No (requires container restart) |

---

## Hardware Profiles

| Node | GPU | VRAM | Primary Role |
|------|-----|------|--------------|
| `pmoves-5090` | RTX 5090 | 32 GB | Primary inference (70B+ models) |
| `pmoves-3090ti` | RTX 3090 Ti | 24 GB | Secondary inference, training |
| `pmoves-4090` | RTX 4090 | 16 GB | Mobile inference, dev |
| `pmoves-jetson-1` | Orin | 32/64 GB | Edge inference |
| `pmoves-jetson-2` | Orin | 32/64 GB | Edge inference |

### Model Placement Strategy

| Model Size | Primary Node | Reason |
|-----------|-------------|--------|
| 70B+ | 5090 | 32 GB VRAM required |
| 30--70B | 3090Ti + 5090 | Tensor parallelism |
| 8--30B | Any GPU | Fits in 16 GB+ |
| 1--8B | Jetsons | Edge deployment |
| Embeddings | VPS (CPU) | Low resource |

---

## NATS Events

| Subject | Payload | Frequency |
|---------|---------|-----------|
| `mesh.gpu.status.v1` | Full GPU status (VRAM, utilization, loaded models) | Every 5s |
| `mesh.gpu.model.loaded.v1` | Model loaded event with VRAM consumed | On load |
| `mesh.gpu.model.unloaded.v1` | Model unloaded event | On unload |
| `mesh.gpu.vram.warning.v1` | VRAM threshold warning | When threshold crossed |

---

## Monitoring

### Glancer (System Metrics)

**Port:** 9105

```bash
# GPU status
curl -s http://localhost:9105/api/4/gpu | jq '.'

# Top GPU processes
curl -s "http://localhost:9105/api/4/processlist?sort=gpu_memory" | jq '.[:10]'

# System capabilities
curl http://localhost:9105/api/system
```

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `gpu_vram_total_bytes` | Gauge | Total VRAM |
| `gpu_vram_used_bytes` | Gauge | Used VRAM |
| `gpu_vram_free_bytes` | Gauge | Free VRAM |
| `gpu_utilization_percent` | Gauge | GPU utilization |
| `gpu_temperature_celsius` | Gauge | GPU temperature |
| `gpu_models_loaded` | Gauge | Count of loaded models (by provider) |
| `gpu_model_load_duration_seconds` | Histogram | Model load time |
| `gpu_queue_size` | Gauge | Current queue length |

### Grafana Dashboard

File: `pmoves/monitoring/grafana/dashboards/gpu-orchestrator.json`

Panels: VRAM usage gauge, model load/unload history, queue status, temperature tracking. Refresh: 10s.

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `GPU_ORCHESTRATOR_PORT` | 8200 | Service port |
| `GPU_ORCHESTRATOR_IDLE_TIMEOUT_SECONDS` | 300 | Model idle timeout |
| `GPU_ORCHESTRATOR_VRAM_WARNING_THRESHOLD` | 0.8 | VRAM warning at 80% |
| `GPU_ORCHESTRATOR_VRAM_CRITICAL_THRESHOLD` | 0.95 | VRAM critical at 95% |
| `GPU_ORCHESTRATOR_MAX_MODELS` | 3 | Max concurrent loaded models |
| `GPU_ORCHESTRATOR_STATUS_PUBLISH_INTERVAL` | 5.0 | NATS status publish interval (sec) |
| `OLLAMA_BASE_URL` | `http://pmoves-ollama:11434` | Ollama provider URL |
| `VLLM_BASE_URL` | `http://pmoves-vllm:8000` | vLLM provider URL |
| `TTS_BASE_URL` | `http://ultimate-tts-studio:7861` | TTS provider URL |

---

## Key Files

| File | Purpose |
|------|---------|
| `pmoves/services/gpu-orchestrator/main.py` | FastAPI entry point |
| `pmoves/services/gpu-orchestrator/api/routes.py` | HTTP API endpoints |
| `pmoves/services/gpu-orchestrator/services/vram_tracker.py` | pynvml GPU metrics |
| `pmoves/services/gpu-orchestrator/services/model_lifecycle.py` | Load/unload orchestration |
| `pmoves/services/gpu-orchestrator/services/priority_queue.py` | Priority-based load queue |
| `pmoves/services/gpu-orchestrator/nats/publisher.py` | NATS event publishing |
| `pmoves/config/gpu-models.yaml` | Model registry with VRAM requirements |
| `pmoves/tools/smoke_gpu.py` | GPU smoke test harness |
| `pmoves/tools/profile_loader.py` | Hardware profile detection |
| `.claude/commands/gpu/*.md` | CLI skill definitions |
| `.claude/context/hardware-profiles.md` | Multi-node GPU fleet config |

---

## Related Documentation

- [Integration Layer Overview](INTEGRATIONS_OVERVIEW.md) --- master entry point
- [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md) --- CHIT Python tools
- [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) --- secrets funnel
- [Hardware Profiles](../../.claude/context/hardware-profiles.md) --- fleet configuration
