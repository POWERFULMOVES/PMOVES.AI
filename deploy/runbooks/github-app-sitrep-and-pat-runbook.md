# GitHub App SITREP & PAT Rotation Runbook

**GRAPHITI_MARK:** `SITREP::GITHUB_APP::2026-04-23`
**Classification:** OPERATIONAL — CONFIDENTIAL
**Author:** SIDECAR-SPARK (GB10 Blackwell)
**Date:** 2026-04-23 17:15 UTC
**Trigger:** PAT expiry incident + AGNOTE4482 CI hardening gap

---

## 1. Executive Summary

PMOVES.AI has 30 GitHub Actions workflows, 92 repo secrets, and 5 self-hosted runners — all primarily authenticated via a **single expired Personal Access Token (PAT)**. A GitHub App exists with all 4 credential secrets in the repo, but **App token generation is silently failing** because the private key is misconfigured. This SITREP documents the current state, identifies every gap, and provides the runbook to fix it.

**Risk Level:** 🔴 HIGH — Single point of failure on an expired credential with no rotation procedure.

---

## 2. Current State — SITREP

### 2.1 Authentication Inventory

| Credential | Location | Status | Used By |
|-----------|----------|--------|---------|
| `GH_PAT` (embedded in git remote URL) | `origin` remote | ✅ Works for git push | Sidecar, all push operations |
| `GH_PAT` (repo secret) | GitHub Secrets | ❌ Expired (401 on API) | 6 workflows, runner registration |
| `GH_PAT_PUBLISH` (repo secret) | GitHub Secrets | ❓ Unknown — likely same PAT | sync-secrets workflows |
| `PMOVES_GITBOT_PAT` (repo secret) | GitHub Secrets | ❓ Unknown | Bot operations |
| `CATACLYSMSTUDIOS_GH_PAT` (repo secret) | GitHub Secrets | ❓ Unknown | Cross-org operations |
| `HUNNINBEAR_GH_PAT` (repo secret) | GitHub Secrets | ❓ Unknown | Cross-org operations |
| `DOCKER_PAT` (repo secret) | GitHub Secrets | ❓ Unknown | Docker operations |
| `GH_APP_ID` (repo secret) | GitHub Secrets | ✅ Present | 4 workflows (via create-github-app-token) |
| `GH_APP_CLIENT_ID` (repo secret) | GitHub Secrets | ✅ Present | OAuth device flow |
| `GH_APP_INSTALLATION_ID` (repo secret) | GitHub Secrets | ✅ Present | Token generation |
| `GH_APP_SEC` (repo secret) | GitHub Secrets | ⚠️ Likely OAuth client secret, NOT PEM | 4 workflows (WRONG — used as private-key) |
| **GH_APP_PRIVATE_KEY (PEM)** | **MISSING** | ❌ Does not exist | **REQUIRED by create-github-app-token** |

### 2.2 Why App Token Generation Is Failing

All 4 workflows using `actions/create-github-app-token` pass `GH_APP_SEC` as `private-key`:

```yaml
- uses: actions/create-github-app-token@v3
  with:
    app-id: ${{ secrets.GH_APP_ID }}
    private-key: ${{ secrets.GH_APP_SEC }}  # ← WRONG: this is OAuth client secret
```

The action requires a **PEM-formatted RSA private key** (starts with `-----BEGIN RSA PRIVATE KEY-----`). `GH_APP_SEC` is almost certainly the OAuth client secret (a short alphanumeric string). The `continue-on-error: true` masks the failure, and workflows fall back to PAT-based GHCR login.

### 2.3 Workflow Authentication Map

| Workflow | PAT Usage | App Token | Status |
|----------|-----------|-----------|--------|
| `build-images.yml` | GHCR fallback | ❌ Silent fail (wrong key) | PAT-dependent |
| `integrations-ghcr.yml` | GHCR fallback | ❌ Silent fail (wrong key) | PAT-dependent |
| `self-hosted-builds.yml` | GHCR fallback | ❌ Silent fail (wrong key) | PAT-dependent |
| `self-hosted-builds-hardened.yml` | GHCR fallback | ❌ Silent fail (wrong key) | PAT-dependent |
| `sync-secrets-local.yml` | Direct PAT | N/A | PAT-dependent |
| `sync-secrets-spark.yml` | Direct PAT | N/A | PAT-dependent |
| Remaining 24 workflows | GITHUB_TOKEN (auto) | N/A | ✅ Working |

