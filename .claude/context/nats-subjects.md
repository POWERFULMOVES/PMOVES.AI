# PMOVES.AI NATS Event Subjects Catalog

Comprehensive reference of all NATS message subjects used for event-driven communication across PMOVES services.

> **See Also:** For GEOMETRY BUS subjects (`tokenism.*`, `geometry.*`), see [geometry-nats-subjects.md](./geometry-nats-subjects.md)

## NATS Configuration

- **Server:** `nats://localhost:4222`
- **JetStream:** Enabled for persistence
- **Version:** 2.10-alpine

## P7 Room and Session Control

P7 separates command subjects from emitted facts:

| Subject | Role | Direction |
|---|---|---|
| `p7.nats.launch` | Start a room session (`room_id` or legacy `room`) | client -> P7 |
| `p7.nats.session` | Session or stage command (`pause`, `resume`, `end`, `archive`, `stage`) | client -> P7 |
| `p7.nats.launch.v1`, `p7.nats.session.v1` | Compatibility aliases for existing PBnJ hooks; payload contract is unchanged | client -> P7 |
| `p7.room.session.started.v1` | Session-start fact | P7 -> consumers |
| `p7.room.checkpoint.v1` | Session checkpoint fact | P7 -> consumers |
| `p7.room.session.ended.v1` | Session-ended fact | P7 -> consumers |
| `p7.room.stage.changed.v1` | Persistent room-stage transition fact | P7 -> consumers |
| `p7.room.command.failed.v1` | Rejected or malformed command fact | P7 -> operators |

`room.stage` is `rehearsal | live | review | archive`. `session_state` is
`planned | active | paused | ended | archived`. A transition to `live` is
CHIT signing-card gated. Every stage transition requires durable Supabase audit
persistence and confirmed NATS stage-fact delivery.

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
- **Direction:** Published by cipher-api (PMOVES shim `src/pmoves/nats-emitter.ts`) → Consumed by monitoring, observability
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
- **Direction:** Published by cipher-api (PMOVES shim `src/pmoves/nats-emitter.ts`) → Consumed by monitoring
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
- **Direction:** Published by cipher-api (PMOVES shim `src/pmoves/nats-emitter.ts`) → Consumed by monitoring
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

## CLAW Provider Lifecycle Subjects

**`claw.provider.activated.v1`**
- **Direction:** Published by provider activation tooling → Consumed by CLAW orchestration, monitoring
- **Purpose:** Announce that a provider key was activated and routing was updated
- **Payload:**
  ```json
  {
    "node_id": "pmoves-4090",
    "provider": "anthropic",
    "env_var": "ANTHROPIC_API_KEY",
    "models_added": ["claude_sonnet_4"],
    "functions_updated": ["agent_zero", "coding_claude_fallback"],
    "coding_stacks_activated": ["claude_code"],
    "vram_warnings": [],
    "timestamp": "2026-03-28T16:00:00Z",
    "success": true
  }
  ```
- **Subscribers:** CLAW routing dashboards, mesh observers, Discord publisher

**`claw.provider.deactivated.v1`**
- **Direction:** Published by provider activation tooling → Consumed by CLAW orchestration, monitoring
- **Purpose:** Announce that a provider key was removed and dependent lanes should rebalance
- **Payload:**
  ```json
  {
    "node_id": "pmoves-4090",
    "provider": "anthropic",
    "env_var": "ANTHROPIC_API_KEY",
    "models_removed": ["claude_sonnet_4"],
    "timestamp": "2026-03-28T18:00:00Z",
    "success": true
  }
  ```
- **Subscribers:** CLAW routing dashboards, mesh observers, Discord publisher

## CLAW Agent Delegation Subjects

**`claw.task.assign.v1`**
- **Direction:** Published by orchestrating agents → Consumed by target node agent runtime
- **Purpose:** Cross-node agent-to-agent task delegation (cascades, handoffs, wave assignments)
- **Payload:**
  ```json
  {
    "from": "pmoves-4090",
    "to": "pmoves-spark",
    "task": "cascade-wave-B",
    "files_released": ["pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"],
    "after_pr": [1504, 1506, 1507],
    "note": "Wave A complete. SPARK may open feat/spark-tz-glm5-minimax-sync PRs."
  }
  ```
- **Subscribers:** Target node agent runtime (SPARK, 5090, etc.)
- **Known Road:** `make -C pmoves nats-pub SUBJECT=claw.task.assign.v1 PAYLOAD='...'`
  (uses the pinned `natsio/nats-box:0.14.5` toolbox image on `pmoves_bus`; run on the node where NATS is local
  or where `NATS_URL` reaches the hub)
- **Note:** Not JetStream — fire and forget. Target agent must be subscribed at publish time.
- **Persistent inbox:** `make -C pmoves nats-agent-inbox` runs
  `pmoves/tools/nats_agent_inbox.py`, which subscribes to `claw.task.assign.v1`,
  `branch.>`, `chit.>`, `p7.>`, and `owner.presence.>` and writes a local JSONL
  inbox outside the repo tree by default. The target uses `uv run --script` so
  `nats-py` is resolved without mutating host Python. Use this on the target node
  when a durable receive path is needed before a full agent runtime is online.
- **Current 5090-CODEX receive-path snapshot (2026-05-21T04:54Z):**
  `pmoves-nats-1` reported 21 connections via `connz?subs=1` and 0 subscriptions matching
  `claw`, `5090`, `codex`, `task`, `chit`, `pinokio`, `branch`, or `owner.presence`.
  Treat direct receive on `claw.task.assign.v1` as unproved until the persistent
  inbox or an equivalent agent runtime is running and visible in `connz?subs=1`.
  The same snapshot observed no receiver for the branch trail / CHIT / P7 receive-path patterns checked.

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

