# GitHub Automation Suite - User Guide

Comprehensive guide for using PMOVES.AI's GitHub automation services to automate repository maintenance and issue management.

## Overview

The GitHub Automation Suite provides two intelligent services:

1. **Branch Cleanup Service** (port 8100) - Automatically removes stale branches
2. **Issue Triage Service** (port 8101) - Intelligently categorizes and labels issues

Both services integrate with PMOVES.AI infrastructure via NATS for event-driven coordination and expose Prometheus metrics for observability.

## Table of Contents

- [Quick Start](#quick-start)
- [Branch Cleanup Service](#branch-cleanup-service)
- [Issue Triage Service](#issue-triage-service)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites

- PMOVES.AI infrastructure running (NATS, Prometheus, Grafana)
- GitHub App configured with appropriate permissions
- Agent Zero MCP service accessible
- (For Issue Triage) Hi-RAG v2 gateway running

### Start Services

```bash
# Start both GitHub automation services
docker compose --profile github-automation up -d

# Check service health
curl http://localhost:8100/healthz  # Branch Cleanup
curl http://localhost:8101/healthz  # Issue Triage

# View logs
docker compose logs -f github-branch-cleanup
docker compose logs -f github-issue-triage
```

### Verify Integration

```bash
# Check NATS connectivity
docker compose logs github-branch-cleanup | grep "Connected to NATS"
docker compose logs github-issue-triage | grep "Connected to NATS"

# View metrics
curl http://localhost:8100/metrics | grep github_branch
curl http://localhost:8101/metrics | grep github_issue
```

---

## Branch Cleanup Service

### Features

- **Automatic Stale Detection**: Identifies branches inactive for 30+ days (configurable)
- **Protected Branch Safeguards**: Never deletes protected branches (main, release-*, etc.)
- **Dry-Run Mode**: Safe testing without actual deletions (default: enabled)
- **Webhook Integration**: Auto-deletes source branches when PRs are closed/merged
- **GitHub App Authentication**: Secure token minting via Agent Zero MCP
- **NATS Events**: Publishes all operations for observability

### Safe Usage

**Default Mode (Dry-Run)**

The service starts in dry-run mode by default, which means it:
- Scans for stale branches
- Reports what would be deleted
- Does NOT actually delete branches
- Requires explicit `DRY_RUN=false` for production use

```bash
# Check what would be deleted
curl "http://localhost:8100/api/stale-branches?repo=PMOVES.AI&days=30"
```

**Enable Production Mode**

⚠️ **WARNING**: Production mode will permanently delete branches!

```bash
# Set environment variable
export DRY_RUN=false

# Or in docker-compose.yml
environment:
  - DRY_RUN=false

# Restart service
docker compose restart github-branch-cleanup
```

### API Endpoints

#### List Stale Branches

```bash
GET /api/stale-branches?repo=PMOVES.AI&days=30
```

**Response:**
```json
{
  "repo": "PMOVES.AI",
  "stale_branches": [
    {
      "name": "feature/old-feature",
      "last_commit_date": "2026-02-01T00:00:00Z",
      "stale_days": 40,
      "repo": "PMOVES.AI"
    }
  ],
  "total_stale": 1
}
```

#### Cleanup Stale Branches

```bash
POST /api/cleanup
Content-Type: application/json

{
  "repo": "PMOVES.AI",
  "dry_run": true,
  "stale_days": 30
}
```

**Response:**
```json
{
  "repo": "PMOVES.AI",
  "stale_branches": [...],
  "deleted_branches": ["feature/old-feature"],
  "protected_skipped": ["main", "release-v1.0"],
  "dry_run": true,
  "duration_seconds": 2.5
}
```

### Protected Branches

The following branches are NEVER deleted (configurable):

**Default Protected Patterns:**
- `main` - Main branch
- `PMOVES.AI-Edition-Hardened` - Hardened branch
- `release-*` - All release branches (wildcard pattern)
- `hotfix-*` - All hotfix branches (wildcard pattern)

**Configure Custom Protected Branches:**

```bash
# Via environment variable
export PROTECTED_BRANCHES="main,develop,release-*,staging-*"

# Or in docker-compose.yml
environment:
  - PROTECTED_BRANCHES=main,develop,release-*,staging-*
```

### Webhook Integration

The service subscribes to `github.webhook.pr.v1` on NATS to auto-delete source branches when PRs are closed/merged.

**Event Flow:**
```
PR closed/merged → n8n webhook → NATS: github.webhook.pr.v1
→ Branch Cleanup Service
→ Check if branch is protected
→ Delete branch (if not protected)
→ Publish: github.branch.auto_deleted.v1
```

**Supported Actions:**
- `closed` - PR closed without merging
- `merged` - PR merged to base branch

---

## Issue Triage Service

### Features

- **Semantic Search**: Uses Hi-RAG v2 to find similar historical issues
- **Pattern Matching**: Regex-based classification as fallback
- **Confidence Threshold**: Only applies labels above threshold (default: 0.7)
- **Multi-Label Support**: Can apply multiple labels per issue
- **Learning Capability**: Improves accuracy over time

### Classification Strategy

The service uses a two-stage classification process:

1. **Semantic Search (Primary)**
   - Queries Hi-RAG v2 for similar historical issues
   - Analyzes labels on similar issues
   - Calculates confidence based on label frequency

2. **Pattern Matching (Fallback)**
   - Uses regex patterns for issue title/body
   - Applies predefined classification rules
   - Used when Hi-RAG is unavailable or confidence is low

### Supported Labels

| Label | Description | Example Patterns |
|-------|-------------|------------------|
| `bug` | Defects, errors, crashes | "error", "crash", "broken", "doesn't work" |
| `feature` | New features, enhancements | "add", "implement", "support for" |
| `documentation` | Documentation issues | "docs", "readme", "guide", "tutorial" |
| `performance` | Performance issues | "slow", "latency", "optimize" |
| `security` | Security vulnerabilities | "exploit", "xss", "csrf", "injection" |
| `refactor` | Code quality issues | "refactor", "clean up", "technical debt" |

### API Endpoints

#### Manual Triage

```bash
POST /api/triage?repo=PMOVES.AI&issue_number=1234
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "repo": "PMOVES.AI",
    "issue_number": 1234,
    "labels": ["bug"],
    "confidence": 0.85,
    "method": "semantic",
    "reasoning": "Found 5 similar issues"
  }
}
```

#### Accuracy Metrics

```bash
GET /api/accuracy?repo=PMOVES.AI&days=30
```

**Note:** Accuracy calculation is not yet implemented (returns placeholder data).

### Webhook Integration

The service subscribes to `github.webhook.issue.v1` on NATS to automatically triage new and edited issues.

**Event Flow:**
```
Issue opened/edited → n8n webhook → NATS: github.webhook.issue.v1
→ Issue Triage Service
→ Classify issue (semantic + pattern)
→ Apply labels via BoTZ MCP
→ Publish: github.issue.labeled.v1
```

**Supported Actions:**
- `opened` - New issue created
- `edited` - Issue title/body modified

### Configuration

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LABEL_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for auto-labeling |
| `INDEX_HISTORICAL_ISSUES` | `true` | Index closed issues on startup |
| `HIRAG_URL` | `http://hi-rag-gateway-v2:8086` | Hi-RAG v2 gateway URL |
| `BOTZ_MCP_URL` | `http://botz-gateway:8102` | BoTZ MCP gateway URL |

**Adjust Confidence Threshold:**

```bash
# More conservative (fewer false positives)
export LABEL_CONFIDENCE_THRESHOLD=0.85

# More aggressive (catch more issues)
export LABEL_CONFIDENCE_THRESHOLD=0.6
```

---

## Configuration

### Environment Variables

**Common Variables (Both Services):**

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection URL |
| `SERVICE_PORT` | - | HTTP port (8100 or 8101) |
| `LOG_LEVEL` | `INFO` | Logging level |

**Branch Cleanup Service:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BRANCH_STALE_DAYS` | `30` | Days before branch is stale |
| `DRY_RUN` | `true` | Dry-run mode (no deletions) |
| `PROTECTED_BRANCHES` | `main,PMOVES.AI-Edition-Hardened,release-*` | Protected branch patterns |
| `GITHUB_ORG` | `POWERFULMOVES` | GitHub organization |
| `GH_APP_ID` | - | GitHub App ID (required) |
| `GH_APP_INSTALLATION_ID` | - | GitHub App Installation ID (required) |
| `AGENTZERO_MCP_URL` | `http://agent-zero:8080/mcp` | Agent Zero MCP endpoint |

**Issue Triage Service:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LABEL_CONFIDENCE_THRESHOLD` | `0.7` | Confidence threshold for labeling |
| `INDEX_HISTORICAL_ISSUES` | `true` | Index historical issues |
| `HIRAG_URL` | `http://hi-rag-gateway-v2:8086` | Hi-RAG v2 URL |
| `BOTZ_MCP_URL` | `http://botz-gateway:8102` | BoTZ MCP URL |

### Docker Compose Configuration

```yaml
services:
  github-branch-cleanup:
    profiles: ["agents", "github-automation"]
    environment:
      - SERVICE_PORT=8100
      - BRANCH_STALE_DAYS=30
      - DRY_RUN=true
      - PROTECTED_BRANCHES=main,PMOVES.AI-Edition-Hardened,release-*
    ports:
      - "8100:8100"

  github-issue-triage:
    profiles: ["agents", "github-automation"]
    environment:
      - SERVICE_PORT=8101
      - LABEL_CONFIDENCE_THRESHOLD=0.7
      - INDEX_HISTORICAL_ISSUES=true
    ports:
      - "8101:8101"
```

---

## Monitoring

### Prometheus Metrics

**Branch Cleanup Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `github_branch_cleanup_stale_total` | Counter | Total stale branches detected |
| `github_branch_cleanup_deleted_total` | Counter | Total branches deleted |
| `github_branch_cleanup_protected_skipped_total` | Counter | Total protected branches skipped |
| `github_branch_cleanup_duration_seconds` | Histogram | Operation duration |
| `github_branch_cleanup_active_operations` | Gauge | Number of active operations |

**Issue Triage Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `github_issue_triaged_total` | Counter | Total issues triaged |
| `github_issue_label_applied_total` | Counter | Total labels applied |
| `github_issue_triage_confidence_histogram` | Histogram | Confidence distribution |
| `github_issue_triage_error_total` | Counter | Total errors |
| `github_issue_hirag_query_duration_seconds` | Histogram | Hi-RAG query latency |

### Grafana Dashboards

**Available Dashboards:**
- GitHub Automation Overview
- Branch Cleanup Analytics
- Issue Triage Performance

**Query Examples:**

```promql
# Stale branch rate
rate(github_branch_cleanup_stale_total[5m])

# Deletion rate by repo
sum(rate(github_branch_cleanup_deleted_total[1h])) by (repo)

# Average triage confidence
avg(github_issue_triage_confidence_histogram) by (repo)

# Hi-RAG query latency
rate(github_issue_hirag_query_duration_seconds_sum[5m]) /
rate(github_issue_hirag_query_duration_seconds_count[5m])
```

### NATS Events

**Published Events:**

**Branch Cleanup:**
- `github.branch.stale_detected.v1` - Stale branches detected
- `github.branch.deleted.v1` - Cleanup operation completed
- `github.branch.auto_deleted.v1` - Branch auto-deleted after PR close

**Issue Triage:**
- `github.issue.triage.v1` - Triage operation completed
- `github.issue.labeled.v1` - Labels applied to issue

**Subscribed Events:**
- `github.webhook.pr.v1` - PR close/merge events
- `github.webhook.issue.v1` - Issue opened/edited events

### Log Aggregation

All service logs are sent to Loki for centralized logging:

```bash
# View logs in Loki
http://localhost:3100

# Query example
{service="github-branch-cleanup"} |= "error"
{service="github-issue-triage"} |= "triaged"
```

---

## Troubleshooting

### Branch Cleanup Service

#### Service Not Starting

**Symptoms:** Container exits immediately or fails health check

**Solutions:**
```bash
# Check logs
docker compose logs github-branch-cleanup

# Verify environment variables
docker compose exec github-branch-cleanup env | grep GITHUB

# Test health endpoint
curl http://localhost:8100/healthz
```

**Common Causes:**
- Missing `GH_APP_ID` or `GH_APP_INSTALLATION_ID`
- Invalid `GITHUB_ORG` name
- NATS connection failure

#### Branches Not Being Deleted

**Symptoms:** Dry-run shows branches but production mode doesn't delete

**Checklist:**
1. Verify `DRY_RUN` is set to `false`
2. Check GitHub App credentials are valid
3. Verify branch is not in protected list
4. Check staleness threshold (`BRANCH_STALE_DAYS`)
5. Review service logs for errors

```bash
# Check dry-run status
docker compose exec github-branch-cleanup env | grep DRY_RUN

# View protected branches
docker compose exec github-branch-cleanup env | grep PROTECTED

# Check logs for errors
docker compose logs github-branch-cleanup | grep -i error
```

#### NATS Connection Issues

**Symptoms:** "Failed to connect to NATS" in logs

**Solutions:**
```bash
# Verify NATS is healthy
curl http://localhost:8222/varz

# Check NATS credentials
echo $NATS_URL  # Should be: nats://nats:pmoves@nats:4222

# Test NATS from container
docker compose exec github-branch-cleanup \
  nc -zv nats 4222
```

### Issue Triage Service

#### Low Accuracy

**Symptoms:** Incorrect labels or low confidence scores

**Solutions:**
```bash
# Check confidence threshold
docker compose exec github-issue-triage env | grep CONFIDENCE

# Verify Hi-RAG is healthy
curl http://localhost:8086/healthz

# Test Hi-RAG query
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "bug report", "top_k": 5, "rerank": true}'
```

**Adjustments:**
- Lower `LABEL_CONFIDENCE_THRESHOLD` for more aggressive labeling
- Ensure Hi-RAG has indexed historical issues
- Check labeling rules in `labeling_rules.py`

#### Labels Not Being Applied

**Symptoms:** Triage succeeds but labels don't appear on GitHub

**Solutions:**
```bash
# Check BoTZ Gateway connectivity
curl http://localhost:8102/healthz

# Verify MCP endpoint
curl http://localhost:8102/mcp/github/add_labels \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"repo": "PMOVES.AI", "issue_number": 1, "labels": ["test"]}'

# Check logs for MCP errors
docker compose logs github-issue-triage | grep -i mcp
```

#### Hi-RAG Connection Failures

**Symptoms:** "Hi-RAG query failed, falling back to patterns" in logs

**Solutions:**
```bash
# Verify Hi-RAG is running
docker compose ps | grep hirag

# Check Hi-RAG health
curl http://localhost:8086/healthz

# Test Hi-RAG directly
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

---

## Best Practices

### Branch Cleanup

1. **Start with Dry-Run**: Always test with `DRY_RUN=true` before enabling production mode
2. **Conservative Staleness Threshold**: Use 30+ days to avoid deleting active work
3. **Protect Important Branches**: Add custom patterns for release, staging, etc.
4. **Monitor Deletions**: Set up Grafana alerts for unexpected deletion spikes
5. **Audit Trail**: Review NATS events for all deletions

### Issue Triage

1. **Tune Confidence Threshold**: Start with 0.7, adjust based on accuracy
2. **Monitor Performance**: Track Hi-RAG query latency
3. **Review False Positives**: Regularly review incorrect labels
4. **Index Historical Issues**: Enable `INDEX_HISTORICAL_ISSUES` for better accuracy
5. **Fallback to Patterns**: Ensure pattern-based rules work when Hi-RAG is down

### Security

1. **GitHub App Permissions**: Grant minimum required permissions
2. **Service-to-Service Auth**: Use JWT authentication for MCP calls
3. **Secrets Management**: Never commit credentials, use environment variables
4. **Audit Logging**: Enable NATS event publishing for all operations
5. **Rate Limiting**: Monitor GitHub API rate limits

### Observability

1. **Metrics Dashboards**: Create Grafana dashboards for key metrics
2. **Alert Rules**: Set up alerts for error rates and latency spikes
3. **Log Aggregation**: Use Loki for centralized log analysis
4. **NATS Monitoring**: Monitor NATS subject throughput and latency
5. **Health Checks**: Monitor `/healthz` endpoints for service availability

---

## Advanced Topics

### Custom Labeling Rules

Edit `pmoves/services/github-issue-triage/labeling_rules.py` to add custom patterns:

```python
LABEL_PATTERNS = {
    "bug": [
        r"\berror\b",
        r"\bcrash\b",
        r"\bbroken\b",
        # Add custom patterns
    ],
    "feature": [
        r"\badd\b",
        r"\bimplement\b",
        # Add custom patterns
    ],
    # Add custom labels
    "critical": [
        r"\burgent\b",
        r"\bcritical\b",
        r"\bblocker\b",
    ],
}
```

### Scheduled Cleanup

Add a cron job to trigger automatic cleanup:

```yaml
# docker-compose.yml
services:
  github-branch-cleanup-scheduler:
    image: alpine:latest
    command: >
      sh -c '
        while true; do
          sleep 86400
          curl -X POST http://github-branch-cleanup:8100/api/cleanup \
            -H "Content-Type: application/json" \
            -d "{\"repo\": \"PMOVES.AI\", \"dry_run\": false, \"stale_days\": 30}"
        done
      '
```

### Multi-Repository Support

Configure the service to handle multiple repositories:

```python
# In app.py
REPOS_TO_MONITOR = os.getenv(
    "REPOS_TO_MONITOR",
    "PMOVES.AI,PMOVES-Agent-Zero,PMOVES-Archon"
).split(",")

# Cleanup all repos
for repo in REPOS_TO_MONITOR:
    await cleanup_stale_branches(repo)
```

---

## Additional Resources

- **API Reference**: See `GITHUB_AUTOMATION_API.md`
- **NATS Events**: See `GITHUB_AUTOMATION_NATS.md`
- **Service READMEs**:
  - `pmoves/services/github-branch-cleanup/README.md`
  - `pmoves/services/github-issue-triage/README.md`
- **PMOVES.AI Documentation**: See `.claude/CLAUDE.md`

---

## Support

For issues or questions:
1. Check service logs: `docker compose logs -f <service>`
2. Review troubleshooting section above
3. Consult PMOVES.AI documentation
4. Open an issue on GitHub repository

---

**Last Updated:** 2026-03-13
**Version:** 1.0.0
