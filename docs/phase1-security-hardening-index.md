# Phase 1 Security Hardening - Documentation Index

**PMOVES.AI Production Security Hardening - Phase 1**

**Status**: ✅ Ready for Deployment
**Completion Date**: 2025-12-06
**Version**: 1.0.0

---

## Quick Links

- **Deployment Guide** (Main Reference): [`phase1-deployment-guide.md`](./phase1-deployment-guide.md)
- **Quick Reference** (Command Cheatsheet): [`phase1-deployment-quickref.md`](./phase1-deployment-quickref.md)
- **Completion Summary**: [`phase1-completion-summary.md`](./phase1-completion-summary.md)
- **Validation Script**: [`../pmoves/scripts/validate-phase1-hardening.sh`](../pmoves/scripts/validate-phase1-hardening.sh)

---

## What is Phase 1?

Phase 1 implements **foundational container security controls** across all PMOVES.AI services:

### Security Controls Implemented

1. **Non-Root User Execution** (29 services)
   - All custom services run as UID/GID 65532:65532 (`pmoves:pmoves`)
   - Dockerfiles modified with `USER pmoves:pmoves` directive
   - Prevents privilege escalation attacks

2. **Read-Only Root Filesystems** (30 services)
   - Prevents runtime filesystem modification
   - Protects against persistence of malicious changes
   - Configured via `read_only: true` in docker-compose.hardened.yml

3. **Tmpfs Mounts for Writable Paths** (30 services)
   - `/tmp` - temporary file storage (500M-10G depending on workload)
   - `/home/pmoves/.cache` - application cache (50M-10G depending on workload)
   - Specialized paths for GPU services (HuggingFace cache, PyTorch cache, /dev/shm)

4. **Capability Drops** (30 services)
   - `cap_drop: ["ALL"]` - removes all Linux capabilities
   - Minimizes attack surface
   - Services run with minimal privileges

5. **Security Options** (30 services)
   - `no-new-privileges:true` - prevents privilege escalation via setuid
   - Hardens container runtime

### Services Covered

**Custom PMOVES Services** (29 services):
- Agent coordination: agent-zero, archon, mesh-agent
- Knowledge services: hi-rag-gateway-v2, hi-rag-gateway-v2-gpu, hi-rag-gateway-gpu
- Media processing: ffmpeg-whisper, media-video, media-audio
- Workers: extract-worker, langextract, pdf-ingest, notebook-sync
- Research: deepresearch, supaserch
- Monitoring: publisher-discord, nats-echo-req, nats-echo-res, publisher, analysis-echo
- Utilities: presign, render-webhook, retrieval-eval, jellyfin-bridge
- Ingestion: pmoves-yt, channel-monitor
- Bridges: invidious-companion-proxy, graph-linker, comfy-watcher, grayjay-plugin-host

**Third-Party Services** (managed in docker-compose.yml):
- Data stores: postgres, qdrant, meilisearch, neo4j, minio
- Infrastructure: nats, postgrest, tensorzero-gateway, tensorzero-clickhouse, pmoves-ollama
- Optional: invidious, cloudflared, bgutil-pot-provider

---

## Documentation Guide

### For Deployment Engineers

**Start here**: [`phase1-deployment-guide.md`](./phase1-deployment-guide.md)

Complete step-by-step guide covering:
- Pre-deployment checklist
- Canary deployment (test one service first)
- Full deployment for Docker Compose
- Kubernetes deployment procedures
- Validation commands
- Rollback procedures
- Troubleshooting guide
- Performance impact assessment

**Quick commands**: [`phase1-deployment-quickref.md`](./phase1-deployment-quickref.md)

One-page command reference for:
- Pre-deployment checks
- Deployment commands
- Validation commands
- Rollback commands
- Troubleshooting shortcuts

### For Security Auditors

**Start here**: [`phase1-completion-summary.md`](./phase1-completion-summary.md)

Detailed technical summary including:
- Security controls matrix
- Service-by-service configuration details
- Tmpfs sizing rationale
- GPU service special considerations
- Compliance verification steps

### For Operations Teams

**Start here**: [`phase1-deployment-quickref.md`](./phase1-deployment-quickref.md)

Quick reference for day-to-day operations:
- Health check commands
- Common troubleshooting
- Monitoring queries
- Rollback procedures

---

## Deployment Workflow

### Pre-Deployment

1. **Run validation script**:
   ```bash
   cd /home/pmoves/PMOVES.AI/pmoves
   ./scripts/validate-phase1-hardening.sh
   ```

2. **Review checklist** in deployment guide

3. **Backup current state**:
   ```bash
   docker compose ps > deployment-backup-$(date +%Y%m%d-%H%M%S).txt
   ```

### Canary Deployment

Test with one service first (presign recommended):

```bash
cd /home/pmoves/PMOVES.AI/pmoves
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d presign
docker compose logs presign --tail 50
curl http://localhost:8088/health
```

