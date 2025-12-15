# Phase 1 Security Hardening - Deployment Guide

**Status**: Ready for Deployment
**Date**: 2025-12-06
**Version**: 1.0.0

> Note (2025-12-14): This document captures the Phase 1 hardening rollout as of 2025-12-06. Since then, additional services and workflows (n8n Voice Agents, Flute Gateway, TensorZero/Ollama local models, etc.) have been added. For the current production baseline and image/compose guidance, prefer `docs/PMOVES.AI-Edition-Hardened-Full.md` and `pmoves/docker-compose.hardened.yml`.

## Overview

This guide covers the deployment of Phase 1 Security Hardening to PMOVES.AI production environments. Phase 1 implements foundational container security controls across all 30 services:

- **29 services** running as non-root user `pmoves` (UID/GID 65532:65532)
- **30 services** with read-only root filesystems + tmpfs mounts
- **30 services** with capability drops and security options
- **Kubernetes SecurityContext** templates ready for K8s deployments

### What's Changed

1. All custom service Dockerfiles now create and use `pmoves:pmoves` user
2. `docker-compose.hardened.yml` overlay applies security constraints to all services
3. Tmpfs mounts configured for `/tmp`, `/home/pmoves/.cache`, and specialized paths
4. All containers drop Linux capabilities and prevent privilege escalation

## Pre-Deployment Checklist

Before deploying, verify the following:

### Environment Readiness

- [ ] **Backup current configuration**: Create snapshot of running services
  ```bash
  cd /home/pmoves/PMOVES.AI/pmoves
  docker compose ps > deployment-backup-$(date +%Y%m%d-%H%M%S).txt
  docker images > images-backup-$(date +%Y%m%d-%H%M%S).txt
  ```

- [ ] **Docker version check**: Ensure Docker 20.10+ and Compose V2+
  ```bash
  docker --version  # Should be 20.10.0 or higher
  docker compose version  # Should be v2.x.x
  ```

- [ ] **Docker builder**: Verify builder is set to `default` (not `buildx`)
  ```bash
  docker buildx ls
  # If 'default' builder is not active:
  docker buildx use default
  ```

- [ ] **Resource availability**: Check disk space for tmpfs allocations
  ```bash
  df -h /var/lib/docker
  # Ensure sufficient space for:
  # - API services: 500M /tmp + 200M cache each
  # - GPU services: 2G /tmp + 10G cache + 4G shm each
  # - Media ingestion: 10G /tmp + 500M cache
  ```

- [ ] **GPU services**: Verify GPU access for services requiring video group
  ```bash
  # Check video group exists
  getent group video

  # Verify NVIDIA runtime available (if using GPU services)
  docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
  ```

- [ ] **Persistent volumes**: Verify ownership of host-mounted directories
  ```bash
  # Check Agent Zero directories
  ls -la /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/

  # Fix ownership if needed (before deployment)
  sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/
  sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/notebook-sync/
  ```

### Configuration Validation

- [ ] **Hardened config exists**:
  ```bash
  ls -lh /home/pmoves/PMOVES.AI/pmoves/docker-compose.hardened.yml
  # Should show 30 services configured
  ```

- [ ] **Service count matches**:
  ```bash
  cd /home/pmoves/PMOVES.AI/pmoves
  # Count services in base config
  grep "^  [a-z]" docker-compose.yml | wc -l

  # Count services in hardened overlay
  grep "^  [a-z]" docker-compose.hardened.yml | wc -l
  # Should be 30
  ```

- [ ] **Dockerfile USER directives**:
  ```bash
  # Verify all service Dockerfiles have USER directive
  grep -r "^USER pmoves:pmoves" services/*/Dockerfile | wc -l
  # Should be 29 (all custom services)
  ```

## Deployment Procedures

### Option A: Docker Compose Deployment (Recommended for Development/Staging)

#### 1. Canary Deployment (Test One Service First)

Start with a single, non-critical service to validate the configuration:

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Test with presign service (small, simple, no external dependencies)
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  up -d presign

# Verify it starts successfully
docker compose ps presign
docker compose logs presign --tail 50

# Check it's running as non-root
docker compose exec presign id
# Expected output: uid=65532(pmoves) gid=65532(pmoves) groups=65532(pmoves)

# Verify read-only filesystem
docker compose exec presign touch /test-readonly
# Expected: touch: cannot touch '/test-readonly': Read-only file system

# Verify tmpfs is writable
docker compose exec presign touch /tmp/test-tmpfs
docker compose exec presign ls -la /tmp/test-tmpfs
# Should succeed

