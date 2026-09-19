# 5090 Lane Dispatch Handoff — 2026-09-11

> Lane dispatch from the 5090 (POWERFULMOVES) Claude session, 2026-09-11.
> Predecessor: PMOVES_SchoolPsych_LANDING_MAP_2026-08-08.md + the v2 work
> order at `SEAP/archon-build/ARCHON_WORK_ORDER_school-psych-v2.md`.
> Ingested into Hi-RAG v2 via `POST /hirag/upsert-batch` under namespace
> `seap-5090-handoff` (admin-tailscale gated; this node is on tailnet
> at `100.73.74.3`).
>
> **Note on path:** the SEAP working directory `pmoves/data/agent-zero/usr/workdir/`
> is a read-only protected path; the handoff lives here at
> `pmoves/docs/handoffs/` instead, which is the convention set by PR #2969.

## What the operator asked for, in one line

Bring up the latest A0, run a fresh TAC over the recent pipecat additions
and flute-gateway optimizations, ingest the SEAP new content, set up
the DARKXSIDE room (operator-hosted, no A0 subordinate yet), wire LinkedIn
to the lane surface, and dispatch the cross-Claude work so the Claudes
can call each other and other harness / model surfaces.

## What the operator ACTed in this session

| Action | Outcome | Where the next Claude should look |
|--------|---------|-------------------------------------|
| ACK lanes 3 + 4 + 6 (the operator wrote "4 4" as shorthand for the same lane twice) | lanes 3, 4, 6 in `AGNOTE4482PHI.t1.md` | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` |
| DEFERRED lane 1 (Crush rebase), lane 2 (pipecat TAC) | tasks #1 + #2 deleted | (none — clean slate when ready) |
| PARKED lane 7 (DARKXSIDE room) — operator hosts personally under auth FO 4$ tier; no A0 subordinate mint yet | task #8 pending | p7:stage once operator hands off |

## Live state findings the next session should NOT re-discover

### A0 wrapper plugin path
The wrapper on `:8080` is the **PMOVES MCP surface** (17 commands: a2a.strategic_handoff,
comfy.render, e2b.sandbox.*, e2b.desktop.create, e2b.spell.execute, e2b.surf.scrape,
form.get, form.switch, geometry.calibration.report, geometry.decode_text,
geometry.jump, geometry.publish_cgp, ingest.youtube, media.transcribe, notebook.search).

The inner A0 runtime's **documented plugin API** lives on `:8081`, NOT `:8080`.
The probe that works is `POST http://localhost:8081/api/plugins/_a0_connector/v1/capabilities`
which returns the protocol banner:

```json
{
  "protocol": "a0-connector.v1",
  "version": "0.1.0",
  "agent_zero_version": "8b3b05d",
  "auth": ["session"],
  "auth_required": false,
  "transports": ["http", "websocket"],
  "streaming": true,
  "websocket_namespace": "/ws",
  "websocket_handlers": ["plugins/_a0_connector/ws_connector"],
  "attachments": {"mode": "path_or_url", "http_upload": "base64_to_file", "max_files": 20},
  "features": ["chat_create", ...29 total handlers]
}
```

The 29 handlers live at `/api/plugins/_a0_connector/v1/<handler>` (message_send,
chats_list, chat_get, agent_editor, model_switcher, log_tail, pause, nudge,
installed_plugins, browser_runtime, launcher_gateway_status, etc.). Auth via
`X-API-KEY` from the wrapper side; loopback callers use session auth.

The wrapper itself already uses the plugin path internally (its
`AGENT_ZERO_HEALTH_PATH=/api/plugins/_a0_connector/v1/capabilities` is wired
in `pmoves/docker-compose.yml`); on a 405 (POST-only route probed with GET)
it falls back to `/health` 404 → "treating as healthy" verdict. **External
probes of the plugin path MUST go to `:8081`, not `:8080`.**

### Restart recipe (use ONLY when the wrapper env is stale)
The target name is `up-agents`, NOT `up-agent-zero`. The full bring-up:
```
bash pmoves/scripts/with-env.sh docker compose -p pmoves \
  -f pmoves/docker-compose.yml \
  -f pmoves/docker-compose.agents.images.yml \
  -f pmoves/docker-compose.hardened.yml restart agent-zero
```
(`restart` preserves the image; `up` rebuilds. For a fresh env, `up -d` from
`pmoves/mk/infra.mk` brings up the full stack.)

