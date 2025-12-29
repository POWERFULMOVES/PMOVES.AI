# PMOVES Hardware Profiles

Hardware fleet configuration for multi-node PMOVES deployment.

## GPU Fleet Overview

| Node | Device | GPU | SM | CUDA | RAM | Role |
|------|--------|-----|-----|------|-----|------|
| `pmoves-5090` | 5090 PC | RTX 5090 | sm_120 | 12.8+ | 32GB VRAM | Primary inference, large models |
| `pmoves-3090ti` | 3090 Ti PC | RTX 3090 Ti | sm_86 | 12.x | 24GB VRAM | Secondary inference, training |
| `pmoves-4090` | 4090 Laptop | RTX 4090 | sm_89 | 12.x | 16GB VRAM | Mobile inference, dev |
| `pmoves-jetson-1` | Jetson Orin | Orin | sm_87 | 12.6/12.8 | 32/64GB | Edge inference |
| `pmoves-jetson-2` | Jetson Orin | Orin | sm_87 | 12.6/12.8 | 32/64GB | Edge inference |

## VPS Fleet

| Node | Type | CPU | RAM | Role |
|------|------|-----|-----|------|
| `pmoves-vps-kvm4-1` | KVM4 | 4 vCPU | 8GB | API gateway, public services |
| `pmoves-vps-kvm4-2` | KVM4 | 4 vCPU | 8GB | Database, storage |
| `pmoves-vps-kvm2` | KVM2 | 2 vCPU | 4GB | Exit node, reverse proxy |

## CUDA Compute Capabilities

```bash
# Full arch list for all GPUs
TORCH_CUDA_ARCH_LIST="8.6;8.7;8.9;9.0;12.0"

# Breakdown:
# sm_86 = RTX 3090 Ti (Ampere)
# sm_87 = Jetson Orin (Ampere)
# sm_89 = RTX 4090 (Ada Lovelace)
# sm_90 = H100/GH200 (Hopper) - future proof
# sm_120 = RTX 5090 (Blackwell)
```

## Base Images by Architecture

### x86_64 (Desktop/Laptop)
```dockerfile
# RTX 5090 (requires CUDA 12.8+)
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

# RTX 3090 Ti / 4090 (CUDA 12.x compatible)
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

# PyTorch with CUDA 12.8
FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime
```

### ARM64 (Jetson Orin)
```dockerfile
# JetPack 6.2.1 (current stable)
FROM nvcr.io/nvidia/l4t-jetpack:r36.4.4

# JetPack 7.0 ready (Ubuntu 24.04 + CUDA 12.8)
FROM dustynv/pytorch:2.8-r36.4-cu128-24.04

# When JetPack 7.0 releases:
# FROM nvcr.io/nvidia/l4t-jetpack:r37.x.x
```

### CPU-only (VPS)
```dockerfile
FROM python:3.11-slim-bookworm
```

## Service Distribution

### GPU-Intensive Services (Local GPUs)
| Service | Primary | Fallback | Notes |
|---------|---------|----------|-------|
| Ultimate-TTS-Studio | 5090 | 4090 | Needs 16GB+ VRAM |
| Whisper Transcription | 3090Ti | Jetsons | Faster-whisper |
| Hi-RAG GPU (reranking) | 4090 | 3090Ti | Cross-encoder |
| Ollama (LLM inference) | 5090 | 3090Ti | Large models |
| vLLM | 5090 | - | 70B+ models |
| ComfyUI | 3090Ti | 4090 | Image generation |

### Edge Services (Jetsons)
| Service | Node | Notes |
|---------|------|-------|
| Local Whisper | jetson-1 | On-device transcription |
| TensorRT inference | jetson-2 | Optimized models |
| ComfyUI | both | TensorRT optimized, --lowvram |
| YOLOv8 (media-video) | both | Object detection |
| Ollama | both | Small models (1-8B) |
| Mesh Agent | both | Node announcement |

### Public Services (VPS)
| Service | Node | Notes |
|---------|------|-------|
| Nginx reverse proxy | kvm2 | Exit node + SSL termination |
| Supabase (PostgREST) | kvm4-2 | Database API |
| Hi-RAG CPU | kvm4-1 | Knowledge retrieval |
| TensorZero Gateway | kvm4-1 | LLM routing |
| Agent Zero API | kvm4-1 | Orchestration |

