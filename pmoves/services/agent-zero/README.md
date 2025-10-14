# Agent Zero Service

Agent Zero is the core PMOVES coordinator. The FastAPI worker exposes both the classic event publication endpoint and an HTTP bridge for the MCP-compatible helpers defined in `mcp_server.py`.

## API Overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/healthz` | GET | Liveness probe for the container. |
| `/config/environment` | GET | Returns resolved configuration (ports, upstream runtimes, runtime directories). |
| `/mcp/commands` | GET | Lists MCP commands and advertises the active form and runtime directories. |
| `/mcp/execute` | POST | Execute an MCP command, e.g. `{ "cmd": "geometry.jump", "arguments": { "point_id": "..." } }`. |
| `/events/publish` | POST | Publish a NATS envelope `{ "topic": "...", "payload": { ... } }`. Optional `correlation_id`, `parent_id`, and `source` fields are forwarded into the envelope metadata. |

### MCP Commands

The `/mcp/commands` endpoint enumerates the available helpers. The following commands are currently supported:

- `geometry.publish_cgp`
- `geometry.jump`
- `geometry.decode_text`
- `geometry.calibration.report`
- `ingest.youtube`
- `media.transcribe`
- `comfy.render`
- `form.get`
- `form.switch`

Refer to the FastAPI docs (`/docs`) for the payload schema of `/mcp/execute`.

## Configuration

The service reads configuration from environment variables and exposes the resolved values via `/config/environment`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | FastAPI listen port. |
| `NATS_URL` | `nats://nats:4222` | Event bus connection string. |
| `HIRAG_URL` / `GATEWAY_URL` | `http://localhost:8087` | Geometry gateway base URL. |
| `YT_URL` | `http://localhost:8077` | YouTube ingest + transcript gateway. |
| `RENDER_WEBHOOK_URL` | `http://localhost:8085` | ComfyUI render webhook. |
| `AGENT_FORM` | `POWERFULMOVES` | Default MCP form. |
| `AGENT_FORMS_DIR` | `configs/agents/forms` | Directory for YAML form definitions. |
| `AGENT_KNOWLEDGE_BASE_DIR` | `runtime/knowledge` | Knowledge base artifacts and caches. |
| `AGENT_MCP_RUNTIME_DIR` | `runtime/mcp` | Working directory for MCP sockets/logs. |
| `AGENTZERO_JETSTREAM` | `true` | Set to `false` to fall back to plain NATS fan-out (no JetStream stream/consumer management). |

## Runtime Notes

1. On startup the supervisor now launches both the UI runtime and the JetStream controller. The controller reconnect loop keeps retrying until `NATS_URL` is reachable, which is especially important for the provisioning bundle and Tailscale-hosted agents.
2. `/healthz` reports controller status (`connected`, `controller_started`) plus the current JetStream metrics so automation checks can confirm subscriptions are alive.
3. MCP executions are dispatched through the existing helper functions in `mcp_server.py`, so updates to those helpers automatically surface via HTTP.
4. The configuration endpoints make it easy to surface runtime state inside OpenAPI clients, MCP hubs, or n8n workflows without shell access.
5. The Docker image runs the upstream `/ins/copy_A0.sh` helper before booting the FastAPI wrapper, keeping `/a0` in sync with the vanilla Agent Zero runtime so volume mounts receive the latest assets.
6. Run `python pmoves/tools/realtime_listener.py --topics content.published.v1 --max 1` (from the repo root) to watch enriched publish events; fields like `thumbnail_url`, `duration`, and `jellyfin_public_url` should appear after `make demo-content-published` completes. Use `--compact` for single-line output or `--url` to target a remote NATS server.
