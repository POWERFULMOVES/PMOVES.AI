# PMOVES.AI Branch Strategy Implementation Report

**Date:** 2026-03-13
**Status:** Analysis Complete - Action Items Identified

---

## Executive Summary

The documented branch strategy at `pmoves/docs/BRANCH_STRATEGY.md` defines a 3-tier promotion model:

```
feature/* → Integrations → Hardened → main
```

**Current Reality:** Most changes merge directly to `main`, bypassing the promotion gates.

---

## Branch Protection Status

### ✅ Properly Configured

| Branch | Status | Notes |
|--------|--------|-------|
| **Hardened** | ✅ Correct | 1 review required, CI checks configured |
| **Integrations** | ✅ Correct | No PR requirement (allows automation), CI gate active |

### ❌ Configuration Gaps

| Branch | Expected | Actual | Severity |
|--------|----------|--------|----------|
| **main** | 1 review required | **0 reviews required** | HIGH |
| **main** | CodeQL, CHIT, SQL checks | **No checks configured** | CRITICAL |
| **main** | Linear history | ✅ Enabled | - |
| **main** | Required signatures | ✅ Enabled | - |

---

## Recent Merge Analysis (PRs #887-#897)

**Finding:** ALL recent PRs merged directly to `main`, bypassing promotion flow.

| PR # | Title | Base Branch | Pattern |
|------|-------|-------------|----------|
| 897 | Z890 GPU node docs | **main** | Direct merge |
| 896 | Google Cast TTS | **main** | Direct merge |
| 895 | Hostinger Makefile | **main** | Direct merge |
| 894 | DEPLOYER agent form | **main** | Direct merge |
| 893 | CHIT HEADSCALE secrets | **main** | Direct merge |
| 892 | MCP configs | **main** | Direct merge |
| 890-887 | GitHub app features | **main** | Direct merge |

**Impact:** Security and quality gates in Hardened branch are being bypassed.

---

## Available CI Workflows

The required checks exist and are active:

```
✅ CodeQL (Advanced) - Active
✅ CodeQL (Legacy) - Active
✅ CHIT Contract Check - Active
✅ SQL Policy Lint - Active
```

**Issue:** These are not configured as required status checks on `main` branch protection.

---

## Action Items

### Priority 1: Fix Main Branch Protection (CRITICAL)

```bash
# Set required reviews on main
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection \
  -f required_pull_request_reviews='{
    "required_approving_review_count": 1
  }'

# Add required status checks
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection \
  -f required_status_checks='{
    "strict": true,
    "contexts": [
      "CodeQL",
      "CodeQL Advanced",
      "CHIT Contract Check",
      "SQL Policy Lint"
    ],
    "checks": [
      {"context": "CodeQL"},
      {"context": "CodeQL Advanced"},
      {"context": "CHIT Contract Check"},
      {"context": "SQL Policy Lint"}
    ]
  }'
```

**Result:** Enforces documented quality gates before merging to main.

### Priority 2: Create Promotion Helper Script

Create `pmoves/mk/promote.mk`:

```makefile
.PHONY: promote-to-integrations promote-to-hardened promote-to-main

# Feature → Integrations
promote-to-integrations:
	@echo "Creating PR to Integrations branch..."
	gh pr create \
		--base PMOVES.AI-Edition-Hardened-Integrations \
		--title "promote: $(shell git branch --show-current) → Integrations" \
		--body "Automated promotion via make target"

# Integrations → Hardened
promote-to-hardened:
	@echo "Creating promotion PR to Hardened branch..."
	gh pr create \
		--base PMOVES.AI-Edition-Hardened \
		--head PMOVES.AI-Edition-Hardened-Integrations \
		--title "promote: Integrations → Hardened" \
		--body "Full audit gate will run on this PR"

# Hardened → Main (Release)
promote-to-main:
	@echo "Creating release PR to main branch..."
	@read -p "Enter release version (e.g., v1.2.3): " version; \
	gh pr create \
		--base main \
		--head PMOVES.AI-Edition-Hardened \
		--title "release: $$version hardened → main" \
		--body "Production release. All gates must pass."
```

**Usage:**
```bash
make -C pmoves promote-to-integrations  # From feature branch
make -C pmoves promote-to-hardened      # From Integrations
make -C pmoves promote-to-main          # From Hardened
```

### Priority 3: Enforce PR Base Branch Validation

Create GitHub Action `.github/workflows/pr-base-check.yml`:

```yaml
name: PR Base Branch Validation

on:
  pull_request:
    types: [opened, edited]

permissions:
  pull-requests: write

jobs:
  validate-base-branch:
    runs-on: ubuntu-latest
    steps:
      - name: Check PR targets main
        if: github.base_ref == 'main'
        run: |
          echo "::error::Direct merges to main are not allowed."
          echo "::error::Please use the promotion flow: feature → Integrations → Hardened → main"
          exit 1

      - name: Check feature branch PRs
        if: github.head_ref != 'PMOVES.AI-Edition-Hardened' && github.head_ref != 'PMOVES.AI-Edition-Hardened-Integrations'
        run: |
          if [[ "${{ github.base_ref }}" != "PMOVES.AI-Edition-Hardened-Integrations" ]]; then
            echo "::warning::Feature branches should target Integrations, not ${{ github.base_ref }}"
          fi
```

### Priority 4: Clean Up Merged Branches

```bash
# Execute cleanup (3 merged branches identified)
make -C pmoves branch-cleanup EXECUTE=1
```

**Branches to delete:**
- `feat/n8n-postgres-control-plane` (merged)
- `feature/github-app-integration` (merged)
- `origin` (stale remote reference)

---

## Recommended Workflow Change

### Before (Current - Anti-Pattern)
```bash
# Developer workflow
git checkout -b feat/new-feature
# ... make changes ...
git push origin feat/new-feature
gh pr create --base main  # ❌ Bypasses gates
```

### After (Recommended)
```bash
# Developer workflow
git checkout -b feat/new-feature
# ... make changes ...
git push origin feat/new-feature
gh pr create --base PMOVES.AI-Edition-Hardened-Integrations  # ✅ CI gate

# After merge, PR admin promotes:
make -C pmoves promote-to-hardened  # ✅ Audit gate
# After review and merge:
make -C pmoves promote-to-main      # ✅ Release
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing workflow | Medium | Medium | Add transition period with warnings |
| PRs blocked on missing checks | High | Low | Checks already exist and pass |
| Team resistance to change | Medium | Medium | Document benefits, provide helper scripts |

---

## Success Metrics

- **Week 1:** Main branch protection updated, PR base validation active
- **Week 2:** 50% of PRs follow promotion flow
- **Week 3:** 100% of PRs follow promotion flow
- **Week 4:** Zero direct merges to main (except emergency fixes)

---

## References

- **Strategy Doc:** `pmoves/docs/BRANCH_STRATEGY.md`
- **CI Workflows:** `.github/workflows/`
- **Branch Audit:** `make -C pmoves branch-audit`
- **Cleanup Tool:** `pmoves/tools/branch_cleanup.py`

---

## Next Steps

1. **Immediate:** Update main branch protection rules
2. **Today:** Create promotion helper Makefile
3. **This Week:** Deploy PR base validation workflow
4. **Ongoing:** Monitor PR patterns and enforce compliance
