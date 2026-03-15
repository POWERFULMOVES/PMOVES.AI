# GitHub App Credentials - Agent Reference

**Complete reference for agents working with GitHub App integration in PMOVES.AI.**

## Architecture Overview

The GitHub App credential flow uses a **multi-tier environment system** to separate credential storage and runtime injection:

```
┌─────────────────┐
│ GitHub Secrets  │ (Cloud storage, 4 credentials: GH_APP_ID, GH_APP_SEC, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   env.shared    │ (Local source of truth, credentials uncommented)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ secrets-funnel  │ (Make target that generates tier files)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ env.tier-agent  │ (Generated file for agent services)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Docker Services │ (Archon, BoTZ Gateway, etc.)
└─────────────────┘
```

## Credential Definitions

| Credential | Type | Purpose | Required |
|------------|------|---------|----------|
| `GH_APP_ID` | Numeric | GitHub App identifier (e.g., `123456`) | Yes |
| `GH_APP_SEC` | PEM | Private key for JWT signing (multi-line RSA key) | Yes |
| `GH_APP_CLIENT_ID` | String | OAuth Client ID (for OAuth flows) | No |
| `GH_APP_INSTALLATION_ID` | Numeric | Installation ID for POWERFULMOVES org (e.g., `789012`) | Yes |

## File Locations

### Local Environment Files

| File | Location | Purpose | Edit Manually? |
|------|----------|---------|----------------|
| `env.shared` | `pmoves/env.shared` | Source of truth for all credentials | Yes (to uncomment) |
| `env.tier-agent` | `pmoves/env.tier-agent` | Generated file for agent services | No (auto-generated) |
| `env.tier-llm` | `pmoves/env.tier-llm` | Generated file for LLM services | No (auto-generated) |
| `env.tier-data` | `pmoves/env.tier-data` | Generated file for data services | No (auto-generated) |
| `env.tier-media` | `pmoves/env.tier-media` | Generated file for media services | No (auto-generated) |

### CHIT Manifest

| File | Location | Purpose |
|------|----------|---------|
| `secrets_manifest.yaml` | `pmoves/chit/secrets_manifest.yaml` | Defines credential targets and tiers |

**Note:** The CHIT secrets manifest (`pmoves/chit/secrets_manifest_v2.yaml`) defines which
credentials are synced to GitHub Secrets. The sync-secrets-local workflow
reads this manifest to determine which secrets to export.
### Docker Compose Configuration

| File | Location | Purpose |
|------|----------|---------|
| `docker-compose.yml` | `pmoves/docker-compose.yml` | Service definitions with env_file references |
| `.env.generated` | `pmoves/.env.generated` | Auto-generated from CHIT bundle (if using CGP workflow) |

## Credential Flow

### 1. Initial Setup (One-Time Per Machine)

```bash
cd pmoves
make github-app-setup
```

**What happens:**
1. Script verifies GitHub CLI authentication
2. Checks GitHub Secrets for all 4 credentials
3. Uncomments credentials in `env.shared` (lines 180-183)
4. Runs `make secrets-funnel` to generate tier files
5. Verifies credentials in `env.tier-agent`

### 2. Secrets Funnel (Generate Tier Files)

```bash
cd pmoves
make secrets-funnel
```

**What happens:**
1. Reads `env.shared` (source of truth)
2. Uses `chit/secrets_manifest_v2.yaml` to determine targets
3. Generates `env.tier-agent` with `GH_APP_*` variables
4. Generates other tier files (`env.tier-llm`, `env.tier-data`, etc.)

**Manifest entries for GitHub App credentials:**

```yaml
# pmoves/chit/secrets_manifest_v2.yaml
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

### 3. Service Launch (Runtime Injection)

```bash
cd pmoves
docker compose up -d archon botz-gateway
```

**What happens:**
1. Docker Compose reads service definitions
2. Each service has `env_file: - env.tier-agent`
3. Environment variables injected into containers
4. Services access credentials via `os.getenv("GH_APP_ID")`

## Integration Patterns

### Pattern 1: Direct Environment Variable Access (Python)

```python
import os

