# PMOVES.AI NATS Event Subjects Catalog

Comprehensive reference of all NATS message subjects used for event-driven communication across PMOVES services.

> **See Also:** For GEOMETRY BUS subjects (`tokenism.*`, `geometry.*`), see [geometry-nats-subjects.md](./geometry-nats-subjects.md)

## NATS Configuration

- **Server:** `nats://localhost:4222`
- **JetStream:** Enabled for persistence
- **Version:** 2.10-alpine

## Subject Naming Convention

PMOVES uses versioned subject names following the pattern:
```
<category>.<service>.<event>.<version>
```

Example: `ingest.transcript.ready.v1`

## Research & Knowledge Subjects

### DeepResearch

**`research.deepresearch.request.v1`**
- **Direction:** Published by clients → Consumed by DeepResearch
- **Purpose:** Request LLM-based research planning
- **Payload:**
  ```json
  {
    "query": "Research question or topic",
    "request_id": "unique-id-for-tracking",
    "requester": "service-name",
    "options": {
      "depth": "basic|detailed|comprehensive",
      "sources": ["web", "knowledge_base", "papers"]
    }
  }
  ```
- **Used By:** SupaSerch, Agent Zero, custom research workflows

**`research.deepresearch.result.v1`**
- **Direction:** Published by DeepResearch → Consumed by clients
- **Purpose:** Research results and findings
- **Payload:**
  ```json
  {
    "request_id": "matching-request-id",
    "query": "original query",
    "findings": [
      {
        "title": "...",
        "content": "...",
        "sources": ["..."],
        "confidence": 0.95
      }
    ],
    "methodology": "description of approach",
    "references": ["..."],
    "stored_in_notebook": true
  }
  ```
- **Auto-Storage:** Results automatically published to Open Notebook

### SupaSerch

**`supaserch.request.v1`**
- **Direction:** Published by clients → Consumed by SupaSerch
- **Purpose:** Request multimodal holographic deep research
- **Payload:**
  ```json
  {
    "query": "Complex research question",
    "request_id": "unique-id",
    "requester": "service-name",
    "options": {
      "use_deep_research": true,
      "use_mcp_tools": true,
      "use_hirag": true,
      "max_iterations": 5
    }
  }
  ```
- **Used By:** Agent Zero, custom research pipelines

**`supaserch.result.v1`**
- **Direction:** Published by SupaSerch → Consumed by clients
- **Purpose:** Comprehensive research results
- **Payload:**
  ```json
  {
    "request_id": "matching-request-id",
    "query": "original query",
    "results": {
      "answer": "synthesized answer",
      "sources": ["..."],
      "methodology": "research approach used",
      "confidence": 0.92
    },
    "execution_log": [
      {
        "step": 1,
        "tool": "deepresearch",
        "result": "..."
      }
    ]
  }
  ```

## Media Ingestion Subjects

### File Ingestion

**`ingest.file.added.v1`**
- **Direction:** Published by PDF Ingest, File Upload services
- **Purpose:** Notify that a new file has been added to MinIO
- **Payload:**
  ```json
  {
    "file_id": "unique-file-id",
    "bucket": "assets",
    "key": "path/to/file.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1234567,
    "timestamp": "2025-12-06T12:00:00Z",
    "uploader": "service-name"
  }
  ```
- **Subscribers:** Discord Publisher, Extract Worker, media analyzers

### Transcript Events

