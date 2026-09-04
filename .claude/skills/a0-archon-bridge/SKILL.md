---
name: a0-archon-bridge
description: Interact with Agent Zero and Archon through their documented integration points - the A0 _a0_connector v1 HTTP API, the wrapper session API, A0's JSON MCP, Archon REST, and the live NATS/CHIT event surface. Use when sending work to Agent Zero or Archon, reading agent sessions/logs, emitting agent events, or wiring new agents (Mavis/Hermes/kiloclaw) into the dispatch bus.
disable-model-invocation: false
user-invocable: true
---

# a0-archon-bridge

Three integration surfaces, each validated live on PMOVES-SPARK 2026-08-26. Prefer them in this order: **documented plugin API > wrapper API > raw internal handlers**. Never hand-discover internal routes — probe the surfaces below first.

## 1. Agent Zero — `_a0_connector` v1 (the documented contract)

The fork's plugin system exposes a versioned HTTP API. This is the stable surface the fork maintains (plugin `AGENTS.md`); the raw `api/api_message` handler is internal.

```
POST http://<a0>:80/api/plugins/_a0_connector/v1/<handler>
Content-Type: application/json
X-API-KEY: <mcp_server_token>        # only needed off-loopback; loopback callers pass session auth
```

Handler inventory (33 features, live on v2.11-hardened `5c280a9`): `chat_create`, `chats_list`, `chat_get`, `chat_reset`, `chat_delete`, `pause`, `nudge`, `message_send`, `message_queue`, `log_tail`, `projects`, `text_editor_remote`, `code_execution_remote`, `computer_use_remote`, `browser_host_remote`, `connector_browser_op`, `remote_file_tree`, `token_status`, `launcher_gateway`, `launcher_gateway_file_write`, `settings_get`, `settings_set`, `agent_profile_set`, `agent_editor`, `agents_list`, `skills_list`, `skills_activate`, `skills_delete`, `installed_plugins`, `model_presets`, `model_switcher`, `browser_runtime_config`, `compact_chat`.

`capabilities` also reports `auth` modes (`["session"]`), `streaming: true`, the websocket namespace (`/ws`, handler `plugins/_a0_connector/ws_connector`), and an attachments contract (`path_or_url`, `http_upload: base64_to_file`, `max_files: 20`).

Key shapes (live-verified):
- `capabilities` → `{"protocol":"a0-connector.v1", "agent_zero_version":..., "auth":["session"], "auth_required":false, "transports":["http","websocket"], "streaming":true, "websocket_namespace":"/ws", "attachments":{...}, "features":[...33]}` — best readiness probe (200 only when the plugin system booted)
- `message_send` `{"message":"...","context_id":opt,"attachments":[{"filename","base64"}]}` → `{"context_id","status":"completed","response"}` (~7s warm; 35s if routed to a cold 51GB local model)
- `log_tail` `{"context_id","limit"}` → `{"context_id","events":[{"sequence","event","timestamp","data"}]}` — event names like `assistant_message`; the wrapper's fetch_log still uses `/api/api_log_get` until a consumer maps this shape
- `pause`/`token_status` require `context_id` (400 otherwise)
- **MCP arg filter (v2.11-hardened `5c280a9`+)**: `filter_declared_args` drops schema-undeclared argument keys at the client boundary and logs `dropping undeclared args for '<tool>': ...` — tool calls must stick to the declared `input_schema.properties`; extras are stripped with an orange log, not rejected

## 2. Agent Zero — PMOVES wrapper (compose :8080)

The hardened public face; use from other services/hosts:

```
POST http://<a0-host>:8080/sessions  {"message":"..."}     → {"context_id","response"}
GET  http://<a0-host>:8080/healthz                        → runtime status
GET  http://<a0-host>:8080/mcp/commands                   → 17 PMOVES MCP commands
POST http://<a0-host>:8080/mcp/execute {"cmd","arguments":{...}}   ← note: "arguments", not "args"
```

Wrapper env contract — **requires PR #2780's compose wiring to be merged** (until then a clean checkout defaults to the raw `/api_message` path and sends no key; on such nodes set these env vars explicitly): `AGENT_ZERO_MESSAGE_PATH=/api/plugins/_a0_connector/v1/message_send`, `AGENT_ZERO_HEALTH_PATH=/api/plugins/_a0_connector/v1/capabilities`, `AGENT_ZERO_API_KEY=<AGENT_ZERO_MCP_TOKEN value>` (canonical #2056 token; env.shared's `MCP_SERVER_TOKEN=dev-local-...` is a placeholder that must never win interpolation). Post-#2813 additions: `AGENT_ZERO_HEALTH_METHOD=POST` (capabilities is POST-only — a GET probe 405s and degrades to the 404-means-alive heuristic) and `AGENT_ZERO_MESSAGE_TIMEOUT=600` (inner-call timeout, was hardcoded 60s — long tasks surfaced as wrapper 503s).

