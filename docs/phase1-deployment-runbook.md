# Phase 1 Hardened Deployment Runbook

**PMOVES.AI Security Hardening - Production Deployment Guide**

> **Status:** Phase 1 Complete
> **Last Updated:** 2025-12-06
> **Estimated Deployment Time:** 5-15 minutes (method dependent)

---

## Overview

This runbook provides step-by-step instructions for deploying Phase 1 security hardening to production. Phase 1 implements:

- **Non-root execution:** All services run as UID/GID 65532 (`pmoves` user)
- **Read-only root filesystems:** Immutable containers with explicit tmpfs mounts
- **Minimal capabilities:** Dropped all unnecessary Linux capabilities
- **Resource limits:** CPU/memory constraints per service
- **GPU access control:** Video group membership for GPU services only

**Security Benefits:**
- Prevents privilege escalation attacks
- Limits blast radius of container compromise
- Enforces principle of least privilege
- Provides resource isolation

---

## Prerequisites

### Required Files
- `/home/pmoves/PMOVES.AI/pmoves/docker-compose.yml` - Base configuration
- `/home/pmoves/PMOVES.AI/pmoves/docker-compose.hardened.yml` - Security overlay
- `/home/pmoves/PMOVES.AI/pmoves/scripts/validate-phase1-hardening.sh` - Validation script

### Required Permissions
- Docker daemon access (`docker compose` commands)
- Sudo access (for volume ownership fixes if needed)
- Read/write access to `/home/pmoves/PMOVES.AI/pmoves/data/*` directories

### System Requirements
- Docker Engine 20.10+ (for read-only rootfs support)
- Docker Compose v2.x (for multiple compose file support)
- Sufficient disk space for tmpfs mounts (typically 100-500MB per service)

---

## Section 1: Pre-Flight Checks

**Run these commands before deployment to verify readiness.**

```bash
# Navigate to project directory
cd /home/pmoves/PMOVES.AI/pmoves

# 1. Verify hardened config exists
test -f docker-compose.hardened.yml && echo "✅ Hardened config found" || echo "❌ Missing hardened config"

# 2. Check current running services
echo "Current service count: $(docker compose ps --all | wc -l)"
docker compose ps --all

# 3. Backup current configuration
mkdir -p /tmp/pmoves-backups
docker compose config > /tmp/pmoves-backups/docker-compose-backup-$(date +%Y%m%d-%H%M%S).yml
echo "✅ Configuration backed up to /tmp/pmoves-backups/"

# 4. Verify Docker builder is 'default' (not pmoves-builder)
echo "Checking Docker builder..."
docker buildx ls | grep "^default" && echo "✅ Using default builder" || echo "⚠️  Non-default builder active"

# 5. Verify validation script exists and is executable
test -x scripts/validate-phase1-hardening.sh && echo "✅ Validation script ready" || echo "❌ Validation script missing or not executable"

# 6. Check current Docker storage usage
echo "Current Docker storage usage:"
docker system df

# 7. Verify required volumes exist
for vol in agent-zero/memory agent-zero/knowledge; do
  test -d "data/$vol" && echo "✅ Volume exists: data/$vol" || echo "❌ Missing: data/$vol"
done

# 8. Check for any running migrations or critical tasks
echo "Running containers:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

**Expected Pre-Flight Output:**
- All checks return ✅ (green checkmarks)
- No critical services in "restarting" state
- Backup file created in `/tmp/pmoves-backups/`

**⚠️ STOP if any pre-flight check fails. Resolve issues before proceeding.**

---

## Section 2: Deployment Methods

Choose the deployment method based on your environment and risk tolerance:

| Method | Downtime | Safety | Recommended For |
|--------|----------|--------|-----------------|
| **Canary** | Minimal | Highest | Production |
| **Full Stack** | 30-60s | Medium | Staging/Dev |
| **Rolling** | None | High | Large deployments |

---

### Method A: Canary Deployment (RECOMMENDED FOR PRODUCTION)

**Safest method - test one service before full deployment.**

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Step 1: Test with presign service (simple, no dependencies)
echo "🔍 Deploying canary service (presign)..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d presign

# Step 2: Wait for container to stabilize
sleep 10

# Step 3: Verify presign is running as pmoves user (UID 65532)
echo "Verifying presign user..."
docker exec pmoves-presign-1 id
# Expected output: uid=65532(pmoves) gid=65532(pmoves)

# Step 4: Verify read-only filesystem
echo "Verifying read-only filesystem..."
docker inspect pmoves-presign-1 --format 'ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}'
# Expected: ReadonlyRootfs=true

# Step 5: Test presign functionality
echo "Testing presign health..."
curl -s http://localhost:8088/health || echo "⚠️  Presign not responding"

# Step 6: Check logs for errors
echo "Checking logs for errors..."
docker compose logs presign --tail=50 | grep -i error && echo "⚠️  Errors detected" || echo "✅ No errors"

# ✅ If all checks pass, proceed with full deployment
echo ""
echo "🎯 Canary validation successful! Proceeding with full deployment..."
echo ""

# Step 7: Deploy all services
docker compose \
  -f docker-compose.yml \
  -f docker-compose.hardened.yml \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# Step 8: Wait for services to start
echo "⏳ Waiting 30 seconds for services to stabilize..."
sleep 30

# Step 9: Verify all services are running
echo "📊 Service status:"
docker compose ps
```

