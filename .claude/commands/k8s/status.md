# Kubernetes Status

Check the status of PMOVES services running in Kubernetes.

## Usage

```
/k8s:status [service|namespace] [environment]
```

## Arguments

- `service`: Service name, `all`, or namespace (default: `all`)
- `environment`: `staging`, `production` (default: current context)

## What This Command Does

1. **Cluster Overview:**
   ```bash
   # Cluster info
   kubectl cluster-info

   # Node status
   kubectl get nodes -o wide

   # Current context
   kubectl config current-context
   ```

2. **Namespace Status:**
   ```bash
   # All resources in namespace
   kubectl get all -n pmoves

   # Pod status with resource usage
   kubectl top pods -n pmoves
   ```

3. **Service Health:**
   ```bash
   # Deployment status
   kubectl get deployments -n pmoves

   # Pod health
   kubectl get pods -n pmoves -o wide

   # Service endpoints
   kubectl get endpoints -n pmoves
   ```

4. **Resource Utilization:**
   ```bash
   # Node resources
   kubectl top nodes

   # Pod resources
   kubectl top pods -n pmoves --containers
   ```

## Status Indicators

| Status | Icon | Meaning |
|--------|------|---------|
| Running | ✓ | Pod healthy and serving |
| Pending | ○ | Waiting for resources |
| Failed | ✗ | Container crashed or error |
| Evicted | ⊘ | Node pressure eviction |
| Unknown | ? | Cannot determine state |

## Output Format

```markdown
## Kubernetes Status

### Cluster: pmoves-staging
### Context: pmoves-staging-admin@pmoves-staging
### Namespace: pmoves

### Node Health
| Node | Status | CPU | Memory | Pods |
|------|--------|-----|--------|------|
| node-1 | Ready | 45% | 62% | 28/110 |
| node-2 | Ready | 38% | 58% | 24/110 |
| node-3 | Ready | 52% | 71% | 31/110 |

### Deployments
| Service | Desired | Ready | Up-to-date | Available | Age |
|---------|---------|-------|------------|-----------|-----|
| agent-zero | 3 | 3 | 3 | 3 | 5d |
| hi-rag | 2 | 2 | 2 | 2 | 5d |
| tensorzero | 2 | 2 | 2 | 2 | 5d |
| archon | 1 | 1 | 1 | 1 | 5d |

### Pod Status
| Pod | Status | Restarts | CPU | Memory | Node |
|-----|--------|----------|-----|--------|------|
| agent-zero-abc123 | Running | 0 | 150m | 512Mi | node-1 |
| agent-zero-def456 | Running | 0 | 145m | 498Mi | node-2 |
| hi-rag-xyz789 | Running | 0 | 200m | 1Gi | node-3 |

### Services
| Service | Type | Cluster-IP | External-IP | Ports |
|---------|------|------------|-------------|-------|
| agent-zero | ClusterIP | 10.0.1.50 | <none> | 8080/TCP |
| hi-rag | ClusterIP | 10.0.1.51 | <none> | 8086/TCP |
| tensorzero | LoadBalancer | 10.0.1.52 | 34.x.x.x | 3030/TCP |

### Recent Events (Last 1h)
| Time | Type | Object | Message |
|------|------|--------|---------|
| 5m | Normal | Pod/agent-zero-abc123 | Started container |
| 15m | Warning | Pod/worker-xyz | Back-off restarting |

### Alerts
- ⚠️ worker-xyz: 3 restarts in last hour
- ✓ All critical services healthy
```

## Example

```bash
# Full cluster status
/k8s:status

# Specific service status
/k8s:status agent-zero

# Production environment
/k8s:status all production

# Namespace overview
/k8s:status pmoves-workers
```

## Quick Diagnostics

### Unhealthy Pods
```bash
# Find pods not running
kubectl get pods -n pmoves --field-selector=status.phase!=Running

# Describe failing pod
kubectl describe pod <pod-name> -n pmoves

# Check events
kubectl get events -n pmoves --sort-by='.lastTimestamp' | head -20
```

### Resource Pressure
```bash
# Check node conditions
kubectl describe nodes | grep -A5 "Conditions:"

# Find resource-hungry pods
kubectl top pods -n pmoves --sort-by=memory
```

### Network Issues
```bash
# Check service endpoints
kubectl get endpoints -n pmoves

# Test DNS resolution
kubectl run -it --rm debug --image=busybox -- nslookup agent-zero.pmoves.svc.cluster.local
```

## Health Check Integration

Services expose health endpoints that Kubernetes probes:

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Resource Quotas

### Namespace Limits (pmoves)
```yaml
requests.cpu: "20"
requests.memory: "40Gi"
limits.cpu: "40"
limits.memory: "80Gi"
pods: "100"
```

### Check Current Usage
```bash
kubectl describe quota -n pmoves
kubectl describe limitrange -n pmoves
```

## Notes

- Status refreshes every 30 seconds in watch mode
- Use `kubectl get pods -w` for live updates
- Check Grafana dashboards for historical trends
- PDB status affects rolling update availability
