# PMOVES.AI Submodules Comprehensive Audit

**Date:** 2026-01-29
**Auditor:** PMOVES.AI Agent Team
**Scope:** 37 submodules total

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| **Tokenism Hub** | 1 | ⚠️ Partially Hardened |
| **Tokenism-Adjacent** | 4 | ⚠️ Mixed Compliance |
| **PMOVES Original** | 25 | ✅ Mostly Hardened |
| **Forked (Upstream)** | 5 | ✅ Synced |
| **External/Vendor** | 2 | N/A |

---

## Tokenism Integration Audit Results

### 1. PMOVES-ToKenism-Multi (Tokenism Hub)

| Aspect | Status | Notes |
|--------|--------|-------|
| Branch | PMOVES.AI-Edition-Hardened | ✅ |
| USER Directive | ❌ Missing | No Dockerfile found |
| pmoves-net | ❌ Missing | No network config |
| /healthz | ❌ Missing | No health endpoint |
| /metrics | ❌ Missing | No metrics endpoint |
| CHIT Secrets | ✅ Present | `chit/secrets_manifest_v2.yaml` |

**Integrations:**
- PMOVES-DoX (Document intelligence) ✅
- PMOVES-Firefly-iii (Financial data) ⚠️ Modified
- CHIT/Geometry bus ✅
- Token contracts ✅

**P0 Issues:**
1. No Dockerfile for containerization
2. Missing health/metrics endpoints
3. Uncommitted Firefly-iii submodule changes

---

### 2. PMOVES-DoX (Document Intelligence)

| Aspect | Status | Notes |
|--------|--------|-------|
| Branch | PMOVES.AI-Edition-Hardened | ✅ |
| USER Directive | ❌ Missing | Runs as root |
| pmoves-net | ❌ Missing | No network config |
| /healthz | ✅ Fixed | **2026-01-29:** Fixed `/health` → `/healthz` |
| /metrics | ✅ Present | Working |
| CHIT Secrets | ✅ Present | Full implementation |

**Nested Submodules:**
- PMOVES-Firefly-iii ✅ Clean

**P0 Issues:**
1. Missing USER directive in Dockerfile (4 Dockerfiles need fix)

**Completed 2026-01-29:**
- ✅ Fixed health endpoint path to `/healthz` with 301 redirect from `/health`

---

### 3. PMOVES-BoTZ (BotZ Gateway)

| Aspect | Status | Notes |
|--------|--------|-------|
| Branch | PMOVES.AI-Edition-Hardened | ✅ |
| USER Directive | ⚠️ Partial | 14/17 services have USER |
| pmoves-net | ✅ Present | In compose files |
| /healthz | ✅ Added | **2026-01-29:** Added to Gateway + Bridge |
| /metrics | ✅ Added | **2026-01-29:** Added to Gateway + Bridge |
| CHIT Secrets | ✅ Present | Full implementation |

**Nested Submodules:**
- PMOVES-DoX ✅ Synced
- PMOVES-Firefly-iii ✅ Clean

**P0 Issues:**
1. 3 services missing USER directive (skills, cipher, crush_shim)

**Completed 2026-01-29:**
- ✅ Added `/healthz` and `/metrics` to Python Gateway (port 2091)
- ✅ Added `/metrics` to MCP Bridge (port 8100)
- ✅ Added USER directive to python-gateway Dockerfile
- ✅ **PR #47** created merging to main

---

### 4. PMOVES-Wealth (Firefly III + Tokenism)

| Aspect | Status | Notes |
|--------|--------|-------|
| Branch | PMOVES.AI-Edition-Hardened | ✅ |
| USER Directive | ✅ Present | `firefly` user |
| pmoves-net | ❌ Missing | Not integrated |
| /healthz | ✅ Added | **2026-01-29:** Added /healthz route |
| /metrics | ✅ Existing | Already present |
| CHIT Secrets | ✅ Present | Full implementation |

**Branches:**
- `PMOVES.AI-Edition-Hardened` (current, also default branch)
- `PMOVES.AI-Edition-Hardened-Tokenism` (integration variant)

**P0 Issues:**
1. Missing pmoves-net integration

**Completed 2026-01-29:**
- ✅ Added `/healthz` route to both web and API routes
- ✅ Changes on default branch, no PR needed

---

### 5. Pmoves-Health-wger (wger + Tokenism)

| Aspect | Status | Notes |
|--------|--------|-------|
| Branch | PMOVES.AI-Edition-Hardened | ✅ (default branch) |
| USER Directive | ✅ Present | `wger` user |
| pmoves-net | ❌ Missing | Not integrated |
| /healthz | ✅ Added | **2026-01-29:** Created observability app |
| /metrics | ✅ Added | **2026-01-29:** Uses django-prometheus |
| CHIT Secrets | ❌ Missing | Not found |

