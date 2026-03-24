# PBnJ | PMOVES + Pinokio

Cluster orchestration bridge for PMOVES.AI — manage local dev, AI Lab (Kubernetes), and KVM4 production deployments from a single control panel.

## Quick Start

1. Select a deployment target from the sidebar:
   - **Local Dev** — Docker Compose on your machine
   - **AI Lab** — Kubernetes cluster for GPU workloads
   - **KVM4 Stack** — Production Kubernetes on KVM4 nodes
2. Click the target to deploy
3. Use **Cluster Status** to verify deployments

## Scripts

### Local Development (Docker Compose)

| Script | Purpose |
|--------|---------|
| `local-up.json` | Start local Docker Compose stack |
| `local-down.json` | Stop local Docker Compose stack |
| `local-logs.json` | Stream logs from local services |

### AI Lab (Kubernetes)

| Script | Purpose |
|--------|---------|
| `lab-up.json` | Apply AI Lab manifests to K8s |
| `lab-down.json` | Delete AI Lab from K8s |

### KVM4 Production (Kubernetes)

| Script | Purpose |
|--------|---------|
| `kvm4-up.json` | Apply KVM4 stack to K8s |
| `kvm4-down.json` | Delete KVM4 stack from K8s |

### VPS Node Deployments (Tailscale SSH)

| Script | Target | Services |
|--------|--------|----------|
| `kvm4-1-deploy.json` | KVM4-1 (API gateway) | TensorZero, Agent Zero, Hi-RAG, Archon, Mesh Agent, Extract Worker |
| `kvm4-2-deploy.json` | KVM4-2 (Data) | Supabase, Qdrant, Neo4j, Meilisearch, NATS, Prometheus, Grafana, Loki, MinIO |
| `kvm2-deploy.json` | KVM2 (Exit) | Nginx reverse proxy |

### Status

| Script | Purpose |
|--------|---------|
| `status.json` | K8s deployment status for AI Lab |
| `vps-status.json` | Tailscale ping + GitHub runner status for all VPS nodes |

## API Reference

### Deploy Script API

All deployment scripts use shell wrappers under `deploy/scripts/`:

**Bash/CLI (deployment scripts)**

```bash
# Local Docker Compose
bash deploy/scripts/deploy-compose.sh up
bash deploy/scripts/deploy-compose.sh down
bash deploy/scripts/deploy-compose.sh logs

# Kubernetes (AI Lab)
bash deploy/scripts/deploy-k8s.sh apply --target ai-lab
bash deploy/scripts/deploy-k8s.sh status --target ai-lab
bash deploy/scripts/deploy-k8s.sh delete --target ai-lab

# Kubernetes (KVM4)
bash deploy/scripts/deploy-k8s.sh apply --target kvm4
bash deploy/scripts/deploy-k8s.sh status --target kvm4
```

**Python**

```python
import subprocess

# Check local stack
result = subprocess.run(
    ["bash", "deploy/scripts/deploy-compose.sh", "status"],
    capture_output=True, text=True, cwd="/path/to/pmoves"
)
print(result.stdout)
```

**JavaScript**

```javascript
const { execSync } = require("child_process");

// Check K8s status
const status = execSync(
  "bash deploy/scripts/deploy-k8s.sh status --target ai-lab",
  { cwd: "/path/to/pmoves", encoding: "utf-8" }
);
console.log(status);
```

### VPS Health Checks (via Tailscale SSH)

```bash
# Ping all nodes
tailscale ping --timeout 3s pmoves-kvm4-1
tailscale ping --timeout 3s pmoves-kvm4-2
tailscale ping --timeout 3s pmoves-kvm2

# Remote health checks
ssh root@pmoves-kvm4-1 'curl -sf http://localhost:8080/healthz'  # Agent Zero
ssh root@pmoves-kvm4-1 'curl -sf http://localhost:3030/healthz'  # TensorZero
ssh root@pmoves-kvm4-2 'curl -sf http://localhost:9090/api/v1/targets'  # Prometheus
ssh root@pmoves-kvm4-2 'curl -sf http://localhost:6333/healthz'  # Qdrant
```

## Agent Hints

AI agents can use this launcher to:

- **Deploy to lab** — Run `lab-up.json` to apply K8s manifests to AI Lab
- **Deploy to production** — Run `kvm4-up.json` or individual node deploy scripts
- **Check cluster status** — Run `status.json` for K8s or `vps-status.json` for VPS fleet
- **View logs** — Run `local-logs.json` for local Docker Compose logs
- **Stop services** — Run `local-down.json`, `lab-down.json`, or `kvm4-down.json`
