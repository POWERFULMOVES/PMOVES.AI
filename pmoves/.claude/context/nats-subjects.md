# PMOVES.AI NATS Event Subjects Catalog

Comprehensive reference of all NATS message subjects used for event-driven communication across PMOVES services.

> **See Also:** For GEOMETRY BUS subjects (`tokenism.*`, `geometry.*`), see [geometry-nats-subjects.md](./geometry-nats-subjects.md)

## NATS Configuration

- **Server:** `nats://nats:pmoves@nats:4222`
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

## Provenance-First Content Subjects

These subjects carry the `z890` / PMOVES-SPARK parity lane that keeps junk out of HiRAG while preserving semantic shape, provenance, and Hyperdimensions replay data.

**`content.raw.v1`**
- **Direction:** Published by ingest and messaging surfaces -> Consumed by `content-provenance-gate`, PMOVES-SPARK
- **Purpose:** Raw message/content payload entering provenance-first shaping before HiRAG
- **Core Fields:** `content_id`, `text`, `source_ref`, optional `favorite_words`, `aliases`, `labels`

**`content.lexicon.shaped.v1`**
- **Direction:** Published by `content-provenance-gate` or PMOVES-SPARK -> Consumed by provenance attesters, Hyperdimensions
- **Purpose:** Context-shaped lexical view of the content with anchors, favorite words, and semantic weights
- **Core Fields:** `shape_id`, `anchor_terms`, `semantic_weights`, `noise_score`, `semantic_density`

**`content.provenance.attested.v1`**
- **Direction:** Published by provenance attesters -> Consumed by the HiRAG gate, Hyperdimensions, Hi-RAG v2
- **Purpose:** Attach CHIT geometry, graphiti mark, and Merkle lineage before deciding whether content is worthy of HiRAG ingest
- **Core Fields:** `graphiti_mark`, `merkle_root`, `provenance_refs`, `hyperbolic_coords`, `spectral_signature`

**`content.hirag.accepted.v1`**
- **Direction:** Published by the `content-provenance-gate` -> Consumed by Hi-RAG v2, Hyperdimensions, operators
- **Purpose:** Content is semantically dense enough and sufficiently attested to enter HiRAG
- **Core Fields:** `kb_namespace`, `accepted_reason`, `scorecard`

**`content.hirag.rejected.v1`**
- **Direction:** Published by the `content-provenance-gate` -> Consumed by PMOVES-SPARK, Hyperdimensions, operators
- **Purpose:** Reject low-signal or weakly attested content before it pollutes HiRAG
- **Core Fields:** `rejected_reason`, `rejected_reasons`, `scorecard`

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

## A2UI (Agent-to-User Interface) Subjects

### A2UI Render Events

**`a2ui.render.v1`**
- **Direction:** Published by A2UI agents → Consumed by UI clients
- **Purpose:** Real-time UI component updates from A2UI agents
- **Payload:** A2UI v0.9 format (JSONL)
- **Stream:** A2UI (JetStream enabled)
- **Events:**
  - `createSurface` - Initialize new UI surface
  - `beginRendering` - Start rendering with root component
  - `surfaceUpdate` / `updateComponents` - Add/update UI components
  - `dataModelUpdate` / `updateDataModel` - Update data bindings
  - `userAction` - User interaction events
  - `closeSurface` - Close UI surface

**`a2ui.request.v1`**
- **Direction:** Published by UI → Consumed by A2UI agents
- **Purpose:** Request UI generation or updates
- **Payload:**
  ```json
  {
    "request_id": "unique-id",
    "surface_id": "target-surface",
    "request_type": "create|update|query",
    "parameters": { ... }
  }
  ```

### A2UI Wildcard Subjects

- **`a2ui.>`** - All A2UI events (for wildcard subscriptions)
- **`geometry.>`** - Cross-service geometry events (A2UI, Tokenism, DoX, Hyperdimensions)

> **See Also:** [geometry-nats-subjects.md](./geometry-nats-subjects.md) for CGP/CHIT geometry protocol subjects

## MiniMax Edition Subjects

### Character Persona System (FlOO$)

**`minimax.character.request.v1`**
- **Direction:** Published by clients → Consumed by MiniMax Edition agents
- **Purpose:** Request character persona synthesis for FlOO$ system
- **Payload:**
  ```json
  {
    "request_id": "unique-id",
    "persona": "dr-bean|mr-clean|powerpuff-girls|custom",
    "context": "task context for persona adaptation",
    "voice_register": "measured_precise|direct_confident|high_energy",
    "temperature": 0.1,
    "speaking_rate": "slow|normal|fast"
  }
  ```
- **Subscribers:** MiniMax Edition agents, 5090-claude

**`minimax.character.response.v1`**
- **Direction:** Published by MiniMax Edition agents → Consumed by voice pipeline
- **Purpose:** Character persona synthesis response
- **Payload:**
  ```json
  {
    "request_id": "matching-request-id",
    "persona": "synthesized persona config",
    "response": "generated content in persona voice",
    "prosodic_config": {
      "bpm": 120,
      "scale": "major",
      "emotion": "positive"
    }
  }
  ```

**`minimax.voice.prosodic.v1`**
- **Direction:** Published by MiniMax Edition → Consumed by Flute Gateway
- **Purpose:** Prosodic voice synthesis with BPM/music mapping
- **Payload:**
  ```json
  {
    "request_id": "unique-id",
    "text": "voice content",
    "persona": "persona used",
    "prosodic_params": {
      "bpm": 120,
      "midi_note": 60,
      "scale": "pentatonicMajor"
    },
    "model": "minimax-m2.7"
  }
  ```

**`minimax.agent.trail.v1`**
- **Direction:** Published by MiniMax Edition agents → Consumed by CHIT trail
- **Purpose:** Agent trail entries for attribution and navigation
- **Payload:**
  ```json
  {
    "agent_id": "minimax",
    "trail_entry": {
      "action": "character_synthesis|voice_generation|reasoning",
      "context": "task context",
      "result_summary": "brief result"
    },
    "timestamp": "ISO-8601",
    "hyperdimensions": {
      "wave_state": "collapsed",
      "plasmons": 42
    }
  }
  ```

**`minimax.agent.status.v1`**
- **Direction:** Published by MiniMax Edition agents → Consumed by monitoring
- **Purpose:** Health heartbeat for MiniMax agents
- **Payload:**
  ```json
  {
    "agent_id": "minimax_edition",
    "status": "healthy|degraded|unavailable",
    "model_loaded": "minimax-m2.7|minimax-m2.1",
    "quota_remaining": 4500,
    "quota_reset_window_seconds": 18000,
    "timestamp": "ISO-8601"
  }
  ```

### Token Plan Quota Events

**`minimax.quota.warning.v1`**
- **Direction:** Published by quota monitor → Consumed by fallback routing
- **Purpose:** Alert when Token Plan quota is running low
- **Payload:**
  ```json
  {
    "quota_type": "m2.7|m2.1|speech|image|video|music",
    "requests_remaining": 500,
    "requests_used": 4000,
    "reset_window_seconds": 18000,
    "recommended_action": "switch_to_payg|wait_for_reset"
  }
  ```

**`minimax.quota.exhausted.v1`**
- **Direction:** Published by quota monitor → Consumed by fallback routing
- **Purpose:** Alert when Token Plan quota is exhausted
- **Payload:**
  ```json
  {
    "quota_type": "m2.7|m2.1|speech|image|video|music",
    "requests_remaining": 0,
    "reset_window_seconds": 18000,
    "fallback_action": "switch_to_glm|switch_to_payg"
  }
  ```
