# GitHub Secrets Guide for PMOVES.AI

This guide covers setting up and using GitHub Secrets for PMOVES.AI CI/CD pipelines.

## Overview

GitHub Secrets allow you to store sensitive information (API keys, passwords, tokens) securely and use them in GitHub Actions workflows.

## Quick Setup

### 1. Navigate to Repository Secrets

1. Go to your repository on GitHub
2. Click **Settings** tab
3. In left sidebar, click **Secrets and variables** > **Actions**
4. Click **New repository secret**

### 2. Add Required Secrets

Add secrets with the `PMOVES_` prefix:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `PMOVES_OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `PMOVES_ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `PMOVES_GOOGLE_API_KEY` | Google API key | `AIza...` |
| `PMOVES_SUPABASE_URL` | Supabase URL | `https://xxx.supabase.co` |
| `PMOVES_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJ...` |

### 3. Reference in Workflows

In `.github/workflows/deploy.yml`:

```yaml
name: Deploy PMOVES.AI

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy services
        env:
          OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.PMOVES_ANTHROPIC_API_KEY }}
          SUPABASE_URL: ${{ secrets.PMOVES_SUPABASE_URL }}
        run: |
          make deploy
```

## Workflow Examples

### LLM Provider Configuration

```yaml
name: Test LLM Integration

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Test OpenAI
        if: secrets.PMOVES_OPENAI_API_KEY != ''
        env:
          OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
        run: |
          pytest tests/test_openai.py

      - name: Test Anthropic
        if: secrets.PMOVES_ANTHROPIC_API_KEY != ''
        env:
          ANTHROPIC_API_KEY: ${{ secrets.PMOVES_ANTHROPIC_API_KEY }}
        run: |
          pytest tests/test_anthropic.py
```

### Docker Build with Secrets

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build image
        env:
          # Build-time secrets
          OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
        run: |
          docker build \
            --build-arg OPENAI_API_KEY \
            -t ghcr.io/${{ github.repository }}:latest \
            .

      - name: Push image
        run: |
          docker push ghcr.io/${{ github.repository }}:latest
```

### Multi-Environment Deployment

```yaml
name: Deploy

on:
  workflow_dispatch:
    inputs:
      environment:
        required: true
        type: choice
        options:
          - dev
          - staging
          - production

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to ${{ inputs.environment }}
        env:
          # Environment-specific secrets
          OPENAI_API_KEY: ${{ secrets[format('PMOVES_{0}_OPENAI_API_KEY', inputs.environment)] || secrets.PMOVES_OPENAI_API_KEY }}
        run: |
          make deploy ENV=${{ inputs.environment }}
```

## Secret Names Reference

### LLM Providers

```bash
PMOVES_OPENAI_API_KEY          # OpenAI
PMOVES_ANTHROPIC_API_KEY       # Anthropic Claude
PMOVES_GOOGLE_API_KEY          # Google Gemini
PMOVES_GROQ_API_KEY            # Groq
PMOVES_OPENROUTER_API_KEY      # OpenRouter
PMOVES_COHERE_API_KEY          # Cohere
PMOVES_MISTRAL_API_KEY         # Mistral AI
PMOVES_DEEPSEEK_API_KEY        # DeepSeek
PMOVES_TOGETHER_AI_API_KEY     # Together AI
PMOVES_FIREWORKS_AI_API_KEY    # Fireworks AI
```

### Database & Storage

```bash
PMOVES_SUPABASE_URL            # Supabase URL
PMOVES_SUPABASE_ANON_KEY       # Supabase anon key
PMOVES_SUPABASE_SERVICE_KEY    # Supabase service key
PMOVES_POSTGRES_URL            # PostgreSQL URL
PMOVES_MONGODB_URI             # MongoDB URI
PMOVES_REDIS_URL               # Redis URL
```

### Cloud Services

```bash
PMOVES_AWS_ACCESS_KEY_ID       # AWS access key
PMOVES_AWS_SECRET_ACCESS_KEY   # AWS secret key
PMOVES_AWS_REGION              # AWS region
PMOVES_GCP_CREDENTIALS         # GCP credentials (JSON)
PMOVES_AZURE_CLIENT_ID         # Azure client ID
PMOVES_AZURE_CLIENT_SECRET     # Azure client secret
```

### Monitoring & Observability

```bash
PMOVES_SENTRY_DSN              # Sentry DSN
PMOVES_DATADOG_API_KEY         # Datadog API key
PMOVES_NEWRELIC_LICENSE_KEY    # New Relic license key
PMOVES_HONEYCOMB_API_KEY       # Honeycomb API key
```

### Integration Services

```bash
PMOVES_DISCORD_WEBHOOK_URL     # Discord webhook
PMOVES_SLACK_BOT_TOKEN         # Slack bot token
PMOVES_TELEGRAM_BOT_TOKEN      # Telegram bot token
PMOVES_JELLYFIN_API_KEY        # Jellyfin API key
PMOVES_SPOTIFY_CLIENT_ID       # Spotify client ID
PMOVES_SPOTIFY_CLIENT_SECRET   # Spotify client secret
```

## Environment-Specific Secrets

For multi-environment setups, prefix with environment:

```bash
# Development
PMOVES_DEV_OPENAI_API_KEY
PMOVES_DEV_SUPABASE_URL

