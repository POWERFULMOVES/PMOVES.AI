> **Superseded by [Production Audit Dashboard](PRODUCTION_AUDIT_DASHBOARD.md)** — This document is retained for historical reference.

# Docker & GHCR Implementation Review

**Date:** 2026-02-08
**Scope:** GHCR build failures, Dockerfile review, multi-arch strategy
**Status:** 🟡 **IN PROGRESS**

---

## Executive Summary

The `integrations-ghcr.yml` workflow has failed 5 consecutive times. Initial analysis reveals:

1. **Workflow only triggers on `main` branch** - PR #606 is on `pr/ci-self-hosted-migration`
2. **Single-arch only** - Most images are `linux/amd64` only (some have arm64)
3. **Secret dependency** - Requires `GH_PAT_PUBLISH` with proper scopes
4. **Multi-repo cloning** - Clones from external GitHub repos during build

---

## Critical Issue #1: Workflow Trigger Configuration

**Problem:** Workflow only runs on `main` branch pushes.

```yaml
on:
  push:
    branches: [main]  # ← PR builds don't trigger GHCR
```

**Impact:** Images are NOT built when PRs are merged to `PMOVES.AI-Edition-Hardened`.

**Fix Required:**
```yaml
on:
  push:
    branches: [main, PMOVES.AI-Edition-Hardened]  # ← Add hardened
  pull_request:
    branches: [main, PMOVES.AI-Edition-Hardened]  # ← Add hardened
```

---

## Critical Issue #2: Multi-Architecture Support

**Current State:**

| Image | Platforms |
|-------|-----------|
| agent-zero | linux/amd64 ❌ |
| archon | linux/amd64 ❌ |
| archon-ui | linux/amd64,linux/arm64 ✅ |
| open-notebook | linux/amd64 ❌ |
| wger | linux/amd64,linux/arm64 ✅ |
| firefly-iii | linux/amd64,linux/arm64 ✅ |
| jellyfin | linux/amd64,linux/arm64 ✅ |
| pmoves-yt | linux/amd64,linux/arm64 ✅ |
| deepresearch | linux/amd64 ❌ |
| supaserch | linux/amd64,linux/arm64 ✅ |

**Analysis:**
- 4 out of 10 images lack arm64 support
- Apple Silicon users (M1/M2/M3) can't use these images natively
- Cloudflare runners may have ARM nodes in the future

**Fix Required:**
1. Enable `linux/arm64` for all images
2. Use `docker buildx` for cross-compilation
3. Verify base images support both architectures
4. Test on self-hosted GPU runner (may have ARM)

---

## Critical Issue #3: External Repository Dependencies

**Problem:** Workflow clones external repositories during build.

```yaml
git_url: https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
ref: PMOVES.AI-Edition-Hardened
```

**Risk:**
1. Submodule may not have the `DockerfileLocal` at expected path
2. Branch `PMOVES.AI-Edition-Hardened` may not exist in submodule
3. Clone failures block entire build

**Investigation Required:**
- Verify each submodule has `PMOVES.AI-Edition-Hardened` branch
- Check Dockerfile locations match matrix configuration
- Test clone step for each repository

---

## Submodule Dockerfile Review

### PMOVES-Agent-Zero

**Expected:** `DockerfileLocal` at root
**Branch:** `PMOVES.AI-Edition-Hardened`

**Investigation needed:**
- [ ] Branch exists?
- [ ] DockerfileLocal exists?
- [ ] Multi-stage build?
- [ ] Base image pinned?

### PMOVES-Archon

**Expected:** `pmoves/services/archon/Dockerfile` in main repo
**Note:** Builds from parent PMOVES.AI repo, not submodule

### PMOVES-Open-Notebook

**Expected:** `Dockerfile` at root
**Branch:** `PMOVES.AI-Edition-Hardened`

### PMOVES-Archon (UI)

**Expected:** `archon-ui-main/Dockerfile` in submodule
**Branch:** `PMOVES.AI-Edition-Hardened`
**Platforms:** Already multi-arch ✅

### PMOVES.YT

**Expected:** `pmoves/services/pmoves-yt/Dockerfile` in main repo
**Platforms:** Already multi-arch ✅

---

## Docker Best Practices Checklist

### Required for Production