**`ingest.transcript.ready.v1`**
- **Direction:** Published by PMOVES.YT, FFmpeg-Whisper
- **Purpose:** Notify that transcription is complete
- **Payload:**
  ```json
  {
    "video_id": "youtube-video-id",
    "transcript_id": "unique-transcript-id",
    "source": "youtube|whisper",
    "language": "en",
    "duration_seconds": 3600,
    "word_count": 5000,
    "storage": {
      "bucket": "assets",
      "key": "transcripts/video-id.txt"
    },
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Subscribers:** Discord Publisher, Extract Worker, analysis pipelines

**`ingest.summary.ready.v1`**
- **Direction:** Published by summary generation services
- **Purpose:** Notify that content summary is available
- **Payload:**
  ```json
  {
    "content_id": "video-id or file-id",
    "summary_id": "unique-summary-id",
    "summary_text": "Brief summary...",
    "key_points": ["point 1", "point 2"],
    "storage": {
      "bucket": "outputs",
      "key": "summaries/content-id.json"
    }
  }
  ```
- **Subscribers:** Discord Publisher, UI updates

**`ingest.chapters.ready.v1`**
- **Direction:** Published by chapter generation services
- **Purpose:** Notify that chapter markers are available
- **Payload:**
  ```json
  {
    "content_id": "video-id",
    "chapters": [
      {
        "start_seconds": 0,
        "title": "Introduction",
        "summary": "..."
      }
    ],
    "storage": {
      "bucket": "outputs",
      "key": "chapters/content-id.json"
    }
  }
  ```
- **Subscribers:** Discord Publisher, UI updates

## Agent Observability Subjects

### Claude Code CLI Tool Execution

**`claude.code.tool.executed.v1`**
- **Direction:** Published by Claude Code CLI hooks → Consumed by monitoring
- **Purpose:** Track developer tool execution for observability
- **Payload:**
  ```json
  {
    "tool": "tool-name",
    "timestamp": "2025-12-06T12:00:00Z",
    "user": "developer-username",
    "session_id": "cli-session-id",
    "result_summary": "brief result description"
  }
  ```
- **Subscribers:** Monitoring dashboards, analytics

### Agent Coordination (Custom)

**`agent.tool.executed.v1`**
- **Direction:** Published by Agent Zero, subordinate agents
- **Purpose:** Track agent tool execution
- **Payload:**
  ```json
  {
    "agent_id": "agent-0 or subordinate-id",
    "tool": "tool-name",
    "timestamp": "2025-12-06T12:00:00Z",
    "result_summary": "...",
    "success": true
  }
  ```
- **Subscribers:** Observability systems, UI dashboards

**`agent.graphiti.signed.v1`**
- **Direction:** Published by BoTZ MCP Gateway and agent handoff services
- **Purpose:** Emit graphiti-signed trail events for cross-agent handoff attribution
- **Payload:**
  ```json
  {
    "agent_id": "codex",
    "display_name": "Codex",
    "glyph": "■",
    "color": "#2563EB",
    "voice": "terse",
    "phase": "phase-name",
    "timestamp": "2026-02-24T00:40:00Z",
    "summary": "short completion summary",
    "resonance": ["domain-a", "domain-b"],
    "handoff": {
      "done": ["item-1"],
      "remaining": ["item-2"],
      "for_next_agent": ["item-3"]
    }
  }
  ```
- **Schema:** `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json`
- **Subscribers:** Agent trail processors, observability dashboards, handoff automation
- **Delivery:** Publish/subscribe (JetStream optional depending on deployment policy)

## Mesh Coordination Subjects

### Node Announcements

**`mesh.node.announce.v1`**
- **Direction:** Published by Mesh Agent on each host
- **Purpose:** Announce host presence and capabilities
- **Payload:**
  ```json
  {
    "node_id": "host-unique-id",
    "hostname": "server-name",
    "capabilities": {
      "gpu": true,
      "gpu_count": 2,
      "cpu_cores": 16,
      "memory_gb": 64
    },
    "services_running": [
      "agent-zero",
      "hi-rag-gpu",
      "media-video-analyzer"
    ],
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Frequency:** Every 15 seconds (configurable)
- **Subscribers:** Orchestration services, load balancers

## Remote Desktop & VPN Subjects

### Remote Sessions

**`remote.session.started.v1`**
- **Direction:** Published by VPN MCP / Remote Desktop Gateway
- **Purpose:** Notify that a remote desktop session has started
- **Payload:**
  ```json
  {
    "session_id": "unique-session-id",
    "user_id": "user-uuid",
    "target_device": "device-name",
    "connection_type": "rustdesk|vpn|direct",
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher, Monitoring, Supabase

**`remote.session.ended.v1`**
- **Direction:** Published by VPN MCP / Remote Desktop Gateway
- **Purpose:** Notify that a remote desktop session has ended
- **Payload:**
  ```json
  {
    "session_id": "matching-session-id",
    "duration_seconds": 3600,
    "terminated_by": "user|admin|timeout",
    "timestamp": "2025-12-06T13:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Monitoring, Supabase

### VPN Node Events

**`vpn.node.connected.v1`**
- **Direction:** Published by Headscale integration
- **Purpose:** Notify that a device has connected to VPN
- **Payload:**
  ```json
  {
    "node_id": "tailscale-node-id",
    "hostname": "device-hostname",
    "tags": ["tag:pmoves", "tag:admin"],
    "ip_addresses": ["100.64.0.5"],
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Monitoring, Supabase (for node registry)

**`vpn.node.disconnected.v1`**
- **Direction:** Published by Headscale integration
- **Purpose:** Notify that a device has disconnected from VPN
- **Payload:**
  ```json
  {
    "node_id": "tailscale-node-id",
    "hostname": "device-hostname",
    "last_seen": "2025-12-06T13:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Monitoring

### VPN Authentication

**`vpn.auth_key.created.v1`**
- **Direction:** Published by VPN MCP when auth key created
- **Purpose:** Audit log for VPN key creation
- **Payload:**
  ```json
  {
    "key_id": "key-identifier",
    "user": "username",
    "tags": ["tag:pmoves"],
    "ephemeral": false,
    "created_by": "agent-zero-or-user-id",
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Audit logging, Supabase

**`vpn.route.advertised.v1`**
- **Direction:** Published by VPN MCP when route is advertised
- **Purpose:** Track VPN route advertisements
- **Payload:**
  ```json
  {
    "node_id": "advertising-node-id",
    "route": "172.30.0.0/24",
    "enabled": true,
    "timestamp": "2025-12-06T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Monitoring

## Voice & Prosodic Subjects

**`tokenism.prosodic.bpm.v1`**
- **Direction:** Published by Flute-Gateway prosodic parser
- **Purpose:** BPM-encoded prosodic timeline events for CHIT voice attribution
- **Payload:**
  ```json
  {
    "utterance_id": "utt-abc123",
    "voice_persona_id": "persona-1",
    "bpm_timeline": [60, 120, 90, 60],
    "boundary_sequence": ["SENTENCE", "PHRASE", "CLAUSE", "SENTENCE"],
    "total_syllables": 42,
    "duration_estimate_ms": 6300,
    "scale": "pentatonicMajor",
    "timestamp": "2026-02-20T12:00:00Z"
  }
  ```
- **Subscribers:** ToKenism-Multi (musicMapping.ts), Hyperdimensions (visualization)
- **Related:** See `/chit:bpm` tool spec, `TAC_TOKENISM.md`, `FLUTE_PROSODIC_ARCHITECTURE.md`

## GitHub Automation & Branch Strategy Subjects

> **Status:** Production — GitHub automation services for branch cleanup, issue triage, naming enforcement, and cross-repo sync

### PR & Promotion Events

**`github.pr.validation.v1`**
- **Direction:** Published by GitHub Actions (pr-base-validation.yml)
- **Purpose:** PR base branch validation results
- **Payload:**
  ```json
  {
    "status": "success|failure",
    "base_ref": "PMOVES.AI-Edition-Hardened-Integrations",
    "head_ref": "feat/new-feature",
    "pr_number": 123,
    "ttl_check_status": "success|failure|skipped",
    "timestamp": "2026-03-13T10:00:00Z",
    "source": "github-workflow"
  }
  ```
- **Subscribers:** Branch Naming Service, Prometheus (via NATS exporter)
- **See:** `.github/workflows/pr-base-validation.yml`

**`github.promotion.requested.v1`**
- **Direction:** Published by `make -C pmoves promote-to-*`
- **Purpose:** Promotion PR creation notification
- **Payload:**
  ```json
  {
    "action": "feature_to_integrations|integrations_to_hardened|hardened_to_main",
    "branch": "feat/new-feature",
    "pr_number": 123,
    "target": "PMOVES.AI-Edition-Hardened-Integrations",
    "release_version": "v1.2.3",
    "timestamp": "2026-03-13T10:00:00Z"
  }
  ```
- **Subscribers:** Cross-Repo Sync Service, Prometheus
- **See:** `pmoves/mk/promote.mk`

**`github.promotion.completed.v1`**
- **Direction:** Published by promotion workflow after merge
- **Purpose:** Promotion merge completed (triggers cross-repo sync)
- **Payload:**
  ```json
  {
    "action": "hardened_to_main",
    "branch": "PMOVES.AI-Edition-Hardened",
    "pr_number": 789,
    "target": "main",
    "merged_by": "username",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```
- **Subscribers:** Cross-Repo Sync Service, Branch Cleanup Service

### Branch Lifecycle Events

**`github.branch.created.v1`**
- **Direction:** Published by n8n webhook → NATS
- **Purpose:** New branch created (triggers naming validation)
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "feat/new-feature",
    "action": "created",
    "creator": "username",
    "timestamp": "2026-03-13T09:00:00Z"
  }
  ```
- **Subscribers:** Branch Naming Service, Prometheus

**`github.branch.validation.v1`**
- **Direction:** Published by Branch Naming Service
- **Purpose:** Branch name validation result
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "random-branch",
    "is_valid": false,
    "category": null,
    "suggested_name": "feat/random-branch",
    "reason": "Invalid branch name format. Suggested: feat/random-branch",
    "timestamp": "2026-03-13T09:05:00Z"
  }
  ```
- **Subscribers:** Prometheus, monitoring dashboards

**`github.branch.rename_suggested.v1`**
- **Direction:** Published by Branch Naming Service
- **Purpose:** Branch rename suggested for invalid names
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "original_branch": "random-branch",
    "suggested_branch": "feat/random-branch",
    "reason": "Branch name must start with feat/, fix/, chore/, docs/, codex/, or ref/docs/",
    "dry_run": true,
    "timestamp": "2026-03-13T09:05:00Z"
  }
  ```
- **Subscribers:** Prometheus (alerting on high rename suggestion rate)

**`github.branch.deleted.v1`**
- **Direction:** Published by Branch Cleanup Service
- **Purpose:** Branch deleted (cleanup operation)
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "deleted_count": 5,
    "dry_run": false,
    "duration_seconds": 2.5,
    "timestamp": "2026-03-13T11:00:00Z"
  }
  ```
- **Subscribers:** Prometheus, Discord Publisher

**`github.branch.stale_detected.v1`**
- **Direction:** Published by Branch Cleanup Service
- **Purpose:** Stale branches detected (TTL exceeded)
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "stale_count": 12,
    "stale_days": 30,
    "timestamp": "2026-03-13T10:00:00Z"
  }
  ```
- **Subscribers:** Branch Cleanup Service (trigger cleanup), Prometheus

**`github.branch.auto_deleted.v1`**
- **Direction:** Published by Branch Cleanup Service
- **Purpose:** Branch auto-deleted after PR merge
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "feat/completed-feature",
    "trigger": "pr_closed",
    "dry_run": false,
    "timestamp": "2026-03-13T14:00:00Z"
  }
  ```
- **Subscribers:** Prometheus, Discord Publisher

### Cross-Repo Sync Events

**`github.crossrepo.sync.v1`**
- **Direction:** Published by Cross-Repo Sync Service
- **Purpose:** Cross-repo sync operation started
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "main",
    "status": "started",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```
- **Subscribers:** Prometheus, monitoring dashboards

**`github.crossrepo.sync.completed.v1`**
- **Direction:** Published by Cross-Repo Sync Service
- **Purpose:** Cross-repo sync completed successfully
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "main",
    "submodules_synced": ["PMOVES-Agent-Zero", "PMOVES-Archon"],
    "submodules_failed": [],
    "duration_seconds": 15.5,
    "timestamp": "2026-03-13T12:00:15Z"
  }
  ```
- **Subscribers:** Prometheus, Discord Publisher

**`github.crossrepo.sync.failed.v1`**
- **Direction:** Published by Cross-Repo Sync Service
- **Purpose:** Cross-repo sync operation failed
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "branch": "main",
    "error": "Failed to update submodule PMOVES-Agent-Zero: git timeout",
    "timestamp": "2026-03-13T12:00:10Z"
  }
  ```
- **Subscribers:** Prometheus (alerting), Discord Publisher

### Issue Triage Events

**`github.issue.triage.v1`**
- **Direction:** Published by Issue Triage Service
- **Purpose:** Issue triage completed (internal event)
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "issue_number": 123,
    "labels": ["bug", "high-priority"],
    "confidence": 0.85,
    "method": "semantic",
    "reasoning": "Found 5 similar issues with these labels",
    "timestamp": "2026-03-13T09:00:00Z"
  }
  ```