# Access GitHub App credentials from environment
gh_app_id = os.getenv("GH_APP_ID")
gh_app_sec = os.getenv("GH_APP_SEC")
gh_app_installation_id = os.getenv("GH_APP_INSTALLATION_ID")

# Use credentials to mint JWT token
import jwt
import time

payload = {
    "iat": int(time.time()),
    "exp": int(time.time()) + 600,
    "iss": gh_app_id
}

token = jwt.encode(payload, gh_app_sec, algorithm="RS256")
```

### Pattern 2: Docker Compose Service Definition

```yaml
# pmoves/docker-compose.yml
services:
  archon:
    build: ./services/archon
    env_file:
      - env.tier-agent  # Contains GH_APP_* variables
    environment:
      - ARCHON_GITHUB_APP_ENABLED=true
    ports:
      - "8091:8091"
```

### Pattern 3: MCP Bridge Integration

```python
# PMOVES-BoTZ/features/mcp_bridge/auth.py
import os
import jwt
import time

def create_github_app_token():
    """Create a GitHub App installation token."""
    gh_app_id = os.getenv("GH_APP_ID")
    gh_app_sec = os.getenv("GH_APP_SEC")
    gh_app_installation_id = os.getenv("GH_APP_INSTALLATION_ID")

    # Create JWT
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "iss": int(gh_app_id)
    }
    jwt_token = jwt.encode(payload, gh_app_sec, algorithm="RS256")

    # Exchange for installation token
    response = requests.post(
        f"https://api.github.com/app/installations/{gh_app_installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json"
        }
    )

    return response.json()["token"]
```

### Pattern 4: Verification Script

```python
# Verify all components of GitHub App integration
def verify_github_app_setup():
    """Verify GitHub App credentials across all tiers."""
    checks = {
        "env.shared": verify_env_shared(),
        "env.tier-agent": verify_env_tier_agent(),
        "docker_compose": verify_docker_compose(),
        "chit_manifest": verify_chit_manifest(),
    }

    return all(checks.values())
```

## Common Agent Tasks

### Task: Add a New Service That Uses GitHub App Credentials

1. **Add service to docker-compose.yml:**
   ```yaml
   services:
     my-agent-service:
       env_file:
         - env.tier-agent  # Include GH_APP_* variables
   ```

2. **Add entry to secrets_manifest.yaml:**
   ```yaml
   - id: my_service_github_app
     source:
       type: cgp
       label: GH_APP_ID
     targets:
     - file: env.tier-agent
       key: GH_APP_ID
     tier: agent
   ```

3. **Run secrets-funnel:**
   ```bash
   make secrets-funnel
   ```

4. **Verify credentials in service:**
   ```bash
   docker compose logs my-agent-service | grep GH_APP
   ```

### Task: Verify GitHub App Integration

```bash
# Run the verification script
make github-app-verify

# Expected output:
# ✓ [PASS] GitHub CLI: Installed (version X.Y.Z) and authenticated
# ✓ [PASS] GitHub Secrets: GitHub App credentials (4/4 found)
# ✓ [PASS] env.shared: GitHub App credentials uncommented (4/4)
# ✓ [PASS] env.tier-agent: GitHub App credentials present (4/4)
# ✓ [PASS] docker-compose.yml: GitHub App credential references (8 found)
# ✓ [PASS] CHIT Manifest: GitHub App entries present
```

### Task: Debug Missing Credentials

1. **Check env.shared:**
   ```bash
   grep GH_APP_ pmoves/env.shared
   # Should show uncommented lines (not #GH_APP_ID=)
   ```

2. **Check env.tier-agent:**
   ```bash
   grep GH_APP_ pmoves/env.tier-agent
   # Should show all 4 credentials
   ```

3. **Check Docker service logs:**
   ```bash
   docker compose logs archon | grep -i "github\|credential"
   ```

4. **Check environment in running container:**
   ```bash
   docker compose exec archon env | grep GH_APP
   ```

### Task: Rotate GitHub App Credentials

1. **Rotate in GitHub App settings:**
   - Visit: https://github.com/organizations/POWERFULMOVES/settings/apps
   - Generate new PEM key
   - Update `GH_APP_SEC` in GitHub Secrets

2. **Update local env.shared:**
   ```bash
   # Edit pmoves/env.shared
   # Replace GH_APP_SEC with new PEM key
   ```

3. **Re-run secrets-funnel:**
   ```bash
   make secrets-funnel
   ```

4. **Restart services:**
   ```bash
   docker compose up -d archon botz-gateway
   ```

## Testing

### Unit Tests

```python
import os
import pytest

