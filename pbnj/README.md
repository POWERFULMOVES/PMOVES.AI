# PBnJ - Pinokio-Based N-tier Deployment for PMOVES.AI

**PBnJ** (Pinokio-Based N-tier) is a one-click deployment interface for PMOVES.AI, providing graphical controls for managing multi-environment orchestration via [Pinokio](https://pinokio.computer).

## What is PBnJ?

PBnJ bridges the gap between complex multi-cluster Kubernetes deployments and simple one-click management. It provides:

- **Graphical Interface**: Click to deploy/teardown entire PMOVES stacks
- **Multi-Target Support**: AI Lab (K8s), KVM4 Gateway (K8s), Local Dev (Docker Compose)
- **Zero Configuration**: Works out-of-box with PMOVES deployment scripts
- **Integrated Monitoring**: Status checks and log streaming

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Pinokio UI (PBnJ App)                    │
├─────────────────────────────────────────────────────────────┤
│  [Start AI Lab]  [Stop AI Lab]  [Start KVM4]  [Stop KVM4]  │
│  [Local Up]  [Local Down]  [Local Logs]  [Cluster Status]  │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  deploy-k8s.sh    deploy-k8s.sh   deploy-compose.sh
  (AI Lab)         (KVM4)          (Local)
        │                │                │
        ▼                ▼                ▼
  ┌─────────┐      ┌─────────┐     ┌──────────────┐
  │ AI Lab  │      │  KVM4   │     │ Docker       │
  │ K8s     │      │ K8s     │     │ Compose      │
  │ Cluster │      │ Gateway │     │ (localhost)  │
  └─────────┘      └─────────┘     └──────────────┘
```

## Installation

### Prerequisites
- [Pinokio](https://pinokio.computer) installed and running
- For K8s: `kubectl` configured with cluster access
- For Local: Docker Engine with Compose plugin

### Installation Steps

1. **Install Pinokio** (if not already installed):
   ```bash
   # Visit https://pinokio.computer and download for your platform
   ```

2. **Link PBnJ to Pinokio**:

   **Option A: Symlink (Recommended)**
   ```bash
   # macOS/Linux
   ln -s /path/to/PMOVES.AI/pbnj/pinokio/api/pmoves-pbnj \
     ~/pinokio/api/pmoves-pbnj

   # Windows (PowerShell as Admin)
   New-Item -ItemType SymbolicLink `
     -Path "$env:USERPROFILE\pinokio\api\pmoves-pbnj" `
     -Target "C:\path\to\PMOVES.AI\pbnj\pinokio\api\pmoves-pbnj"
   ```

   **Option B: Copy**
   ```bash
   cp -r pbnj/pinokio/api/pmoves-pbnj ~/pinokio/api/
   ```

3. **Restart Pinokio** to detect the new application

4. **Launch PBnJ** from the Pinokio dashboard

## Usage

### AI Lab Cluster (Kubernetes)

**Start AI Lab:**
1. Click "Start AI Lab (K8s)" in PBnJ menu
2. Wait for deployment completion (~2-3 minutes)
3. Verify with "Cluster Status (AI Lab)"

**Stop AI Lab:**
1. Click "Stop AI Lab (K8s)"
2. Confirms all resources deleted

**What it does:**
- Applies Kustomize manifests from `deploy/k8s/ai-lab/`
- Deploys 5 replicas of PMOVES core
- Configures ingress at `pmoves.lab.local`
- Uses hardened image tag: `v1.0.0-lab-hardened`

### KVM4 Gateway (Kubernetes)

**Start KVM4:**
1. Click "Start KVM4 Stack (K8s)"
2. Gateway deploys to edge cluster

**Stop KVM4:**
1. Click "Stop KVM4 Stack (K8s)"

**What it does:**
- Applies Kustomize manifests from `deploy/k8s/kvm4/`
- Deploys 2 replicas for HA
- Configures ingress at `pmoves.kvm4.yourdomain.tld`
- Uses hardened image tag: `v1.0.0-kvm4-hardened`

### Local Development (Docker Compose)

**Start Local Stack:**
1. Click "Local Dev (Docker) - Up"
2. All PMOVES services start via Docker Compose
3. Access at `http://localhost:*` (see service ports)

**View Logs:**
1. Click "Local Dev (Docker) Logs"
2. Real-time log streaming from all containers

**Stop Local Stack:**
1. Click "Local Dev (Docker) - Down"
2. Containers stopped and removed

**What it does:**
- Runs `deploy/scripts/deploy-compose.sh`
- Uses compose file: `pmoves/docker-compose.yml`
- Project name: `pmoves_local`

## Configuration

### Environment Variables

Create `.env` file in PMOVES.AI root or set in your shell:

```bash
# Kubernetes Contexts
export PMOVES_K8S_CONTEXT_AI_LAB=ai-lab
export PMOVES_K8S_CONTEXT_KVM4=kvm4
export PMOVES_K8S_CONTEXT_LOCAL=kind-pmoves

# Kubernetes Namespaces
export PMOVES_K8S_NS_AI_LAB=pmoves
export PMOVES_K8S_NS_KVM4=pmoves
export PMOVES_K8S_NS_LOCAL=pmoves-dev

# Docker Compose
export PMOVES_COMPOSE_FILE=/home/pmoves/PMOVES.AI/pmoves/docker-compose.yml
export PMOVES_COMPOSE_PROJECT=pmoves_local
```

### Customizing Workflows

PBnJ workflows are JSON files in `pinokio/api/pmoves-pbnj/`. Edit these to customize behavior:

**Example: Add pre-deployment health check**

Edit `lab-up.json`:
```json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": ["kubectl", "cluster-info"]
      }
    },
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": [
          "bash",
          "deploy/scripts/deploy-k8s.sh",
          "apply",
          "--target",
          "ai-lab"
        ]
      }
    }
  ]
}
```

### Adding Custom Icon

Replace `pinokio/api/pmoves-pbnj/icon.png` with your custom icon:
- Recommended: 512x512 PNG
- Transparent background
- PMOVES.AI branding

## Workflow Files

| File | Description | Command |
|------|-------------|---------|
| `lab-up.json` | Deploy AI Lab | `deploy-k8s.sh apply --target ai-lab` |
| `lab-down.json` | Teardown AI Lab | `deploy-k8s.sh delete --target ai-lab` |
| `kvm4-up.json` | Deploy KVM4 | `deploy-k8s.sh apply --target kvm4` |
| `kvm4-down.json` | Teardown KVM4 | `deploy-k8s.sh delete --target kvm4` |
| `status.json` | Cluster status | `deploy-k8s.sh status --target ai-lab` |
| `local-up.json` | Start local stack | `deploy-compose.sh up` |
| `local-down.json` | Stop local stack | `deploy-compose.sh down` |
| `local-logs.json` | Stream logs | `deploy-compose.sh logs` |

## Troubleshooting

### "Command not found: kubectl"
**Solution:** Install kubectl and add to PATH
```bash
# macOS
brew install kubectl

# Ubuntu/Debian
sudo apt-get install -y kubectl

# Verify
kubectl version --client
```

### "Context not found: ai-lab"
**Solution:** Set correct context name via environment variable
```bash
export PMOVES_K8S_CONTEXT_AI_LAB=your-actual-context
kubectl config get-contexts  # List available contexts
```

### "docker compose: command not found"
**Solution:** Install Docker Compose v2 or use docker-compose
```bash
# Install Docker Desktop (includes Compose v2)
# OR install standalone:
sudo apt-get install docker-compose-plugin
```

### Workflow appears but doesn't run
1. Check Pinokio console for errors
2. Verify scripts are executable:
   ```bash
   chmod +x deploy/scripts/*.sh
   ```
3. Test script manually:
   ```bash
   bash deploy/scripts/deploy-k8s.sh status --target ai-lab
   ```

### Changes not reflected in Pinokio
- Restart Pinokio application
- Or: Click "Reload" in Pinokio settings

## Integration with WorkOS IAM

PBnJ is designed to integrate with WorkOS for identity-aware deployments (see Cloud School IAM strategy):

1. **User Authentication**: Pinokio user → WorkOS SSO
2. **Role-Based Access**:
   - Developers: Local dev only
   - DevOps: All environments
   - Admins: Full control + monitoring
3. **Audit Logging**: All PBnJ actions logged to WorkOS audit stream

*Note: WorkOS integration requires additional configuration. See `/docs/Cloud School IAM and Onboarding Strategy.pdf`*

## Development

### Testing New Workflows

1. Create new JSON workflow in `pinokio/api/pmoves-pbnj/`
2. Add menu entry to `pinokio.js`:
   ```javascript
   { text: "My Workflow", href: "my-workflow.json" }
   ```
3. Restart Pinokio to load changes

### Workflow Template

```json
{
  "run": [
    {
      "method": "shell.run",
      "params": {
        "path": "{{local.root}}",
        "cmd": ["bash", "path/to/script.sh", "arg1", "arg2"]
      }
    }
  ]
}
```

Variables:
- `{{local.root}}`: PMOVES.AI repository root
- `{{os.platform}}`: OS platform (darwin, linux, win32)
- `{{env.VAR}}`: Environment variable

## Security Considerations

- **Credential Management**: Never hardcode credentials in workflow files
- **Script Validation**: Ensure deployment scripts validate inputs
- **Least Privilege**: Grant kubectl/docker permissions only as needed
- **Audit Trail**: Enable command logging in Pinokio settings

See `/docs/Security-Hardening-Roadmap.md` for comprehensive security guidelines.

## Related Documentation

- [Deployment Scripts](/deploy/README.md)
- [PMOVES Architecture](/.claude/CLAUDE.md)
- [Kubernetes Manifests](/deploy/k8s/)
- [Pinokio Documentation](https://docs.pinokio.computer)

## Support

For issues or questions:
1. Test deployment scripts directly (bypass Pinokio)
2. Check Pinokio console for error messages
3. Review logs: `./deploy/scripts/deploy-compose.sh logs`
4. Verify environment variables are set

## License

Part of the PMOVES.AI project. See repository root for license details.
