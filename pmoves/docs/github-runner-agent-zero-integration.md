# GitHub Runner Controller - Agent Zero Integration Guide

**PMOVES.AI Agent Zero MCP Commands and NATS Event Integration**

---

## Overview

The `github-runner-ctl` service integrates with Agent Zero through:
1. **HTTP API** - Direct REST endpoints for querying and controlling runners
2. **NATS Events** - Real-time event publishing for reactive automation
3. **MCP Integration** - Potential for extending Agent Zero's capabilities

---

## HTTP API Integration

### Base URL
```
http://github-runner-ctl:8100
```

### Endpoints

#### Get All Runners
```bash
curl http://github-runner-ctl:8100/runners
```

**Response:**
```json
{
  "runners": [
    {
      "name": "ai-lab",
      "location": "local",
      "status": "online",
      "busy": false,
      "queue_depth": 0,
      "capabilities": {
        "gpu": true,
        "ram": "64GB",
        "storage": "200GB"
      }
    }
  ],
  "total": 3,
  "online": 2,
  "busy": 1
}
```

#### Get Specific Runner Status
```bash
curl http://github-runner-ctl:8100/runners/ai-lab
```

#### Get Queue Status for Repository
```bash
curl http://github-runner-ctl:8100/queue/POWERFULMOVES/PMOVES.AI
```

**Response:**
```json
{
  "repository": "POWERFULMOVES/PMOVES.AI",
  "total_jobs": 5,
  "queued": 2,
  "in_progress": 2,
  "completed": 1,
  "jobs": [
    {
      "id": 12345,
      "workflow": "pytest.yml",
      "status": "queued",
      "runner": "cloudstartup",
      "queued_at": "2025-12-30T01:00:00Z"
    }
  ]
}
```

#### Control Runner Action
```bash
curl -X POST http://github-runner-ctl:8100/runners/ai-lab/action \
  -H "Content-Type: application/json" \
  -d '{"action": "disable", "reason": "Maintenance"}'
```

**Actions:** `enable`, `disable`, `restart`, `drain`

---

## NATS Event Integration

### Runner Lifecycle Events

These events are published by `github-runner-ctl` for Agent Zero to consume:

```text
github.runner.registered.v1       # New runner registered
github.runner.removed.v1          # Runner decommissioned
github.runner.enabled.v1          # Runner brought online
github.runner.disabled.v1         # Runner taken offline
github.runner.unreachable.v1      # Runner health check failed
github.runner.cpu_high.v1         # CPU usage above threshold
github.runner.memory_high.v1      # Memory usage above threshold
github.runner.disk_low.v1         # Disk space below threshold
github.runner.queue_backlog.v1    # Queue depth above threshold
```

### Job Lifecycle Events

```text
github.job.queued.v1              # Job queued for runner
github.job.started.v1             # Job started on runner
github.job.completed.v1           # Job completed successfully
github.job.failed.v1              # Job failed
```

### Event Envelope Format (PMOVES Standard)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "github.job.completed.v1",
  "ts": "2025-12-30T01:00:00Z",
  "version": "v1",
  "source": "github-runner-ctl",
  "payload": {
    "runner": "ai-lab",
    "repository": "POWERFULMOVES/PMOVES.AI",
    "job_id": 12345,
    "workflow": "pytest.yml",
    "status": "completed",
    "conclusion": "success",
    "duration_seconds": 245
  },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "parent_id": null
}
```

---

## Agent Zero Command Examples

### Query Runner Status

```python
# Agent Zero MCP command
GET /mcp/github-runner/runners

# Response
{
  "runners": ["ai-lab", "vps", "cloudstartup"],
  "online": ["ai-lab", "vps"],
  "busy": ["ai-lab"],
  "queues": {
    "ai-lab": 0,
    "vps": 3,
    "cloudstartup": 1
  }
}
```

### Find Available Runner for Workload Type

```python
# Agent Zero: Find GPU runner for training job
GET /mcp/github-runner/find?type=gpu&available=true

# Response
{
  "runner": "ai-lab",
  "location": "local",
  "labels": ["self-hosted", "ai-lab", "gpu"],
  "queue_depth": 0,
  "capabilities": {
    "gpu": true,
    "ram": "64GB"
  }
}
```

### Trigger Workflow on Specific Runner

```python
# Agent Zero: Trigger build on vps
POST /mcp/github-runner/trigger
{
  "repository": "POWERFULMOVES/PMOVES.AI",
  "workflow": "docker-build.yml",
  "branch": "main",
  "labels": ["self-hosted", "vps"]
}
```

### Get Queue Status

```python
# Agent Zero: Check queue for PMOVES.AI
GET /mcp/github-runner/queue?repo=POWERFULMOVES/PMOVES.AI