- **Subscribers:** Prometheus (accuracy tracking)

**`github.issue.labeled.v1`**
- **Direction:** Published by Issue Triage Service
- **Purpose:** Labels applied to issue via GitHub API
- **Payload:**
  ```json
  {
    "repo": "PMOVES.AI",
    "issue_number": 123,
    "labels": ["bug", "high-priority"],
    "confidence": 0.85,
    "method": "semantic",
    "timestamp": "2026-03-13T09:00:05Z"
  }
  ```
- **Subscribers:** Prometheus, Discord Publisher

### Webhook Events (from n8n)

**`github.webhook.pr.v1`**
- **Direction:** Published by n8n webhook processor
- **Purpose:** PR webhook event from GitHub
- **Payload:** GitHub webhook payload (see GitHub docs)
- **Subscribers:** Branch Cleanup Service (auto-delete after merge)

**`github.webhook.issue.v1`**
- **Direction:** Published by n8n webhook processor
- **Purpose:** Issue webhook event from GitHub
- **Payload:** GitHub webhook payload (see GitHub docs)
- **Subscribers:** Issue Triage Service

**`github.webhook.branch.v1`**
- **Direction:** Published by n8n webhook processor
- **Purpose:** Branch webhook event from GitHub
- **Payload:** GitHub webhook payload (see GitHub docs)
- **Subscribers:** Branch Naming Service

