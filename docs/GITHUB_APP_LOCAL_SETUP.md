# GitHub App Local Setup (Self-Hosted)

This runbook covers the common "GitHub App needs a website URL" and "I want to run locally" setup.

## What GitHub Requires

- **Homepage URL** (required): can be your repo URL, e.g. `https://github.com/POWERFULMOVES/PMOVES.AI`.
- **Webhook URL** (optional but needed for event-driven automation): must be publicly reachable.
- **Callback URL** (only if using user-to-server OAuth flow): can use a tunnel URL during local testing.

You do **not** need a permanently hosted website to use a GitHub App locally.

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

## Secrets You Should Set

- `GHCR_USERNAME`: GitHub username that owns the package PAT (if PAT auth is used).
- `GHCR_TOKEN`: PAT with `write:packages` + `read:packages` (and `repo` for private repos).
- `GH_APP_ID`: GitHub App ID.
- `GH_APP_INSTALLATION_ID`: installation ID for the target org/repo.
- `GH_APP_PRIVATE_KEY`: full PEM private key.

## Validation Checklist

- Webhook deliveries in the GitHub App settings show `2xx`.
- Local relay logs incoming webhook payloads.
- Actions that mint app tokens succeed.
- GHCR login works with matching `GHCR_USERNAME` + `GHCR_TOKEN`.

