# GitHub App Permission Matrix — PMOVES.AI Configuration

**GRAPHITI_MARK:** `CONFIG::GITHUB_APP::PERMISSIONS::2026-04-23`
**Purpose:** Exact permissions, scopes, and webhook events needed to configure the GitHub App for PMOVES.AI
**App Origin:** Previously used for Transcribe/fetch on cataclysmstududios.net
**Target:** POWERFULMOVES/PMOVES.AI (and future PMOVES services)

---

## 1. Current App State Assessment

### What the Transcribe/Fetch App Likely Had

| Permission | Level | Reason (Transcribe/Fetch) |
|-----------|-------|---------------------------|
| Contents | Read | Clone repos for transcription |
| Metadata | Read | Always required |
| Pull requests | Read | Read PR content for processing |
| Issues | Read | Read issue context |
| Webhooks | — | Receive push/PR events |

### What PMOVES.AI Needs (Delta)

| Permission | Current (Est.) | Needed | Delta |
|-----------|-----------------|--------|-------|
| Contents | Read | **Read & Write** | ⬆️ Upgrade |
| Actions | None | **Read & Write** | 🆕 New |
| Administration | None | **Read & Write** | 🆕 New |
| Attestations | None | **Read & Write** | 🆕 New |
| Packages | None | **Read & Write** | 🆕 New |
| Pages | None | **Read & Write** | 🆕 New |
| Deployments | None | **Read & Write** | 🆕 New |
| Environments | None | **Read & Write** | 🆕 New |
| Metadata | Read | Read | ✅ No change |
| Pull requests | Read | **Read & Write** | ⬆️ Upgrade |
| Issues | Read | **Read & Write** | ⬆️ Upgrade |
| Workflows | None | **Read & Write** | 🆕 New |

### Recommendation: Separate App?

**Short answer:** For now, reuse with upgraded permissions. Consider splitting later.

| Approach | Pros | Cons |
|----------|------|------|
| **Reuse existing App** | One App ID, one private key, secrets already exist | Mixed concerns, broader permissions than Transcribe needs |
| **Create new PMOVES.AI App** | Clean separation, least-privilege per App | New App ID, new secrets, more setup |
| **Two Apps, shared runner** | Best practice | Complex runner config |

**Verdict:** Reuse for now. The Transcribe/fetch use case is dormant, and PMOVES.AI is the active project. Flag for future split if Transcribe resumes.

---

## 2. Exact Permission Configuration

### 2.1 Repository Permissions

Go to: `https://github.com/settings/developers` → Click the App → **Permissions** tab

| Permission | Level | Use Case |
|-----------|-------|----------|
| **Actions** | Read & Write | Trigger workflows, manage workflow runs, cancel/rerun, runner registration tokens |
| **Administration** | Read & Write | Manage runners, repository settings, branch protection (if needed) |
| **Attestations** | Read & Write | SLSA provenance — create and verify build attestations |
| **Contents** | Read & Write | Checkout code, push tags, create releases, git operations |
| **Deployments** | Read & Write | Create/update deployment records, deployment statuses |
| **Environments** | Read & Write | Manage deployment environments, protection rules |
| **Issues** | Read & Write | Create issues (PAT health check), manage labels, comment |
| **Metadata** | Read | **Always required — cannot be disabled** |
| **Packages** | Read & Write | Push/pull GHCR containers, manage package settings |
| **Pages** | Read & Write | Deploy to GitHub Pages, configure Pages settings, manage custom domains |
| **Pull requests** | Read & Write | Create PRs, comment, review, merge (future agent-driven PRs) |
| **Secrets** | Read & Write | Manage repo/org secrets (for sync-secrets workflow) |
| **Workflows** | Read & Write | Update workflow files, manage workflow approvals |

### 2.2 Organization Permissions (if installed at org level)

| Permission | Level | Use Case |
|-----------|-------|----------|
| **Members** | Read | List org members for runner access control |
| **Self-hosted runners** | Read & Write | Register/manage org-level runners |

### 2.3 Account-Level Permissions (User-to-Server)

| Permission | Level | Use Case |
|-----------|-------|----------|
| **Email addresses** | Read | Optional — for notifications |

---

## 3. Webhook Events

Go to: App settings → **Webhooks** tab → **Subscribe to events**

### 3.1 Required Events

