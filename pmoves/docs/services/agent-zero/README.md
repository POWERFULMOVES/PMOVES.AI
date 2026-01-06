# agent-zero — Service Guide

Status: Implemented (compose)

Overview
- Agent Zero is the control plane and tools layer; it subscribes to NATS and orchestrates tasks for the rest of the stack (Archon, PMOVES.YT, geometry, media, etc.).
- The `agent-zero` container runs a FastAPI **supervisor** on port `8080` and supervises an embedded Agent Zero runtime (UI/agent) inside `/a0`. Long-running work happens in the embedded runtime; the supervisor provides a stable HTTP/MCP surface.

Compose
- Service: `agent-zero`
- Ports: `8080:8080` (supervisor API), `8081:80` (Agent Zero UI)
- Profiles: `agents`
- Depends on: `nats`

Environment (core)
- `PORT` — FastAPI listen port (default `8080`).
- `NATS_URL` — NATS connection string (default `nats://nats:4222`).
- `AGENT_ZERO_API_BASE` — base URL the supervisor uses to talk to the embedded runtime (default `http://127.0.0.1:80` inside the container).
- `AGENT_ZERO_CAPTURE_OUTPUT` — capture embedded runtime stdout/stderr in the supervisor logs (default `true`).
- `AGENT_ZERO_EXTRA_ARGS` — additional args for the embedded runtime (default `--port=80`).
- `AGENTZERO_JETSTREAM` — enable JetStream controller (default `true`; falls back to plain NATS fan-out when `false`).

Environment (MCP + upstreams)
- `HIRAG_URL` / `GATEWAY_URL` — geometry gateway (Hi‑RAG v2) base URL.
- `YT_URL` — pmoves-yt ingest/transcript gateway.
- `RENDER_WEBHOOK_URL` — ComfyUI render webhook base URL.
- `OPEN_NOTEBOOK_API_URL` / `OPEN_NOTEBOOK_API_TOKEN` / `OPEN_NOTEBOOK_WORKSPACE` — Open Notebook search integration.
- `AGENT_FORM` — default MCP form name (default `POWERFULMOVES`).
- `AGENT_FORMS_DIR` — directory for YAML form definitions (default `configs/agents/forms`).
- `AGENT_KNOWLEDGE_BASE_DIR` — local knowledge base directory (default `runtime/knowledge`).
- `AGENT_MCP_RUNTIME_DIR` — MCP runtime working directory (default `runtime/mcp`).
- `AGENT_ZERO_EVENTS_TOKEN` — bearer token for `/events/publish` (defined in `pmoves/env.shared`).

HTTP API (supervisor)
- `GET /healthz` — supervisor + embedded runtime health:
  - Includes supervisor status, command, PID, last return code.
  - Embeds JetStream/NATS metrics (`connected`, `controller_started`, `use_jetstream`, `stream`, `subjects`, optional `metrics`).
  - If the embedded runtime is healthy, includes a `runtime` block containing its own health payload.
- `GET /config/environment` — returns the resolved `AgentZeroServiceConfig` (ports, gateway URLs, forms dir, knowledge base dir, MCP runtime dir). Useful for debugging and tooling.
- `GET /mcp/commands` — lists available MCP commands:
  - `default_form`, `forms_dir`, `runtime` directories.
  - `commands[]` with `name` and `description` from `COMMAND_REGISTRY`.
- `POST /mcp/execute` — executes an MCP command:
  - Body: `{ "cmd": "<command-name>", "arguments": { ... } }`.
  - Response: `{ "cmd": "<command-name>", "result": { ... } }`.
  - Example safe call (no external dependencies): `{"cmd":"form.get","arguments":{}}`.
- `POST /events/publish` — publishes an envelope via the Agent Zero controller:
  - Body: `{ "topic": "...", "payload": { ... }, "correlation_id": "...", "parent_id": "...", "source": "..." }`.
  - Requires the controller to be connected to NATS (`controller_started=true` in `/healthz` detail).

MCP commands
- Exposed via `/mcp/commands` and `/mcp/execute` using `services/agent-zero/mcp_server.py`:
  - `geometry.publish_cgp` — POSTs a geometry program to Hi‑RAG v2.
  - `geometry.jump` — jumps to a geometry point (requires `point_id`).
  - `geometry.decode_text` — decodes text embeddings (requires `constellation_id`).
  - `geometry.calibration.report` — posts calibration data.
  - `ingest.youtube` — ingests a YouTube URL (requires `url`).
  - `media.transcribe` — triggers transcript generation for a video (requires `video_id`).
  - `comfy.render` — triggers ComfyUI render flows (requires `flow_id` and `inputs`).
  - `notebook.search` — searches Open Notebook (requires either a `query` or filters).
  - `form.get` — returns the active MCP form.
  - `form.switch` — switches the active MCP form by name.

Smokes & tests
- Minimal container smoke:
  ```bash
  docker compose --profile agents up -d nats agent-zero
  docker compose ps agent-zero
  curl -sS http://localhost:8080/healthz | jq .
  docker compose logs -n 50 agent-zero
  ```
- Make-based health check (used by `agents-headless-smoke`):
  - `make -C pmoves health-agent-zero`
    - Verifies `GET /healthz` returns 200 and reports a default form.
    - Verifies `GET /config/environment` is non-empty.
    - Calls `make a0-mcp-exec-smoke` to execute a `form.get` MCP command via `/mcp/execute` and asserts the form is present in the result.
- Dedicated MCP smokes:
  - `make -C pmoves a0-mcp-smoke` — lists MCP commands and prints count/sample.
  - `make -C pmoves a0-mcp-exec-smoke` — executes `form.get` via `/mcp/execute` and checks `.result.form`.

Runbook
- Start/stop via the `agents` targets documented in [LOCAL_TOOLING_REFERENCE](../../PMOVES.AI%20PLANS/LOCAL_TOOLING_REFERENCE.md), e.g.:
  - `make -C pmoves up-agents` — headless agents (NATS, Agent Zero, Archon, mesh, publisher-discord).
  - `make -C pmoves up-agents-ui` — agents plus UIs (Agent Zero UI, Archon UI, SupaSerch).
  - `make -C pmoves agents-headless-smoke` — checks Agent Zero + Archon headless stacks.

Ops Quicklinks
- Smoke checklist: [SMOKETESTS](../../PMOVES.AI%20PLANS/SMOKETESTS.md)
- Next steps plan: [NEXT_STEPS](../../PMOVES.AI%20PLANS/NEXT_STEPS.md)
- Roadmap context: [ROADMAP](../../PMOVES.AI%20PLANS/ROADMAP.md)

Local realtime voice (operator audio)
- To hear `voice.agent.response.v1` events locally, run the host-run speaker + follower:
  - `make -C pmoves voice-speaker-start`
  - `make -C pmoves voice-follow-start`
- Quick manual check:
  - `make -C pmoves voice-say MSG="Voice loop check" VOICE_SPEAKER_MODE=batch`