## Health & Fitness Subjects (Planned)

> **Status:** Planned — Health (wger) integration is pre-stage maturity. These subjects define the target contract.

**`health.metrics.updated.v1`**
- **Direction:** Published by Health (wger) service
- **Purpose:** Body metrics updated (weight, body fat, measurements)
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "metric_type": "weight",
    "value": 82.5,
    "unit": "kg",
    "recorded_at": "2026-02-20T08:00:00Z",
    "timestamp": "2026-02-20T08:01:00Z"
  }
  ```
- **Subscribers:** Agent Zero, ToKenism-Multi, Wealth (correlation)

**`health.workout.completed.v1`**
- **Direction:** Published by Health (wger) service
- **Purpose:** Workout session completed
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "workout_id": "wkt-456",
    "duration_min": 45,
    "exercises": ["bench_press", "squat", "deadlift"],
    "timestamp": "2026-02-20T09:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher

**`health.weekly.summary.v1`**
- **Direction:** Published by Health (wger) cron job
- **Purpose:** Weekly fitness summary for dashboard and agent context
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "week_start": "2026-02-17",
    "workouts_count": 4,
    "total_duration_min": 180,
    "weight_change_kg": -0.3,
    "timestamp": "2026-02-23T00:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, SupaSerch, Discord Publisher

## Finance & Wealth Subjects (Planned)

> **Status:** Planned — Wealth (Firefly III) integration is pre-stage maturity. These subjects define the target contract.

**`finance.transactions.ingested.v1`**
- **Direction:** Published by Wealth (Firefly III) service
- **Purpose:** New financial transactions imported or created
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "transaction_count": 5,
    "source": "bank_import",
    "categories": ["groceries", "utilities"],
    "total_amount": 245.67,
    "currency": "USD",
    "timestamp": "2026-02-20T10:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, ToKenism-Multi (finance events)

**`finance.budget.alert.v1`**
- **Direction:** Published by Wealth (Firefly III) service
- **Purpose:** Budget threshold exceeded alert
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "budget_name": "dining_out",
    "spent": 450.00,
    "limit": 400.00,
    "percentage": 112.5,
    "currency": "USD",
    "timestamp": "2026-02-20T11:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher

**`finance.monthly.summary.v1`**
- **Direction:** Published by Wealth (Firefly III) cron job
- **Purpose:** Monthly financial summary for dashboard and agent context
- **Payload:**
  ```json
  {
    "user_id": "user-123",
    "month": "2026-02",
    "income": 5000.00,
    "expenses": 3200.00,
    "savings_rate": 36.0,
    "top_categories": [
      {"name": "housing", "amount": 1200.00},
      {"name": "groceries", "amount": 600.00}
    ],
    "currency": "USD",
    "timestamp": "2026-03-01T00:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, SupaSerch, Discord Publisher

## Testing & Development Subjects

**`test.smoke.v1`**
- **Purpose:** Smoke testing NATS pub/sub
- **Usage:** `nats pub "test.smoke.v1" "test message"`

**`dev.debug.v1`**
- **Purpose:** Development debugging messages
- **Usage:** Ad-hoc debugging during development

## Subject Wildcards

NATS supports wildcards for subscriptions:

**Single-level wildcard (`*`):**
```bash
# Subscribe to all ingest events regardless of type
nats sub "ingest.*.ready.v1"
```

**Multi-level wildcard (`>`):**
```bash
# Subscribe to ALL ingest events
nats sub "ingest.>"

# Subscribe to all research-related events
nats sub "research.>"
```

## Best Practices

### Publishing Events

1. **Always include version** - `v1`, `v2`, etc. for backward compatibility
2. **Include request_id** - For tracking and correlation
3. **Add timestamp** - ISO 8601 format (UTC)
4. **Provide context** - Include enough info for subscribers to act

### Subscribing to Events

1. **Use queue groups** - For load balancing: `nats sub subject --queue workers`
2. **Handle failures gracefully** - Events may arrive out of order
3. **Acknowledge processing** - If using JetStream persistence
4. **Log all events** - For debugging and audit trails

### Versioning

When changing payload structure:
- Create new version: `subject.v2`
- Maintain old version for transition period
- Document migration path in release notes

## NATS CLI Examples

### Publish Event
```bash
nats pub "research.deepresearch.request.v1" '{
  "query": "test query",
  "request_id": "test-123",
  "requester": "cli"
}'
```

### Subscribe to Events
```bash
# Single subject
nats sub "ingest.transcript.ready.v1"

# Wildcard - all ingest events
nats sub "ingest.>" --max 10

# Queue group for load balancing
nats sub "research.deepresearch.request.v1" --queue workers
```

### Monitor Traffic
```bash
# View all traffic (careful in production!)
nats sub ">"

# View specific category
nats sub "research.>"
```

## JetStream Configuration

For persistent subjects requiring guaranteed delivery:

```bash
# Create stream for research events
nats stream add RESEARCH \
  --subjects "research.>" \
  --retention limits \
  --max-age 7d

# Create consumer
nats consumer add RESEARCH research_worker \
  --deliver all \
  --ack explicit
```

## Monitoring

### Check NATS Server Status
```bash
nats server info
```

### View Subject Activity
```bash
nats server report connections
```

### Metrics (if NATS Prometheus exporter enabled)
- `nats_server_connections` - Active connections
- `nats_server_subscriptions` - Active subscriptions
- `nats_server_messages_in` - Messages received
- `nats_server_messages_out` - Messages sent

## BoTZ MCP GitHub Subjects

### GitHub Tool Execution

**`botz.mcp.github.tool.executed.v1`**
- **Direction:** Published by BoTZ GitHub MCP server → Consumed by monitoring
- **Purpose:** Track all GitHub MCP tool calls for observability
- **Payload:**
  ```json
  {
    "tool": "create_pull_request",
    "repo": "POWERFULMOVES/PMOVES.AI",
    "timestamp": "2026-03-10T12:00:00Z",
    "success": true,
    "duration_ms": 450
  }
  ```
- **Subscribers:** Observability dashboards, Graphiti trail

**`botz.mcp.github.pr.created.v1`**
- **Direction:** Published by BoTZ GitHub MCP server → Consumed by Agent Zero, Discord
- **Purpose:** Notify that a PR was created via MCP tooling
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "pr_number": 849,
    "title": "feat(github-app): docs, registry, and org-wide strategy",
    "author": "pmoves-ai[bot]",
    "timestamp": "2026-03-10T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher, PR Monitor

**`botz.mcp.github.issue.created.v1`**
- **Direction:** Published by BoTZ GitHub MCP server → Consumed by Agent Zero, Discord
- **Purpose:** Notify that an issue was created via MCP tooling
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "issue_number": 100,
    "title": "Issue title",
    "labels": ["bug"],
    "timestamp": "2026-03-10T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher

## GPU Mesh & Model Lifecycle Subjects

### GPU Orchestrator → Model Registry

**`mesh.gpu.status.v1`**
- **Direction:** Published by gpu-orchestrator (every 5s) → Consumed by monitoring
- **Purpose:** Periodic GPU status broadcast (VRAM, loaded models, health)

**`mesh.gpu.model.loaded.v1`**
- **Direction:** Published by gpu-orchestrator → Consumed by model-registry
- **Purpose:** Notify registry that a model was loaded on GPU
- **Payload:**
  ```json
  {"type": "mesh.gpu.model.loaded.v1", "model_key": "ollama/qwen3:8b", "vram_mb": 6144, "ts": 1709568000}
  ```

**`mesh.gpu.model.unloaded.v1`**
- **Direction:** Published by gpu-orchestrator → Consumed by model-registry
- **Purpose:** Notify registry that a model was unloaded from GPU
- **Payload:**
  ```json
  {"type": "mesh.gpu.model.unloaded.v1", "model_key": "ollama/qwen3:8b", "ts": 1709568000}
  ```

**`mesh.gpu.vram.warning.v1`**
- **Direction:** Published by gpu-orchestrator → Consumed by monitoring/alerting
- **Purpose:** VRAM usage exceeded threshold (rate-limited to 1/min)

### Model Registry → Downstream

**`model.registry.updated.v1`**
- **Direction:** Published by model-registry → Consumed by future consumers
- **Purpose:** Catalog mutation notification (model/provider/mapping CRUD)
- **Payload:**
  ```json
  {"type": "model.registry.updated.v1", "action": "created|updated|deleted", "resource_type": "model|provider|mapping|deployment", "resource_id": "...", "ts": 1709568000}
  ```

### Any Service → GPU Orchestrator (Commands)

**`mesh.gpu.command.v1`**
- **Direction:** Published by any service → Consumed by gpu-orchestrator
- **Purpose:** Request model lifecycle operations via NATS
- **Payload:**
  ```json
  {"action": "load|unload|optimize", "model_id": "qwen3:8b", "provider": "ollama", "priority": 5, "session_id": "optional-session-id"}
  ```

**`mesh.gpu.command.result.v1`**
- **Direction:** Published by gpu-orchestrator → Consumed by requestor
- **Purpose:** Command execution result (fire-and-forget, no request-reply)
- **Payload:**
  ```json
  {"type": "mesh.gpu.command.result.v1", "success": true, "model_key": "ollama/qwen3:8b", "ts": 1709568000}
  ```

## GitHub Automation Subjects

**`github.webhook.pr.v1`**
- **Direction:** Published by n8n → Consumed by github-branch-cleanup
- **Purpose:** Pull request webhook events (closed/merged)
- **Payload:**
  ```json
  {"repository": {"name": "PMOVES.AI"}, "action": "closed", "pull_request": {"head": {"ref": "feature-branch"}}}
  ```

**`github.webhook.issue.v1`**
- **Direction:** Published by n8n → Consumed by github-issue-triage
- **Purpose:** Issue webhook events (opened/edited)
- **Payload:**
  ```json
  {"repository": {"name": "PMOVES.AI"}, "action": "opened", "issue": {"number": 123, "title": "...", "body": "..."}}
  ```

**`github.branch.deleted.v1`**
- **Direction:** Published by github-branch-cleanup → Consumed by monitoring/alerting
- **Purpose:** Branch cleanup deletion events
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "deleted_count": 5, "dry_run": false, "duration_seconds": 2.5, "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.branch.stale_detected.v1`**
- **Direction:** Published by github-branch-cleanup → Consumed by monitoring
- **Purpose:** Stale branch detection events
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "stale_count": 12, "stale_days": 30, "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.branch.auto_deleted.v1`**
- **Direction:** Published by github-branch-cleanup → Consumed by monitoring
- **Purpose:** Auto-delete after PR closed/merged
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "branch": "feature-branch", "trigger": "pr_closed", "dry_run": true, "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.issue.triage.v1`**
- **Direction:** Published by github-issue-triage → Consumed by monitoring
- **Purpose:** Issue triage results
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "issue_number": 123, "labels": ["bug", "high-priority"], "confidence": 0.85, "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.issue.labeled.v1`**
- **Direction:** Published by github-issue-triage → Consumed by monitoring
- **Purpose:** Label application events after successful triage
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "issue_number": 123, "labels": ["bug"], "confidence": 0.85, "method": "semantic", "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.issue.labeled.v1`**
- **Direction:** Published by github-issue-triage → Consumed by monitoring
- **Purpose:** Label application events
- **Payload:**
  ```json
  {"repo": "PMOVES.AI", "issue_number": 123, "label": "bug", "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.crossrepo.pr_batch.v1`**
- **Direction:** Published by github-crossrepo-pr → Consumed by monitoring
- **Purpose:** Cross-repo PR batch events
- **Payload:**
  ```json
  {"workflow_id": "abc-123", "repos": ["PMOVES.AI", "PMOVES-Agent-Zero"], "pr_count": 2, "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`github.crossrepo.workflow.v1`**
- **Direction:** Published by github-crossrepo-pr → Consumed by monitoring
- **Purpose:** Workflow execution events
- **Payload:**
  ```json
  {"workflow_id": "abc-123", "workflow_type": "submodule_update", "status": "completed", "timestamp": "2026-03-13T00:00:00Z"}
  ```

**`archon.work_order.github.v1`**
- **Direction:** Published by Archon → Consumed by github-crossrepo-pr
- **Purpose:** Work order for GitHub cross-repo operations
- **Payload:**
  ```json
  {"work_order_id": "wo-123", "workflow_type": "submodule_update", "repos": ["PMOVES.AI"], "changes": [...], "approved": true}
  ```
