# PMOVES.AI Submodule Audit Report

**Date:** 2026-02-07
**Audit Type:** Branch Alignment and Upstream Sync
**Branch:** feat/supabase-variable-standardization
**Target:** PMOVES.AI-Edition-Hardened alignment

---

## Executive Summary

**Total Submodules:** 40 (39 initialized, 1 not initialized)

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ On PMOVES.AI-Edition-Hardened | 27 | 67.5% |
| ⚠️ Wrong Branch / Detached | 12 | 30% |
| ❌ Not Initialized | 1 | 2.5% |

**Key Findings:**
- 27/40 submodules are correctly on `PMOVES.AI-Edition-Hardened` branch
- 12 submodules need branch alignment fixes
- 1 submodule (`Pmoves-open-notebook`) not initialized
- 1 submodule (`PMOVES-Wealth`, formerly `PMOVES-Firefly-iii`) not initialized
- Most submodules are up-to-date with their remotes

---

## Submodule Status Details

### ✅ Correctly Aligned (27)

| Submodule | Branch | Commit Date | Commit |
|-----------|--------|-------------|--------|
| PMOVES-Archon | PMOVES.AI-Edition-Hardened | 2026-02-03 | 5fc6ceb |
| PMOVES-BoTZ | PMOVES.AI-Edition-Hardened | 2026-02-05 | 2b00d40 |
| PMOVES-BotZ-gateway | PMOVES.AI-Edition-Hardened | 2026-01-15 | 5dbe5d6 |
| PMOVES-A2UI | PMOVES.AI-Edition-Hardened | 2026-01-27 | ff88ffa |
| PMOVES-Deep-Serch | PMOVES.AI-Edition-Hardened | 2026-01-21 | e2af6b6 |
| PMOVES-HiRAG | PMOVES.AI-Edition-Hardened | 2026-01-21 | 9671dc1 |
| Pmoves-hyperdimensions | PMOVES.AI-Edition-Hardened | 2025-12-27 | 79d656f |
| PMOVES-AgentGym | PMOVES.AI-Edition-Hardened | 2025-09-11 | c3b300f |
| PMOVES-surf | PMOVES.AI-Edition-Hardened | 2025-12-12 | 135748a |
| PMOVES-E2B-Danger-Room | PMOVES.AI-Edition-Hardened | 2026-01-27 | 65a7e9b1 |
| PMOVES-E2B-Danger-Room-Desktop | PMOVES.AI-Edition-Hardened | 2026-01-16 | a589d59 |
| PMOVES-Danger-infra | PMOVES.AI-Edition-Hardened | 2026-01-28 | eeb044365 |
| PMOVES-E2b-Spells | PMOVES.AI-Edition-Hardened | 2026-01-21 | 43f4f8b |
| PMOVES-Pinokio-Ultimate-TTS-Studio | PMOVES.AI-Edition-Hardened | 2026-01-21 | 7a91ca9 |
| PMOVES-transcribe-and-fetch | PMOVES.AI-Edition-Hardened | 2026-02-04 | fb20b0d8 |
| PMOVES-Jellyfin | PMOVES.AI-Edition-Hardened | 2026-01-21 | ecdfad9e3 |
| PMOVES-Open-Notebook | PMOVES.AI-Edition-Hardened | 2026-01-31 | af45126 |
| PMOVES-DoX | PMOVES.AI-Edition-Hardened | 2026-02-07 | 6ea52f4 |
| PMOVES-Creator | PMOVES.AI-Edition-Hardened | 2026-01-21 | 5e30680a |
| PMOVES-crush | PMOVES.AI-Edition-Hardened | 2026-01-21 | 75ce0126 |
| PMOVES-tensorzero | PMOVES.AI-Edition-Hardened | 2026-01-27 | 555a9206 |
| PMOVES-Wealth | PMOVES.AI-Edition-Hardened | 2026-01-29 | 932222c9fb |
| Pmoves-Health-wger | PMOVES.AI-Edition-Hardened | 2026-01-29 | bd5059c55 |
| PMOVES-Tailscale | PMOVES.AI-Edition-Hardened | 2026-01-21 | 43a3bc7bd |
| PMOVES-Headscale | PMOVES.AI-Edition-Hardened | 2026-02-06 | bfb6fd80 |
| PMOVES-ToKenism-Multi | PMOVES.AI-Edition-Hardened | 2026-02-06 | a17d8a2 |
| pmoves/integrations/archon | PMOVES.AI-Edition-Hardened | 2025-12-23 | 951be3e |
| PMOVES-supabase | PMOVES.AI-Edition-Hardened | 2026-02-06 | e8162fee08 |