# Response
{
  "repository": "POWERFULMOVES/PMOVES.AI",
  "queue_depth": 5,
  "estimated_wait_minutes": 12,
  "runners_available": 2
}
```

---

## Agent Zero Auto-Response Scenarios

### Scenario 1: Queue Backlog Detected

When `github.runner.queue_backlog.v1` event is received:

```python
# Agent Zero response
if event.payload.queue_depth > 10:
    # Check cloud runner capacity
    cloud_runners = query_runners(location="cloud")
    active_cloud = sum(1 for r in cloud_runners if r.status == "online")

    if active_cloud < 3:
        # Scale up cloud startup runner
        trigger_n8n_workflow("github-runner-autoscaler")

    # Notify user
    send_discord_alert(
        f"Queue depth: {event.payload.queue_depth}, "
        f"Scaling cloud runners to {active_cloud + 1}"
    )
```

### Scenario 2: Job Failed

When `github.job.failed.v1` event is received:

```python
# Agent Zero analysis
if event.payload.conclusion == "failure":
    # Get job details
    job = get_job_details(
        event.payload.repository,
        event.payload.job_id
    )

    # Analyze failure type
    if "tests failed" in job.logs:
        # Create GitHub issue for investigation
        create_github_issue(
            title=f"Tests failed in {job.workflow}",
            body=job.failure_summary,
            labels=["bug", "tests"]
        )

    elif "out of memory" in job.logs:
        # Alert about resource exhaustion
        send_discord_alert(
            f"Runner {event.payload.runner} out of memory",
            severity="critical"
        )

        # Disable runner until investigated
        disable_runner(
            event.payload.runner,
            reason="Memory exhaustion - investigation needed"
        )
```

### Scenario 3: Runner Offline

When `github.runner.unreachable.v1` event is received:

```python
# Agent Zero response
offline_count = count_events(
    "github.runner.unreachable.v1",
    runner=event.payload.runner,
    since=now() - minutes(10)
)

if offline_count > 3:
    # Runner has been unreachable for >10 minutes
    notify_ops_team(
        f"Runner {event.payload.runner} is offline",
        severity="warning"
    )

    # Check if we need to reroute queued jobs
    reroute_queued_jobs(from=event.payload.runner)
```

---

## Example Workflows

### Workflow 1: Intelligent Build Routing

```yaml
# Agent Zero workflow triggered by GitHub webhook
1. Receive workflow_job event from GitHub
2. Parse job type from workflow name
3. Query routing config for matching pattern
4. Get available runners for that route
5. If no runners available, trigger auto-scaler
6. Respond to GitHub with recommended runner labels
```

### Workflow 2: Cost Optimization

```yaml
# Agent Zero scheduled task (every 15 minutes)
1. Query all runners and their queue depths
2. Identify idle cloud runners (queue_depth = 0 for >15m)
3. Calculate current cost per hour
4. If cost > threshold and local runners available:
   - Disable idle cloud runners
   - Send summary report
```

### Workflow 3: Security Scan Integration

```yaml
# Agent Zero triggered by workflow completion
1. Listen for github.job.completed.v1 events
2. If workflow_name contains "security":
   - Download scan artifacts
   - Parse findings (SAST, dependency, container)
   - If critical findings:
     * Create GitHub issue
     * Notify via Discord
     * Block merge if applicable
```

---

## MCP Command Reference

### Available Commands

| Command | Method | Description |
|---------|--------|-------------|
| `/runners list` | GET | List all configured runners |
| `/runners get {name}` | GET | Get specific runner status |
| `/runners action {name} {action}` | POST | Control runner (enable/disable/restart) |
| `/queue {repo}` | GET | Get workflow queue status |
| `/find-runner {type}` | GET | Find available runner by workload type |
| `/trigger {repo} {workflow}` | POST | Trigger workflow with specific labels |

### Example CLI Usage

```bash
# Via Agent Zero MCP
curl -X POST http://agent-zero:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "runners_list",
    "parameters": {
      "status": "online"
    }
  }'
```

---

## Security Considerations

### Authentication
- All API endpoints should be protected with authentication in production
- Use internal network policies to restrict access
- GitHub PAT should be stored in Docker secrets

### Authorization
- Agent Zero should use service account with limited permissions
- Only read-only access to runner status for most queries
- Write access (enable/disable) requires elevated permissions

### Rate Limiting
- Implement rate limiting on control endpoints
- Cache runner status queries (TTL: 30s)
- Batch API calls when monitoring multiple runners

---

## Troubleshooting

### Agent Zero Can't Reach github-runner-ctl

1. Check service is running:
   ```bash
   curl http://github-runner-ctl:8100/healthz
   ```

2. Verify network connectivity:
   ```bash
   docker network inspect pmoves_net
   ```

3. Check firewall rules between Agent Zero and github-runner-ctl

### NATS Events Not Received

1. Verify NATS connection:
   ```bash
   nats sub "github.>" &
   # Trigger a job and check for events
   ```

2. Check github-runner-ctl logs:
   ```bash
   docker logs pmoves-github-runner-ctl-1
   ```

3. Verify Agent Zero is subscribed to correct subjects

---

## See Also

- [PMOVES Agent Zero Documentation](../services/agent-zero/README.md)
- [GitHub Runner Workflows Guide](./github-runner-workflows.md)
- [NATS Subject Catalog](./nats-subjects.md)
