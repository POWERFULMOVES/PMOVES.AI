# PMOVES.AI Deployment Infrastructure

This directory contains the **PBnJ (Pinokio-Based N-tier)** deployment system for PMOVES.AI, enabling one-click orchestration across multiple deployment targets.

## Directory Structure

```
deploy/
├── scripts/          # Deployment automation scripts
│   ├── deploy-k8s.sh       # Kubernetes orchestration
│   └── deploy-compose.sh   # Docker Compose wrapper
├── k8s/              # Kubernetes manifests (Kustomize)
│   ├── base/               # Base manifests
│   ├── ai-lab/             # AI Lab cluster overlay
│   ├── kvm4/               # KVM4 gateway overlay
│   └── local/              # Local dev overlay
├── config/           # Configuration files (future)
└── docs/             # Deployment documentation (future)
```

## Deployment Targets

### 1. AI Lab Cluster (Kubernetes)
Production AI research cluster with GPU support.

```bash
./scripts/deploy-k8s.sh apply --target ai-lab
./scripts/deploy-k8s.sh status --target ai-lab
./scripts/deploy-k8s.sh delete --target ai-lab
```

**Configuration:**
- **Image**: `ghcr.io/powerfulmoves/pmoves-core:v1.0.0-lab-hardened`
- **Replicas**: 5
- **Hostname**: `pmoves.lab.local`
- **Context**: `ai-lab` (env: `PMOVES_K8S_CONTEXT_AI_LAB`)
- **Namespace**: `pmoves` (env: `PMOVES_K8S_NS_AI_LAB`)

### 2. KVM4 Gateway (Kubernetes)
Edge gateway for external access and load balancing.

```bash
./scripts/deploy-k8s.sh apply --target kvm4
./scripts/deploy-k8s.sh status --target kvm4
```

**Configuration:**
- **Image**: `ghcr.io/powerfulmoves/pmoves-core:v1.0.0-kvm4-hardened`
- **Replicas**: 2
- **Hostname**: `pmoves.kvm4.yourdomain.tld`
- **Context**: `kvm4` (env: `PMOVES_K8S_CONTEXT_KVM4`)
- **Namespace**: `pmoves` (env: `PMOVES_K8S_NS_KVM4`)

### 3. Local Development (Docker Compose)
Local development environment using Docker Compose.

```bash
./scripts/deploy-compose.sh up
./scripts/deploy-compose.sh logs
./scripts/deploy-compose.sh down
```

**Configuration:**
- **Compose File**: `../pmoves/docker-compose.yml` (env: `PMOVES_COMPOSE_FILE`)
- **Project**: `pmoves_local` (env: `PMOVES_COMPOSE_PROJECT`)

## Kubernetes Manifests (Kustomize)

### Base Manifests (`k8s/base/`)
- `namespace.yaml` - PMOVES namespace definition
- `pmoves-core-deployment.yaml` - Core service deployment (3 replicas)
- `pmoves-core-service.yaml` - ClusterIP service
- `ingress.yaml` - Nginx ingress controller configuration
- `kustomization.yaml` - Kustomize resources list

### Overlays
Each overlay extends the base manifests with environment-specific configuration:

- **ai-lab**: Production hardened, 5 replicas
- **kvm4**: Gateway optimized, 2 replicas
- **local**: Development build, dev-local tag

## Environment Variables

### Kubernetes Deployment
```bash
# AI Lab
export PMOVES_K8S_CONTEXT_AI_LAB=ai-lab
export PMOVES_K8S_NS_AI_LAB=pmoves

# KVM4
export PMOVES_K8S_CONTEXT_KVM4=kvm4
export PMOVES_K8S_NS_KVM4=pmoves

# Local (kind/k3d)
export PMOVES_K8S_CONTEXT_LOCAL=kind-pmoves
export PMOVES_K8S_NS_LOCAL=pmoves-dev
```

### Docker Compose
```bash
export PMOVES_COMPOSE_FILE=/path/to/docker-compose.yml
export PMOVES_COMPOSE_PROJECT=pmoves_local
```

## Pinokio Integration

This deployment infrastructure integrates with the **PBnJ Pinokio application** located at `/pbnj/pinokio/api/pmoves-pbnj/`.

