# PMOVES.AI Submodule Integration Plan

**Created**: 2026-02-12
**Status**: In Progress
**Goal**: Fix submodule configuration, restore missing frameworks, and create atomic PRs

---

## Overview

This plan tracks the submodule integration work across PMOVES.AI and its nested services. Each task is designed to be atomic and target-specific to prevent conflicts and regressions.

---

## Architecture Understanding

### Key Principles

1. **Git Submodules = Code Ownership**
   - Services that need version control integration
   - Services with specific branch variants (e.g., `PMOVES.AI-Edition-Hardened-DoX`)
   - PMOVES-specific implementations

2. **Networking Integrations = Runtime Collaboration**
   - Services integrate via NATS, gRPC, HTTP
   - No git relationship needed
   - Used in docked/standalone/hybrid modes

### Branch Strategy

- **PMOVES.AI-Edition-Hardened**: Primary hardened branch for all services
- **PMOVES.AI-Edition-Hardened-DoX**: DoX-specific variant (Agent-Zero, BoTZ instances)
- **Feature branches**: `feat/*` → merge to hardened → cascade to variants

---

## Service-Specific Architectures

### PMOVES-DoX ✅ Architecture is CORRECT

**Current State**:
- Has nested submodules for DoX-specific features
- Uses **networking** (not git submodules) for PMOVES-Agent-Zero and PMOVES-BoTZ
- `external/PMOVES-Agent-Zero/` = DoX-specific instance (on `PMOVES.AI-Edition-Hardened-DoX` branch)
- Works WITH root PMOVES.AI services via NATS/gRPC/HTTP

**Untracked Files to Handle**:
- `external/PMOVES-Agent-Zero/` - **REMOVE** (orphaned from cleanup)
- `external/PMOVES-BoTZ/` - **REMOVE** (orphaned from cleanup)
- `.github/workflows/validate-infrastructure.yml` - **COMMIT** (new work)
- `docs/INFRASTRUCTURE_VALIDATION.md` - **COMMIT** (new work)
- `docs/architecture/*.md` (7 files) - **COMMIT** (new work)
- `docs/templates/*.md` (3 files) - **COMMIT** (new work)
- `scripts/generate-service-docs.sh` - **COMMIT** (new work)
- `scripts/pre-commit-hook` - **COMMIT** (new work)
- `scripts/validate-changes.sh` - **COMMIT** (new work)

**Action Required**:
```bash
# Remove orphaned directories
rm -rf external/PMOVES-Agent-Zero/ external/PMOVES-BoTZ/

# Commit new infrastructure work
git add .github/workflows/ docs/ scripts/
git commit -m "feat: Add infrastructure validation and documentation"
```

---

### PMOVES-BoTZ ✅ Needs Branch Config

**Current State**:
- Has **15+ nested submodules** (skills, tools, gateway)
- These are BoTZ-specific and should remain as nested submodules
- Missing `branch = PMOVES.AI-Edition-Hardened` configuration

**Nested Submodules** (from PMOVES-BoTZ/.gitmodules):
```
pmoves_multi_agent_pro_pack/docling
pmoves_multi_agent_pro_pack/mcp_gateway/PMOVES-BotZ-gateway
features/cipher/pmoves_cipher
PMOVES-awesome-agent-skills
features/skills/repos/anthropics-skills
features/skills/repos/huggingface-skills
features/skills/repos/skillcreator-skills
features/skills/repos/awesome-claude-skills
features/skills/repos/d3js-skill
features/skills/repos/obsidian-plugin-skill
features/skills/repos/aws-skills
features/skills/repos/playwright-skill
features/skills/repos/epub-skill
features/skills/repos/skills-marketplace
tools/claude-code-damage-control
```

**Action Required**:
```bash
# Add branch = PMOVES.AI-Edition-Hardened to each nested submodule
# Update .gitmodules with branch specifications
```

---

### PMOVES-ToKenism-Multi ✅ Architecture is CORRECT

**Current State**:
- `.gitmodules` is **empty** (correct - no nested submodules)
- Uses **runtime-only integrations** via networking
- Economic simulation service that consumes other PMOVES.AI services

**Untracked Files to Handle**:
- `docker-compose.docked.yml` - **COMMIT** (new docked mode config)
- `home/` - **REMOVE** (orphaned from old invalid .gitmodules with absolute paths)
- `integrations/PMOVES-DoX/` - **REMOVE** (runtime integration, not git submodule)
- `integrations/PMOVES-Wealth/` - **REMOVE** (runtime integration, not git submodule)

**Action Required**:
```bash
# Remove orphaned directories
rm -rf home/ integrations/

# Commit new docked config
git add docker-compose.docked.yml
git commit -m "feat: Add docked mode configuration"
```

---

### PMOVES-n8n ⚠️ Needs Framework Restoration

**Current State**:
- Has empty `pmoves_*` directories (only `__pycache__`)
- Framework code exists in **PMOVES-crush** (working source)
- Represents incomplete work from PR integration

**Missing Files** (to be restored from PMOVES-crush):
```
pmoves_announcer/__init__.py    # NATS service discovery
pmoves_common/__init__.py       # ServiceTier, HealthStatus enums
pmoves_health/__init__.py       # Health check system
pmoves_registry/__init__.py     # Service discovery registry
```

**Source**: `/home/pmoves/PMOVES.AI/PMOVES-crush/`

**Context from Investigation**:
- Added in commit `6cf4618` (PMOVES.AI integration alignment)
- Removed in cleanup commit `359ffd9` (invalid submodule cleanup)
- PMOVES-n8n needs its OWN implementation (not a copy of PMOVES-crush)
- Each service has specific pmoves integration needs

**Action Required**:
```bash
# Need to find PMOVES-n8n SPECIFIC implementation from git history
# Or adapt from PMOVES-crush with n8n-specific modifications
```

