# GitHub Promotion Dashboard

This document provides Grafana dashboard queries and monitoring guidance for the PMOVES.AI GitHub automation and branch strategy integration.

## Dashboard Overview

The GitHub Promotion Dashboard provides real-time visibility into:
- PR validation events
- Branch promotion flow
- Branch naming compliance
- Cross-repo synchronization
- NATS event throughput

## Grafana Dashboard JSON

Import this JSON into Grafana to create the promotion monitoring dashboard:

```json
{
  "dashboard": {
    "title": "GitHub Promotion & Branch Strategy",
    "tags": ["github", "promotion", "branch-strategy"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "PR Validation Status",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 8, "h": 4},
        "targets": [
          {
            "expr": "github_pr_validation_total",
            "legendFormat": "{{status}}"
          }
        ]
      },
      {
        "id": 2,
        "title": "Promotion Events (Last 24h)",
        "type": "graph",
        "gridPos": {"x": 8, "y": 0, "w": 16, "h": 4},
        "targets": [
          {
            "expr": "rate(github_promotion_requested_total[5m])",
            "legendFormat": "Requested - {{action}}"
          },
          {
            "expr": "rate(github_promotion_completed_total[5m])",
            "legendFormat": "Completed - {{action}}"
          }
        ]
      },
      {
        "id": 3,
        "title": "Branch Naming Compliance",
        "type": "piechart",
        "gridPos": {"x": 0, "y": 4, "w": 12, "h": 6},
        "targets": [
          {
            "expr": "sum(github_branch_naming_validated_total{valid=\"true\"}) by (category)",
            "legendFormat": "{{category}}"
          },
          {
            "expr": "sum(github_branch_naming_validated_total{valid=\"false\"})",
            "legendFormat": "Invalid"
          }
        ]
      },
      {
        "id": 4,
        "title": "Cross-Repo Sync Status",
        "type": "stat",
        "gridPos": {"x": 12, "y": 4, "w": 12, "h": 6},
        "targets": [
          {
            "expr": "github_crossrepo_sync_active_operations",
            "legendFormat": "Active Syncs"
          },
          {
            "expr": "rate(github_crossrepo_sync_completed_total[5m])",
            "legendFormat": "Sync Rate ({{status}})"
          }
        ]
      },
      {
        "id": 5,
        "title": "Branch Cleanup Activity",
        "type": "graph",
        "gridPos": {"x": 0, "y": 10, "w": 24, "h": 6},
        "targets": [
          {
            "expr": "rate(github_branch_cleanup_stale_total[5m])",
            "legendFormat": "Stale Detected - {{repo}}"
          },
          {
            "expr": "rate(github_branch_cleanup_deleted_total[5m])",
            "legendFormat": "Deleted - {{repo}}"
          }
        ]
      },
      {
        "id": 6,
        "title": "Issue Triage Confidence",
        "type": "heatmap",
        "gridPos": {"x": 0, "y": 16, "w": 12, "h": 6},
        "targets": [
          {
            "expr": "github_issue_triage_confidence_histogram",
            "legendFormat": "{{repo}}"
          }
        ]
      },
      {
        "id": 7,
        "title": "NATS Event Throughput",
        "type": "graph",
        "gridPos": {"x": 12, "y": 16, "w": 12, "h": 6},
        "targets": [
          {
            "expr": "rate(nats_msgs_in[5m])",
            "legendFormat": "{{subject}}"
          }
        ]
      }
    ],
    "refresh": "30s",
    "schemaVersion": 36,
    "version": 1
  }
}
```

## Prometheus Queries

### PR Validation Events

**Count validations by status:**
```promql
sum by (status) (github_pr_validation_total)
```

**Validation success rate:**
```promql
sum(github_pr_validation_total{status="success"}) / sum(github_pr_validation_total)
```

**Validations per hour:**
```promql
rate(github_pr_validation_total[1h])
```

### Promotion Flow

**Promotion requests by action:**
```promql
sum by (action) (github_promotion_requested_total)
```

**Promotion completion rate:**
```promql
sum by (action) (rate(github_promotion_completed_total[5m]))
```

**Average promotion duration:**
```promql
avg(github_promotion_duration_seconds) by (action)
```

**Pending promotions (requested but not completed):**
```promql
github_promotion_requested_total - github_promotion_completed_total
```

### Branch Naming

**Branch naming compliance rate:**
```promql
sum(github_branch_naming_validated_total{valid="true"}) / sum(github_branch_naming_validated_total)
```

**Invalid branches by type:**
```promql
sum by (suggested_rename) (github_branch_naming_failed_total)
```

**Rename suggestion rate:**
```promql
rate(github_branch_naming_rename_suggested_total[5m])
```

### Cross-Repo Sync

**Active sync operations:**
```promql
github_crossrepo_sync_active_operations
```

**Sync success rate:**
```promql
sum(github_crossrepo_sync_completed_total{status="success"}) / sum(github_crossrepo_sync_completed_total)
```

**Average sync duration:**
```promql
avg(github_crossrepo_sync_duration_seconds{status="success"})
```

**Failed syncs by error type:**
```promql
sum by (error_type) (github_crossrepo_sync_failed_total)
```

### Branch Cleanup

**Stale branches detected:**
```promql
sum by (repo) (github_branch_cleanup_stale_total)
```

**Branches deleted:**
```promql
sum by (repo) (github_branch_cleanup_deleted_total)
```

**Cleanup operation duration:**
```promql
avg(github_branch_cleanup_duration_seconds) by (repo, status)
```

### Issue Triage

**Triage accuracy (confidence > 0.7):**
```promql
sum(github_issue_triaged_total) / sum(github_issue_triaged_total)
```