**`pmoves.space.action.v1`**
- **Direction:** Published by Space-Agent bridge (on inbound `/api/pmoves_bridge` POST)
- **Purpose:** Surface space CRUD actions (create_space, update_widget, delete_space, list_spaces, read_space) onto the bus for downstream listeners
- **Payload:**
  ```json
  {
    "action": "create_space",
    "username": "pilot-id",
    "spaceId": "uuid-or-slug",
    "request_id": "uuid",
    "timestamp": "2026-04-25T12:00:00Z"
  }
  ```
- **Subscribers:** Agent Zero (for orchestration), audit/observability sinks

**`pmoves.space.event.v1`**
- **Direction:** Published by Space-Agent on customware lifecycle changes
- **Purpose:** Notify subscribers when space state advances (mutation succeeded, widget updated, space deleted)
- **Payload:**
  ```json
  {
    "event": "widget_updated",
    "username": "pilot-id",
    "spaceId": "uuid-or-slug",
    "widgetId": "widget-name",
    "timestamp": "2026-04-25T12:00:00Z"
  }
  ```
- **Subscribers:** UI feeds, attestation workers (Stage 8 token-stub watches for `event` to mint work-receipts)

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

**`agent.identity.altered.v1`**
- **Direction:** Built by `sign_trail.py --alter` (payload only, no NATS client) → Published by BoTZ gateway or trail ingestor on behalf of CLI → Consumed by monitoring, Graphiti trail
- **Purpose:** Notify that an agent selected an alter identity for a trail entry
- **Payload:**
  ```json
  {
    "agent_id": "4090-claude",
    "selected_alter": "4090-field",
    "alter_glyph": "◎",
    "alter_color": "#065F46",
    "timestamp": "2026-03-24T12:00:00Z"
  }
  ```
- **Subscribers:** Agent trail processors, observability dashboards, identity analytics
- **Delivery:** Publish/subscribe (advisory, no JetStream required)

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

### Fleet Enrollment & RustDesk Audit

> **Source:** z890 fleet enrollment rollout (2026-03-27). RustDesk enrollment + KVM2 audit watcher.

**`fleet.enrollment.created.v1`**
- **Direction:** Published by `generate-enrollment.py` -> Consumed by audit/notification subscribers
- **Purpose:** Record that a time-limited RustDesk/Tailscale enrollment token was generated
- **Payload:**
  ```json
  {
    "token_id": "tok-abc123",
    "role": "owner|partner|guest",
    "device_name": "Pixel 10",
    "issued_at": "2026-03-27T18:00:00Z",
    "expires_at": 1774638000,
    "signed": true
  }
  ```
- **Subscribers:** Discord Publisher, observability dashboards, future fleet admin UI

**`fleet.device.registered.v1`**
- **Direction:** Published by `fleet-audit-watcher.sh` on KVM2 -> Consumed by monitoring/admin flows
- **Purpose:** Notify that RustDesk `hbbs` observed a new client registration (`update_pk`)
- **Payload:**
  ```json
  {
    "event": "device.registered",
    "ts": "2026-03-27T18:05:00Z",
    "client_id": "123456789",
    "raw": "hbbs update_pk 123456789 ..."
  }
  ```
- **Subscribers:** Discord Publisher, monitoring dashboards, future approval workflow

**`fleet.audit.connection.v1`**
- **Direction:** Published by `fleet-audit-watcher.sh` on KVM2 -> Consumed by monitoring
- **Purpose:** Stream relay connection, disconnect, and timeout activity from `hbbs` / `hbbr`
- **Payload:**
  ```json
  {
    "event": "relay.connection|connection.closed",
    "ts": "2026-03-27T18:06:00Z",
    "raw": "2026-03-27T18:06:00Z hbbr relay connection ..."
  }
  ```
- **Subscribers:** Monitoring dashboards, Discord Publisher

**`fleet.audit.heartbeat.v1`**
- **Direction:** Published by `fleet-audit-watcher.sh` every 5 minutes -> Consumed by monitoring
- **Purpose:** Liveness signal for the KVM2 fleet watcher
- **Payload:**
  ```json
  {
    "event": "heartbeat",
    "ts": "2026-03-27T18:10:00Z",
    "service": "fleet-audit-watcher",
    "node": "kvm2"
  }
  ```
- **Subscribers:** Monitoring dashboards, ops alerts

**`fleet.device.approved.v1`**
- **Direction:** Reserved for admin workflow / approval tooling
- **Purpose:** Record that a newly registered device was approved for continued fleet access
- **Subscribers:** Discord Publisher, audit trails, future fleet admin UI

**`fleet.device.blocked.v1`**
- **Direction:** Reserved for admin workflow / approval tooling
- **Purpose:** Record that a device was denied or revoked from fleet access
- **Subscribers:** Discord Publisher, audit trails, future fleet admin UI

## Voice & Prosodic Subjects

## Tokenism Simulator Subjects

**Service mapping:** Tokenism Simulator listens on host port `8103` mapped to container port `8100`; health endpoint is `GET /healthz`.

**`tokenism.cgp.ready.v1`**
- **Direction:** Published by Tokenism Simulator -> Consumed by geometry bus workers, extract/deepresearch consumers, and monitoring
- **Purpose:** Announce a CHIT geometry packet ready for downstream attribution and traversal
- **Schema:** `pmoves/contracts/schemas/tokenism/cgp.ready.v1.schema.json`

