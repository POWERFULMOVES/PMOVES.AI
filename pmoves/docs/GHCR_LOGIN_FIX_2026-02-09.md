# GHCR Login Failure - Root Cause & Fix

**Date:** 2026-02-09 03:57 UTC
**Status:** 🔴 **BLOCKING** - GHCR login failing even with GH_PAT_PUBLISH
**Workflow Run:** #21811783792
**Latest Test Run:** https://github.com/POWERFULMOVES/PMOVES.AI/actions/runs/21811783792

---

## Problem

The GHCR workflow is failing at the "Log in to GHCR" step with error:
```
Error response from daemon: Get "https://ghcr.io/v2/": denied: denied
```

**Test Run Results (2026-02-09 03:57 UTC):**
- ❌ All 10 integration jobs failed at GHCR login
- ❌ agent-zero, archon, archon-ui, deepresearch, firefly-iii, jellyfin, open-notebook, pmoves-yt, supaserch, wger

**Root Cause Analysis (Updated 2026-02-09 04:16 UTC):**

The `GH_PAT_PUBLISH` secret is one of the following:
1. **Token owner mismatch** - The PAT token was created by a different user than `GHCR_USERNAME` secret
2. **Set but lacks `write:packages` scope** - Token doesn't have package write permissions
3. **Organization permissions** - Token user doesn't have write access to POWERFULMOVES org packages
4. **Expired or invalid token**

**CRITICAL**: The token owner MUST match the `GHCR_USERNAME` secret value, OR the token must have explicit organization package write permissions.

**Workflow uses self-hosted runner** (`runs-on: [self-hosted, vps]`), so the GITHUB_TOKEN fallback won't work for GHCR.

---

## How GitHub Actions Login Works

The workflow uses this configuration:

```yaml
env:
  GHCR_USERNAME: ${{ secrets.GHCR_USERNAME || github.actor }}
  GHCR_PASSWORD: ${{ secrets.GH_PAT_PUBLISH || github.token }}

steps:
  - name: Log in to GHCR
    uses: docker/login-action@v3
    with:
      registry: ghcr.io
      username: ${{ env.GHCR_USERNAME }}
      password: ${{ env.GHCR_PASSWORD }}
```

**Default behavior if secrets not set:**
- `GHCR_USERNAME` → `github.actor` (the user triggering the workflow)
- `GHCR_PASSWORD` → `github.token` (the automatic GITHUB_TOKEN)

**Issue:** `github.token` may not have `write:packages` scope for GHCR.

---

## Required Fix

### Option A: Create/Set GH_PAT_PUBLISH Secret (Recommended)

1. **Generate a Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Note: Use "Fine-grained token" if available for better security

2. **Set scopes:**
   ```
   repo (full control of private repositories)
   write:packages (write packages)
   read:org (read org and team data, if org-level GHCR)
   ```

3. **Add Secret to Repository:**
   - Go to: https://github.com/POWERFULMOVES/PMOVES.AI/settings/secrets/actions
   - Click "New repository secret"
   - Name: `GH_PAT_PUBLISH`
   - Value: [paste the generated token]
   - Add repository: `POWERFULMOVES/PMOVES.AI`

4. **Verify:**
   ```bash
   # Test from local machine with the token
   echo "YOUR_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin
   ```

### Option B: Use Fine-Grained Token (More Secure)

1. Go to: https://github.com/settings/tokens?type=beta

2. Create a new fine-grained token with:
   - **Repository access:** POWERFULES/PMOVES.AI
   - **Permissions:**
     - Contents: Read and Write
     - Actions: Read and Write
     - Packages: Read and Write
     - Administration: Read self-hosted runners

3. Add as `GH_PAT_PUBLISH` secret

### Option C: Enable GitHub Actions Default Token (If Available)

In some organizations, `GITHUB_TOKEN` may have `write:packages` scope. To use it:

```yaml
env:
  GHCR_PASSWORD: ${{ secrets.GITHUB_TOKEN }}  # Use GITHUB_TOKEN directly
```

**Note:** This only works if the token has the required scope.

---

## Verification Steps

After setting the secret:

1. **Re-run the workflow:**
   ```bash
   gh workflow run integrations-ghcr.yml -f integration=agent-zero
   ```

2. **Monitor the workflow:**
   - Go to: https://github.com/POWERFULMOVES/PMOVES.AI/actions
   - Click on the latest "Build and publish integration images to GHCR" run
   - Check if "Log in to GHCR" step succeeds

3. **Check for successful login in logs:**
   - Look for: "Login Succeeded"
   - No "denied" or "unauthorized" errors

---

## Alternative: Docker Hub Fallback

If GHCR continues to have issues, we can use Docker Hub as a fallback:

```yaml
env:
  REGISTRY: docker.io  # Change from ghcr.io
  DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
  DOCKERHUB_PASSWORD: ${{ secrets.DOCKERHUB_TOKEN }}
```

**Note:** This requires Docker Hub credentials to be set as secrets.

---

## Security Note

⚠️ **Never commit PATs to the repository!**

The `GH_PAT_PUBLISH` secret must be set via GitHub UI, not in code.

---

## Related Documentation

- GitHub Docs: https://docs.github.com/en/actions/security-guides/automatic-token-authentication
- GHCR Docs: https://docs.github.com/en/packages/working-with-a-github-packages-container-registry-getting-started
- Docker Login Action: https://github.com/docker/login-action

---

**Created:** 2026-02-09 03:20 UTC
**Priority:** CRITICAL - Blocks production deployment
**Owner:** Infrastructure Team
