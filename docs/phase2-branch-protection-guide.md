# Phase 2 Task 2.3: Branch Protection Rules Implementation Guide

**Status:** Ready to implement (15-minute task)
**Priority:** HIGH (Quick win - foundational security control)
**Effort:** 15 minutes via GitHub UI
**Date:** 2025-12-06

## Overview

Branch protection rules are a critical security control that enforces code review requirements, prevents force pushes, and ensures all changes go through the CI/CD pipeline before merging to main.

## Prerequisites

- GitHub repository admin access
- Existing CI/CD workflows configured:
  - `python-tests.yml` (Python Tests)
  - `chit-contract.yml` (CHIT Contract Check)

## Implementation Steps

### Step 1: Navigate to Branch Protection Settings

1. Open your browser and navigate to:
   ```
   https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches
   ```

2. Click the **"Add branch protection rule"** button

3. In the **"Branch name pattern"** field, enter:
   ```
   main
   ```

### Step 2: Configure Protection Rules

Enable the following settings exactly as specified:

#### 2.1 Pull Request Requirements

**✅ Require a pull request before merging**
- **Required approvals:** `1`
- **✅ Dismiss stale pull request approvals when new commits are pushed**
- **✅ Require review from Code Owners**
  - Note: Create a `.github/CODEOWNERS` file if not present (see Step 4)

#### 2.2 Status Checks

**✅ Require status checks to pass before merging**
- **✅ Require branches to be up to date before merging**
- **Required status checks:**
  - Search and select: `tests` (from Python Tests workflow)
  - Search and select: `verify` (from CHIT Contract Check workflow)

  *Note: These checks must have run at least once to appear in the dropdown*

#### 2.3 Conversation Resolution

**✅ Require conversation resolution before merging**

#### 2.4 Commit Signing

**✅ Require signed commits**

*Note: This ensures all commits are cryptographically signed. Contributors will need to set up GPG signing:*
```bash
git config --global commit.gpgsign true
```

#### 2.5 History Requirements

**✅ Require linear history**

This prevents merge commits and enforces either:
- Squash merging
- Rebase merging
- Fast-forward only

Recommended: Configure repository to allow only "Squash and merge" in Settings → Pull Requests.

#### 2.6 Administrator Enforcement

**✅ Do not allow bypassing the above settings**
- **✅ Apply rules to administrators**

This ensures even repository admins must follow the same rules.

#### 2.7 Settings to LEAVE DISABLED

**❌ Lock branch** - Leave unchecked (would prevent all pushes)
**❌ Require deployments to succeed** - Leave unchecked (not applicable)
**❌ Restrict who can push** - Leave unchecked (PR review provides sufficient control)

### Step 3: Save Configuration

1. Scroll to the bottom of the page
2. Click **"Create"** or **"Save changes"**

### Step 4: Create CODEOWNERS File (If Not Present)

If you don't have a `.github/CODEOWNERS` file, create one:

```bash
# File: .github/CODEOWNERS
# Default code owners for the repository
* @POWERFULMOVES/pmoves-core-team

# Critical infrastructure files require additional review
/.github/workflows/ @POWERFULMOVES/devops-team
/pmoves/docker-compose*.yml @POWERFULMOVES/devops-team
/deploy/ @POWERFULMOVES/devops-team
/pmoves/services/ @POWERFULMOVES/backend-team

# Security-sensitive files
/.env* @POWERFULMOVES/security-team
/pmoves/env.* @POWERFULMOVES/security-team
/docs/SECRETS*.md @POWERFULMOVES/security-team
```

**Note:** Replace team slugs with your actual GitHub team names or individual usernames (e.g., `@username`).

## Validation Procedure

### Test 1: Direct Push to Main (Should Fail)

1. Create a test change on your local main branch:
   ```bash
   echo "test" > test-branch-protection.txt
   git add test-branch-protection.txt
   git commit -m "test: verify branch protection"
   git push origin main
   ```

2. **Expected result:**
   ```
   ! [remote rejected] main -> main (protected branch hook declined)
   error: failed to push some refs to 'github.com:POWERFULMOVES/PMOVES.AI.git'
   ```

3. Clean up:
   ```bash
   git reset --hard HEAD~1
   ```

### Test 2: Create PR Without Approval (Should Block Merge)

1. Create a test branch:
   ```bash
   git checkout -b test-branch-protection
   echo "test" > test-file.txt
   git add test-file.txt
   git commit -m "test: verify PR requirements"
   git push origin test-branch-protection
   ```

2. Open a PR to main via GitHub UI

3. **Expected behavior:**
   - Merge button should be disabled
   - Status message: "Merging is blocked"
   - Required checks must pass (tests, verify)
   - Requires 1 approving review

4. Have another team member review and approve

5. After approval and passing checks, merge button should become available

6. Clean up:
   ```bash
   git checkout main
   git branch -D test-branch-protection
   git push origin --delete test-branch-protection
   ```

