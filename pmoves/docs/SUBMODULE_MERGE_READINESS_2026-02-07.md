# Submodule Merge Readiness Review - 2026-02-07

**Purpose:** Review submodules worked on this session and determine readiness to merge to parent PMOVES.AI repo.

---

## Current Submodule Status

| Submodule | Current SHA | Expected Branch | Status | Action Needed |
|-----------|-------------|-----------------|--------|---------------|
| PMOVES-Archon | `5fc6ceb5` | PMOVES.AI-Edition-Hardened | ⚠️ Behind | Wait for PR #7, then update |
| PMOVES-DoX | `bbef123` | PMOVES.AI-Edition-Hardened | ✅ Correct | None (DO NOT merge main) |
| PMOVES-Wealth | `234d2bb` | main | ⚠️ Wrong branch | Switch to hardened |
| PMOVES-BoTZ | `0ba3a13` | feat/tensorzero-* | ⚠️ Wrong branch | Switch to hardened |
| PMOVES-transcribe-and-fetch | `fb20b0d` | PMOVES.AI-Edition-Hardened | ✅ Correct | None |

---

## Detailed Review

### 1. PMOVES-Archon ⚠️

**Current State:**
- Parent references: `5fc6ceb5` (PMOVES.AI-Edition-Hardened)
- Remote hardened HEAD: `5fc6ceb5`
- **Status:** Currently in sync, but PR #7 pending

**PR #7 Status:** https://github.com/POWERFULMOVES/PMOVES-Archon/pull/7

**Changes in PR #7:**
- Claude Code MCP adapter (PMOVES.AI integration)
- CODEOWNERS configuration (security)
- 7 nested submodules for standalone operation
- Persona service (457 lines) + API routes

**Action:** Wait for PR #7 to merge, then update parent submodule reference.

---

### 2. PMOVES-DoX ✅

**Current State:**
- Parent references: `bbef123` (PMOVES.AI-Edition-Hardened)
- Remote hardened HEAD: `6ea52f46`
- **Status:** Slightly behind but safe

**Analysis:**
- Hardened branch has proper JWT authentication
- Main branch (`bdd1f82c`) removes authentication - **DO NOT MERGE**
- Current hardened HEAD (`6ea52f46`) includes recent PostgreSQL 17 compatibility fix

**Action:** Update to latest hardened (`6ea52f46`) for PostgreSQL 17 fix.

---

### 3. PMOVES-Wealth ⚠️

**Current State:**
- Parent references: `234d2bb` (main branch)
- Should reference: `932222c9` (PMOVES.AI-Edition-Hardened)

**Issue:** Parent is tracking main branch instead of hardened.

**Hardened Branch Status:**
- Has all PMOVES-specific changes via PR #17
- Includes Dockerfile, comprehensive README, GPG fixes
- Properly configured for PMOVES.AI integration

**Action:** Update submodule reference from main to PMOVES.AI-Edition-Hardened.

---

### 4. PMOVES-BoTZ ⚠️

**Current State:**
- Parent references: `0ba3a13` (feat/tensorzero-glm-cipher-enhancement)
- Should reference: `1c97c42` (PMOVES.AI-Edition-Hardened)

**Issue:** Parent is tracking a feature branch instead of hardened.

**Hardened Branch Status:**
- Latest commit: `3cecfa6` (merge of hardened branch)
- Includes: VPN MCP server, TensorZero port standardization, health checks

**Action:** Update submodule reference to PMOVES.AI-Edition-Hardened.

---

### 5. PMOVES-transcribe-and-fetch ✅

**Current State:**
- Parent references: `fb20b0d` (PMOVES.AI-Edition-Hardened)
- **Status:** Correct branch

**Action:** None needed.

---

## Recommended Actions

### Immediate (Before Commit)

1. **Update PMOVES-Wealth to hardened branch**
   ```bash
   cd PMOVES-Wealth
   git checkout PMOVES.AI-Edition-Hardened
   cd ..
   git add PMOVES-Wealth
   ```

2. **Update PMOVES-BoTZ to hardened branch**
   ```bash
   cd PMOVES-BoTZ
   git checkout PMOVES.AI-Edition-Hardened
   cd ..
   git add PMOVES-BoTZ
   ```

3. **Update PMOVES-DoX to latest hardened** (for PostgreSQL 17 fix)
   ```bash
   cd PMOVES-DoX
   git checkout PMOVES.AI-Edition-Hardened
   git pull origin PMOVES.AI-Edition-Hardened
   cd ..
   git add PMOVES-DoX
   ```

4. **Leave PMOVES-Archon as-is** until PR #7 merges

### After PMOVES-Archon PR #7 Merges

5. **Update PMOVES-Archon to latest hardened**
   ```bash
   cd PMOVES-Archon
   git checkout PMOVES.AI-Edition-Hardened
   git pull origin PMOVES.AI-Edition-Hardened
   cd ..
   git add PMOVES-Archon
   ```

---

## Commit Message Template

```
docs: Update submodules to PMOVES.AI-Edition-Hardened branches

- PMOVES-Wealth: Switch from main to PMOVES.AI-Edition-Hardened (932222c9)
- PMOVES-BoTZ: Switch from feat branch to PMOVES.AI-Edition-Hardened (1c97c42)
- PMOVES-DoX: Update to latest hardened with PostgreSQL 17 fix (6ea52f46)
- PMOVES-transcribe-and-fetch: No change (already on hardened)

Note: PMOVES-Archon will be updated after PR #7 merges.

🤖 Generated with Claude Code
```

---

## Branch Strategy Reminder

**PMOVES.AI Submodule Branch Strategy:**
- `PMOVES.AI-Edition-Hardened` = Production branch (use this in parent)
- `main` = Development/experimental (may have regressions)
- Feature branches = Temporary work (do not reference in parent)

**Exception:** PMOVES-DoX uses `PMOVES.AI-Edition-Hardened` as its default branch.

---

## Verification Checklist

Before committing to parent PMOVES.AI:

- [ ] PMOVES-Wealth points to PMOVES.AI-Edition-Hardened
- [ ] PMOVES-BoTZ points to PMOVES.AI-Edition-Hardened
- [ ] PMOVES-DoX points to PMOVES.AI-Edition-Hardened (latest)
- [ ] PMOVES-transcribe-and-fetch unchanged (already correct)
- [ ] PMOVES-Archon left as-is (awaiting PR #7)
- [ ] Run `git submodule status` to verify
- [ ] Test key services after update

---

**Date:** February 7, 2026