**Canary Success Criteria:**
- Presign exits 0 on `id` command
- ReadonlyRootfs shows `true`
- Health endpoint returns 200 OK
- No error logs detected

**If canary fails, STOP and investigate before deploying full stack.**

---

### Method B: Full Stack Deployment

**Faster but higher risk - deploys all services at once.**

> ⚠️ **WARNING:** This method causes 30-60 seconds of downtime. Use for non-production environments.

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Step 1: Stop all current services
echo "🛑 Stopping all services..."
docker compose down

# Optional: Clean up orphaned volumes (only if needed)
# docker volume prune -f

# Step 2: Deploy hardened stack
echo "🚀 Deploying hardened stack..."
docker compose \
  -f docker-compose.yml \
  -f docker-compose.hardened.yml \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# Step 3: Wait for services to start
echo "⏳ Waiting 30 seconds for services to stabilize..."
sleep 30

# Step 4: Verify all services are healthy
echo "📊 Service status:"
docker compose ps

# Step 5: Quick health check
echo "🏥 Health check:"
curl -s http://localhost:8086/health && echo " ✅ Hi-RAG v2" || echo " ❌ Hi-RAG v2"
curl -s http://localhost:8080/healthz && echo " ✅ Agent Zero" || echo " ❌ Agent Zero"
curl -s http://localhost:3030/health && echo " ✅ TensorZero" || echo " ❌ TensorZero"
```

**Full Stack Success Criteria:**
- All services show "running" in `docker compose ps`
- Health endpoints respond within 30 seconds
- No containers in "restarting" state

---

### Method C: Rolling Update (Zero Downtime)

**Progressive deployment in dependency order - ideal for large production systems.**

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# Step 1: Data layer (databases and message bus)
echo "📦 Phase 1: Deploying data layer..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  qdrant neo4j meilisearch minio nats supabase-db

# Wait for databases to initialize
echo "⏳ Waiting 15 seconds for databases..."
sleep 15

# Verify data layer
docker compose ps qdrant neo4j meilisearch minio nats supabase-db

# Step 2: Observability infrastructure
echo "📊 Phase 2: Deploying observability..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  tensorzero-clickhouse tensorzero tensorzero-ui prometheus grafana loki promtail

sleep 10
docker compose ps tensorzero-clickhouse tensorzero prometheus

# Step 3: Workers and processing services
echo "⚙️  Phase 3: Deploying workers..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  extract-worker langextract presign render-webhook \
  ffmpeg-whisper media-video-analyzer media-audio-analyzer

sleep 10
docker compose ps extract-worker langextract presign

# Step 4: RAG and search services
echo "🔍 Phase 4: Deploying RAG services..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  hi-rag-gateway-v2 hi-rag-gateway-v1-cpu

sleep 10
curl -s http://localhost:8086/health && echo "✅ Hi-RAG v2 online"

# Step 5: Agent coordination services
echo "🤖 Phase 5: Deploying agent services..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  agent-zero archon mesh-agent

sleep 10
curl -s http://localhost:8080/healthz && echo "✅ Agent Zero online"
curl -s http://localhost:8091/healthz && echo "✅ Archon online"

# Step 6: Orchestration and research services
echo "🔬 Phase 6: Deploying orchestration..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  supaserch deepresearch

sleep 10
curl -s http://localhost:8099/metrics && echo "✅ SupaSerch online"

# Step 7: Ingestion and integration services
echo "📥 Phase 7: Deploying ingestion services..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d \
  pmoves-yt channel-monitor pdf-ingest notebook-sync \
  publisher-discord jellyfin-bridge

sleep 10

# Step 8: Verify full deployment
echo ""
echo "✅ Rolling deployment complete!"
echo "📊 Final service status:"
docker compose ps
```

**Rolling Update Phases:**
1. **Data Layer** (15s) - Databases and storage
2. **Observability** (10s) - Metrics and logging
3. **Workers** (10s) - Processing services
4. **RAG** (10s) - Search and retrieval
5. **Agents** (10s) - Coordination services
6. **Orchestration** (10s) - Research services
7. **Ingestion** (10s) - Content processing

