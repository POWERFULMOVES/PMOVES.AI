# PMOVES.AI Cloudflare Workers CI/CD Integration

**Purpose**: Intelligent CI/CD orchestration layer that routes GitHub Actions builds to optimal runners (GPU, VPS, or cloud) based on workload analysis.

## Architecture Overview

```
GitHub Webhook
      ↓
Cloudflare Worker (Edge)
   ├── Analyzes changed files
   ├── Determines requirements (GPU, Docker, lightweight)
   └── Routes to optimal runner:
       ├── GPU builds → AI Lab (self-hosted, RTX 5090)
       ├── VPS deploys → cloudstartup/kvm4 (self-hosted)
       └── Lightweight → GitHub hosted (cost-effective)
```

### What This Is NOT

- **NOT a GitHub Actions runner replacement** - Cloudflare Workers cannot execute GitHub Actions jobs directly
- **NOT for running builds** - This orchestrates and tracks builds, doesn't run them

### What This IS

- **Intelligent build router** - Analyzes commits and routes to best runner
- **Build state tracker** - Stores build metadata in Cloudflare KV
- **Cost optimizer** - Uses cheapest runner for each task type
- **Notification hub** - Sends Discord alerts for important builds

## Hybrid Runner Strategy

### Runner Selection Matrix

