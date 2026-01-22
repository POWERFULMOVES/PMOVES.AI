# GitHub Environment Setup for PMOVES.AI

## Overview

This guide provides step-by-step instructions for setting up GitHub environments (Dev, Prod) and managing environment-scoped secrets for the PMOVES.AI project.

## Current Status

**Existing Environment:**
- `PMOVES` environment already exists (created 2025-11-10)
- **Action Required:** Create `Dev` and `Prod` environments

## Understanding GitHub Environments vs Repository Secrets

### Repository Secrets
- Available to all workflows in the repository
- No approval gates or protection rules
- Use for: Shared credentials, build tools, general-purpose API keys

### Environment Secrets
- Scoped to specific environments (Dev, Prod, etc.)
- Can require approval workflows before access
- Higher precedence than repository secrets
- Use for: Environment-specific credentials, deployment keys, production-only secrets

**Precedence Order:** Environment Secrets > Repository Secrets > Organization Secrets

## Step 1: Create GitHub Environments

### Option A: Using GitHub Web UI (Recommended)

1. Navigate to your repository: https://github.com/POWERFULMOVES/PMOVES.AI
2. Click **Settings** tab
3. In the left sidebar, click **Environments**
4. Click **New environment**
5. Enter environment name: `Dev`
6. Click **Configure environment**
7. (Optional) Configure protection rules:
   - **Wait timer**: Delay deployments (e.g., 0 minutes for Dev)
   - **Required reviewers**: Add team members who must approve deployments
   - **Deployment branches**: Restrict which branches can deploy to this environment
8. Click **Save protection rules**
9. Repeat steps 4-8 for `Prod` environment
   - For Prod, consider adding reviewers and a wait timer for safety

### Option B: Using GitHub CLI Extension

Install the `gh-environments` extension:

```bash
gh extension install katiem0/gh-environments
```

Create environments using the extension:

```bash
# Create Dev environment
gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/POWERFULMOVES/PMOVES.AI/environments/Dev

# Create Prod environment with protection rules
gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/POWERFULMOVES/PMOVES.AI/environments/Prod \
  -f wait_timer=30 \
  -F prevent_self_review=true
```

### Option C: Using Direct API Call

```bash
# Create Dev environment
curl -L \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/POWERFULMOVES/PMOVES.AI/environments/Dev \
  -d '{"prevent_self_review":false}'

# Create Prod environment with protection
curl -L \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/POWERFULMOVES/PMOVES.AI/environments/Prod \
  -d '{"wait_timer":30,"prevent_self_review":true}'
```

### Verify Environment Creation

```bash
# List all environments
gh api repos/POWERFULMOVES/PMOVES.AI/environments

# Check specific environment
gh api repos/POWERFULMOVES/PMOVES.AI/environments/Dev
gh api repos/POWERFULMOVES/PMOVES.AI/environments/Prod
```

## Step 2: Categorize Secrets

Based on the `secrets_manifest.yaml` analysis, here's the recommended secret categorization:

### Environment-Scoped Secrets (Different per Environment)

**Critical Production Secrets (Prod-only or different per environment):**
- `SUPABASE_URL` - Different endpoints for Dev/Prod
- `SUPABASE_ANON_KEY` - Different keys per environment
- `SUPABASE_SERVICE_ROLE_KEY` - Different keys per environment
- `SUPABASE_JWT_SECRET` - Different secrets per environment
- `POSTGRES_HOSTNAME` - Different database hosts
- `MINIO_USER` / `MINIO_PASSWORD` - Different storage credentials
- `OPEN_NOTEBOOK_API_URL` - Different notebook instances
- `OPEN_NOTEBOOK_API_TOKEN` - Different API tokens
- `JELLYFIN_URL` / `JELLYFIN_API_KEY` - Different media server instances
- `DISCORD_WEBHOOK_URL` - Separate webhook channels for Dev/Prod notifications

**Deployment & Infrastructure:**
- `GH_PAT_PUBLISH` - GitHub Personal Access Token for publishing
- `DOCKERHUB_PAT` / `DOCKERHUB_USERNAME` - Docker registry credentials
- `GHCR_USERNAME` - GitHub Container Registry username
- `HOSTINGER_API_TOKEN` / `HOSTINGER_SSH_*` - VPS deployment credentials

### Repository-Level Secrets (Shared Across All Environments)

**LLM Provider API Keys (same across environments):**
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `COHERE_API_KEY`
- `DEEPSEEK_API_KEY`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `MISTRAL_API_KEY`
- `OPENROUTER_API_KEY`
- `PERPLEXITYAI_API_KEY`
- `TOGETHER_AI_API_KEY`
- `VOYAGE_API_KEY`
- `XAI_API_KEY`
- `FIREWORKS_AI_API_KEY`

**Media & Content Processing:**
- `ELEVENLABS_API_KEY`
- `REPLICATE_API_TOKEN`
- `TINIFY_API_KEY`
- `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` / `CLOUDINARY_CLOUD_NAME`

**Integration Services:**
- `AIRTABLE_API_KEY` / `AIRTABLE_BASE_ID`
- `N8N_API_KEY` / `N8N_RUNNERS_AUTH_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `WGER_API_TOKEN`

**Security & Encryption:**
- `CHIT_PASSPHRASE` - Shared encryption key
- `VALID_API_KEYS` - API authentication tokens

## Step 3: Push Secrets to Environments

### Using the Existing Script

Once environments are created, use the `push-gh-secrets.sh` script:

```bash
# Push to Dev environment
./pmoves/tools/push-gh-secrets.sh \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Dev \
  --file pmoves/env.shared