**Total Rolling Update Time:** ~10-15 minutes

---

## Section 3: Post-Deployment Validation

**Run these checks after ANY deployment method to verify security hardening.**

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# 1. Verify all containers running as UID 65532
echo "🔐 Verifying non-root execution..."
docker compose ps --format json | jq -r '.[].Name' | while read container; do
  echo -n "$container: "
  docker exec "$container" id 2>/dev/null || echo "N/A (not running or no shell)"
done | grep -v "uid=65532" && echo "⚠️  Some containers not running as UID 65532" || echo "✅ All containers running as pmoves user"

# 2. Verify read-only filesystems
echo ""
echo "📁 Verifying read-only root filesystems..."
docker inspect $(docker compose ps -q) --format '{{.Name}}: ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}' | grep "false" && echo "⚠️  Some containers have writable root" || echo "✅ All containers have read-only root"

# 3. Check tmpfs mounts
echo ""
echo "💾 Verifying tmpfs mounts..."
docker inspect $(docker compose ps -q) --format '{{.Name}}: {{.HostConfig.Tmpfs}}' | grep -v "map\[\]" | head -10
echo "..."
echo "(Showing first 10, all services should have tmpfs for /tmp)"

# 4. Test critical service endpoints
echo ""
echo "🏥 Testing service health endpoints..."
curl -f -s http://localhost:8086/health > /dev/null && echo "✅ Hi-RAG v2" || echo "❌ Hi-RAG v2 not responding"
curl -f -s http://localhost:8080/healthz > /dev/null && echo "✅ Agent Zero" || echo "❌ Agent Zero not responding"
curl -f -s http://localhost:3030/health > /dev/null && echo "✅ TensorZero" || echo "❌ TensorZero not responding"
curl -f -s http://localhost:8091/healthz > /dev/null && echo "✅ Archon" || echo "❌ Archon not responding"
curl -f -s http://localhost:8099/metrics > /dev/null && echo "✅ SupaSerch" || echo "❌ SupaSerch not responding"
curl -f -s http://localhost:8077/health > /dev/null && echo "✅ PMOVES.YT" || echo "❌ PMOVES.YT not responding"

# 5. Verify dropped capabilities
echo ""
echo "🔒 Verifying dropped capabilities..."
docker inspect $(docker compose ps -q hi-rag-gateway-v2) --format '{{.HostConfig.CapDrop}}' | grep "ALL" && echo "✅ Capabilities dropped" || echo "⚠️  Capabilities not dropped"

# 6. Check resource limits
echo ""
echo "⚙️  Verifying resource limits..."
docker inspect $(docker compose ps -q) --format '{{.Name}}: Memory={{.HostConfig.Memory}} CPUs={{.HostConfig.NanoCpus}}' | grep -v "Memory=0" | head -5
echo "..."
echo "(Services should have non-zero memory limits)"

# 7. Run full validation script
echo ""
echo "🧪 Running comprehensive validation..."
./scripts/validate-phase1-hardening.sh

# 8. Check for any restarting containers
echo ""
echo "🔄 Checking for unstable containers..."
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep "restarting" && echo "⚠️  Some containers are restarting" || echo "✅ No containers restarting"

# 9. Verify GPU services (if applicable)
echo ""
echo "🎮 Verifying GPU access (if GPU services running)..."
if docker compose ps | grep -q "gpu"; then
  docker exec $(docker compose ps -q hi-rag-gateway-v2-gpu 2>/dev/null) groups 2>/dev/null | grep "video" && echo "✅ GPU group access configured" || echo "⚠️  GPU group access not detected"
else
  echo "ℹ️  No GPU services running"
fi

