# Kubernetes Deploy

Deploy or update PMOVES services to Kubernetes cluster.

## Usage

```
/k8s:deploy [service|all] [environment]
```

## Arguments

- `service`: Service name or `all` for full deployment (default: `all`)
- `environment`: `staging`, `production` (default: `staging`)

## What This Command Does

1. **Pre-flight Checks:**
   ```bash
   # Verify cluster access
   kubectl cluster-info
   kubectl auth can-i create deployments

   # Check current context
   kubectl config current-context
   ```

2. **Build and Push Images:**
   ```bash
   # Build with BuildKit
   docker buildx build -t ghcr.io/powerfulmoves/<service>:latest .

   # Push to registry
   docker push ghcr.io/powerfulmoves/<service>:latest
   ```

3. **Apply Kustomize Manifests:**
   ```bash
   # Preview changes
   kubectl kustomize deploy/k8s/overlays/${ENV}

   # Apply deployment
   kubectl apply -k deploy/k8s/overlays/${ENV}
   ```

4. **Verify Rollout:**
   ```bash
   kubectl rollout status deployment/<service> -n pmoves
   ```

## Safety Rules

### Pre-Deploy Checklist
- [ ] All smoke tests passing (`make verify-all`)
- [ ] No critical Dependabot alerts
- [ ] PR approved and merged (for production)
- [ ] Backup verified (for stateful services)

### Production Deployment
- Requires manual approval
- Must be from `main` branch
- Canary deployment first (10% traffic)
- Rollback plan documented

### BLOCKED Operations
- Deploy to production from feature branch
- Skip staging validation
- Deploy during incident
- Force push over failed health checks

## Deployment Structure

```
deploy/
├── k8s/
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   └── services/
│   │       ├── agent-zero/
│   │       ├── hi-rag/
│   │       ├── tensorzero/
│   │       └── ...
│   └── overlays/
│       ├── staging/
│       │   ├── kustomization.yaml
│       │   └── patches/
│       └── production/
│           ├── kustomization.yaml
│           └── patches/
└── scripts/
    ├── deploy-k8s.sh
    └── rollback.sh
```

## Service Deployment Order

Critical path (deploy in order):

| Order | Service | Dependencies | Port |
|-------|---------|--------------|------|
| 1 | nats | None | 4222 |
| 2 | supabase | nats | 3010 |
| 3 | minio | None | 9000 |
| 4 | qdrant | None | 6333 |
| 5 | tensorzero | clickhouse | 3030 |
| 6 | hi-rag | qdrant, neo4j, meilisearch | 8086 |
| 7 | agent-zero | nats, supabase | 8080 |
| 8 | archon | agent-zero, supabase | 8091 |
| 9+ | workers | All above | Various |

## Output Format

```markdown
## Deployment Status

### Environment: staging
### Service: agent-zero

### Pre-flight
- [x] Cluster accessible
- [x] Namespace exists
- [x] Secrets configured
- [x] Image built and pushed

### Deployment Progress
| Step | Status | Duration |
|------|--------|----------|
| Image build | ✓ Complete | 45s |
| Image push | ✓ Complete | 12s |
| Apply manifests | ✓ Complete | 3s |
| Rollout | ✓ Complete | 28s |

### Verification
- **Pods Ready:** 3/3
- **Health Check:** Passing
- **Endpoints:** Active

### Access
- **Internal:** agent-zero.pmoves.svc.cluster.local:8080
- **External:** https://agent-zero.staging.pmoves.ai
```

## Example

```bash
# Deploy all services to staging
/k8s:deploy all staging

# Deploy specific service
/k8s:deploy agent-zero staging

# Deploy to production (requires approval)
/k8s:deploy all production

# Preview changes without applying
kubectl kustomize deploy/k8s/overlays/staging
```

## Rollback Procedures

### Quick Rollback
```bash
# Rollback to previous revision
kubectl rollout undo deployment/<service> -n pmoves

# Rollback to specific revision
kubectl rollout undo deployment/<service> -n pmoves --to-revision=2
```

### Full Environment Rollback
```bash
# List previous deployments
kubectl rollout history deployment/<service> -n pmoves

# Rollback all services
./deploy/scripts/rollback.sh staging
```

## Environment Variables

Kubernetes Secrets required:
- `supabase-credentials` - DB connection strings
- `minio-credentials` - Object storage keys
- `tensorzero-keys` - LLM provider API keys
- `nats-credentials` - NATS auth tokens

## Monitoring During Deploy

```bash
# Watch pods
kubectl get pods -n pmoves -w

# Stream logs
kubectl logs -f deployment/<service> -n pmoves

# Check events
kubectl get events -n pmoves --sort-by='.lastTimestamp'
```

## Notes

- Always deploy to staging first
- Use `kubectl diff` before `kubectl apply`
- Monitor Grafana during production deploys
- Canary deployments use 10% traffic split
- PDB (Pod Disruption Budget) ensures availability