**P0 Issues:**
1. Missing CHIT secrets
2. Missing pmoves-net integration

**Completed 2026-01-29:**
- ✅ Created `wger.observability` Django app
- ✅ Added `/healthz` endpoint with database connectivity check
- ✅ Added `/metrics` endpoint using existing django-prometheus
- ✅ Changes on default branch, no PR needed

---

## Tokenism Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  PMOVES-ToKenism-Multi (Hub)               │
│                    ⚠️ Partially Hardened                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   DoX    │  │  Wealth  │  │  Health  │  │   BoTZ   │   │
│  │  ⚠️ P0   │  │  ⚠️ P1   │  │  ⚠️ P1   │  │  ⚠️ P0   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│        │             │              │             │          │
│        └─────────────┴──────────────┴─────────────┘          │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Integration Coordinator                 │   │
│  │              (TypeScript/Node.js)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   NATS   │  │ Geometry │  │   CHIT   │  │ Secrets  │   │
│  │   Bus    │  │  Engine  │  │   Vault  │  │ Manager  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Remaining Submodules Audit (25 total)

### Tokenism-Adjacent (Priority)
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-Archon | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Agent-Zero | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-n8n | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### Media Services
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES.YT | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Pinokio-Ultimate-TTS-Studio | ? | ? | Unknown |
| PMOVES-Ultimate-TTS-Studio | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Remote-View | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Jellyfin | master | ❌ | Not on hardened |

### AI/ML Services
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-HiRAG | main | ❌ | Not on hardened |
| PMOVES-Deep-Serch | main | ❌ | Not on hardened |
| PMOVES-tensorzero | HEAD | ✅ | Detached |
| PMOVES-Pipecat | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### Infrastructure
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-Tailscale | main | ❌ | Not on hardened |
| PMOVES-crush | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Danger-infra | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### UI/UX
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-A2UI | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-MAI-UI | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-Creator | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### E2B/Compute
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-E2B-Danger-Room | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-E2B-Danger-Room-Desktop | main | ❌ | Not on hardened |
| PMOVES-E2b-Spells | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### Agents/Gym
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-AgentGym | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| Pmoves-AgentGym-RL | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| PMOVES-BotZ-gateway | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |

### Other
| Submodule | Branch | Hardened | Status |
|-----------|--------|----------|--------|
| PMOVES-surf | PMOVES.AI-Edition-Hardened | ✅ | Fully hardened |
| Pmoves-Jellyfin-AI-Media-Stack | ? | ? | Unknown |
| Pmoves-hyperdimensions | ? | ? | Unknown |

---

## Consolidated Action Items

### P0 - Critical (Security)
| Action | Submodule | Status |
|--------|-----------|--------|
| Add USER directive to 4 Dockerfiles | PMOVES-DoX | 🔲 Pending |
| Add USER to 3 BoTZ services | PMOVES-BoTZ | 🔲 Pending (skills, cipher, crush_shim) |
| Create Dockerfile | PMOVES-ToKenism-Multi | 🔲 Pending |
| ~~Fix health endpoint path~~ | PMOVES-DoX | ✅ **COMPLETED** |

