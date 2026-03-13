# Branch Strategy Implementation - Quick Start

**Date:** 2026-03-13
**Status:** ✅ Implementation Complete - Ready for Execution

---

## 🚀 Quick Start (3 Steps)

### Step 1: Configure Main Branch Protection (CRITICAL)

```bash
# Run automated setup
make -C pmoves main-branch-protection-setup
```

**What this does:**
- Requires 1 approval before merging to main
- Requires 4 CI checks to pass (CodeQL, CHIT, SQL)
- Enforces linear history and signed commits

### Step 2: Test PR Validation

```bash
# Create test PR to verify restrictions
git checkout -b test/protection-validation
echo "# Test" > test-protection.md
git add test-protection.md
git commit -m "test: verify main branch protection"
git push origin test/protection-validation

# Try to create PR targeting main (should warn/block)
gh pr create --base main --title "test: protection validation"

# Clean up
git checkout main
git branch -D test/protection-validation
gh pr close <number> || true
git push origin --delete test/protection-validation
```

### Step 3: Start Using Promotion Flow

```bash
# For new features
git checkout -b feat/my-feature
# ... make changes ...
git push origin feat/my-feature

# Create PR to Integrations (NOT main!)
gh pr create --base PMOVES.AI-Edition-Hardened-Integrations

# After merge, promote to Hardened
make -C pmoves promote-to-hardened

# After review and merge, release to main
make -C pmoves promote-to-main
```

---

## 📋 What Was Implemented

### 1. Documentation & Analysis

**File:** `pmoves/docs/BRANCH_STRATEGY_IMPLEMENTATION_REPORT.md`

- **Analysis:** Current branch protection gaps identified
- **Findings:** All recent PRs (#892-#897) merged directly to main
- **Action Items:** Prioritized list with severity ratings

### 2. Promotion Helper Tool

**File:** `pmoves/mk/promote.mk`

**Targets:**
- `make -C pmoves promote-to-integrations` - Feature → Integrations
- `make -C pmoves promote-to-hardened` - Integrations → Hardened
- `make -C pmoves promote-to-main` - Hardened → main (release)
- `make -C pmoves promote-check` - Validate branch state

**Features:**
- Validates clean working directory before promotion
- Generates professional PR descriptions
- Shows CI gate requirements
- Tracks changes in promotion

### 3. PR Base Validation Workflow

**File:** `.github/workflows/pr-base-validation.yml`

**Validates:**
- ✅ Release PRs from Hardened → main (allowed)
- ✅ Promotion PRs from Integrations → Hardened (allowed)
- ❌ Direct merges to main from feature branches (blocked)
- ⚠️ Feature branches targeting Hardened directly (warn)
- 🔍 Branch TTL compliance checks

### 4. Setup Automation

**File:** `pmoves/docs/MAIN_BRANCH_PROTECTION_SETUP.md`
**Target:** `make -C pmoves main-branch-protection-setup`

**Includes:**
- Automated setup script
- Manual UI instructions
- Verification commands
- Troubleshooting guide
- Rollback procedures

---

## 🎯 Promotion Flow Diagram

```
┌─────────────┐
│  feature/*  │ ← Developer work
└──────┬──────┘
       │ gh pr create --base PMOVES.AI-Edition-Hardened-Integrations
       ▼
┌─────────────────────────────────┐
│  Integrations Branch            │
│  - CI gate runs                 │
│  - Fast feedback                │
└──────┬──────────────────────────┘
       │ make -C pmoves promote-to-hardened
       ▼
┌─────────────────────────────────┐
│  Hardened Branch                │
│  - Full audit gate              │
│  - Security review required     │
└──────┬──────────────────────────┘
       │ make -C pmoves promote-to-main
       ▼
┌─────────────────────────────────┐
│  main Branch (Production)       │
│  - All gates passed             │
│  - Tagged release               │
└─────────────────────────────────┘
```

---

## ⚠️ Important Notes

### Emergency Fixes

For emergency production fixes, you can still bypass:

```bash
# Direct merge to main with admin override
gh pr merge <number> --admin
```

### Existing Feature Branches

Current feature branches can continue targeting main **temporarily**:

1. Existing PRs: Continue as normal
2. New PRs: Use promotion flow
3. Migration period: 1 week

### Maintainer Override

Maintainers can override PR validation warnings:

- Feature → Hardened: Allowed with warning
- Release (Hardened → main): Always allowed

---

## 📊 Success Metrics

| Metric | Week 1 | Week 2 | Week 3 | Week 4 |
|--------|--------|--------|--------|--------|
| Main protection configured | ✅ | ✅ | ✅ | ✅ |
| PRs following promotion flow | 50% | 75% | 90% | 100% |
| Direct merges to main | 5 | 3 | 1 | 0 |
| CI gate pass rate | 80% | 90% | 95% | 95% |

---

## 🔍 References

| Document | Path |
|----------|------|
| Branch Strategy | `pmoves/docs/BRANCH_STRATEGY.md` |
| Implementation Report | `pmoves/docs/BRANCH_STRATEGY_IMPLEMENTATION_REPORT.md` |
| Setup Guide | `pmoves/docs/MAIN_BRANCH_PROTECTION_SETUP.md` |
| Promotion Helper | `pmoves/mk/promote.mk` |
| PR Validation | `.github/workflows/pr-base-validation.yml` |

---

## 🆘 Troubleshooting

### PR blocked unexpectedly

```bash
# Check workflow run
gh run view <run-id>

# Check required checks
gh api repos/POWERFULMOVES/PMOVES.AI/branches/main/protection
```

### Maintainer bypass needed

```bash
# Emergency merge to main
gh pr merge <number> --admin
```

### Rollback protection rules

```bash
# Remove all restrictions
gh api --method DELETE \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection
```

---

## ✅ Checklist

- [ ] Run `make -C pmoves main-branch-protection-setup`
- [ ] Create test PR to verify restrictions
- [ ] Review PR validation workflow (should pass)
- [ ] Test promotion helper with feature branch
- [ ] Document any issues in implementation report
- [ ] Monitor for 1 week
- [ ] Adjust rules if needed

---

**Questions?** See `pmoves/docs/BRANCH_STRATEGY_IMPLEMENTATION_REPORT.md` for detailed analysis.