**`tokenism.simulation.result.v1`**
- **Direction:** Published by Tokenism Simulator -> Consumed by calibration, model-fitness, and monitoring lanes
- **Purpose:** Economic simulation result metadata

**`tokenism.calibration.result.v1`**
- **Direction:** Published by Tokenism Simulator -> Consumed by Tokenism calibration observers
- **Purpose:** Calibration output for simulation/evaluation feedback

**`tokenism.export.result.v1`**
- **Direction:** Published by the ToKenism→Firefly exporter (`PMOVES-ToKenism-Multi/integrations/firefly/export_sim_to_firefly.ts` with `--nats`; HTTP wrapper planned per `docs/superpowers/specs/2026-07-11-tokenism-wealth-demo-wiring.md` G1) -> Consumed by monitoring; pre-authorized in the `tokenism.room.exchange` room manifest publish allow-list
- **Purpose:** Result of exporting a simulation run into the PMOVES-Wealth (Firefly III) ledger — account/transaction counts, dry-run flag, report refs

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

## Voice Sampler Subjects

Media-sourced voice references (VOICE_SAMPLER_SPEC.md; voice-sampler service, port 8124).
Voice references are personal data: payloads carry JuiceFS keys only, never audio.

**`voice.sample.candidates.v1`**
- **Publisher:** voice-sampler (after diarize + segment cut + JuiceFS stage)
- **Subscribers:** Voice Vault room app (audition lanes)
- **Payload:** `{batch_id, bucket, prefix, speakers: [{speaker, clips: [{key, start, end, duration}]}], room, persona_id, source: {bucket, key}, diarization_model, timestamp}`

**`voice.reference.approved.v1`**
- **Publisher:** Voice Vault room app (owner-only pub-gate decision)
- **Subscribers:** voice-sampler (executes PUBLISH: JuiceFS refs path + OmniVoice catalog + optional flute clone register)
- **Payload:** `{batch_id, room, persona_id, owner_id, catalog_id?, clips: [candidate keys], chit_sig}`
- **Gate:** sampler refuses unless `owner_id` matches `VOICE_SAMPLER_OWNER_ID` and `chit_sig` present (fail closed; full CHIT verification is the follow-up)

**`voice.reference.published.v1`**
- **Publisher:** voice-sampler (ANNOUNCE after successful publish)
- **Subscribers:** room surfaces, H3/Maestro reference pickers
- **Payload:** `{persona_id, catalog_id, room, refs: [keys], source_batch, chit_sig, timestamp}`
- **Profiles:** `workers`, `voice`

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

**`ops.submodule.update.detected.v1`**
- **Direction:** Published by GitHub Actions (submodule-update-check workflow) → Consumed by Publisher-Discord, monitoring
- **Purpose:** Notify that one or more tracked upstream submodules have new commits and auto-update PRs were created
- **Payload:**
  ```json
  {
    "workflow": "submodule-update-check",
    "updated": 2,
    "timestamp": "2026-04-12T06:00:00Z"
  }
  ```
- **Publisher:** `.github/workflows/submodule-update-check.yml` (weekly + manual)
- **Subscribers:** Publisher-Discord (alert team to pending PRs), ops monitoring
- **Delivery:** Best-effort (publish only if `NATS_URL` secret is configured on the runner)
- **Related:** See `pmoves/docs/operations/UPSTREAM_UPDATE_RUNBOOK.md` for the full update flow

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

## Fordham Hill Community Room Subjects

