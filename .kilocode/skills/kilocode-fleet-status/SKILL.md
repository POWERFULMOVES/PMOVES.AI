---
name: kilocode-fleet-status
description: Fleet status reporting and GPU mesh coordination for PMOVES.AI on the 5090 node. Use when checking service health, GPU utilization, fleet connectivity, or coordinating model load/unload events.
keywords: [fleet, status, gpu, health, mesh, ollama, nvidia]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode Fleet Status

Comprehensive fleet status reporting from the 5090 GPU node using GLM-5.2 for analysis and summarization.

## Purpose

Gather health, GPU, fleet, and service status into a single sitrep. Emit mesh events for model load/unload. Coordinate with Z890 hub services via Tailscale.

## Capabilities

- 📊 Generate comprehensive sitrep (git, services, GPU, Ollama, fleet, PRs)
- 🖥️ Monitor GPU utilization and memory
- 🌐 Check Tailscale mesh connectivity to fleet nodes
- 📦 Track Ollama model availability
- 📢 Publish `mesh.gpu.status.v1` announcements

## Integration Points

- **NATS Subject (publish)**: `mesh.gpu.status.v1`
- **NATS Subject (subscribe)**: `mesh.gpu.model.loaded.v1`
- **TensorZero Gateway**: `http://localhost:3030/health`
- **Tailscale Mesh**: `${TS_Z890}`, `${TS_5090}`
- **Ollama**: `http://localhost:11434`

## Workflow

### Step 1: Local GPU Check

```bash
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

### Step 2: Service Health

```bash
# Local services
docker ps --format "table {{.Names}}\t{{.Status}}"

# Remote services via Tailscale
curl -sf http://${TS_Z890}:8080/healthz  # Agent Zero
curl -sf http://${TS_Z890}:3030/health   # TensorZero
curl -sf http://${TS_Z890}:8105/health   # Cipher
```

### Step 3: Ollama Models

```bash
ollama list
```

### Step 4: Fleet Status

```bash
make -C pmoves fleet-status
```

### Step 5: Generate Sitrep

Combine all outputs into a structured sitrep with:
- Git status and branch
- Container count and health
- GPU utilization percentage
- Ollama models available
- Fleet node connectivity
- Open PRs (if any)

## Trigger Phrases

- "fleet status"
- "sitrep"
- "check services"
- "GPU status"
- "node health"
