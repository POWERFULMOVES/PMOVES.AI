# Branch Protection Setup Instructions

**Created:** 2026-01-31
**Status:** PENDING USER ACTION
**Task:** 2.3 of Phase 2 Security Hardening Plan

---

## Quick Setup (15 minutes)

Navigate to:
```
https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches
```

Click **"Add branch protection rule"** and configure:

| Setting | Value |
|---------|-------|
| Branch name pattern | `main` |
| ✅ Require a pull request | **Enabled** |
| &nbsp;&nbsp;Approvals required | `1` |
| &nbsp;&nbsp;Dismiss stale reviews | Enabled |
| ✅ Require status checks | **Enabled** |
| &nbsp;&nbsp;Required checks | `tests, verify` |
| &nbsp;&nbsp;Require branches to be up to date | **Enabled** |
| ✅ Require conversation resolution | **Enabled** |
| ✅ Require signed commits | **Enabled** |
| ✅ Linear history | **Enabled** (Squash or Merge) |
| ✅ Apply to administrators | **ENABLED** |
| ❌ Lock branch | Disabled |
| ❌ Require deployments | Disabled |

---

## Validation

After configuring, test with a dummy PR:

```bash
# Create test branch
git checkout -b test/branch-protection-validation

# Make dummy change
echo "# test" > TEST.md

# Commit and push
git add TEST.md
git commit -m "test: validate branch protection"
git push origin test/branch-protection-validation

# Create PR via GitHub CLI
gh pr create --title "Test Branch Protection" --body "Validation PR"

# Expected: PR should require approval and checks to pass
```

---

## CODEOWNERS File

Already created at `.github/CODEOWNERS` with:
- CATACLYSM_STUDIOS_INC protection
- Security-critical path approvals
- Infrastructure change requirements

---

## References

- Phase 2 Task Breakdown: `/docs/phase2-task-breakdown.md`
- Skills Reference: `/docs/phase2-skills-reference.md`