# 10. Final summary
echo ""
echo "═══════════════════════════════════════════════════════"
echo "📋 VALIDATION SUMMARY"
echo "═══════════════════════════════════════════════════════"
echo "Total containers: $(docker compose ps | wc -l)"
echo "Running containers: $(docker compose ps --filter status=running | wc -l)"
echo "Health checks passing: $(curl -s http://localhost:8086/health > /dev/null && echo -n "1 " || echo -n "0 ")$(curl -s http://localhost:8080/healthz > /dev/null && echo -n "1 " || echo -n "0 ")$(curl -s http://localhost:3030/health > /dev/null && echo -n "1 " || echo -n "0 ")/ 3 critical services"
echo "Security hardening: Phase 1 (non-root, read-only, capabilities)"
echo "═══════════════════════════════════════════════════════"
```

**✅ Validation Success Criteria:**
- All containers report `uid=65532(pmoves) gid=65532(pmoves)`
- All containers have `ReadonlyRootfs=true`
- Critical health endpoints return HTTP 200
- No containers in "restarting" loop
- Validation script exits 0

**⚠️ If validation fails, proceed to Section 5: Troubleshooting**

---

## Section 4: Rollback Procedure

**Use this procedure if deployment fails or validation errors occur.**

### Emergency Rollback (Fast - 2 minutes)

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# 1. Stop hardened deployment immediately
echo "🛑 EMERGENCY ROLLBACK - Stopping hardened services..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml down

# 2. Restart with standard (non-hardened) configuration
echo "🔄 Restarting with standard configuration..."
docker compose \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# 3. Wait for services to recover
echo "⏳ Waiting 30 seconds for recovery..."
sleep 30

# 4. Verify services recovered
echo "📊 Recovery status:"
docker compose ps

# 5. Test critical endpoints
echo "🏥 Critical service health:"
curl -f -s http://localhost:8086/health && echo "✅ Hi-RAG v2" || echo "❌ Hi-RAG v2"
curl -f -s http://localhost:8080/healthz && echo "✅ Agent Zero" || echo "❌ Agent Zero"
curl -f -s http://localhost:3030/health && echo "✅ TensorZero" || echo "❌ TensorZero"

echo ""
echo "✅ Rollback complete. Services restored to pre-hardening state."
echo "⚠️  Investigate hardening issues before attempting redeployment."
```

### Graceful Rollback (Safer - 5 minutes)

```bash
cd /home/pmoves/PMOVES.AI/pmoves

# 1. Export current container logs for investigation
echo "📝 Exporting logs for investigation..."
mkdir -p /tmp/pmoves-rollback-logs-$(date +%Y%m%d-%H%M%S)
docker compose logs > /tmp/pmoves-rollback-logs-$(date +%Y%m%d-%H%M%S)/all-services.log

# 2. Identify problematic services
echo "🔍 Identifying failing services..."
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -v "running"

# 3. Stop hardened deployment
echo "🛑 Stopping hardened services..."
docker compose -f docker-compose.yml -f docker-compose.hardened.yml down --remove-orphans

# 4. Clean up any dangling volumes (optional, use with caution)
# docker volume prune -f

# 5. Restore from backup configuration
echo "📦 Restoring previous configuration..."
LATEST_BACKUP=$(ls -t /tmp/pmoves-backups/docker-compose-backup-*.yml | head -1)
echo "Using backup: $LATEST_BACKUP"

# 6. Restart with standard configuration
echo "🔄 Restarting services..."
docker compose \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d

# 7. Progressive health check
echo "⏳ Waiting for services to stabilize..."
for i in {1..6}; do
  echo "Check $i/6 (${i}0 seconds)..."
  sleep 10
  RUNNING=$(docker compose ps --filter status=running | wc -l)
  echo "Running services: $RUNNING"
done

# 8. Final verification
echo ""
echo "📊 Final rollback status:"
docker compose ps
echo ""
echo "Logs saved to: /tmp/pmoves-rollback-logs-*/"
echo "Backup config: $LATEST_BACKUP"
```

**Rollback Decision Matrix:**

| Symptom | Rollback Type | Urgency |
|---------|---------------|---------|
| All services down | Emergency | Immediate |
| Critical services failing | Emergency | Immediate |
| 1-2 non-critical services failing | Graceful | Within 5 min |
| Performance degradation | Graceful | Within 15 min |
| Permission errors only | Troubleshoot first | Can defer |

---

## Section 5: Troubleshooting

### Issue 1: Permission Denied Errors

**Symptom:**
```
Error: EACCES: permission denied, open '/app/data/file.json'
```

**Diagnosis:**
```bash
# Check which service is failing
docker compose logs | grep "permission denied"

# Check volume ownership
ls -la /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/
```

**Fix:**
```bash
# Fix Agent Zero volume ownership
sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/memory
sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/knowledge

# Fix other service volumes (if needed)
sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/qdrant
sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/neo4j

# Verify ownership
ls -ln /home/pmoves/PMOVES.AI/pmoves/data/agent-zero/
# Should show: 65532 65532

# Restart affected service
docker compose restart agent-zero
```

**Prevention:**
- Run `scripts/validate-phase1-hardening.sh` before deployment
- Document any custom volume mounts that need ownership fixes

---

### Issue 2: Container Fails to Write to /tmp

**Symptom:**
```
Error: EROFS: read-only file system, write '/tmp/cache.db'
```

**Diagnosis:**
```bash
# Check if tmpfs mount exists
SERVICE_NAME="hi-rag-gateway-v2"
docker inspect pmoves-${SERVICE_NAME}-1 --format '{{.HostConfig.Tmpfs}}'
# Expected: map[/tmp:rw,size=100M]
```

