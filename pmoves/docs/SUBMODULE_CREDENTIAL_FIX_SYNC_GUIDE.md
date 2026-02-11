# PMOVES.AI Credential Fixes - Submodule Sync Guide

**Date:** 2026-02-08
**Parent Commit:** `f943db5b` - `fix: Correct grep regex pattern for environment variable counting`
**Parent Repo:** `POWERFULMOVES/PMOVES.AI`

---

## Overview

PMOVES.AI has received critical fixes to the credential management system. All 27 submodules with PMOVES.AI integration should sync to get these fixes.

---

## What Was Fixed in PMOVES.AI

### 1. Bootstrap Script (`scripts/bootstrap_credentials.sh`)
- ✅ Fixed broken bash regex comparison for environment variables
- ✅ Fixed security issue: silent tier fallback now fails explicitly
- ✅ Fixed version mismatch: v4 → v5 alignment
- ✅ Corrected grep pattern from `^[A-Z_]+=` to `^[A-Z_][A-Z0-9_]*=`

### 2. Credential Wizard (`pmoves/tools/credential_setup.py`)
- ✅ Fixed undefined `GITHUB_SECRET_PREFIX` variable
- ✅ Now uses proper GitHub Actions secret format: `${{SECRET_NAME}}`

### 3. Documentation
- ✅ New: `docs/TIER_BASED_CREDENTIAL_ARCHITECTURE.md` - Comprehensive tier documentation
- ✅ New: `pmoves/docs/PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md` - Universal integration guide
- ✅ Clarified tier file status: only 3 exist (llm, data, api), 3 planned (agent, worker, media)
- ✅ Fixed CHIT CGP search paths to match actual implementation

---

## Action Required for Each Submodule

### Option 1: Quick Sync (Recommended for Most Submodules)

If your submodule uses PMOVES.AI integration patterns:

1. **Update submodule reference to latest PMOVES.AI**
   ```bash
   cd your-submodule
   git submodule update --remote PMOVES.AI
   ```

2. **Update your `PMOVES.AI_INTEGRATION.md`** to reference the new universal guide:
   ```markdown
   ## Overview

   **For comprehensive PMOVES.AI integration documentation, see the
   [Universal Submodule Integration Guide](../../pmoves/docs/PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md).**
   ```

3. **Verify `PMOVES_ENV` default is `production`** (not `development`):
   ```bash
   grep "PMOVES_ENV.*production" env.shared docker-compose.pmoves.yml
   ```

### Option 2: Manual File Sync (If Not Using Git Submodules)

If your submodule references PMOVES.AI files without using git submodules:

1. **Copy the fixed bootstrap script** (if you use it):
   ```bash
   # From PMOVES.AI root
   cp scripts/bootstrap_credentials.sh /path/to/submodule/scripts/
   ```

2. **Copy the new documentation** (for reference):
   ```bash
   cp docs/TIER_BASED_CREDENTIAL_ARCHITECTURE.md /path/to/submodule/docs/reference/
   ```

3. **Update your integration docs** to reference the universal guide.

### Option 3: Full PR Update

If you have an active PR (like PMOVES.YT #1):

1. **Cherry-pick the fixes** to your PR branch:
   ```bash
   git fetch https://github.com/POWERFULMOVES/PMOVES.AI.git main
   git cherry-pick 1894a284 f943db5b
   ```

2. **Update your files** as described in Option 1

3. **Run validation**:
   ```bash
   bash -n scripts/bootstrap_credentials.sh  # Syntax check
   ```

---

## Verification Checklist

After syncing, verify:

- [ ] Bootstrap script syntax is valid: `bash -n scripts/bootstrap_credentials.sh`
- [ ] `PMOVES_ENV=${PMOVES_ENV:-production}` in `env.shared`
- [ ] `PMOVES_ENV: ${PMOVES_ENV:-production}` in `docker-compose.pmoves.yml`
- [ ] `PMOVES.AI_INTEGRATION.md` references universal guide
- [ ] No hardcoded credentials in template files
- [ ] Bootstrap runs without errors: `./scripts/bootstrap_credentials.sh`

---

## Submodules Requiring Sync

| # | Submodule | Status | Notes |
|---|-----------|--------|-------|
| 1 | PMOVES-A2UI | ⏳ Pending | |
| 2 | PMOVES-Agent-Zero | ⏳ Pending | |
| 3 | PMOVES-Archon | ⏳ Pending | |
| 4 | PMOVES-BoTZ | ⏳ Pending | |
| 5 | PMOVES-BoTZ-check | ⏳ Pending | |
| 6 | PMOVES-Creator | ⏳ Pending | |
| 7 | PMOVES-Danger-infra | ⏳ Pending | |
| 8 | PMOVES-Deep-Serch | ⏳ Pending | |
| 9 | PMOVES-DoX | ⏳ Pending | |
| 10 | PMOVES-DoX-check | ⏳ Pending | |
| 11 | PMOVES-E2b-Spells | ⏳ Pending | |
| 12 | PMOVES-HiRAG | ⏳ Pending | |
| 13 | PMOVES-HiRAG-check | ⏳ Pending | |
| 14 | PMOVES-Jellyfin | ⏳ Pending | |
| 15 | PMOVES-Open-Notebook | ⏳ Pending | |
| 16 | PMOVES-Pinokio-Ultimate-TTS-Studio | ⏳ Pending | |
| 17 | PMOVES-Pipecat | ⏳ Pending | |
| 18 | PMOVES-Tailscale | ⏳ Pending | |
| 19 | PMOVES-ToKenism-Multi | ⏳ Pending | |
| 20 | PMOVES-Wealth | ⏳ Pending | |
| 21 | PMOVES-crush | ⏳ Pending | |
| 22 | PMOVES-n8n | ⏳ Pending | |
| 23 | PMOVES-tensorzero | ⏳ Pending | |
| 24 | PMOVES-DoX/external/PMOVES-Agent-Zero | ⏳ Pending | Nested submodule |
| 25 | PMOVES-DoX/external/PMOVES-BoTZ | ⏳ Pending | Nested submodule |
| 26 | PMOVES-DoX/external/PMOVES-n8n | ⏳ Pending | Nested submodule |
| 27 | PMOVES-YT | 🔴 PR #1 | Has active PR needing sync |

---

## Impact Summary

**Critical Security Fix**: Tier fallback behavior changed
- **Before**: Missing tier file silently loaded ALL tiers (security violation)
- **After**: Missing tier file fails explicitly with error message

**Functional Fixes**:
- Bootstrap script now correctly counts environment variables
- Credential wizard uses proper GitHub Actions secret format

**Documentation Updates**:
- Tier file status clarified (3 exist, 3 planned)
- CHIT CGP search paths corrected
- Universal integration guide created

---

## Questions?

Refer to:
- `docs/TIER_BASED_CREDENTIAL_ARCHITECTURE.md` - Tier system documentation
- `pmoves/docs/PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md` - Integration guide
- `scripts/bootstrap_credentials.sh` - Bootstrap script (v5)

---

**Last Updated:** 2026-02-08