The wrapper's startup_timeout is 180s. A real `docker ps` on the
pmoves-agent-zero-1 container shows `health: starting` for 90–135s; the
health probe flips to `healthy` once the inner A0 registers its plugins.
Don't poll `:8080/healthz` more often than every 15s during this window.

### Hi-RAG v2 routes
The real route prefix is `/hirag/*`, NOT `/v1/*` or `/api/*`:
- `POST /hirag/query` — search; body is `{"query":"...", "top_k":10}` (note
  the field is `query`, not `q`).
- `POST /hirag/upsert-batch` — ingest; body is `UpsertReq` with `items: [UpsertItem]`
  where each item has `doc_id`, `chunk_id`, `text`, `namespace`,
  `section_id`, `payload`. Admin-tailscale gated (must come from a
  Tailscale address).
- The compose maps `HIRAG_V2_GPU_HOST_PORT:-8087` on the host to container
  `8086`. Either host port works externally.

### flute-gateway
Not a submodule. The directory is `pmoves/services/flute-gateway/`. The
service already has PR #2977 (`flute-voice — 6-tool TTS surface over all
14 engines`) on main. The lane-3 work is therefore a **delta**: profile
the BPM encoder + persona selector, write
`pmoves/configs/tac_trees/flute-gateway.tac.yaml`, push a delta PR.

### Crush (lane 1 — DEFERRED)
`PMOVES-crush` gitlink is at `9c3742e3` (HEAD = `9c3742e3 fix(pmoves):
repair Showtime and Pinokio launchers (#8)`). The fork tracks
`PMOVES.AI-Edition-Hardened` — DO NOT sync the `main` branch (drops
hardening, breaks the gitlink). When the operator picks this up, the
recipe is `fleet:fork-sync` skill, step 2 (fork-sync.yml), then
union-rebase the PMOVES.AI gitlink on a clean fast-forward.

## DARKXSIDE room hosting (lane 7, operator-as-host)

The operator is hosting the room personally under auth FO 4$ tier.
No A0 subordinate is minted in their name. The p7:stage skill records
the room state. The catalog row is `darkxsides.room.control`. When the
operator wants to hand off hosting to a Claude, the next step is
`archon:mint-agent` with a DARKXSIDE persona-bound subordinate that
takes the room host role.

## Cross-Claude dispatch (the "call other harness and model for assistance" surface)

The five lanes that have a named Claude:

| Lane | Owner | Sub-surface |
|------|-------|-------------|
| 3 — flute-gateway delta | 5090 (this node) | /voice:status + Ultimate-TTS-Studio :7860 |
| 4 — SEAP ingest | 5090 (this node) | this brief → upsert-batch on hi-rag |
| 6 — A0 bring-up | 5090 (this node) | complete; documented above |
| 7 — DARKXSIDE room | operator (FO 4$ tier) | p7:stage + archon creator-onboard when ready |
| Crush rebase | 4090 | fleet:fork-sync (deferred) |

The A0 wrapper exposes 17 MCP commands that are the **dispatch surface**
between any Claude and any other agent / model / harness. The list is
in the table under "A0 wrapper plugin path" above. Use them by calling
`POST http://localhost:8080/mcp/execute` with `{"cmd":"...", "arguments":{...}}`
(yes, the body field is `arguments`, not `args` — measured live).

## Cipher entry (marco-polo pattern)

For the next session, store this brief and search with a different phrasing
to verify the retrieval bridge works:
- marco: store the brief under `code_pattern` category with tags
  `["handoff","a0","flute-gateway","hi-rag","seap","5090"]`
- polo: search with `how does the A0 wrapper expose the plugin path`
  or `how do I ingest into hi-rag v2` — should retrieve this entry.

## Gaps intentionally NOT closed this session

- LinkedIn surface (a/b/c design pick): parked; operator has not chosen.
  Composio is the most likely path (lanes with z-autoclaw legal-assistant
  already use it). Mavis owns the design once a pick is made.
- Cross-Claude dispatch table in `AGNOTE4482PHI.t1.md`: parked; needs
  the LinkedIn pick + the DARKXSIDE host handoff before it's coherent.
- 4090's wave of remaining open PRs (the 13 thread-bearing ones + the
  ~25 thread-free): owner is 4090; this session's progress was 6 PRs
  merged via REST PUT with sha pin. The pattern is documented; the
  queue is not.