# Push to Prod environment
./pmoves/tools/push-gh-secrets.sh \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Prod \
  --file pmoves/env.shared

# Push only specific secrets
./pmoves/tools/push-gh-secrets.sh \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Prod \
  --only SUPABASE_SERVICE_ROLE_KEY,SUPABASE_URL,POSTGRES_HOSTNAME

# Dry run to preview
./pmoves/tools/push-gh-secrets.sh \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Dev \
  --dry-run
```

### Using GitHub CLI Directly

```bash
# Set environment secret
echo "secret_value" | gh secret set SECRET_NAME \
  --repo POWERFULMOVES/PMOVES.AI \
  --app actions \
  --env Dev

# Set repository secret (no --env flag)
echo "secret_value" | gh secret set SECRET_NAME \
  --repo POWERFULMOVES/PMOVES.AI \
  --app actions
```

### Using gh-environments Extension

```bash
# Create secrets from CSV
gh environments secrets create POWERFULMOVES \
  -f dev-secrets.csv \
  PMOVES.AI

# CSV format: repository,environment,secret_name,secret_value
# Example: PMOVES.AI,Dev,SUPABASE_URL,https://dev.supabase.co
```

## Step 4: Verify Secret Configuration

```bash
# List environment secrets for Dev
gh secret list \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Dev

# List environment secrets for Prod
gh secret list \
  --repo POWERFULMOVES/PMOVES.AI \
  --env Prod

# List repository secrets
gh secret list \
  --repo POWERFULMOVES/PMOVES.AI
```

## Step 5: Update GitHub Actions Workflows

Modify your workflow files to use environments:

```yaml
name: Deploy to Dev
on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: Dev  # Specifies environment
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        env:
          # Environment secrets automatically available
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          echo "Deploying to Dev environment..."
```

## Best Practices

1. **Rotate Secrets Regularly**
   - Rotate environment secrets every 30-90 days
   - Use OIDC tokens instead of long-lived credentials where possible

2. **Use Minimum Permissions**
   - Grant least privilege access to secrets
   - Use environment-specific service accounts

3. **Environment Protection Rules**
   - **Dev:** Minimal protection, fast iteration
   - **Prod:** Required reviewers, wait timer, branch restrictions

4. **Secret Naming Conventions**
   - Use consistent naming: `SERVICE_CREDENTIAL_TYPE`
   - Example: `SUPABASE_SERVICE_ROLE_KEY`, not `SUPA_KEY`

5. **Documentation**
   - Document which secrets are environment-specific
   - Keep `secrets_manifest.yaml` updated
   - Track secret rotation schedules

6. **Audit Trail**
   - Monitor secret access in GitHub Actions logs
   - Review environment deployment history regularly

## Troubleshooting

### Error: "failed to fetch public key: HTTP 404"

**Cause:** Environment doesn't exist yet

**Solution:** Create the environment first using one of the methods in Step 1

### Error: "Resource not accessible by integration"

**Cause:** Insufficient permissions on GitHub token

**Solution:** Ensure your GitHub token has `repo` scope or use a token with admin permissions

### Secrets Not Available in Workflow

**Cause:** Workflow doesn't specify environment, or secret is in wrong scope

**Solution:** Add `environment: Dev` to your job definition in the workflow YAML

## Automated Setup Script

For convenience, here's a complete setup script:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="POWERFULMOVES/PMOVES.AI"

echo "Creating GitHub environments..."

# Create Dev environment
gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/$REPO/environments/Dev

# Create Prod environment with protection
gh api --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/$REPO/environments/Prod \
  -f wait_timer=30 \
  -F prevent_self_review=true

echo "Environments created successfully!"

# Verify
echo "Listing environments:"
gh api repos/$REPO/environments | jq -r '.environments[].name'

echo ""
echo "Next steps:"
echo "1. Run: ./pmoves/tools/push-gh-secrets.sh --env Dev --file pmoves/env.shared"
echo "2. Run: ./pmoves/tools/push-gh-secrets.sh --env Prod --file pmoves/env.shared"
```

Save this as `/home/pmoves/PMOVES.AI/pmoves/tools/setup-gh-environments.sh` and run:

```bash
chmod +x /home/pmoves/PMOVES.AI/pmoves/tools/setup-gh-environments.sh
./pmoves/tools/setup-gh-environments.sh
```

## References

- [GitHub REST API - Deployment Environments](https://docs.github.com/en/rest/deployments/environments)
- [GitHub Actions - Using Secrets](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions)
- [Managing Environments for Deployment](https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Best Practices for Managing Secrets in GitHub Actions](https://www.blacksmith.sh/blog/best-practices-for-managing-secrets-in-github-actions)
- [GitHub CLI Extension: gh-environments](https://github.com/katiem0/gh-environments)
- [GitHub Secrets: The Basics and Best Practices](https://configu.com/blog/github-secrets-the-basics-and-4-critical-best-practices/)
- [GitHub Actions Secrets and Variables Guide](https://medium.com/@morepravin1989/github-actions-secrets-and-variables-understanding-repository-and-environment-secrets-for-2b2eed404222)

## Summary

**Required Actions:**
1. Create `Dev` and `Prod` environments (UI or CLI)
2. Categorize secrets as environment-scoped vs repository-scoped
3. Push secrets using `push-gh-secrets.sh` with `--env` flag
4. Update workflows to specify `environment:` in job definitions
5. Configure protection rules for Prod environment

**Key Insight:** The 404 error occurs because environments must be created BEFORE secrets can be pushed to them. GitHub's API requires the environment resource to exist first.