> **Source:** `fordham.room.community` (stage `rehearsal`, PR #1993). The 4 dedicated
> agents (onboarding / transaction / creator / voice) + the `fordham-steward` coordinator.
> Every dollar/vote/governance payload is **DRAFT — REQUIRES LEGAL REVIEW**; transparency /
> auditable records only, never accusations. Two subjects are marked **DRAFT** — not yet
> emitted; run `pmoves-nats-subject-audit` before their publishers go live.

**`fordham.onboarding.request.v1`**
- **Direction:** Published by the room UI / steward → Consumed by `fordham-onboarding`
- **Purpose:** Request to enroll a resident onto the mesh + eligible-voter roll (record-only; consent required)

**`fordham.roll.updated.v1`**
- **Direction:** Published by `fordham-onboarding` → Consumed by `fordham-creator` (read-only), roster tooling
- **Purpose:** A resident was recorded on the eligible-voter roll (roll is 1-of-N today; DRAFT-legal)

**`fordham.dues.received.v1`**
- **Direction:** Published by dues intake → Consumed by `fordham-transaction`
- **Purpose:** A pooled member due was received; triggers a deterministic Firefly co-op ledger entry

**`fordham.ledger.entry.v1`**
- **Direction:** Published by `fordham-transaction` → Consumed by `fordham-creator` (read-only)
- **Purpose:** A double-entry co-op ledger posting. All figures MODELED/illustrative until an ADOPTED RATE is set

**`fordham.surplus.updated.v1`**
- **Direction:** Published by `fordham-transaction` → Consumed by dashboard/creator
- **Purpose:** Community surplus recomputed (the saved dollars the capacity lane frees). DRAFT-legal-accounting

**`fordham.dashboard.request.v1`**
- **Direction:** Published by the room → Consumed by `fordham-creator` + `fordham-voice`
- **Purpose:** Request to (re)generate the pilot dashboard or a spoken read-out of its state

**`fordham.artifact.published.v1`**
- **Direction:** Published by `fordham-creator` → Consumed by the room / notebook
- **Purpose:** A resident-facing material or dashboard snapshot was published (DRAFT watermark carried on every figure)

**`fordham.voice.delivered.v1`**
- **Direction:** Published by `fordham-voice` → Consumed by the room
- **Purpose:** A spoken summary was delivered (with an audible draft/pending-legal disclaimer on any figure)

**`fleet.enroll.token.v1`** — **DRAFT (not yet emitted)**
- **Direction:** Published by `fordham-onboarding` (`fleet:enroll`) → Consumed by fleet/audit subscribers
- **Purpose:** A CHIT-signed device enrollment token for a resident joining the mesh. Complements the existing
  `fleet.enrollment.created.v1` (RustDesk/Tailscale) — this is the room-scoped mesh-join variant

**`voice.synth.request.v1`** — **DRAFT (not yet emitted)**
- **Direction:** Published by `fordham-voice` → Consumed by Flute-Gateway / Ultimate-TTS
- **Purpose:** Request prosodic voice synthesis for a resident-facing spoken read-out (FlOO$ suit)

**Shared subjects this room reuses** (defined elsewhere, listed for traceability):
`room.session.updated.v1` (room events) · `chit.signed.v1` (enrollment/dues/trail receipts) ·
`vote.signed.v1` (governance receipts — **SCAFFOLDED**, gated `enabled:false` in rehearsal) ·
`tokenism.prosodic.bpm.v1` (voice prosody, see Voice & Prosodic Subjects).

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

**`branch.<path-segments>.trail.v1`**
- **Direction:** Published by `pmoves-ci-bot` (GH Actions) → Consumed by monitoring / audit lane
- **Purpose:** §9.4 branch lifecycle CHIT trail — emits a HMAC-signed entry on branch create,
  PR link, merge, and delete. Subject uses dot-separated branch path segments
  (e.g. `branch.feat.my-feature.trail.v1`). Implemented by `pmoves/services/common/branch_trail.py`
  (Layer 1 emit primitive) and `.github/workflows/branch-trail-emit.yml` (Layer 4 GH Actions).
- **Payload:**
  ```json
  {
    "spec": "branch-trail-v1",
    "branch": "feat/my-feature",
    "event": "create",
    "sha": "abc1234",
    "agent_id": "pmoves-ci-bot",
    "signing_card_id": "00000000-0000-4000-8000-000000000035",
    "ecosystem": "github",
    "timestamp": "2026-05-12T00:00:00Z"
  }
  ```
- **Notes:** Signing key delivered via `CHIT_PASSPHRASE` / `CHIT_SIGNING_KEY` repo secrets.
  Best-effort — publish failure logs and exits 0 without blocking branch operations.
  Gated against fork PRs to prevent RCE on the tailnet-connected ai-lab runner.
- **Current 5090-CODEX receive-path snapshot (2026-05-21T04:54Z):**
  `connz?subs=1` on `pmoves-nats-1` showed no live subscription matching `branch`
  or `chit`. Branch trail publish remains CI-owned; live branch/CHIT receive needs a
  persistent audit subscriber, `make -C pmoves nats-agent-inbox`, or an equivalent
  MCP/NATS bridge before it can be treated as online.

**`branch.<branch>.a2ui.trail.v1`**
- **Direction:** Published by the local PostToolUse hook `.claude/hooks/a2ui-crew-trail.sh`
  (dev-time, best-effort) → Consumed by monitoring / audit lane
- **Purpose:** Dev-time A2UI lane branch trail — emits an advisory event when an A2UI lane
  file is edited (web components, `a2ui-*` contracts, compose tools, tenant templates).
  Subject uses dot-separated branch path segments (e.g. `branch.feat.a2ui-v02.a2ui.trail.v1`).
  Sibling of the shift-crew lane hook `.claude/hooks/shift-crew-trail.sh`
  (`branch.<branch>.trail.v1`); different lane, different subject.
- **Payload:**
  ```json
  {
    "event": "a2ui_edit",
    "file": "pm-ballot.js",
    "path": "pmoves/web-components/pm-ballot/pm-ballot.js",
    "pattern": "pmoves/web-components/",
    "branch": "feat/a2ui-v02-impl-review-style",
    "node": "<hostname>",
    "ts": "2026-07-16T00:00:00Z"
  }
  ```
- **Notes:** ADVISORY / UNSIGNED — unlike the CI `branch.<path-segments>.trail.v1` §9.4
  trail, this payload carries NO `spec`, NO `signing_card_id`, and NO HMAC. Audit-lane
  consumers of `branch.>` MUST skip it for signature verification. Best-effort: publish
  failure is silent and the hook always exits 0; a durable local record is appended to
  the gitignored `pmoves/docs/logs/a2ui_branch_trail.jsonl` regardless.

**`village.gate.result.v1`**
- **Direction:** Staged by `pmoves/tools/village_gate.py` (CI + local `make village-gate`) → Consumed by monitoring / signoff audit lane
- **Purpose:** P0 Evaluation Gates — verdict of the automated evaluator gate that runs
  quality-threshold checks (`pmoves/configs/village_gate_thresholds.yaml`) before
  AGNOTE4482 Village Rule signoff. The envelope is written into the verdict JSON
  (`pmoves/docs/logs/village_gate_latest.json`) as a STAGED publish — emit via
  `pmoves-nats-mcp` when wired, same staged pattern as the archon mint commands.
- **Payload:**
  ```json
  {
    "gate": "village-gate",
    "hard_pass": true,
    "failed_checks": [],
    "advisory_failures": ["docs-freshness"]
  }
  ```
- **Notes:** Status STAGED (no live CI publisher yet — mirrors the pre-#1462 state of
  `branch.<path-segments>.trail.v1`). Prometheus exposure is via textfile-collector
  exposition (`--prom-textfile`), not a pushgateway.

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

**`archon.crawl.request.v1`** — ⚠️ **STUB — does not crawl.** Web crawl request (Agent/UI → Archon)
**`archon.crawl.result.v1`** — ⚠️ **STUB — echoes the request.** Crawl result (Archon → requesting agent)

> **Read this before building against the crawl pair.** A handler does exist —
> `ArchonOrchestrator` (`pmoves/services/archon/orchestrator.py:22`) subscribes to
> `archon.crawl.request[.v1]` — but `_process_crawl` takes the `metadata` dict **from the
> request message** and republishes it unchanged as `extracted_text` and `fragments`,
> stamped `"status": "completed"`. Nothing fetches the URL: there is no HTTP client,
> headless browser, or crawler anywhere under `pmoves/services/archon/`.
>
> So a consumer receives a success result whose content is whatever the *requester*
> supplied. That is a stronger failure than an unimplemented subject — an unimplemented
> subject times out and you notice; this one reports completion. The existing tests are not
> thin — `test_archon_orchestrator.py:206-264` covers the crawl state machine
> (`queued -> processing -> completed`), result publication on `archon.crawl.result.v1`, and
> the result payload's shape. What none of them assert is **network retrieval**: no test
> checks that the URL was ever fetched or that the returned content came from it.
> `test_crawl_result_payload_structure` in fact demonstrates the defect — it feeds
> `metadata.fragments = ["a", "b"]` in the request and asserts the *result* carries the same
> `["a", "b"]` back. That round-trip passes whether or not a crawler exists, which is why
> the gap survived a well-covered suite.
>
> **Retire-vs-implement is an open operator decision**, parked and delegated to Archon in
> `AGNOTE4482PHI.t1.md` (`ACK::Z890-CLAUDE::CONTROL-ITEMS-RESOLVED-2026-08-08`). This entry
> does not pre-empt it — it only stops the catalog from advertising a crawler that is not
> there.
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
**`a2ui.event.v1`** — ⛔ **NEVER IMPLEMENTED.** UI event for real-time display (any agent → A2UI NATS bridge)
**`a2ui.command.v1`** — ⛔ **NEVER IMPLEMENTED.** User command from UI (UI → A2UI NATS bridge)

> **These two have never existed in code — not now, not in any commit.** A history-wide
> pickaxe search (`git log -S` across `*.py *.ts *.tsx *.js *.yml *.yaml *.json`) returns
> nothing for either name. The catalog lists the A2UI NATS bridge as their endpoint;
> `bridge.py` has never referenced them.
>
> Both entered on **2026-03-15** via `pmoves/docs/reviews/nats-subject-catalog-gaps.md`, a
> security-audit handoff whose premise was that *"30+ NATS subjects were found
> **undocumented**"* and whose action was to register them. For these two the premise did
> not hold — they were intent written up as discovery, then registered as fact. Full
> trace: `pmoves/docs/audit/A2UI_INTEGRATION_AUDIT_2026-08-14.md` § F5.
>
> The subjects the A2UI renderer **actually** publishes are `a2ui.render.completed.v1`,
> `ingest.file.added.v1`, and `agent.graphiti.signed.v1`.

## Archon Mint Subjects

> The PMOVES agent-factory contract. Ritual: `.claude/commands/archon/{mint-agent,mint-skill,creator-onboard}.md`.
> QA gate: `.claude/agents/archon-qa-agent.md` — `archon.qa.result.v1` **blocks** `archon.mint.confirmed.v1`.
> Design review + landing plan: `pmoves/docs/handoffs/ARCHON_MINT_CONTRACT_REVIEW.md`.
>
> **Status: contract registered, publishers not yet implemented.** Archon 0.6.0 (TS) carries no NATS
> client; these subjects go live with the planned `archon-nats-bridge`. Registered here ahead of
> implementation because `archon-qa-agent` check 3 rejects any manifest referencing an unregistered
> subject — including the mint contract's own.

**`archon.mint.agent.v1`** — Proposed agent mint spec (mint ritual → Archon factory)
- **Direction:** Published by `/archon:mint-agent` → Consumed by Archon factory + `archon-qa-agent`
- **Purpose:** Submit an `AgentMintSpec` for scaffolding. Full manifest schema (metadata + spec with
  role, team_ref, node_affinity, model routing, capabilities, skills, nats, guardrails) in
  `pmoves/docs/pilots/fordham-hill/05-room-agents-mint-specs.md`.
- **Payload:**
  ```json
  {"agent_id": "<uuid>", "agent_name": "geometry-curator", "room_id": "4090-field.room.control", "owning_persona": "delivery-agent", "manifest_url": "https://archon.pmoves.ai/<id>", "ts": "2026-08-01T00:00:00Z"}
  ```

**`archon.qa.result.v1`** — Blocking QA verdict (archon-qa-agent → Archon factory)
- **Direction:** Published by `archon-qa-agent` → Consumed by Archon factory
- **Purpose:** Gate between `mint.agent` and `mint.confirmed`. Seven checks: schema, NATS subject
  registration + branded namespace, CHIT tier, name collision, branded defaults/no-SaaS, OAuth identity,
  env tier. **Archon must never publish `mint.confirmed` without an explicit `pass`.**
- **Payload (pass):**
  ```json
  {"status": "pass", "agent": "geometry-curator", "checks": ["schema", "nats", "chit", "collision", "branded", "auth", "tier"]}
  ```
- **Payload (fail):** `{"status": "fail", "agent": "<name>", "reasons": ["<reason with path:line>"]}`

**`archon.mint.confirmed.v1`** — Mint confirmation (Archon → fleet)
- **Direction:** Published by Archon factory → Consumed by registry consumers / monitoring
- **Purpose:** Agent is live and registered. Emitted only after `archon.qa.result.v1` = pass.
- **Payload:**
  ```json
  {"agent_id": "<uuid>", "confirmed_at": "2026-08-01T00:00:00Z"}
  ```

**`archon.mint.skill.v1`** — Skill mint (mint ritual → Archon)
- **Direction:** Published by `/archon:mint-skill` → Consumed by Archon factory
- **Payload:**
  ```json
  {"skill_id": "<uuid|null>", "skill_name": "pmoves-chit-sign", "path": ".claude/skills/pmoves-chit-sign/SKILL.md", "user_invocable": true, "owning_persona": "delivery-agent", "ts": "2026-08-01T00:00:00Z"}
  ```

**`archon.mint.creator.v1`** — Human creator onboarding (mint ritual → Archon)
- **Direction:** Published by `/archon:creator-onboard` → Consumed by Archon factory
- **Purpose:** Provision a human creator identity. `creator_id` is the Supabase `auth.users.id`; email is
  carried as a SHA-256 hash, never in clear.
- **Payload:**
  ```json
  {"creator_id": "<supabase auth.users.id>", "handle": "darkxside", "role": "operator", "email_hash": "<sha256>", "provider": "google", "default_room": "4090-field.room.control", "github_username": "<optional>", "ts": "2026-08-01T00:00:00Z"}
  ```

## Token Work Attestation Subjects

> The input side of the economy: cryptographic proof that a contributor performed a unit of work.
> Schema: `pmoves/contracts/schemas/token/work.attested.v1.schema.json`. Chain analysis:
> `pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md` §6a.
>
> **Status: contract + recorder service + ledger migration all exist; NONE of it is deployed.**
> `pmoves/services/token-stub/app.py` (dry-run recorder) is in no compose file, and
> `pmoves/supabase/migrations/20260425000300_work_attestations.sql` has never been applied — the relation
> `pmoves_core.work_attestations` does not exist on the live Supabase.

**`token.work.attested.v1`** — Signed work attestation (contributor/agent → attestation recorder)

- **Direction:** Published on completion of a unit of work → Consumed by `token-stub` (and, once wired, the
  attribution stage)
- **Purpose:** Establish *who did what*, verifiably, as the input to attribution and eventually settlement.
- **Crypto note:** this contract specifies **Ed25519** (asymmetric, 128-hex signature) — deliberately
  different from the live CHIT trail's **symmetric HMAC** with a single operator-held passphrase.
  Asymmetric is the right model for attribution a contributor should be able to prove independently. The
  divergence is unresolved and needs an explicit decision, not a silent merge.
- **Identity note:** `contributor` is a UUID that lands in `work_attestations.contributor_id`, which the
  migration's RLS policy binds to Supabase `auth.uid()`. **This is the only payable human anchor in the
  repo** — the Archon mint contract's `creator_id`/`owning_persona` is a separate, unimplemented model.
- **Payload:**
  ```json
  {
    "work_id": "<uuid>",
    "contributor": "<uuid — Supabase auth.users.id>",
    "attestation_sig": "<128 hex chars, Ed25519>",
    "merkle_root": "0x<64 hex>",
    "attested_at": "2026-08-01T00:00:00Z",
    "metadata": {}
  }
  ```

## CHIT Economics Subjects

> Cost/usage metering for the tokenomics layer. Design rationale and the full value-chain analysis:
> `pmoves/docs/handoffs/PMOVES_VALUE_CHAIN_REVIEW.md` §2, §8.
>
> **Status: contract registered, publisher not yet implemented.** Registered ahead of code deliberately —
> `archon-qa-agent` check 3 rejects manifests referencing unregistered subjects, and this is the subject an
> economically-accountable agent will declare.

**`chit.economics.usage.v1`** — Content-free LLM usage/cost record (any metered service → economics consumers)

- **Direction:** Published per inference by the metering shim → Consumed by settlement / audit / dashboards
- **Purpose:** Make agent cost measurable **without recording what was said.** This exists because
  TensorZero's own observability is disabled by policy (`pmoves/tensorzero/config/tensorzero.toml:8-30`,
  Cyber Defence Initiative 2026-04-25): enabling it auto-creates ClickHouse tables holding full prompt and
  response text with no TTL, which violates Data Retention Policy T0 and creates a warrantable store of
  user content. Tokenomics needs **counts, not content** — so this subject carries counts only and trips
  none of the six documented re-enable conditions.