# Test service endpoint
curl -v http://localhost:8088/health
# Should return 200 OK
```

If canary deployment succeeds, proceed to full deployment.

#### 2. Full Deployment

Deploy all services with hardened configuration:

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Stop current services (optional - you can also do rolling update)
docker compose down

# Deploy with hardened overlay
# This merges docker-compose.yml + docker-compose.hardened.yml
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# Monitor startup
docker compose logs -f --tail 100
```

#### 3. Verify Deployment Success

Run validation commands to ensure all services are running correctly:

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Check all containers are running
docker compose ps

# Verify all services running as UID 65532
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: {{.Config.User}}' | grep -v "65532:65532" || echo "All services running as pmoves user"

# Verify read-only filesystems active
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}' | grep "false" || echo "All services have read-only root"

# Verify tmpfs mounts present
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: {{range .Mounts}}{{if eq .Type "tmpfs"}}tmpfs:{{.Destination}} {{end}}{{end}}'

# Test service endpoints
echo "Testing service health endpoints..."
curl -f http://localhost:8080/healthz || echo "Agent Zero: FAIL"
curl -f http://localhost:8091/healthz || echo "Archon: FAIL"
curl -f http://localhost:8086/health || echo "Hi-RAG v2: FAIL"
curl -f http://localhost:8077/health || echo "PMOVES.YT: FAIL"
curl -f http://localhost:8098/health || echo "DeepResearch: FAIL"
curl -f http://localhost:8099/metrics || echo "SupaSerch: FAIL"

# Check NATS connectivity
docker compose exec nats nats-server --signal healthz
```

#### 4. Monitor for Issues

Watch logs for permission errors or startup failures:

```bash
# Watch all service logs
docker compose logs -f --tail 50

# Check for common issues
docker compose logs --tail 200 | grep -i "permission denied"
docker compose logs --tail 200 | grep -i "read-only"
docker compose logs --tail 200 | grep -i "cannot create"

# Individual service debugging
docker compose logs <service-name> --tail 100 -f
```

#### Expected Warnings (Safe to Ignore)

Some services may log benign warnings during startup:

- **Agent Zero**: May attempt to write to `/a0/` directories - ensure volumes are owned by UID 65532
- **DeepResearch**: May log about `/opt/DeepResearch` tmpfs - this is expected and working correctly
- **GPU Services**: May log CUDA initialization messages - normal for GPU-enabled containers

#### Common Issues and Fixes

**Issue**: Service fails with "permission denied" on volume mount

```bash
# Fix: Update ownership of host-mounted directory
sudo chown -R 65532:65532 /path/to/mounted/volume

# Then restart service
docker compose restart <service-name>
```

**Issue**: Service fails with "cannot create directory" in cache

```bash
# Verify tmpfs mount is present
docker compose exec <service-name> df -h | grep cache

# If missing, rebuild with hardened config
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d --force-recreate <service-name>
```

**Issue**: GPU service fails to access GPU

```bash
# Verify GPU access
docker compose exec <gpu-service> nvidia-smi

# If fails, check container has proper device access
docker compose exec <gpu-service> ls -la /dev/nvidia*

# May need to add user to video group in Dockerfile (already done for Phase 1)
```

**Issue**: Service exits immediately with no logs

```bash
# Check container exit code
docker compose ps <service-name>

# Inspect container configuration
docker compose exec <service-name> id
docker compose exec <service-name> ls -la /

# Try running with shell to debug
docker compose run --rm <service-name> /bin/sh
```

### Option B: Kubernetes Deployment

#### 1. Build and Tag Images

First, build hardened images for Kubernetes:

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Build all service images with hardened Dockerfiles
make build-all

# Tag for your registry (example using GHCR)
export REGISTRY="ghcr.io/powerfulmoves"
export TAG="hardened-v1.0.0"

docker tag pmoves/agent-zero:latest $REGISTRY/agent-zero:$TAG
docker tag pmoves/archon:latest $REGISTRY/archon:$TAG
docker tag pmoves/hi-rag-gateway-v2:latest $REGISTRY/hi-rag-gateway-v2:$TAG
# ... repeat for all services

# Push to registry
docker push $REGISTRY/agent-zero:$TAG
docker push $REGISTRY/archon:$TAG
# ... repeat for all services
```

#### 2. Validate Kubernetes SecurityContext

Review the SecurityContext template in `/home/pmoves/PMOVES.AI/deploy/k8s/base/pmoves-core-deployment.yaml`:

```bash
cd /home/pmoves/PMOVES.AI

# View current SecurityContext
cat deploy/k8s/base/pmoves-core-deployment.yaml | grep -A 20 "securityContext:"
```

