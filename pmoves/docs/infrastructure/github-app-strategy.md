# GitHub App Strategy — PMOVES.AI

**Version:** 1.0
**Date:** 2026-03-10
**Status:** Active

---

## 1. App Overview

The **PMOVES.AI** GitHub App is installed org-wide on all POWERFULMOVES repositories.

| Property | Value |
|----------|-------|
| App name | PMOVES.AI |
| Org | POWERFULMOVES |
| Installation scope | All repositories |
| Permissions | `contents:read`, `packages:write`, `pull_requests:write`, `issues:write`, `actions:read` |
| Webhook URL | Configurable (Smee for dev, n8n for production) |

### Secrets

| Secret | Location | Sensitive |
|--------|----------|-----------|
| `GH_APP_ID` | GitHub Actions + `env.shared` | No |
| `GH_APP_CLIENT_ID` | GitHub Actions + `env.shared` | No |
| `GH_APP_SEC` | GitHub Actions + `env.shared` | Yes (PEM) |
| `GH_APP_INSTALLATION_ID` | GitHub Actions + `env.shared` | No |

---

## 2. Token Hierarchy

```
GitHub App (long-lived credentials)
├── CI: actions/create-github-app-token@v2
│   └── Ephemeral GITHUB_TOKEN (1hr) → GHCR push/pull, cross-repo checkout
├── Runtime: JWT → installation token (1hr)
│   └── BoTZ MCP GitHub server, Archon work orders
└── Webhook: GitHub → n8n → NATS events
```

### Why App Tokens Over PATs

| Aspect | GitHub App Token | Personal Access Token |
|--------|------------------|----------------------|
| Expiry | 1 hour (auto) | Manual rotation |
| Scope | Per-installation | Per-user |
| Audit trail | App-level attribution | User-level |
| Rate limit | 5000/hr per installation | 5000/hr per user |
| Revocation | Automatic on expiry | Manual |

---

## 3. CI/CD Use

### GHCR Authentication

All image build workflows use the App for GHCR login:

```yaml
- name: Generate GitHub App token
  id: app_token
  continue-on-error: true
  uses: actions/create-github-app-token@v2
  with:
    app-id: ${{ secrets.GH_APP_ID }}
    private-key: ${{ secrets.GH_APP_SEC }}

- name: Login GHCR
  uses: docker/login-action@v4
  with:
    registry: ghcr.io
    username: ${{ steps.app_token.outputs.token && 'x-access-token' || env.GHCR_USERNAME }}
    password: ${{ steps.app_token.outputs.token || env.GHCR_PASSWORD }}
```

**Workflows:** `build-images.yml`, `integrations-ghcr.yml`, `self-hosted-builds.yml`, `self-hosted-builds-hardened.yml`

### Private Submodule Checkout

For workflows that need access to private POWERFULMOVES repos:

```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ steps.app_token.outputs.token }}
    submodules: true
```

### PEM Troubleshooting

`actions/create-github-app-token@v2` has strict PEM validation. If `Invalid keyData`:

```bash
gh secret set GH_APP_SEC --repo POWERFULMOVES/PMOVES.AI < /path/to/private-key.pem
```

Never paste PEM content — always use file redirect to preserve encoding.

---

## 4. BoTZ Integration (MCP GitHub Server)

Per AGNOTE4482, GitHub operations route through the BoTZ MCP catalog → Gateway → Agent Zero.

### Architecture

```
Agent Zero MCP API
    ↓
BoTZ Gateway (gateway.py)
    ↓
MCP Catalog (catalog.yml)
    ↓
github MCP server (@modelcontextprotocol/server-github)
    ↑
Token minted from GH_APP_ID + GH_APP_SEC
```

### Token Minting Wrapper

`features/github/mint_and_exec.py` — mints a short-lived installation token, then execs the upstream MCP server:

1. Reads `GH_APP_ID`, `GH_APP_SEC`, `GH_APP_INSTALLATION_ID` from env
2. Signs a JWT with the App's private key
3. Exchanges JWT for an installation token via GitHub API
4. Sets `GITHUB_PERSONAL_ACCESS_TOKEN` for the MCP server
5. Execs `npx -y @modelcontextprotocol/server-github`

### Available MCP Tools

Once registered, the following GitHub tools are available through BoTZ:

- `create_or_update_file` — Create/update files in repos
- `search_repositories` — Search across POWERFULMOVES org
- `create_issue` — Open issues
- `create_pull_request` — Open PRs
- `list_issues` / `list_pull_requests` — Query issues/PRs
- `get_file_contents` — Read files from repos
- `push_files` — Push multiple files
- `create_branch` — Branch management
- `search_code` — Code search across org

