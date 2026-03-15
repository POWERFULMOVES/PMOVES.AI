# GitHub App Local Setup Guide

**Version:** 1.0
**Date:** 2026-03-12
**Status:** Active

---

## Overview

This guide explains how to configure GitHub App credentials for local development and runtime services. The PMOVES.AI GitHub App enables:

- CI/CD GHCR authentication
- Runtime token minting for Archon work orders
- BoTZ MCP GitHub server integration
- Agent Zero GitHub tool access

---

## Prerequisites

- gh CLI installed and authenticated
- Access to POWERFULMOVES/PMOVES.AI repository
- GitHub App secrets configured in Actions

---

## Quick Setup

### Method 1: Interactive Script (Recommended)

```bash
cd pmoves
bash scripts/github_app_setup.sh
```

This script:
1. Checks GitHub Secrets availability
2. Provides step-by-step instructions
3. Validates env.shared configuration

### Method 2: Manual Setup

1. **Get credentials from GitHub Secrets:**
   ```bash
   gh secret list --repo POWERFULMOVES/PMOVES.AI
   ```

2. **Download PEM private key:**
   - Go to: https://github.com/organizations/POWERFULMOVES/settings/apps/pmoves-ai
   - Download private key PEM file
   - Copy contents to clipboard (preserve newlines!)

3. **Add to pmoves/env.shared:**
   ```bash
   # Edit pmoves/env.shared and add:
   GH_APP_ID=<your-app-id>
   GH_APP_CLIENT_ID=<your-client-id>  # Optional
   GH_APP_SEC=<paste-PEM-contents-here>
   GH_APP_INSTALLATION_ID=<your-installation-id>
   ```

4. **Verify PEM formatting:**
   - Ensure newlines are preserved (no \n escapes)
   - File should start with `-----BEGIN RSA PRIVATE KEY-----`
   - File should end with `-----END RSA PRIVATE KEY-----`

### Method 3: Environment Variable Sync

```bash
# Set credentials in environment
export GH_APP_ID='your-value'
export GH_APP_SEC="$(cat /path/to/private-key.pem)"
export GH_APP_INSTALLATION_ID='your-value'

# Run fetch script to sync to env.shared
bash pmoves/scripts/fetch_credentials.sh
```

---

## Verify Configuration

### Check env.shared

```bash
grep "^GH_APP_" pmoves/env.shared
```

Expected output:
```
GH_APP_ID=123456
GH_APP_CLIENT_ID=Iv1.abc123...
GH_APP_SEC=-----BEGIN RSA PRIVATE KEY-----
...
GH_APP_INSTALLATION_ID=789012
```

### Test Docker Compose Resolution

```bash
cd pmoves
docker compose config | grep -A2 "GH_APP_"
```

Expected output (services that consume these variables):
```yaml
environment:
  - GH_APP_ID=123456
  - GH_APP_SEC=...
  - GH_APP_INSTALLATION_ID=789012
```

### Test Token Minting (BoTZ)

```bash
cd PMOVES-BoTZ
python features/github/mint_and_exec.py
```

Expected output:
```
✓ GitHub App token minted successfully
✓ Token expires in 3600 seconds
✓ MCP server starting...
```

---

## Services Using GitHub App Credentials

| Service | Environment Variables | Purpose |
|---------|---------------------|---------|
| archon | GH_APP_ID, GH_APP_SEC, GH_APP_INSTALLATION_ID | Cross-repo work orders |
| botz-gateway | GH_APP_ID, GH_APP_SEC, GH_APP_INSTALLATION_ID | MCP GitHub server token minting |

---

## Troubleshooting

### "Invalid keyData" Error

**Problem:** PEM key formatting issue
**Solution:** Use file redirect, not paste:
```bash
gh secret set GH_APP_SEC --repo POWERFULMOVES/PMOVES.AI < /path/to/key.pem
```

### "GH_APP_SEC not found" Error

**Problem:** Credential missing from env.shared
**Solution:** Run `bash pmoves/scripts/github_app_setup.sh` and follow prompts

### Token Minting Fails

**Problem:** Credentials invalid or network issue
**Solution:**
1. Verify GH_APP_ID is numeric (no quotes)
2. Verify GH_APP_INSTALLATION_ID is numeric
3. Check PEM key starts/ends with proper delimiters
4. Test network: `curl -I https://api.github.com`

### Container Cannot Access Credentials

**Problem:** Docker Compose not resolving env vars
**Solution:**
1. Ensure env.shared is in pmoves/ directory
2. Restart Docker Compose: `docker compose down && docker compose up -d`
3. Check container env: `docker exec <container> env | grep GH_APP`

---

## Security Considerations

1. **Never commit PEM keys** - env.shared is in .gitignore
2. **Rotate credentials annually** - GitHub App keys should be regenerated periodically
3. **Limit permissions** - App has minimum required permissions (contents:read, packages:write, etc.)
4. **Monitor usage** - Check GitHub App settings for installation activity

---

## Related Documentation

- [GitHub App Strategy](pmoves/docs/infrastructure/github-app-strategy.md) - Complete strategy reference
- [BoTZ MCP GitHub Integration](PMOVES-BoTZ/features/github/) - Token minting wrapper
- [Archon Work Orders](PMOVES-Archon/python/src/agent_work_orders/github_integration/) - GitHub client usage

---

## CI/CD Integration

GitHub Actions automatically uses these credentials via:

```yaml
- name: Generate GitHub App token
  id: app_token
  uses: actions/create-github-app-token@v2
  with:
    app-id: ${{ secrets.GH_APP_ID }}
    private-key: $${{ secrets.GH_APP_SEC }}
```

No local setup required for CI - credentials are in GitHub Secrets.

---

## Support

For issues or questions:
1. Check: `pmoves/docs/infrastructure/github-app-strategy.md`
2. Run: `bash pmoves/scripts/github_app_setup.sh --verbose`
3. GitHub Issues: https://github.com/POWERFULMOVES/PMOVES.AI/issues
