# DGX Spark Ollama Setup Runbook

## Overview
Configure Ollama on the Gigabyte GB10 Grace-Blackwell workstation (DGX Spark) for GPU inference with 128GB unified memory, accessible via Tailscale for PMOVES.AI services.

## Hardware

| Spec | Value |
|------|-------|
| Model | Gigabyte GB10 Grace-Blackwell |
| CPU | NVIDIA Grace (72-core Arm)
| GPU | NVIDIA Blackwell (unknown SM count) |
| Memory | 128GB unified (CPU+GPU shared) |
| Networking | Ethernet + Tailscale VPN |
| Role | GPU inference node for PMOVES.AI |

## Prerequisites

- GB10 workstation powered on and accessible via SSH
- Tailscale installed on the workstation
- Tailscale auth key with `tag:gpu` ACL
- Agent Zero configured with `ollama_spark` provider

## Steps

### 1. Install Tailscale

```bash
# On the GB10 workstation
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey=$TS_AUTHKEY --tag=gpu
```

Verify: `tailscale status` should show `pmoves-dgx-spark` with `tag:gpu`.

### 2. Install Ollama

```bash
# Ollama provides ARM64 binaries for Grace
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

If the install script doesn't support ARM64/Grace:
```bash
# Manual install
download_url=$(curl -s https://api.github.com/repos/ollama/ollama/releases/latest | grep browser_download | grep linux-arm64 | cut -d'"' -f4)
curl -L $download_url -o ollama-linux-arm64.tgz
tar xzf ollama-linux-arm64.tgz
sudo mv ollama /usr/local/bin/
```

### 3. Configure Ollama for Tailscale Access

By default, Ollama binds to `127.0.0.1:11434`. To allow Tailscale access:

```bash
# Set Ollama to listen on Tailscale interface
export OLLAMA_HOST=0.0.0.0:11434

# Or configure via systemd (if installed as service)
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

### 4. Pull Default Model

```bash
# gemma4:31b — default model for PMOVES Spark preset
ollama pull gemma4:31b

# Verify
ollama list
```

Expected output:
```
NAME            ID              SIZE
gemma4:31b      <sha256>        ~20GB
```

### 5. Test Inference

```bash
ollama run gemma4:31b "Hello, respond in one sentence."
```

Expected: Coherent response within a few seconds (Grace-Blackwell is fast).

### 6. Verify Tailscale Connectivity

From another PMOVES node (e.g., Agent Zero server):
```bash
# Test Ollama API via Tailscale
curl http://pmoves-dgx-spark:11434/api/tags

# Should return JSON with model list:
# {"models": [{"name": "gemma4:31b", ...}]}
```

### 7. Configure Agent Zero

The `ollama_spark` provider is already configured in `/a0/conf/model_providers.yaml`:
```yaml
ollama_spark:
  provider: ollama
  base_url: http://pmoves-dgx-spark:11434
```

The PMOVES Spark preset uses this provider. Switch to it in the model selector UI.

### 8. Configure NATS JetStream Streams

The mesh GPU streams are defined in `pmoves/nats/mesh_gpu_streams.yaml`.
Deploy them on the NATS server:

```bash
# From the NATS server or via nats CLI
nats stream add mesh_gpu_inference \
  --subjects "mesh.gpu.inference.>" \
  --retention limits \
  --max-msgs 10000 \
  --max-age 24h
```

## GPU Memory Planning

| Model | Parameters | VRAM Estimate | Fits in 128GB? |
|--------|-----------|---------------|----------------|
| gemma4:31b | 31B | ~20GB | ✅ Plenty |
| gemma4:27b | 27B | ~17GB | ✅ |
| llama3:70b | 70B | ~40GB | ✅ |
| llama3:405b | 405B | ~230GB | ❌ Quantized maybe |
| mixtral:8x22b | 141B | ~90GB | ✅ Tight |

With 128GB unified memory, you can run multiple models simultaneously or one large model comfortably.

## Monitoring

```bash
# Ollama logs
journalctl -u ollama -f

# GPU utilization (if nvidia-smi available)
watch -n1 nvidia-smi

# Tailscale connectivity
watch -n5 tailscale ping pmoves-dgx-spark

# NATS message flow
nats server stats | grep mesh.gpu
```

## Auto-Pull on Boot

Create a systemd service or cron job to ensure models are pulled after reboot:

```bash
# /etc/systemd/system/ollama-models.service
[Unit]
Description=Pull Ollama models
After=ollama.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ollama pull gemma4:31b

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ollama-models.service
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `connection refused` on 11434 | Check OLLAMA_HOST=0.0.0.0:11434 |
| Tailscale can't reach DGX Spark | Check ACL: `tag:pmoves` → `tag:gpu:11434` |
| Model pull fails | Check disk space: `df -h`, models are ~20GB each |
| Slow inference | Check GPU utilization with nvidia-smi |
| ARM64 binary not found | Use manual install method above |

### Required Secrets

| Secret | GitHub Secret Key | Description |
|--------|-------------------|-------------|
| OLLAMA_SPARK_BASE_URL | `OLLAMA_SPARK_BASE_URL` | Ollama endpoint (default: http://pmoves-dgx-spark:11434) |
| DGX_SPARK_SSH_USER | `DGX_SPARK_SSH_USER` | SSH username for GB10 management |
| NATS_SPARK_PASSWORD | `NATS_SPARK_PASSWORD` | NATS leaf node auth (if secured) |

These can be set via: `gh secret set OLLAMA_SPARK_BASE_URL --body 'http://pmoves-dgx-spark:11434'`

## TODO

- [ ] Verify GB10 has Ollama pre-installed
- [ ] Test gemma4:31b inference performance and latency
- [ ] Configure model auto-pull on boot
- [ ] Set up NATS mesh.gpu.* JetStream stream consumers
- [ ] Add GPU utilization metrics to Prometheus
- [ ] Test concurrent inference with multiple requests
- [ ] Configure model warm-up on boot

## References

- Ollama: https://ollama.com/
- Ollama ARM64: https://github.com/ollama/ollama/releases
- TAC Tree: `pmoves/configs/tac_trees/dgx-spark.tac.yaml` (278 lines)
- NATS Streams: `pmoves/nats/mesh_gpu_streams.yaml`
- Agent Zero Provider: `/a0/conf/model_providers.yaml` → `ollama_spark`
- AGNOTE: `pmoves/docs/AGENTS/AGNOTE-dgx-spark.md`

Added: 2026-04-17