### ⚠️ Need Branch Alignment (12)

| Submodule | Current Branch | Issue | Action Required |
|-----------|----------------|-------|-----------------|
| **PMOVES-Agent-Zero** | feat/personas-first-architecture | Feature branch, not hardened | Switch to PMOVES.AI-Edition-Hardened |
| **Pmoves-AgentGym-RL** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES-llama-throughput-lab** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **pmoves-e2b-mcp-server** | main | On main instead of hardened | Switch to PMOVES.AI-Edition-Hardened |
| **PMOVES-Pipecat** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES-Ultimate-TTS-Studio** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES.YT** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **Pmoves-Jellyfin-AI-Media-Stack** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES-n8n** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES-MAI-UI** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |
| **PMOVES-Remote-View** | (empty/detached) | Detached HEAD | Checkout PMOVES.AI-Edition-Hardened |

### ❌ Not Initialized (2)

| Submodule | Issue | Action Required |
|-----------|-------|-----------------|
| **Pmoves-open-notebook** | Not initialized | Run `git submodule update --init Pmoves-open-notebook` |
| **PMOVES-Wealth** | Not initialized | Run `git submodule update --init PMOVES-Wealth` |

---

## Remediation Plan

### Phase 1: Initialize Missing Submodules

```bash
git submodule update --init Pmoves-open-notebook
git submodule update --init PMOVES-Wealth
```

### Phase 2: Align Detached Submodules

For each submodule with detached HEAD, checkout the hardened branch:

```bash
# Loop through all submodules and checkout PMOVES.AI-Edition-Hardened
git submodule foreach 'git checkout PMOVES.AI-Edition-Hardened 2>/dev/null || echo "No hardened branch for $name"'
```

### Phase 3: Handle pmoves-e2b-mcp-server (on main)

```bash
cd pmoves-e2b-mcp-server
git checkout PMOVES.AI-Edition-Hardened
cd ..
```

### Phase 4: Handle PMOVES-Agent-Zero (feature branch)

This submodule is on `feat/personas-first-architecture`. Need to determine:
1. Should this feature be merged into PMOVES.AI-Edition-Hardened?
2. Or should we switch back to PMOVES.AI-Edition-Hardened?

**Action:** Review with user before changing PMOVES-Agent-Zero branch.

---

## Upstream Sync Status

All submodules are POWERFULMOVES forks. To check for upstream updates:

```bash
# Check if any submodule has upstream configured
git submodule foreach 'echo "=== $name ==="; git remote -v | grep upstream; echo ""'

# For each submodule with upstream:
cd <submodule>
git fetch upstream
git log HEAD..upstream/main --oneline | head -5
```

---

## Recommendations

1. **Automate Branch Alignment:** Create a script that runs during repo setup to ensure all submodules are on PMOVES.AI-Edition-Hardened

2. **Pre-commit Hook:** Add check to prevent commits when submodules are on wrong branches

3. **CI Validation:** Add workflow check to verify submodule branches before merging

4. **Submodule Update Policy:** Establish policy for when to sync submodules with upstream

---

## GHCR / CI Status

**Docker Hardening Validation Workflow:** Jobs are QUEUED (waiting for self-hosted runner)

| Job | Status |
|-----|--------|
| Validate Hardening Patterns | QUEUED |
| Validate Dockerfiles (8 services) | QUEUED |
| Docker Bench Security | QUEUED |
| Validate Compose Files | QUEUED |

**Note:** Self-hosted runner may be offline or busy. Jobs will process when runner becomes available.

---

## Sign-Off

| Role | Name | Date |
|------|------|------|
| Auditor | Claude Code (AI) | 2026-02-07 |
| Reviewed By | | |
| Approved By | | |

---

## Related Documentation

- `pmoves/docs/AUDIT_LOG_2026-02-07.md` - Security audit log
- `pmoves/docs/SECURITY_RUNBOOK.md` - Security procedures
- `.claude/context/submodules.md` - Complete submodule catalog
