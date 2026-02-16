# PMOVES Check Directories Investigation

**Date:** 2026-02-08
**Status:** 🔍 **PENDING INVESTIGATION**
**Priority:** **MEDIUM** (May contain incomplete work)

---

## Background

During PR #606 merge preparation, three untracked submodule-like directories were discovered blocking the merge. These were moved to `/tmp/pmoves-check-backup-20260208/` for investigation.

---

## Directories Found

| Directory | Status When Found | Branch | Notes |
|-----------|-------------------|--------|-------|
| `PMOVES-BoTZ-check` | Git worktree | `main` | Has commits ahead of hardened |
| `PMOVES-DoX-check` | Git worktree | `hardened` | At hardened commit |
| `PMOVES-HiRAG-check` | Empty | N/A | No content |

---

## PMOVES-BoTZ-check (IMPORTANT - Contains Work)

### Current State
- **Location:** `/tmp/pmoves-check-backup-20260208/PMOVES-BoTZ-check/`
- **Branch:** `main`
- **Latest Commit:** `6c9cae2 chore(deps): bump the npm_and_yarn group across 2 directories with 3 updates (#49)`
- **Files of Interest:**
  - `features/vl_sentinel/app_vl.py` - 491 lines, VL Sentinel implementation
  - `config/tensorzero.local.models.toml` - Local model configuration

### Comparison to Hardened
- This worktree is on `main` branch, not `PMOVES.AI-Edition-Hardened`
- May contain features/fixes not yet in hardened

### Investigation Questions
1. What features are in `main` that aren't in `hardened`?
2. Is VL Sentinel fully functional and tested?
3. Should this be PR'd to hardened or is it experimental?

---

## PMOVES-DoX-check

### Current State
- **Location:** `/tmp/pmoves-check-backup-20260208/PMOVES-DoX-check/`
- **Branch:** `PMOVES.AI-Edition-Hardened`
- **Latest Commit:** `6ea52f4 fix: PostgreSQL 17 compatibility and CodeRabbit review comments`
- **Status:** Matches hardened, can be re-cloned if needed

---

## PMOVES-HiRAG-check

- **Status:** Empty directory, no content
- **Action:** None required

---

## Recommended Actions

### High Priority
1. **Review PMOVES-BoTZ-check/main branch**
   - Compare `main` vs `PMOVES.AI-Edition-Hardened`
   - Identify any commits that should be in hardened
   - Determine if VL Sentinel is production-ready

2. **Document purpose of check directories**
   - Were these for testing?
   - Are they part of a development workflow?
   - Should they be added to `.gitignore` globally?

### Medium Priority
3. **Clean up or restore**
   - If work is needed: PR it to appropriate branch
   - If obsolete: Archive or delete
   - Document decision

---

## Next Steps

1. Assign to PMOVES-BoTZ team for review
2. Create PR for any missing features
3. Update documentation if check directories are part of dev workflow
4. Close this task when resolved

---

**Created by:** Claude Code (PR #606 merge preparation)
**Backup Location:** `/tmp/pmoves-check-backup-20260208/`