| Event | Category | Why |
|-------|----------|-----|
| `push` | Code | Trigger builds on push to main/develop |
| `pull_request` | Code | Trigger CI on PRs, agent-driven PR creation |
| `workflow_run` | Actions | Chain workflows (e.g., build → deploy) |
| `workflow_dispatch` | Actions | Manual workflow triggers via App |
| `deployment` | Deployment | Track deployment lifecycle |
| `deployment_status` | Deployment | Monitor deployment outcomes |
| `release` | Release | Trigger builds on release creation |

### 3.2 Recommended Events

| Event | Category | Why |
|-------|----------|-----|
| `issues` | Issues | PAT health check creates issues, agent issue management |
| `issue_comment` | Issues | Agent responses to issue comments |
| `repository` | Meta | Track repo settings changes |
| `member` | Org | Track team membership changes |
| `check_run` | Actions | Monitor check status for provenance |
| `check_suite` | Actions | Monitor suite status |

### 3.3 Optional (Future)

| Event | Category | Why |
|-------|----------|-----|
| `page_build` | Pages | Track Pages build status |
| `star` | Meta | Track project popularity |
| `watch` | Meta | Track watchers |

---

## 4. Installation Configuration

### 4.1 Where to Install

| Option | Recommendation | Why |
|--------|---------------|-----|
| **All repositories** | ✅ **Recommended** | PMOVES.AI will spawn sub-repos for agents, claws, modules. One install = all covered. |
| Specific repositories | ❌ Not recommended | Would need to re-install for every new repo. |

### 4.2 Installation Steps

```
1. Go to: https://github.com/settings/installations
   OR: App settings → "Install App" → select POWERFULMOVES org

2. Select: "All repositories"

3. Click Install

4. Note the Installation ID from the URL:
   https://github.com/settings/installations/<INSTALLATION_ID>
   This should match the GH_APP_INSTALLATION_ID secret value.
```

### 4.3 Verify Installation ID

After installation, verify the Installation ID matches:

```bash
# Using JWT (see §6 for JWT generation)
curl -s -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations \
  | python3 -c 'import sys,json
for inst in json.load(sys.stdin):
    print(f"ID: {inst["id"]}, Account: {inst["account"]["login"]}, Repos: {inst["repository_selection"]}")'
```

Expected output:
```
ID: <matches GH_APP_INSTALLATION_ID>, Account: POWERFULMOVES, Repos: all
```

---

## 5. Private Key & Secret Reconciliation

### 5.1 The GH_APP_SEC Identity Crisis

The verify script (`pmoves/tools/verify_github_app_setup.py` line 146-148) expects `GH_APP_SEC` to be PEM-formatted:

```python
elif key == 'GH_APP_SEC':
    if not value.startswith('-----BEGIN'):
        return False, "must be PEM-formatted private key"
```

But `actions/create-github-app-token` is silently failing, meaning the actual secret value is likely the **OAuth client secret** (short string), not PEM.

### 5.2 Resolution

**Option A: Fix GH_APP_SEC to be the PEM key** (maintains backward compat with verify script)

```
1. App settings → Private keys → Generate a new private key
2. Download the .pem file
3. Update GH_APP_SEC secret with the full PEM content
4. No workflow changes needed
```

**Option B: Add new GH_APP_PRIVATE_KEY, keep GH_APP_SEC as OAuth secret** (cleaner separation)

```
1. Generate/download PEM from App settings
2. Add NEW secret: GH_APP_PRIVATE_KEY = <PEM content>
3. Patch 4 workflows: GH_APP_SEC → GH_APP_PRIVATE_KEY
4. Keep GH_APP_SEC for OAuth flows if needed
```

**Recommendation:** **Option A** — it's simpler, the verify script already expects it, and OAuth client secret is rarely needed for CI/CD (App-to-Server auth uses JWT+PEM, not OAuth). If OAuth is needed later, add `GH_APP_OAUTH_SECRET` separately.

### 5.3 Private Key Generation Steps

```
1. Go to: https://github.com/settings/developers
2. Click the App
3. Scroll to "Private keys" section
4. Click "Generate a private key"
5. A .pem file downloads automatically
6. Copy the ENTIRE content including:
   -----BEGIN RSA PRIVATE KEY-----
   <base64 content>
   -----END RSA PRIVATE KEY-----
7. Go to: https://github.com/POWERFULMOVES/PMOVES.AI/settings/secrets/actions
8. Update GH_APP_SECRET: paste the full PEM content
```

**Security note:** The .pem file is the only copy. Store it securely (not in the repo). If lost, generate a new one — old keys remain valid until deleted from App settings.

---