def test_github_app_credentials_present():
    """Test that GitHub App credentials are present in environment."""
    assert os.getenv("GH_APP_ID") is not None
    assert os.getenv("GH_APP_SEC") is not None
    assert os.getenv("GH_APP_INSTALLATION_ID") is not None

def test_github_app_jwt_creation():
    """Test JWT creation with GitHub App credentials."""
    import jwt
    import time

    gh_app_id = os.getenv("GH_APP_ID")
    gh_app_sec = os.getenv("GH_APP_SEC")

    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "iss": int(gh_app_id)
    }

    token = jwt.encode(payload, gh_app_sec, algorithm="RS256")
    assert token is not None
```

### Integration Tests

```bash
# Test token minting end-to-end
cd PMOVES-BoTZ
python features/github/mint_and_exec.py

# Expected output:
# ✓ JWT token created successfully
# ✓ Installation token minted
# ✓ API call successful
```

## Security Best Practices

1. **Never commit real credentials** - `env.shared` is in `.gitignore`
2. **Use PEM keys securely** - `GH_APP_SEC` should have restricted permissions (600)
3. **Rotate credentials regularly** - GitHub App PEM keys should be rotated periodically
4. **Use short-lived tokens** - JWT tokens expire after 10 minutes
5. **Fail closed** - Services should fail to start if credentials are missing

## Troubleshooting

### Issue: Credentials Not Found in Service

**Symptom:** Service logs show "GH_APP_ID not found"

**Diagnosis:**
```bash
# Check if credentials in env.tier-agent
grep GH_APP_ID pmoves/env.tier-agent

# Check if service includes env_file
grep -A 5 "archon:" pmoves/docker-compose.yml | grep env_file
```

**Solution:**
```bash
# Re-run secrets-funnel
make secrets-funnel

# Restart service
docker compose up -d archon
```

### Issue: JWT Token Invalid

**Symptom:** GitHub API returns "Bad credentials"

**Diagnosis:**
```python
import jwt

# Verify JWT payload
gh_app_id = os.getenv("GH_APP_ID")
gh_app_sec = os.getenv("GH_APP_SEC")

payload = {
    "iat": int(time.time()),
    "exp": int(time.time()) + 600,
    "iss": int(gh_app_id)
}

try:
    token = jwt.encode(payload, gh_app_sec, algorithm="RS256")
    decoded = jwt.decode(token, gh_app_sec, algorithms=["RS256"])
    print(decoded)
except Exception as e:
    print(f"JWT error: {e}")
```

**Solution:**
- Verify `GH_APP_SEC` is the complete PEM key (with newlines)
- Verify `GH_APP_ID` is numeric (not quoted)
- Check system time is accurate (JWT uses timestamps)

### Issue: PEM Key Format Errors

**Symptom:** "Could not deserialize key data"

**Diagnosis:**
```bash
# Check PEM key format
grep -A 10 "GH_APP_SEC=" pmoves/env.tier-agent

# Should show:
# GH_APP_SEC="-----BEGIN RSA PRIVATE KEY-----
# MIIEpAIBAAKCAQEA...
# -----END RSA PRIVATE KEY-----"
```

**Solution:**
- Ensure PEM key is quoted
- Preserve newlines in multi-line format
- Verify key starts with `-----BEGIN RSA PRIVATE KEY-----`

## References

- **Quick Start:** `docs/GITHUB_APP_QUICK_START.md`
- **Integration Guide:** `docs/infrastructure/GITHUB_APP_CHIT_INTEGRATION.md`
- **Credentials Workflow:** `.claude/context/credentials-workflow.md`
- **GitHub Apps Docs:** https://docs.github.com/en/developers/apps
- **JWT Auth:** https://docs.github.com/en/developers/apps/authenticating-with-github-apps