The Pinokio app provides a graphical interface for:
- Starting/stopping AI Lab cluster
- Starting/stopping KVM4 gateway
- Managing local Docker Compose stack
- Checking cluster status

See `/pbnj/README.md` for Pinokio installation and usage.

## Prerequisites

### For Kubernetes Deployments
- **kubectl 1.14+** with built-in Kustomize support
  ```bash
  # Verify installation
  kubectl version --client
  kubectl kustomize --help
  ```
- **Valid kubeconfig** with cluster access
  ```bash
  # List available contexts
  kubectl config get-contexts

  # Test cluster connectivity
  kubectl cluster-info
  ```
- **Namespace permissions** for target cluster (create, read, update, delete)
- **Nginx Ingress Controller** installed in cluster
  ```bash
  # Verify ingress controller
  kubectl get ingressclass
  # Expected output should include 'nginx'
  ```
- **Environment variables configured** (see `.envrc.example`)

### For Docker Compose
- **Docker Engine 20.10+** or Docker Desktop
  ```bash
  # Verify installation
  docker version
  docker compose version  # Note: v2 uses 'compose' not 'compose'
  ```
- **8GB+ RAM recommended** for full stack (all 29 services)
- **docker-compose v2** or `docker compose` plugin
  ```bash
  # If using standalone docker-compose v1:
  sudo apt-get install docker-compose-plugin  # Upgrade to v2
  ```

## Usage Examples

### Deploy to AI Lab with Custom Context
```bash
./scripts/deploy-k8s.sh apply \
  --target ai-lab \
  --context my-cluster \
  --namespace pmoves-prod \
  --kubeconfig ~/.kube/lab-config
```

### Check Status Across All Targets
```bash
for target in ai-lab kvm4 local; do
  echo "=== $target ==="
  ./scripts/deploy-k8s.sh status --target $target
done
```

### Local Development Workflow
```bash
# Start local stack
./scripts/deploy-compose.sh up

# Watch logs
./scripts/deploy-compose.sh logs

# Make changes, restart services
cd ../pmoves && docker compose restart agent-zero

# Tear down
./scripts/deploy-compose.sh down
```

## Customization

### Adding a New Kubernetes Overlay
1. Create directory: `k8s/my-overlay/`
2. Create `kustomization.yaml`:
   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
     - ../base
   images:
     - name: ghcr.io/powerfulmoves/pmoves-core
       newTag: "my-version"
   ```
3. Update `deploy-k8s.sh` to recognize new target

### Modifying Base Manifests
Edit files in `k8s/base/` and changes will propagate to all overlays via Kustomize.

## Security Considerations

- **Secrets Management**: Store secrets in Kubernetes Secrets or Docker secrets, not in manifests
- **Image Tags**: Use specific version tags, not `latest`
- **RBAC**: Ensure service accounts have minimal required permissions
- **Network Policies**: Configure NetworkPolicies for inter-service communication
- **TLS**: Configure cert-manager for automatic certificate management

See `/docs/Security-Hardening-Roadmap.md` for comprehensive security guidelines.

## Troubleshooting

### Kubernetes Deployment Fails
```bash
# Validate manifests
kubectl kustomize k8s/ai-lab

# Check for syntax errors
kubectl apply --dry-run=client -k k8s/ai-lab

# Describe failed resources
kubectl describe pod -n pmoves
```

### Docker Compose Issues
```bash
# Validate compose file
docker compose -f ../pmoves/docker-compose.yml config

# Check service logs
docker compose -f ../pmoves/docker-compose.yml logs --tail=50
```

## Related Documentation

- [PBnJ Pinokio Application](/pbnj/README.md)
- [PMOVES Architecture](/.claude/CLAUDE.md)
- [Security Hardening Roadmap](/docs/Security-Hardening-Roadmap.md)
- [Deployment Notes](/docs/pmoves-deploy-notes.md)

## Support

For issues or questions:
1. Check deployment logs: `./scripts/deploy-k8s.sh status --target <target>`
2. Review service health: `make verify-all` (from pmoves/ directory)
3. Consult [deployment notes](/docs/pmoves-deploy-notes.md)
