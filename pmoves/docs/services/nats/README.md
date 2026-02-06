# nats — Service Guide

Status: Implemented (compose)

Overview
- NATS is PMOVES.AI's event-driven message bus, providing pub/sub messaging for service coordination, agent communication, and async event processing.
- The `nats` container runs NATS server with JetStream enabled for persistent messaging, supporting request/reply patterns, queue groups, and message replay.
- Services subscribe to subjects (topics) to receive events and publish to subjects to broadcast messages, enabling loose coupling between microservices.
- PMOVES uses versioned subject names following the pattern: `<category>.<service>.<event>.<version>` (e.g., `ingest.transcript.ready.v1`).
- Authentication enabled with username/password (default: `nats`/`pmoves`).

Compose
- Service: `nats`
- Ports: `4222:4222` (client connections), `9223:4223` (monitoring)
- Profiles: (no profile - always starts)
- Depends on: (no dependencies - core infrastructure)

Environment (core)
- `DOCKED_MODE` — Container deployment mode (default `true`).
- `PARENT_SYSTEM` — Parent system identifier (default `PMOVES.AI`).
- `PARENT_VERSION` — Parent system version (default `1.0.0-hardened`).

Command-line arguments
- `-js` — Enable JetStream for persistent messaging.
- `-m 8222` — Enable HTTP monitoring on port 8222.
- `--user nats` — Set authentication username.
- `--pass pmoves` — Set authentication password.

Client connection strings
- Default internal: `nats://nats:4222`
- With credentials: `nats://nats:pmoves@nats:4222`
- External from host: `nats://localhost:4222`
- With credentials external: `nats://nats:pmoves@localhost:4222`

Key subject categories
- Research & Knowledge: `research.>`, `supaserch.>`
- Media Ingestion: `ingest.>` (file.added, transcript.ready, summary.ready, chapters.ready)
- Agent Observability: `claude.code.>`, `agent.tool.>`
- Mesh Coordination: `mesh.node.>`
- Testing & Development: `test.>`, `dev.>`
- Geometry Bus: `tokenism.>`, `geometry.>` (see `.claude/context/geometry-nats-subjects.md`)

Critical subjects
- `research.deepresearch.request.v1` / `research.deepresearch.result.v1` — DeepResearch LLM-based research planning.
- `supaserch.request.v1` / `supaserch.result.v1` — SupaSerch multimodal holographic deep research.
- `ingest.file.added.v1` — New file added to MinIO (published by PDF Ingest, File Upload).
- `ingest.transcript.ready.v1` — Transcription completed (published by PMOVES.YT, FFmpeg-Whisper).
- `ingest.summary.ready.v1` — Content summary generated.
- `ingest.chapters.ready.v1` — Chapter markers created.
- `claude.code.tool.executed.v1` — Claude Code CLI tool execution events.
- `mesh.node.announce.v1` — Mesh Agent node announcements (every 15s).

API Endpoints (monitoring)
- `GET http://localhost:8222/varz` — Server runtime statistics:
  - Connections, subscriptions, messages in/out.
  - JetStream metrics.
  - Memory and CPU usage.

- `GET http://localhost:8222/connz` — Connection details:
  - Active connections with CID, IP, port.
  - Subscriptions per connection.
  - Message counts per connection.

- `GET http://localhost:9223/routing` — Routing information (monitoring port):
  - Subject subscriptions.
  - Queue group memberships.

NATS CLI usage
- Publish event:
  ```bash
  nats pub "research.deepresearch.request.v1" '{
    "query": "test query",
    "request_id": "test-123",
    "requester": "cli"
  }'
  ```

- Subscribe to subject:
  ```bash
  # Single subject
  nats sub "ingest.transcript.ready.v1"

  # Wildcard - all ingest events
  nats sub "ingest.>" --max 10

  # Queue group for load balancing
  nats sub "research.deepresearch.request.v1" --queue workers
  ```

- Monitor traffic:
  ```bash
  # View all traffic (careful in production!)
  nats sub ">"

  # View specific category
  nats sub "research.>"
  ```

- Server info:
  ```bash
  nats server info
  nats server report connections
  ```

JetStream configuration
For persistent subjects requiring guaranteed delivery:
- Create stream for research events:
  ```bash
  nats stream add RESEARCH \
    --subjects "research.>" \
    --retention limits \
    --max-age 7d
  ```

- Create consumer:
  ```bash
  nats consumer add RESEARCH research_worker \
    --deliver all \
    --ack explicit
  ```

- List streams:
  ```bash
  nats stream list
  nats stream info RESEARCH
  ```

Smokes & tests
- Minimal container smoke:
  ```bash
  docker compose up -d nats
  docker compose ps nats
  nats server info
  ```

- Test pub/sub:
  ```bash
  # Terminal 1: Subscribe
  nats sub "test.smoke.v1"

  # Terminal 2: Publish
  nats pub "test.smoke.v1" "test message"
  ```

- Test with authentication:
  ```bash
  nats -s nats://nats:pmoves@localhost:4222 server info
  ```

- Test JetStream:
  ```bash
  nats stream add TEST_STREAM --subjects "test.>" --retention limits
  nats stream list
  nats pub "test.jetstream.v1" "persistent message"
  nats stream info TEST_STREAM
  ```