### Test 3: Attempt Force Push (Should Fail)

1. Make a commit and attempt force push:
   ```bash
   git checkout -b test-force-push
   echo "test" > test-force.txt
   git add test-force.txt
   git commit -m "test: verify force push protection"
   git push origin test-force-push

   # Amend the commit
   git commit --amend -m "test: amended commit"
   git push --force origin test-force-push
   ```

2. **Expected result:**
   - Force push to main should be rejected
   - Force push to feature branch should succeed (branches other than main)

3. Clean up:
   ```bash
   git checkout main
   git branch -D test-force-push
   git push origin --delete test-force-push
   ```

## Expected Workflow After Implementation

### For Contributors

1. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -S -m "feat: add new feature"  # Note: -S for signed commit
   ```

3. **Push to remote:**
   ```bash
   git push origin feature/my-feature
   ```

4. **Open PR on GitHub:**
   - Navigate to repository
   - Click "Pull requests" → "New pull request"
   - Select `base: main` ← `compare: feature/my-feature`
   - Fill in PR description
   - Submit

5. **Wait for CI/CD:**
   - All required checks must pass (tests, verify)
   - Address any failures by pushing new commits to the branch

6. **Request review:**
   - Assign reviewers
   - Wait for at least 1 approval

7. **Merge:**
   - After approval + passing checks, click "Squash and merge"
   - Delete branch after merge

### For Reviewers

1. **Review code changes**
2. **Test locally if needed**
3. **Request changes or approve**
4. **Ensure conversations are resolved before approving**

## GPG Commit Signing Setup

Branch protection now requires signed commits. Contributors must set up GPG signing:

### Generate GPG Key

```bash
gpg --full-generate-key
# Choose: RSA and RSA, 4096 bits, no expiration
# Enter your name and GitHub email
```

### Add GPG Key to GitHub

1. List your GPG key:
   ```bash
   gpg --list-secret-keys --keyid-format=long
   ```

2. Export public key:
   ```bash
   gpg --armor --export YOUR_KEY_ID
   ```

3. Go to GitHub Settings → SSH and GPG keys → New GPG key
4. Paste the public key

### Configure Git

```bash
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true
```

### Verify Signing

```bash
git commit -S -m "test: signed commit"
git log --show-signature -1
```

## Troubleshooting

### Issue: Required checks don't appear in dropdown

**Solution:**
- The workflows must run at least once before they appear
- Trigger workflows manually via Actions tab
- Or make a test PR to trigger them

### Issue: Can't push signed commits (GPG error)

**Solution:**
```bash
# Set GPG_TTY environment variable
export GPG_TTY=$(tty)
echo 'export GPG_TTY=$(tty)' >> ~/.bashrc

# Test GPG signing
echo "test" | gpg --clearsign
```

### Issue: CODEOWNERS team doesn't exist

**Solution:**
- Replace team slugs with individual usernames: `@username`
- Or create GitHub teams in your organization

### Issue: Accidentally locked out of main branch

**Solution:**
- As admin, go to Settings → Branches
- Edit the branch protection rule
- Temporarily disable "Do not allow bypassing"
- Make necessary changes
- Re-enable the setting

## Rollback Procedure

If you need to remove branch protection:

1. Go to: `https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches`
2. Find the `main` branch rule
3. Click **"Delete"**
4. Confirm deletion

**Warning:** Only do this in emergencies. Branch protection is a critical security control.

## Security Benefits

✅ **Prevents unauthorized changes** - All code must be reviewed
✅ **Ensures CI/CD compliance** - All tests must pass before merge
✅ **Maintains audit trail** - All changes are documented in PRs
✅ **Enforces code signing** - Cryptographic proof of authorship
✅ **Prevents history rewriting** - Linear history prevents force pushes
✅ **Requires conversation resolution** - All review comments addressed

## Next Steps

After implementing branch protection:

1. ✅ **Communicate to team** - Send email/Slack about new workflow
2. ✅ **Update documentation** - Add to contributing guide
3. ✅ **Test thoroughly** - Run through validation procedure
4. ✅ **Monitor** - Watch for issues in first week
5. ✅ **Train team** - Help contributors set up GPG signing

## Related Documentation

- [Phase 2 Security Hardening Plan](./phase2-security-hardening-plan.md) (when created)
- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
- [GPG Signing Guide](https://docs.github.com/en/authentication/managing-commit-signature-verification)

## Status Tracking

- [ ] Branch protection rule created
- [ ] CODEOWNERS file created
- [ ] Validation tests passed
- [ ] Team notified
- [ ] GPG signing setup documented
- [ ] First test PR merged successfully

---

**Implementation Time:** 15 minutes
**Total Effort Saved:** Prevents countless hours of incident response
**Security Impact:** HIGH - Critical foundational control
**Maintenance:** None required after initial setup
