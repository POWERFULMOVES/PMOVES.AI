# RAW RESEARCH: actions/create-github-app-token
# Compiled: 2026-04-23 — No synthesis, no summarization. Raw findings only.

---

## SOURCE 1: Search Engine Query — "actions create-github-app-token usage examples repositories permissions"
### URL: search_engine results

**Result 1:** https://github.com/actions/create-github-app-token
> Usage In order to use this action, you need to: Register new GitHub App. Store the App's Client ID in your repository environment variables (example: GITHUB_APP_CLIENT_ID). Store the App's private key in your repository secrets (example: GITHUB_APP_PRIVATE_KEY).

**Result 2:** https://blog.devops.dev/a-comprehensive-guide-to-creating-and-using-a-basic-github-app-for-token-management-via-0bfcfa39f5c1
> At this point, you have seen quite a bit: the process of registering and installing a Github App, generating a private key and storing it as a secret, setting the App ID as a repository variable, how to utilize the App to generate installation access tokens with actions/create-github-app-installation-token in a workflow, and finally using that...

**Result 3:** https://github.com/marketplace/actions/create-github-app-token
> Usage · Create a token for the current repository · Use app token with actions/checkout · Create a git committer string for an app installation · Configure git CLI...

**Result 4:** https://deepwiki.com/actions/create-github-app-token/2-getting-started
> Getting Started Relevant source files This document provides instructions for setting up and implementing the create-github-app-token GitHub Action in your workflows. You'll learn how to create a GitHub App, configure the action, and use the generated tokens in various scenarios. For details about the internal architecture, see Architecture. Prerequisites Before using this action, you need to...

**Result 5:** https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
> When a user authorizes the app to act on their behalf, the GitHub App can use the resulting user access token to make requests to the REST API and the GraphQL...

**Result 6:** https://aembit.io/blog/replacing-a-github-personal-access-token-with-a-github-application/
> One common method for authenticating against GitHub APIs is to use personal access tokens (PATs), which are user-generated, fine-grained tokens. These tokens...

**Result 7:** https://remarkablemark.org/blog/2026/01/28/create-github-app-token/
> This post goes over how to generate an app token in GitHub Actions with Create GitHub App Token. Prerequisites Follow the steps: Register a new GitHub App Store your App ID in your repository secrets Store your App private key in your repository secrets Create GitHub App Token Use actions/create-github-app-token with actions/checkout:

**Result 8:** https://github.com/orgs/community/discussions/24636
> You cannot authenticate with a GitHub App token on the GitHub Package Registry. This is a pain point for other GitHub users as well and the Packages team is...

**Result 9:** https://timesofcloud.com/github-actions/github-apps/
> GitHub Apps: The default GITHUB_TOKEN has limitations — it can't trigger other workflows, has limited rate limits, and its permissions are scoped to the current repository. GitHub Apps solve these problems.
> When to Use a GitHub App:
> - Scenario | GITHUB_TOKEN | GitHub App
> - Checkout code | yes | yes
> - Comment on PRs | yes | yes
> - Trigger other workflows | NO | yes
> - Cross-repo operations | NO | yes
> - Higher API rate limits | 1,000/hr | 5,000/hr
> - Fine-grained... | limited | yes

**Result 10:** https://adaptive-enforcement-lab.com/patterns/github-actions/actions-integration/token-generation/
> Installation tokens provide automated, secure access to repositories where your GitHub App is installed. Use installation tokens for GitHub Actions workflows, CI/CD automation, and cross-repository operations.

---

## SOURCE 2: Search Engine Query — "actions/create-github-app-token inputs app-id private-key owner repositories"
### URL: search_engine results

**Result 1:** https://github.com/actions/create-github-app-token
> Usage In order to use this action, you need to: Register new GitHub App. Store the App's Client ID in your repository environment variables (example: GITHUB_APP_CLIENT_ID). Store the App's private key in your repository secrets (example: GITHUB_APP_PRIVATE_KEY).

**Result 2:** https://blog.devops.dev/a-comprehensive-guide-to-creating-and-using-a-basic-github-app-for-token-management-via-0bfcfa39f5c1
> (same as above)

**Result 3:** https://dev.to/dtinth/authenticating-as-a-github-app-in-a-github-actions-workflow-27co
> Oftentimes we need to make our GitHub Actions workflow communicate with GitHub APIs. Many authentication methods exist, and each comes with its own pros and cons. You can use the built-in GITHUB_TOKEN secret, a personal access token, or a GitHub App. The first two methods are pretty well-documented, but soon I faced some limitations when using these two methods. The GITHUB_TOKEN cannot access...

