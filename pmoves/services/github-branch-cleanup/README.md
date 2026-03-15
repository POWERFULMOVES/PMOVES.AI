# GitHub Branch Cleanup Service

Automatically removes stale branches from POWERFULMOVES repositories to reduce repository clutter and improve branch management hygiene.

## Overview

The Branch Cleanup Service monitors GitHub repositories for inactive branches and safely removes them after a configurable staleness period (default: 30 days). It integrates with PMOVES.AI infrastructure via NATS for event-driven coordination and exposes Prometheus metrics for observability.

## Features

- **Automatic Stale Detection**: Identifies branches inactive for 30+ days (configurable)
- **Protected Branch Safeguards**: Never deletes main, release branches, or custom protected patterns
- **Dry-Run Mode**: Safe testing without actual deletions (default: enabled)
- **Webhook Integration**: Auto-deletes source branches when PRs are closed/merged
- **GitHub App Auth**: Secure token minting via Agent Zero MCP
- **NATS Events**: Publishes all operations for Grafana dashboard correlation
- **Prometheus Metrics**: Tracks stale branches, deletions, and operation duration

## Architecture

```
GitHub Webhook → n8n → NATS: github.webhook.pr.v1
    → github-branch-cleanup (port 8100)
    → Agent Zero MCP (token minting)
    → GitHub API (branch operations)
    → NATS: github.branch.deleted.v1
```

## API Endpoints

### Health Check
```bash
GET /healthz
```

### List Stale Branches
```bash
GET /api/stale-branches?repo=PMOVES.AI&days=30
```

Response:
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

### Cleanup Stale Branches
```bash
POST /api/cleanup
Content-Type: application/json

{
  "repo": "PMOVES.AI",
  "dry_run": true,
  "stale_days": 30
}
```

Response:
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

### Prometheus Metrics
```bash
GET /metrics
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS connection URL |
| `SERVICE_PORT` | `8100` | HTTP port for API |
| `BRANCH_STALE_DAYS` | `30` | Days before branch is considered stale |
| `DRY_RUN` | `true` | Enable dry-run mode (no actual deletions) |
| `PROTECTED_BRANCHES` | `main,PMOVES.AI-Edition-Hardened,release-*` | Comma-separated branch patterns to protect |
| `GITHUB_ORG` | `POWERFULMOVES` | GitHub organization name |
| `GH_APP_ID` | - | GitHub App ID (required) |
| `GH_APP_INSTALLATION_ID` | - | GitHub App Installation ID (required) |
| `AGENTZERO_MCP_URL` | `http://agent-zero:8080/mcp` | Agent Zero MCP endpoint |

### Protected Branch Patterns

Protected branches use two matching strategies:

1. **Exact Match**: `main`, `PMOVES.AI-Edition-Hardened`
2. **Wildcard Match**: `release-*`, `hotfix-*` (matches `release-v1.0`, `hotfix-123`)

## Deployment

### Docker Compose

```bash
# Start service
docker compose --profile agents up -d github-branch-cleanup

# View logs
docker compose logs -f github-branch-cleanup

# Stop service
docker compose stop github-branch-cleanup
```

### Enable Production Mode

To enable actual branch deletions (disable dry-run):

```bash
# Set environment variable
export DRY_RUN=false

# Or in docker-compose.yml
environment:
  - DRY_RUN=false
```

## NATS Events

### Published Events

- **`github.branch.stale_detected.v1`**: Emitted when stale branches detected
- **`github.branch.deleted.v1`**: Emitted after cleanup operation completes
- **`github.branch.auto_deleted.v1`**: Emitted when branch auto-deleted after PR close

### Subscribed Events

- **`github.webhook.pr.v1`**: Listens for PR close/merge events to auto-delete source branches

## Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|-------|-------------|
| `github_branch_cleanup_stale_total` | Counter | `repo` | Total stale branches detected |
| `github_branch_cleanup_deleted_total` | Counter | `repo` | Total branches deleted |
| `github_branch_cleanup_protected_skipped_total` | Counter | `repo` | Total protected branches skipped |
| `github_branch_cleanup_duration_seconds` | Histogram | `repo`, `status` | Operation duration |
| `github_branch_cleanup_active_operations` | Gauge | - | Number of active cleanup operations |

### Query Examples

```promql
# Stale branch rate
rate(github_branch_cleanup_stale_total[5m])

# Deletion rate by repo
sum(rate(github_branch_cleanup_deleted_total[1h])) by (repo)

# Average cleanup duration
rate(github_branch_cleanup_duration_seconds_sum[5m]) / rate(github_branch_cleanup_duration_seconds_count[5m])

# Active operations
github_branch_cleanup_active_operations
```

## Testing

### Unit Tests
```bash
pytest pmoves/tests/test_branch_cleanup.py -v
```

### Integration Tests
```bash
# List stale branches (dry-run)
curl http://localhost:8100/api/stale-branches?repo=PMOVES.AI&days=30

# Run cleanup (dry-run)
curl -X POST http://localhost:8100/api/cleanup \
  -H "Content-Type: application/json" \
  -d '{"repo": "PMOVES.AI", "dry_run": true, "stale_days": 30}'

# Run cleanup (production - requires DRY_RUN=false)
curl -X POST http://localhost:8100/api/cleanup \
  -H "Content-Type: application/json" \
  -d '{"repo": "PMOVES.AI", "dry_run": false, "stale_days": 30}'
```

## Safety Features

### Protected Branches
The following branches are NEVER deleted (configurable via `PROTECTED_BRANCHES`):
- `main`
- `PMOVES.AI-Edition-Hardened`
- `release-*` (all release branches)
- Custom patterns via environment variable

### Dry-Run Mode
By default, the service operates in dry-run mode (`DRY_RUN=true`):
- Scans for stale branches
- Reports what would be deleted
- Does NOT actually delete branches
- Requires explicit `DRY_RUN=false` for production use

### Audit Trail
All operations are logged and published to NATS:
- Branch deletions
- Protected branch skips
- Operation duration
- Dry-run status

## Troubleshooting

### Service Not Starting
```bash
# Check logs
docker compose logs github-branch-cleanup

# Verify environment variables
docker compose exec github-branch-cleanup env | grep GITHUB

# Test health endpoint
curl http://localhost:8100/healthz
```

### Branches Not Being Deleted
1. Verify `DRY_RUN` is set to `false`
2. Check GitHub App credentials (`GH_APP_ID`, `GH_APP_INSTALLATION_ID`)
3. Verify branch is not in protected list
4. Check staleness threshold (`BRANCH_STALE_DAYS`)

### NATS Connection Issues
```bash
# Verify NATS is healthy
curl http://localhost:8222/varz

# Check NATS credentials
echo $NATS_URL  # Should include credentials: nats://nats:pmoves@nats:4222
```

## Integration with Other Services

### Agent Zero MCP
The service uses Agent Zero's MCP endpoint to mint GitHub App installation tokens:
- Endpoint: `http://agent-zero:8080/mcp`
- Tool: `github_mint_token`
- Token Expiry: 1 hour (auto-rotated)

### Grafana Dashboard
Metrics are available in Grafana:
- Dashboard: GitHub Automation Overview
- Datasource: Prometheus
- Panels: Stale branches, deletion rate, operation duration

## Future Enhancements

- [ ] Scheduled automatic cleanup (cron-triggered)
- [ ] Branch naming policy enforcement
- [ ] Integration with repository-specific rules
- [ ] Slack/Discord notifications for deletions
- [ ] Branch lifecycle analytics
