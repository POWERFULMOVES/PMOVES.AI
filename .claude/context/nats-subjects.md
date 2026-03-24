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

## Cipher Memory Subjects

**`cipher.memory.stored.v1`**
- **Direction:** Published by Cipher MCP bridge → Consumed by monitoring, observability
- **Purpose:** Notify that a memory was stored in Cipher
- **Payload:**
  ```json
  {
    "memory_id": "mem-abc123",
    "category": "code_pattern",
    "tags": ["python", "async"],
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Subscribers:** Observability dashboards, Discord Publisher (optional)

**`cipher.memory.searched.v1`**
- **Direction:** Published by Cipher MCP bridge → Consumed by monitoring
- **Purpose:** Notify that a memory search was performed
- **Payload:**
  ```json
  {
    "query": "search query text",
    "result_count": 5,
    "category": "architecture | null",
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Note:** `category` is `null` when the search is unfiltered (no category specified)
- **Subscribers:** Observability dashboards

**`cipher.reasoning.stored.v1`**
- **Direction:** Published by Cipher MCP bridge → Consumed by monitoring
- **Purpose:** Notify that a reasoning trace was stored
- **Payload:**
  ```json
  {
    "reasoning_id": "reason-abc123",
    "question": "How to optimize query performance...",
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Note:** `question` is truncated to 200 characters in the event payload
- **Subscribers:** Observability dashboards, Graphiti trail processors

## OpenClaw (ClawZ) Messaging Subjects

**`openclaw.message.received.v1`**
- **Direction:** Published by ClawZ nats-bridge extension → Consumed by monitoring, Agent Zero
- **Purpose:** Notify that an inbound message was received on any channel
- **Payload:**
  ```json
  {
    "channel": "discord",
    "message_id": "msg-abc123",
    "author": "user-id",
    "content_length": 128,
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, observability dashboards

**`openclaw.message.sent.v1`**
- **Direction:** Published by ClawZ nats-bridge extension → Consumed by monitoring
- **Purpose:** Notify that an outbound message was sent on any channel
- **Payload:**
  ```json
  {
    "channel": "telegram",
    "message_id": "msg-def456",
    "content_length": 256,
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Subscribers:** Observability dashboards

**`openclaw.channel.connected.v1`**
- **Direction:** Published by ClawZ nats-bridge extension → Consumed by monitoring
- **Purpose:** Notify that a channel adapter connected or disconnected
- **Payload:**
  ```json
  {
    "channel": "discord",
    "status": "connected",
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Subscribers:** Observability dashboards, Agent Zero

## autoresearch Experiment Subjects

**`research.autoresearch.result.v1`**
- **Direction:** Published by `nats_reporter.py` → Consumed by Agent Zero, monitoring
- **Purpose:** Notify that an experiment completed with results
- **Payload:**
  ```json
  {
    "commit": "a1b2c3d",
    "branch": "autoresearch/mar15",
    "val_bpb": 0.997900,
    "peak_vram_mb": 45060.2,
    "training_seconds": 300.1,
    "num_steps": 953,
    "num_params_M": 50.3,
    "timestamp": "2026-03-15T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero, AgentGym RL coordinator, observability dashboards

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

**`ops.pr.insight.shared.v1`**
- **Direction:** Published by any node agent during PR review or commit work
- **Purpose:** Share cross-PR insights between node agents (z890, 5090, 4090) for validation
- **Payload:**
  ```json
  {
    "pr_number": 1048,
    "source_agent": "z890-claude",
    "target_agents": ["4090-claude", "5090-claude"],
    "insight_type": "pattern|blocker|dependency|learning",
    "summary": "SSL_CERT_FILE leak affects both v1 and v2 Hi-RAG variants",
    "files_affected": ["pmoves/docker-compose.yml"],
    "action_required": "Apply SSL env neutralization to v1 services"
  }
  ```
- **Subscribers:** Node agents, PR monitor, Graphiti trail processors
- **Delivery:** Publish/subscribe (JetStream for persistence across agent sessions)

**`mesh.agent.<node>.capabilities.v1`**
- **Direction:** Published by node agents on session start
- **Purpose:** Announce cognitive specialization (mirrors `mesh.gpu.status.v1` for compute)
- **Config:** `pmoves/configs/node-agent-specialization.yaml`
- **Subscribers:** PR routing, task assignment coordinator

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

**`voice.ear.analysis.v1`**
- **Direction:** Published by Flute-Gateway prosodic ear (Phase A+)
- **Purpose:** Full prosodic analysis of incoming speech (pitch, energy, tempo, pauses)
- **Payload:**
  ```json
  {
    "f0_mean": 185.3,
    "energy_mean": 0.045,
    "estimated_bpm": 72.5,
    "boundaries": [{"type": "SENTENCE", "position_sec": 1.2}],
    "emotion": "calm",
    "duration_sec": 2.3
  }
  ```
- **Subscribers:** CHIT BPM encoder, Hyperdimensions (ear visualization)
- **Related:** See `PROSODIC_EAR_SPEC.md`

**`voice.ear.emotion.v1`**
- **Direction:** Published by Flute-Gateway prosodic ear (via media-audio-analyzer at :8082)
- **Purpose:** Emotion detection from incoming speech audio
- **Payload:**
  ```json
  {
    "emotion": "happy",
    "confidence": 0.87,
    "speaker_id": null,
    "duration_sec": 2.3
  }
  ```
- **Subscribers:** Agent persona selector (emotion-aware engine routing)
- **Related:** See `PROSODIC_EAR_SPEC.md`, media-audio-analyzer (HuBERT model)

## Voice Agent Relay Subjects

**`voice.agent.response.v1`** (relayed)
- **Direction:** voice-relay subscribes to `agentzero.task.result.v1`, filters `meta.voice_mode`, republishes
- **Publisher:** voice-relay service (port 8121)
- **Subscribers:** `voice_follow_agent.py` (local TTS), `voice_follow_cast_agent.py` (Google Cast)
- **Payload:**
  ```json
  {
    "platform": "agent-zero",
    "user_id": "user-id-from-meta",
    "message_id": "task-id",
    "response_text": "The spoken response text",
    "model_used": "model-name-or-null",
    "timestamp": "2026-03-14T12:00:00Z",
    "sources": [],
    "meta": {}
  }
  ```
- **Schema:** `pmoves/contracts/schemas/voice/agent.response.v1.schema.json`
- **Filter:** Only tasks with `meta.voice_mode: true` in the input payload are relayed
- **Profiles:** `cast`, `media`

## Cast TTS Subjects

**`voice.cast.completed.v1`**
- **Direction:** Published by cast-tts-gateway → Consumed by monitoring, Discord Publisher
- **Purpose:** Notify when TTS audio has been cast to a Chromecast/Google Home device
- **Payload:**
  ```json
  {
    "device_name": "Living Room Speaker",
    "device_ip": "192.168.1.x",
    "text_length": 128,
    "engine": "kokoro",
    "duration_ms": 3200,
    "timestamp": "2026-03-14T12:00:00Z"
  }
  ```
- **Subscribers:** Monitoring dashboards, Discord Publisher

**`voice.cast.failed.v1`**
- **Direction:** Published by cast-tts-gateway → Consumed by Discord Publisher
- **Purpose:** Notify when a TTS synthesis or device cast operation fails
- **Payload:**
  ```json
  {
    "stage": "tts_synthesis|device_cast|fallback_exhausted|queue_timeout",
    "reason": "httpx timeout on Ultimate-TTS",
    "retryable": true,
    "outcome": "fatal|partial",
    "timestamp": "2026-03-17T12:00:00Z",
    "device_name": "Living Room Speaker",
    "text": "Hello world",
    "provider_attempted": "ultimate_tts"
  }
  ```
- **Subscribers:** Discord Publisher, monitoring dashboards

**`voice.cast.health_alert.v1`**
- **Direction:** Published by cast-tts-gateway → Consumed by monitoring
- **Purpose:** Health alert when device or provider is degraded
- **Subscribers:** Monitoring dashboards, Agent Zero

**`device.cast.discovered.v1`**
- **Direction:** Published by cast-tts-gateway → Consumed by Agent Zero, Discord Publisher
- **Purpose:** Report device inventory changes after discovery scan
- **Payload:**
  ```json
  {
    "devices": [{"name": "Living Room Speaker", "ip": "192.168.1.50", "address": "192.168.1.50:8009"}],
    "count": 3,
    "timestamp": "2026-03-17T12:00:00Z",
    "new_devices": ["Office Speaker"],
    "lost_devices": [],
    "forced": true
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher

## Health & Fitness Subjects

> **Status:** Subjects defined and NATS wiring active in main compose (`NATS_URL` + `WGER_ENABLE_NATS`). n8n workflows defined but require activation and smoke testing before production use.

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

## Operations Subjects

**`ops.pr.trim.completed.v1`**
- **Direction:** Published by claude-code-cli (pr-hedge-trim tool) → Consumed by pr-monitor, Discord Publisher
- **Purpose:** Notify that a PR hedge trim cycle completed — review threads classified, fixed, and resolved
- **Payload:**
  ```json
  {
    "pr_number": 934,
    "repo": "POWERFULMOVES/PMOVES.AI",
    "agent_id": "claude-opus",
    "total_threads": 12,
    "actionable": 5,
    "design_decision": 2,
    "false_positive": 3,
    "nitpick": 2,
    "resolved": 10,
    "commit_sha": "abc123",
    "timestamp": "2026-03-15T12:00:00Z",
    "trail_signed": true
  }
  ```
- **Schema:** `pmoves/contracts/schemas/ops/pr.trim.completed.v1.schema.json`
- **Subscribers:** PR Monitor (pipeline chain), Discord Publisher
- **Delivery:** Publish/subscribe (advisory, no JetStream required)
- **Related:** Part of `pr-monitor-graphiti-chit` FlOO$ pairing chain

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

## AgentGym RL Training Subjects

### Training Lifecycle

**`agentgym.train.started.v1`**
- **Direction:** Published by EvoSwarm (evo-controller) → Consumed by AgentGym-RL coordinator, monitoring
- **Purpose:** Notify that RL training has been triggered
- **Payload:**
  ```json
  {
    "training_run_id": "run-abc123",
    "environment": "pmoves-hirag",
    "trigger_reason": "fitness_plateau|new_constellation|scheduled|fitness_degradation",
    "population_id": "pop-5",
    "algorithm": "ppo|grpo|rloo|reinforce++",
    "horizon": 10,
    "num_epochs": 25,
    "learning_rate": 1e-6,
    "geometry_config": {
      "cgp_fitness_weight": 0.2,
      "retrieval_quality_weight": 0.3,
      "task_success_weight": 0.4
    },
    "timestamp": "2026-03-14T12:00:00Z"
  }
  ```
- **Subscribers:** AgentGym-RL coordinator, observability dashboards

**`agentgym.train.completed.v1`**
- **Direction:** Published by EvoSwarm (evo-controller) → Consumed by AgentGym-RL coordinator
- **Purpose:** Training run finished — triggers auto-publish to HuggingFace Hub
- **Payload:**
  ```json
  {
    "training_run_id": "run-abc123",
    "trajectory_ids": ["traj-1", "traj-2"],
    "model_id": "Qwen3-8B-Instruct",
    "population_id": "pop-5",
    "fitness_metrics": {
      "avg_reward": 0.82,
      "task_success_rate": 0.91,
      "retrieval_quality": 0.78
    },
    "epoch": 50,
    "generation": 5,
    "timestamp": "2026-03-14T14:00:00Z"
  }
  ```
- **Subscribers:** AgentGym-RL coordinator (auto-publishes to HF), monitoring
- **Triggers:** `agentgym.model.published.v1`, `skills.pipeline.model-benchmark-viz.v1`

**`agentgym.model.published.v1`**
- **Direction:** Published by AgentGym-RL coordinator → Consumed by monitoring, Agent Zero
- **Purpose:** Model/dataset published to HuggingFace Hub
- **Payload:**
  ```json
  {
    "training_run_id": "run-abc123",
    "model_id": "Qwen3-8B-Instruct",
    "dataset_id": "pmoves/agentgym-run-abc123",
    "repo_url": "https://huggingface.co/datasets/pmoves/agentgym-run-abc123",
    "trajectory_count": 15,
    "source": "agentgym-rl-coordinator"
  }
  ```
- **Subscribers:** Agent Zero, Discord Publisher, observability dashboards

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

## GitHub Automation Subjects

### Branch Cleanup Service

**`github.branch.stale_detected.v1`**
- **Direction:** Published by github-branch-cleanup → Consumed by monitoring
- **Purpose:** Notify when stale branches are detected
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "feature/old-feature",
    "last_commit_days": 45,
    "stale_threshold_days": 30,
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.branch.auto_deleted.v1`**
- **Direction:** Published by github-branch-cleanup → Consumed by monitoring
- **Purpose:** Notify when branches are auto-deleted after PR merge
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "feature/completed-feature",
    "pr_number": 1234,
    "delete_reason": "pr_merged",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

### Issue Triage Service

**`github.issue.triage.completed.v1`**
- **Direction:** Published by github-issue-triage → Consumed by monitoring
- **Purpose:** Notify when issue triage is completed
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "issue_number": 567,
    "labels_added": ["bug", "high-priority"],
    "category": "bug_report",
    "confidence": 0.95,
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

### Branch Naming Service

**`github.branch.created.v1`**
- **Direction:** Published by GitHub webhooks → Consumed by github-branch-naming
- **Purpose:** Trigger branch name validation when new branches created
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "feature/new-feature",
    "action": "created",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.branch.validation.v1`**
- **Direction:** Published by github-branch-naming → Consumed by monitoring
- **Purpose:** Notify of branch name validation results
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "feature/new-feature",
    "is_valid": true,
    "category": "feature",
    "suggested_name": null,
    "reason": "Valid feature branch name",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.branch.rename_suggested.v1`**
- **Direction:** Published by github-branch-naming → Consumed by monitoring
- **Purpose:** Notify when branch rename is suggested
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "original_branch": "feature/bad-name",
    "suggested_branch": "feat/bad-name",
    "reason": "Invalid branch name format. Suggested: feat/bad-name",
    "dry_run": true,
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

### Cross-Repository Sync Service

**`github.crossrepo.sync.v1`**
- **Direction:** Published by github-crossrepo-sync → Consumed by monitoring
- **Purpose:** Notify when cross-repo sync operation starts
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "main",
    "status": "started",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.crossrepo.sync.completed.v1`**
- **Direction:** Published by github-crossrepo-sync → Consumed by github-crossrepo-pr, monitoring
- **Purpose:** Notify when cross-repo sync completes successfully
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "main",
    "submodules_synced": ["PMOVES-Agent-Zero", "PMOVES-Archon"],
    "submodules_failed": [],
    "duration_seconds": 5.2,
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.crossrepo.sync.failed.v1`**
- **Direction:** Published by github-crossrepo-sync → Consumed by monitoring
- **Purpose:** Notify when cross-repo sync fails
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "branch": "main",
    "error": "Failed to connect to GitHub API",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

### Cross-Repository PR Automation Service

**`github.crossrepo.pr.created.v1`**
- **Direction:** Published by github-crossrepo-pr → Consumed by monitoring
- **Purpose:** Notify when cross-repo PR is created
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "pr_number": 1234,
    "pr_url": "https://github.com/POWERFULMOVES/PMOVES.AI/pull/1234",
    "pr_type": "dependency_update",
    "base_branch": "main",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.crossrepo.pr.merged.v1`**
- **Direction:** Published by github-crossrepo-pr → Consumed by github-branch-cleanup, monitoring
- **Purpose:** Notify when cross-repo PR is merged
- **Payload:**
  ```json
  {
    "repo": "POWERFULMOVES/PMOVES.AI",
    "pr_number": 1234,
    "pr_type": "dependency_update",
    "merge_method": "squash",
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

**`github.crossrepo.pr.batch_completed.v1`**
- **Direction:** Published by github-crossrepo-pr → Consumed by monitoring
- **Purpose:** Notify when batch PR creation completes
- **Payload:**
  ```json
  {
    "pr_type": "dependency_update",
    "repos": ["PMOVES.AI", "PMOVES-Agent-Zero", "PMOVES-Archon"],
    "successful": 3,
    "failed": 0,
    "timestamp": "2026-03-13T12:00:00Z"
  }
  ```

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

## Agent Zero Task Coordination Subjects

> **Source:** Z890 gap analysis (2026-03-15). Previously undocumented.

**`agentzero.task.submit.v1`**
- **Direction:** Published by any agent → Consumed by Agent Zero
- **Purpose:** Submit task for orchestration
- **Subscribers:** Agent Zero (task queue)

**`agentzero.task.status.v1`**
- **Direction:** Published by Agent Zero → Consumed by requesting agent
- **Purpose:** Task status update (queued, running, blocked, etc.)

**`agentzero.task.complete.v1`**
- **Direction:** Published by Agent Zero → Consumed by requesting agent
- **Purpose:** Task completion notification with result payload

## PMOVES Agent Lifecycle & Task Management Subjects

> **Source:** Z890 gap analysis (2026-03-15). Agent-to-agent protocol subjects.

**`pmoves.agent.register.v1`** — Agent self-registration with Agent Zero
**`pmoves.agent.heartbeat.v1`** — Periodic agent liveness (all agents → Agent Zero)
**`pmoves.agent.deregister.v1`** — Agent graceful shutdown notification
**`pmoves.task.assign.v1`** — Task assignment to specific agent (Agent Zero → target)
**`pmoves.task.progress.v1`** — Task progress update (working agent → Agent Zero, UI)
**`pmoves.task.error.v1`** — Task error report (working agent → Agent Zero)
**`pmoves.task.cancel.v1`** — Task cancellation request (Agent Zero → working agent)
**`pmoves.a2a.request.v1`** — Agent-to-Agent direct request
**`pmoves.a2a.response.v1`** — Agent-to-Agent direct response
**`pmoves.skill.invoke.v1`** — Skill invocation request (any agent → skill executor)
**`pmoves.skill.result.v1`** — Skill execution result (skill executor → requester)
**`pmoves.config.update.v1`** — Configuration change broadcast (admin/UI → all agents)
**`pmoves.config.reload.v1`** — Force config reload (admin/UI → specific agent)
**`pmoves.log.agent.v1`** — Structured agent log entry (all agents → Loki/aggregator)
**`pmoves.metric.agent.v1`** — Agent-level metric report (all agents → Prometheus push)
**`pmoves.event.lifecycle.v1`** — Agent lifecycle event: start, stop, error (all agents → observability)

## Content Publishing Pipeline Subjects

**`content.publish.request.v1`** — Content publish request (UI/Agent → publisher services)
**`content.publish.complete.v1`** — Publish completed notification (publisher → UI/Agent)
**`content.moderation.v1`** — Content moderation check (content pipeline → moderation service)

## Analysis Subjects

**`analysis.topic.extract.v1`** — Topic extraction request (extract worker → LangExtract)
**`analysis.topic.result.v1`** — Topic extraction result (LangExtract → extract worker)

## Additional Voice Subjects

**`voice.cast.health_alert.v1`** — Health alert from cast-tts gateway (cast-tts → monitoring)

## Service Coordination Subjects

**`archon.crawl.request.v1`** — Web crawl request (Agent/UI → Archon)
**`archon.crawl.result.v1`** — Crawl result (Archon → requesting agent)
**`persona.publish.v1`** — Persona definition publish (Archon → Agent Zero)
**`persona.update.v1`** — Persona update (Archon → Agent Zero)
**`mesh.node.announce.v2`** — Node announcement v2 format (Mesh Agent → Agent Zero)
**`kb.upsert.request.v1`** — Knowledge base upsert (any agent → Hi-RAG)
**`kb.upsert.result.v1`** — Upsert confirmation (Hi-RAG → requesting agent)
**`compute.vllm.load.v1`** — Model load command (GPU orchestrator → vLLM worker)
**`compute.vllm.status.v1`** — vLLM instance status (vLLM worker → GPU orchestrator)
**`hf.model.download.v1`** — HuggingFace model download (any agent → HF downloader)
**`hf.model.ready.v1`** — Model download complete (HF downloader → requesting agent)
**`botz.skill.register.v1`** — Skill registration (BoTZ gateway → Agent Zero)
**`botz.skill.health.v1`** — Skill health status (BoTZ gateway → monitoring)
**`a2ui.event.v1`** — UI event for real-time display (any agent → A2UI NATS bridge)
**`a2ui.command.v1`** — User command from UI (UI → A2UI NATS bridge)

## CGP Version Naming Clarification

> **Note:** The apparent version mismatch between NATS subjects and payload specs is **intentional** — they operate at different layers:

| Context | Format | Example | Purpose |
|---------|--------|---------|---------|
| NATS transport subject | `geometry.cgp.v{N}` | `geometry.cgp.v1` | Subject routing (stays as-is) |
| Payload spec version | `chit.cgp.v{major}.{minor}` | `chit.cgp.v0.1`, `chit.cgp.v0.2` | Schema versioning inside packet |
| Internal canonical | `chit.cgp.v{major}.{minor}` | `chit.cgp.v1.0` | Documentation reference |

This is analogous to HTTP path versioning (`/api/v1/`) vs content-type versioning (`application/vnd.pmoves.cgp.v2+json`) — both are valid, complementary approaches.

## Agent Zero Task Coordination Subjects

> **Source:** Z890 gap analysis (2026-03-15). Previously undocumented.

**`agentzero.task.submit.v1`**
- **Direction:** Published by any agent -> Consumed by Agent Zero
- **Purpose:** Submit task for orchestration
- **Payload:**
  ```json
  {"task_id": "t-abc123", "type": "research|ingest|render", "priority": 5, "payload": {...}}
  ```

**`agentzero.task.status.v1`**
- **Direction:** Published by Agent Zero -> Consumed by requesting agent
- **Purpose:** Task status updates (queued, running, completed, failed)

**`agentzero.task.result.v1`**
- **Direction:** Published by Agent Zero -> Consumed by requesting agent
- **Purpose:** Task completion with result payload

## Tailscale Mesh Networking Subjects

> **Source:** Tailscale infra bootstrap (2026-03-15). Multi-host mesh networking.

### Node Lifecycle

**`mesh.node.announce.v1`**
- **Direction:** Published by mesh-agent on each node -> Consumed by all nodes
- **Purpose:** Periodic node presence announcement (every 15s)
- **Payload:**
  ```json
  {"node_id": "z890", "hostname": "pmoves-z890", "tailscale_ip": "100.x.y.z", "capabilities": ["gpu", "tts"], "ts": 1709568000}
  ```

**`mesh.node.health.v1`**
- **Direction:** Published by mesh-agent -> Consumed by monitoring
- **Purpose:** Node health metrics (CPU, memory, disk, GPU utilization)

**`mesh.node.capability.v1`**
- **Direction:** Published by mesh-agent -> Consumed by orchestrator
- **Purpose:** Capability registration/update (available services, GPU models loaded)

**`mesh.node.deregister.v1`**
- **Direction:** Published by mesh-agent on shutdown -> Consumed by all nodes
- **Purpose:** Graceful node departure from mesh

### Tailscale VPN Status

**`mesh.tailscale.status.v1`**
- **Direction:** Published by mesh-agent -> Consumed by monitoring
- **Purpose:** Tailscale connection status (connected, needs-login, stopped)

**`mesh.tailscale.acl.v1`**
- **Direction:** Published by admin tooling -> Consumed by mesh-agent
- **Purpose:** ACL policy update notification

**`mesh.tailscale.dns.v1`**
- **Direction:** Published by mesh-agent -> Consumed by service discovery
- **Purpose:** MagicDNS hostname resolution updates

**`mesh.tailscale.route.v1`**
- **Direction:** Published by mesh-agent -> Consumed by routing layer
- **Purpose:** Subnet route advertisement changes

**`mesh.tailscale.key.expiry.v1`**
- **Direction:** Published by mesh-agent -> Consumed by ops alerting
- **Purpose:** Auth key expiry warning (7-day, 1-day, expired)

### Operations Monitoring

**`ops.tailscale.node.v1`**
- **Direction:** Published by ops tooling -> Consumed by dashboard
- **Purpose:** Node inventory changes (added, removed, renamed)

**`ops.tailscale.health.v1`**
- **Direction:** Published by health-check cron -> Consumed by alerting
- **Purpose:** Fleet-wide Tailscale health summary