**`healthz` is a child-process check, not a reachability check.** It returns 503 **only** when the child process is not running -- the 503 branch tests `process_manager.is_running` and nothing else (`pmoves/services/agent-zero/main.py:851-856`). Two ways a **200** can come back over a runtime you cannot actually talk to:

- the probe raises: `healthz()` catches `AgentZeroRequestError`, records `runtime.status = "error"`, and falls through to 200 (`main.py:843-858`);
- the probe 404s: `client.health()` treats 404 as "running but no health endpoint" and returns `{"status": "ok", "note": "health endpoint not found (404)"}` (`main.py:331-338`, and the same for the fallback path at `:354-360`).

The second is not hypothetical -- it is what this node returns today (measured B850, 2026-09-02): `GET :8080/healthz` -> **HTTP 200**, `runtime: {"status": "ok", "note": "health endpoint not found (404)"}`, i.e. the connector path is not being reached at all and the body still says `ok`.

So **do not read the HTTP code alone**: read `runtime.status` *and* `runtime.note` from the body. `status: ok` with a 404 note means the wrapper is up and the connector wiring above is not in place.

This is the same green-while-dead shape the 503 branch was added to fix (its own comment at `main.py:852-854` says so), still open one level in. Documented rather than patched here: making probe failures 503 changes Docker healthcheck semantics for every A0 container on the fleet, including the nodes this same paragraph describes as lacking the connector wiring, so it belongs to the service lane and not to a docs change.

## 3. Archon — REST only

MCP deliberately disabled (fleet decision, PR #2303 — archon is REST-only). One native-Archon 0.6.0 service on container **:3090**, host-published by default on **:8091** (`ARCHON_API_PORT`, docker-compose agents overlay) with **:3737** an alias onto it — identical `/api/health` payloads measured on all three (SPARK, 2026-09-04). mcp-gateway also binds 8091 in-network but is host-published as 8189 by default to avoid exactly this collision. CATALOG's "0.6.0 rewrote the old Python `:8091` service" is history, not a port claim — the current compose re-adopted 8091 as Archon's default API port; see `.claude/CATALOG.md`:

```
GET /api/health   → {"status":"ok","adapter":"web","concurrency":{...}}   # rich
GET /health       → {"status":"ok"}                                        # simple
```

Work submission goes through REST conversation endpoints (see `make archon-native-health`, CATALOG §archon). Do not wire MCP clients to Archon.

## 4. NATS / CHIT event surface (live state, audited 2026-08-26)

**Core NATS (works, use it):**
- `pmoves.agent.task.v1` → `pmoves.agent.result.v1` — the dispatch wire. Any node joins via:
  `bash pmoves/scripts/with-env.sh python3 -m pmoves.tools.agent_task_subscriber --agent <id>`
- `mesh.node.announce.v1/.v2` — heartbeats (observed live)
- A0 wrapper `POST /events/publish` emits validated envelopes (`services/common/events`)

**JetStream (mostly dormant — do not assume consumers exist):**
- 9 streams provisioned; only `GEOMETRY_CGP` (`geometry.>`) has live consumers
- `ARCHON`/`BOTZ_COORDINATION`/`ROOMS`/`CONTENT_PROVENANCE`/`TOKENISM_ATTRIBUTION` streams exist with **0 messages, 0 consumers**
- `chit.>` and `agent.graphiti.signed.v1` are **declared in docs but have no stream** — publishing them is fire-into-void unless a consumer is stood up first

**CHIT provenance:** `make -C pmoves sign-trail SUMMARY=... AGENT=... PHASE=...` (trail entry; unsigned-local if no passphrase — acceptable in dev).

## Gotchas

- NATS monitoring: host port is **9223** (container 8222) — the audit script defaults to 8222 and reports everything as orphan
- NATS connect string lives in env.shared (`NATS_PASSWORD`), not exported on the host shell
- TensorZero gateway :3030 has no auth (network-local posture) — probes prove routing, never credentials
- A0 inner runtime registers handlers under the `/api/` prefix; fork docs (connectivity.md) show unprefixed names — trust the probe, file the doc bug

## Validation one-liners

```bash
python3 -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://localhost:8080/healthz'))['status'])"
python3 -c "import urllib.request,json; r=urllib.request.Request('http://localhost:8080/sessions',data=json.dumps({'message':'reply: OK'}).encode(),headers={'Content-Type':'application/json'}); print(json.load(urllib.request.urlopen(r,timeout=120)))"
python3 .claude/skills/pmoves-nats-subject-audit/scripts/audit.py   # then re-check orphans against :9223
```