**Fix:**
```bash
# Verify docker-compose.hardened.yml has tmpfs for service
grep -A 5 "^  ${SERVICE_NAME}:" docker-compose.hardened.yml | grep tmpfs

# If missing, add to docker-compose.hardened.yml:
#   hi-rag-gateway-v2:
#     tmpfs:
#       - /tmp:rw,size=100M

# Redeploy service
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d ${SERVICE_NAME}
```

**Prevention:**
- All services that write to `/tmp` must have tmpfs mount
- Default size: 100M (adjust per service needs)
- Monitor tmpfs usage: `docker exec <container> df -h /tmp`

---

### Issue 3: GPU Services Fail

**Symptom:**
```
Error: Could not initialize CUDA
RuntimeError: No CUDA GPUs are available
```

**Diagnosis:**
```bash
# Check GPU service group membership
docker exec pmoves-hi-rag-gateway-v2-gpu-1 groups
# Expected: pmoves video

# Check if video group GID matches host
getent group video
# Host GID should match container GID (typically 44)
```

**Fix:**
```bash
# Verify docker-compose.hardened.yml has video group
grep -A 10 "hi-rag-gateway-v2-gpu:" docker-compose.hardened.yml | grep group_add

# Should show:
#   group_add:
#     - video

# If missing, add and redeploy:
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d hi-rag-gateway-v2-gpu

# Test GPU access
docker exec pmoves-hi-rag-gateway-v2-gpu-1 nvidia-smi
```

**Prevention:**
- GPU services MUST have `group_add: [video]` in hardened config
- Verify host has `video` group: `getent group video`
- Test GPU access before full deployment

---

### Issue 4: Service Keeps Restarting

**Symptom:**
```
docker compose ps shows "Restarting (1) 10 seconds ago"
```

**Diagnosis:**
```bash
# Check restart loop logs
SERVICE_NAME="extract-worker"
docker compose logs ${SERVICE_NAME} --tail=100

# Check container exit code
docker inspect pmoves-${SERVICE_NAME}-1 --format '{{.State.ExitCode}}'

# Common exit codes:
# 1   - General application error
# 126 - Permission denied (likely filesystem issue)
# 137 - OOM killed (memory limit too low)
# 139 - Segmentation fault
```

**Fix:**

**If Exit Code 126 (Permission):**
```bash
# Check volume ownership
ls -la /home/pmoves/PMOVES.AI/pmoves/data/${SERVICE_NAME}/
sudo chown -R 65532:65532 /home/pmoves/PMOVES.AI/pmoves/data/${SERVICE_NAME}/
```

**If Exit Code 137 (OOM):**
```bash
# Check memory limit
docker inspect pmoves-${SERVICE_NAME}-1 --format '{{.HostConfig.Memory}}'

# Increase memory limit in docker-compose.hardened.yml:
#   extract-worker:
#     deploy:
#       resources:
#         limits:
#           memory: 2G  # Increased from 1G

# Redeploy
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d ${SERVICE_NAME}
```

**If General Error (Exit Code 1):**
```bash
# Review logs for specific error
docker compose logs ${SERVICE_NAME} --tail=200 | grep -i error

# Common issues:
# - Missing environment variables
# - Database connection failures (check depends_on)
# - Missing tmpfs mount for /tmp writes
```

**Prevention:**
- Always check logs immediately after deployment
- Set appropriate memory limits (monitor with `docker stats`)
- Ensure all dependencies started before dependent services

---

### Issue 5: Service Health Check Fails

**Symptom:**
```
curl http://localhost:8086/health
curl: (7) Failed to connect to localhost port 8086: Connection refused
```

**Diagnosis:**
```bash
# Check if container is running
docker compose ps hi-rag-gateway-v2

# Check if port is exposed
docker port pmoves-hi-rag-gateway-v2-1

# Check if service is listening
docker exec pmoves-hi-rag-gateway-v2-1 netstat -tulpn | grep 8086

# Check firewall/port conflicts
sudo ss -tulpn | grep 8086
```

**Fix:**

**If Container Not Running:**
```bash
docker compose logs hi-rag-gateway-v2 --tail=50
# Fix based on error (see Issue 4)
```

**If Port Not Exposed:**
```bash
# Verify docker-compose.yml has port mapping:
grep -A 5 "hi-rag-gateway-v2:" docker-compose.yml | grep ports
# Should show: - "8086:8086"
```

**If Service Not Listening:**
```bash
# Check application logs for startup errors
docker compose logs hi-rag-gateway-v2 | grep -i "listening\|started\|error"

# Verify environment variables
docker exec pmoves-hi-rag-gateway-v2-1 env | grep PORT
```

