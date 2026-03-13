# GitHub App CHIT Integration Guide

This document describes how GitHub App credentials are integrated into the PMOVES.AI CHIT credentials management system.

## Quick Start (Automated Setup)

**For most users, run the automated setup script:**

```bash
cd pmoves
make github-app-setup
```

This handles everything:
- ✓ Verify GitHub CLI authentication
- ✓ Check GitHub Secrets for credentials
- ✓ Uncomment credentials in `env.shared`
- ✓ Run `secrets-funnel` to generate tier files
- ✓ Verify credentials in `env.tier-agent`

**Verify the setup:**
```bash
make github-app-verify
```

**See also:**
- **Quick Start Guide:** `docs/GITHUB_APP_QUICK_START.md` - User-facing guide
- **Agent Reference:** `docs/AGENTS/GITHUB_APP_CREDENTIALS.md` - Agent integration patterns

---

## Architecture

GitHub App credentials follow the documented CHIT secrets funnel flow:

```
env.shared (local) → CHIT bundle (env.cgp.json) → tier files (env.tier-*)
                                                      ↓
                                                Docker services
```

## Credential Definitions

The following GitHub App credentials are now part of the CHIT manifest system:

| Credential | Required | Purpose | Targets |
|------------|----------|---------|---------|
| `GH_APP_ID` | Yes | Numeric GitHub App ID | env.shared, env.tier-agent, GitHub Secrets, Docker |
| `GH_APP_CLIENT_ID` | No | OAuth Client ID | env.shared, env.tier-agent, GitHub Secrets, Docker |
| `GH_APP_SEC` | Yes | PEM private key | env.shared, env.tier-agent, GitHub Secrets, Docker |
| `GH_APP_INSTALLATION_ID` | Yes | Installation ID | env.shared, env.tier-agent, GitHub Secrets, Docker |

## Integration Workflow

### Phase 1: Add to CHIT Manifest ✅ (COMPLETE)

The GitHub App entries have been added to `pmoves/chit/secrets_manifest_v2.yaml`:

```yaml
- id: gh_app_id
  source:
    type: cgp
    label: GH_APP_ID
  targets:
  - file: env.shared.generated
    key: GH_APP_ID
  - file: .env.generated
    key: GH_APP_ID
  - file: env.tier-agent
    key: GH_APP_ID
  - github_secret: GH_APP_ID
  - docker_secret: pmoves_gh_app_id
  required: true
  tier: agent
```

### Phase 2: Populate env.shared

**RECOMMENDED: Use the automated setup script**

Run the automated setup script (handles all remaining phases):

```bash
cd pmoves
make github-app-setup
```

This script will:
- ✓ Verify GitHub CLI authentication
- ✓ Check GitHub Secrets for all 4 credentials
- ✓ Uncomment credentials in `env.shared`
- ✓ Run `secrets-funnel` to generate tier files
- ✓ Verify credentials in `env.tier-agent`

**MANUAL SETUP (if automated script fails):**

The credential templates are in env.shared at lines 176-183:
- Lines 176-179: Comment block describing each credential
- Lines 180-183: Commented credential assignments (to be uncommented)

```bash
# GH_APP_ID - Numeric App ID from GitHub App settings
# GH_APP_CLIENT_ID - OAuth Client ID from GitHub App settings (optional, for OAuth flows)
# GH_APP_SEC - PEM private key (full contents with newlines preserved)
# GH_APP_INSTALLATION_ID - Installation ID for POWERFULMOVES org
#GH_APP_ID=
#GH_APP_CLIENT_ID=
#GH_APP_SEC=
#GH_APP_INSTALLATION_ID=
```

**Steps:**

1. **Retrieve credentials from GitHub App settings:**
   - Go to: https://github.com/organizations/POWERFULMOVES/settings/apps
   - Select the PMOVES.AI GitHub App
   - Copy the App ID, Client ID, and download the PEM private key
   - Get the Installation ID for POWERFULMOVES org

2. **Uncomment and populate in env.shared:**
   ```bash
   # Edit pmoves/env.shared
   GH_APP_ID=123456
   GH_APP_CLIENT_ID=Iv1.abc123...
   GH_APP_SEC="-----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA...
   ...
   -----END RSA PRIVATE KEY-----"
   GH_APP_INSTALLATION_ID=789012
   ```

   **Important:** For `GH_APP_SEC`, preserve the newlines in the PEM key. The multi-line format is required.

### Phase 3: Export to CHIT Bundle

Once credentials are in env.shared, encode them into the CHIT bundle:

```bash
cd pmoves
python tools/chit_encode_secrets.py
```

This creates `pmoves/data/chit/env.cgp.json` with the GitHub App credentials.