# Staging
PMOVES_STAGING_OPENAI_API_KEY
PMOVES_STAGING_SUPABASE_URL

# Production
PMOVES_PROD_OPENAI_API_KEY
PMOVES_PROD_SUPABASE_URL
```

Reference in workflows:
```yaml
env:
  OPENAI_API_KEY: ${{ secrets[format('PMOVES_{0}_OPENAI_API_KEY', github.ref_name)] }}
```

## Organization Secrets

For shared secrets across repositories:

1. Go to Organization **Settings**
2. Navigate to **Secrets** > **Actions**
3. Click **New organization secret**

Set repository access:
- **All repositories**: All repos can access
- **Selected repositories**: Only specific repos

Use same as repository secrets:
```yaml
env:
  OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
```

## Best Practices

### 1. Naming Convention

Use consistent prefixing:
- `PMOVES_` prefix for all PMOVES.AI secrets
- Environment prefix for multi-env: `PMOVES_DEV_`, `PMOVES_PROD_`
- Service-specific: `PMOVES_OPENAI_API_KEY` (not just `API_KEY`)

### 2. Secret Rotation

Rotate secrets regularly:
1. Create new secret (e.g., `PMOVES_OPENAI_API_KEY_V2`)
2. Update workflow to use new secret
3. Deploy and verify
4. Delete old secret

### 3. Least Privilege

- Use service accounts with minimal permissions
- Rotate compromised keys immediately
- Use different keys for dev/prod

### 4. Validation

Validate secrets in workflow:
```yaml
- name: Validate secrets
  env:
    OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
  run: |
    if [[ -z "$OPENAI_API_KEY" ]]; then
      echo "Error: OPENAI_API_KEY not set"
      exit 1
    fi
```

## Troubleshooting

### Secret not accessible

**Error**: `The secret 'PMOVES_XXX' is not set`

**Solutions**:
1. Verify secret name exactly matches (case-sensitive)
2. Check secret is set in correct scope (repo/org)
3. Ensure workflow has access to secret

### Secret value truncated

**Cause**: GitHub masks secrets in logs

**Solution**: This is expected behavior. Secrets are never shown in logs.

### Secret not updating

**Cause**: Caching or old values

**Solution**:
1. Verify secret value in GitHub UI
2. Re-run workflow with fresh token
3. Check for environment override

## Migration from Files to Secrets

If you currently use `env.shared`:

```bash
# Extract keys to GitHub secrets format
make secrets-chit-decode < user_keys.yaml | grep -E "^[A-Z]" | while read line; do
  key=$(echo $line | cut -d= -f1)
  value=$(echo $line | cut -d= -f2)
  echo "PMOVES_${key}=${value}"
done
```

Add each to GitHub Secrets, then update workflow:
```yaml
env:
  # Load all PMOVES secrets
  OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
  # ... etc
```

## See Also

- `docs/SECRETS_ONBOARDING.md` - General secrets setup
- `docs/DOCKER_SECRETS_GUIDE.md` - Docker/K8s secrets
- `docs/CHIT_USER_GUIDE.md` - CHIT encoding for backup
