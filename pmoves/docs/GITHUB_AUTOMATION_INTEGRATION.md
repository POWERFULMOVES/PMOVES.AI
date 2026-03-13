# GitHub Automation & Branch Strategy Integration

This document describes the integration between GitHub automation services and the PMOVES.AI branch strategy enforcement system.

## Overview

The integration combines three key systems:

1. **Branch Strategy Enforcement** - 3-tier promotion flow with validation
2. **GitHub Automation Services** - Branch cleanup, issue triage, naming validation
3. **Cross-Repo Synchronization** - Automated submodule updates

All systems communicate via NATS message bus for observability and coordination.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Webhooks                              │
│                    (via n8n or direct)                              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          NATS Message Bus                             │
│                       nats://nats:4222                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Branch     │  │    Issue     │  │   Cross-Repo │
│   Cleanup    │  │   Triage     │  │    Sync      │
│  Port 8100   │  │  Port 8101   │  │  Port 8103   │
└──────────────┘  └──────────────┘  └──────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │  Branch Naming       │
                  │  Enforcement         │
                  │  Port 8102           │
                  └──────────────────────┘
```

## Services

### 1. Branch Cleanup Service (Port 8100)

**Purpose:** Automatically removes stale branches after PR merge

**NATS Events:**
- Subscribe: `github.webhook.pr.v1`
- Publish: `github.branch.deleted.v1`, `github.branch.auto_deleted.v1`

**Key Features:**
- Auto-delete source branches after PR merge
- Stale branch detection (configurable TTL)
- Protected branch safeguards
- Dry-run mode for testing

**Configuration:**
```bash
# Environment variables
DRY_RUN=true                    # Set to false for production
STALE_DAYS=30                   # Days before branch considered stale
GITHUB_APP_ID=your_app_id
GITHUB_APP_INSTALLATION_ID=your_installation_id
```

**API Endpoints:**
- `GET /healthz` - Health check
- `GET /api/stale-branches?repo=PMOVES.AI&days=30` - List stale branches
- `POST /api/cleanup` - Trigger cleanup operation

### 2. Issue Triage Service (Port 8101)

**Purpose:** Intelligently categorize and label GitHub issues

**NATS Events:**
- Subscribe: `github.webhook.issue.v1`
- Publish: `github.issue.triage.v1`, `github.issue.labeled.v1`

**Key Features:**
- Semantic search via Hi-RAG v2
- Pattern-based classification fallback
- Confidence threshold filtering
- Label application via MCP

**Configuration:**
```bash
# Environment variables
HIRAG_URL=http://hi-rag-gateway-v2:8086
LABEL_CONFIDENCE_THRESHOLD=0.7
BOTZ_MCP_URL=http://botz-gateway:8102
```

**API Endpoints:**
- `GET /healthz` - Health check
- `POST /api/triage?repo=PMOVES.AI&issue_number=123` - Manual triage
- `GET /api/accuracy?repo=PMOVES.AI&days=30` - Triage accuracy

### 3. Branch Naming Service (Port 8102)

**Purpose:** Enforce PMOVES.AI branch naming conventions

**NATS Events:**
- Subscribe: `github.branch.created.v1`
- Publish: `github.branch.validation.v1`, `github.branch.rename_suggested.v1`

**Valid Patterns:**
- `feat/` - New features
- `fix/` - Bug fixes
- `chore/` - Maintenance tasks
- `docs/` - Documentation updates
- `codex/` - CODEX-generated branches
- `ref/docs/` - Reference documentation branches

**Protected Branches:**
- `PMOVES.AI-Edition-Hardened`
- `PMOVES.AI-Edition-Hardened-Integrations`
- `main`

**Configuration:**
```bash
# Environment variables
DRY_RUN=true                    # Set to false to auto-rename branches
NATS_URL=nats://nats:pmoves@nats:4222
```

**API Endpoints:**
- `GET /healthz` - Health check
- `GET /api/validate?branch=feat/new-feature` - Validate branch name
- `POST /api/validate` - Validate via JSON payload
- `GET /api/patterns` - List valid patterns

### 4. Cross-Repo Sync Service (Port 8103)

**Purpose:** Synchronize branch promotions across submodules

**NATS Events:**
- Subscribe: `github.promotion.completed.v1`
- Publish: `github.crossrepo.sync.v1`, `github.crossrepo.sync.completed.v1`, `github.crossrepo.sync.failed.v1`

**Key Features:**
- Automatic submodule gitlink updates
- Detects affected submodules
- Creates promotion PRs in submodules
- Dry-run mode for testing

**Configuration:**
```bash
# Environment variables
DRY_RUN=true                    # Set to false for production
GITHUB_ORG=POWERFULMOVES
MAIN_REPO=PMOVES.AI
WORKDIR=/tmp/github-crossrepo-sync
```

**API Endpoints:**
- `GET /healthz` - Health check
- `POST /api/sync` - Trigger manual sync
- `GET /api/submodules?repo=PMOVES.AI&branch=main` - List submodules

## Branch Strategy Integration

### Promotion Flow with NATS Events

```
feature/branch → Integrations → Hardened → main
       │              │              │         │
       ▼              ▼              ▼         ▼
   [validate]    [promote]      [promote]   [sync]
       │              │              │         │
       └──────────────┴──────────────┴─────────┘
                      │
                      ▼
                [NATS Events]