- **HARD INVARIANT — this payload MUST NOT carry prompt text, response text, message content, tool
  arguments, or any user-supplied string.** Only identifiers, counts, and money. A publisher that adds a
  content field re-creates exactly the retention hazard the policy was written to prevent. Treat any such
  field as a blocking review failure.
  > ⚠️ **Currently prose-only — NOT yet machine-enforced.** The envelope path validates a payload only when
  > the subject is registered in `pmoves/contracts/topics.json` with a schema. Until
  > `pmoves/contracts/schemas/chit/economics.usage.v1.schema.json` exists with
  > `"additionalProperties": false` and a matching `topics.json` entry, this invariant can be violated
  > without any failure. **Land the schema before the first publisher.** (Blocked on an operator-set
  > `KNOWN_ROAD=schema:...` — `pmoves/contracts/schemas/` is a damage-control read-only path.)

- **Payload:**
  ```json
  {
    "agent_name": "fordham-transaction",
    "tensorzero_function": "pmoves_worker_glm",
    "model_name": "glm-5.2",
    "provider_name": "zai",
    "node": "z890",
    "prompt_tokens": 1840,
    "completion_tokens": 412,
    "estimated_cost_usd": 0.0031,
    "ts": "2026-08-01T00:00:00Z"
  }
  ```