**Prevention:**
- Use `depends_on` for service dependencies
- Add startup delays for slow-starting services
- Monitor startup logs: `docker compose logs -f`

---

### Issue 6: Orphaned Containers or Volumes

**Symptom:**
```
Warning: orphan containers found
Error: volume already in use
```

**Diagnosis:**
```bash
# List orphaned containers
docker ps -a --filter "status=exited"

# List all volumes
docker volume ls

# Find unused volumes
docker volume ls -qf dangling=true
```

**Fix:**
```bash
# Remove orphaned containers
docker compose down --remove-orphans

# Clean up stopped containers (CAUTION)
docker container prune -f

# Remove unused volumes (CAUTION - verify before running)
docker volume ls -qf dangling=true
# If safe to remove:
docker volume prune -f

# Nuclear option (DANGER - removes all unused Docker objects)
# docker system prune -a --volumes -f
```

**Prevention:**
- Always use `docker compose down` instead of `docker stop`
- Use `--remove-orphans` flag when switching compose files
- Regularly audit volumes: `docker volume ls`

---

### Issue 7: High Memory Usage

**Symptom:**
```
Host system running out of memory
docker stats shows services near limits
```

**Diagnosis:**
```bash
# Monitor real-time usage
docker stats --no-stream

# Check specific service
docker stats pmoves-hi-rag-gateway-v2-1 --no-stream

# Check host memory
free -h
```

**Fix:**

**Reduce Memory Limits (Temporary):**
```bash
# Edit docker-compose.hardened.yml
# Reduce memory limits for non-critical services:
#   publisher-discord:
#     deploy:
#       resources:
#         limits:
#           memory: 256M  # Reduced from 512M

# Redeploy
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d
```

**Scale Down Services (Emergency):**
```bash
# Stop non-critical services
docker compose stop publisher-discord jellyfin-bridge channel-monitor

# Verify memory freed
free -h
```

**Prevention:**
- Set realistic memory limits based on monitoring
- Use profiles to load only needed services
- Monitor with Prometheus/Grafana
- Consider increasing host RAM for production

---

## Section 6: Monitoring

### Real-Time Monitoring

```bash
# Watch all service logs (live tail)
docker compose logs -f --tail=100

# Watch specific services
docker compose logs -f agent-zero hi-rag-gateway-v2 tensorzero

# Filter for errors
docker compose logs -f | grep -i error

# Monitor resource usage (live updates)
docker stats

# Monitor specific service resources
docker stats pmoves-hi-rag-gateway-v2-1 pmoves-agent-zero-1 pmoves-tensorzero-1

# Monitor container restart counts
watch -n 5 'docker compose ps --format "table {{.Name}}\t{{.Status}}"'
```

### Prometheus Queries

```bash
# Check all services are up
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq '.data.result[] | select(.value[1]=="0")'

# Query service-specific metrics
curl -s 'http://localhost:9090/api/v1/query?query=hirag_requests_total' | jq '.'

# Check memory usage across services
curl -s 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes' | jq '.'

# Check container restart counts
curl -s 'http://localhost:9090/api/v1/query?query=container_restarts_total' | jq '.'
```

### Grafana Dashboards

```bash
# Access Grafana UI
firefox http://localhost:3000

# Default credentials:
# Username: admin
# Password: admin (change on first login)

# Pre-configured dashboards:
# - Services Overview (all service metrics)
# - Container Metrics (resource usage)
# - NATS Monitoring (message bus stats)
```

### Log Aggregation (Loki)

```bash
# Query logs via Loki API
curl -s 'http://localhost:3100/loki/api/v1/query_range?query={container_name="pmoves-agent-zero-1"}' | jq '.'

# Query error logs across all services
curl -s 'http://localhost:3100/loki/api/v1/query_range?query={job="docker"} |= "error"' | jq '.'

# Access Loki via Grafana Explore
firefox http://localhost:3000/explore
```

### Health Monitoring Script

```bash
# Create monitoring script for continuous health checks
cat > /tmp/pmoves-health-monitor.sh <<'EOF'
#!/bin/bash
while true; do
  clear
  echo "=== PMOVES.AI Health Monitor ==="
  echo "Time: $(date)"
  echo ""

  echo "Critical Services:"
  curl -f -s http://localhost:8086/health && echo "✅ Hi-RAG v2" || echo "❌ Hi-RAG v2"
  curl -f -s http://localhost:8080/healthz && echo "✅ Agent Zero" || echo "❌ Agent Zero"
  curl -f -s http://localhost:3030/health && echo "✅ TensorZero" || echo "✅ TensorZero"

  echo ""
  echo "Container Status:"
  docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -v "Up" || echo "All containers running"

  echo ""
  echo "Resource Usage (Top 5):"
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -6

  sleep 10
done
EOF

chmod +x /tmp/pmoves-health-monitor.sh
/tmp/pmoves-health-monitor.sh
```