### Phase 4: Sync to Tier Files

Run the secrets funnel to populate tier files:

```bash
cd pmoves
python tools/secrets_sync.py generate --manifest chit/secrets_manifest_v2.yaml
```

Or use the make target (if available):

```bash
cd pmoves
make secrets-funnel-sync
```

This will:
- Read from `pmoves/data/chit/env.cgp.json`
- Write to `env.shared.generated` (if using CHIT as source)
- Write to `env.tier-agent` with GH_APP_* variables
- Populate Docker container environment

### Phase 5: Verify Services

Start the services that use GitHub App credentials:

```bash
cd pmoves
docker compose up -d archon botz-gateway
docker compose logs -f archon botz-gateway
```

Verify health:

```bash
curl http://localhost:8054/healthz  # BoTZ gateway
curl http://localhost:8091/healthz  # Archon
```

### Phase 6: Test Token Minting

Test that the credentials work:

```bash
cd PMOVES-BoTZ

# Set credentials from env.shared
export GH_APP_ID=$(grep "^GH_APP_ID=" ../pmoves/env.shared | cut -d'=' -f2)
export GH_APP_SEC=$(grep "^GH_APP_SEC=" ../pmoves/env.shared | cut -d'=' -f2-)
export GH_APP_INSTALLATION_ID=$(grep "^GH_APP_INSTALLATION_ID=" ../pmoves/env.shared | cut -d'=' -f2)

# Test minting
python features/github/mint_and_exec.py
```

## CHIT Bundle Structure

The exported CHIT bundle (`pmoves/data/chit/env.cgp.json`) has this structure:

```json
{
  "version": 1,
  "meta": {
    "namespace": "pmoves.secrets",
    "summary": "PMOVES shared secrets"
  },
  "env": {
    "GH_APP_ID": "<numeric-id>",
    "GH_APP_SEC": "<hex-encoded-pem-key>",
    "GH_APP_INSTALLATION_ID": "<installation-id>",
    ...
  },
  "sig": {
    "alg": "HMAC-SHA256",
    "kid": "<key-id>",
    "hmac": "<signature>"
  }
}
```

## Syncing from GitHub Secrets

Alternatively, you can sync GitHub Secrets to the local CHIT bundle:

```bash
# Run the sync workflow
gh workflow run sync-secrets-local.yml --repo POWERFULMOVES/PMOVES.AI -f output_format=cgp

# This creates ~/.config/pmoves/chit/env.cgp.json
```

Then decode and sync to env.shared:

```bash
cd pmoves
python tools/chit_decode_secrets.py --cgp-file ~/.config/pmoves/chit/env.cgp.json --output env.shared
```

## Troubleshooting

### Credential not found in services

**Symptom:** Services show "GH_APP_ID not found"

**Solution:**
1. Verify env.shared has uncommented credentials
2. Re-run CHIT encode: `python tools/chit_encode_secrets.py`
3. Re-run secrets sync: `python tools/secrets_sync.py generate`
4. Restart services: `docker compose up -d archon botz-gateway`

### PEM key format errors

**Symptom:** "Invalid PEM format" or "Failed to load private key"

**Solution:**
1. Ensure GH_APP_SEC preserves newlines
2. Use quoted multi-line format in env.shared
3. Verify the PEM file starts with `-----BEGIN RSA PRIVATE KEY-----`

### Secrets sync fails

**Symptom:** `secrets_sync.py` fails with "Missing required credential"

**Solution:**
1. Check secrets_manifest_v2.yaml has the correct entries
2. Verify CHIT bundle exists: `ls -la pmoves/data/chit/env.cgp.json`
3. Run with --allow-missing for debugging:
   ```bash
   python tools/secrets_sync.py generate --manifest chit/secrets_manifest_v2.yaml --allow-missing
   ```

## Verification Checklist

- [ ] GitHub App entries added to secrets_manifest_v2.yaml
- [ ] Credentials uncommented in env.shared
- [ ] CHIT bundle created (pmoves/data/chit/env.cgp.json)
- [ ] Tier files generated (env.tier-agent contains GH_APP_*)
- [ ] Services start without credential errors
- [ ] Token minting test succeeds

## References

- **Strategy:** `pmoves/docs/infrastructure/github-app-strategy.md`
- **Setup Guide:** `pmoves/docs/infrastructure/github-app-setup-guide.md`
- **Credentials Workflow:** `.claude/context/credentials-workflow.md`
- **CHIT Manifest:** `pmoves/chit/secrets_manifest_v2.yaml`
- **Tooling Scripts:** `pmoves/scripts/github_app_setup.sh`, `pmoves/scripts/verify_github_app.sh`
