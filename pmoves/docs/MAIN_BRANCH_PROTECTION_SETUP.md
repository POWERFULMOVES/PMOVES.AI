# Main Branch Protection Setup Guide

**Purpose:** Configure main branch protection to match documented security and quality gates.

**Date:** 2026-03-13
**Priority:** CRITICAL

---

## Current State vs Required State

### ❌ Current Configuration
```json
{
  "required_approving_review_count": 0,
  "required_status_checks": {
    "contexts": [],
    "strict": true
  }
}
```

### ✅ Required Configuration
```json
{
  "required_approving_review_count": 1,
  "required_status_checks": {
    "contexts": [
      "CodeQL",
      "CodeQL Advanced",
      "CHIT Contract Check",
      "SQL Policy Lint"
    ],
    "strict": true
  }
}
```

---

## Automated Setup (Recommended)

### Option 1: Using GitHub CLI

```bash
# Set required reviews (1 approval required)
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection \
  -f required_pull_request_reviews='{
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
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
    ]
  }'

# Verify configuration
gh api repos/POWERFULMOVES/PMOVES.AI/branches/main/protection
```

### Option 2: Using Make Target

```bash
# Run the setup script
make -C pmoves main-branch-protection-setup
```

---

## Manual Setup (GitHub UI)

### Step 1: Navigate to Branch Settings

1. Go to: https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches
2. Find `main` branch
3. Click "Edit" or "+ Add rule"

### Step 2: Configure Basic Settings

- ✅ **Require a pull request before merging**
  - ✅ **Require approvals** = 1
  - ❌ Dismiss stale reviews = unchecked
  - ❌ Require review from CODEOWNERS = unchecked
  - ❌ Require last push approval = unchecked

- ✅ **Require status checks to pass before merging**
  - ✅ **Require branches to be up to date before merging**
  - Add required checks:
    - `CodeQL`
    - `CodeQL Advanced`
    - `CHIT Contract Check`
    - `SQL Policy Lint`

- ✅ **Require linear history**
- ✅ **Require signed commits**

### Step 3: Save Changes

Click "Create" or "Save changes"

---

## Verification

### Check Current Protection Rules

```bash
gh api repos/POWERFULMOVES/PMOVES.AI/branches/main/protection --jq '.'
```

### Expected Output

```json
{
  "required_linear_history": {"enabled": true},
  "required_signatures": {"enabled": true},
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "CodeQL",
      "CodeQL Advanced",
      "CHIT Contract Check",
      "SQL Policy Lint"
    ]
  }
}
```

### Test with a PR

```bash
# Create test PR
git checkout -b test/main-protection
echo "# Test" > test.md
git add test.md
git commit -m "test: verify main branch protection"
git push origin test/main-protection

# Try to create PR targeting main
gh pr create --base main --title "test: main protection"

# Should show: "1 approval required" and "4 checks required"
```

---

## Rollback (If Needed)

### Remove All Restrictions

```bash
gh api \
  --method DELETE \
  -H "Accept: application/vnd.github+json" \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection
```

### Restore Previous Configuration

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  repos/POWERFULMOVES/PMOVES.AI/branches/main/protection \
  -d '{
    "required_pull_request_reviews": {
      "required_approving_review_count": 0
    },
    "required_status_checks": {
      "strict": true,
      "contexts": []
    },
    "enforce_admins": false,
    "required_linear_history": true,
    "required_signatures": true
  }'
```

---

## Troubleshooting

### Issue: PRs blocked unexpectedly

**Cause:** Required checks not passing
**Solution:** Check workflow runs and fix issues

```bash
gh run list --workflow=CodeQL
gh run list --workflow="CHIT Contract Check"
gh run list --workflow="SQL Policy Lint"
```

### Issue: Maintainer bypass not working

**Cause:** `enforce_admins` is disabled (correct state)
**Solution:** Use `--admin` flag for emergency merges

```bash
gh pr merge <pr-number> --admin --merge
```

### Issue: Workflow names don't match

**Cause:** Check names changed
**Solution:** Update protection rules with current check names

```bash
gh run list --limit 50 | grep -E "(CodeQL|CHIT|SQL)"
```

---

## References

- **Branch Strategy:** `pmoves/docs/BRANCH_STRATEGY.md`
- **Implementation Report:** `pmoves/docs/BRANCH_STRATEGY_IMPLEMENTATION_REPORT.md`
- **CI Workflows:** `.github/workflows/`
- **GitHub Branch Protection API:** https://docs.github.com/en/rest/branches/branch-protection

---

## Success Criteria

✅ Main branch requires 1 approval before merge
✅ Main branch requires 4 CI checks to pass
✅ Linear history enforced
✅ Signed commits enforced
✅ No direct pushes allowed
✅ Test PR validates all restrictions

---

**Next Steps:**
1. Run automated setup script OR configure manually via UI
2. Verify with test PR
3. Monitor for 1 week
4. Document any issues in `pmoves/docs/BRANCH_STRATEGY_IMPLEMENTATION_REPORT.md`
