# GitHub App Quick Start Guide

**Get GitHub App credentials working on your local machine in 3 simple steps.**

## Prerequisites

Before you begin, ensure you have:

1. **GitHub CLI installed**
   - **Linux:** `curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg`
   - **macOS:** `brew install gh`
   - **Windows:** Download from [cli.github.com](https://cli.github.com/)

2. **GitHub CLI authenticated**
   ```bash
   gh auth login
   ```

3. **GitHub App credentials in GitHub Secrets** (already done for PMOVES.AI)
   - `GH_APP_ID` - Numeric App ID
   - `GH_APP_SEC` - PEM private key
   - `GH_APP_CLIENT_ID` - OAuth Client ID (optional)
   - `GH_APP_INSTALLATION_ID` - Installation ID for POWERFULMOVES org

## Quick Setup (3 Steps)

### Step 1: Run the Automated Setup

```bash
cd pmoves
make github-app-setup
```

This script will:
- ✓ Verify GitHub CLI authentication
- ✓ Check GitHub Secrets for all 4 credentials
- ✓ Uncomment credentials in `env.shared`
- ✓ Run `secrets-funnel` to generate `env.tier-agent`
- ✓ Verify credentials in tier files

### Step 2: Verify the Setup

```bash
make github-app-verify
```

This checks:
- ✓ GitHub CLI installed and authenticated
- ✓ Credentials in GitHub Secrets
- ✓ Credentials uncommented in `env.shared`
- ✓ Credentials in `env.tier-agent`
- ✓ Docker Compose configuration references

### Step 3: Test Token Minting

```bash
# First, start the services that use GitHub App credentials
docker compose up -d archon botz-gateway

# Then test token minting
make github-app-test
```

## Troubleshooting

### GitHub CLI not authenticated

**Error:** `GitHub CLI not authenticated`

**Solution:**
```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

### Credentials not found in GitHub Secrets

**Error:** `Only X/4 credentials found in GitHub Secrets`

**Solution:** This is a setup issue for repository administrators. The credentials must be added to GitHub Secrets first.

1. Visit: https://github.com/organizations/POWERFULMOVES/PMOVES.AI/settings/secrets/actions
2. Add the 4 GitHub App credentials:
   - `GH_APP_ID` (Numeric App ID from GitHub App settings)
   - `GH_APP_SEC` (PEM private key - download from GitHub App settings)
   - `GH_APP_CLIENT_ID` (OAuth Client ID - optional)
   - `GH_APP_INSTALLATION_ID` (Installation ID for POWERFULMOVES org)

### env.shared not updated

**Error:** `GitHub App credentials already uncommented in env.shared` (but they're not)

**Solution:** Manually verify and edit `pmoves/env.shared`:

```bash
# Edit pmoves/env.shared
# Lines 180-183 should look like this (uncommented):
GH_APP_ID=<your-app-id>
GH_APP_CLIENT_ID=<your-client-id>
GH_APP_SEC="-----BEGIN RSA PRIVATE KEY-----
<your-pem-key>
-----END RSA PRIVATE KEY-----"
GH_APP_INSTALLATION_ID=<your-installation-id>
```

**Important:** For `GH_APP_SEC`, preserve the newlines in the PEM key. Use the multi-line quoted format.

### env.tier-agent not generated

**Error:** `env.tier-agent not found`

**Solution:** Run the secrets funnel manually:

```bash
cd pmoves
make secrets-funnel
```

This generates `env.tier-agent` from `env.shared`.

### Services fail to start with credential errors

**Error:** Services show "GH_APP_ID not found"

**Solution:**
1. Verify `env.tier-agent` contains the credentials:
   ```bash
   grep GH_APP_ pmoves/env.tier-agent
   ```

2. Restart the services:
   ```bash
   docker compose up -d archon botz-gateway
   docker compose logs -f archon botz-gateway
   ```

3. Check service logs for credential-related errors:
   ```bash
   docker compose logs archon | grep GH_APP
   docker compose logs botz-gateway | grep GH_APP
   ```

## Platform-Specific Notes

### Linux

Everything should work out of the box with the standard commands.

### macOS

Same as Linux. If you don't have `gh` installed via Homebrew, install it first:

```bash
brew install gh
gh auth login
```

### Windows

**Option 1: Use Git Bash or WSL**

The `make` commands will work in Git Bash or WSL (Windows Subsystem for Linux).

**Option 2: Use PowerShell**

Run the Python scripts directly:

```powershell
# Navigate to pmoves directory
cd pmoves

# Run setup
python tools/github_app_auto_setup.py

# Verify
python tools/verify_github_app_setup.py
```

## Next Steps

After completing the setup:

1. **Start services:**
   ```bash
   docker compose up -d archon botz-gateway
   ```

2. **Verify health:**
   ```bash
   curl http://localhost:8091/healthz  # Archon
   curl http://localhost:8054/healthz  # BoTZ Gateway
   ```

3. **Test token minting:**
   ```bash
   make github-app-test
   ```

## What Actually Happens

The automated setup script (`github_app_auto_setup.py`) performs these steps:

1. **Verify GitHub CLI** - Ensures `gh` is installed and authenticated
2. **Check GitHub Secrets** - Verifies all 4 credentials exist in GitHub Secrets
3. **Update env.shared** - Uncomments the GitHub App credential lines
4. **Run secrets-funnel** - Generates `env.tier-agent` from `env.shared`
5. **Verify tier files** - Confirms credentials are present in `env.tier-agent`

This creates a complete credential flow:

```
GitHub Secrets → env.shared → env.tier-agent → Docker services
```

## See Also

- **Agent Documentation:** `docs/AGENTS/GITHUB_APP_CREDENTIALS.md`
- **Integration Guide:** `docs/infrastructure/GITHUB_APP_CHIT_INTEGRATION.md`
- **Credentials Workflow:** `.claude/context/credentials-workflow.md`

## Support

If you encounter issues not covered here:

1. Check the detailed documentation in `docs/infrastructure/GITHUB_APP_CHIT_INTEGRATION.md`
2. Verify your setup with `make github-app-verify`
3. Check service logs: `docker compose logs archon botz-gateway`
4. Open an issue on GitHub with the error output
