# PMOVES Sidecar

The PMOVES Sidecar is a standalone Agent Zero container that serves as the **deployment interface** for PMOVES.AI on any system. It combines Agent Zero's agentic capabilities with the PMOVES Mini CLI to bootstrap, configure, and manage PMOVES on new devices.

## How It Differs from Compose Mode

| Aspect | Sidecar (Standalone) | Compose (Docked) |
|--------|---------------------|------------------|
| Services | Agent Zero only | Full stack (NATS, TensorZero, Supabase, etc.) |
| LLM | Ollama local or Z.AI cloud | TensorZero routing with fallbacks |
| Networking | host.docker.internal only | Docker compose network mesh |
| CHIT | Dev mode (non-enforcing) | Production mode (signature + anchor) |
| JetStream | Disabled | Enabled via NATS |
| Use case | Deploy on new systems | Production workloads |

## Prerequisites

- Docker installed and running
- (Optional) Ollama for local LLM inference
- (Optional) nvidia-container-toolkit for GPU passthrough
- PMOVES repo cloned on the host

## Quick Start on a New Device

### 1. Clone and prepare
```bash
git clone https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI
```

### 2. Run host prep (auto-detects GPU, Ollama, ports)
```bash
bash scripts/sidecar-host-prep.sh
```

### 3. Start the sidecar
Copy the printed `docker run` command from the prep script output and execute it.

### 4. Verify
```bash
# Check container is running
docker logs PMOVES-Sidecar --tail 20

# Verify Ollama reachability (if Ollama is installed)
docker exec PMOVES-Sidecar curl -s http://host.docker.internal:11434/api/tags

# Verify PMOVES parent config
docker exec PMOVES-Sidecar env | grep PARENT_SYSTEM
```

## Mini CLI Integration

Once the sidecar is running, use Agent Zero's `code_execution_remote` to run Mini CLI commands on the host:

| Command | Purpose |
|---------|---------|
| `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults --service agent-zero` | Bootstrap environment files |
| `python3 -m pmoves.tools.mini_cli profile_detect` | Auto-detect hardware capabilities |
| `python3 -m pmoves.tools.mini_cli profile_apply <id>` | Apply a hardware profile |
| `python3 -m pmoves.tools.mini_cli credentials_fetch` | Pull secrets from GitHub |
| `python3 -m pmoves.tools.mini_cli tailscale_authkey` | Configure Tailscale networking |
| `python3 -m pmoves.tools.mini_cli deps check` | Verify host tooling |

## Agent Profiles

The sidecar ships with 4 agent profiles in `.a0proj/agents.json`:

- **sidecar** (default) — Ollama local inference via `host.docker.internal:11434`
- **tensorzero** — TensorZero routing (requires compose stack)
- **researcher** — GLM-5-turbo via Z.AI for research tasks
- **code-reviewer** — GLM-5-turbo via Z.AI for code review

Switch profiles in Agent Zero Settings → Agent.

## Environment Configuration

Copy the template and customize:
```bash
cp deploy/sidecar/sidecar-env.template ~/agent-zero/PMOVES-Sidecar/sidecar.env
```
See `sidecar-env.template` for documented variables grouped by: topology, CHIT, JetStream, endpoints, Agent Zero, security.

## Standalone → Docked Transition

When the full PMOVES compose stack becomes available on the same host:

1. Edit `sidecar.env`:
   - `TOPOLOGY_MODE=docked`
   - `CHIT_REQUIRE_SIGNATURE=true`
   - `CHIT_DECRYPT_ANCHORS=true`
   - `AGENTZERO_JETSTREAM=true`
2. Switch to the **tensorzero** agent profile in Agent Zero
3. Connect the container to the compose network:
   ```bash
   docker network connect pmoves_app PMOVES-Sidecar
   docker network connect pmoves_bus PMOVES-Sidecar
   ```
4. Restart: `docker restart PMOVES-Sidecar`

## GPU Passthrough

GPU is optional. The host prep script auto-detects nvidia-container-runtime:

- **Detected**: Adds `--gpus all` (or `--runtime=nvidia --gpus all` if not default)
- **Not detected**: Runs CPU-only — works fine with Z.AI cloud providers

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Ollama unreachable from container | Ensure `--add-host host.docker.internal:host-gateway` is set |
| Port 5080 already in use | Change host port mapping: `-p 5081:8080` |
| NATS connection errors in logs | Confirm `AGENTZERO_JETSTREAM=false` in standalone mode |
| No GPU inside container | Verify nvidia-container-toolkit: `docker info | grep nvidia` |