| Workload Type | Runner | Reason | Cost/Build |
|--------------|--------|--------|-----------|
| **GPU builds** (Ollama, Hi-RAG GPU) | AI Lab (self-hosted) | Requires CUDA, RTX 5090 | $0 (electricity only) |
| **Docker builds** (services/*) | VPS (self-hosted) | Layer cache, persistent storage | $0 (fixed VPS cost) |
| **Deployments** (staging/prod) | cloudstartup/kvm4 (self-hosted) | Direct access to target env | $0 |
| **Lightweight** (docs, lint, tests) | GitHub hosted | No cache needed, quick spin-up | ~$0.05 |
| **Overflow/Fallback** | kvm2 (self-hosted) | Backup when primary busy | $0 |

### Decision Tree

```
Is GPU required?
├─ YES → AI Lab (self-hosted, gpu)
└─ NO → Is Docker build with cache benefit?
    ├─ YES → VPS (self-hosted)
    └─ NO → Is deployment to specific env?
        ├─ YES → cloudstartup/kvm4 (self-hosted)
        └─ NO → Is lightweight (<2 min)?
            ├─ YES → GitHub hosted
            └─ NO → VPS (self-hosted, default)
```

## Setup Instructions

### Prerequisites

1. **Cloudflare Account** with Workers enabled (free tier works)
2. **Wrangler CLI**: `npm install -g wrangler`
3. **GitHub webhook secret** (generate: `openssl rand -hex 32`)

### Installation

```bash
cd deploy/cloudflare

# Install dependencies
npm install

# Login to Cloudflare
wrangler login

# Create KV namespace for build state
wrangler kv:namespace create "CI_STATE"
wrangler kv:namespace create "CI_STATE" --preview

# Update wrangler.toml with KV IDs returned above
```

### Configuration

1. **Edit `wrangler.toml`**:
   ```toml
   account_id = "your_cloudflare_account_id"

   [[kv_namespaces]]
   binding = "CI_STATE"
   id = "your_kv_namespace_id"
   preview_id = "your_preview_kv_namespace_id"
   ```

2. **Set secrets**:
   ```bash
   # GitHub webhook secret
   echo "your_webhook_secret" | wrangler secret put WEBHOOK_SECRET

   # GitHub PAT for API calls (optional)
   echo "ghp_your_token" | wrangler secret put GITHUB_TOKEN

   # Discord webhook URL (optional)
   echo "https://discord.com/api/webhooks/..." | wrangler secret put DISCORD_WEBHOOK_URL
   ```

3. **Deploy**:
   ```bash
   # Staging
   npm run deploy:staging

   # Production
   npm run deploy:production
   ```

### GitHub Webhook Setup

1. Go to your GitHub repo: **Settings → Webhooks → Add webhook**

2. **Payload URL**: `https://pmoves-ci-orchestrator.your-account.workers.dev/webhook/github`

3. **Content type**: `application/json`

4. **Secret**: Your `WEBHOOK_SECRET` value

5. **Events**:
   - ✅ Push events
   - ✅ Pull request events
   - ✅ Workflow dispatch events
   - ✅ Workflow run events

6. **Active**: ✅ Enabled

## Usage

### Testing Locally

```bash
# Start dev server
npm run dev

# Test health endpoint
curl http://localhost:8787/health

# Test webhook (requires valid signature)
curl -X POST http://localhost:8787/webhook/github \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d @test-payload.json
```

### Monitoring

#### View logs:
```bash
wrangler tail
```

#### Check build status:
```bash
curl https://pmoves-ci-orchestrator.your-account.workers.dev/status?build_id=build-123456
```

#### Metrics (Prometheus format):
```bash
curl https://pmoves-ci-orchestrator.your-account.workers.dev/metrics
```

### Integration with Existing Workflows

The Worker doesn't replace your `.github/workflows/*.yml` files - it provides intelligence about which runner to use.

**Before** (static runner assignment):
```yaml
jobs:
  build:
    runs-on: ubuntu-latest  # Always GitHub hosted
```

**After** (dynamic, cost-optimized):
```yaml
jobs:
  build:
    # Worker analyzes commit and suggests optimal runner via API
    # Still uses your existing self-hosted-builds.yml logic
    runs-on: [self-hosted, vps]  # or [self-hosted, ai-lab, gpu]
```

The Worker acts as a **monitoring and analytics layer**, not a replacement for runner logic.

## Cost Analysis

### Monthly Scenario: 500 CI Builds

| Component | Cost |
|-----------|------|
| Cloudflare Worker (50K requests) | **$0** (free tier: 100K req/day) |
| KV storage (build metadata, 24hr TTL) | **$0** (free tier: 1GB) |
| Self-hosted runners (AI Lab + 3x VPS) | **$30**/mo (VPS hosting) |
| GitHub hosted fallback (~50 builds) | **$5**/mo |
| **Total** | **$35/mo** |

### Without Hybrid Strategy (GitHub hosted only)

| Component | Cost |
|-----------|------|
| GitHub hosted (500 builds × 15min avg) | **$300**/mo |
| No GPU support | **N/A** (can't do GPU builds) |

**Savings: $265/month (88% reduction)**

## Operational Modes

Configure via `RUNNER_DISPATCH_MODE` in `wrangler.toml`:

### 1. Hybrid Mode (Recommended)
```toml
vars = { RUNNER_DISPATCH_MODE = "hybrid" }
```
- Intelligent routing based on workload analysis
- Uses cheapest runner for each task type
- Best cost/performance balance

### 2. Self-Hosted Only
```toml
vars = { RUNNER_DISPATCH_MODE = "self-hosted-only" }
```
- All builds on self-hosted infrastructure
- Maximum cost savings
- Requires sufficient self-hosted capacity

### 3. Cloudflare Mode (Testing)
```toml
vars = { RUNNER_DISPATCH_MODE = "cloudflare-only" }
```
- Uses GitHub hosted for compute (no self-hosted)
- Worker provides observability only
- Good for testing without self-hosted setup

## Limitations

### What Cloudflare Workers CAN'T Do

1. **Run GitHub Actions jobs directly** - Workers have 50ms CPU limit, can't build Docker images
2. **Access Docker daemon** - No containerization capabilities
3. **Mount volumes** - Ephemeral, stateless execution
4. **Run for >30 seconds** - Timeout constraints
5. **Execute arbitrary code** - Sandboxed JavaScript runtime

### What Self-Hosted Runners Provide

1. **GPU access** - CUDA builds, model inference
2. **Persistent cache** - Docker layers, dependencies
3. **Long-running builds** - 30+ minute builds
4. **Direct deployment** - SSH access to target environments
5. **Custom tooling** - Full control over runner environment

## Troubleshooting

### Worker not receiving webhooks

1. Check webhook deliveries in GitHub:
   - Settings → Webhooks → Recent Deliveries
   - Look for 2xx response codes

2. Verify signature validation:
   ```bash
   wrangler tail --format pretty
   # Look for "Invalid signature" errors
   ```

3. Check WEBHOOK_SECRET matches GitHub:
   ```bash
   wrangler secret list
   ```

### Build routing not working

1. Check worker logs:
   ```bash
   wrangler tail
   ```

2. Verify KV namespace is accessible:
   ```bash
   wrangler kv:key list --namespace-id=your_kv_id
   ```

3. Test locally with sample payload:
   ```bash
   npm run dev
   # Send test webhook
   ```

### Discord notifications not sending

1. Verify DISCORD_WEBHOOK_URL secret:
   ```bash
   wrangler secret list
   ```

2. Test webhook manually:
   ```bash
   curl -X POST "https://discord.com/api/webhooks/..." \
     -H "Content-Type: application/json" \
     -d '{"content": "Test from PMOVES.AI"}'
   ```

## Maintenance

### Updating the Worker

```bash
# Edit worker.js
vim worker.js

# Test locally
npm run dev

# Deploy to staging first
npm run deploy:staging

# Verify staging
curl https://pmoves-ci-orchestrator-staging.your-account.workers.dev/health

# Deploy to production
npm run deploy:production
```

### Rotating Secrets

```bash
# Update GitHub webhook secret
echo "new_secret" | wrangler secret put WEBHOOK_SECRET

# Update in GitHub webhook settings
# Settings → Webhooks → Edit → Update Secret
```

### Monitoring Usage

```bash
# Check Workers analytics in Cloudflare dashboard
# Workers & Pages → pmoves-ci-orchestrator → Metrics

# View request volume, errors, CPU time
```

## Future Enhancements

### Phase 2 (Planned)

- [ ] **Cost tracking** - Store runner costs in KV, generate reports
- [ ] **Build queue management** - Dispatch to available runner with least load
- [ ] **Automatic failover** - Retry on backup runner if primary fails
- [ ] **A/B testing** - Route percentage of builds to test new runners

### Phase 3 (Future)

- [ ] **ML-based routing** - Learn optimal runner for each repo/branch
- [ ] **Predictive scaling** - Pre-warm runners based on commit patterns
- [ ] **Multi-repo orchestration** - Coordinate builds across PMOVES org

## References

- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [GitHub Webhooks](https://docs.github.com/en/webhooks)
- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [PMOVES.AI Self-Hosted Runners](/home/pmoves/PMOVES.AI/deploy/runners/README.md)

---

**Questions?** See `/home/pmoves/PMOVES.AI/.claude/CLAUDE.md` for PMOVES.AI architecture context.