### NATS Subjects

```
botz.mcp.github.tool.executed.v1    # All GitHub tool calls
botz.mcp.github.pr.created.v1      # PR creation events
botz.mcp.github.issue.created.v1   # Issue creation events
```

---

## 5. Agent Zero Coordination

Agent Zero receives GitHub tools via BoTZ gateway's MCP catalog. When Agent Zero needs to interact with GitHub:

1. Agent Zero calls BoTZ Gateway MCP API
2. Gateway routes to `github` MCP server
3. MCP server uses minted installation token
4. Result flows back through the chain
5. Graphiti trail is signed for provenance

---

## 6. Archon Work Orders

Archon's repository management UI (`archon-ui-main/src/features/agent-work-orders/`) can use App installation tokens for:

- Cross-repo PR verification
- Repository status checks
- Automated issue management

**Backend:** Archon mints tokens using the same `GH_APP_ID` + `GH_APP_SEC` pattern.

---

## 7. n8n Webhook Automation

GitHub App webhooks → n8n → NATS events:

| GitHub Event | n8n Workflow | NATS Subject |
|-------------|-------------|--------------|
| `pull_request` | PR Router | `github.webhook.pr.v1` |
| `push` | Push Handler | `github.webhook.push.v1` |
| `issues` | Issue Router | `github.webhook.issue.v1` |
| `workflow_run` | CI Monitor | `github.webhook.ci.v1` |

**Setup:** Configure n8n's GitHub App credential node with `GH_APP_ID` + `GH_APP_SEC`. Webhook URL in App settings points to n8n's public endpoint.

---

## 8. Cross-Repo Operations

### Submodule Coordination

With org-wide installation, the App can:
- Checkout private submodules in CI without PATs
- Trigger builds across repos
- Coordinate submodule version bumps

### Org-Wide PR Automation

Via BoTZ MCP → Agent Zero:
- Automated PR creation for dependency updates
- Cross-repo change coordination
- Release management across POWERFULMOVES repos

---

## 9. Security Model

### Short-Lived Tokens
- Installation tokens expire after **1 hour**
- CI tokens are minted per-workflow-run
- Runtime tokens are minted on-demand (not cached)

### Credential Un-Export
- `GH_APP_SEC` (PEM) is in `env.shared` (gitignored) and GitHub Secrets
- Never committed to source
- Not in CHIT manifest (CI-only credential lifecycle)

### Audit Trail
- GitHub App provides app-level attribution for all API calls
- BoTZ MCP tool calls are logged to NATS (`botz.mcp.github.tool.executed.v1`)
- Graphiti trail entries are CHIT-signed for provenance

### Least Privilege
- App permissions are scoped to what's needed (contents:read, packages:write)
- Installation tokens inherit the App's permission set
- No user-level access — operations are attributed to the App

---

## Use Case Matrix

| Use Case | Channel | Service | Token Source |
|----------|---------|---------|-------------|
| GHCR auth | `actions/create-github-app-token@v2` | CI/CD | CI action |
| Private submodule checkout | App token in `actions/checkout` | CI/CD | CI action |
| PR automation (cross-repo) | BoTZ GitHub MCP → Agent Zero | BoTZ + Agent Zero | Runtime mint |
| Issue triage | BoTZ GitHub MCP → Agent Zero | BoTZ + Agent Zero | Runtime mint |
| Repo management | Archon work orders → App token | Archon | Runtime mint |
| Webhook events | GitHub App → n8n → NATS | n8n | Webhook signature |
| Submodule coordination | CI workflows + BoTZ MCP | CI + BoTZ | Both |
| Release automation | BoTZ MCP → `/github:actions` | BoTZ | Runtime mint |
| Security scanning aggregation | `/github:security` CLI command | Claude Code | `gh` CLI auth |
| Graphiti trail signing | Agent operation → `sign_trail.py` | BoTZ + Cipher | N/A |

---

## Related Files

| File | Purpose |
|------|---------|
| `.claude/context/credentials-workflow.md` | Credential bootstrap flow |
| `docs/GITHUB_APP_LOCAL_SETUP.md` | Local setup runbook |
| `pmoves/bootstrap/registry.json` | Bootstrap registry (`github-app` section) |
| `pmoves/tools/push-gh-secrets.sh` | Secret sync to GitHub Actions |
| `.github/workflows/build-images.yml` | Primary CI workflow using App token |
| `pmoves/docs/AGENTS/BOTZ_GATEWAY_AGENT_INTEGRATION.md` | BoTZ gateway architecture |
| `pmoves/docs/AGENTS/AGNOTE4482.md` | Agentic framework reference |