### 2.4 Runner Fleet

| Runner | Labels | Registration Auth | Status |
|--------|--------|-------------------|--------|
| AI Lab | `self-hosted, ai-lab, gpu, cuda` | PAT (GITHUB_PAT env) | ⚠️ Will fail on re-registration |
| SPARK | `self-hosted, spark, Linux, ARM64` | PAT | ⚠️ Will fail on re-registration |
| cloudstartup | `self-hosted, vps, cloudstartup, staging` | PAT | ⚠️ Will fail on re-registration |
| kvm4 | `self-hosted, vps, kvm4, production` | PAT | ⚠️ Will fail on re-registration |
| kvm2 | `self-hosted, vps, kvm2, backup` | PAT | ⚠️ Will fail on re-registration |

Runner registration tokens expire after 1 hour. Re-registration requires a valid PAT or App token.

### 2.5 What's Working Despite the Gaps

- Git push via embedded PAT in remote URL (sidecar)
- All 24 workflows using `GITHUB_TOKEN` (auto-generated, 1hr TTL)
- Dependabot (uses its own App identity)
- CodeQL (uses its own App identity)
- GHCR fallback login in 4 workflows (uses GHCR_USERNAME + GHCR_TOKEN secrets, not GH_PAT)

### 2.6 Research Assessment Correction

The consolidated research reference (now removed) contained stale data in its PMOVES.AI Assessment section:

> ❌ "GH_APP_ID and GH_APP_INSTALLATION_ID are missing"

**Reality:** Both exist as repo secrets (confirmed via API 2026-04-23). The actual missing piece is the **PEM private key**.

---

## 3. PAT Rotation Runbook

### 3.1 The Hard Truth

**GitHub does NOT support programmatic PAT creation or rotation.** There is no `POST /user/personal-access-tokens` endpoint (GitHub Discussion #148626). Any "PAT rotation workflow" is either:
- Rotating **App installation tokens** (not PATs)
- Semi-automated: human creates token → workflow distributes it

### 3.2 Recommended Approach: Eliminate PAT, Not Rotate It

The correct strategy is **PAT → GitHub App migration**, not PAT rotation. However, during transition:

### 3.3 Interim PAT Refresh Procedure (Manual)

**Prerequisites:** Repo owner access to github.com

```
STEP 1: Create new fine-grained PAT
  → https://github.com/settings/personal-access-tokens/new
  → Name: pmoves-ci-YYYY-MM-DD
  → Expiry: 7 days (minimum practical)
  → Repository: POWERFULMOVES/PMOVES.AI only
  → Permissions:
    Contents: Read & Write
    Actions: Read & Write
    Metadata: Read
  → Copy token immediately

STEP 2: Update repo secret
  → https://github.com/POWERFULMOVES/PMOVES.AI/settings/secrets/actions
  → Update GH_PAT with new token value

STEP 3: Update git remote on sidecar
  → git remote set-url origin https://pmoves-spark:<NEW_TOKEN>@github.com/POWERFULMOVES/PMOVES.AI.git

STEP 4: Update runners (if registration needed)
 → SSH to each runner
 → Update GITHUB_PAT env var in runner service/env file
 → Re-run: ./actions-runner/run.sh

STEP 5: Verify
  → curl -s -H "Authorization: token <NEW_TOKEN>" https://api.github.com/user
  → Trigger a test workflow run

STEP 6: Set calendar reminder for expiry - 1 day
```

### 3.4 PAT Expiry Monitoring Workflow

Create `.github/workflows/pat-health-check.yml`:

```yaml
name: PAT Health Check
on:
  schedule:
    - cron: '0 12 * * *'  # Daily at noon UTC
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check GH_PAT validity
        env:
          GH_TOKEN: ${{ secrets.GH_PAT }}
        run: |
          if gh api user >/dev/null 2>&1; then
            echo "✅ GH_PAT is valid"
            # Check expiry
            EXPIRY=$(gh api -H "Accept: application/vnd.github+json" /rate_limit 2>/dev/null | \
              python3 -c "import sys,json; print('ok')" 2>/dev/null)
            echo "Token responds to API calls"
          else
            echo "❌ GH_PAT is EXPIRED or INVALID"
            echo "::error::GH_PAT needs rotation immediately"
            exit 1
          fi

      - name: Notify on failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `🔴 GH_PAT Expired — ${new Date().toISOString().split('T')[0]}`,
              body: `## PAT Health Check Failed\n\nThe GH_PAT secret is expired or invalid.\n\n### Immediate Action Required\n1. Create new fine-grained PAT (7-day expiry)\n2. Update GH_PAT secret\n3. Update git remote on sidecar\n4. See: deploy/runbooks/github-app-sitrep-and-pat-runbook.md §3.3\n\n### Runbook\nThis issue was auto-created by the PAT Health Check workflow.`,
              labels: ['operations', 'security', 'urgent']
            })