### Alerting

**Set up basic alerting via Prometheus:**

```bash
# Edit Prometheus alerting rules
# /home/pmoves/PMOVES.AI/pmoves/monitoring/prometheus/alerts.yml

# Example alert rule:
# - alert: ServiceDown
#   expr: up == 0
#   for: 2m
#   labels:
#     severity: critical
#   annotations:
#     summary: "Service {{ $labels.job }} is down"
```

**Monitor via systemd (if running as service):**

```bash
# If PMOVES.AI is running as systemd service
journalctl -u pmoves -f
systemctl status pmoves
```

---

## Section 7: Best Practices

### Pre-Deployment Checklist

- [ ] Run all pre-flight checks successfully
- [ ] Backup current configuration (`docker compose config`)
- [ ] Backup critical data volumes
- [ ] Review recent commits for breaking changes
- [ ] Verify no active migrations or critical tasks
- [ ] Schedule deployment during low-traffic window
- [ ] Notify team of deployment window
- [ ] Have rollback procedure ready

### During Deployment

- [ ] Use canary deployment for production
- [ ] Monitor logs in real-time (`docker compose logs -f`)
- [ ] Watch resource usage (`docker stats`)
- [ ] Test health endpoints after each phase
- [ ] Document any unexpected behavior
- [ ] Keep rollback commands ready

### Post-Deployment

- [ ] Run full validation script
- [ ] Verify all services healthy
- [ ] Check Grafana dashboards
- [ ] Review error logs in Loki
- [ ] Monitor for 30 minutes after deployment
- [ ] Document any issues encountered
- [ ] Update runbook with lessons learned
- [ ] Notify team of successful deployment

### Security Verification

After deployment, verify Phase 1 hardening is active:

```bash
# Quick security audit
cd /home/pmoves/PMOVES.AI/pmoves

echo "Security Audit for Phase 1 Hardening"
echo "====================================="

# 1. Non-root execution
echo "1. Checking non-root execution..."
docker compose ps -q | xargs -I {} docker exec {} id 2>/dev/null | grep "uid=65532" | wc -l
echo "   Services running as UID 65532: $(docker compose ps -q | xargs -I {} docker exec {} id 2>/dev/null | grep "uid=65532" | wc -l)"

# 2. Read-only filesystems
echo "2. Checking read-only root filesystems..."
docker inspect $(docker compose ps -q) --format '{{.HostConfig.ReadonlyRootfs}}' | grep "true" | wc -l
echo "   Services with read-only root: $(docker inspect $(docker compose ps -q) --format '{{.HostConfig.ReadonlyRootfs}}' | grep 'true' | wc -l)"

# 3. Dropped capabilities
echo "3. Checking dropped capabilities..."
docker inspect $(docker compose ps -q) --format '{{.HostConfig.CapDrop}}' | grep "ALL" | wc -l
echo "   Services with ALL capabilities dropped: $(docker inspect $(docker compose ps -q) --format '{{.HostConfig.CapDrop}}' | grep 'ALL' | wc -l)"

# 4. Resource limits
echo "4. Checking resource limits..."
docker inspect $(docker compose ps -q) --format '{{.HostConfig.Memory}}' | grep -v "^0$" | wc -l
echo "   Services with memory limits: $(docker inspect $(docker compose ps -q) --format '{{.HostConfig.Memory}}' | grep -v '^0$' | wc -l)"

echo ""
echo "✅ Security audit complete"
```

---

## Section 8: Reference

### Key Files

| File | Purpose | Location |
|------|---------|----------|
| `docker-compose.yml` | Base configuration | `/home/pmoves/PMOVES.AI/pmoves/` |
| `docker-compose.hardened.yml` | Security overlay | `/home/pmoves/PMOVES.AI/pmoves/` |
| `validate-phase1-hardening.sh` | Validation script | `/home/pmoves/PMOVES.AI/pmoves/scripts/` |
| `phase1-hardening-summary.md` | Implementation docs | `/home/pmoves/PMOVES.AI/docs/` |

### Service Ports (Quick Reference)

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| Hi-RAG v2 | 8086 | `GET /health` |
| Agent Zero | 8080 | `GET /healthz` |
| TensorZero | 3030 | `GET /health` |
| Archon | 8091 | `GET /healthz` |
| SupaSerch | 8099 | `GET /metrics` |
| PMOVES.YT | 8077 | `GET /health` |
| Prometheus | 9090 | `GET /-/healthy` |
| Grafana | 3000 | `GET /api/health` |