**Labels applied by type:**
```promql
sum by (label) (github_issue_label_applied_total)
```

**Average triage confidence:**
```promql
avg(github_issue_triage_confidence_histogram)
```

**Triage error rate:**
```promql
sum(github_issue_triage_error_total) / sum(github_issue_triaged_total)
```

## NATS Subject Monitoring

### Key Subjects to Monitor

**PR & Promotion Events:**
- `github.pr.validation.v1` - PR validation results
- `github.promotion.requested.v1` - Promotion PR creation
- `github.promotion.completed.v1` - Promotion PR merge

**Branch Lifecycle Events:**
- `github.branch.created.v1` - New branch creation
- `github.branch.validation.v1` - Branch name validation
- `github.branch.deleted.v1` - Branch deletion
- `github.branch.stale_detected.v1` - Stale branch detection

**Cross-Repo Events:**
- `github.crossrepo.sync.v1` - Sync operation started
- `github.crossrepo.sync.completed.v1` - Sync completed
- `github.crossrepo.sync.failed.v1` - Sync failed

**Issue Events:**
- `github.issue.triage.v1` - Issue triage completed
- `github.issue.labeled.v1` - Labels applied

### Monitoring Commands

**Subscribe to all GitHub automation events:**
```bash
nats sub "github.>" -csv
```

**Watch promotion flow:**
```bash
nats sub "github.promotion.>" -csv
```

**Monitor branch validation:**
```bash
nats sub "github.branch.validation.v1" -json
```

**Track cross-repo sync:**
```bash
nats sub "github.crossrepo.>" -csv
```

## Alerting Rules

### Critical Alerts

**High validation failure rate:**
```yaml
- alert: GitHubValidationFailureRateHigh
  expr: |
    sum(rate(github_pr_validation_total{status="failure"}[5m])) /
    sum(rate(github_pr_validation_total[5m])) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "GitHub PR validation failure rate > 10%"
    description: "{{ $value | humanizePercentage }} of PR validations failing"
```

**Sync operations failing:**
```yaml
- alert: GitHubCrossRepoSyncFailing
  expr: |
    sum(rate(github_crossrepo_sync_failed_total[5m])) > 0
  for: 15m
  labels:
    severity: critical
  annotations:
    summary: "Cross-repo sync operations failing"
    description: "{{ $value }} sync failures per second"
```

**Stale branch backlog:**
```yaml
- alert: GitHubStaleBranchBacklog
  expr: |
    sum(github_branch_cleanup_stale_total) - sum(github_branch_cleanup_deleted_total) > 100
  for: 1h
  labels:
    severity: info
  annotations:
    summary: "Large backlog of stale branches"
    description: "{{ $value }} stale branches awaiting cleanup"
```

### Warning Alerts

**Branch naming compliance low:**
```yaml
- alert: GitHubBranchNamingComplianceLow
  expr: |
    sum(github_branch_naming_validated_total{valid="true"}) /
    sum(github_branch_naming_validated_total) < 0.9
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Branch naming compliance < 90%"
    description: "{{ $value | humanizePercentage }} compliance rate"
```

**Issue triage confidence low:**
```yaml
- alert: GitHubIssueTriageConfidenceLow
  expr: |
    avg(github_issue_triage_confidence_histogram) < 0.7
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Issue triage confidence < 70%"
    description: "Average confidence: {{ $value | humanizePercentage }}"
```

## Troubleshooting

### Common Issues

**No events appearing in dashboard:**
1. Check NATS connection: `curl http://localhost:8102/healthz`
2. Verify NATS subscriptions: `nats sub ">" -csv`
3. Check Prometheus targets: http://localhost:9090/targets

**High validation failure rate:**
1. Check validation logs: `docker logs github-branch-naming`
2. Review PR patterns: check recent PRs for violations
3. Verify NATS event payloads: `nats sub "github.pr.validation.v1" -json`

**Cross-repo sync stuck:**
1. Check active operations: `github_crossrepo_sync_active_operations`
2. Review sync logs: `docker logs github-crossrepo-sync`
3. Verify GitHub token permissions

**Branch cleanup not running:**
1. Check service health: `curl http://localhost:8100/healthz`
2. Verify NATS connection: check logs for "NATS not connected"
3. Review DRY_RUN setting (should be false for production)

### Log Locations

**Service logs:**
```bash
# Branch Cleanup
docker logs github-branch-cleanup -f

# Issue Triage
docker logs github-issue-triage -f

# Branch Naming
docker logs github-branch-naming -f

# Cross-Repo Sync
docker logs github-crossrepo-sync -f
```

**NATS logs:**
```bash
docker logs nats -f
```

## Performance Tuning

### High-Volume Repositories

For repositories with high PR/branch turnover:

1. **Increase NATS subscriber queue:**
   ```yaml
   queue: "github-automation-workers"
   ```

2. **Adjust scrape intervals:**
   ```yaml
   scrape_interval: 15s  # Prometheus
   ```

3. **Enable metrics caching:**
   ```python
   CACHE_TTL = 30  # seconds
   ```

### Resource Allocation

**Recommended service limits:**
```yaml
github-branch-naming:
  memory: "256Mi"
  cpu: "200m"

github-crossrepo-sync:
  memory: "512Mi"
  cpu: "500m"

github-branch-cleanup:
  memory: "256Mi"
  cpu: "200m"
```

## Maintenance

### Daily Checks

- Review validation failure rate
- Check sync operation status
- Verify stale branch backlog

### Weekly Tasks

- Review false positive triage labels
- Update branch naming patterns
- Audit cross-repo sync failures

### Monthly Tasks

- Review and update alert thresholds
- Audit NATS subject usage
- Review dashboard panel relevance
