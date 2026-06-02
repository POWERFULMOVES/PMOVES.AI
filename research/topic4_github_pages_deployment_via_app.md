# Topic 4: GitHub Pages Deployment via GitHub App — Full Technical Reference

**Research Date:** 2026-04-23
**Status:** COMPLETE

---

## Table of Contents

1. [GitHub App Permissions Required for Pages](#1-github-app-permissions-required-for-pages)
2. [Configuring a GitHub App for Pages](#2-configuring-a-github-app-for-pages)
3. [GitHub Pages REST API Endpoints](#3-github-pages-rest-api-endpoints)
4. [Configuring Pages Source via App API](#4-configuring-pages-source-via-app-api)
5. [Creating a Pages Deployment via App API](#5-creating-a-pages-deployment-via-app-api)
6. [Deploying via GitHub Actions with App Token](#6-deploying-via-github-actions-with-app-token)
7. [GITHUB_TOKEN vs GitHub App Token for Pages](#7-github_token-vs-github-app-token-for-pages)
8. [Complete Workflow YAML Examples](#8-complete-workflow-yaml-examples)
9. [Caveats and Known Limitations](#9-caveats-and-known-limitations)
10. [Source URLs](#10-source-urls)

---

## 1. GitHub App Permissions Required for Pages

### Permission Matrix by Operation

| Operation | Pages Permission | Administration Permission | Contents Permission | Notes |
|-----------|-----------------|--------------------------|-------------------|-------|
| Read Pages site info | `pages: read` | — | — | Public repos: no auth needed |
| Read Pages builds | `pages: read` | — | — | Public repos: no auth needed |
| Read deployment status | `pages: read` | — | — | Public repos: no auth needed |
| Request a Pages build | `pages: write` | — | — | — |
| Create a Pages deployment | `pages: write` | — | — | Requires valid `oidc_token` |
| Cancel a Pages deployment | `pages: write` | — | — | — |
| **Create a Pages site** (enable) | `pages: write` | `administration: write` | — | First-time enablement |
| **Update Pages config** (source, build_type) | `pages: write` | `administration: write` | — | Changing branch/path/build type |
| **Delete a Pages site** | `pages: write` | `administration: write` | — | Disabling Pages entirely |
| DNS health check | `pages: write` | `administration: write` | — | — |
| Commit files to gh-pages branch (legacy) | — | — | `contents: write` | Only for legacy deployment method |

### Minimum Permissions for Full Pages Management

To perform ALL Pages operations (enable, configure, deploy, monitor) via a GitHub App:

```
Repository Permissions:
  Pages:          Read and Write
  Administration: Read and Write
```

If you also need to commit built files to a branch (legacy mode):

```
Repository Permissions:
  Pages:          Read and Write
  Administration: Read and Write
  Contents:       Read and Write
```

### Permission Names in GitHub App Settings UI

In the GitHub App settings page (Settings > Developer settings > GitHub Apps > [Your App] > Permissions > Repository permissions), these appear as:

- **Pages** → dropdown: "No access" / "Read-only" / "Read and write"
- **Administration** → dropdown: "No access" / "Read-only" / "Read and write"
- **Contents** → dropdown: "No access" / "Read-only" / "Read and write"

### Important: `id-token: write` is NOT a GitHub App Permission

The `id-token: write` permission that appears in workflow YAML is a **job-level permission** for GitHub Actions, not a GitHub App repository permission. It controls whether the workflow job can request an OIDC JWT token from GitHub's OIDC provider. It is set in the `permissions:` block of a workflow job, not in the GitHub App settings.

---

## 2. Configuring a GitHub App for Pages

### Step-by-Step App Configuration

1. **Create the GitHub App** at https://github.com/settings/apps/new
   - Set a name, homepage URL, webhook URL (optional for API-only use)
   - Uncheck "Active" for webhooks if using pure API approach

2. **Set Repository Permissions** (Permissions tab > Repository permissions):

   | Permission | Access Level |
   |-----------|-------------|
   | Pages | Read and write |
   | Administration | Read and write |
   | Contents | Read and write (if using legacy deployment or committing files) |
   | Metadata | Read-only (always required) |

3. **Set Subscription** (Install App tab):
   - Install on the target repository or organization
   - Select "All repositories" or specific repositories as needed

4. **Generate a Private Key** (App settings > General > Private keys > Generate a private key):
   - Downloads a `.pem` file
   - Store this securely (e.g., as a GitHub Actions secret)

5. **Note the App ID and Client ID** (App settings > General):
   - `App ID`: Numeric ID (e.g., `123456`)
   - `Client ID`: OAuth Client ID string (e.g., `Iv1.ab12cd34ef56gh78`)

### What the `permission-<name>` Override Does in `create-github-app-token`

When using `actions/create-github-app-token`, you can narrow the token's permissions below what the App installation has:

```yaml
- uses: actions/create-github-app-token@v3
  with:
    client-id: ${{ vars.APP_CLIENT_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
    permission-pages: write          # Explicitly grant pages:write
    permission-administration: write  # Explicitly grant administration:write
```

**Critical rule:** You can only narrow permissions, not expand them. The requested permissions must already be granted to the App installation on that repository. Setting a permission the installation doesn't have causes an error.

---

## 3. GitHub Pages REST API Endpoints

### Complete Endpoint List

| Method | Endpoint | Permission Required | Description |
|--------|----------|-------------------|-------------|
| GET | `/repos/{owner}/{repo}/pages` | pages: read | Get Pages site configuration |
| POST | `/repos/{owner}/{repo}/pages` | pages: write + administration: write | Create/enable a Pages site |
| PUT | `/repos/{owner}/{repo}/pages` | pages: write + administration: write | Update Pages configuration |
| DELETE | `/repos/{owner}/{repo}/pages` | pages: write + administration: write | Disable/delete Pages site |
| GET | `/repos/{owner}/{repo}/pages/builds` | pages: read | List all Pages builds |
| GET | `/repos/{owner}/{repo}/pages/builds/latest` | pages: read | Get latest Pages build |
| GET | `/repos/{owner}/{repo}/pages/builds/{build_id}` | pages: read | Get specific Pages build |
| POST | `/repos/{owner}/{repo}/pages/builds` | pages: write | Request a new Pages build (legacy mode) |
| **POST** | **`/repos/{owner}/{repo}/pages/deployments`** | **pages: write** | **Create a Pages deployment** |
| GET | `/repos/{owner}/{repo}/pages/deployments/{deployment_id}` | pages: read | Get deployment status |
| POST | `/repos/{owner}/{repo}/pages/deployments/{deployment_id}/cancel` | pages: write | Cancel a deployment |
| GET | `/repos/{owner}/{repo}/pages/health` | pages: write + administration: write | DNS health check |

### Supported Token Types

All Pages endpoints support:
- GitHub App user access tokens
- **GitHub App installation access tokens** (primary use case)
- Fine-grained personal access tokens
- OAuth app tokens / Personal access tokens (classic) with `repo` scope

---

## 4. Configuring Pages Source via App API

### Enable Pages and Set to Workflow Mode

This is something **GITHUB_TOKEN cannot do** (returns 403), but a **GitHub App token can**.

```bash
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages \
  -d '{
    "build_type": "workflow",
    "source": {
      "branch": "main",
      "path": "/"
    }
  }'
```

### Update Existing Pages Configuration

```bash
curl -L \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages \
  -d '{
    "build_type": "workflow",
    "source": {
      "branch": "main",
      "path": "/docs"
    }
  }'
```

### Request Parameters for PUT /repos/{owner}/{repo}/pages

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `build_type` | string | No | `"legacy"` or `"workflow"` |
| `source.branch` | string | Yes | Repository branch for publishing source files |
| `source.path` | string | No | Directory with source files. Allowed: `"/"` or `"/docs"`. Default: `"/"` |

### Response (200 OK)

```json
{
  "url": "https://api.github.com/repos/OWNER/REPO/pages",
  "status": "built",
  "cname": "custom.example.com",
  "custom_404": false,
  "html_url": "https://OWNER.github.io/REPO",
  "source": {
    "branch": "main",
    "path": "/"
  },
  "public": true,
  "https_certificate": {
    "state": "approved",
    "description": "Certificate is approved",
    "domains": ["custom.example.com"],
    "expires_at": "2027-05-22"
  },
  "https_enforced": true
}
```

### Switch from Legacy to Workflow Build Type

```bash
curl -L \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages \
  -d '{
    "build_type": "workflow"
  }'
```

**Yes, a GitHub App CAN set the Pages `build_type` to `workflow` or `legacy` via the API.** This is a key capability that GITHUB_TOKEN lacks.

### Read Current Pages Configuration

```bash
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages
```

### Request a Legacy Build

```bash
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages/builds
```

Response (201):
```json
{
  "url": "https://api.github.com/repos/OWNER/REPO/pages/builds/latest",
  "status": "queued"
}
```

**Note:** Build requests are limited to one concurrent build per repository.

---

## 5. Creating a Pages Deployment via App API

### The Critical OIDC Token Requirement

**This is the most important technical detail for App-based Pages deployment:**

The `POST /repos/{owner}/{repo}/pages/deployments` endpoint requires an `oidc_token` field in the request body. This OIDC token:

1. Is issued by GitHub's OIDC provider
2. Can ONLY be obtained from within a GitHub Actions workflow job (via `id-token: write` permission)
3. Contains claims about the branch/ref executing the workflow
4. Is validated by GitHub's Pages backend to verify deployment origin
5. **Cannot be generated by a GitHub App token outside of Actions**

**Implication:** A GitHub App token calling the deployment API from outside GitHub Actions (e.g., from a local script, CI server, or webhook handler) **cannot** provide a valid `oidc_token`. The deployment will fail.

### Full Request Format

```bash
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages/deployments \
  -d '{
    "artifact_id": 12345,
    "artifact_url": "https://downloadcontent/",
    "environment": "github-pages",
    "pages_build_version": "4fd754f7e594640989b406850d0bc8f06a121251",
    "oidc_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..."
  }'
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_id` | number | Conditional* | ID of an artifact containing .zip or .tar of static assets |
| `artifact_url` | string | Conditional* | URL of an artifact containing .zip or .tar of static assets |
| `environment` | string | No | Target environment. Default: `"github-pages"` |
| `pages_build_version` | string | Yes | Unique string for the build version. Typically set to the commit SHA |
| `oidc_token` | string | Yes | OIDC JWT token issued by GitHub Actions |

*Either `artifact_id` or `artifact_url` must be provided.

### Response (200 OK)

```json
{
  "id": "4fd754f7e594640989b406850d0bc8f06a121251",
  "status_url": "https://api.github.com/repos/OWNER/REPO/pages/deployments/4fd754f7e594640989b406850d0bc8f06a121251/status",
  "page_url": "OWNER.github.io/REPO"
}
```

### Check Deployment Status

```bash
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages/deployments/4fd754f7e594640989b406850d0bc8f06a121251/status
```

### Cancel a Deployment

```bash
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/REPO/pages/deployments/4fd754f7e594640989b406850d0bc8f06a121251/cancel
```

### External CI Deployment (Without OIDC)

For external CI systems (Travis CI, Jenkins, etc.) that cannot obtain a GitHub Actions OIDC token, the standard approach is:

1. Use `build_type: "legacy"` in Pages configuration
2. Commit the built static files to the `gh-pages` branch (or configured source branch)
3. GitHub automatically builds from that branch
4. Use `POST /repos/{owner}/{repo}/pages/builds` to trigger a build

This bypasses the deployment API entirely but requires `contents: write` permission.

---

## 6. Deploying via GitHub Actions with App Token

### The Two-Workflow Pattern (Recommended)

This is the most common pattern when using a GitHub App token for Pages:

**Workflow 1: Build** — Uses App token for checkout/push to protected branches
**Workflow 2: Deploy** — Uses GITHUB_TOKEN + OIDC for Pages deployment

The two workflows are connected via `workflow_run` trigger. This is necessary because:
- The App token is needed to push to protected branches (GITHUB_TOKEN can't do this)
- `actions/deploy-pages` requires OIDC (which requires `id-token: write`, an Actions-only permission)
- Using the App token directly with `actions/deploy-pages` does NOT bypass the OIDC requirement

### Why App Token + deploy-pages Directly Doesn't Work as Expected

Even if you pass an App token to `actions/deploy-pages` via its `token` input:

```yaml
- uses: actions/deploy-pages@v4
  with:
    token: ${{ steps.app-token.outputs.token }}  # App token
```

The action still needs an OIDC token to include in the API request's `oidc_token` field. The OIDC token is obtained via the `id-token: write` job permission, which is independent of whichever token is used for API authentication. The App token authenticates the API call, but the OIDC token proves the deployment originates from a legitimate workflow run.

**Result:** Passing an App token to `deploy-pages` works, but you still need `id-token: write` in the job permissions. The benefit of using the App token here is that the deployment appears as the App's bot user rather than `github-actions[bot]`.

### Single-Workflow Pattern with App Token

If you don't need to push to protected branches, you CAN use a single workflow with the App token passed to `deploy-pages`:

```yaml
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          permission-pages: write
      - uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
      # ... build steps ...
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./build
      - uses: actions/deploy-pages@v4
        id: deployment
        with:
          token: ${{ steps.app-token.outputs.token }}
```

This works, but the main benefit is cosmetic (App bot user vs github-actions bot) — the OIDC flow remains the same.

---

## 7. GITHUB_TOKEN vs GitHub App Token for Pages

### Comparison Table

| Capability | GITHUB_TOKEN | GitHub App Token |
|-----------|-------------|------------------|
| Read Pages site config | Yes (pages: read) | Yes (pages: read) |
| Read Pages builds | Yes (pages: read) | Yes (pages: read) |
| Read deployment status | Yes (pages: read) | Yes (pages: read) |
| **Create/enable Pages site** (POST /pages) | **NO (403)** | **Yes** |
| **Update Pages config** (PUT /pages) | **NO (403)** | **Yes** |
| **Delete Pages site** | **NO (403)** | **Yes** |
| **Set build_type: workflow** | **NO (403)** | **Yes** |
| Request a legacy build (POST /pages/builds) | Yes (pages: write) | Yes (pages: write) |
| Create deployment (POST /pages/deployments) | Yes (pages: write + OIDC) | Yes (pages: write + OIDC) |
| Cancel deployment | Yes (pages: write) | Yes (pages: write) |
| DNS health check | No (403) | Yes (pages:write + admin:write) |
| Generate OIDC token | Yes (via id-token: write) | **No** |
| Push to protected branches | **No** | **Yes** |
| Push to unprotected branches | Yes (contents: write) | Yes (contents: write) |
| Token lifetime | Job-scoped (~6hr hosted, ~24hr self-hosted) | 1 hour (API-generated) or job-scoped (via action) |
| Token scope | Current repository only | Configurable (specific repos, all repos in org) |
| Cross-repo access | No | Yes (if configured) |
| Identity | `github-actions[bot]` | `YourApp[bot]` |

### Why GITHUB_TOKEN Fails for Pages Configuration

GITHUB_TOKEN is an installation access token for the auto-installed `github-actions` App per repository. This App intentionally does NOT have `administration: write` permission. Even if you set `permissions: write-all` in the workflow YAML, the underlying App installation lacks the required repository permission, resulting in:

```
RequestError [HttpError]: Resource not accessible by integration
HTTP 403
```

This was confirmed in github.com/actions/configure-pages/issues/40 and remains the case as of 2026.

### Why GitHub App Token Works for Pages Configuration

A custom GitHub App can be granted `administration: write` and `pages: write` permissions in its settings. When installed on a repository, the installation access token inherits these permissions, allowing full Pages configuration via the API.

---

## 8. Complete Workflow YAML Examples

### Example 1: Two-Workflow Pattern (App Token for Build, GITHUB_TOKEN for Deploy)

**File: `.github/workflows/build.yml`**

```yaml
name: Build Site

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      # Step 1: Create GitHub App token for protected branch access
      - name: Create GitHub App token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          permission-contents: write

      # Step 2: Checkout with App token (can push to protected branches)
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}

      # Step 3: Build the site
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build site
        run: npm run build

      # Step 4: Upload artifact for the deploy workflow
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./out
```

**File: `.github/workflows/deploy.yml`**

```yaml
name: Deploy to Pages

on:
  workflow_run:
    workflows: ['Build Site']
    types: [completed]

jobs:
  deploy:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    permissions:
      pages: write
      id-token: write
      contents: read
    steps:
      - name: Download Pages artifact
        uses: actions/download-artifact@v4
        with:
          name: github-pages
          path: ./artifact
          run-id: ${{ github.event.workflow_run.id }}

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### Example 2: Single Workflow with App Token for Everything

```yaml
name: Build and Deploy to Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      # Create App token
      - name: Create GitHub App token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          permission-pages: write
          permission-contents: read

      # Checkout with App token
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}

      # Build
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install and build
        run: |
          npm ci
          npm run build

      # Upload artifact
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

      # Deploy using App token (OIDC still comes from id-token: write)
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
```

### Example 3: App Token for Pages Configuration + Build + Deploy

This example shows the App token being used to programmatically ensure Pages is configured correctly BEFORE deploying.

```yaml
name: Configure, Build, and Deploy to Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  setup-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      # Create App token with full Pages permissions
      - name: Create GitHub App token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          permission-pages: write
          permission-administration: write
          permission-contents: read

      # Ensure Pages is configured for workflow mode
      - name: Configure Pages source
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          # Check if Pages is already configured
          STATUS=$(gh api /repos/${{ github.repository }}/pages --jq '.status' 2>/dev/null || echo "not_configured")

          if [ "$STATUS" = "not_configured" ]; then
            echo "Pages not configured. Enabling..."
            gh api \
              --method POST \
              /repos/${{ github.repository }}/pages \
              -f build_type=workflow \
              -f source[branch]=main \
              -f source[path]=/
          else
            echo "Pages already configured (status: $STATUS). Updating to workflow mode..."
            gh api \
              --method PUT \
              /repos/${{ github.repository }}/pages \
              -f build_type=workflow
          fi

      # Checkout and build
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Build
        run: |
          npm ci
          npm run build

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
```

### Example 4: Pure API Deployment Script (Requires OIDC from Actions Context)

This shows what `actions/deploy-pages` does internally — useful if building a custom deployment action.

```yaml
name: Custom Pages Deployment

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - name: Create GitHub App token
        id: app-token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          permission-pages: write

      - name: Checkout and build
        uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
      - run: npm ci && npm run build

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: github-pages
          path: ./dist
          retention-days: 1

      - name: Get OIDC token
        id: oidc
        uses: actions/github-script@v7
        with:
          script: |
            const oidc = await core.getIDToken()
            core.setOutput('token', oidc)

      - name: Get artifact ID
        id: artifact
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          ARTIFACT_ID=$(gh api \
            /repos/${{ github.repository }}/actions/artifacts \
            --jq '.artifacts[] | select(.name == "github-pages") | .id' | head -1)
          echo "id=$ARTIFACT_ID" >> "$GITHUB_OUTPUT"

      - name: Create Pages deployment
        id: deploy
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          RESPONSE=$(gh api \
            --method POST \
            /repos/${{ github.repository }}/pages/deployments \
            -f artifact_id=${{ steps.artifact.outputs.id }} \
            -f pages_build_version=${{ github.sha }} \
            -f environment=github-pages \
            -f oidc_token="${{ steps.oidc.outputs.token }}")
          PAGE_URL=$(echo "$RESPONSE" | jq -r '.page_url')
          echo "page_url=https://$PAGE_URL" >> "$GITHUB_OUTPUT"
          echo "Deployed to https://$PAGE_URL"
```

### Example 5: External CI with Legacy Mode via App Token

For deploying from outside GitHub Actions (e.g., local script, Jenkins, Travis CI):

```bash
#!/bin/bash
set -euo pipefail

# Generate App installation token
APP_ID="123456"
PRIVATE_KEY_PATH="./app-private-key.pem"
REPO="OWNER/REPO"

# Get installation ID
INSTALLATION_ID=$(curl -s -H "Authorization: Bearer $(jwt_sign "$APP_ID" "$PRIVATE_KEY_PATH")" \
  https://api.github.com/app/installations | \
  jq -r '.[] | select(.account.login == "OWNER") | .id')

# Get installation access token
APP_TOKEN=$(curl -s -X POST \
  -H "Authorization: Bearer $(jwt_sign "$APP_ID" "$PRIVATE_KEY_PATH")" \
  https://api.github.com/app/installations/$INSTALLATION_ID/access_tokens | \
  jq -r '.token')

# Configure Pages for legacy mode (if not already)
curl -s -X PUT \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$REPO/pages \
  -d '{"build_type": "legacy", "source": {"branch": "gh-pages", "path": "/"}}' \
  > /dev/null

# Clone, build, and push to gh-pages branch
git clone --depth 1 "https://x-access-token:$APP_TOKEN@github.com/$REPO.git" /tmp/repo
cd /tmp/repo
npm ci && npm run build

# Deploy to gh-pages branch
git checkout --orphan gh-pages
rm -rf *
cp -r ../dist/* .
git add -A
git commit -m "Deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push origin gh-pages --force

# Trigger Pages build
curl -s -X POST \
  -H "Authorization: Bearer $APP_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$REPO/pages/builds

echo "Deployment triggered"
```

---

## 9. Caveats and Known Limitations

### 9.1 App Must Be Installed on the Repository

A GitHub App can only generate installation access tokens for repositories where it is installed. If the App is not installed, API calls return 404 or 403.

**Check installation status:**
```bash
curl -H "Authorization: Bearer $APP_TOKEN" \
  https://api.github.com/installation/repositories | jq '.repositories[].full_name'
```

### 9.2 Pages Must Be Enabled Before Deployment

You cannot create a deployment for a repository that doesn't have Pages enabled. You must first call `POST /repos/{owner}/{repo}/pages` (or enable it manually in the repo settings). A GitHub App token CAN do this; GITHUB_TOKEN cannot.

### 9.3 The github-pages Environment Must Exist

When Pages is configured with `build_type: "workflow"`, GitHub automatically creates a `github-pages` deployment environment. Your workflow must reference this environment:

```yaml
environment:
  name: github-pages
  url: ${{ steps.deployment.outputs.page_url }}
```

If the environment doesn't exist yet (first-time setup), you may need to enable Pages first via the API, then run the deployment workflow.

### 9.4 OIDC Token is Actions-Only

The `oidc_token` field in the deployment API request MUST be a JWT issued by GitHub's OIDC provider, which is only available within a GitHub Actions workflow job. There is no way to generate this token from:
- A local script
- An external CI system
- A GitHub App webhook handler
- The GitHub App API directly

**Workaround for external CI:** Use `build_type: "legacy"` and commit to the source branch instead of using the deployment API.

### 9.5 Token Lifetime and Revocation

- **App tokens via `actions/create-github-app-token`:** Automatically revoked at the end of the job (unless `skip-token-revoke: true`). Cannot be passed between jobs.
- **App tokens via API (JWT -> installation token):** 1-hour TTL. Must be refreshed for long-running operations.
- **GITHUB_TOKEN:** Scoped to job lifetime (~6 hours hosted, ~24 hours self-hosted).

### 9.6 Two-Workflow Pattern Needed to Avoid Double Deployment

When using the App token for building AND GITHUB_TOKEN for deploying, you must split into two workflows triggered by `workflow_run`. If both build and deploy are in the same workflow, and the build step commits to the source branch, it can trigger a second Pages deployment.

### 9.7 First Deployment Requires Manual Pages Branch Selection

When using `actions/upload-pages-artifact` + `actions/deploy-pages` for the very first time, you may need to manually select the GitHub Pages branch in the repository settings (Settings > Pages > Source) before the workflow can deploy. After the first successful deployment, subsequent deployments work automatically.

This caveat applies to the `peaceiris/actions-gh-pages` action as well, which notes: "The GITHUB_TOKEN has limitations for the first deployment so we have to select the GitHub Pages branch on the repository settings tab. After that, do the second deployment."

### 9.8 Rate Limits

- Standard authenticated rate limit: 5,000 requests/hour
- Enterprise Cloud org-owned GitHub Apps: 10,000 requests/hour
- Secondary limits: 100 concurrent requests max, 500/min burst limit
- Pages builds: 1 concurrent build per repository, 1 concurrent build per requester

### 9.9 App Token Permission Narrowing Must Not Exceed Installation Permissions

When using `permission-<name>` inputs in `create-github-app-token`, the requested permission level must be equal to or less than what the App installation has. Requesting `permission-pages: write` when the installation only has `pages: read` will cause an error.

### 9.10 `contents:write` is NOT Required for Workflow-Based Deployment

A common misconception is that `contents: write` is needed for Pages deployment. For `build_type: "workflow"` deployment via `actions/deploy-pages` or the deployment API, only `pages: write` is needed. `contents: write` is only required if:
- Using legacy mode (committing to gh-pages branch)
- The build workflow needs to commit files back to the repository

---

## 10. Source URLs

- GitHub REST API endpoints for GitHub Pages: https://docs.github.com/en/rest/pages/pages
- Permissions required for GitHub Apps: https://docs.github.com/en/rest/overview/permissions-required-for-github-apps
- actions/deploy-pages: https://github.com/actions/deploy-pages
- actions/create-github-app-token: https://github.com/actions/create-github-app-token
- actions/configure-pages issue #40 (GITHUB_TOKEN 403 for Pages config): https://github.com/actions/configure-pages/issues/40
- Configuring a publishing source for GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- REST API endpoints for deployments: https://docs.github.com/en/rest/deployments/deployments
- GitHub App Token Authorization Guide: https://medium.com/@tiwari09abhi/github-app-token-authorization-a-complete-guide-169461f2953f
- actions/deploy-pages DeepWiki: https://deepwiki.com/actions/deploy-pages
- peaceiris/actions-gh-pages: https://github.com/peaceiris/actions-gh-pages
- Qiita article on App token + protected branch + Pages: https://qiita.com/kiwsdiv/items/7cd77b0a85eb7a367ff3
- GitHub Actions for GitHub Pages (cicube.io): https://cicube.io/workflow-hub/github-actions-deploy-pages/
- Deploy to GitHub Pages marketplace action: https://github.com/marketplace/actions/deploy-to-github-pages
