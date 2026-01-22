# PMOVES.AI Secrets Templates

This directory contains templates for setting up secrets and API keys for PMOVES.AI.

## Quick Start

1. **Copy the template**:
   ```bash
   cp templates/secrets/user_keys.template.yaml user_keys.yaml
   ```

2. **Fill in your API keys** in `user_keys.yaml`

3. **Import to environment**:
   ```bash
   # Load into shell environment
   make secrets-import < user_keys.yaml

   # Or encode to CHIT for backup
   make secrets-chit-encode < user_keys.yaml > secrets.chit
   ```

## Template Files

| File | Purpose |
|------|---------|
| `user_keys.template.yaml` | LLM providers, embeddings, search APIs |
| `integrations.template.yaml` | Third-party integrations (Jellyfin, Spotify, etc.) |

## Security Best Practices

- **NEVER commit filled secrets** to git
- Keep `user_keys.yaml` in `.gitignore`
- Use environment variables for production
- Rotate API keys regularly
- Use CHIT encoding for backup/transfer

## CHIT Encoding

CHIT (Compressed Hierarchical Information Transfer) is PMOVES.AI's secure encoding format for secrets.

**Encode secrets** (for backup/transfer):
```bash
make secrets-chit-encode < user_keys.yaml > secrets.chit
```

**Decode secrets**:
```bash
make secrets-chit-decode < secrets.chit > user_keys.yaml
```

## Environment Variables

For production deployment, set environment variables instead of using files:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
```

Or add to `pmoves/env.shared` (not committed to git):
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## GitHub Secrets

For GitHub Actions CI/CD, add secrets to repository settings:

1. Go to Repository > Settings > Secrets and variables > Actions
2. Add secrets with `PMOVES_` prefix:
   - `PMOVES_OPENAI_API_KEY`
   - `PMOVES_ANTHROPIC_API_KEY`
   - `PMOVES_GOOGLE_API_KEY`
   - etc.

## Required vs Optional Secrets

### Required (for core functionality)
- At least one LLM provider key (OpenAI, Anthropic, or local Ollama)
- Supabase credentials (if using Supabase backend)

### Optional (for specific features)
- Embedding providers (Voyage AI, or use built-in)
- Media integrations (Jellyfin, YouTube, Spotify)
- Communication (Discord, Slack, Telegram)
- Health/Fitness (Oura, Fitbit)

## Getting API Keys

### LLM Providers

| Provider | URL | Free Tier |
|----------|-----|-----------|
| OpenAI | https://platform.openai.com/api-keys | No ($5 credit) |
| Anthropic | https://console.anthropic.com/ | Yes (limited) |
| Google | https://makersuite.google.com/app/apikey | Yes |
| Groq | https://console.groq.com/ | Yes |
| OpenRouter | https://openrouter.ai/keys | No |

### Other Services

See individual service documentation for API key instructions.

## Troubleshooting

**"API key not found" error**:
- Check that secrets are loaded: `make secrets-show`
- Verify environment variables: `echo $OPENAI_API_KEY`

**"Invalid API key" error**:
- Verify the key is correct (no extra spaces)
- Check the key hasn't expired or been revoked
- Ensure you're using the right key for the right service

**Keys not persisting**:
- Make sure `user_keys.yaml` is not in `.gitignore` if you want it tracked (not recommended)
- Use `env.shared` for persistent local configuration
- For production, use GitHub/Docker secrets

## See Also

- `docs/SECRETS_ONBOARDING.md` - Complete onboarding guide
- `docs/CHIT_USER_GUIDE.md` - CHIT encoding documentation
- `docs/GITHUB_SECRETS_GUIDE.md` - GitHub Actions secrets setup
- `docs/DOCKER_SECRETS_GUIDE.md` - Docker/K8s secrets setup