### Docker Compose Profiles

| Profile | Services Included |
|---------|-------------------|
| `data` | qdrant, neo4j, meilisearch, minio, nats |
| `workers` | extract-worker, langextract, media processors |
| `orchestration` | supaserch, deepresearch |
| `agents` | agent-zero, archon, mesh-agent |
| `tensorzero` | tensorzero, tensorzero-clickhouse, tensorzero-ui |

### Common Commands

```bash
# View running services
docker compose ps

# View all services (including stopped)
docker compose ps --all

# Restart specific service
docker compose restart <service-name>

# View logs
docker compose logs <service-name> --tail=100

# Follow logs
docker compose logs -f <service-name>

# Execute command in container
docker exec -it pmoves-<service>-1 <command>

# Check resource usage
docker stats

# Prune unused resources
docker system prune -f
```

### Environment Variables

Key environment variables for hardened deployment:

```bash
# User/Group IDs (must match across all services)
PUID=65532
PGID=65532

# GPU access (if using GPU services)
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### Support Resources

- **Phase 1 Implementation Docs:** `/home/pmoves/PMOVES.AI/docs/phase1-hardening-summary.md`
- **Validation Script:** `/home/pmoves/PMOVES.AI/pmoves/scripts/validate-phase1-hardening.sh`
- **Docker Compose Docs:** https://docs.docker.com/compose/
- **Docker Security Best Practices:** https://docs.docker.com/engine/security/

---

## Section 9: Deployment Timeline

### Canary Deployment Timeline

| Time | Phase | Action | Expected Result |
|------|-------|--------|-----------------|
| T+0 | Pre-flight | Run all checks | All ✅ |
| T+1 | Canary Deploy | Deploy presign | Container starts |
| T+2 | Canary Validate | Check UID, read-only, health | All pass |
| T+3 | Full Deploy | Deploy all services | All start |
| T+4 | Stabilization | Wait for services | Containers running |
| T+5 | Validation | Run post-deployment checks | All ✅ |
| T+6 | Monitoring | Watch for errors | No errors |
| **Total** | **~6 minutes** | | |

### Full Stack Deployment Timeline

| Time | Phase | Action | Expected Result |
|------|-------|--------|-----------------|
| T+0 | Pre-flight | Run all checks | All ✅ |
| T+1 | Shutdown | Stop all services | Clean shutdown |
| T+2 | Deploy | Start hardened stack | All start |
| T+3 | Stabilization | Wait for services | Containers running |
| T+4 | Validation | Run post-deployment checks | All ✅ |
| **Total** | **~4 minutes** | | |

### Rolling Update Timeline

| Time | Phase | Services | Expected Result |
|------|-------|----------|-----------------|
| T+0 | Pre-flight | N/A | All ✅ |
| T+1 | Data Layer | qdrant, neo4j, meilisearch, minio, nats | All start |
| T+2 | Observability | tensorzero, prometheus, grafana | All start |
| T+3 | Workers | extract-worker, langextract, presign | All start |
| T+5 | RAG | hi-rag-gateway-v2 | Health ✅ |
| T+7 | Agents | agent-zero, archon | Health ✅ |
| T+9 | Orchestration | supaserch, deepresearch | All start |
| T+11 | Ingestion | pmoves-yt, channel-monitor | All start |
| T+13 | Validation | Full post-deployment checks | All ✅ |
| **Total** | **~13 minutes** | | |

---

## Appendix A: Emergency Contacts

**Deployment Lead:** [Your Name]
**Infrastructure Team:** [Team Contact]
**On-Call Engineer:** [On-Call Contact]

**Escalation Path:**
1. Check this runbook for troubleshooting steps
2. Review logs in Loki/Grafana
3. Attempt rollback if critical services down
4. Contact infrastructure team if rollback fails
5. Escalate to on-call engineer for system-level issues

---

## Appendix B: Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-12-06 | 1.0 | Initial runbook for Phase 1 hardening | Claude Sonnet 4.5 |

---

## Appendix C: Phase 2 & 3 Preview

**Phase 2: Network Segmentation** (Planned)
- Service-specific bridge networks
- Network policies for inter-service communication
- Ingress/egress traffic controls

**Phase 3: Secrets Management** (Planned)
- Docker secrets for sensitive data
- Vault integration for dynamic secrets
- Encrypted environment variables

**Stay tuned for Phase 2 runbook after Phase 1 deployment success!**

---

**End of Runbook**

For questions or issues not covered in this runbook, refer to:
- `/home/pmoves/PMOVES.AI/docs/phase1-hardening-summary.md`
- `.claude/context/services-catalog.md`
- Docker Compose documentation

**Happy Hardening!** 🔒
