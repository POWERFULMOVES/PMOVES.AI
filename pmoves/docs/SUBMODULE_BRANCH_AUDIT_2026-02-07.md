# Submodule Branch Alignment Audit

**Date:** February 7, 2026
**Scope:** All 47 PMOVES.AI submodules
**Purpose:** Identify branches with commits not yet on `PMOVES.AI-Edition-Hardened`

---

## Summary

| Category | Count | Notes |
|----------|-------|-------|
| ✅ Properly aligned | ~40 | On PMOVES.AI-Edition-Hardened |
| ⚠️ Has feature branches | 3 | Agent-Zero, BoTZ, transcribe-and-fetch |
| ❌ Wrong branch | 3 | llama-throughput-lab (main), Wealth (tag), tensorzero (detached) |
| 📝 PRs created | 1 | PMOVES-DoX #96 |

---

## Submodules with Feature Branches (Need Review)

### PMOVES-Agent-Zero
**Remote branches with commits ahead of hardened:**
- `feat/personas-first-architecture` - Need to check commits
- `feat/pmoves-ai-integration` - Need to check commits

**Status:** ⚠️ Has new commits locally (+)
**Action:** Create PR if commits are production-ready

### PMOVES-BoTZ
**Remote branches with commits ahead of hardened:**
- `feat/tensorzero-2026-migration` (5 commits ahead)
  - `377073e` - docs: add TensorZero migration and integration documentation
  - `c350ec9` - fix(scripts): add local config support to verify_env.sh
  - `0c8bea1` - feat(env): add env.tier-agent dotenv format and Windows hooks fix
  - `8f461b8` - chore(deps): bump actions/setup-python from 5 to 6
  - `e302171` - chore(deps): bump pnpm/action-setup from 2 to 4
- `feat/skills-integration-71-skills`
- `feat/tensorzero-glm-cipher-enhancement`
- `feat/wave2-integration-orchestration`
- `fix/cipher-embedding-model`

**Status:** ⚠️ Has new commits locally (+)
**Action:** Consider merging `feat/tensorzero-2026-migration` for TensorZero integration

### PMOVES-transcribe-and-fetch
**Open PRs:**
- #41: chore: refresh pinned Python dependency versions for security alerts (OPEN)

**Remote branches:**
- `feat/postgres17-compatibility` - Need to check commits
- `feat/hardened-edition-alignment`
- `fix/review-corrections-and-docs`

**Status:** ⚠️ Has new commits locally (+)
**Action:** PR #41 should be merged

---

## Submodules on Wrong Branch

### PMOVES-llama-throughput-lab
**Current:** `heads/main`
**Should be:** `PMOVES.AI-Edition-Hardened`
**Issue:** Does this submodule have a hardened branch?

### PMOVES-tensorzero
**Current:** `remotes/origin/HEAD`
**Should be:** `PMOVES.AI-Edition-Hardened`
**Note:** Has hardened branch available, just needs checkout

### PMOVES-Wealth
**Current:** `v6.4.16-20-g932222c` (tag)
**Should be:** `main` or `PMOVES.AI-Edition-Hardened`
**Issue:** Detached on version tag

### Pmoves-hyperdimensions
**Current:** `4b38031` (detached)
**Should be:** `PMOVES.AI-Edition-Hardened`

---

## Nested Submodules (PMOVES-DoX)

PMOVES-DoX contains 13 nested submodules, many configured for `PMOVES.AI-Edition-Hardened-DoX` branch which may not exist:

| Nested Submodule | Current Branch | Configured Branch | Issue |
|-----------------|---------------|-------------------|-------|
| A2UI_reference | main | PMOVES.AI-Edition-Hardened-DoX | Branch doesn't exist |
| PsyFeR_reference | main | PMOVES.AI-Edition-Hardened-DoX | Branch doesn't exist |
| PMOVES-Agent-Zero | detached | PMOVES.AI-Edition-Hardened-DoX | Branch doesn't exist |
| PMOVES-BoTZ | hardened | PMOVES.AI-Edition-Hardened | ✅ Correct |
| Pmoves-Glancer | develop | PMOVES.AI-Edition-Hardened-DoX | Wrong branch |
| Pmoves-hyperdimensions | main | PMOVES.AI-Edition-Hardened-DoX | Branch doesn't exist |

**Recommendation:** Create `PMOVES.AI-Edition-Hardened-DoX` branches in nested submodules OR update .gitmodules to track standard `PMOVES.AI-Edition-Hardened` branches.

---

## Orphan Submodule Reference

**Issue:** `e2b` submodule referenced in `.git/modules` but not in `.gitmodules`

**Error:** `fatal: no submodule mapping found in .gitmodules for path 'e2b'`

**Action Required:** Clean up orphan submodule reference:
```bash
git config --remove-section submodule.e2b
git config --remove-section submodule.pmoves/vendor/e2b
rm -rf .git/modules/pmoves/vendor/e2b
```

---

## PRs Created This Session

1. **PMOVES-DoX #96**: fix: PostgreSQL 17 compatibility and CodeRabbit review comments ✅
   - Branch: `feat/v5-secrets-bootstrap` → `PMOVES.AI-Edition-Hardened`
   - URL: https://github.com/POWERFULMOVES/PMOVES-DoX/pull/96
   - Status: **OPEN**

2. **PMOVES-BoTZ #51**: feat: TensorZero 2026 migration and integration updates ✅
   - Branch: `feat/tensorzero-2026-migration` → `PMOVES.AI-Edition-Hardened`
   - URL: https://github.com/POWERFULMOVES/PMOVES-BoTZ/pull/51
   - Status: **OPEN** (17 commits)

3. **PMOVES-Agent-Zero #3**: feat(pmoves-ai): Add PMOVES.AI integration patterns ✅
   - Branch: `feat/pmoves-ai-integration` → `PMOVES.AI-Edition-Hardened`
   - URL: https://github.com/POWERFULMOVES/PMOVES-Agent-Zero/pull/3
   - Status: **OPEN** (1 commit, 1548 lines)

---

## Actions Completed - 2026-02-07

### Fixed Submodule Alignment
| Submodule | Previous State | Current State | Action |
|-----------|---------------|---------------|--------|
| PMOVES-tensorzero | detached | PMOVES.AI-Edition-Hardened | ✅ Checked out |
| Pmoves-hyperdimensions | detached | PMOVES.AI-Edition-Hardened | ✅ Checked out |
| PMOVES-Wealth | tag v6.4.16-20 | origin/main (detached at correct commit) | ✅ Verified |
| PMOVES-llama-throughput-lab | main | main | ✅ Correct (no hardened branch) |

### Cleaned Up
- ✅ Removed orphan `e2b` submodule reference from `.git/modules`
- ✅ Removed `pmoves/vendor/e2b` from git config

### Open PRs Summary
| Repo | PR # | Title | Branch | Status |
|------|------|-------|--------|--------|
| PMOVES-DoX | 96 | PostgreSQL 17 compatibility | feat/v5-secrets-bootstrap | Open |
| PMOVES-BoTZ | 51 | TensorZero 2026 migration | feat/tensorzero-2026-migration | Open |
| PMOVES-Agent-Zero | 3 | PMOVES.AI integration patterns | feat/pmoves-ai-integration | Open |
| PMOVES-transcribe-and-fetch | 41 | Dependency security updates | - | CI Failing |

---

**Last Updated:** 2026-02-07 18:00 UTC