```

### Phase 1: Feature → Integrations

**Action:** Create PR targeting `PMOVES.AI-Edition-Hardened-Integrations`

**Command:**
```bash
make -C pmoves promote-to-integrations
```

**NATS Events Published:**
```json
{
  "subject": "github.promotion.requested.v1",
  "payload": {
    "action": "feature_to_integrations",
    "branch": "feat/new-feature",
    "pr_number": 123,
    "target": "PMOVES.AI-Edition-Hardened-Integrations",
    "timestamp": "2026-03-13T10:00:00Z"
  }
}
```

**Validation:** GitHub Actions workflow validates PR base branch

### Phase 2: Integrations → Hardened

**Action:** Create PR from `PMOVES.AI-Edition-Hardened-Integrations` to `PMOVES.AI-Edition-Hardened`

**Command:**
```bash
make -C pmoves promote-to-hardened
```

**NATS Events Published:**
```json
{
  "subject": "github.promotion.requested.v1",
  "payload": {
    "action": "integrations_to_hardened",
    "branch": "PMOVES.AI-Edition-Hardened-Integrations",
    "pr_number": 456,
    "target": "PMOVES.AI-Edition-Hardened",
    "timestamp": "2026-03-13T11:00:00Z"
  }
}
```

**Gates:** integration-gate + hardening-validation + CodeQL + CHIT + SQL Policy Lint

### Phase 3: Hardened → Main

**Action:** Create release PR from `PMOVES.AI-Edition-Hardened` to `main`

**Command:**
```bash
make -C pmoves promote-to-main
# Follow prompts for version and release notes
```

**NATS Events Published:**
```json
{
  "subject": "github.promotion.requested.v1",
  "payload": {
    "action": "hardened_to_main",
    "branch": "PMOVES.AI-Edition-Hardened",
    "pr_number": 789,
    "target": "main",
    "release_version": "v1.2.3",
    "timestamp": "2026-03-13T12:00:00Z"
  }
}
```

**Triggers Cross-Repo Sync:** Service detects `hardened_to_main` action and synchronizes submodules

## Workflow Integration

### GitHub Actions PR Validation

**File:** `.github/workflows/pr-base-validation.yml`

**NATS Integration:**
```yaml
- name: Publish PR Validation Event
  if: always()
  run: |
    nats pub "github.pr.validation.v1" "$(jq -n \
      --arg status "${{ job.status }}" \
      --arg base "${{ github.event.pull_request.base.ref }}" \
      --arg head "${{ github.event.pull_request.head.ref }}" \
      '{
        status: $status,
        base_ref: $base,
        head_ref: $head,
        pr_number: ($pr_number | tonumber),
        timestamp: now | todate
      }')"
```

### Branch Naming Validation

**Integration Point:** PR workflow calls branch naming service

```yaml
- name: Validate Branch Naming
  run: |
    response=$(curl -f "http://github-branch-naming:8102/api/validate?branch=${{ github.event.pull_request.head.ref }}")
    is_valid=$(echo $response | jq -r '.is_valid')

    if [ "$is_valid" != "true" ]; then
      echo "❌ Invalid branch name"
      echo $response | jq -r '.reason'
      exit 1
    fi
```

### Makefile Promotion Helpers

**File:** `pmoves/mk/promote.mk`

**NATS Publishing:**
```makefile
publish-nats-promotion:
	@nats pub "$(NATS_URL)" "github.promotion.requested.v1" \
		'{$(promote_payload)}'

promote-to-integrations: promote-check
	# ... create PR ...
	pr_number=$$(gh pr create --json number --jq '.number')
	$(MAKE) publish-nats-promotion \
		promote_payload='"action":"feature_to_integrations","branch":"$$(git branch --show-current)","pr_number":"'$$pr_number'"'
```

## Docker Compose Integration

**File:** `pmoves/docker-compose.yml`

**Add to services section:**
```yaml
services:
  # Existing services...

  github-branch-naming:
    build: ./services/github-branch-naming
    profiles:
      - github-automation
      - agents
    ports:
      - "8102:8102"
    environment:
      - NATS_URL=nats://nats:pmoves@nats:4222
      - DRY_RUN=true
    <<: *tier-agent-hardened-ro
    depends_on:
      nats:
        condition: service_healthy

  github-crossrepo-sync:
    build: ./services/github-crossrepo-sync
    profiles:
      - github-automation
      - agents
    ports:
      - "8103:8103"
    environment:
      - NATS_URL=nats://nats:pmoves@nats:4222
      - DRY_RUN=true
      - GITHUB_ORG=POWERFULMOVES
      - MAIN_REPO=PMOVES.AI
    <<: *tier-agent-hardened-ro
    depends_on:
      nats:
        condition: service_healthy
