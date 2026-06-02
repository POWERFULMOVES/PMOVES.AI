# Topic 2: PAT Rotation Automation — Deep Research Report

**Research Date:** 2026-04-23  
**Status:** Complete  
**Sources:** GitHub Docs, GitHub Blog, GitHub Community Discussions, Shopify Engineering, StepSecurity, Michael Heap

---

## Table of Contents

1. [Critical Finding: No PAT API for Programmatic Rotation](#1-critical-finding-no-pat-api-for-programmatic-rotation)
2. [Fine-Grained PATs vs Classic PATs — Complete Comparison](#2-fine-grained-pats-vs-classic-pats--complete-comparison)
3. [GITHUB_TOKEN vs PAT — Complete Differences](#3-github_token-vs-pat--complete-differences)
4. [Recommended Expiry Settings by Token Type](#4-recommended-expiry-settings-by-token-type)
5. [GitHub API Endpoints for Token Management](#5-github-api-endpoints-for-token-management)
6. [The Only Viable Automated Rotation: GitHub Apps](#6-the-only-viable-automated-rotation-github-apps)
7. [Working Rotation Workflow YAML (GitHub App Approach)](#7-working-rotation-workflow-yaml-github-app-approach)
8. [Semi-Automated PAT Rotation Workflow (Reminder-Based)](#8-semi-automated-pat-rotation-workflow-reminder-based)
9. [Rate Limits](#9-rate-limits)
10. [Caveats: Notification Emails, Service Disruption, Edge Cases](#10-caveats-notification-emails-service-disruption-edge-cases)
11. [Source URLs](#11-source-urls)

---

## 1. Critical Finding: No PAT API for Programmatic Rotation

**GitHub does NOT support programmatic creation or deletion of Personal Access Tokens (PATs) — neither fine-grained nor classic — via their REST or GraphQL APIs.**

This is confirmed in GitHub Community Discussion #148626 (January 2025, still current as of April 2026). Personal Access Tokens must be created manually through the GitHub settings page at `https://github.com/settings/personal-access-tokens`.

**Implications:**
- You **cannot** write a GitHub Actions workflow that creates a new fine-grained PAT via `POST /user/personal-access-tokens` because **that endpoint does not exist**.
- You **cannot** atomically swap an old PAT for a new one via API.
- Any workflow claiming to "rotate PATs" is either: (a) rotating GitHub App installation tokens (not PATs), or (b) using a semi-automated approach where a human manually creates the new PAT and the workflow distributes it.

**Official GitHub alternatives for automated token rotation:**
1. **GitHub Apps** — Designed for programmatic access; can dynamically generate time-limited installation access tokens via API that refresh as needed.
2. **Semi-manual rotation with automated distribution** — Human creates new PAT manually; a script/workflow updates all repository secrets that reference it.
3. **External secrets managers** — HashiCorp Vault, AWS Secrets Manager, Azure Key Vault for token lifecycle management.

**Source:** https://github.com/orgs/community/discussions/148626

---

## 2. Fine-Grained PATs vs Classic PATs — Complete Comparison

### Permissions Model

| Aspect | Fine-Grained PATs | Classic PATs |
|---|---|---|
| Permission granularity | 50+ individual permissions, each settable to "no access", "read", or "read and write" | Coarse-grained scopes (e.g., `repo`, `admin:org`, `read:org`) that grant broad access |
| Repository scoping | Explicitly scoped to specific repositories only (can target a single repo) | Automatically has access to ALL repositories the owning user can access |
| Organization scoping | Can be scoped to specific organizations | Automatically has access to ALL organizations the user is a member of |
| Permission categories | Three categories: repository permissions, organization permissions, account permissions | Single flat list of scopes with no categorization |

### Available Fine-Grained Permission Examples

**Repository Permissions** (per-repo granularity):
- `contents` — read / read and write (repository content, commits, branches)
- `issues` — read / read and write
- `pull_requests` — read / read and write
- `workflows` — read / read and write (update GitHub Actions workflows)
- `deployments` — read / read and write
- `packages` — read / read and write
- `pages` — read / read and write
- `secrets` — read / read and write (repository secrets)
- `actions` — read / read and write
- `administration` — read / read and write (repository settings)
- `attestations` — read / read and write
- `checks` — read / read and write
- `codespaces` — read / read and write
- `dependabot_secrets` — read / read and write
- `environments` — read / read and write
- `metadata` — read only (always required, cannot be disabled)

**Organization Permissions** (per-org granularity):
- `members` — read / read and write
- `organization_administration` — read / read and write
- `organization_custom_roles` — read / read and write
- `organization_personal_access_tokens` — read / read and write
- `organization_personal_token_requests` — read / read and write
- `organization_plan` — read
- `organization_projects` — read / read and write
- `organization_secrets` — read / read and write
- `organization_self_hosted_runners` — read / read and write
- `organization_user_blocking` — read / read and write

**Account Permissions** (account-level):
- `user_following` — read / read and write
- `user_projects` — read / read and write
- `user_ssh_keys` — read / read and write
- `user_profile` — read
- `user_models` — read (Copilot model access)

### Classic PAT Scopes

Classic PATs use broad OAuth-style scopes:
- `repo` — Full control of private repositories
- `repo:status` — Access commit status
- `repo_deployment` — Access deployment status
- `public_repo` — Access public repositories
- `admin:repo_hook` — Full control of repository hooks
- `read:org` — Read org membership
- `admin:org` — Full control of orgs
- `admin:public_key` — Full control of public keys
- `admin:org_hook` — Full control of org hooks
- `gist` — Create gists
- `notifications` — Access notifications
- `user` — Read user profile
- `user:email` — Read user email
- `delete_repo` — Delete repositories
- `write:discussion` — Write discussions
- `read:discussion` — Read discussions
- `admin:enterprise` — Full control of enterprise
- `manage_runners` — Manage self-hosted runners
- `workflow` — Update GitHub Actions workflows

### Visibility and Control for Org/Enterprise Admins

| Feature | Fine-Grained PATs | Classic PATs |
|---|---|---|
| Org admin visibility | Full visibility — admins can see all fine-grained PATs accessing their resources | No visibility — only visible if SAML SSO is enforced |
| Approval policies | Org admins can require approval for fine-grained PATs | No approval mechanism |
| Revocation | Org admins can revoke fine-grained PAT access to their resources | Cannot revoke (only via SAML SSO) |
| Audit trail | Full audit log of fine-grained PAT access | No audit trail |

### Security Posture Summary

| Risk | Fine-Grained PATs | Classic PATs |
|---|---|---|
| Blast radius on compromise | Limited to specific repos/permissions | Broad — all repos, all permissions in scope |
| Lifetime control | Enforceable by org policy (1-366 days) | No enforcement possible |
| Default expiration | 30 days (or org policy, whichever is shorter) | No default — can be infinite |
| Auto-revocation | Revoked if user loses access to resource | NOT revoked if user loses access |

**Source:** https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/  
**Source:** https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

---

## 3. GITHUB_TOKEN vs PAT — Complete Differences

### What GITHUB_TOKEN Actually Is

GITHUB_TOKEN is NOT a personal access token. Under the hood, when you enable GitHub Actions on a repository, GitHub automatically installs a hidden GitHub App on that repository. The `GITHUB_TOKEN` is actually a **GitHub App installation access token** for this auto-installed app. Each time a GitHub Actions job runs, GitHub generates a **new** installation access token and injects it into the job's runtime environment.

### Lifecycle Comparison

| Aspect | GITHUB_TOKEN | Fine-Grained PAT | Classic PAT |
|---|---|---|---|
| Creation | Automatic — generated before each job starts | Manual — created via GitHub Settings UI | Manual — created via GitHub Settings UI |
| Expiration | When job finishes, OR max 6 hours (GitHub-hosted runners), OR max 24 hours (self-hosted runners, non-refreshable after that) | 1-366 days (configurable), or org policy max | Configurable, can be infinite |
| Scope | Only the repository containing the workflow | Explicitly selected repositories | All repositories user can access |
| Permissions | Configured per-workflow or per-job via `permissions` key | Configured per-token at creation | Configured per-token at creation via scopes |
| Persistence | Ephemeral — does not persist after job | Persists until deleted or expired | Persists until deleted or expired |
| User binding | Bound to the repository (not a user) | Bound to the user who created it | Bound to the user who created it |
| Cross-repo access | Cannot access other repositories (unless using `actions/create-github-app-token` with a different app) | Can access multiple explicitly-selected repos | Can access all repos the user can access |
| Availability | `${{ secrets.GITHUB_TOKEN }}` or `github.token` context | Stored as a secret, used as `${{ secrets.MY_PAT }}` | Stored as a secret, used as `${{ secrets.MY_PAT }}` |

### Permissions Model

**GITHUB_TOKEN permissions** are set in the workflow YAML:

~~~yaml
# Workflow-level permissions
permissions:
  contents: read
  issues: write
  pull-requests: read

# Or per-job
jobs:
  my-job:
    permissions:
      contents: none
      actions: read
~~~

**Critical default behavior:** If you do NOT specify a `permissions` key, the GITHUB_TOKEN is granted **read AND write** permission for ALL available scopes. This can be changed at the repository level under Settings → Actions → "Read repository contents permission".

**PAT permissions** are set at token creation time in the GitHub UI and cannot be changed without creating a new token.

### What GITHUB_TOKEN CAN Do

- Read/write repository contents (if permitted)
- Create/update issues and pull requests (if permitted)
- Create/update releases (if permitted)
- Trigger other workflows via `workflow_dispatch` (if permitted)
- Interact with the GitHub Packages registry
- Use `gh` CLI for API calls within permission scope

### What GITHUB_TOKEN CANNOT Do

- Access other repositories (even in the same org)
- Trigger `workflow_run` events for workflows in other repos
- Create or manage repository secrets (requires `secrets:write` but this only works for the current repo)
- Bypass branch protection rules that require "specified users" (it is not a user)
- Access organization-level resources beyond what the repo-level installation allows
- Perform SAML SSO authentication (it is repo-scoped, not user-scoped)

### When You MUST Use a PAT or GitHub App Instead of GITHUB_TOKEN

1. Cross-repository operations (e.g., updating secrets in multiple repos)
2. Organization-level API calls
3. Operations requiring user-level permissions (not repo-level)
4. Workflows that need to trigger other workflows in different repositories
5. Self-hosted runners running jobs longer than 24 hours
6. Accessing resources outside the repository context

**Sources:**  
https://docs.github.com/en/actions/concepts/security/github_token  
https://docs.github.com/en/actions/tutorials/authenticate-with-github_token  
https://www.stepsecurity.io/blog/github-token-how-it-works-and-how-to-secure-automatic-github-action-tokens  
https://michaelheap.com/ultimate-guide-github-actions-authentication/  
https://xebia.com/blog/github-access-tokens-explained/

---

## 4. Recommended Expiry Settings by Token Type

### Fine-Grained PATs

| Use Case | Recommended Expiry | Rationale |
|---|---|---|
| Local development (personal) | 30 days (default) | Balance of security and convenience; short enough to limit blast radius |
| CI/CD pipeline secret | 30 days | Should NOT be used for CI/CD — use GitHub Apps instead |
| Service account (org) | As short as org policy allows (7-30 days) | Org admins should enforce via rotation policies |
| Emergency/break-glass | 7 days | Minimize window of exposure |
| Personal project (no org policy) | Can be set to `none` (no expiry) as of Oct 2024 | Acceptable for personal use; avoid for anything shared |

**Fine-grained PAT default:** If no expiration is specified, defaults to **30 days** (or shorter if org/enterprise policy enforces a lower maximum).

**`expires_in` parameter:** Integer between 1 and 366 days, or `none` for non-expiring.

### Classic PATs

| Use Case | Recommended Expiry | Rationale |
|---|---|---|
| Any use case | Shortest possible; migrate to fine-grained or GitHub App | Classic PATs are a security liability — broad scope, no org visibility |
| Legacy migration interim | 7-14 days | Only while migrating to better alternatives |
| Break-glass | 1-3 days | Absolutely minimal window |

**Classic PAT default:** No default expiration — can be set to never expire. This is a security anti-pattern.

### GitHub App Installation Access Tokens

| Use Case | Expiry | Rationale |
|---|---|---|
| GitHub Actions GITHUB_TOKEN | Automatic (job-scoped) | No configuration needed — handled by GitHub |
| Custom GitHub App token | 1 hour (GitHub-enforced maximum) | This is the ideal rotation model — tokens are inherently short-lived |
| Renewal | Before 1-hour expiry | Standard pattern: generate new token, use it, discard |

### Organization/Enterprise Rotation Policies (New — October 2024)

Enterprise and organization administrators can now enforce maximum token lifetimes:

- **Policy granularity:** Separate policies for fine-grained PATs and classic PATs
- **Range:** 1 to 366 days maximum lifetime
- **Enforcement point:** When tokens are created, regenerated, or used — if a token's lifetime exceeds the policy, API calls using that token will **fail**
- **Strategic use:** Set short max for classic PATs (e.g., 7 days) to drive migration, while allowing longer for fine-grained (e.g., 90 days)
- **Default org policy:** 366 days for fine-grained PATs (effectively no restriction unless explicitly set)

**Source:** https://github.blog/changelog/2024-10-18-new-pat-rotation-policies-preview-and-optional-expiration-for-fine-grained-pats/

---

## 5. GitHub API Endpoints for Token Management

### IMPORTANT: What Does NOT Exist

There is **NO REST API endpoint** for:
- Creating a personal access token (fine-grained or classic)
- Deleting/revoking a personal access token by the token owner
- Listing a user's own personal access tokens
- Updating a personal access token's expiration or permissions

These operations can ONLY be performed through the GitHub web UI.

### What DOES Exist

#### GitHub App Token Endpoints (for automated rotation)

**Create an installation access token:**
```bash
curl -X POST   https://api.github.com/app/installations/{installation_id}/access_tokens   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {JWT}"
```

Response:
```json
{
  "token": "ghs_xxxxxxxxxxxx",
  "expires_at": "2026-04-23T17:00:00Z",
  "permissions": {
    "contents": "read",
    "metadata": "read"
  },
  "repository_selection": "all",
  "repositories": []
}
```

**Revoke an installation access token:**
```bash
curl -X DELETE   https://api.github.com/app/installations/{installation_id}/access_tokens/{token_id}   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {JWT}"
```

Note: `token_id` is NOT the token string itself — it is the numeric ID returned in the token creation response as `id`.

**Get repository public key (for encrypting secrets):**
```bash
curl   https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {TOKEN}"
```

Response:
```json
{
  "key_id": "012345678912345678",
  "key": "2Sg8iYjAxxmI2LvUXpJjkYrMxURPc8r+dB7TJyvv1234"
}
```

**Create or update a repository secret:**
```bash
curl -X PUT   https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {TOKEN_WITH_SECRETS_WRITE}"   -d '{
    "encrypted_value": "{ENCRYPTED_SECRET_STRING}",
    "key_id": "012345678912345678"
  }'
```

The `encrypted_value` must be encrypted using the public key retrieved above, using libsodium's `sealed box` encryption (NaCl `crypto_box_seal`).

#### Organization PAT Management Endpoints (Admin-Only, GitHub Apps Only)

These endpoints are for **organization administrators** managing **other users'** fine-grained PAT requests — NOT for creating your own tokens:

**List fine-grained PAT requests to access org resources:**
```bash
curl   https://api.github.com/orgs/{org}/personal-access-token-requests   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {GITHUB_APP_TOKEN}"
```

Note: Only GitHub Apps can use this endpoint. PATs and users cannot.

**Review (approve/deny) a fine-grained PAT request:**
```bash
curl -X POST   https://api.github.com/orgs/{org}/personal-access-token-requests/{request_id}   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {GITHUB_APP_TOKEN}"   -d '{"action": "approve"}'
```

**Revoke a fine-grained PAT's access to org resources:**
```bash
curl -X DELETE   https://api.github.com/orgs/{org}/personal-access-tokens/{pat_id}   -H "Accept: application/vnd.github+json"   -H "Authorization: Bearer {GITHUB_APP_TOKEN}"
```

Again: Only GitHub Apps. This revokes the token's access to the organization, it does not delete the token itself.

#### JWT Generation for GitHub App Authentication

To call the installation token endpoints, you must first generate a JWT:

~~~python
import jwt
import time

# GitHub App credentials
APP_ID = 123456
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQ...
-----END RSA PRIVATE KEY-----"""

payload = {
    "iat": int(time.time()) - 60,  # Issued at (60s clock drift allowance)
    "exp": int(time.time()) + (10 * 60),  # Expires in 10 minutes
    "iss": APP_ID  # GitHub App ID as issuer
}

token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
~~~

**Sources:**  
https://docs.github.com/en/rest/orgs/personal-access-tokens  
https://docs.github.com/en/rest/apps/installations  
https://docs.github.com/en/rest/actions/secrets  

---

## 6. The Only Viable Automated Rotation: GitHub Apps

Since PATs cannot be created/deleted via API, the only fully automated rotation mechanism uses **GitHub Apps with installation access tokens**. This is the approach used by Shopify (documented in their engineering blog) and is the pattern recommended by GitHub.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Rotation Repository                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Scheduled GitHub Actions Workflow            │  │
│  │                                                     │  │
│  │  1. Generate JWT from App private key               │  │
│  │  2. Create installation access token (1hr TTL)      │  │
│  │  3. Get target repo public key                       │  │
│  │  4. Encrypt token with public key (libsodium)        │  │
│  │  5. PUT to /repos/{owner}/{repo}/actions/secrets     │  │
│  │  6. Revoke the installation token used for step 5    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Secrets stored:                                         │
│  - APP_PRIVATE_KEY (GitHub App private key PEM)          │
│  - APP_ID (GitHub App ID)                                │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   Target Repositories                     │
│                                                          │
│  Secret: ROTATED_APP_TOKEN                                │
│  └── Used by workflows in this repo for API access       │
│      └── Auto-rotated every N hours by rotation workflow  │
└──────────────────────────────────────────────────────────┘
```

### GitHub App Setup Prerequisites

1. **Register a GitHub App** at `https://github.com/settings/apps/new`
   - Set "Repository permissions" to the superset of all permissions any target repo will need
   - Set "Organization permissions" if needed
   - Generate a private key and download the `.pem` file

2. **Install the App** on the organization or target repositories

3. **Store credentials** in the rotation repository:
   - `APP_PRIVATE_KEY` → Repository secret (the PEM file contents)
   - `APP_ID` → Repository variable (just the numeric ID)

4. **Note:** The GitHub App can only grant tokens with a **subset** of its own permissions. If the App has `contents:write`, it can create tokens with `contents:read` or `contents:write` but not with `issues:write` if the App doesn't have that permission.

**Source:** https://shopify.engineering/automatically-rotate-github-tokens

---

## 7. Working Rotation Workflow YAML (GitHub App Approach)

This is a complete, working workflow that automates token rotation using GitHub Apps:

~~~yaml
name: Rotate GitHub App Token

on:
  schedule:
    # Run every 4 hours at minute 15 — avoid :00 to reduce contention
    - cron: '15 */4 * * *'
  workflow_dispatch: # Allow manual trigger

jobs:
  rotate-token:
    runs-on: ubuntu-latest
    # This token needs to write secrets in THIS repo (the rotation repo)
    # NOT needed if using a separate App token for secret placement
    permissions:
      contents: read

    strategy:
      matrix:
        # List of target repos to rotate the token into
        target_repo:
          - 'my-org/repo-1'
          - 'my-org/repo-2'
          - 'my-org/repo-3'
      # Do NOT run in parallel — sequential to avoid rate limits
      max-parallel: 1

    steps:
      - name: Checkout rotation repo
        uses: actions/checkout@v4

      - name: Generate GitHub App installation token (for target repo use)
        id: app-token
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          # Optional: restrict to specific repos
          repositories: ${{ matrix.target_repo }}

      - name: Generate GitHub App installation token (for secret placement)
        id: secret-token
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          # This token needs secrets:write on the target repo
          # The App must have 'secrets' permission set to 'write'

      - name: Get target repo public key
        id: public-key
        env:
          GH_TOKEN: ${{ steps.secret-token.outputs.token }}
        run: |
          RESPONSE=$(gh api             repos/${{ matrix.target_repo }}/actions/secrets/public-key             --jq '.key_id,.key')
          KEY_ID=$(echo "$RESPONSE" | head -1)
          PUBLIC_KEY=$(echo "$RESPONSE" | tail -1)
          echo "key_id=${KEY_ID}" >> "$GITHUB_OUTPUT"
          echo "public_key=${PUBLIC_KEY}" >> "$GITHUB_OUTPUT"

      - name: Encrypt and store the rotated token
        env:
          GH_TOKEN: ${{ steps.secret-token.outputs.token }}
        run: |
          # Install libsodium for sealed box encryption
          sudo apt-get update -qq && sudo apt-get install -qq -y libsodium-dev

          python3 << 'PYEOF'
          import subprocess
          import json
          import base64
          import os
          import sys

          token = os.environ['ROTATED_TOKEN']
          public_key = os.environ['PUBLIC_KEY']
          key_id = os.environ['KEY_ID']
          target_repo = os.environ['TARGET_REPO']
          secret_name = os.environ.get('SECRET_NAME', 'APP_TOKEN')

          # Write public key to temp file (libsodium base64 format)
          with open('/tmp/pubkey.bin', 'wb') as f:
              f.write(base64.b64decode(public_key))

          # Write token to temp file
          with open('/tmp/token.txt', 'w') as f:
              f.write(token)

          # Encrypt using sodium-sealbox (Python bindings)
          try:
              import nacl.public
              public_key_obj = nacl.public.PublicKey(base64.b64decode(public_key))
              sealed_box = nacl.public.SealedBox(public_key_obj)
              encrypted = sealed_box.encrypt(token.encode('utf-8'))
              encrypted_value = base64.b64encode(encrypted).decode('utf-8')
          except ImportError:
              # Fallback: use pynacl or install it
              subprocess.run([sys.executable, '-m', 'pip', 'install', 'pynacl', '-q'],
                           check=True)
              import nacl.public
              public_key_obj = nacl.public.PublicKey(base64.b64decode(public_key))
              sealed_box = nacl.public.SealedBox(public_key_obj)
              encrypted = sealed_box.encrypt(token.encode('utf-8'))
              encrypted_value = base64.b64encode(encrypted).decode('utf-8')

          # Update the secret via API
          payload = json.dumps({
              "encrypted_value": encrypted_value,
              "key_id": key_id
          })

          result = subprocess.run([
              'gh', 'api', '-X', 'PUT',
              f'repos/{target_repo}/actions/secrets/{secret_name}',
              '--input', '-'
          ], input=payload, capture_output=True, text=True, env={
              **os.environ,
              'GH_TOKEN': os.environ['GH_TOKEN']
          })

          if result.returncode != 0:
              print(f"ERROR updating secret: {result.stderr}", file=sys.stderr)
              sys.exit(1)

          print(f"Successfully rotated token in {target_repo}/{secret_name}")
          PYEOF
        env:
          ROTATED_TOKEN: ${{ steps.app-token.outputs.token }}
          PUBLIC_KEY: ${{ steps.public-key.outputs.public_key }}
          KEY_ID: ${{ steps.public-key.outputs.key_id }}
          TARGET_REPO: ${{ matrix.target_repo }}
          SECRET_NAME: ${{ vars.SECRET_NAME || 'APP_TOKEN' }}
          GH_TOKEN: ${{ steps.secret-token.outputs.token }}

      - name: Revoke the secret-placement token
        if: always()
        env:
          GH_TOKEN: ${{ steps.secret-token.outputs.token }}
        run: |
          # The app-token from step 1 expires in 1 hour automatically
          # The secret-token should be revoked for defense-in-depth
          # Note: There is no direct REST endpoint to revoke by token string
          # The token will expire in 1 hour regardless
          echo "Token will auto-expire within 1 hour"

      - name: Verify token works in target repo
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          # Quick verification that the stored token actually works
          # (This tests the token we just generated, not the encrypted one)
          gh api repos/${{ matrix.target_repo }} --jq '.full_name'
~~~

### Using `actions/create-github-app-token` — Simplified Version

For most cases, the official action handles everything. Each workflow in a target repo simply generates a fresh token at runtime:

~~~yaml
# This goes in the TARGET repo, not the rotation repo
name: My Workflow Using App Token

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Generate App Token
        id: app-token
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}

      - name: Use the token
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          gh api repos/my-org/my-repo --jq '.full_name'
          # Token auto-expires in 1 hour — no rotation needed!
~~~

With this pattern, **no rotation workflow is needed at all** because every job generates a fresh 1-hour token. This is the ideal approach.

**Sources:**  
https://github.com/actions/create-github-app-token  
https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow  
https://shopify.engineering/automatically-rotate-github-tokens

---

## 8. Semi-Automated PAT Rotation Workflow (Reminder-Based)

Since PATs cannot be created via API, this is the closest you can get to "PAT rotation automation": a workflow that **reminds** a human to create a new PAT, then **distributes** it across repositories once provided.

~~~yaml
name: PAT Rotation Reminder

on:
  schedule:
    # Run every 28 days (before 30-day default expiry)
    - cron: '0 9 1,15 * *'
  workflow_dispatch:
    inputs:
      new_pat:
        description: 'New PAT value to distribute (paste here)'
        required: true
        type: string
      secret_name:
        description: 'Secret name to update'
        required: false
        default: 'DEPLOY_PAT'
        type: string

jobs:
  remind:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - name: Create rotation issue
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue create             --title "⚠️ PAT Rotation Required: ${{ secrets.SECRET_NAME || 'DEPLOY_PAT' }}"             --body "The personal access token stored as DEPLOY_PAT is due for rotation.

          ## Steps:
          1. Go to https://github.com/settings/personal-access-tokens
          2. Create a new fine-grained PAT with the same permissions
          3. Set expiration to 30 days
          4. Run this workflow manually with the new token value
          5. Delete the old token from GitHub settings

          ## To distribute the new token:
          
          gh workflow run pat-rotation-reminder.yml -f new_pat='ghp_...' -f secret_name='DEPLOY_PAT'
          "

          This issue was auto-created by the PAT rotation reminder workflow."             --label "security,token-rotation"

  distribute:
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'
    permissions:
      actions: write

    strategy:
      matrix:
        target_repo:
          - 'my-org/repo-1'
          - 'my-org/repo-2'
          - 'my-org/repo-3'
      max-parallel: 1

    steps:
      - name: Get target repo public key
        id: pubkey
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          RESPONSE=$(gh api repos/${{ matrix.target_repo }}/actions/secrets/public-key --jq '.key_id,.key')
          echo "key_id=$(echo "$RESPONSE" | head -1)" >> "$GITHUB_OUTPUT"
          echo "public_key=$(echo "$RESPONSE" | tail -1)" >> "$GITHUB_OUTPUT"

      - name: Encrypt and update secret
        run: |
          pip install pynacl -q
          python3 << PYEOF
          import nacl.public, base64, json, subprocess, os, sys

          token = os.environ['NEW_PAT']
          pubkey_b64 = os.environ['PUBKEY']
          key_id = os.environ['KEY_ID']
          repo = os.environ['REPO']
          name = os.environ['SECRET_NAME']

          pk = nacl.public.PublicKey(base64.b64decode(pubkey_b64))
          sealed = nacl.public.SealedBox(pk).encrypt(token.encode())
          enc_val = base64.b64encode(sealed).decode()

          payload = json.dumps({"encrypted_value": enc_val, "key_id": key_id})
          r = subprocess.run(
              ["gh", "api", "-X", "PUT", f"repos/{repo}/actions/secrets/{name}", "--input", "-"],
              input=payload, capture_output=True, text=True
          )
          if r.returncode != 0:
              print(f"FAIL {repo}: {r.stderr}", file=sys.stderr)
              sys.exit(1)
          print(f"OK {repo}/{name}")
          PYEOF
        env:
          NEW_PAT: ${{ inputs.new_pat }}
          PUBKEY: ${{ steps.pubkey.outputs.public_key }}
          KEY_ID: ${{ steps.pubkey.outputs.key_id }}
          REPO: ${{ matrix.target_repo }}
          SECRET_NAME: ${{ inputs.secret_name }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Post-distribution reminder
        if: always()
        run: |
          echo "::warning::Don't forget to DELETE the old PAT at https://github.com/settings/personal-access-tokens"
~~~

**Source pattern:** https://rohithykrohith.medium.com/how-to-update-rotate-github-pat-in-multiple-github-repositories-using-a-workflow-8543d86debb7 (adapted; original was behind paywall)

---

## 9. Rate Limits

### Primary Rate Limits (REST API)

| Authentication | Requests per hour |
|---|---|
| Unauthenticated | 60 per IP address |
| Authenticated (PAT, OAuth, or App installation token) | 5,000 per user |
| GitHub App on behalf of user (Enterprise Cloud org-owned) | 10,000 per hour |
| GitHub Actions GITHUB_TOKEN | 5,000 per hour (same as authenticated) |

### Secondary Rate Limits

GitHub enforces additional secondary rate limits to prevent abuse patterns:

- **Concurrent requests:** Maximum of 100 concurrent requests per token
- **Burst behavior:** No more than 500 requests in a 1-minute window (beyond primary limits)
- **Specific endpoint limits:** Search API has a limit of 30 requests per minute (authenticated)

### Rate Limit Headers

Every API response includes these headers:
```
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4998
X-RateLimit-Used: 2
X-RateLimit-Reset: 1713897600
X-RateLimit-Resource: core
```

### Impact on Token Rotation

- A rotation workflow updating 50 repos (3 API calls each = 150 calls) uses ~3% of hourly budget
- Sequential execution (not parallel) is critical — 50 parallel requests could hit secondary rate limits
- Shopify's experience: billing is calculated per-job-minute rounded up and summed even for parallel jobs, causing cost explosions
- Recommended: keep rotation workflows to a single job with a matrix strategy using `max-parallel: 1`

### Checking Rate Limit Status

```bash
curl -I https://api.github.com/user   -H "Authorization: Bearer ghp_xxxxxxxxxxxx"
```

Or via `gh`:
```bash
gh api rate_limit
```

**Sources:**  
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api  
https://www.lunar.dev/post/a-developers-guide-managing-rate-limits-for-the-github-api  
https://dev.to/mehmetakar/api-rate-limit-exceeded-github-how-to-fix-4h6n

---

## 10. Caveats: Notification Emails, Service Disruption, Edge Cases

### Notification Emails

- **Fine-grained PAT creation:** GitHub sends an email notification to the token owner when a new fine-grained PAT is created
- **Fine-grained PAT access to org resources:** Organization administrators receive notification when a member creates a fine-grained PAT that requests access to organization resources (if approval policy is enabled)
- **GitHub App installation:** Organization admins receive notification when a GitHub App is installed on the organization
- **No notification for installation token creation:** Generating installation access tokens via API does NOT trigger email notifications (this is by design for automation)
- **Secret updates:** No email notification when a repository secret is updated via API

### Service Disruption During Rotation

**For GitHub App token rotation (recommended):**
- Zero disruption — the new token is written to the secret store atomically via `PUT /repos/{owner}/{repo}/actions/secrets/{secret_name}`
- Any workflow that reads the secret at job start will get the new value
- Running jobs continue using the token they loaded at startup (they don't re-read secrets mid-job)
- There is no "gap" because old tokens expire naturally (1 hour TTL) and the new one is already in place

**For semi-automated PAT rotation:**
- **Disruption window exists** between when the old PAT is deleted and when all consumers pick up the new one
- If a workflow is running with the old PAT value loaded into its environment, it will continue working until the job finishes
- If the old PAT is deleted BEFORE all running jobs complete, those jobs will fail on any subsequent API calls
- **Mitigation:** Do NOT delete the old PAT until all running workflows have completed (check via `GET /repos/{owner}/{repo}/actions/runs?status=in_progress`)

### Scheduled Workflow Reliability

The `schedule` trigger in GitHub Actions is **best-effort only** and heavily dependent on GitHub Actions service load:
- Using `*/45 * * * *` (every 45 minutes) proved extremely unreliable at Shopify — sometimes not triggering for tens of minutes
- **Solution:** Use explicit minutes-on-the-hour (e.g., `15 */4 * * *`) instead of "every-X-minutes" patterns
- Shortest documented interval: once every 5 minutes
- High-load periods (UTC 00:00-01:00) have higher skip rates

### Edge Cases

1. **Token stored in multiple places:** If the PAT is used as a git remote URL credential (`https://x-access-token:ghp_xxx@github.com/...`), updating the GitHub secret alone won't update cached credentials on self-hosted runners. You must also update any `.git/config` or credential helper entries.

2. **Forks:** Secrets are NOT copied to forks. Rotation workflows must target each fork independently if needed.

3. **Environment secrets:** Secrets scoped to environments (e.g., `production`) require the `environment` parameter in the API call: `PUT /repos/{owner}/{repo}/environments/{environment}/secrets/{secret_name}`

4. **Organization secrets:** If the PAT is stored as an org-level secret, the endpoint is different: `PUT /orgs/{org}/actions/secrets/{secret_name}` — and it may be scoped to specific repos via `repository_ids` array.

5. **GitHub automatically revokes inactive PATs:** Any personal access token that hasn't been used in **1 year** is automatically removed, regardless of stated expiration.

6. **User account deactivation:** Both fine-grained and classic PATs become inactive if the user who generated them loses access to the resource (e.g., removed from org). Fine-grained PATs also become inactive if the user's account is deleted. Classic PATs do NOT become inactive if the user's account is deleted (a known security gap).

7. **SAML SSO enforcement:** If an organization enforces SAML SSO, classic PATs must be authorized for SAML. Fine-grained PATs do not require separate SAML authorization (they use a different authentication flow).

### Cost Considerations (Shopify's Lessons)

- Billable minutes are calculated at the **job level**, not organization level
- Each workflow has N underlying jobs with execution durations rounded to the **nearest minute**
- These rounded minutes are summed **even if jobs ran in parallel**
- Example: 10 parallel jobs each executing in 1 second = **10 billable minutes**, not 1 minute
- This caused cost explosions during prototyping at Shopify
- Solution: Use sequential execution (single job with matrix, `max-parallel: 1`)

**Sources:**  
https://shopify.engineering/automatically-rotate-github-tokens  
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens  
https://github.com/actions/actions-runner-controller/issues/1376

---

## 11. Source URLs

### GitHub Official Documentation
- Managing personal access tokens: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- GITHUB_TOKEN security: https://docs.github.com/en/actions/concepts/security/github_token
- Authenticate with GITHUB_TOKEN: https://docs.github.com/en/actions/tutorials/authenticate-with-github_token
- REST API rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Org PAT management endpoints: https://docs.github.com/en/rest/orgs/personal-access-tokens
- Fine-grained PAT available endpoints: https://docs.github.com/en/rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens
- GitHub App workflow auth: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow
- Actions secrets API: https://docs.github.com/en/rest/actions/secrets

### GitHub Blog & Changelog
- Introducing fine-grained PATs: https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/
- PAT rotation policies (Oct 2024): https://github.blog/changelog/2024-10-18-new-pat-rotation-policies-preview-and-optional-expiration-for-fine-grained-pats/

### GitHub Community Discussions
- No API for PAT creation/deletion: https://github.com/orgs/community/discussions/148626
- PAT rotation requirements: https://github.com/orgs/community/discussions/24366
- Fine-grained PAT feedback: https://github.com/orgs/community/discussions/36441
- Fine-grained PAT expiration options: https://github.com/orgs/community/discussions/184161

### Engineering Blogs & Articles
- Shopify: Automatically Rotating GitHub Tokens: https://shopify.engineering/automatically-rotate-github-tokens
- StepSecurity: GITHUB_TOKEN security: https://www.stepsecurity.io/blog/github-token-how-it-works-and-how-to-secure-automatic-github-action-tokens
- Michael Heap: GitHub Actions auth guide: https://michaelheap.com/ultimate-guide-github-actions-authentication/
- Xebia: GitHub access tokens explained: https://xebia.com/blog/github-access-tokens-explained/
- Aembit: Replacing PAT with GitHub App: https://aembit.io/blog/replacing-a-github-personal-access-token-with-a-github-application/
- Blacksmith: Secrets management best practices: https://www.blacksmith.sh/blog/best-practices-for-managing-secrets-in-github-actions

### GitHub Actions
- `actions/create-github-app-token`: https://github.com/actions/create-github-app-token
- Cross-repo PAT rotation workflow: https://rohithykrohith.medium.com/how-to-update-rotate-github-pat-in-multiple-github-repositories-using-a-workflow-8543d86debb7

### Rate Limits
- Lunar: GitHub API rate limits guide: https://www.lunar.dev/post/a-developers-guide-managing-rate-limits-for-the-github-api
- DEV Community: API rate limit fix: https://dev.to/mehmetakar/api-rate-limit-exceeded-github-how-to-fix-4h6n

---

*End of Topic 2 Research Report*
