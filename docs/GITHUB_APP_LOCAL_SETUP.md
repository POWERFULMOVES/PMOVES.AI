# GitHub App Local Setup (Self-Hosted)

This runbook covers the PMOVES.AI GitHub App: local setup, org-wide installation, and runtime token minting.

## What GitHub Requires

- **Homepage URL** (required): can be your repo URL, e.g. `https://github.com/POWERFULMOVES/PMOVES.AI`.
- **Webhook URL** (optional but needed for event-driven automation): must be publicly reachable.
- **Callback URL** (only if using user-to-server OAuth flow): can use a tunnel URL during local testing.

You do **not** need a permanently hosted website to use a GitHub App locally.

## Org-Wide Installation

The PMOVES.AI GitHub App is installed org-wide on all POWERFULMOVES repositories.

### Install Steps

1. GitHub.com → Settings → Developer Settings → GitHub Apps → PMOVES.AI app
2. Install → Select **"All repositories"** under POWERFULMOVES org
3. Verify installation:

```bash
gh api /user/installations --jq '.installations[] | {id, account: .account.login, repository_selection}'
```

4. Store the installation ID as a GitHub secret:

```bash
gh secret set GH_APP_INSTALLATION_ID --repo POWERFULMOVES/PMOVES.AI
```

## Secrets Reference

### GitHub Actions Secrets (CI)

| Secret | Description | How to Set |
|--------|-------------|------------|
| `GH_APP_ID` | GitHub App numeric ID | GitHub App settings page |
| `GH_APP_SEC` | PEM private key (full file contents) | `gh secret set GH_APP_SEC < /path/to/private-key.pem` |
| `GH_APP_CLIENT_ID` | OAuth Client ID | GitHub App settings page |
| `GH_APP_INSTALLATION_ID` | Installation ID for POWERFULMOVES org | From `gh api /user/installations` |

### Local Environment (env.shared)

For runtime token minting by services (BoTZ MCP gateway, Archon):

| Variable | Description |
|----------|-------------|
| `GH_APP_ID` | Same App ID as CI |
| `GH_APP_SEC` | PEM private key (multi-line value in env file) |
| `GH_APP_CLIENT_ID` | OAuth Client ID |
| `GH_APP_INSTALLATION_ID` | Installation ID |

### Naming Clarification

- `GH_APP_SEC` = the PEM private key (GitHub Actions secret name)
- `GH_APP_PRIVATE_KEY` = legacy alias used in some older docs (same value)
- Always use `GH_APP_SEC` for consistency with CI

## PEM Key Troubleshooting

The `actions/create-github-app-token@v2` action has strict PEM validation. If you see `Invalid keyData`:

1. **Re-set the secret from the raw PEM file:**
```bash
# Bash / WSL
gh secret set GH_APP_SEC --repo POWERFULMOVES/PMOVES.AI < /path/to/private-key.pem

# PowerShell
Get-Content .\private-key.pem -Raw | gh secret set GH_APP_SEC --repo POWERFULMOVES/PMOVES.AI
```

2. **Verify the PEM file is valid:**
```bash
openssl rsa -in /path/to/private-key.pem -check -noout
```

3. **Common issues:**
   - Extra whitespace or newlines at end of file
   - Encoding corruption from copy-paste (use file redirect, not paste)
   - Missing `-----BEGIN RSA PRIVATE KEY-----` header/footer

## Local Webhook Patterns

### Option A: Smee (simple relay)

1. Create a channel at `https://smee.io`.
2. Put that Smee URL in GitHub App **Webhook URL**.
3. Run local relay:

```bash
npx smee-client --url https://smee.io/<channel-id> --path /github/webhook --port 3000
```

4. Run your local webhook server on port `3000`.

### Option B: Cloudflared / ngrok

- Start local server on `localhost:3000`.
- Expose it with a tunnel and use the generated HTTPS URL as webhook URL.

## Runtime Token Minting (Services)

Services that need GitHub API access can mint short-lived installation tokens:

```python
import jwt, time, requests, os

def mint_installation_token():
    app_id = os.environ["GH_APP_ID"]
    pem = os.environ["GH_APP_SEC"]
    install_id = os.environ["GH_APP_INSTALLATION_ID"]

    payload = {"iat": int(time.time()) - 60, "exp": int(time.time()) + 600, "iss": app_id}
    jwt_token = jwt.encode(payload, pem, algorithm="RS256")

    resp = requests.post(
        f"https://api.github.com/app/installations/{install_id}/access_tokens",
        headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]
```

Installation tokens expire after 1 hour. Services should mint on-demand, not cache.

## Validation Checklist

- [ ] Webhook deliveries in the GitHub App settings show `2xx`
- [ ] Local relay logs incoming webhook payloads
- [ ] Actions that mint app tokens succeed (`actions/create-github-app-token@v2`)
- [ ] GHCR login works with minted token
- [ ] `gh api /user/installations` shows `repository_selection: "all"`
- [ ] `GH_APP_INSTALLATION_ID` secret is set

## Further Reading

- Strategy doc: `pmoves/docs/infrastructure/github-app-strategy.md`
- Credentials workflow: `.claude/context/credentials-workflow.md`
- Bootstrap registry: `pmoves/bootstrap/registry.json` (section `github-app`)