Expected SecurityContext configuration:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 65532      # Maps to pmoves user in Dockerfile
  runAsGroup: 65532     # Maps to pmoves group in Dockerfile
  fsGroup: 65532
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

#### 3. Build Kustomize Manifests

Generate manifests for each overlay:

```bash
cd /home/pmoves/PMOVES.AI/deploy/k8s

# Build for local development
kubectl kustomize local > /tmp/pmoves-local-hardened.yaml
kubectl apply --dry-run=client -f /tmp/pmoves-local-hardened.yaml

# Build for ai-lab overlay
kubectl kustomize ai-lab > /tmp/pmoves-ai-lab-hardened.yaml
kubectl apply --dry-run=client -f /tmp/pmoves-ai-lab-hardened.yaml

# Build for kvm4 overlay
kubectl kustomize kvm4 > /tmp/pmoves-kvm4-hardened.yaml
kubectl apply --dry-run=client -f /tmp/pmoves-kvm4-hardened.yaml
```

#### 4. Deploy to Kubernetes

Deploy to your chosen environment:

```bash
# Deploy to local (example)
kubectl apply -k /home/pmoves/PMOVES.AI/deploy/k8s/local

# Monitor deployment
kubectl get pods -n pmoves-ai -w

# Check pod security settings
kubectl get pod <pod-name> -n pmoves-ai -o jsonpath='{.spec.securityContext}'
kubectl get pod <pod-name> -n pmoves-ai -o jsonpath='{.spec.containers[0].securityContext}'

# Verify pods are running as UID 65532
kubectl exec -n pmoves-ai <pod-name> -- id
# Expected: uid=65532(pmoves) gid=65532(pmoves)

# Test service endpoints (port-forward first)
kubectl port-forward -n pmoves-ai svc/pmoves-core 8080:8080
curl http://localhost:8080/healthz
```

#### 5. Kubernetes Health Checks

Verify health probes are working:

```bash
# Check readiness probes
kubectl get pods -n pmoves-ai -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'

# Check liveness probes
kubectl describe pod <pod-name> -n pmoves-ai | grep -A 5 "Liveness:"

# View pod events for probe failures
kubectl get events -n pmoves-ai --sort-by='.lastTimestamp'
```

## Rollback Procedures

If issues occur, you can quickly rollback to the non-hardened configuration:

### Docker Compose Rollback

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Stop hardened services
docker compose -f docker-compose.yml -f docker-compose.hardened.yml down

# Restart without hardened overlay
docker compose up -d

# Verify services are running
docker compose ps
```

### Kubernetes Rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/pmoves-core -n pmoves-ai

# Or rollback to specific revision
kubectl rollout history deployment/pmoves-core -n pmoves-ai
kubectl rollout undo deployment/pmoves-core --to-revision=<revision-number> -n pmoves-ai

# Monitor rollback
kubectl rollout status deployment/pmoves-core -n pmoves-ai
```

## Post-Deployment Validation

After successful deployment, run comprehensive validation:

### 1. Service Availability Tests

```bash
# Test all service endpoints
curl -f http://localhost:8080/healthz  # Agent Zero
curl -f http://localhost:8091/healthz  # Archon
curl -f http://localhost:8086/health   # Hi-RAG v2
curl -f http://localhost:8077/health   # PMOVES.YT
curl -f http://localhost:8098/health   # DeepResearch
curl -f http://localhost:8099/metrics  # SupaSerch
curl -f http://localhost:8088/health   # Presign
curl -f http://localhost:${EXTRACT_WORKER_HOST_PORT:-8083}/health   # Extract Worker

# Test NATS pub/sub
docker compose exec nats nats pub test.subject "test message"
```

### 2. Security Validation

```bash
# Verify no containers running as root
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: User={{.Config.User}} RootFS={{.HostConfig.ReadonlyRootfs}}' \
  | grep -E "User=root|RootFS=false" || echo "Security checks passed"

# Verify capability drops
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: CapDrop={{.HostConfig.CapDrop}}' \
  | grep -v "ALL" || echo "All capabilities dropped"

# Verify no-new-privileges
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}: NoNewPrivileges={{.HostConfig.SecurityOpt}}' \
  | grep "no-new-privileges:true"
```

### 3. Functional Testing

Run end-to-end tests to verify core functionality:

```bash
# Test Hi-RAG query
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5, "rerank": true}'

# Test Agent Zero MCP API
curl -X POST http://localhost:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}'

# Test PMOVES.YT health
curl http://localhost:8077/health

# Test TensorZero gateway (OpenAI-compatible)
curl -X POST http://localhost:3030/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "tensorzero::model_name::qwen2_5_14b", "messages": [{"role": "user", "content": "Hello"}]}'
```

### 4. Performance Baseline

Establish baseline metrics for comparison:

```bash
# Query Prometheus for service latencies
curl -s 'http://localhost:9090/api/v1/query?query=http_request_duration_seconds' | jq

# Check container resource usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Monitor tmpfs usage
docker compose ps -q | xargs docker inspect \
  --format '{{.Name}}' | while read name; do
    echo "$name tmpfs usage:"
    docker compose exec $(echo $name | sed 's/.*-//') df -h | grep tmpfs
  done
```

## Monitoring and Alerts

After deployment, configure monitoring:

### Prometheus Metrics

Key metrics to monitor:

- Container restart count: `container_restarts_total`
- Service availability: `up{job="<service-name>"}`
- HTTP request latency: `http_request_duration_seconds`
- Error rates: `http_requests_total{status=~"5.."}`

### Grafana Dashboards

Import the "Services Overview" dashboard and monitor:

- Service health status
- Request rates and latencies
- Error rates
- Resource utilization (CPU, Memory, Disk)

### Loki Log Queries

Monitor for security-related log patterns:

```logql
{container_name=~".+"} |~ "permission denied|read-only|cannot create"
```

### Docker Compose Health Checks

```bash
# Continuous health monitoring
watch -n 10 'docker compose ps'

# Alert on unhealthy containers
docker compose ps --format json | jq -r '.[] | select(.Health != "healthy") | .Name'
```

## Troubleshooting Guide

### Service Won't Start

1. Check logs for permission errors:
   ```bash
   docker compose logs <service-name> --tail 100
   ```

2. Verify tmpfs mounts:
   ```bash
   docker compose exec <service-name> df -h
   ```

3. Check file ownership on host volumes:
   ```bash
   ls -la /path/to/host/volume
   ```

4. Rebuild container with hardened config:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
     up -d --force-recreate --build <service-name>
   ```

### Permission Denied Errors

1. Identify the file/directory:
   ```bash
   docker compose logs <service-name> | grep "permission denied"
   ```

2. Check if it's a host volume:
   ```bash
   docker compose exec <service-name> ls -la /path/to/file
   ```

3. Fix ownership:
   ```bash
   sudo chown -R 65532:65532 /path/on/host
   docker compose restart <service-name>
   ```

### Read-Only Filesystem Errors

1. Verify the path should be writable:
   - `/tmp` - should be tmpfs (writable)
   - `/home/pmoves/.cache` - should be tmpfs (writable)
   - Everything else - should be read-only

2. If path needs to be writable, add tmpfs mount in `docker-compose.hardened.yml`:
   ```yaml
   tmpfs:
     - /path/to/writable:size=100M,uid=65532,gid=65532
   ```

### GPU Access Issues

1. Verify GPU visible to container:
   ```bash
   docker compose exec <gpu-service> nvidia-smi
   ```

2. Check video group membership:
   ```bash
   docker compose exec <gpu-service> id
   # Should show: groups=65532(pmoves),44(video)
   ```

3. Verify NVIDIA runtime configuration:
   ```bash
   docker info | grep -i runtime
   ```

## Performance Impact Assessment

Expected performance changes after hardening:

### Positive Impacts

- **Security**: Reduced attack surface, privilege containment
- **Stability**: Prevent accidental filesystem corruption
- **Compliance**: Meet security baseline requirements

### Neutral/Minimal Impact

- **CPU**: No measurable impact from security constraints
- **Memory**: Tmpfs uses RAM but sizes are appropriate for workloads
- **Network**: No impact on network performance

### Monitoring Recommendations

Monitor these metrics post-deployment:

1. **Container Restart Rate**: Should remain stable or decrease
2. **Response Latency**: Should not increase (±5% acceptable variance)
3. **Memory Usage**: May increase slightly due to tmpfs, but within limits
4. **Error Rates**: Should not increase

If you observe degradation beyond expected variance, investigate:

```bash
# Compare before/after metrics
curl 'http://localhost:9090/api/v1/query_range?query=http_request_duration_seconds&start=<before-time>&end=<after-time>&step=1m'

# Check for OOM events
docker compose ps -a | grep -i oom