```

---

## 4. GitHub App Fix & Migration Plan

### Phase 0: Obtain PEM Private Key (OPERATOR ACTION REQUIRED)

```
1. Go to: https://github.com/settings/developers
2. Click on the PMOVES GitHub App
3. Scroll to "Private keys" section
4. Either:
   a. Download existing key (if one was generated), OR
   b. Generate a new key ("Generate a private key" button)
5. Save the .pem file securely
6. Add as repo secret: GH_APP_PRIVATE_KEY
   → https://github.com/POWERFULMOVES/PMOVES.AI/settings/secrets/actions
   → Name: GH_APP_PRIVATE_KEY
   → Value: (paste entire PEM content including BEGIN/END lines)

7. Verify the App ID matches GH_APP_ID secret value
8. Verify Installation ID matches GH_APP_INSTALLATION_ID secret value
```

### Phase 1: Verify App Token Generation

After Phase 0, create a test workflow or run existing one:

```yaml
name: Test App Token
on: workflow_dispatch
jobs:
 test:
   runs-on: ubuntu-latest
   steps:
     - uses: actions/create-github-app-token@v3
       id: app-token
       with:
         app-id: ${{ secrets.GH_APP_ID }}
         private-key: ${{ secrets.GH_APP_PRIVATE_KEY }}
     - name: Verify
       env:
         GH_TOKEN: ${{ steps.app-token.outputs.token }}
       run: |
         echo "Token obtained successfully"
         gh api user
```

### Phase 2: Fix Workflows (6 files)

**Change in all 4 hybrid workflows:**
```diff
 -        private-key: ${{ secrets.GH_APP_SEC }}
 +        private-key: ${{ secrets.GH_APP_PRIVATE_KEY }}
