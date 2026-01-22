# PMOVES.AI Secrets Onboarding Guide

This guide helps you set up API keys and secrets for PMOVES.AI in under 5 minutes.

## Quick Start (5 Minutes)

### Option 1: Interactive Wizard (Recommended)

```bash
cd /path/to/PMOVES.AI/pmoves
make secrets-setup-wizard
```

The wizard will guide you through:
1. Selecting which LLM providers you use
2. Entering API keys (masked input)
3. Choosing optional integrations
4. Validating your keys
5. Saving to environment or CHIT format

### Option 2: Template Method

1. **Copy the template**:
   ```bash
   cp templates/secrets/user_keys.template.yaml user_keys.yaml
   ```

2. **Edit and fill in your keys**:
   ```bash
   nano user_keys.yaml  # or your preferred editor
   ```

3. **Import to environment**:
   ```bash
   make secrets-import < user_keys.yaml
   ```

### Option 3: Direct Environment Variables

Add to `pmoves/env.shared`:
```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Load into shell
source env.shared
```

## Required Secrets

You need at least **one LLM provider** to use PMOVES.AI:

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| **OpenAI** | No ($5 credit) | GPT-4, GPT-3.5 |
| **Anthropic** | Yes (limited) | Claude Opus, Sonnet |
| **Groq** | Yes | Fast inference |
| **Ollama** | Yes (local) | Privacy, no API calls |

### Getting Your First API Key

**OpenAI** (Recommended for beginners):
1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys > Create new secret key
4. Copy the key (starts with `sk-`)

**Anthropic** (Best for Claude):
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys > Create Key
4. Copy the key (starts with `sk-ant-`)

## Optional Integrations

### Media & Content

- **Jellyfin**: Media server integration
- **YouTube**: Video ingestion and transcription
- **Spotify**: Music integration

### Health & Fitness

- **Oura Ring**: Sleep tracking
- **Fitbit**: Activity tracking
- **Apple Health**: Health data sync

### Productivity

- **Notion**: Knowledge base integration
- **Todoist**: Task management
- **Trello**: Project boards

See `integrations.template.yaml` for all available integrations.

## CHIT Encoding (Backup & Transfer)

CHIT is PMOVES.AI's secure encoding format for secrets.

**Encode your secrets** (for backup):
```bash
make secrets-chit-encode < user_keys.yaml > secrets.chit
```

**Decode your secrets** (restore):
```bash
make secrets-chit-decode < secrets.chit > user_keys.yaml
```

**Why use CHIT?**
- Compressed and encrypted
- Easy to transfer between machines
- Safe to store in version control (encrypted)
- Supports password protection

## GitHub Secrets Setup

For GitHub Actions CI/CD:

1. Go to your repository on GitHub
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add secrets with `PMOVES_` prefix:

   | Name | Example Value |
   |------|---------------|
   | `PMOVES_OPENAI_API_KEY` | `sk-proj-...` |
   | `PMOVES_ANTHROPIC_API_KEY` | `sk-ant-...` |
   | `PMOVES_GOOGLE_API_KEY` | `AIza...` |

5. Reference in workflows:
   ```yaml
   env:
     OPENAI_API_KEY: ${{ secrets.PMOVES_OPENAI_API_KEY }}
   ```

See `docs/GITHUB_SECRETS_GUIDE.md` for complete guide.

## Docker Secrets Setup

For Docker Swarm or Kubernetes:

### Docker Swarm
```bash
echo "sk-..." | docker secret create openai_api_key -
```

In `docker-compose.yml`:
```yaml
services:
  agent-zero:
    secrets:
      - openai_api_key
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key

secrets:
  openai_api_key:
    external: true
```

### Kubernetes
```bash
kubectl create secret generic pmoves-secrets \
  --from-literal=openai-api-key='sk-...'
```

See `docs/DOCKER_SECRETS_GUIDE.md` for complete guide.

## Validation

Test that your secrets are working:

```bash
# Show loaded secrets
make secrets-show

# Validate API keys
make secrets-validate

# Test LLM connection
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Troubleshooting

### "API key not found"

**Cause**: Secrets not loaded into environment

**Solution**:
```bash
# Check if key is set
echo $OPENAI_API_KEY

# Reload environment
source pmoves/env.shared

# Or run import again
make secrets-import < user_keys.yaml
```

### "Invalid API key"

**Cause**: Incorrect key or wrong service

**Solution**:
- Verify no extra spaces in the key
- Check you're using the right key for the right service
- Ensure the key hasn't expired

### "Connection refused"

**Cause**: Service not running or wrong port

**Solution**:
```bash
# Check service status
make health

# Start the service
make up
```

## Security Best Practices

1. **Never commit secrets to git**
   - Keep `user_keys.yaml` in `.gitignore`
   - Use environment variables for production

2. **Rotate keys regularly**
   - Every 90 days for production
   - Immediately if compromised

3. **Use least privilege**
   - Only grant necessary permissions
   - Use read-only keys when possible

4. **Monitor usage**
   - Check API usage regularly
   - Set up alerts for unusual activity

## Next Steps

- **Set up integrations**: Configure optional services you use
- **CHIT encoding**: Encode secrets for backup
- **Production deployment**: Set up GitHub/Docker secrets

## See Also

- `templates/secrets/README.md` - Template documentation
- `docs/CHIT_USER_GUIDE.md` - CHIT encoding guide
- `docs/GITHUB_SECRETS_GUIDE.md` - GitHub Actions secrets
- `docs/DOCKER_SECRETS_GUIDE.md` - Docker/K8s secrets