- **Field notes:**
  - `tensorzero_function` — the `[functions.X]` block the call routed through (29 exist; see
    `tensorzero.toml:763-1734`). This is the **join key** that lets cost roll up per lane. It is
    function-granular, not per-agent-instance: agents sharing a function are indistinguishable in the
    rollup. True per-instance attribution needs TensorZero-side request tagging — a follow-up, not this
    subject's job.
  - `node` — which fleet node served the call. Present so node-operator hosting cost can eventually be
    accounted; no compensation mechanism exists today.
  - `estimated_cost_usd` — explicitly an *estimate*. Rates are not authoritative
    (`llm_observability_specialist.py:154-161` currently hardcodes placeholder rates).

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

## Fleet Audit Watcher Subjects

> **Source:** `pmoves/scripts/fleet/fleet-audit-watcher.sh` on the z890/KVM2 fleet lane.

**`fleet.device.registered.v1`**
- **Direction:** Published by `fleet-audit-watcher` on KVM2 -> Consumed by observability, enrollment follow-through, or Discord publisher lanes
- **Purpose:** New RustDesk client registration detected from `hbbs` journal `update_pk` events
- **Reliability:** Fire-and-forget NATS publish; every event is also appended to `/var/log/pmoves/fleet-audit.jsonl` on KVM2

