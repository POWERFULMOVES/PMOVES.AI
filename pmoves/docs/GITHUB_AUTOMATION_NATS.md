# GitHub Automation NATS Event Catalog

Complete reference for all NATS events published and consumed by PMOVES.AI's GitHub automation services.

## Table of Contents

- [Overview](#overview)
- [Incoming Events](#incoming-events)
- [Outgoing Events](#outgoing-events)
- [Event Schemas](#event-schemas)
- [Integration Patterns](#integration-patterns)
- [Monitoring](#monitoring)

---

## Overview

The GitHub Automation Suite uses NATS for event-driven communication between services, webhooks, and observability tools.

### NATS Configuration

- **Server:** `nats://nats:pmoves@nats:4222`
- **Authentication:** Username/Password (nats/pmoves)
- **JetStream:** Enabled for persistence
- **Monitoring:** http://localhost:8222/varz

### Subject Naming Convention

GitHub automation subjects follow PMOVES.AI convention:
```
<category>.<service>.<event>.<version>
```

Examples:
- `github.branch.stale_detected.v1`
- `github.issue.labeled.v1`
- `github.webhook.pr.v1`

---

## Incoming Events

Events consumed by GitHub automation services from NATS.

### github.webhook.pr.v1

**Consumed by:** Branch Cleanup Service (port 8100)

**Purpose:** Trigger auto-deletion of source branches when PRs are closed/merged

**Source:** n8n webhook → NATS

**Payload Schema:**
```json
{
  "action": "closed | merged",
  "repository": {
    "name": "string",
    "full_name": "string",
    "private": boolean,
    "owner": {
      "login": "string"
    }
  },
  "pull_request": {
    "number": integer,
    "state": "string",
    "title": "string",
    "body": "string",
    "head": {
      "ref": "string",
      "sha": "string",
      "repo": {
        "name": "string"
      }
    },
    "base": {
      "ref": "string",
      "sha": "string",
      "repo": {
        "name": "string"
      }
    },
    "merged": boolean,
    "merged_at": "string (ISO 8601)",
    "closed_at": "string (ISO 8601)"
  },
  "sender": {
    "login": "string",
    "type": "string"
  }
}
```

**Example Payload:**
```json
{
  "action": "closed",
  "repository": {
    "name": "PMOVES.AI",
    "full_name": "POWERFULMOVES/PMOVES.AI",
    "private": false,
    "owner": {
      "login": "POWERFULMOVES"
    }
  },
  "pull_request": {
    "number": 1234,
    "state": "closed",
    "title": "Add new feature",
    "body": "This PR adds...",
    "head": {
      "ref": "feature/new-feature",
      "sha": "abc123def456",
      "repo": {
        "name": "PMOVES.AI"
      }
    },
    "base": {
      "ref": "main",
      "sha": "789ghi012jkl",
      "repo": {
        "name": "PMOVES.AI"
      }
    },
    "merged": false,
    "merged_at": null,
    "closed_at": "2026-03-13T12:00:00Z"
  },
  "sender": {
    "login": "contributor",
    "type": "User"
  }
}
```

**Processing Logic:**
1. Check if action is `closed` or `merged`
2. Extract source branch name from `pull_request.head.ref`
3. Check if branch is protected (main, release-*, etc.)
4. If not protected and `DRY_RUN=false`, delete branch
5. Publish `github.branch.auto_deleted.v1` event

**Response Events:**
- `github.branch.auto_deleted.v1` - On successful deletion

---

### github.webhook.issue.v1

**Consumed by:** Issue Triage Service (port 8101)

**Purpose:** Trigger automatic issue classification and labeling

**Source:** n8n webhook → NATS

**Payload Schema:**
```json
{
  "action": "opened | edited",
  "issue": {
    "number": integer,
    "title": "string",
    "body": "string | null",
    "state": "open | closed",
    "labels": [
      {
        "name": "string",
        "color": "string"
      }
    ],
    "repository": {
      "name": "string",
      "full_name": "string",
      "private": boolean
    },
    "user": {
      "login": "string"
    },
    "created_at": "string (ISO 8601)",
    "updated_at": "string (ISO 8601)"
  },
  "repository": {
    "name": "string",
    "full_name": "string"
  },
  "sender": {
    "login": "string"
  }
}
```

**Example Payload:**
```json
{
  "action": "opened",
  "issue": {
    "number": 5678,
    "title": "Bug: Feature X crashes on startup",
    "body": "When I start feature X, it crashes with error...",
    "state": "open",
    "labels": [],
    "repository": {
      "name": "PMOVES.AI",
      "full_name": "POWERFULMOVES/PMOVES.AI",
      "private": false
    },
    "user": {
      "login": "reporter"
    },
    "created_at": "2026-03-13T12:00:00Z",
    "updated_at": "2026-03-13T12:00:00Z"
  },
  "repository": {
    "name": "PMOVES.AI",
    "full_name": "POWERFULMOVES/PMOVES.AI"
  },
  "sender": {
    "login": "reporter"
  }
}
```

**Processing Logic:**
1. Check if action is `opened` or `edited`
2. Extract issue text (title + body)
3. Query Hi-RAG v2 for similar issues (semantic search)
4. Apply pattern-based classification as fallback
5. Apply labels if confidence ≥ threshold (default: 0.7)
6. Publish `github.issue.labeled.v1` event

**Response Events:**
- `github.issue.triage.v1` - Triage operation completed
- `github.issue.labeled.v1` - Labels applied successfully

---

## Outgoing Events

Events published by GitHub automation services to NATS.

### github.branch.stale_detected.v1

**Published by:** Branch Cleanup Service (port 8100)

**Purpose:** Notify when stale branches are detected

**Payload Schema:**
```json
{
  "repo": "string",
  "stale_count": integer,
  "stale_days": integer,
  "timestamp": "string (ISO 8601)"
}
```

**Example Payload:**
```json
{
  "repo": "PMOVES.AI",
  "stale_count": 5,
  "stale_days": 30,
  "timestamp": "2026-03-13T12:00:00Z"
}
```

**Consumed by:**
- Grafana dashboards (alerting)
- Log aggregators (Loki)
- Custom monitoring services

---

### github.branch.deleted.v1

**Published by:** Branch Cleanup Service (port 8100)

**Purpose:** Notify when branches are deleted (manual or auto)

**Payload Schema:**
```json
{
  "repo": "string",
  "deleted_count": integer,
  "dry_run": boolean,
  "duration_seconds": float,
  "deleted_branches": ["string"],
  "protected_skipped": ["string"],
  "timestamp": "string (ISO 8601)"
}
```

**Example Payload:**
```json
{
  "repo": "PMOVES.AI",
  "deleted_count": 3,
  "dry_run": false,
  "duration_seconds": 2.5,
  "deleted_branches": [
    "feature/old-feature-1",
    "feature/old-feature-2",
    "fix/obsolete-bug"
  ],
  "protected_skipped": ["main", "release-v1.0"],
  "timestamp": "2026-03-13T12:00:00Z"
}
```

**Consumed by:**
- Grafana dashboards
- Audit loggers
- Compliance tools

---

### github.branch.auto_deleted.v1

**Published by:** Branch Cleanup Service (port 8100)

**Purpose:** Notify when branch is auto-deleted after PR close/merge

**Payload Schema:**
```json
{
  "repo": "string",
  "branch": "string",
  "trigger": "pr_closed | pr_merged",
  "dry_run": boolean,
  "timestamp": "string (ISO 8601)"
}
```

**Example Payload:**
```json
{
  "repo": "PMOVES.AI",
  "branch": "feature/completed-feature",
  "trigger": "pr_merged",
  "dry_run": false,
  "timestamp": "2026-03-13T12:00:00Z"
}
```

**Consumed by:**
- Grafana dashboards
- PR workflow monitors
- Repository hygiene tools

---

### github.issue.triage.v1

**Published by:** Issue Triage Service (port 8101)

**Purpose:** Notify when issue triage operation completes

**Payload Schema:**
```json
{
  "repo": "string",
  "issue_number": integer,
  "labels": ["string"],
  "confidence": float,
  "method": "semantic | pattern",
  "reasoning": "string",
  "timestamp": "string (ISO 8601)"
}
```

**Example Payload:**
```json
{
  "repo": "PMOVES.AI",
  "issue_number": 5678,
  "labels": ["bug"],
  "confidence": 0.85,
  "method": "semantic",
  "reasoning": "Found 5 similar issues with label 'bug'",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

**Consumed by:**
- Grafana dashboards
- Accuracy calculators
- ML training pipelines

---

### github.issue.labeled.v1

**Published by:** Issue Triage Service (port 8101)

**Purpose:** Notify when labels are successfully applied to an issue

**Payload Schema:**
```json
{
  "repo": "string",
  "issue_number": integer,
  "labels": ["string"],
  "confidence": float,
  "method": "semantic | pattern",
  "timestamp": "string (ISO 8601)"
}
```

**Example Payload:**
```json
{
  "repo": "PMOVES.AI",
  "issue_number": 5678,
  "labels": ["bug", "high-priority"],
  "confidence": 0.85,
  "method": "semantic",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

**Consumed by:**
- Grafana dashboards
- Notification services (Slack, Discord)
- Analytics services

---

## Event Schemas

### Common Fields

All GitHub automation events include these common fields:

```json
{
  "repo": "string",           // Repository name
  "timestamp": "string",      // ISO 8601 timestamp
  "event_type": "string"      // Event type identifier
}
```

### Branch Cleanup Events

**Stale Detection:**
```json
{
  "repo": "string",
  "stale_count": integer,
  "stale_days": integer,
  "timestamp": "string"
}
```

**Deletion:**
```json
{
  "repo": "string",
  "deleted_count": integer,
  "dry_run": boolean,
  "duration_seconds": float,
  "deleted_branches": ["string"],
  "protected_skipped": ["string"],
  "timestamp": "string"
}
```

**Auto-Deletion:**
```json
{
  "repo": "string",
  "branch": "string",
  "trigger": "pr_closed | pr_merged",
  "dry_run": boolean,
  "timestamp": "string"
}
```

### Issue Triage Events

**Triage:**
```json
{
  "repo": "string",
  "issue_number": integer,
  "labels": ["string"],
  "confidence": float,
  "method": "semantic | pattern",
  "reasoning": "string",
  "timestamp": "string"
}
```

**Labeled:**
```json
{
  "repo": "string",
  "issue_number": integer,
  "labels": ["string"],
  "confidence": float,
  "method": "semantic | pattern",
  "timestamp": "string"
}
```

---

## Integration Patterns

### Webhook to NATS Flow

```
GitHub Webhook
    ↓
n8n (webhook receiver)
    ↓
NATS: github.webhook.{pr|issue}.v1
    ↓
GitHub Automation Service
    ↓
Process event
    ↓
NATS: github.{branch|issue}.{event}.v1
    ↓
Observability (Grafana, Loki)
```

### Service Integration

**Branch Cleanup Service Integration:**
1. Subscribe to `github.webhook.pr.v1`
2. Detect PR close/merge events
3. Validate branch protection rules
4. Delete branch if safe
5. Publish `github.branch.auto_deleted.v1`

**Issue Triage Service Integration:**
1. Subscribe to `github.webhook.issue.v1`
2. Detect issue opened/edited events
3. Classify issue (semantic + pattern)
4. Apply labels via BoTZ MCP
5. Publish `github.issue.labeled.v1`

### Event Correlation

**Correlating PR to Branch Deletion:**
```python
# Subscribe to events
async def handle_auto_delete(msg):
    data = json.loads(msg.data)
    pr_number = extract_pr_number_from_context(msg)
    branch = data["branch"]

    # Correlate with GitHub
    pr = await get_github_pr(pr_number)
    assert pr["head"]["ref"] == branch

    # Log correlation
    logger.info(f"PR #{pr_number} closed → branch {branch} deleted")
```

**Correlating Issue Triage:**
```python
# Track triage accuracy
async def handle_labeled(msg):
    data = json.loads(msg.data)
    issue_number = data["issue_number"]
    predicted_labels = data["labels"]

    # Get actual labels from GitHub
    actual_labels = await get_github_labels(issue_number)

    # Calculate accuracy
    accuracy = calculate_accuracy(predicted_labels, actual_labels)

    # Publish metrics
    await publish_metric("triage_accuracy", accuracy)
```

---

## Monitoring

### NATS Monitoring

**Server Health:**
```bash
# Check NATS server status
curl http://localhost:8222/varz

# Check connections
curl http://localhost:8222/connz

# Check subscriptions
curl http://localhost:8222/subsz
```

**Subject Monitoring:**
```bash
# Monitor github.* subjects
nats sub "github.>"

# Monitor specific service
nats sub "github.branch.>"
nats sub "github.issue.>"
```

### Event Throughput

**Key Metrics:**
- `github_branch_stale_detected_total` - Stale branch detections
- `github_branch_deleted_total` - Branch deletions
- `github_issue_labeled_total` - Labels applied
- `github_webhook_received_total` - Webhook events received

**Prometheus Queries:**
```promql
# Webhook event rate
sum(rate(nats_msg_in{subject="github.webhook.>"}[5m])) by (subject)

# Branch deletion rate
sum(rate(github_branch_deleted_total[1h])) by (repo)

# Issue triage rate
sum(rate(github_issue_labeled_total[1h])) by (repo)
```

### Alerting

**Recommended Alerts:**

```yaml
# High branch deletion rate
- alert: HighBranchDeletionRate
  expr: rate(github_branch_deleted_total[5m]) > 10
  for: 5m
  annotations:
    summary: "Unusually high branch deletion rate"

# No triage events
- alert: NoIssueTriage
  expr: github_issue_labeled_total == 0
  for: 1h
  annotations:
    summary: "No issues triaged in the last hour"

# NATS connection down
- alert: NATSConnectionDown
  expr: nats_up == 0
  for: 1m
  annotations:
    summary: "NATS connection lost"
```

### Event Visualization

**Grafana Dashboard Queries:**

```promql
# Branch cleanup activity
sum(increase(github_branch_deleted_total[1h])) by (repo)

# Issue triage accuracy
avg(github_issue_triage_confidence) by (repo)

# Webhook event volume
sum(rate(nats_msg_in{subject=~"github.webhook.*"}[5m])) by (subject)

# Label distribution
sum(github_issue_label_applied_total) by (label)
```

---

## Testing

### Publishing Test Events

**Test Branch Cleanup:**
```bash
# Publish test PR event
nats pub github.webhook.pr.v1 '{
  "action": "closed",
  "repository": {
    "name": "PMOVES.AI",
    "full_name": "POWERFULMOVES/PMOVES.AI"
  },
  "pull_request": {
    "number": 1234,
    "head": {"ref": "test-branch"},
    "base": {"ref": "main"},
    "merged": false
  }
}'
```

**Test Issue Triage:**
```bash
# Publish test issue event
nats pub github.webhook.issue.v1 '{
  "action": "opened",
  "issue": {
    "number": 1,
    "title": "Test issue",
    "body": "This is a test issue",
    "repository": {
      "name": "PMOVES.AI",
      "full_name": "POWERFULMOVES/PMOVES.AI"
    }
  }
}'
```

### Subscribing to Events

**Monitor All GitHub Events:**
```bash
# Subscribe to all github.* events
nats sub "github.>" &

# Watch for branch deletions
nats sub "github.branch.deleted.v1"

# Watch for issue labels
nats sub "github.issue.labeled.v1"
```

### Event Validation

**Validate Event Schema:**
```python
import json
import jsonschema

# Load schema
with open("schemas/github.branch.deleted.v1.json") as f:
    schema = json.load(f)

# Validate event
event = json.loads(nats_message.data)
jsonschema.validate(event, schema)
```

---

## Best Practices

### Event Design

1. **Versioning:** Always include `.v1` suffix for future compatibility
2. **Timestamps:** Use ISO 8601 format (`2026-03-13T12:00:00Z`)
3. **Snake Case:** Use `snake_case` for field names
4. **Consistent Types:** Maintain consistent data types across events
5. **Minimal Payloads:** Include only necessary fields

### Subscription Management

1. **Queue Groups:** Use queue groups for load balancing
   ```python
   await nc.subscribe("github.>", "workers", callback)
   ```

2. **Durable Subscriptions:** Use JetStream for reliability
   ```python
   await nc.subscribe(
       "github.webhook.pr.v1",
       "branch-cleanup",
       durable=True,
       callback=handle_webhook
   )
   ```

3. **Ack Policies:** Set appropriate acknowledgment policies
   ```python
   await nc.subscribe(
       "github.>",
       ack_policy="explicit"
   )
   ```

### Error Handling

1. **Retry Logic:** Implement exponential backoff for failed events
2. **Dead Letter Queue:** Route unprocessable events to DLQ
3. **Logging:** Log all events with context for debugging
4. **Monitoring:** Alert on high error rates

---

## Additional Resources

- **User Guide:** See `GITHUB_AUTOMATION_GUIDE.md`
- **API Reference:** See `GITHUB_AUTOMATION_API.md`
- **NATS Documentation:** https://docs.nats.io
- **PMOVES.AI NATS:** See `.claude/context/nats-subjects.md`

---

**Last Updated:** 2026-03-13
**NATS Schema Version:** 1.0