### Full Deployment

Deploy all services:

```bash
cd /home/pmoves/PMOVES.AI/pmoves
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  --profile data \
  --profile workers \
  --profile orchestration \
  --profile agents \
  --profile tensorzero \
  up -d
```

### Post-Deployment

Validate deployment:

```bash
# Run validation script
./scripts/validate-phase1-hardening.sh

# Check service endpoints
curl -f http://localhost:8080/healthz  # Agent Zero
curl -f http://localhost:8091/healthz  # Archon
curl -f http://localhost:8086/health   # Hi-RAG v2
```

---

## File Locations

### Configuration Files

- **Hardened Overlay**: `/home/pmoves/PMOVES.AI/pmoves/docker-compose.hardened.yml`
- **Base Compose**: `/home/pmoves/PMOVES.AI/pmoves/docker-compose.yml`
- **Service Dockerfiles**: `/home/pmoves/PMOVES.AI/pmoves/services/*/Dockerfile`

### Kubernetes

- **Base Manifests**: `/home/pmoves/PMOVES.AI/deploy/k8s/base/`
- **Overlays**: `/home/pmoves/PMOVES.AI/deploy/k8s/{local,ai-lab,kvm4}/`
- **SecurityContext Template**: `/home/pmoves/PMOVES.AI/deploy/k8s/base/pmoves-core-deployment.yaml`

### Scripts

- **Validation**: `/home/pmoves/PMOVES.AI/pmoves/scripts/validate-phase1-hardening.sh`

### Documentation

- **Deployment Guide**: `/home/pmoves/PMOVES.AI/docs/phase1-deployment-guide.md`
- **Quick Reference**: `/home/pmoves/PMOVES.AI/docs/phase1-deployment-quickref.md`
- **Completion Summary**: `/home/pmoves/PMOVES.AI/docs/phase1-completion-summary.md`
- **This Index**: `/home/pmoves/PMOVES.AI/docs/phase1-security-hardening-index.md`

---

## Rollback Plan

If issues occur:

```bash
# Stop hardened deployment
cd /home/pmoves/PMOVES.AI/pmoves
docker compose -f docker-compose.yml -f docker-compose.hardened.yml down

# Restart without hardening
docker compose up -d

# Verify
docker compose ps
```

See full rollback procedures in the [deployment guide](./phase1-deployment-guide.md#rollback-procedures).

---

## Success Criteria

Phase 1 deployment is considered successful when:

- [ ] All services start and pass health checks
- [ ] No permission errors in logs
- [ ] All endpoints responding correctly
- [ ] Containers running as UID 65532 (custom services)
- [ ] Read-only root filesystems active
- [ ] Tmpfs mounts present and writable
- [ ] Service functionality unchanged (functional testing passes)
- [ ] Performance within expected variance (±5%)

---

## Known Limitations (Expected)

These are known and acceptable in Phase 1:

1. **Third-party services**: Run with upstream defaults (postgres, qdrant, etc.)
2. **Agent Zero volumes**: Require manual ownership fix before first run
3. **GPU services**: Need video group access (already configured in Dockerfiles)
4. **Memory usage**: Slight increase due to tmpfs (within configured limits)

These will be addressed in future phases as appropriate.

---

## Next Steps (Future Phases)

After successful Phase 1 deployment:

- **Phase 2**: Secret management (Docker Secrets, Kubernetes Secrets)
- **Phase 3**: Network policies and egress controls
- **Phase 4**: Resource limits and quotas
- **Phase 5**: Runtime security monitoring (Falco, AppArmor/SELinux)

---

## Support

For issues during deployment:

1. Check service logs: `docker compose logs <service-name>`
2. Run validation script: `./scripts/validate-phase1-hardening.sh`
3. Review troubleshooting guide in deployment documentation
4. Check monitoring dashboards (Grafana: http://localhost:3000)

---

## Compliance Notes

Phase 1 security controls align with:

- **CIS Docker Benchmark**: Section 5 (Container Runtime)
  - 5.1: Verify AppArmor/SELinux (future phase)
  - 5.2: Verify container user (✅ implemented)
  - 5.12: Ensure root filesystem is read-only (✅ implemented)
  - 5.25: Restrict container from acquiring additional privileges (✅ implemented)

- **NIST SP 800-190**: Container Security Guide
  - Image and registry security (✅ non-root user)
  - Runtime security (✅ read-only, capabilities drop)
  - Host security (future phase)

- **Kubernetes Pod Security Standards**: Restricted profile
  - runAsNonRoot (✅ implemented)
  - readOnlyRootFilesystem (✅ implemented)
  - allowPrivilegeEscalation: false (✅ implemented)
  - capabilities.drop: ALL (✅ implemented)

---

**Phase 1 Security Hardening**
**PMOVES.AI Production Deployment**
**Version 1.0.0 - 2025-12-06**