**`fleet.audit.connection.v1`**
- **Direction:** Published by `fleet-audit-watcher` on KVM2 -> Consumed by observability or alerting
- **Purpose:** Relay connection and disconnect events detected from `hbbs` / `hbbr` journals
- **Reliability:** Fire-and-forget NATS publish with local JSONL fallback on KVM2

**`fleet.audit.heartbeat.v1`**
- **Direction:** Published by `fleet-audit-watcher` on KVM2 -> Consumed by observability or alerting
- **Purpose:** Watcher liveness heartbeat emitted every 5 minutes
- **Reliability:** Fire-and-forget NATS publish with local JSONL fallback on KVM2

### Fleet Audit Watcher Notes

- Publisher runtime: `pmoves/scripts/fleet/fleet-audit-watcher.sh`
- Runtime dependencies: `nats` CLI, `hbbs` / `hbbr` systemd journals, `/var/log/pmoves`, and a NATS broker reachable from KVM2
- Auth split: `TAILSCALE_AUTHKEY` joins nodes; `TAILSCALE_API_KEY` is for admin API operations and is not used to publish watcher events
- Reachability caveat: the repo-default NATS broker is localhost-only on port `4222`, so remote watcher publishes stay blocked until one broker is exposed on a Tailscale-reachable interface


## Validation Subjects (MiSSinGLinC external peer review)

> Namespace `validation.*` introduced by the MiSSinGLinC mint
> (`pmoves/docs/AGENTS/MISSINGLINC_MINT_SPEC.md`, 2026-08-09). The branded
> namespace table addition in `.claude/context/self-hosted-defaults.md` is
> staged in the mint PR body — that file is damage-control protected, so the
> table row lands via operator apply.

**`validation.run.requested.v1`**
- **Direction:** Published by rooms/agents requesting validation -> Consumed by missinglinc-validator
- **Purpose:** Request an external peer-review validation run: `{claim_set, evidence_corpus_refs, validation_depth}`
- **Status:** REGISTERED-AHEAD — publisher lands with the MiSSinGLinC service (mint spec Wave-0; no consumer live yet)

**`validation.verdict.ready.v1`**
- **Direction:** Published by missinglinc-validator -> Consumed by rooms, Makeda voice readout (persona.makeda.missinglinc), Hi-RAG ingest
- **Purpose:** Structured validation verdict with per-claim evidence chains and CHIT CGP proof packet
- **Status:** REGISTERED-AHEAD — see mint spec

**`validation.evidence.chain.v1`**
- **Direction:** Published by missinglinc-validator -> Consumed by graph persistence (Neo4j lane), audit surfaces
- **Purpose:** Claim -> evidence -> source graph (JSON-LD) for a completed validation run
- **Status:** REGISTERED-AHEAD — see mint spec

**`validation.counter.evidence.v1`**
- **Direction:** Published by missinglinc-validator (adversarial depth only) -> Consumed by rooms, alerting
- **Purpose:** Counter-evidence report: contradictions found while red-teaming a claim set
- **Status:** REGISTERED-AHEAD — see mint spec

## Mavis Harness v0 Subjects