## 6. Verification Procedure

### 6.1 After Configuration, Run This

```bash
# Set values (operator fills in)
export APP_ID="<from App settings General page>"
export PEM_PATH="/path/to/downloaded/key.pem"

# Generate JWT
JWT=$(python3 -c "
import jwt, time
with open('$PEM_PATH') as f:
    key = f.read()
print(jwt.encode(
    {'iat': int(time.time()), 'exp': int(time.time()) + 600, 'iss': $APP_ID},
    key, algorithm='RS256'
))")

# List installations
echo "=== Installations ==="
curl -s -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations | python3 -m json.tool

# Get installation token (replace INSTALL_ID)
echo "=== Installation Token ==="
INSTALL_ID="<from above output>"
TOKEN=$(curl -s -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/$INSTALL_ID/access_tokens" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

# Test token
echo "=== Token Test ==="
curl -s -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/POWERFULMOVES/PMOVES.AI | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"Repo: {d["full_name"]}, Private: {d["private"]}")'
```

### 6.2 Quick Workflow Test

After updating GH_APP_SEC with PEM, trigger any workflow that uses `create-github-app-token` (e.g., `build-images.yml` via workflow_dispatch). Check that the App token step does NOT show "continue-on-error" fallback.

---

## 7. Future Agent/Claw Deployment Scenarios

Once the App is configured, these become possible:

| Scenario | How | Permissions Used |
|----------|-----|-----------------|
| **Agent creates PR** | App token → `gh pr create` in workflow | Contents:Write, Pull requests:Write |
| **Claw auto-deploys to VPS** | Workflow triggered by push → deploy via SSH | Actions:Write, Deployments:Write |
| **Agent responds to issues** | Webhook `issues` → workflow → `gh issue comment` | Issues:Write |
| **Provenance-signed release** | Build workflow → `attest-build-provenance` | Attestations:Write, Packages:Write |
| **Pages site update** | Workflow → deploy to gh-pages branch | Pages:Write, Contents:Write |
| **Runner auto-scaling** | ARC controller with App token | Administration:Write, Self-hosted runners:Write |
| **Secret sync across repos** | Workflow reads secrets, writes to other repos | Secrets:Write, Contents:Write |

---

## 8. Configuration Checklist (Operator Copy-Paste)

```
□ Go to https://github.com/settings/developers
□ Click the App
□ GENERAL TAB: Note the App ID → verify matches GH_APP_ID secret

□ PERMISSIONS TAB — Repository Permissions:
  □ Actions: Read & Write
  □ Administration: Read & Write
  □ Attestations: Read & Write
  □ Contents: Read & Write
  □ Deployments: Read & Write
  □ Environments: Read & Write
  □ Issues: Read & Write
  □ Metadata: Read (should be default)
  □ Packages: Read & Write
  □ Pages: Read & Write
  □ Pull requests: Read & Write
  □ Secrets: Read & Write
  □ Workflows: Read & Write

□ PERMISSIONS TAB — Organization Permissions:
  □ Members: Read
  □ Self-hosted runners: Read & Write

□ WEBHOOKS TAB — Subscribe to events:
  □ push
  □ pull_request
  □ workflow_run
  □ workflow_dispatch
  □ deployment
  □ deployment_status
  □ release
  □ issues
  □ issue_comment
  □ repository
  □ check_run
  □ check_suite

□ PRIVATE KEYS TAB:
  □ Generate a new private key (or download existing)
  □ Save the .pem file securely

□ INSTALLATION:
  □ Install on POWERFULMOVES org
  □ Select "All repositories"
  □ Note Installation ID from URL
  □ Verify matches GH_APP_INSTALLATION_ID secret

□ REPO SECRETS:
  □ Update GH_APP_SEC with full PEM content
  □ Verify GH_APP_ID matches App settings
  □ Verify GH_APP_INSTALLATION_ID matches installation URL
  □ Verify GH_APP_CLIENT_ID matches App settings

□ TEST:
  □ Run verification commands from §6.1
  □ Trigger test workflow (build-images.yml workflow_dispatch)
  □ Confirm App token step succeeds (no fallback)
```

---

## 9. Relationship to SITREP

This document is the **configuration companion** to `github-app-sitrep-and-pat-runbook.md`.

- SITREP: *What's broken and why*
- This document: *Exactly how to configure the App to fix it*

Once configuration is complete, execute SITREP Phase 2 (patch workflows) and Phase 3 (migrate runners).

---
`END CONFIG MATRIX`