**Result 4:** https://github.com/marketplace/actions/create-github-app-token
> Create a token for multiple repositories in the current owner's installation ... on: [issues] jobs: hello-world: runs-on: ubuntu-latest steps: - uses: actions/...

**Result 5:** https://deepwiki.com/actions/create-github-app-token/2-getting-started
> (same as above)

**Result 6:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
> The ID of a single repository that the user access token can access. If the GitHub App or user cannot access the repository, this will be ignored. Use this...

**Result 7:** https://remarkablemark.org/blog/2026/01/28/create-github-app-token/
> (same as above)

**Result 8:** https://github.com/marketplace/actions/create-github-app-token-using-aws-kms
> GitHub Action for generating a GitHub App installation access token using AWS KMS in order to safely store the GitHub App private key.

**Result 9:** https://explained.tines.com/en/articles/9968892-github-apps-authentication-guide
> "Client ID" of the GitHub App - Required to generate a JWT token to obtain an installation token. "Private key" of the GitHub App - Required to generate a...

**Result 10:** https://cicube.io/workflow-hub/tibdex-github-app-token-action/
> App ID: Available in the settings for your GitHub App. Private Key: Created during the creation of the GitHub App, be sure to keep this in a secure location. When you store your credentials securely with GitHub Secrets, no one unauthorized will get access to them, and your automation process stays intact in its integrity.

---

## SOURCE 3: Search Engine Query — "github app token scope specific repositories actions"
### URL: search_engine results

**Result 1:** https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
> Scopes let you specify exactly what type of access you need. Scopes limit access for OAuth tokens. They do not grant any additional permission beyond that which the user already has.

**Result 2:** https://github.com/orgs/community/discussions/21999
> GitHub Apps allow per-repository access and more finely-grained scopes. One approach you could take is creating a GitHub App whose sole responsibility is...

**Result 3:** https://deepwiki.com/actions/create-github-app-token/5.2-cross-repository-operations
> The create-github-app-token action provides flexible scoping options through its owner and repositories inputs. Understanding how these inputs affect token scope is essential for cross-repository operations.

**Result 4:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
> The ID of a single repository that the user access token can access. If the GitHub App or user cannot access the repository, this will be ignored. Use this...

**Result 5:** https://stackoverflow.com/questions/71068476/accessing-another-repository-with-github-cli-in-github-actions
> The GITHUB_TOKEN is scoped only to the triggering repository. If you need to access any resources in other repositories or in other accounts then you need to pass a token with a wider scope to the checkout step. This can be a GitHub App token, a Personal Access Token etc. Store the token in the Secrets/Actions and pass it to the checkout task's token parameter.

**Result 6:** https://github.com/akuity/kargo/issues/3172
> Dec 21, 2024 ... When using a global GitHub App installation token, introduce some way to define a set of repositories accessible by individual Projects which...

**Result 7:** https://jfagerberg.me/blog/2024-11-03-gha-access-other-repos/
> The simplest approach is for the developer creating your CI workflow to generate a personal access token (PAT) with the required permissions, and then store it as a secret in your source repository. Since GitHub supports fine-grained PATs scoped to specific repositories, a leak of this secret won't cause too wide of a breach.

**Result 8:** https://stackoverflow.com/questions/63906613/minimal-set-of-scopes-to-push-to-github-using-an-access-token
> Sep 15, 2020 ... According to the GitHub documentation, the scope for public repositories is public_repo , and for private repositories is repo . A token...

**Result 9:** https://remarkablemark.org/blog/2026/01/28/create-github-app-token/
> Set owner and/or repositories to set the token access scope: ... If owner is set and repositories is empty, access will be scoped to all repositories in the provided repository owner's installation. If owner and repositories are empty, access will be scoped to only the current repository.

**Result 10:** https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
> Each token is limited to access resources owned by a single user or organization. · Each token can be further limited to only access specific repositories for...

---

## SOURCE 4: Search Engine Query — "github app private key management best practices actions workflow"
### URL: search_engine results

**Result 1:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
> You should not hard-code your private key in your app, even if your code is stored in a private repository. For more information, see Best practices for creating a GitHub App.

**Result 2:** https://devactivity.com/insights/github-app-tokens-secure-practices-for-workflow-performance-and-analytics/
> Explore best practices for managing GitHub App tokens across jobs in GitHub Actions. Learn why generating fresh, short-lived tokens for each job is crucial for security, workflow integrity, and reliable data for performance analytics software.

