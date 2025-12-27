# Cloudflare Worker Quick Start

**Time to deploy**: ~10 minutes

## Prerequisites

```bash
# Install Node.js 18+ and npm
node --version  # Should be v18 or higher

# Install Wrangler CLI globally
npm install -g wrangler

# Verify installation
wrangler --version
```

## 1-Minute Setup

```bash
# Navigate to deploy directory
cd /home/pmoves/PMOVES.AI/deploy/cloudflare

# Install dependencies
npm install

# Login to Cloudflare (opens browser)
wrangler login

# Create KV namespace for build state
wrangler kv:namespace create "CI_STATE"
# Copy the 'id' value returned

wrangler kv:namespace create "CI_STATE" --preview
# Copy the 'preview_id' value returned
```

## Configuration

### 1. Update wrangler.toml

```bash
vim wrangler.toml
```

Replace these values:
```toml
# account_id = "your_account_id_here"  # Find at: cloudflare.com → Workers & Pages
account_id = "abc123def456"

[[kv_namespaces]]
binding = "CI_STATE"
id = "xyz789abc123"  # From 'wrangler kv:namespace create' above
preview_id = "preview789abc123"  # From preview command above
```

### 2. Set Secrets

```bash
# GitHub webhook secret (generate: openssl rand -hex 32)
echo "your_webhook_secret_here" | wrangler secret put WEBHOOK_SECRET

# Optional: Discord webhook for notifications
echo "https://discord.com/api/webhooks/..." | wrangler secret put DISCORD_WEBHOOK_URL

# Optional: GitHub PAT for API calls
echo "ghp_your_github_token" | wrangler secret put GITHUB_TOKEN
```

## Deploy

```bash
# Deploy to production
npm run deploy

# Or deploy to staging first
npm run deploy:staging
```

**Output**:
```
Published pmoves-ci-orchestrator (0.42 sec)
  https://pmoves-ci-orchestrator.your-account.workers.dev
```

## Test

```bash
# Health check
curl https://pmoves-ci-orchestrator.your-account.workers.dev/health

# Expected response:
# {"status":"healthy","service":"pmoves-ci-orchestrator","mode":"hybrid","timestamp":"2025-12-08T..."}
```

## GitHub Webhook Setup

1. Go to: `https://github.com/POWERFULMOVES/PMOVES.AI/settings/hooks/new`

2. **Payload URL**: `https://pmoves-ci-orchestrator.your-account.workers.dev/webhook/github`

3. **Content type**: `application/json`

4. **Secret**: Your `WEBHOOK_SECRET` value (from step 2 above)

5. **Events**: Select:
   - ✅ Pushes
   - ✅ Pull requests
   - ✅ Workflow runs

6. Click **Add webhook**

7. **Test**: Push a commit and check Recent Deliveries tab

## Monitoring

```bash
# Watch live logs
wrangler tail

# View metrics in Cloudflare dashboard
# → Workers & Pages → pmoves-ci-orchestrator → Metrics
```

## Troubleshooting

### "Error: No account_id specified"

**Fix**: Add your Cloudflare account ID to `wrangler.toml`:
```bash
# Find your account ID
wrangler whoami
# Copy the Account ID, add to wrangler.toml
```

### "KV namespace not found"

**Fix**: Create KV namespace:
```bash
wrangler kv:namespace create "CI_STATE"
wrangler kv:namespace create "CI_STATE" --preview
# Update IDs in wrangler.toml
```

### "Invalid signature" in webhook logs

**Fix**: Ensure WEBHOOK_SECRET matches GitHub:
```bash
# Re-set secret
echo "correct_secret" | wrangler secret put WEBHOOK_SECRET

# Update in GitHub webhook settings
```

## Next Steps

1. ✅ Deployed Cloudflare Worker
2. ✅ Configured GitHub webhook
3. ➡️ See [HYBRID_RUNNER_STRATEGY.md](/home/pmoves/PMOVES.AI/deploy/HYBRID_RUNNER_STRATEGY.md) for full architecture
4. ➡️ Configure self-hosted runners: [/deploy/runners/README.md](/home/pmoves/PMOVES.AI/deploy/runners/README.md)

---

**Need help?** Check [deploy/cloudflare/README.md](/home/pmoves/PMOVES.AI/deploy/cloudflare/README.md) for detailed docs.