## Network Topology

```
                    ┌─────────────────┐
                    │   Internet      │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │     pmoves-vps-kvm2         │
              │   (Exit Node / Reverse Proxy)│
              └──────────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────┴────────┐ ┌────────┴────────┐ ┌────────┴────────┐
│ pmoves-vps-kvm4-1│ │ pmoves-vps-kvm4-2│ │   WireGuard     │
│ (API Gateway)   │ │ (Database)      │ │   Tunnel        │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │      Home Network           │
              │      (WireGuard Mesh)       │
              └──────────────┬──────────────┘
                             │
    ┌────────────┬───────────┼───────────┬────────────┐
    │            │           │           │            │
┌───┴───┐   ┌───┴───┐   ┌───┴───┐   ┌───┴───┐   ┌───┴───┐
│ 5090  │   │3090Ti │   │ 4090  │   │Jetson1│   │Jetson2│
│  PC   │   │  PC   │   │Laptop │   │ Orin  │   │ Orin  │
└───────┘   └───────┘   └───────┘   └───────┘   └───────┘
```

## NATS Mesh Configuration

All nodes connect to NATS for coordination:

```yaml
# Each node announces presence
nats pub "mesh.node.announce.v1" '{
  "node_id": "pmoves-5090",
  "capabilities": ["gpu:rtx5090", "vram:32gb", "cuda:12.8"],
  "services": ["ollama", "tts-studio", "vllm"],
  "load": 0.25
}'
```

### Mesh Subjects
```
mesh.node.announce.v1     # Node heartbeat
mesh.node.offline.v1      # Node going offline
mesh.work.available.v1    # Work available for claiming
mesh.work.claimed.v1      # Work claimed by node
mesh.work.completed.v1    # Work completed
mesh.gpu.status.v1        # GPU utilization updates
```

## Environment Variables by Node

### GPU Nodes (5090/3090Ti/4090)
```bash
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
CUDA_VISIBLE_DEVICES=0
TORCH_CUDA_ARCH_LIST="8.6;8.7;8.9;9.0;12.0"
```

### Jetson Nodes
```bash
# JetPack 6.2.1
JETSON_JETPACK_VERSION=6.2.1
L4T_VERSION=36.4.4

# JetPack 7.0 (when released)
# JETSON_JETPACK_VERSION=7.0
# L4T_VERSION=37.x.x
```

### VPS Nodes
```bash
# No GPU
CUDA_VISIBLE_DEVICES=""
TENSORZERO_MODEL_DEFAULT="openai::qwen3:8b"  # Route to home GPU
```

## Glancer Integration

Use Pmoves-Glancer for system provisioning:

```bash
# Query node capabilities
curl http://pmoves-5090:9105/api/system

# Response includes:
# - GPU info (model, VRAM, utilization)
# - CPU/RAM stats
# - Network interfaces
# - Docker status
```

## Deployment Commands

### Start GPU services on 5090
```bash
COMPOSE_PROFILES=gpu,tts docker compose up -d
```

### Start edge services on Jetsons
```bash
docker compose -f docker-compose.arm64.yml up -d
```

### Start public services on VPS
```bash
COMPOSE_PROFILES=api,db docker compose up -d
```

## Model Placement Strategy

| Model Size | Primary Node | Reasoning |
|------------|--------------|-----------|
| 70B+ (Llama 3.1 70B) | 5090 | 32GB VRAM needed |
| 30-70B | 3090Ti + 5090 | Tensor parallelism |
| 8-30B | Any GPU | Fits in 16GB+ |
| 1-8B | Jetsons | Edge inference |
| Embeddings | VPS (CPU) | Low resource |

## References

- [NVIDIA NGC L4T JetPack](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/l4t-jetpack)
- [dusty-nv/jetson-containers](https://github.com/dusty-nv/jetson-containers)
- [PyTorch CUDA 12.8 Docker](https://hub.docker.com/r/pytorch/pytorch)
- [NVIDIA CUDA Docker Hub](https://hub.docker.com/r/nvidia/cuda)