# Review container events
docker events --since <deployment-time>
```

## Next Steps

After successful Phase 1 deployment:

1. **Monitor for 48 hours**: Watch for any late-appearing issues
2. **Collect baseline metrics**: Establish performance baselines
3. **Update runbooks**: Document any environment-specific adjustments
4. **Plan Phase 2**: Secret management with Docker Secrets
5. **Plan Phase 3**: Network policies and egress controls

## Support and Documentation

- **Primary Config**: `/home/pmoves/PMOVES.AI/pmoves/docker-compose.hardened.yml`
- **Dockerfiles**: `/home/pmoves/PMOVES.AI/pmoves/services/*/Dockerfile`
- **K8s Manifests**: `/home/pmoves/PMOVES.AI/deploy/k8s/`
- **Monitoring**: Grafana at `http://localhost:3000`
- **Logs**: Loki at `http://localhost:3100`

For issues or questions:
- Review service logs: `docker compose logs <service-name>`
- Check Prometheus alerts: `http://localhost:9090/alerts`
- View Grafana dashboards: `http://localhost:3000`

## Appendix: Service Security Matrix

| Service | UID:GID | Read-Only FS | Tmpfs /tmp | Tmpfs Cache | Cap Drop | Notes |
|---------|---------|--------------|------------|-------------|----------|-------|
| agent-zero | 65532:65532 | Yes | 1G | 500M | ALL | Persistent volumes need ownership |
| archon | 65532:65532 | Yes | 1G | 2G | ALL | Uses Docker secrets |
| hi-rag-gateway-v2 | 65532:65532 | Yes | 500M | 200M | ALL | CPU variant |
| hi-rag-gateway-v2-gpu | 65532:65532 | Yes | 2G | 10G + 4G shm | ALL | GPU variant |
| extract-worker | 65532:65532 | Yes | 500M | 200M | ALL | - |
| langextract | 65532:65532 | Yes | 500M | 200M | ALL | - |
| presign | 65532:65532 | Yes | 500M | 200M | ALL | - |
| render-webhook | 65532:65532 | Yes | 500M | 200M | ALL | - |
| retrieval-eval | 65532:65532 | Yes | 500M | 200M | ALL | - |
| pdf-ingest | 65532:65532 | Yes | 500M | 200M | ALL | - |
| jellyfin-bridge | 65532:65532 | Yes | 500M | 200M | ALL | - |
| invidious-companion-proxy | 65532:65532 | Yes | 500M | 200M | ALL | - |
| ffmpeg-whisper | 65532:65532 | Yes | 2G | 10G + 4G shm | ALL | GPU, HF cache configured |
| media-video | 65532:65532 | Yes | 2G | 10G + 4G shm | ALL | GPU, HF cache configured |
| media-audio | 65532:65532 | Yes | 2G | 10G + 4G shm | ALL | GPU, HF cache configured |
| hi-rag-gateway-gpu | 65532:65532 | Yes | 2G | 10G + 4G shm | ALL | Legacy GPU variant |
| deepresearch | 65532:65532 | Yes | 500M | 100M + 100M app | ALL | Special tmpfs for app dir |
| supaserch | 65532:65532 | Yes | 500M | 100M | ALL | - |
| publisher-discord | 65532:65532 | Yes | 500M | 100M | ALL | - |
| mesh-agent | 65532:65532 | Yes | 500M | 100M | ALL | - |
| nats-echo-req | 65532:65532 | Yes | 500M | 100M | ALL | - |
| nats-echo-res | 65532:65532 | Yes | 500M | 100M | ALL | - |
| publisher | 65532:65532 | Yes | 500M | 100M | ALL | - |
| analysis-echo | 65532:65532 | Yes | 500M | 100M | ALL | - |
| graph-linker | 65532:65532 | Yes | 500M | 100M | ALL | - |
| comfy-watcher | 65532:65532 | Yes | 500M | 100M | ALL | - |
| grayjay-plugin-host | 65532:65532 | Yes | 500M | 100M | ALL | - |
| channel-monitor | 65532:65532 | Yes | 500M | 100M | ALL | - |
| pmoves-yt | 65532:65532 | Yes | 10G | 500M | ALL | Large tmpfs for media processing |
| notebook-sync | 65532:65532 | Yes | 100M | 50M | ALL | Persistent /data volume |

**Third-party services** (not modified in Phase 1):
- postgres, postgrest, qdrant, meilisearch, neo4j, minio, nats
- tensorzero-gateway, tensorzero-ui, tensorzero-clickhouse, pmoves-ollama
- invidious, invidious-db, invidious-companion
- cloudflared, bgutil-pot-provider, grayjay-server

These run with their upstream default security configurations and will be evaluated for Phase 2+.

---

**End of Phase 1 Deployment Guide**