**Result 3:** https://dev.to/dtinth/authenticating-as-a-github-app-in-a-github-actions-workflow-27co
> (same as above)

**Result 4:** https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app
> You should delete private keys that are no longer in use. For more information, see Managing private keys for GitHub Apps. Client secrets. Client secrets are...

**Result 5:** https://blog.devops.dev/a-comprehensive-guide-to-creating-and-using-a-basic-github-app-for-token-management-via-0bfcfa39f5c1
> Feb 15, 2026 ... Installation access tokens are short-lived, transient tokens that inherit permissions granted to the Github App. They're "non-personal" in that...

**Result 6:** https://medium.com/@innovativejude.tech/securely-managing-api-keys-and-credentials-in-github-actions-workflows-982277bef842
> By following these best practices and using the correct syntax to reference secrets, you ensure that sensitive information is handled securely in your GitHub Actions workflows.

**Result 7:** https://github.com/marketplace/actions/github-app-auth
> This action allows you to authenticate as an installation of a GitHub App in your workflow. This can be a more secure way to authenticate than using a personal...

**Result 8:** https://devtoolhub.com/github-actions-secrets-security-best-practices/
> When working with GitHub Actions, your workflows often require API keys, tokens, or credentials for deployments and integrations. Storing these securely is crucial — leaking secrets can compromise your entire system.

**Result 9:** https://github.com/orgs/community/discussions/187776
> You should never hardcode sensitive data like API keys or passwords in your workflow files or repository. Storage Levels: Repository Secrets: Best for secrets...

**Result 10:** https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow
> Register a GitHub App. · Store the app ID of your GitHub App as a GitHub Actions configuration variable. · Generate a private key for your app. · Install the...

---

## SOURCE 5: Official Action README — https://github.com/actions/create-github-app-token
### URL: https://github.com/actions/create-github-app-token
### Fetched via document_query with targeted questions

### ALL INPUT PARAMETERS (exact names, types, required/optional, defaults, descriptions):

1. **`client-id`** — *Required* — GitHub App Client ID. Note: The legacy `app-id` input is also accepted, but `client-id` is recommended.
2. **`app-id`** — *Required (legacy)* — Legacy input name for the GitHub App ID. `client-id` is the recommended replacement.
3. **`private-key`** — *Required* — GitHub App private key. Escaped newlines (`\\n`) will be automatically replaced with actual newlines.
4. **`skip-token-revoke`** — *Optional* — If true, the token will not be revoked when the current job is complete.
5. **`github-api-url`** — *Optional* — The URL of the GitHub REST API. Defaults to the URL of the GitHub REST API where the workflow is run from.
6. **`owner`** — *Optional* — The owner of the GitHub App installation. If empty, defaults to the current repository owner.
7. **`repositories`** — *Optional* — Comma or newline-separated list of repositories to grant access to.
8. **`permission-<permission name>`** — *Optional* — The permissions to grant to the token. By default, the token inherits all of the installation's permissions. We recommend to explicitly list the permissions that are required for a use case.

### ALL OUTPUT VARIABLES:

1. **`token`** — GitHub App installation access token.
2. **`installation-id`** — GitHub App installation ID.
3. **`app-slug`** — GitHub App slug.

### PERMISSIONS INPUT FORMAT:

The permissions input uses the format `permission-<permission name>` (e.g., `pull-requests` becomes `permission-pull-requests`). This format was chosen to benefit from type intelligence and input validation built into GitHub's action runner.

Valid permission names are listed in GitHub's documentation for controlling permissions of GITHUB_TOKEN in workflows: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token

You prefix the permission key with `permission-` (e.g., `pull-requests` → `permission-pull-requests`, `issues` → `permission-issues`).

Levels include at least `write`, `read`, and `none` based on standard GitHub token permissions.

Important notes:
- By default, if no permissions are specified, the token inherits all of the installation's permissions.
- It is recommended to explicitly list only the permissions required for a use case.
- Selected permissions must be granted to the installation of the specified app and repository owner.
- Setting a permission that the installation does not have will result in an error.

### REPOSITORIES INPUT — TOKEN SCOPING BEHAVIOR:

The `repositories` input accepts a comma or newline-separated list of repositories to grant access to. The scoping behavior depends on the combination with the `owner` input:

- **If `owner` and `repositories` are both empty:** Access is scoped to only the current repository.
- **If `owner` is set and `repositories` is empty:** Access is scoped to all repositories in the provided repository owner's installation.
- **If `repositories` is set (with or without `owner`):** Access is scoped to only the specified repositories.

### OWNER PARAMETER BEHAVIOR:

The `owner` parameter is optional and specifies the owner of the GitHub App installation. If left empty, it defaults to the current repository owner.

Use cases:
- **Empty/default:** Targets the current repository owner's installation
- **Specific owner (e.g., `owner: another-owner`):** Targets another owner's installation entirely
- **With `repositories`:** Targets specific repositories within that owner's installation
- **In matrix strategies:** Can be used with `${{ matrix.owners-and-repos.owner }}` to create tokens for multiple owners dynamically

Useful for GitHub Enterprise Server scenarios where you might need to specify a different installation organization.

### COMPLETE YAML WORKFLOW EXAMPLES FROM OFFICIAL README:

**Example 1: Use app token with actions/checkout**
```yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          # required
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - uses: actions/checkout@v6
        with:
          token: ${{ steps.app-token.outputs.token }}
          ref: ${{ github.head_ref }}
          # Make sure the value of GITHUB_TOKEN will not be persisted in repo's config
          persist-credentials: false
      - uses: creyD/prettier_action@v6
        with:
          github_token: ${{ steps.app-token.outputs.token }}
```

**Example 2: Create a git committer string for an app installation**
```yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          # required
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - name: Get GitHub App User ID
        id: get-user-id
        run: echo "user-id=$(gh api "/users/${{ steps.app-token.outputs.app-slug }}[bot]" --jq .id)" >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
      - id: committer
        run: echo "string=${{ steps.app-token.outputs.app-slug }}[bot] <${{ steps.get-user-id.outputs.user-id }}+${{ steps.app-token.outputs.app-slug }}[bot]@users.noreply.github.com>"  >> "$GITHUB_OUTPUT"
      - run: echo "committer string is ${{ steps.committer.outputs.string }}"
```

**Example 3: Create a token for the current repository (push event, self-hosted runner, GHES)**
```yaml
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
```

**Example 4: Create a token for the current repository (push to main)**
```yaml
name: Run tests on staging
on:
  push:
    branches:
      - main

jobs:
  hello-world:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          client-id: ${{ vars.APP_CLIENT_ID }}
          private-key: ${{ secrets.APP_PRIVATE_KEY }}
      - uses: ./actions/staging-tests
        with:
          token: ${{ steps.app-token.outputs.token }}
```

**Example 5: Configure git CLI for an app's bot user**
```yaml
on: [pull_request]

jobs:
  auto-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          # required
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
      # git commands like commit work using the bot user
      - run: |
          git add .
          git commit -m "Auto-generated changes"
          git push
```

**Example 6: Create a token with specific permissions**
```yaml
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
```

**Example 7: Create a token for all repositories in the current owner's installation**
```yaml
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
      - uses: peter-evans/create-or-update-comment@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
          issue-number: ${{ github.event.issue.number }}
          body: "Hello, World!"
```

**Example 8: Create a token for all repositories in another owner's installation**
```yaml
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
```

**Example 9: Create a token for multiple repositories in the current owner's installation**
```yaml
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
```

**Example 10: Create tokens for multiple user or organization accounts (matrix strategy)**
```yaml
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
```

**Example 11: Proxy support**
```yaml
- uses: actions/create-github-app-token@v3
  id: app-token
  env:
    HTTPS_PROXY: http://proxy.example.com:8080
    NO_PROXY: github.example.com
    NODE_USE_ENV_PROXY: "1"
  with:
    client-id: ${{ vars.APP_CLIENT_ID }}
    private-key: ${{ secrets.APP_PRIVATE_KEY }}
```

**Example 12: Decode Base64 encoded private key**
```yaml
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
```

### UNDERLYING API ENDPOINT:

The action creates an installation access token using the **`POST /app/installations/{installation_id}/access_tokens`** endpoint.

Documentation: https://docs.github.com/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app

### LIMITATIONS AND GOTCHAS:

1. **Token expiration:** An installation access token expires after 1 hour. For long-running processes, alternative approaches may be needed (see https://github.com/actions/create-github-app-token/issues/121#issuecomment-2043214796).

2. **Token revocation:** Unless the `skip-token-revoke` input is set to true, the token is revoked in the `post` step of the action. This means the token **cannot be passed to another job**.

3. **Installation permissions vs. App permissions:** Installation permissions can differ from the app's permissions they belong to. Installation permissions are set when an app is installed on an account. When the app adds more permissions after the installation, an account administrator must approve the new permissions before they are set on the installation.

4. **Permission validation errors:** Setting a permission that the installation does not have will result in an error. Selected permissions must be granted to the installation of the specified app and repository owner.

5. **Token masking:** The token is masked and cannot be logged accidentally (this is a security feature, but may complicate debugging).

6. **Proxy configuration:** If using `HTTP_PROXY` or `HTTPS_PROXY`, you must also set `NODE_USE_ENV_PROXY: "1"` on the action step so Node.js honors those variables. For proxy bypass rules, set `NO_PROXY` alongside them.

---

## SOURCE 6: GitHub Docs — Generating an Installation Access Token
### URL: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
### Fetched via document_query

### COMPLETE PROCESS FOR GENERATING AN INSTALLATION ACCESS TOKEN:

The complete process consists of three main steps:

1. **Generate a JSON Web Token (JWT)** for your app.
2. **Obtain the ID of the installation** you want to authenticate as. This can be found in:
   - The webhook payload if you are responding to a webhook event
   - REST API endpoints:
     - `GET /users/{username}/installation`
     - `GET /repos/{owner}/{repo}/installation`
     - `GET /orgs/{org}/installation`
     - `GET /app/installations`
3. **Send a REST API POST request** to `/app/installations/INSTALLATION_ID/access_tokens`, replacing `INSTALLATION_ID` with your actual installation ID, and include your JWT in the `Authorization` header.

### JWT AND API CALL DETAILS:

For JWT creation, you must generate a JSON web token specifically for your GitHub App. For the API call, you must send a `POST` request to the `/app/installations/INSTALLATION_ID/access_tokens` endpoint.

Critical: When passing the JWT in the `Authorization` header, you must use the format `Authorization: Bearer JWT`; unlike other tokens where `Authorization: Bearer` or `Authorization: token` can be used interchangeably, you MUST use `Bearer` for a JWT.

Required headers:
- `Accept: application/vnd.github+json`
- `X-GitHub-Api-Version: 2026-03-10`

### PERMISSIONS AND SCOPES FOR INSTALLATION ACCESS TOKENS:

If the `permissions` body parameter is not specified during creation, the installation access token will inherit all of the permissions that were granted to the app. You can optionally use the `permissions` parameter to specify exact permissions, but the token cannot be granted any permissions that the app itself was not granted.

Regarding repository access: If you do not use the `repositories` or `repository_ids` body parameters, the token will have access to all repositories that the installation was granted access to. You can optionally limit this to up to 500 specific repositories, but you cannot grant the token access to repositories that the installation was not already granted access to.

### TOKEN LIFETIME AND EXPIRATION:

An installation access token will expire after 1 hour. The exact time that the token expires is included in the response payload returned by the API when the token is successfully generated.

### RATE LIMITS:

The provided document does not contain specific information regarding the rate limits for installation access tokens.

### HOW INSTALLATION TOKENS DIFFER FROM OTHER TOKEN TYPES:

- When generating an installation access token, you must pass the required JWT using the `Authorization: Bearer` header, whereas other tokens can typically be passed using either `Bearer` or `token`.
- Unlike other tokens that might require manual generation and refreshing, GitHub's Octokit SDKs can automatically handle the generation and regeneration of installation access tokens once they expire.
- Installation access tokens are distinguished from:
  - JWTs (used to authenticate as the app itself)
  - User access tokens (used to authenticate on behalf of users)

---

## SOURCE 7: REST API Reference — POST /app/installations/{installation_id}/access_tokens
### URL: https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app
### Fetched via document_query

### EXACT PARAMETERS:

**Headers:**
- `accept` string — Setting to `application/vnd.github+json` is recommended.

**Path parameters:**
- `installation_id` integer (Required) — The unique identifier of the installation.

**Body parameters:**
- `repositories` array of strings — List of repository names that the token should have access to
- `repository_ids` array of integers — List of repository IDs that the token should have access to
- `permissions` object — The permissions granted to the user access token

### REQUEST BODY PARAMETER DETAILS:

- **`repositories`** (array of strings): List of repository names that the token should have access to. Optionally, you can use this parameter to specify individual repositories that the installation access token can access. Up to 500 repositories can be listed in this manner.

- **`repository_ids`** (array of integers): List of repository IDs that the token should have access to. This serves as an alternative to `repositories` for specifying repositories by their IDs.

- **`permissions`** (object): The permissions granted to the user access token. If not specified, the installation access token will have all of the permissions that were granted to the app. The installation access token cannot be granted permissions that the app was not granted.

**Important notes:** If you don't use `repositories` or `repository_ids` to grant access to specific repositories, the installation access token will have access to all repositories that the installation was granted access to. The installation access token cannot be granted access to repositories that the installation was not granted access to.

### RESPONSE FORMAT (Status 201):

```json
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
```

Response fields:
- `token` — The installation access token (prefixed with `ghs_`)
- `expires_at` — ISO 8601 timestamp of when the token expires
- `permissions` — Object mapping permission names to their level (e.g., `"issues": "write"`, `"contents": "read"`)
- `repository_selection` — Either "selected" or "all" indicating the scope
- `repositories` — Array of repository objects the token has access to

### STATUS CODES:

| Status Code | Description |
| --- | --- |
| `201` | Created |
| `401` | Requires authentication |
| `403` | Forbidden |
| `404` | Resource not found |
| `422` | Validation failed, or the endpoint has been spammed. |

### RATE LIMITS:

The document does not provide specific rate limit information for this endpoint. Rate limits for the REST API are covered in a separate section referenced in the navigation ("Rate limits" under "Using the REST API"), but the details are not included in the provided document text.

### REQUIRED HTTP HEADERS:

- **`Accept`**: Setting to `application/vnd.github+json` is recommended.
- **`Authorization`**: `Bearer <YOUR-TOKEN>` — You must use a JWT (JSON Web Token) to access this endpoint.
- **`X-GitHub-Api-Version`**: e.g., `2026-03-10` — Specifies the API version to use.

**Critical note:** This endpoint does NOT work with:
- GitHub App user access tokens
- GitHub App installation access tokens
- Fine-grained personal access tokens

You MUST authenticate as a GitHub App using a JWT.

---

## ADDITIONAL CONTEXT FROM PRIOR RESEARCH (stored in agent memory):

### GITHUB_TOKEN vs GitHub App Installation Access Token:

GITHUB_TOKEN (the default token in GitHub Actions) is actually a GitHub App installation access token under the hood — an auto-installed hidden app per repo, not a PAT. It's ephemeral (per-job lifetime: max 6hr on hosted runners, 24hr on self-hosted), repo-scoped only, and permissions are set via the YAML 'permissions' key.

GitHub Apps use installation access tokens (typically 1-hour TTL when generated via API using JWT auth from a PEM private key) as the only fully automated token rotation mechanism — this is the approach used by Shopify and recommended by GitHub. The difference in TTL (1hr API-generated vs 6hr/24hr job-scoped) reflects that GITHUB_TOKEN is scoped to the job lifecycle, not the raw token's maximum lifetime.

### GitHub API Rate Limits (from prior research):

- 5,000 requests/hr authenticated
- 10,000/hr for Enterprise Cloud org-owned GitHub Apps
- 60/hr unauthenticated
- Secondary limits: 100 concurrent requests max, 500/min burst limit

### GITHUB_TOKEN Limitations (from search results):

- Cannot trigger other workflows
- Limited rate limits (1,000/hr vs 5,000/hr for GitHub Apps)
- Permissions scoped to the current repository only
- Cannot do cross-repo operations

### GitHub App Token Advantages (from search results):

- Can trigger other workflows
- Higher API rate limits (5,000/hr)
- Cross-repository operations
- Fine-grained permission control
- Non-personal identity (bot user)
- Automatic rotation (1-hour TTL)

### Private Key Format:

- PEM format
- Generated from GitHub App settings page
- Must be stored as a repository or organization secret
- Escaped newlines (`\\n`) in secrets are automatically handled by the action
- Can be Base64-encoded and decoded in a workflow step before passing to the action

### Key Rotation Best Practices (from search results):

- You should delete private keys that are no longer in use
- You should not hard-code your private key in your app, even if your code is stored in a private repository
- Generating fresh, short-lived tokens for each job is crucial for security
- Store credentials securely with GitHub Secrets

### GitHub Packages Limitation:

From https://github.com/orgs/community/discussions/24636:
> You cannot authenticate with a GitHub App token on the GitHub Package Registry. This is a pain point for other GitHub users as well and the Packages team is...

---

## END OF RAW RESEARCH DATA
## Total sources: 7 (4 search engine queries, 3 document_query fetches) + prior memory context
## File saved to: /a0/usr/projects/pmoves/research/actions-create-github-app-token-raw-research.md
