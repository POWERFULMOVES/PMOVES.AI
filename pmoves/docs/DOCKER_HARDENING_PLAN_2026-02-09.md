# Docker Hardening Plan - Post-Merge Priority

**Date:** 2026-02-09
**Priority:** HIGH (Production Readiness)
**Status:** 🟡 **IN PROGRESS**

---

## Executive Summary

Following PR #606 merge, Docker hardening is required across all submodule images before production deployment. The GHCR workflow has been triggered to test builds, but immediate action is needed on Dockerfile security and best practices.

---

## Current Status

### GHCR Workflow
- ✅ Workflow triggered: `integrations-ghcr.yml` (Run #21811059081)
- ⏳ Status: In Progress
- 🎯 Target: Build agent-zero image as test

### Multi-Architecture Support
- ✅ Workflow updated to include `PMOVES.AI-Edition-Hardened` branch
- ✅ All images now configured for `linux/amd64,linux/arm64`

---

## Docker Hardening Requirements

### Priority 1: Security (Critical)

| Issue | Risk | Services Affected | Fix Priority |
|-------|------|-------------------|--------------|
| Runs as root | Container escape | PMOVES-Agent-Zero | HIGH |
| Unpinned base images | Supply chain | Most services | HIGH |
| No health checks | Orchestration | All services | MEDIUM |

### Priority 2: Operational (Medium)

| Issue | Impact | Services Affected | Fix Priority |
|-------|--------|-------------------|--------------|
| No STOPSIGNAL | Graceful shutdown | All services | MEDIUM |
| No multi-stage builds | Image size | All services | LOW |
| No layer caching | Build speed | All services | LOW |

---

## Service-by-Service Assessment

### PMOVES-Agent-Zero (HIGH PRIORITY)

**Current Issues:**
1. ❌ Runs as root (no USER directive)
2. ❌ Base image not pinned (`agent0ai/agent-zero-base:latest`)
3. ❌ No health check
4. ❌ No STOPSIGNAL
5. ❌ No multi-stage build

**Hardening Plan:**
```dockerfile
# 1. Pin base image with digest
FROM agent0ai/agent-zero-base:latest@sha256:ABC123...
# OR use official Python base
FROM python:3.12.1-slim@sha256:XYZ789...

# 2. Add non-root user (before COPY commands)
RUN groupadd -r agent --gid=65532 && \
    useradd -r -g agent --uid=65532 --home-dir /agent --shell=/sbin/nologin agent

# 3. Set permissions for directories
RUN chown -R agent:agent /agent /git /exe /ins

# 4. Switch to non-root user
USER agent:agent

# 5. Add health check (if service exposes HTTP)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/healthz || exit 1

# 6. Add signal handling
STOPSIGNAL SIGTERM

# 7. Copy files as non-root or with correct ownership
COPY --chown=agent:agent ./docker/run/fs/ /
```

**Implementation Location:** PMOVES-Agent-Zero/DockerfileLocal
**Branch:** `PMOVES.AI-Edition-Hardened`

---

### PMOVES-Archon (MEDIUM PRIORITY)

**Current State:**
- ✅ Non-root user (pmoves:pmoves)
- ❌ Base image not pinned (`python:3.12-slim`)
- ❌ No health check
- ❌ No STOPSIGNAL
- ❌ No multi-stage build

**Quick Wins:**
```dockerfile
# Pin base image
FROM python:3.12.1-slim@sha256:...

# Add health check (Archon exposes port 8091)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8091/healthz || exit 1

# Add signal handling
STOPSIGNAL SIGTERM
```

---

### PMOVES.YT (MEDIUM PRIORITY)

**Current State:**
- ✅ Non-root user (pmoves:pmoves)
- ⚠️ Base image partially pinned (`python:3.11-slim` - no digest)
- ❌ No health check (port 8077)
- ❌ No STOPSIGNAL
- ❌ No multi-stage build

**Quick Wins:**
```dockerfile
# Pin base image
FROM python:3.11.9-slim@sha256:...

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8077/healthz || exit 1

# Add signal handling
STOPSIGNAL SIGTERM
```

---

### PMOVES-Open-Notebook (TO BE ASSESSED)

**Status:** TBD - Need to review Dockerfile
**Branch:** `PMOVES.AI-Edition-Hardened`

---

## Multi-Stage Build Strategy

### Before (Single Stage)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

### After (Multi-Stage)
```dockerfile
FROM python:3.12.1-slim@sha256:... AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.12.1-slim@sha256:...
WORKDIR /app
RUN groupadd -r app --gid=65532 && useradd -r -g app --uid=65532 app
COPY --from=builder --chown=app:app /root/.local /root/.local
COPY --chown=app:app . .
USER app
HEALTHCHECK CMD curl -f http://localhost:8080/healthz || exit 1
STOPSIGNAL SIGTERM
CMD ["python", "app.py"]
```

**Benefits:**
- Smaller final image (no build tools)
- Clearer separation of concerns
- Better layer caching

---

## Health Check Standards

All PMOVES.AI services should expose a `/healthz` endpoint that:
1. Returns 200 OK when healthy
2. Returns 503 Service Unavailable when unhealthy
3. Checks critical dependencies (database, NATS, etc.)
4. Responds within 5 seconds

**Implementation Example (FastAPI):**
```python
@app.get("/healthz")
async def healthz():
    """Health check endpoint for container orchestration."""
    try:
        # Check database connection
        await db.execute("SELECT 1")
        
        # Check NATS connection
        await nc.publish("health.check", b"ping")
        
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

---

## Implementation Sequence

### Phase 1: Immediate (Today)
1. ✅ Trigger GHCR workflow (DONE - Run #21811059081)
2. 🔄 Monitor agent-zero build
3. 📝 Create hardening PRs for each submodule

### Phase 2: This Week
4. PMOVES-Agent-Zero hardening PR
5. PMOVES-Archon hardening PR
6. PMOVES.YT hardening PR
7. Test all images with GHCR workflow

### Phase 3: Before Production
8. Verify all images pass Trivy scans
9. Verify all images have Cosign signatures
10. Verify SBOMs are generated
11. Run smoke tests with hardened images

---

## Testing Procedure

After hardening, each image should be tested:

```bash
# 1. Build image locally
docker build -t pmoves-agent-zero:test .

# 2. Run container
docker run -d --name agent-test -p 8080:80 pmoves-agent-zero:test

# 3. Check health
docker exec agent-test curl http://localhost/healthz

# 4. Check user (should not be root)
docker exec agent-test whoami  # Should return "agent" or "pmoves", not "root"

# 5. Check image size
docker images pmoves-agent-zero:test

# 6. Scan with Trivy
docker scan pmoves-agent-zero:test
```

---

## Success Criteria

An image is production-ready when:
- [ ] Builds successfully on both amd64 and arm64
- [ ] Runs as non-root user
- [ ] Base image is pinned with digest
- [ ] Health check returns 200 OK
- [ ] Trivy scan shows no HIGH/CRITICAL vulnerabilities (with fixes)
- [ ] Image is signed with Cosign
- [ ] SBOM is generated
- [ ] Image size is reasonable (< 2GB for most services)

---

## Related Tasks

- #58: Test GHCR workflow with manual dispatch
- #59: Docker hardening for PMOVES-Agent-Zero
- #60: GHCR build monitoring and troubleshooting

---

**Next Update:** After agent-zero build completes
**Owner:** Infrastructure Team
