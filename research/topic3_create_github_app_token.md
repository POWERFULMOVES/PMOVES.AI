# TOPIC 3: `actions/create-github-app-token` — Complete Technical Reference

**Research Date:** 2026-04-23  
**Action Version:** v3  
**Repository:** https://github.com/actions/create-github-app-token  
**Marketplace:** https://github.com/marketplace/actions/create-github-app-token

---

## Table of Contents

1. [Overview](#overview)
2. [Input Parameters](#input-parameters)
3. [Output Variables](#output-variables)
4. [Permissions System](#permissions-system)
5. [Repository Scoping](#repository-scoping)
6. [Owner Parameter](#owner-parameter)
7. [Complete Workflow YAML Examples](#complete-workflow-yaml-examples)
8. [Underlying API Call](#underlying-api-call)
9. [Token Comparison: GITHUB_TOKEN vs App Token vs PAT](#token-comparison)
10. [Private Key Management](#private-key-management)
11. [Limitations and Gotchas](#limitations-and-gotchas)
12. [Source URLs](#source-urls)

---

## Overview

`actions/create-github-app-token` is an official GitHub Action that generates a GitHub App installation access token for use within a workflow. It handles the full authentication flow internally: JWT generation from the private key, installation lookup, and token creation via the REST API. The token is automatically revoked at the end of the job (unless opted out).

The action is maintained by the `actions` organization (GitHub staff) and is the recommended way to use GitHub App authentication in GitHub Actions workflows.

**Prerequisites:**
1. Register a GitHub App (https://github.com/settings/apps)
2. Store the App's Client ID as a repository/organization variable (e.g., `APP_CLIENT_ID`)
3. Store the App's private key as a repository/organization secret (e.g., `APP_PRIVATE_KEY`)
4. Install the App on the target account/organization with appropriate repository access and permissions

---

## Input Parameters

### `client-id` (Recommended) / `app-id` (Legacy)

| Field | Value |
|---|---|
| **Name** | `client-id` (recommended) or `app-id` (legacy) |
| **Type** | string |
| **Required** | Yes (one of client-id or app-id) |
| **Default** | — |
| **Description** | The GitHub App Client ID (preferred) or the numeric App ID. The Client ID is the OAuth Client ID found on the GitHub App settings page. The legacy `app-id` input is the numeric App ID and is still accepted for backward compatibility. |

**Where to find it:** GitHub App Settings page → "About" section → Client ID (e.g., `Iv1.1234567890abcdef`) or App ID (e.g., `123456`)

### `private-key`

| Field | Value |
|---|---|
| **Name** | `private-key` |
| **Type** | string |
| **Required** | Yes |
| **Default** | — |
| **Description** | The GitHub App private key in PEM format. Escaped newlines (`\\n`) stored in GitHub Secrets are automatically replaced with actual newlines by the action. |

### `owner`

| Field | Value |
|---|---|
| **Name** | `owner` |
| **Type** | string |
| **Required** | No |
| **Default** | Current repository owner (`github.repository_owner`) |
| **Description** | The owner of the GitHub App installation to target. If empty, defaults to the current repository owner. Used for cross-organization scenarios or GHES environments. |

### `repositories`

| Field | Value |
|---|---|
| **Name** | `repositories` |
| **Type** | string |
| **Required** | No |
| **Default** | — |
| **Description** | Comma or newline-separated list of repository names to grant the token access to. See [Repository Scoping](#repository-scoping) for complete behavior. |

### `permission-<permission name>` (Dynamic Inputs)

| Field | Value |
|---|---|
| **Name** | `permission-<name>` (e.g., `permission-issues`, `permission-contents`) |
| **Type** | string |
| **Required** | No |
| **Default** | Inherits all installation permissions if none specified |
| **Description** | Override the permission level for a specific permission scope. See [Permissions System](#permissions-system) for the complete list of valid names and levels. |

### `skip-token-revoke`

| Field | Value |
|---|---|
| **Name** | `skip-token-revoke` |
| **Type** | boolean |
| **Required** | No |
| **Default** | `false` |
| **Description** | If `true`, the token will NOT be revoked when the current job completes. By default, the action runs a `post` step that revokes the token. Setting this to `true` is necessary if the token needs to be passed to another job (via `jobs.<job_id>.outputs`). |

### `github-api-url`

| Field | Value |
|---|---|
| **Name** | `github-api-url` |
| **Type** | string |
| **Required** | No |
| **Default** | The GitHub REST API URL of the environment where the workflow runs |
| **Description** | The URL of the GitHub REST API. Required for GitHub Enterprise Server (GHES) environments where the API URL differs from `https://api.github.com`. |

---

## Output Variables

| Output | Type | Description |
|---|---|---|
| `token` | string | The GitHub App installation access token (prefixed with `ghs_`). This is the primary output used for authentication. |
| `installation-id` | string | The numeric ID of the GitHub App installation that was used to create the token. |
| `app-slug` | string | The URL-friendly name of the GitHub App (e.g., `my-awesome-app`). Used to construct the bot user identity: `{app-slug}[bot]`. |

**Usage pattern:**
~~~yaml
- uses: actions/create-github-app-token@v3
  id: app-token
  with:
    client-id: ${{ vars.APP_CLIENT_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
# Later in the workflow:
# ${{ steps.app-token.outputs.token }}
# ${{ steps.app-token.outputs.installation-id }}
# ${{ steps.app-token.outputs.app-slug }}
~~~

**Note:** The action does NOT output `expires_at`. The underlying API returns it, but the action does not expose it as an output. The token always expires after 1 hour from creation.

---

## Permissions System

### Format

Permissions are specified as individual inputs using the pattern `permission-<name>`:

~~~yaml
permission-issues: write
permission-contents: read
permission-pull-requests: write
~~~

This format was chosen to leverage GitHub Actions' built-in input validation and type intelligence.

### Default Behavior

If NO `permission-*` inputs are specified, the token inherits ALL permissions granted to the installation. GitHub recommends explicitly listing only the permissions required for a specific use case (principle of least privilege).

### Validation Rules

- A requested permission level CANNOT exceed what the installation was granted.
- If the installation has `issues: read` and you request `permission-issues: write`, the action will ERROR.
- Installation permissions may differ from the App's declared permissions. When an App adds new permissions after installation, an org admin must approve them before they take effect on the installation.

### Valid Levels

| Level | Description |
|---|---|
| `read` | Read-only access |
| `write` | Read and write access |
| `admin` | Full administrative access (only supported by some permissions) |
| `none` | Explicitly deny access (reduces from inherited default) |

**Note:** Not every permission supports all levels. Most support `read` and `write`; only a few support `admin`.

### Complete Permission Names List

The permission names below are the exact strings used after the `permission-` prefix. They are identical to the permission names used in the `permissions:` key at the workflow/job level and in fine-grained PAT configuration.

#### Repository Permissions (most commonly used with this action)

| Permission Name | Valid Levels | Description |
|---|---|---|
| `actions` | read, write | Workflow runs and artifacts |
| `actions_variables` | read, write | Repository-level Actions variables |
| `administration` | read, write | Repository settings |
| `artifact_metadata` | read, write | Artifact metadata |
| `attestations` | read, write | Artifact attestations |
| `codespaces` | read, write | Codespaces |
| `codespaces_lifecycle_admin` | read, write | Codespaces lifecycle management |
| `codespaces_metadata` | read | Codespaces metadata |
| `codespaces_secrets` | write | Codespaces secrets |
| `contents` | read, write | Repository contents (files, commits, branches) |
| `dependabot_secrets` | read, write | Dependabot secrets |
| `deployments` | read, write | Deployments |
| `discussions` | read, write | Discussions |
| `environments` | read, write | Environments |
| `issues` | read, write | Issues |
| `merge_queues` | read, write | Merge queues |
| `metadata` | read | Repository metadata (search, always read-only) |
| `pages` | read, write | GitHub Pages |
| `pull_requests` | read, write | Pull requests |
| `repository_advisories` | read, write | Security advisories |
| `repository_custom_properties` | read, write | Repository custom properties |
| `repository_hooks` | read, write | Webhooks |
| `secret_scanning_alerts` | read, write | Secret scanning alerts |
| `secrets` | read, write | Repository secrets |
| `security_events` | read, write | Code scanning and security events |
| `statuses` | read, write | Commit statuses |
| `vulnerability_alerts` | read, write | Dependabot vulnerability alerts |
| `workflows` | write | Workflow files (write-only permission) |

#### Organization Permissions

| Permission Name | Valid Levels |
|---|---|
| `issue_types` | read, write |
| `members` | read, write |
| `organization_actions_variables` | read, write |
| `organization_administration` | read, write |
| `organization_announcement_banners` | read, write |
| `organization_api_insights` | read |
| `organization_campaigns` | read, write |
| `organization_code_scanning_dismissal_requests` | read, write |
| `organization_codespaces` | read, write |
| `organization_codespaces_secrets` | read, write |
| `organization_codespaces_settings` | read, write |
| `organization_copilot_seat_management` | read, write |
| `organization_custom_org_roles` | read, write |
| `organization_custom_properties` | read, write, admin |
| `organization_custom_roles` | read, write |
| `organization_dependabot_secrets` | read, write |
| `organization_events` | read |
| `organization_hooks` | read, write |
| `organization_knowledge_bases` | read, write |
| `organization_models` | read |
| `organization_network_configurations` | read, write |
| `organization_plan` | read |
| `organization_private_registries` | read, write |
| `organization_projects` | read, write, admin |
| `organization_secrets` | read, write |
| `organization_self_hosted_runners` | read, write |
| `organization_user_blocking` | read, write |
| `team_discussions` | read, write |

#### Account Permissions (rarely used with this action)

| Permission Name | Valid Levels |
|---|---|
| `blocking` | read, write |
| `codespaces_user_secrets` | read, write |
| `copilot_editor_context` | read |
| `copilot_messages` | read |
| `copilot_requests` | write |
| `emails` | read, write |
| `followers` | read, write |
| `gists` | write |
| `git_signing_ssh_public_keys` | read, write |
| `gpg_keys` | read, write |
| `interaction_limits` | read, write |
| `keys` | read, write |
| `knowledge_bases` | read, write |
| `plan` | read |
| `private_repository_invitations` | read |
| `profile` | write |
| `starring` | read, write |
| `user_events` | read |
| `user_models` | read |
| `watching` | read, write |

---

## Repository Scoping

The `repositories` input controls which repositories the generated token can access. Its behavior depends on the combination with the `owner` input:

### Scoping Matrix

| `owner` | `repositories` | Result |
|---|---|---|
| Empty (default) | Empty | Token scoped to the **current repository only** |
| Set (e.g., `my-org`) | Empty | Token scoped to **ALL repositories** in that owner's installation |
| Empty or set | Set (list of repos) | Token scoped to **only the specified repositories** within the resolved installation |

### Format

~~~yaml
# Comma-separated
repositories: repo1,repo2,repo3

# Newline-separated (YAML block scalar)
repositories: |
  repo1
  repo2
  repo3

# Dynamic (from matrix)
repositories: ${{ join(matrix.repos) }}
~~~

### Constraints

- You can only specify repositories that the App installation already has access to.
- Requesting a repository the installation cannot access will cause an error.
- The underlying API supports up to **500 repositories** per token.
- Repository names are just the name portion (not `owner/repo`), since the owner is resolved separately.

---

## Owner Parameter

### Default Behavior

When `owner` is omitted, the action uses `github.repository_owner` — the owner of the repository where the workflow is running.

### Use Cases

**1. Current owner (default):**
~~~yaml
# No owner needed for same-org usage
uses: actions/create-github-app-token@v3
with:
  client-id: ${{ vars.APP_CLIENT_ID }}
  private-key: ${{ secrets.APP_PRIVATE_KEY }}
~~~

**2. Cross-organization access:**
~~~yaml
# Target a different organization's installation
uses: actions/create-github-app-token@v3
with:
  client-id: ${{ vars.APP_CLIENT_ID }}
  private-key: ${{ secrets.APP_PRIVATE_KEY }}
  owner: another-org
~~~

**3. GHES with explicit installation org:**
~~~yaml
uses: actions/create-github-app-token@v3
with:
  client-id: ${{ vars.GHES_APP_CLIENT_ID }}
  private-key: ${{ secrets.GHES_APP_PRIVATE_KEY }}
  owner: ${{ vars.GHES_INSTALLATION_ORG }}
  github-api-url: ${{ vars.GITHUB_API_URL }}
~~~

**4. Matrix strategy for multi-org:**
~~~yaml
owner: ${{ matrix.owners-and-repos.owner }}
repositories: ${{ join(matrix.owners-and-repos.repos) }}
~~~

---

## Complete Workflow YAML Examples

### Example 1: Basic Usage with `actions/checkout`

~~~yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - uses: actions/checkout@v6
        with:
          token: ${{ steps.app-token.outputs.token }}
          ref: ${{ github.head_ref }}
          persist-credentials: false
      - uses: creyD/prettier_action@v6
        with:
          github_token: ${{ steps.app-token.outputs.token }}
~~~

### Example 2: Git Committer String for Bot User

~~~yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - name: Get GitHub App User ID
        id: get-user-id
        run: echo "user-id=$(gh api "/users/${{ steps.app-token.outputs.app-slug }}[bot]" --jq .id)" >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
      - id: committer
        run: echo "string=${{ steps.app-token.outputs.app-slug }}[bot] <${{ steps.get-user-id.outputs.user-id }}+${{ steps.app-token.outputs.app-slug }}[bot]@users.noreply.github.com>" >> "$GITHUB_OUTPUT"
      - run: echo "committer string is ${{ steps.committer.outputs.string }}"
~~~

### Example 3: Permission Override (Specific Permissions Only)

~~~yaml
on: [issues]

jobs:
  hello-world:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          permission-issues: write
      - uses: peter-evans/create-or-update-comment@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
          issue-number: ${{ github.event.issue.number }}
          body: "Hello, World!"
~~~

### Example 4: All Repositories in Current Owner's Installation

~~~yaml
on: [workflow_dispatch]

jobs:
  hello-world:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
      # Token now has access to ALL repos the App is installed on for this owner
      - uses: octokit/request-action@v2.x
        with:
          route: GET /installation/repositories
        env:
          GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}
~~~

### Example 5: Multiple Specific Repositories

~~~yaml
on: [issues]

jobs:
  hello-world:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          repositories: |
            repo1
            repo2
      - uses: peter-evans/create-or-update-comment@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
          issue-number: ${{ github.event.issue.number }}
          body: "Hello, World!"
~~~

### Example 6: Cross-Organization Access

~~~yaml
on: [issues]

jobs:
  hello-world:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          owner: another-owner
      - uses: peter-evans/create-or-update-comment@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
          issue-number: ${{ github.event.issue.number }}
          body: "Hello, World!"
~~~

### Example 7: Matrix Strategy for Multiple Owners/Repos

~~~yaml
on: [workflow_dispatch]

jobs:
  set-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set.outputs.matrix }}
    steps:
      - id: set
        run: echo 'matrix=[{"owner":"owner1"},{"owner":"owner2","repos":["repo1"]}]' >>"$GITHUB_OUTPUT"

  use-matrix:
    name: "@${{ matrix.owners-and-repos.owner }} installation"
    needs: [set-matrix]
    runs-on: ubuntu-latest
    strategy:
      matrix:
        owners-and-repos: ${{ fromJson(needs.set-matrix.outputs.matrix) }}

    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          owner: ${{ matrix.owners-and-repos.owner }}
          repositories: ${{ join(matrix.owners-and-repos.repos) }}
      - uses: octokit/request-action@v2.x
        id: get-installation-repositories
        with:
          route: GET /installation/repositories
        env:
          GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}
      - run: echo "$MULTILINE_JSON_STRING"
        env:
          MULTILINE_JSON_STRING: ${{ steps.get-installation-repositories.outputs.data }}
~~~

### Example 8: GHES / Self-Hosted Runner

~~~yaml
on: [push]

jobs:
  create_issue:
    runs-on: self-hosted
    steps:
      - name: Create GitHub App token
        id: create_token
        uses: actions/create-github-app-token@v3
        with:
          client-id: ${{ vars.GHES_APP_CLIENT_ID }}
          private-key: ${{ secrets.GHES_APP_PRIVATE_KEY }}
          owner: ${{ vars.GHES_INSTALLATION_ORG }}
          github-api-url: ${{ vars.GITHUB_API_URL }}

      - name: Create issue
        uses: octokit/request-action@v2.x
        with:
          route: POST /repos/${{ github.repository }}/issues
          title: "New issue from workflow"
          body: "This is a new issue created from a GitHub Action workflow."
        env:
          GITHUB_TOKEN: ${{ steps.create_token.outputs.token }}
~~~

### Example 9: Configure Git CLI for Bot User

~~~yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - name: Get GitHub App User ID
        id: get-user-id
        run: echo "user-id=$(gh api "/users/${{ steps.app-token.outputs.app-slug }}[bot]" --jq .id)" >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
      - run: |
          git config --global user.name '${{ steps.app-token.outputs.app-slug }}[bot]'
          git config --global user.email '${{ steps.get-user-id.outputs.user-id }}+${{ steps.app-token.outputs.app-slug }}[bot]@users.noreply.github.com'
      - run: |
          git add .
          git commit -m "Auto-generated changes"
          git push
~~~

### Example 10: Proxy Support

~~~yaml
- uses: actions/create-github-app-token@v3
  id: app-token
  env:
    HTTPS_PROXY: http://proxy.example.com:8080
    NO_PROXY: github.example.com
    NODE_USE_ENV_PROXY: "1"
  with:
    client-id: ${{ vars.APP_CLIENT_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
~~~

### Example 11: Base64-Encoded Private Key

~~~yaml
steps:
  - name: Decode the GitHub App Private Key
    id: decode
    run: |
      private_key=$(echo "${{ secrets.APP_PRIVATE_KEY }}" | base64 -d | awk 'BEGIN {ORS="\\n"} {print}' | head -c -2) &> /dev/null
      echo "::add-mask::$private_key"
      echo "private-key=$private_key" >> "$GITHUB_OUTPUT"
  - name: Generate GitHub App Token
    id: app-token
    uses: actions/create-github-app-token@v3
    with:
      client-id: ${{ vars.APP_CLIENT_ID }}
      private-key: ${{ steps.decode.outputs.private-key }}
~~~

### Example 12: Passing Token to Another Job (skip-token-revoke)

~~~yaml
jobs:
  generate-token:
    runs-on: ubuntu-latest
    outputs:
      token: ${{ steps.app-token.outputs.token }}
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
          skip-token-revoke: true

  use-token:
    needs: generate-token
    runs-on: ubuntu-latest
    steps:
      - run: echo "Token received (first 10 chars): ${{ needs.generate-token.outputs.token }}"
        # Note: token is masked, so full value won't print
~~~

---

## Underlying API Call

### Endpoint

```
POST /app/installations/{installation_id}/access_tokens
```

**Documentation:** https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app

### Authentication

This endpoint requires authentication as the **GitHub App itself** using a JWT. It does NOT work with:
- GitHub App user access tokens
- GitHub App installation access tokens
- Fine-grained personal access tokens

**Authorization header format:** `Authorization: Bearer <JWT>` (MUST use `Bearer`, not `token`)

### The Full Authentication Flow (what the action does internally)

1. **Generate a JWT** signed with the App's private key containing:
   - `iss`: The App ID (numeric)
   - `iat`: Issued at time
   - `exp`: Expiration time (max 10 minutes from `iat`)
   - Algorithm: RS256

2. **Find the installation ID** using one of:
   - `GET /repos/{owner}/{repo}/installation`
   - `GET /orgs/{org}/installation`
   - `GET /app/installations` (list all, filter by owner)

3. **Create the token** by posting to `/app/installations/{installation_id}/access_tokens`

### Request Body Parameters

| Parameter | Type | Description |
|---|---|---|
| `repositories` | array of strings | List of repository names to scope access to (max 500) |
| `repository_ids` | array of integers | Alternative: list repository IDs to scope access to (max 500) |
| `permissions` | object | Map of permission name to level (e.g., `{"issues": "write", "contents": "read"}`) |

### Required Headers

~~~
Accept: application/vnd.github+json
Authorization: Bearer <JWT>
X-GitHub-Api-Version: 2026-03-10
~~~

### Response (Status 201)

~~~json
{
  "token": "ghs_16C7e42F292c6912E7710c838347Ae178B4a",
  "expires_at": "2016-07-11T22:14:10Z",
  "permissions": {
    "issues": "write",
    "contents": "read"
  },
  "repository_selection": "selected",
  "repositories": [
    {
      "id": 1296269,
      "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
      "name": "Hello-World",
      "full_name": "octocat/Hello-World",
      "owner": {
        "login": "octocat",
        "id": 1,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif"
      },
      "has_multiple_single_files": false,
      "single_file_paths": []
    }
  ]
}
~~~

### Response Fields

| Field | Type | Description |
|---|---|---|
| `token` | string | The installation access token (prefixed `ghs_`) |
| `expires_at` | string | ISO 8601 timestamp of expiration (always 1 hour from creation) |
| `permissions` | object | The actual permissions granted to the token |
| `repository_selection` | string | `"selected"` if scoped to specific repos, `"all"` if all installation repos |
| `repositories` | array | Repository objects the token has access to (only present when `repository_selection` is `"selected"`) |

### Status Codes

| Code | Meaning |
|---|---|
| 201 | Token created successfully |
| 401 | Authentication failed (invalid JWT) |
| 403 | Forbidden (app not installed, or insufficient permissions) |
| 404 | Installation not found |
| 422 | Validation failed (e.g., requested permissions exceed installation permissions) |

---

## Token Comparison

| Feature | `GITHUB_TOKEN` | GitHub App Token (this action) | Personal Access Token (PAT) |
|---|---|---|---|
| **Identity** | Auto-generated hidden app per repo | Your registered GitHub App | Individual user |
| **Token prefix** | `ghs_` | `ghs_` | Fine-grained: `github_pat_`; Classic: `ghp_` |
| **Max lifetime** | Job-scoped (6hr hosted, 24hr self-hosted) | 1 hour | Fine-grained: configurable; Classic: no expiry by default |
| **Scope** | Current repository only | Installation-wide (can be scoped down per-repo) | Configured at creation (user/org + repos) |
| **Cross-repo access** | No | Yes | Yes (if granted) |
| **Trigger other workflows** | No | Yes | Yes |
| **API rate limit** | 1,000 requests/hour | 5,000 requests/hour (10,000/hr Enterprise Cloud) | 5,000 requests/hour (10,000/hr Enterprise Cloud) |
| **Permission control** | `permissions:` key in YAML | `permission-*` inputs + installation settings | Set at token creation, cannot be changed |
| **Rotation** | Automatic (per-job) | Automatic (1hr TTL, must regenerate) | Manual (must create new token, delete old) |
| **Revocation** | Automatic (end of job) | Automatic (end of job, unless `skip-token-revoke`) | Manual deletion required |
| **Programmatic creation** | N/A (auto-provided) | Yes (via API with JWT) | No API exists for creation/deletion |
| **Bot user identity** | `github-actions[bot]` | `{app-slug}[bot]` | User's actual identity |
| **GitHub Packages auth** | Yes | No (known limitation) | Yes |
| **Secret storage** | Not needed (auto-provided) | Private key as secret | Token itself as secret |

---

## Private Key Management

### Key Format

- **Format:** PEM (Privacy Enhanced Mail)
- **Algorithm:** RSA (typically 2048-bit or 4096-bit)
- **Headers:** `-----BEGIN RSA PRIVATE KEY-----` ... `-----END RSA PRIVATE KEY-----`
- **Generated from:** GitHub App Settings → "Private keys" section → "Generate a private key"

### Generating a Key

1. Go to https://github.com/settings/apps → select your App
2. Scroll to "Private keys" section
3. Click "Generate a private key"
4. A `.pem` file downloads automatically
5. GitHub stores only the public key; you cannot re-download the private key later

### Storing the Key

**Recommended: Organization Secret**
- Navigate to Organization Settings → Secrets and variables → Actions
- Add as an organization secret (e.g., `APP_PRIVATE_KEY`)
- Paste the full PEM contents including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`
- GitHub Secrets automatically handle escaped newlines (`\n`), and the action auto-converts them back

**Alternative: Repository Secret**
- For single-repo usage, store at repo level
- Same paste process as above

**Alternative: Base64-Encoded**
- Encode: `base64 -w 0 private-key.pem`
- Store the base64 string as a secret
- Decode in workflow before passing to action (see Example 11 above)
- Useful when the key contains characters that cause issues in some secret storage systems

### Key Rotation Best Practices

1. **Delete unused keys:** If you generate a new private key, delete the old one from GitHub App settings. Old keys remain valid until deleted.
2. **Never hard-code keys:** Even in private repositories. Always use GitHub Secrets.
3. **Use org-level secrets:** When the App is used across multiple repos, store the key at the org level for centralized management.
4. **Generate fresh tokens per job:** The 1-hour TTL and auto-revocation ensure each job gets a fresh token. Do NOT cache tokens across runs.
5. **Audit key usage:** Monitor the GitHub App's installation access token usage in the Audit Log (Organization Settings → Audit log → filter by `app_installation`).
6. **Multiple keys for rotation:** You can have up to a limited number of active private keys simultaneously, allowing zero-downtime rotation:
   - Generate new key
   - Update the secret with the new key
   - Verify workflows work with the new key
   - Delete the old key from GitHub App settings
7. **Do NOT store in environment variables:** Environment variables can leak in logs. Use Secrets only.

### What Happens If a Key Is Compromised

1. Immediately delete the private key from GitHub App settings (this invalidates all tokens signed with it)
2. Generate a new private key
3. Update the secret in all organizations/repositories
4. All existing installation access tokens signed with the old key become invalid immediately

---

## Limitations and Gotchas

### Token Lifetime
- Installation access tokens expire after exactly **1 hour** from creation.
- For jobs running longer than 1 hour, you must regenerate the token (the action can be called again in a later step, or use `skip-token-revoke: true` and pass the token between jobs — but it still expires at 1 hour).
- Reference: https://github.com/actions/create-github-app-token/issues/121#issuecomment-2043214796

### Token Revocation and Cross-Job Passing
- By default, the token is revoked in the action's `post` step (after the job completes).
- This means the token **CANNOT be passed to another job** unless you set `skip-token-revoke: true`.
- Even with `skip-token-revoke: true`, the token still expires after 1 hour.
- The token is automatically **masked** in logs — you cannot accidentally log it.

### Permission Elevation Is Impossible
- You can only narrow permissions from what the installation has, never broaden them.
- If the installation has `issues: read` and you request `permission-issues: write`, the action errors.
- Installation permissions may lag behind App permissions: when an App adds new permissions post-installation, an org admin must approve them before they take effect on the installation.

### Repository Access Constraints
- Can only access repositories the App installation was granted access to.
- Maximum 500 repositories per token (API limit).
- Repository names are resolved within the context of the specified `owner`.

### GitHub Packages Limitation
- GitHub App installation access tokens **cannot authenticate with GitHub Package Registry**.
- This is a known pain point documented in GitHub Community Discussion #24636.
- For package operations, use `GITHUB_TOKEN` or a PAT instead.

### Rate Limits

| Context | Rate Limit |
|---|---|
| GitHub App installation token (standard) | 5,000 requests/hour |
| GitHub App installation token (Enterprise Cloud, org-owned) | 10,000 requests/hour |
| GITHUB_TOKEN | 1,000 requests/hour |
| Unauthenticated | 60 requests/hour |
| Secondary limits | 100 concurrent requests max, 500/min burst |

### Proxy Configuration
- If using `HTTP_PROXY` or `HTTPS_PROXY` environment variables, you must also set `NODE_USE_ENV_PROXY: "1"` on the action step.
- Use `NO_PROXY` for proxy bypass rules.
- The proxy env vars must be set on the `env` block of the step, not at job or workflow level (see Example 10).

### Client ID vs App ID
- `client-id` is the recommended input (the OAuth Client ID string like `Iv1.abc123`)
- `app-id` is the legacy input (the numeric ID like `123456`)
- Both work; the action accepts either. Prefer `client-id` for new workflows.

---

## Source URLs

1. **Official Action Repository:** https://github.com/actions/create-github-app-token
2. **GitHub Marketplace Listing:** https://github.com/marketplace/actions/create-github-app-token
3. **Generating an Installation Access Token:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
4. **REST API Reference — Create Installation Access Token:** https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app
5. **Managing Private Keys for GitHub Apps:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
6. **Best Practices for Creating a GitHub App:** https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app
7. **Choosing Permissions for a GitHub App:** https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
8. **Controlling Permissions for GITHUB_TOKEN:** https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token
9. **GITHUB_TOKEN Concepts:** https://docs.github.com/en/actions/concepts/security/github_token
10. **Permissions Required for GitHub Apps:** https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps
11. **Managing Personal Access Tokens (permission names reference):** https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
12. **DeepWiki — Cross-Repository Operations:** https://deepwiki.com/actions/create-github-app-token/5.2-cross-repository-operations
13. **Replacing PAT with GitHub App (Aembit):** https://aembit.io/blog/replacing-a-github-personal-access-token-with-a-github-application/
14. **GitHub Apps vs GITHUB_TOKEN (TimesOfCloud):** https://timesofcloud.com/github-actions/github-apps/
15. **GitHub Packages Auth Limitation (Community Discussion #24636):** https://github.com/orgs/community/discussions/24636
16. **Long-running Token Issue (#121):** https://github.com/actions/create-github-app-token/issues/121#issuecomment-2043214796