```

**Remove `continue-on-error: true`** after verification succeeds.

**Files to patch:**
- `.github/workflows/build-images.yml`
- `.github/workflows/integrations-ghcr.yml`
- `.github/workflows/self-hosted-builds.yml`
- `.github/workflows/self-hosted-builds-hardened.yml`

**For sync-secrets workflows** (PAT-only), add App token step:
- `.github/workflows/sync-secrets-local.yml`
- `.github/workflows/sync-secrets-spark.yml`

### Phase 3: Migrate Runner Registration

Update `deploy/runners/vps/install.sh` and `deploy/runners/ailab/install.sh`:

```bash
# Replace PAT-based registration with App token-based
generate_app_token() {
    local app_id="$1"
    local installation_id="$2"
    local pem_path="$3"
    
    # Generate JWT (requires PyJWT)
    local jwt=$(python3 -c "
import jwt, time, sys
with open('$pem_path') as f:
    key = f.read()
payload = {
    'iat': int(time.time()),
    'exp': int(time.time()) + 600,
    'iss': $app_id
}
print(jwt.encode(payload, key, algorithm='RS256'))
")
    
    # Get installation token
    local install_token=$(curl -sf -X POST \
        -H "Authorization: Bearer $jwt" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/app/installations/$installation_id/access_tokens" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
    
    echo "$install_token"
}
```

### Phase 4: Harden

- [ ] Remove `continue-on-error: true` from all App token steps
- [ ] Update git remote to remove embedded PAT: `git remote set-url origin https://github.com/POWERFULMOVES/PMOVES.AI.git`
- [ ] Configure git credential helper to use `GH_TOKEN` env var
- [ ] Delete `GH_PAT` repo secret (after confirming all workflows migrated)
- [ ] Enable branch protection "Do not allow bypassing" (App tokens can't bypass)
- [ ] Consider ARC (Actions Runner Controller) for scale-set runners

---

## 5. Future Leverage: GitHub App Capabilities

### 5.1 SLSA Provenance Enhancement

Current `attest-provenance.yml` uses `GITHUB_TOKEN` (OIDC keyless signing → L3 on hosted, L2 on self-hosted).

**With App key signing on self-hosted runners:**
```yaml
- uses: actions/attest-build-provenance@v2
  with:
    subject-name: ghcr.io/${{ github.repository }}/service
    subject-digest: sha256:${{ steps.build.outputs.digest }}
```

For self-hosted L3, need cosign key import with App identity — see `research/topic1_slsa_provenance_github_apps.md`.

### 5.2 GitHub Pages Management

The App can:
- Enable/configure Pages via API (unlike GITHUB_TOKEN)
- Deploy to Pages with App token
- Manage custom domains

Required permissions: `pages:write`, `administration:write`

See `research/topic4_github_pages_deployment_via_app.md` for 5 workflow examples.

### 5.3 Graphiti Protocol Provenance

App tokens enable:
- Cryptographic signing of Graphiti protocol events
- Non-repudiable audit trail (App identity, not user)
- Integration with SLSA/DSEE attestation chain

### 5.4 Webhook-Driven CI/CD

App webhooks (vs repo webhooks):
- `workflow_dispatch` event (App-only)
- `deployment_protection_rule` event (App-only)
- Higher rate limits (15,000/hr vs 5,000/hr)
- Not subject to SAML SSO

---

## 6. Operator Action Items

| # | Action | Who | Blocking? | Priority |
|---|--------|-----|-----------|----------|
| 1 | Download/generate PEM private key from GitHub App settings | OPERATOR | 🔴 YES | P0 |
| 2 | Add `GH_APP_PRIVATE_KEY` to repo secrets | OPERATOR | 🔴 YES | P0 |
| 3 | Verify GH_APP_ID and GH_APP_INSTALLATION_ID values match App settings | OPERATOR | 🔴 YES | P0 |
| 4 | Create 7-day temp PAT for interim use | OPERATOR | 🟡 YES | P1 |
| 5 | Update GH_PAT repo secret with temp PAT | SIDECAR (after #4) | 🟡 | P1 |
| 6 | Patch 4 workflows: GH_APP_SEC → GH_APP_PRIVATE_KEY | SIDECAR (after #2) | 🟡 | P1 |
| 7 | Create PAT health check workflow | SIDECAR | 🟢 No | P2 |
| 8 | Migrate sync-secrets workflows to App token | SIDECAR | 🟢 No | P2 |
| 9 | Update runner install scripts for App token | SIDECAR | 🟢 No | P2 |
| 10 | Remove embedded PAT from git remote | SIDECAR | 🟢 No | P3 |
| 11 | Delete GH_PAT repo secret | SIDECAR (after all migrated) | 🟢 No | P3 |
| 12 | Enable branch protection hard mode | OPERATOR | 🟢 No | P3 |

---

## 7. Research References

| File | Lines | Topic |
|------|-------|-------|
| `research/topic1_slsa_provenance_github_apps.md` | 888 | SLSA provenance with App signing |
| `research/topic2_pat_rotation_automation.md` | 912 | PAT rotation limitations & workarounds |
| `research/topic3_create_github-app-token.md` | 902 | Action internals & configuration |
| `research/topic4_github_pages_deployment_via_app.md` | 920 | Pages deployment via App |
| `research/topic5_self_hosted_runner_registration_app_tokens.md` | 1,369 | Runner registration with App tokens |

---

## 8. AGNOTE4482 Impact

This SITREP relates to:
- **§6.4** (suit updates as release concerns) — CI gate created, but CI itself runs on broken auth
- **§2** (Agent Zero baseline) — CI/CD is part of the baseline
- **§8** (docs parity) — hardening tracker workflow count is stale (says 17, actual is 30)

**Recommended tracker update:** Increment workflow count, add GitHub App auth gap as a hardening item.

---
`END SITREP`