```

**Start services:**
```bash
docker compose --profile github-automation up -d
```

## NATS Subject Catalog

### Complete Subject List

**PR & Promotion:**
- `github.pr.validation.v1` - PR validation results
- `github.promotion.requested.v1` - Promotion PR created
- `github.promotion.completed.v1` - Promotion PR merged

**Branch Lifecycle:**
- `github.webhook.pr.v1` - PR webhook events (from n8n)
- `github.webhook.issue.v1` - Issue webhook events (from n8n)
- `github.branch.created.v1` - Branch created
- `github.branch.validation.v1` - Branch name validated
- `github.branch.rename_suggested.v1` - Branch rename suggested
- `github.branch.deleted.v1` - Branch deleted
- `github.branch.stale_detected.v1` - Stale branch detected
- `github.branch.auto_deleted.v1` - Branch auto-deleted after PR

**Cross-Repo Sync:**
- `github.crossrepo.sync.v1` - Sync operation started
- `github.crossrepo.sync.completed.v1` - Sync completed successfully
- `github.crossrepo.sync.failed.v1` - Sync operation failed

**Issue Triage:**
- `github.issue.triage.v1` - Issue triage completed
- `github.issue.labeled.v1` - Labels applied to issue

## Testing

### Manual Testing

**1. Test Branch Naming Validation:**
```bash
# Valid branch
curl "http://localhost:8102/api/validate?branch=feat/new-feature"

# Invalid branch
curl "http://localhost:8102/api/validate?branch=random-branch"
```

**2. Test NATS Events:**
```bash
# Subscribe to all GitHub events
nats sub "github.>" -csv

# Watch promotion flow
nats sub "github.promotion.>" -json
```

**3. Test Promotion Helpers:**
```bash
# Feature → Integrations
make -C pmoves promote-to-integrations

# Check NATS event
nats sub "github.promotion.requested.v1" -json
```

### Integration Testing

**1. Create Test PR:**
```bash
git checkout -b feat/test-integration
git commit --allow-empty -m "Test integration"
git push origin feat/test-integration
gh pr create --base PMOVES.AI-Edition-Hardened-Integrations --title "test: integration"
```

**2. Monitor Events:**
```bash
# Terminal 1: Watch NATS events
nats sub "github.>" -csv

# Terminal 2: Watch service logs
docker logs github-branch-naming -f
```

**3. Verify Validation:**
- Check PR validation workflow results
- Verify NATS event published to `github.pr.validation.v1`
- Confirm branch naming validation passed

## Troubleshooting

### Common Issues

**NATS connection failures:**
1. Check NATS is running: `docker ps | grep nats`
2. Verify NATS URL: `nats://nats:pmoves@nats:4222`
3. Test NATS connection: `nats server info`

**Branch naming not enforcing:**
1. Check service health: `curl http://localhost:8102/healthz`
2. Review service logs: `docker logs github-branch-naming`
3. Verify NATS subscription: `nats sub "github.branch.created.v1" -csv`

**Cross-repo sync not triggering:**
1. Check promotion events: `nats sub "github.promotion.completed.v1" -json`
2. Verify service health: `curl http://localhost:8103/healthz`
3. Review sync logs: `docker logs github-crossrepo-sync`

**PR validation not publishing:**
1. Check workflow logs in GitHub Actions
2. Verify NATS secrets are set in repository
3. Test NATS connection from workflow runner

## Monitoring

### Key Metrics

**Validation Success Rate:**
```promql
sum(github_pr_validation_total{status="success"}) / sum(github_pr_validation_total)
```

**Branch Naming Compliance:**
```promql
sum(github_branch_naming_validated_total{valid="true"}) / sum(github_branch_naming_validated_total)
```

**Cross-Repo Sync Success:**
```promql
sum(github_crossrepo_sync_completed_total{status="success"}) / sum(github_crossrepo_sync_completed_total)
```

### Grafana Dashboard

Import the dashboard from `pmoves/docs/GITHUB_PROMOTION_DASHBOARD.md` for comprehensive monitoring.

## Security Considerations

**GitHub App Permissions:**
- Repository administration (for branch operations)
- Pull request read/write
- Issue read/write
- Webhook management

**NATS Authentication:**
- All services use authenticated NATS connection
- Credentials stored in environment variables
- Never log or expose NATS credentials

**DRY_RUN Mode:**
- Services default to DRY_RUN=true
- Set DRY_RUN=false for production after testing
- Auto-branch deletion and renaming require explicit confirmation

## Future Enhancements

**Planned Features:**
1. Automatic branch renaming (not just suggestions)
2. Submodule PR auto-creation and merging
3. Promotion rollback capabilities
4. Multi-repository promotion orchestration
5. Slack/Discord notifications for promotions
6. Promotion approval workflow integration

**Contributing:**
See `pmoves/docs/BRANCH_STRATEGY.md` for contribution guidelines.