- [ ] **Base images pinned** (e.g., `python:3.12-slim` → `python:3.12.1-slim`)
- [ ] **Multi-stage builds** (reduce image size)
- [ ] **Non-root user** (security)
- [ ] **Health check** (HEALTHCHECK instruction)
- [ ] **Signal handling** (STOPSIGNAL, graceful shutdown)
- [ ] **Layer caching** (optimize build speed)
- [ ] **Security scanning** (Trivy integrated ✅)

---

## Recommended Multi-Arch Strategy

### Option A: Full Cross-Compilation (Recommended)

```yaml
platforms: linux/amd64,linux/arm64

# Use buildx with QEMU emulation
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3  # ✅ Already in workflow

- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3  # ✅ Already in workflow
```

**Pros:** Single build, both architectures
**Cons:** Slower build (emulation overhead)

### Option B: Native Build Per Architecture

```yaml
strategy:
  matrix:
    platform: [linux/amd64, linux/arm64]
runs-on: ${{ matrix.platform == 'linux/arm64' && 'self-hosted-arm' || 'self-hosted' }}
```

**Pros:** Native builds, faster
**Cons:** Requires ARM runners, double the jobs

---

## Immediate Actions Required

### 1. Fix Workflow Triggers (High Priority)

```yaml
on:
  push:
    branches: [main, PMOVES.AI-Edition-Hardened]  # ← ADD
  pull_request:
    branches: [main, PMOVES.AI-Edition-Hardened]  # ← ADD
```

### 2. Investigate Build Failures (High Priority)

```bash
# Check recent workflow run logs
gh run view 21803132486 --log

# Check for specific error messages
gh api /repos/POWERFULMOVES/PMOVES.AI/actions/runs/21803132486/jobs
```

### 3. Verify Submodule Branches (High Priority)

```bash
# Check if PMOVES.AI-Edition-Hardened exists in submodules
for sub in PMOVES-Agent-Zero PMOVES-Archon PMOVES-Open-Notebook; do
  echo "=== $sub ==="
  cd "$sub" && git branch -a | grep PMOVES.AI-Edition-Hardened || echo "NOT FOUND"
  cd ..
done
```

### 4. Enable Multi-Arch for All Images (Medium Priority)

Update matrix to add `linux/arm64` to all images.

### 5. Verify Base Image Availability (Medium Priority)

Check if all base images support arm64:
- `python:3.12-slim` ✅
- `node:20-alpine` ✅
- Custom bases: ❓ Need verification

---

## Production Docker Configuration Standards

### Base Image Pinning

```dockerfile
# Bad
FROM python:3.12-slim

# Good
FROM python:3.12.1-slim@sha256:abc123...
```

### Multi-Stage Build

```dockerfile
# Builder stage
FROM python:3.12.1-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.12.1-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
CMD ["python", "app.py"]
```

### Non-Root User

```dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

### Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1
```

### Signal Handling

```dockerfile
STOPSIGNAL SIGTERM
```

---

## Runner Strategy for Multi-Arch

### Current Runners

| Runner | Arch | Purpose |
|--------|------|---------|
| vps | amd64 | General CI |
| ai-lab | amd64 | AI/ML workloads |
| gpu | amd64 | GPU builds |

### Recommended Addition

| Runner | Arch | Purpose |
|--------|------|---------|
| arm | arm64 | ARM native builds |
| or | use buildx QEMU emulation |

---

## GHCR Configuration Checklist

- [ ] GHCR enabled for organization
- [ ] `GH_PAT_PUBLISH` secret has `write:packages` scope
- [ ] `GH_PAT_PUBLISH` secret has `read:org` scope (if needed)
- [ ] Workflow has `packages: write` permission ✅
- [ ] Workflow has `contents: read` permission ✅
- [ ] Workflow has `id-token: write` permission ✅

---

## Next Steps

1. **Immediate:** Fix workflow triggers to include `PMOVES.AI-Edition-Hardened`
2. **Immediate:** Run manual workflow dispatch to test one image
3. **Today:** Verify all submodules have required branches
4. **This Week:** Enable arm64 for all images
5. **Ongoing:** Review each Dockerfile against standards

---

**Related Tasks:**
- #54: Investigate GHCR build failures
- #55: Review submodule Dockerfiles
- #56: Audit multi-arch build strategy
- #57: Review Docker deployment patterns
