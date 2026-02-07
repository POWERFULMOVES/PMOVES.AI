# Submodule Branch Alignment Audit

**Date:** February 7, 2026
**Last Updated:** February 7, 2026 18:30 UTC
**Scope:** All 47 PMOVES.AI submodules
**Purpose:** Identify branches with commits not yet on `PMOVES.AI-Edition-Hardened`

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| ✅ Properly aligned | ~43 | On PMOVES.AI-Edition-Hardened |
| ✅ PRs created | 3 | Ready for review/merge |
| ⚠️ DoX variant branches needed | 2 | Need creation for nested submodules |
| ⚠️ No hardened branch | 1 | transcribe-and-fetch (uses alignment branch) |
| ✅ Issues resolved | 5 | tensorzero, Wealth, hyperdimensions, e2b, llama-lab |

---

## PRs Created This Session

| Repo | PR # | Title | Branch | Status |
|------|------|-------|--------|--------|
| PMOVES-DoX | 96 | PostgreSQL 17 compatibility and CodeRabbit review | feat/v5-secrets-bootstrap | Open |
| PMOVES-BoTZ | 51 | TensorZero 2026 migration and integration updates | feat/tensorzero-2026-migration | Open |
| PMOVES-Agent-Zero | 3 | PMOVES.AI integration patterns | feat/pmoves-ai-integration | Open |

---

## DoX Variant Branch Pattern

**Pattern:** `PMOVES.AI-Edition-Hardened-DoX` = Hardened commits + DoX-specific enhancements

| Submodule | Hardened | DoX Variant | Status |
|-----------|----------|-------------|--------|
| PMOVES-Agent-Zero | ✅ | ✅ | Same commits + DoX additions |
| Pmoves-hyperdimensions | ✅ | ✅ | Same commits + DoX additions |
| Pmoves-PsyFeR-Holo | ✅ | ✅ | Branch exists |
| Pmoves-A2UI | ✅ | ⚠️ | **Needs creation** |

**Purpose:** DoX variant branches provide submodule-specific context while maintaining all hardened commits. They are used when the submodule is nested within PMOVES-DoX.

---

## Submodule Status Details

### ✅ Fixed This Session

| Submodule | Issue | Resolution |
|-----------|-------|------------|
| PMOVES-tensorzero | Detached HEAD | ✅ Switched to PMOVES.AI-Edition-Hardened |
| Pmoves-hyperdimensions | Detached commit | ✅ Switched to PMOVES.AI-Edition-Hardened |
| PMOVES-Wealth | Tag detachment | ✅ Verified on origin/main (fork with upstream) |
| PMOVES-llama-throughput-lab | No hardened branch | ✅ Using main (correct - no hardened needed) |
| Orphan e2b reference | .git/modules pollution | ✅ Cleaned up |

### ✅ Fixed This Session

| Submodule | Issue | Resolution |
|-----------|-------|------------|
| PMOVES-tensorzero | Detached HEAD | ✅ Switched to PMOVES.AI-Edition-Hardened |
| Pmoves-hyperdimensions | Detached commit | ✅ Switched to PMOVES.AI-Edition-Hardened |
| PMOVES-Wealth | Tag detachment | ✅ Verified on origin/main (fork with upstream) |
| PMOVES-llama-throughput-lab | No hardened branch | ✅ Using main (correct - no hardened needed) |
| Orphan e2b reference | .git/modules pollution | ✅ Cleaned up |
| **Vendor e2b entries** | Deprecated submodule references | ✅ Commented out in .gitmodules (commit e844d29c) |

### ⚠️ Needs Attention

#### PMOVES-transcribe-and-fetch
- **Issue:** No PMOVES.AI-Edition-Hardened branch exists
- **Current:** Uses `feat/hardened-edition-alignment`
- **Open PR:** #41 (codex branch, CI failing)
- **Action:** Create PMOVES.AI-Edition-Hardened branch or use alignment branch

#### PMOVES-DoX Nested Submodules
Nested submodules configured for `PMOVES.AI-Edition-Hardened-DoX`:

| Nested Submodule | Has DoX Variant | Needs Action |
|-----------------|-----------------|--------------|
| A2UI_reference | ❌ No | **Create branch** |
| PsyFeR_reference | ✅ Yes | |
| PMOVES-Agent-Zero | ✅ Yes | |
| PMOVES-BoTZ | ⚠️ Uses standard | Update config or create variant |
| PMOVES-BotZ-gateway | ⚠️ Uses standard | Update config or create variant |
| Pmoves-Glancer | ❌ No | **Create branch** |
| Pmoves-hyperdimensions | ✅ Yes | |
| PMOVES-docling | ⚠️ Main only | Accept or create variant |
| PMOVES-google_workspace_mcp | ⚠️ Main only | Accept or create variant |
| PMOVES-n8n-mcp | ⚠️ Main only | Accept or create variant |
| PMOVES-n8n | ⚠️ Main only | Accept or create variant |
| PMOVES-postman-mcp-server | ⚠️ Main only | Accept or create variant |
| conductor | ⚠️ Tag only | Accept or create variant |

---

## Commits Analysis

### PMOVES-BoTZ Feature Branch Status

| Branch | Commits Ahead | Status |
|--------|---------------|--------|
| feat/skills-integration-71-skills | 0 | Empty/already merged |
| feat/tensorzero-glm-cipher-enhancement | 0 | Empty/already merged |
| feat/wave2-integration-orchestration | ? | Needs verification |
| fix/cipher-embedding-model | ? | Needs verification |

### PMOVES-Agent-Zero Feature Branch Status

| Branch | Commits Ahead | Status |
|--------|---------------|--------|
| feat/personas-first-architecture | 0 | Empty/already merged |
| feat/pmoves-ai-integration | 1 (1548 lines) | ✅ PR #3 created |

---

## Actions Completed - 2026-02-07

1. ✅ Created PMOVES-DoX #96 (PostgreSQL 17, CodeRabbit fixes)
2. ✅ Created PMOVES-BoTZ #51 (TensorZero 2026 migration, 17 commits)
3. ✅ Created PMOVES-Agent-Zero #3 (PMOVES.AI integration, 1548 lines)
4. ✅ Fixed PMOVES-tensorzero to hardened branch
5. ✅ Fixed Pmoves-hyperdimensions to hardened branch
6. ✅ Verified PMOVES-Wealth on origin/main
7. ✅ Verified PMOVES-llama-throughput-lab on main (correct)
8. ✅ Cleaned up orphan e2b submodule reference
9. ✅ Created PMOVES.AI-Edition-Hardened-DoX variant for Pmoves-hyperdimensions
10. ✅ Verified PMOVES.AI-Edition-Hardened-DoX variant for PMOVES-Agent-Zero
11. ✅ Pushed audit updates to main (commit 6eef951d)
12. ✅ **Cleaned up vendor e2b submodule entries** (commit e844d29c)
13. ✅ **Investigated vendor e2b history - confirmed no code lost**

---

## Dependency Graph

```
[TASK 1] Update PMOVES-DoX .gitmodules
    ↓
[TASK 2] Create DoX variant branches for nested submodules
    ↓ (depends on TASK 2)
[TASK 3] Update nested submodule references in PMOVES-DoX
    ↓
[TASK 4] Create PMOVES.AI-Edition-Hardened for transcribe-and-fetch
    ↓ (depends on TASK 4)
[TASK 5] Fix CI failures in transcribe-and-fetch PR #41
    ↓ (depends on TASK 5)
[TASK 6] Review and merge open PRs (#96, #51, #3)
    ↓
[TASK 7] Create missing hardened branches for remaining submodules
    ↓
[TASK 8] Final verification and documentation update
```

---

## Remaining Work

### High Priority
1. Create PMOVES.AI-Edition-Hardened branch for transcribe-and-fetch
2. Fix CI failures in PR #41 (transcribe-and-fetch)
3. Review and merge PRs #96, #51, #3

### Medium Priority
4. Create DoX variant branches for A2UI_reference, Pmoves-Glancer
5. Update PMOVES-DoX .gitmodules to reference correct branches
6. Verify all nested submodules are initialized

### Low Priority
7. Create hardened branches for docling, n8n-mcp, postman-mcp (if needed)
8. Verify wave2 and cipher-embedding-model branches in BoTZ

---

## Files Modified This Session

- `pmoves/docs/PRODUCTION_READINESS_AUDIT_2026-02-07.md` (created)
- `pmoves/docs/SUBMODULE_BRANCH_AUDIT_2026-02-07.md` (created, updated)
- `.gitmodules` (via submodule updates)
- Various submodule branches checked out

---

**Last Updated:** 2026-02-07 18:30 UTC
