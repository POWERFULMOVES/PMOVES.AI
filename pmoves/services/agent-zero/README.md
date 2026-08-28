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
- `notebook.search`
- `form.get`
- `form.switch`

Refer to the FastAPI docs (`/docs`) for the payload schema of `/mcp/execute`.

## Configuration

The service reads configuration from environment variables and exposes the resolved values via `/config/environment`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | FastAPI listen port. |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | Event bus connection string. |
| `HIRAG_URL` / `GATEWAY_URL` | `http://localhost:8086` | Geometry gateway base URL. |
| `YT_URL` | `http://localhost:8077` | YouTube ingest + transcript gateway. |
| `RENDER_WEBHOOK_URL` | `http://localhost:8085` | ComfyUI render webhook. |
| `OPEN_NOTEBOOK_API_URL` / `NOTEBOOK_API_URL` | — | Base URL for the Open Notebook API queried by `notebook.search` (prefers `/api/search` for Open Notebook `1.8+`, falls back to legacy `/api/v1/notebooks/search`). |
| `OPEN_NOTEBOOK_API_TOKEN` / `NOTEBOOK_API_TOKEN` | — | Bearer token used to authenticate notebook search requests. |
| `OPEN_NOTEBOOK_WORKSPACE` / `NOTEBOOK_WORKSPACE` | — | Optional workspace identifier automatically applied to notebook searches. |
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

## Geometry Bus (CHIT) Integration

- Publishes and queries CHIT via the configured Hi‑RAG gateway (`HIRAG_URL`/`GATEWAY_URL`).
- Supported MCP commands forward to gateway endpoints:
  - `geometry.publish_cgp` → `POST /geometry/event`
  - `geometry.jump` → `GET /shape/point/{point_id}/jump`
  - `geometry.decode_text` → `POST /geometry/decode/text`
  - `geometry.calibration.report` → `POST /geometry/calibration/report`
- Environment:
  - `HIRAG_URL`/`GATEWAY_URL` must point to `hi-rag-gateway-v2` (default `http://localhost:8086`) or GPU variant (`:8087`).
- Make targets
  - Bring up agents: `make up-agents` (includes Agent Zero)
  - Bring up gateways: `make up-both-gateways` (v2 CPU) / `make up-gpu-gateways` (v2 GPU)

---

## Auto-Update System

### How It Works

A GitHub Actions workflow (`agent-zero-upstream-check.yml`) runs daily at 06:00 UTC and checks for new releases of [agent0ai/agent-zero](https://github.com/agent0ai/agent-zero).

**Version tracking:** The current pin is derived from `Dockerfile.multiarch` — the `ARG AGENT_ZERO_REF` value (a fork branch, normally `PMOVES.AI-Edition-<version>`), with an optional `ARG AGENT_ZERO_UPSTREAM_VERSION=<tag>` marker for when the ref is a rolling branch (e.g. `-Hardened`) whose name carries no version. Those committed ARGs are the single source of truth — the old gitignored `.a0-upstream-version` file is retired.

**Detection flow:**
1. Workflow fetches latest release tag from `agent0ai/agent-zero` via GitHub API
2. Compares against the version parsed from `AGENT_ZERO_REF` (or the `AGENT_ZERO_UPSTREAM_VERSION` marker); if the ref carries no comparable version, it reports current and asks the operator to add the marker rather than opening a PR
3. If different and no existing PR, creates a draft PR

**Draft PR contents:**
- Bumps `AGENT_ZERO_REF` ARG in `Dockerfile.multiarch` to the new upstream tag
- Updates the `AGENT_ZERO_UPSTREAM_VERSION` marker in `Dockerfile.multiarch` (when present)
- Updates `upstream-constraints.txt` if new transitive dep pins are needed
- Includes fork sync instructions and review checklist

**CI behavior:**
- The PR initially points at the upstream tag (not the fork branch), so CI **will fail** until fork sync is completed
- On CI failure, a comment is posted explaining that fork sync is the expected next step
- After fork sync, update `AGENT_ZERO_REF` to the synced fork branch → CI re-runs
- On CI pass, PR is labeled `ready-for-review` for manual merge approval

### Fork Sync Process

Fork syncing is **manual** and **not automated** because:
- 24 PMOVES overlay commits must be re-applied
- 6 files with architectural conflicts need re-implementation
- NATS hardening, Prometheus metrics, and TensorZero integrations need validation

**Steps:**
1. Note the upstream version from the draft PR
2. In `POWERFULMOVES/PMOVES-Agent-Zero`, sync from upstream tag
3. Create branch `PMOVES.AI-Edition-v{version}` with overlays applied
4. Update the draft PR's `AGENT_ZERO_REF` to the fork branch
5. Verify CI passes
6. Review and merge

### upstream-constraints.txt

This file pins **transitive dependencies** that agent-zero pulls in indirectly via its `requirements.txt`. These pins prevent known-bad versions from being installed in Stage 1 of the Docker build.

**Rules:**
- Only transitive deps (not direct agent-zero deps)
- Only pins that prevent conflicts with PMOVES Stage 2 dependencies
- PMOVES-specific pins go in `requirements.lock`
- Direct agent-zero deps go in agent-zero's own `requirements.txt`

### Manual Trigger

The workflow supports manual dispatch with an optional version override:

```yaml
# In GitHub Actions → Run workflow
upstream_version: "v1.14"  # optional, auto-detects if empty
```

### Files

| File | Purpose |
------|---------|
| `.github/workflows/agent-zero-upstream-check.yml` | Daily upstream check + PR creation |
| `Dockerfile.multiarch` | `AGENT_ZERO_UPSTREAM_VERSION` marker — comparable version pin when the ref is a rolling branch |
| `upstream-constraints.txt` | Transitive dep pins for Stage 1 install |
| `Dockerfile.multiarch` | `AGENT_ZERO_REF` ARG (bumped by workflow) |