> Namespace `pmoves.agent.*` + `pmoves.bpm.*` introduced by the Mavis multi-agent
> harness v0 (`pmoves/tools/orchestrator.py` + `pmoves/tools/bpm_cron.py`).
> Locked in PR #2477; registered here in PR follow-up slice. The `pmoves-nats-mcp`
> slice (z890 PR #2492 spec) is the consumer that will produce these messages
> in production; the MockPublisher in `pmoves/tools/orchestrator.py` is the
> test-surface that runs without a live NATS broker.

**`pmoves.agent.task.v1`**
- **Direction:** Published by `pmoves/tools/orchestrator.py::Orchestrator.dispatch` → Consumed by worker agents (Hermes, KiloClaw, Mavis-self)
- **Purpose:** A multi-agent task envelope. The orchestrator publishes one task with a `task_id`; the worker replies on `pmoves.agent.result.v1` keyed by the same `task_id`.
- **Payload:**
  ```json
  {
    "task_id": "uuid",
    "task": "render cyber.png as the Pillar 4 encoding skin",
    "agents": ["mavis", "kiloclaw"],
    "context": { "identity": "critic", "tools_bridge": [...] }
  }
  ```
- **Subscribers:** Agent Zero (for routing), worker agents, audit/observability sinks
- **Status:** REGISTERED — orchestrator + bpm_cron use these subjects; consumer-fork wire-up (Hermes, KiloClaw) is the harness v0 consumer slice

**`pmoves.agent.result.v1`**
- **Direction:** Published by worker agents → Consumed by `pmoves/tools/orchestrator.py::Orchestrator` (correlates by `task_id`)
- **Purpose:** The worker's reply to a task. Multiple workers may reply for the same `task_id`; the orchestrator merges per-phase.
- **Payload:**
  ```json
  {
    "task_id": "uuid",
    "target": "kiloclaw",
    "status": "success | error | pending | timeout",
    "output": "rendered PNG at /tmp/.../cyber.png",
    "elapsed_s": 12.4,
    "error": ""
  }
  ```
- **Subscribers:** Orchestrator, audit/observability, A2UI live trail
- **Status:** REGISTERED — same as `pmoves.agent.task.v1`

**`pmoves.bpm.phase.v1`**
- **Direction:** Published by `pmoves/tools/bpm_cron.py::BpmCron.advance` → Consumed by the orchestrator, A2UI, observability
- **Purpose:** A BPM phase transition event. The 5 phases are `define → assign → execute → review → close`; each transition is a published event so the orchestrator can dispatch the next phase's work and A2UI can render the live trail.
- **Payload:**
  ```json
  {
    "task_id": "uuid",
    "task_name": "react-to-video-123",
    "phase": "execute",
    "previous_phase": "assign",
    "agent": "mavis",
    "timestamp": "2026-08-15T12:00:00Z"
  }
  ```
- **Subscribers:** Orchestrator, A2UI live trail, observability
- **Status:** REGISTERED — bpm_cron publishes per-phase

**`pmoves.kvm.focus.v1`**
- **Direction:** Published by `pmoves/tools/orchestrator.py::Orchestrator.publish_kvm_focus` → Consumed by the external KVM controller (RustDesk + Tailscale)
- **Purpose:** Ask the operator's KVM to switch focus to the node a dispatch just landed on. Emitted only when the target's routing `node` is a real remote machine — local targets (`self`, `host`) and placeholders (`TBD`, `none`, `n/a`, `-`, empty) are no-ops.
- **Payload:**
  ```json
  {
    "task_id": "uuid",
    "target": "glm-5.1",
    "target_node": "5090",
    "issued_at": 1755700000.0
  }
  ```
- **Note:** This began life as a `phase: kvm-focus` event on `pmoves.bpm.phase.v1`, reusing that subscriber. It was split out because that subject is contracted as the five lifecycle phases carrying `task_name`/`previous_phase`, so a focus request read as an invalid lifecycle transition to any A2UI or observability consumer. A discriminator field does not make an incompatible payload compatible.

**`pmoves.bpm.pomodoro.v1`**
- **Direction:** Published by `pmoves/tools/bpm_cron.py::BpmCron` (focus-block boundaries) → Consumed by A2UI, observability, the operator's check-in dispatcher
- **Purpose:** A pomodoro focus-block event: 25-min work + 5-min check-in (configurable via env). Each block boundary is a published event so the operator check-in surface knows when to interrupt.
- **Payload:**
  ```json
  {
    "task_id": "uuid",
    "task_name": "react-to-video-123",
    "block_index": 1,
    "event": "start | completed | skipped",
    "work_minutes": 25,
    "checkin_minutes": 5,
    "timestamp": "2026-08-15T12:00:00Z"
  }
  ```
- **Subscribers:** A2UI, observability, operator check-in surfaces
- **Status:** REGISTERED — bpm_cron publishes per-block

**`pmoves.branch_protection.drift.v1`**
- **Direction:** Published by `pmoves/tools/branch_protection_publisher.py::publish_drift_report` → Consumed by the orchestrator (remediation dispatch), A2UI (live ruleset trail), observability
- **Purpose:** A per-repo branch-protection drift report. One message per non-compliant repo (compliant repos are silent to avoid flooding the subject). The envelope wraps the `AuditResult.to_dict()` shape and adds a `source` + `published_at` for filtering.
- **Payload:**
  ```json
  {
    "envelope": "drift.v1",
    "source": "pmoves.branch_protection",
    "published_at": "2026-08-15T12:00:00Z",
    "audit": {
      "repo": "POWERFULMOVES/PMOVES.AI",
      "profile": "monorepo",
      "branch": "main",
      "compliant": false,
      "drift": [
        { "field": "rulesets[[ main ]].rules[type=required_signatures]", "expected": "present", "actual": "missing", "severity": "block" }
      ],
      "checked_at": "2026-08-15T12:00:00Z",
      "source_url": "https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches"
    }
  }
  ```
- **Publisher cadence:** Daily 06:00 UTC (the `branch-protection-drift.yml` workflow schedule) + manual `workflow_dispatch`
- **Subscribers:** Orchestrator (remediation session), A2UI live ruleset trail, observability
- **Status:** REGISTERED — `branch_protection_publisher.py` publishes via the `FilePublisher` (JSONL stdout, the default sink) or `NatsPublisher` (when `pmoves-nats-mcp` is wired)
