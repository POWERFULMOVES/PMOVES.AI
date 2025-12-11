# GitHub Secrets Quick Start Guide

## Problem Statement

The `push-gh-secrets.sh` script fails with:
```
failed to fetch public key: HTTP 404: Not Found
(https://api.github.com/repos/POWERFULMOVES/PMOVES.AI/environments/Dev/secrets/public-key)
```

**Root Cause:** GitHub environments `Dev` and `Prod` don't exist yet. Environments must be created before secrets can be pushed to them.

## Quick Fix (3 Steps)

### Step 1: Create Environments

Run the automated setup script:

```bash
./pmoves/tools/setup-gh-environments.sh
```

Or manually via GitHub CLI:

```bash
# Create Dev environment
gh api --method PUT /repos/POWERFULMOVES/PMOVES.AI/environments/Dev

# Create Prod environment with protection
gh api --method PUT /repos/POWERFULMOVES/PMOVES.AI/environments/Prod \
  -f wait_timer=30 -F prevent_self_review=true
```

Or via GitHub UI:
1. Go to https://github.com/POWERFULMOVES/PMOVES.AI/settings/environments
2. Click "New environment"
3. Enter "Dev", then click "Configure environment"
4. Repeat for "Prod"

### Step 2: Push Secrets

**Option A: Smart Categorized Push (Recommended)**

```bash
# Push Dev environment secrets (automatically categorized)
./pmoves/tools/push-categorized-secrets.sh --env Dev

# Push Prod environment secrets (automatically categorized)
./pmoves/tools/push-categorized-secrets.sh --env Prod

# Push repository-level secrets only
./pmoves/tools/push-categorized-secrets.sh --env none
```

**Option B: Manual Push with Existing Script**

```bash
# Push to Dev
./pmoves/tools/push-gh-secrets.sh --env Dev --file pmoves/env.shared

# Push to Prod
./pmoves/tools/push-gh-secrets.sh --env Prod --file pmoves/env.shared

# Push specific secrets only
./pmoves/tools/push-gh-secrets.sh --env Prod \
  --only SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY
```

### Step 3: Verify

```bash
# List environments
gh api repos/POWERFULMOVES/PMOVES.AI/environments | jq -r '.environments[].name'

# List Dev secrets
gh secret list --repo POWERFULMOVES/PMOVES.AI --env Dev

# List Prod secrets
gh secret list --repo POWERFULMOVES/PMOVES.AI --env Prod

# List repository secrets
gh secret list --repo POWERFULMOVES/PMOVES.AI
```

## Understanding the Setup

### What's Been Created

1. **Scripts:**
   - `/home/pmoves/PMOVES.AI/pmoves/tools/setup-gh-environments.sh` - Creates environments
   - `/home/pmoves/PMOVES.AI/pmoves/tools/push-categorized-secrets.sh` - Smart secret pusher
   - `/home/pmoves/PMOVES.AI/pmoves/tools/push-gh-secrets.sh` - Original secret pusher (still works)

2. **Documentation:**
   - `/home/pmoves/PMOVES.AI/docs/github-environment-setup.md` - Comprehensive guide
   - `/home/pmoves/PMOVES.AI/pmoves/chit/secrets_categorization.yaml` - Secret categories

### Secret Categories

**Environment Secrets (Different per Dev/Prod):**
- Database credentials: `SUPABASE_URL`, `POSTGRES_HOSTNAME`, etc.
- Storage: `MINIO_USER`, `MINIO_PASSWORD`
- Infrastructure: `JELLYFIN_URL`, `OPEN_NOTEBOOK_API_URL`
- Deployment: `GH_PAT_PUBLISH`, `DOCKERHUB_PAT`
- Notifications: `DISCORD_WEBHOOK_URL`

**Repository Secrets (Same everywhere):**
- LLM APIs: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
- External services: `ELEVENLABS_API_KEY`, `REPLICATE_API_TOKEN`
- Security: `CHIT_PASSPHRASE`, `VALID_API_KEYS`

### Environment Protection Rules

**Dev Environment:**
- No wait timer (fast iteration)
- No required reviewers
- Open to all branches

**Prod Environment:**
- 30-minute wait timer
- Self-review prevention enabled
- Should add required reviewers (manual step)

## Common Tasks

### Update a Single Secret

```bash
# Update environment secret
echo "new_value" | gh secret set SECRET_NAME \
  --repo POWERFULMOVES/PMOVES.AI --env Prod

# Update repository secret
echo "new_value" | gh secret set SECRET_NAME \
  --repo POWERFULMOVES/PMOVES.AI
```

### Delete a Secret

```bash
# Delete from environment
gh secret delete SECRET_NAME --repo POWERFULMOVES/PMOVES.AI --env Dev

# Delete from repository
gh secret delete SECRET_NAME --repo POWERFULMOVES/PMOVES.AI
```

### Dry Run Before Pushing

```bash
# Preview what would be pushed
./pmoves/tools/push-categorized-secrets.sh --env Dev --dry-run
./pmoves/tools/push-gh-secrets.sh --env Prod --dry-run
```

## Using Environments in Workflows

```yaml
name: Deploy to Production
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: Prod  # <-- This line enables environment secrets
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        env:
          # Environment secret (Prod-specific value)
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          # Repository secret (same everywhere)
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          echo "Deploying with Prod credentials..."
```

## Troubleshooting

### "Environment not found" Error

**Solution:** Create the environment first using `setup-gh-environments.sh`

### "Resource not accessible by integration"

**Solution:** Check your GitHub token has `repo` scope:
```bash
gh auth status
gh auth refresh -s repo
```

### Secret Not Available in Workflow

**Solution:** Add `environment: EnvName` to your job definition

### Need to Check Current Environments

```bash
gh api repos/POWERFULMOVES/PMOVES.AI/environments | jq
```

## Advanced: Add Required Reviewers to Prod

```bash
# Add user as reviewer (need user ID)
gh api --method PUT /repos/POWERFULMOVES/PMOVES.AI/environments/Prod \
  -f reviewers='[{"type":"User","id":YOUR_USER_ID}]'

# Or use GitHub UI:
# Settings → Environments → Prod → Required reviewers → Add
```

## Best Practices Checklist

- [ ] Environments created (Dev, Prod)
- [ ] Prod environment has protection rules
- [ ] Environment secrets pushed to Dev
- [ ] Environment secrets pushed to Prod
- [ ] Repository secrets pushed
- [ ] Secrets verified with `gh secret list`
- [ ] Workflows updated to use `environment:` directive
- [ ] Prod environment has required reviewers (optional but recommended)
- [ ] Secret rotation schedule documented

## Additional Resources

See `/home/pmoves/PMOVES.AI/docs/github-environment-setup.md` for comprehensive documentation including:
- Detailed API reference
- Secret categorization rationale
- Protection rules configuration
- Security best practices
- Rotation schedules

## Summary

**The 404 error happens because:**
GitHub environments must exist before secrets can be pushed to them.

**The fix:**
1. Create environments: `./pmoves/tools/setup-gh-environments.sh`
2. Push secrets: `./pmoves/tools/push-categorized-secrets.sh --env Dev`
3. Verify: `gh secret list --env Dev`

That's it!