- Check monitoring endpoint:
  ```bash
  curl http://localhost:8222/varz | jq .
  ```

Runbook
- Start NATS:
  ```bash
  docker compose up -d nats
  ```

- View NATS logs:
  ```bash
  docker compose logs -f nats
  ```

- Monitor connections:
  ```bash
  nats server report connections
  curl http://localhost:8222/connz | jq .
  ```

- Test JetStream persistence:
  ```bash
  nats stream list
  nats consumer list
  ```

- Replay messages from stream:
  ```bash
  nats consumer next RESEARCH research_worker
  ```

Service integration patterns
- Publishing events (Python):
  ```python
  import nats
  import asyncio
  import json

  async def publish_event():
      nc = await nats.connect("nats://nats:pmoves@nats:4222")
      await nc.publish("ingest.file.added.v1", json.dumps({
          "file_id": "unique-id",
          "bucket": "assets",
          "key": "path/to/file.pdf"
      }).encode())
      await nc.close()

  asyncio.run(publish_event())
  ```

- Subscribing to events (Python):
  ```python
  import nats
  import asyncio
  import json

  async def subscribe_events():
      nc = await nats.connect("nats://nats:pmoves@nats:4222")

      async def handle_message(msg):
          data = json.loads(msg.data.decode())
          print(f"Received on {msg.subject}: {data}")

      await nc.subscribe("ingest.>", cb=handle_message)
      await asyncio.Event().wait()

  asyncio.run(subscribe_events())
  ```

- Queue group for load balancing:
  ```python
  # Multiple workers with same queue name
  await nc.subscribe("research.deepresearch.request.v1", "workers", cb=handle_request)
  ```

Best practices
- Always include version in subject names (`.v1`, `.v2`) for backward compatibility.
- Include `request_id` in payloads for tracking and correlation.
- Add `timestamp` in ISO 8601 format (UTC) to all payloads.
- Use queue groups (`--queue workers`) for load balancing across multiple instances.
- Acknowledge JetStream messages explicitly after processing.
- Log all events for debugging and audit trails.
- When changing payload structure, create new version (`.v2`) and maintain old version.
- Use wildcards (`*` for single-level, `>` for multi-level) for flexible subscriptions.
- Test NATS connectivity in service health checks.
- Use JetStream for critical events requiring guaranteed delivery.

Troubleshooting
- NATS won't start:
  - Check port conflicts: `lsof -i :4222`
  - Verify authentication: Ensure services use correct credentials (`nats:pmoves`)
  - Check logs: `docker compose logs nats`

- Services can't connect:
  - Verify NATS URL in service environment: `docker compose exec <service> env | grep NATS_URL`
  - Test connection from host: `nc -zv localhost 4222`
  - Check authentication: `nats -s nats://nats:pmoves@localhost:4222 server info`

- Messages not delivered:
  - Verify subject names match exactly (case-sensitive).
  - Check subscriber is running: `nats server report connections`
  - Ensure JetStream consumer exists: `nats consumer list`
  - Check for queue group mismatches.

- High memory usage:
  - Monitor JetStream streams: `nats stream list`
  - Check message retention policies: `nats stream info <stream_name>`
  - Adjust max-age or max-msgs limits on streams.

- JetStream errors:
  - Verify JetStream enabled: Check for `-js` flag in container command.
  - Create stream before publishing: `nats stream add <name> --subjects "..."`
  - Check consumer state: `nats consumer info <stream> <consumer>`

Metrics (if Prometheus exporter enabled)
- `nats_server_connections` — Active connections
- `nats_server_subscriptions` — Active subscriptions
- `nats_server_messages_in` — Messages received
- `nats_server_messages_out` — Messages sent
- `nats_server_jetstream_messages` — JetStream message counts

Ops Quicklinks
- NATS documentation: https://docs.nats.io
- NATS CLI guide: https://github.com/nats-io/natscli
- JetStream guide: https://docs.nats.io/running-a-nats-service/configuration/jetstream
- PMOVES NATS subjects: `.claude/context/nats-subjects.md`
- PMOVES geometry subjects: `.claude/context/geometry-nats-subjects.md`
- NATS monitoring: `http://localhost:8222/varz` (server stats)
- NATS connections: `http://localhost:8222/connz` (connection details)

Service dependencies
All PMOVES services depend on NATS for event-driven communication:
- Agent Zero — Subscribes to task subjects, publishes tool execution events
- Archon — Subscribes to agent events, publishes workflow results
- PMOVES.YT — Publishes transcript events when transcription completes
- FFmpeg-Whisper — Publishes transcription completion events
- Discord Publisher — Subscribes to ingest events for notifications
- Mesh Agent — Publishes node announcements every 15 seconds
- DeepResearch — Subscribes to research requests, publishes results
- SupaSerch — Coordinates research via NATS subjects

Security notes
- Default credentials (nats/pmoves) should be rotated in production deployments.
- Consider enabling TLS for client connections in production.
- Use subject-level permissions for multi-tenant deployments.
- Monitor connection activity via `/connz` endpoint for anomalies.
- Restrict monitoring port (8222) access in production environments.