### P1 - High Priority (Compliance)
| Action | Submodule | Status |
|--------|-----------|--------|
| ~~Add /healthz endpoint~~ | PMOVES-BoTZ | ✅ **COMPLETED** |
| ~~Add /healthz endpoint~~ | PMOVES-Wealth | ✅ **COMPLETED** |
| ~~Add /healthz endpoint~~ | Pmoves-Health-wger | ✅ **COMPLETED** |
| ~~Add /metrics endpoint~~ | PMOVES-BoTZ | ✅ **COMPLETED** |
| Add /metrics endpoint | PMOVES-Wealth | ✅ Already existed |
| ~~Add /metrics endpoint~~ | Pmoves-Health-wger | ✅ **COMPLETED** |
| Add pmoves-net config | PMOVES-Wealth | 🔲 Pending |
| Add pmoves-net config | Pmoves-Health-wger | 🔲 Pending |
| ~~Commit submodule changes~~ | PMOVES-ToKenism-Multi | ✅ **COMPLETED** |
| ~~Sync submodule~~ | PMOVES-BoTZ | ✅ **COMPLETED** |
| ~~Push transcribe-and-fetch~~ | PMOVES-transcribe-and-fetch | ✅ **COMPLETED** (1,241 commits) |
| ~~Create upstream PRs~~ | lfnovo/open-notebook | ✅ **COMPLETED** (#496, #497) |

### P2 - Medium Priority (Branch Migration)
| Action | Submodules | Command |
|--------|-----------|---------|
| Migrate to hardened branch | PMOVES-Jellyfin | `git checkout PMOVES.AI-Edition-Hardened` |
| Migrate to hardened branch | PMOVES-HiRAG | `git checkout PMOVES.AI-Edition-Hardened` |
| Migrate to hardened branch | PMOVES-Deep-Serch | `git checkout PMOVES.AI-Edition-Hardened` |
| Migrate to hardened branch | PMOVES-Tailscale | `git checkout PMOVES.AI-Edition-Hardened` |
| Migrate to hardened branch | PMOVES-E2B-Danger-Room-Desktop | `git checkout PMOVES.AI-Edition-Hardened` |

### P3 - Low Priority (Cleanup)
| Action | Submodules | Command |
|--------|-----------|---------|
| Rebase Tokenism branch | PMOVES-Wealth | `git rebase PMOVES.AI-Edition-Hardened` |
| Fix detached HEAD | Pmoves-Health-wger | `git checkout PMOVES.AI-Edition-Hardened` |
| Add CHIT secrets | Pmoves-Health-wger | `create chit/secrets_manifest_v2.yaml` |

---

## Previously Reviewed Submodules

### PMOVES-transcribe-and-fetch
- ✅ Remote fixed (now points to correct fork)
- ⚠️ **1,241 commits need push to origin**
- Status: Diverged (ahead 1241, behind 126)

### PMOVES-Open-Notebook
- ✅ Fully hardened
- ⚠️ **3 upstream PRs needed** (security fixes)
  - CVE-2025-55182 (Next.js 15.4.8)
  - Non-root user Dockerfile
  - API bug fix

---

## Audit Reports Generated

| Report | Location |
|--------|----------|
| PMOVES-DoX | `/home/pmoves/pmoves-audit-worktrees/audit-PMOVES-DoX.md` |
| PMOVES-BoTZ | `/home/pmoves/pmoves-audit-worktrees/audit-PMOVES-BoTZ.md` |
| PMOVES-ToKenism-Multi | `/home/pmoves/pmoves-audit-worktrees/audit-PMOVES-ToKenism-Multi.md` |
| Remaining | Agent output (not saved to file) |

---

## Completed Actions (2026-01-29 Session)

### Observability Endpoints - COMPLETED ✅

| Submodule | /healthz | /metrics | PR | Status |
|-----------|----------|----------|-----|--------|
| PMOVES-DoX | ✅ Fixed | ✅ Existing | N/A | Pushed |
| PMOVES-BoTZ | ✅ Added | ✅ Added | #47 | Pushed |
| PMOVES-Wealth | ✅ Added | ✅ Existing | N/A | Pushed |
| Pmoves-Health-wger | ✅ Added | ✅ Added | N/A | Pushed |

**Details:**
- **PMOVES-DoX**: Fixed `/health` → `/healthz` with 301 redirect for backwards compatibility
- **PMOVES-BoTZ**: Added `/healthz` and `/metrics` to Python Gateway (port 2091) and MCP Bridge (port 8100)
- **PMOVES-Wealth**: Added `/healthz` route to both web and API routes
- **Pmoves-Health-wger**: Created new `wger.observability` Django app with health and metrics endpoints

### Upstream Contributions - COMPLETED ✅

| Repository | PR | Title | Status |
|------------|-----|-------|--------|
| lfnovo/open-notebook | #496 | Add non-root user to Dockerfile | Open |
| lfnovo/open-notebook | #497 | Fix file_path initialization bug | Open |
| lfnovo/open-notebook | - | CVE-2025-55182 (Next.js) | Skipped (already patched upstream) |

### Submodule Sync - COMPLETED ✅

| Submodule | Commits | Status |
|-----------|---------|--------|
| PMOVES-transcribe-and-fetch | 1,241 | ✅ Pushed |
| PMOVES-BoTZ | 1 (observability) | ✅ Pushed |
| PMOVES-Wealth | 1 (healthz) | ✅ Pushed |
| PMOVES-ToKenism-Multi | 1 (submodule update) | ✅ Pushed |
| Pmoves-Health-wger | 1 (observability) | ✅ Pushed |
| PMOVES-DoX | 1 (healthz fix) | ✅ Pushed |

---

## Remaining Next Steps

1. **Fix P0 security issues** (USER directives):
   - PMOVES-DoX: Add USER to 4 Dockerfiles
   - PMOVES-BoTZ: Add USER to 3 services (skills, cipher, crush_shim)
   - PMOVES-ToKenism-Multi: Create Dockerfile

2. **Merge PR #47** for PMOVES-BoTZ observability

3. **Migrate remaining submodules** to hardened branch:
   - PMOVES-Jellyfin
   - PMOVES-HiRAG
   - PMOVES-Deep-Serch
   - PMOVES-Tailscale
   - PMOVES-E2B-Danger-Room-Desktop

---

## Related Documentation

- [PMOVES Git Organization](./PMOVES_Git_Organization.md)
- [Submodules Upstream Audit](./submodules-upstream-audit.md)
- [Security Hardening Roadmap](./Security-Hardening-Roadmap.md)