---

### PMOVES-supabase ✅ Minor Cleanup

**Untracked Files**:
- `docker/.env.backup-*` - Add to `.gitignore`
- `docker/.env.pmoves` - Add to `.gitignore`
- `examples/_internal/fixtures/__pycache__/` - Add to `.gitignore`

---

## Task List

### Task #16: Restore pmoves framework to PMOVES-n8n
**Status**: Pending
**Branch**: `feat/n8n-pmoves-integration`
**Target**: `PMOVES.AI-Edition-Hardened`

1. Find PMOVES-n8n specific pmoves implementation from git history
2. Restore `pmoves_announcer/__init__.py`
3. Restore `pmoves_common/__init__.py`
4. Restore `pmoves_health/__init__.py`
5. Restore `pmoves_registry/__init__.py`
6. Add `**/__pycache__/` to `.gitignore`
7. Create PR to POWERFULMOVES/PMOVES-n8n

### Task #20: Update PMOVES-DoX docs and cleanup
**Status**: Pending
**Branch**: `feat/dox-infrastructure-validation`
**Target**: `PMOVES.AI-Edition-Hardened`

1. Remove `external/PMOVES-Agent-Zero/` (orphaned)
2. Remove `external/PMOVES-BoTZ/` (orphaned)
3. Add `**/__pycache__/` to `.gitignore`
4. Commit new infrastructure validation workflow
5. Commit new documentation files
6. Commit new scripts
7. Create PR to POWERFULMOVES/PMOVES-DoX

### Task #21: Review PMOVES-BoTZ nested submodule config
**Status**: Pending
**Branch**: `feat/botz-submodule-branch-config`
**Target**: `PMOVES.AI-Edition-Hardened`

1. Review PMOVES-BoTZ/.gitmodules
2. Add `branch = PMOVES.AI-Edition-Hardened` to all nested submodules
3. Document branching strategy (similar to Agent-Zero)
4. Create PR to POWERFULMOVES/PMOVES-BoTZ

### Task #22: Create branch strategy documentation
**Status**: Pending
**File**: `docs/BRANCH_STRATEGY.md`

1. Document standard branch naming convention
2. Document feature flow: `feat/*` → `PMOVES.AI-Edition-Hardened` → cascade to variants
3. Document nested submodule branch configuration
4. Document networking vs git submodule decision tree
5. Document how to handle variant-specific branches

### Task #23: PMOVES-ToKenism-Multi cleanup
**Status**: Pending
**Branch**: `feat/tokenism-docked-config`
**Target**: `PMOVES.AI-Edition-Hardened`

1. Remove `home/` directory (orphaned)
2. Remove `integrations/PMOVES-DoX/` (runtime only)
3. Remove `integrations/PMOVES-Wealth/` (runtime only)
4. Commit `docker-compose.docked.yml` (new config)
5. Create PR to POWERFULMOVES/PMOVES-ToKenism-Multi

---

## PR Merge Order

**CRITICAL**: Merge in this order to avoid conflicts

1. **Submodule PRs first** (to `PMOVES.AI-Edition-Hardened`):
   - PMOVES-n8n: Restore pmoves framework
   - PMOVES-DoX: Infrastructure validation
   - PMOVES-BoTZ: Submodule branch config
   - PMOVES-ToKenism-Multi: Docked config
   - PMOVES-supabase: Gitignore updates

2. **PMOVES.AI Parent PR** (to `main`):
   - Update `.gitmodules` to point to new submodule commits
   - Only after all submodule PRs are merged

3. **Post-merge**:
   - `git submodule update --recursive`

---

## References

- `docs/SUBMODULE_ARCHITECTURE.md` - Complete submodule structure
- `docs/NETWORKING_MODES.md` - Holographic networking design
- `docs/SUBMODULE_PR_WORKFLOW.md` - PR validation checklist
- `PMOVES.AI-Edition-Hardened` branch - Production target for all services

---

## Session Notes

### 2026-02-12 Session 1

**Completed**:
- ✅ Fixed PMOVES.AI parent .gitmodules (removed duplicates: Firefly-iii, Pmoves-open-notebook)
- ✅ Created documentation (SUBMODULE_ARCHITECTURE.md, NETWORKING_MODES.md, SUBMODULE_PR_WORKFLOW.md)
- ✅ Pushed feature/pmoves-ai-integration to origin fork
- ✅ Investigated PMOVES-n8n pmoves framework (found in PMOVES-crush)
- ✅ Clarified PMOVES-DoX architecture (networking vs git submodules)
- ✅ Clarified PMOVES-ToKenism-Multi architecture (runtime integrations only)

**Discovered**:
- PMOVES-DoX uses networking for Agent-Zero/BoTZ (correct architecture)
- PMOVES-ToKenism-Multi has no nested submodules (correct architecture)
- PMOVES-n8n needs pmoves framework restored (incomplete work)
- PMOVES-BoTZ needs branch config for nested submodules

**Next Session**:
- Start with Task #16 (PMOVES-n8n framework restoration)
- Complete Task #20 (PMOVES-DoX cleanup)
- Complete Task #21 (PMOVES-BoTZ branch config)
- Complete Task #23 (PMOVES-ToKenism-Multi cleanup)
- Create coordinated PRs

---

## Git Commands Reference

```bash
# Create feature branch from hardened
git checkout PMOVES.AI-Edition-Hardened
git checkout -b feat/description

# Commit changes
git add <files>
git commit -m "feat/description"

# Push to fork
git push origin feat/description

# Create PR via GitHub CLI
gh pr create --title "Title" --body "Description" --base PMOVES.AI-Edition-Hardened

# Update submodules after merge
git submodule update --recursive
```
