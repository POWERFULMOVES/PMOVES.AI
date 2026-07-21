---
name: p7-stage
description: Operate the P7 room-aware stage manager — read a room's current stage, transition a room (gated rehearsal→live via the canonical CHIT activation checklist), and observe lifecycle events on NATS. Use when claiming/transitioning a room, when the operator asks "what stage is room X in?", or when wiring a UI to reflect room transitions in real-time.
disable-model-invocation: false
user-invocable: true
---

# p7-stage

Procedural skill for interacting with the **P7** room-aware stage manager
(`pmoves/services/p7-room-orchestrator/`, FastAPI on port **8120**).

P7 is the canonical owner of the room lifecycle per the rooms-on-a-stage
model (`pmoves/docs/ROOMS_ON_A_STAGE.md`). The state machine is:

```
rehearsal ──► live ──► review ──► archive
                │        │
                └────────┴──► (review or archive)
```

- **`rehearsal → live`** is **gated** by the canonical CHIT activation
  checklist (7 items, single source of truth in
  `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` § "CHIT Signing-Card Activation
  Checklist"). P7 returns `422` with the unchecked items if any fail.
- **`live → review` / `live → archive` / `review → live` / `review → archive`**
  are ungated.
- **`archive` is terminal** — no further transitions.
- Same → same is an idempotent no-op (`noop: true` in the response).

Three operations: **claim** (read state), **transition** (mutate state),
**observe** (subscribe to events).

## When to invoke

- Operator asks "what stage is room X in?" / "is the demo room live yet?"
- A PR or lane claim requires a room to be `live` to do real work.
- Wiring a UI surface to reflect room transitions (badge / banner / status pill).
- Auditing: "when did room X last transition?" — answer comes from the
  subscribed NATS stream (or from the per-room catalog row's
  `stage_verified_at`).
- Operator wants to pause a room for review or archive a retired room.

## When NOT to invoke

- Skill execution, model routing, notebook writeback — those are the agent
  runtime's job, not P7's. P7 owns lifecycle state, not workload.
- Creating or editing a room manifest — that's the catalog/manifest lane
  (separate concern; P7 reads what the catalog gives it).
- Cross-node peer discovery — use `Agent Zero /mcp/*` or A2A, not P7.

## Procedural steps (Claude follows this in order)

### Operation 1: `claim` — read a room's current stage

1. **Confirm the P7 service is up.** `curl -sf http://localhost:8120/healthz`
   must return `{"status": "ok", ...}`. If not, surface
   `make -C pmoves up-p7` and pause.
2. **Fetch the catalog row.** `GET /api/p7/rooms` returns the full list
   (with `current_stage` per row). For one room, `GET /api/p7/rooms/{room_id}`.
3. **Read the manifest (optional, for full detail).** The detail endpoint
   returns `catalog_row` + the full validated manifest + any
   `manifest_error` (e.g. schema drift).
4. **Report.** Tell the operator the room's `current_stage` and
   `stage_verified_at`. If the stage is `rehearsal` and they want it `live`,
   proceed to Operation 2.

```bash
# All rooms
curl -s http://localhost:8120/api/p7/rooms | jq '.rooms[] | {room_id, current_stage, agent_id}'

# One room
curl -s http://localhost:8120/api/p7/rooms/4090-field.room.control | jq
```

### Operation 2: `transition` — move a room to a new stage

1. **Pre-check.** Call `claim` (Operation 1) to confirm the current stage.
   The transition must respect the state machine (see diagram above);
   otherwise P7 returns `409` with `valid_next_stages` in the body.
2. **Construct the request body.** All three fields are required:
   ```json
   {
     "target_stage": "live|review|archive|rehearsal",
     "reason": "<operator-supplied reason for audit trail; min 1 char>",
     "requester": "<agent_id or operator handle>"
   }
   ```
3. **POST the transition.** `POST /api/p7/rooms/{room_id}/transition` with
   the body. P7 will:
   - **Idempotent no-op** if `current_stage == target_stage` (returns
     `noop: true`).
   - **State-machine rejection** if the transition is invalid (returns
     `409` with `valid_next_stages`).
   - **CHIT gate** on `rehearsal → live` (returns `422` with `unchecked` list
     if any of the 7 items fail; otherwise proceeds).
   - **Atomic catalog writeback** of `current_stage` + `stage_verified_at`.
   - **NATS publish** on `room.session.updated.v1` with a `chit` envelope.
     The envelope is `signed` (HMAC-SHA256) when `P7_SERVICE_CARD_ID` +
     `P7_SIGNING_KEY` are both set, otherwise `unsigned-local` (per
     `.claude/BOOTSTRAP.md` § "Signing is optional locally" — same convention
     used elsewhere in PMOVES for local-dev).
4. **Report.** Tell the operator the result. If `422`, surface the
   `unchecked` items verbatim — they are operator-actionable (each maps to
   a specific checklist line in `ROOM_MANIFEST_CONTRACT.md`).

```bash
curl -X POST http://localhost:8120/api/p7/rooms/z890-infra.room.fabric/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_stage": "live",
    "reason": "z890 brought up; all CHIT checks pass per 2026-07-20 audit",
    "requester": "DARKXSIDE"
  }'
```

### Operation 3: `observe` — subscribe to room lifecycle events

P7 publishes two NATS subjects to the control plane (per
`pmoves/docs/specs/p7-service-spec-2026-07-20.md` §6):

| Subject | When | Payload |
|---|---|---|
| `room.session.updated.v1` | on every stage transition | `room_id, previous_stage, new_stage, reason, requester, chit{...}` |
| `pmoves.config.rooms.reloaded.v1` | on startup + `/api/p7/reload` | `schema_version, rooms_loaded, chit{...}` |

Every payload has a `chit` block (`{kid, ts, status, signature}`).
`chit.status` is `signed` if P7 is configured with a signing key, otherwise
`unsigned-local` per `pmoves/.claude/BOOTSTRAP.md` § "Signing is optional
locally".

1. **Pick the subscription mechanism.** The A2UI NATS bridge
   (`pmoves/services/a2ui-nats-bridge/bridge.py`, port 9224) auto-forwards
   these events to its `/ws/client` WebSocket consumers as a `p7-rooms`
   envelope — that's the recommended path for UIs. For pure CLI / agent
   observation, use the NATS CLI directly:
   ```bash
   nats sub 'room.session.updated.v1'   # transitions only
   nats sub 'pmoves.config.rooms.reloaded.v1'  # catalog reloads
   nats sub '>'                          # everything (debug only)
   ```
2. **Act on the event.** When you see a `room.session.updated.v1` payload,
   the `previous_stage → new_stage` delta tells you what changed. Common
   handlers: update a UI badge; clear cached manifests for that room; emit
   a downstream signal (e.g. an A2UI surface update); trigger a test
   against the new stage.
3. **Acknowledge CHIT failures.** If a transition returns `422`, the
   NATS event was NOT published (the gate failed pre-publish). Don't
   re-attempt the transition without addressing the unchecked items.

## Common pitfalls (and their fixes)

| Symptom | Cause | Fix |
|---|---|---|
| `404` from `/api/p7/rooms/{id}` | room not in catalog | Add the room to `pmoves/config/rooms/catalog.json` (schema_version 1.2.0+ requires `current_stage`) |
| `409 invalid_transition` | state machine rejects | Read the response's `valid_next_stages` field; chain transitions |
| `422 chit_checklist_failed` | one or more of the 7 CHIT items fail | The response's `unchecked` list is the spec; address each, then retry |
| NATS subject has no traffic | P7 service not connected to NATS | `curl http://localhost:8120/healthz | jq .nats_connected`; restart `make -C pmoves up-p7` if false |
| `meta.chit.card_id is missing` (item 1) | manifest doesn't reference a signing card | Add `meta.chit.card_id: "<uuid>"` to the room's `*.room.json` manifest, AND add a row in `pmoves/config/signing_identity_cards.yaml` |
| Port 8120 collision | other service grabbed it | 8092 is taken by `pdf-ingest` + `publisher-discord`; 8120 should be free. `lsof -i :8120` to confirm |

## Inputs expected at invocation time

- `room_id` — the catalog room_id (e.g. `4090-field.room.control`)
- `target_stage` — one of `rehearsal`, `live`, `review`, `archive`
- `reason` — operator-supplied audit string (min 1 char)
- `requester` — agent or operator handle
- For `observe`: which subject(s) to subscribe to, and what handler to wire

## Outputs / side effects

- `claim` → in-memory read; no side effects
- `transition` → atomic writeback of `catalog.json` (the `current_stage` row);
  one signed NATS publish on `room.session.updated.v1`
- `observe` → no side effects; receives events

## Cross-references

- Service spec: [`pmoves/docs/specs/p7-service-spec-2026-07-20.md`](../../pmoves/docs/specs/p7-service-spec-2026-07-20.md)
- Canonical CHIT checklist: [`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](../../pmoves/docs/ROOM_MANIFEST_CONTRACT.md)
- Rooms-on-a-stage model: [`pmoves/docs/ROOMS_ON_A_STAGE.md`](../../pmoves/docs/ROOMS_ON_A_STAGE.md)
- Schema extensions (operator-approved 2026-07-20): [`pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md`](../../pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md)
- Service code: [`pmoves/services/p7-room-orchestrator/`](../../pmoves/services/p7-room-orchestrator/)
- Service README: [`pmoves/services/p7-room-orchestrator/README.md`](../../pmoves/services/p7-room-orchestrator/README.md)
- Operator slash command: [`.claude/commands/p7/room.md`](../commands/p7/room.md)
- A2UI bridge consumer (auto-forwards to WebSocket): [`pmoves/services/a2ui-nats-bridge/bridge.py`](../../pmoves/services/a2ui-nats-bridge/bridge.py)
- AGNOTE lane trail: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (search "Mavis::OPEN-ROOM-LANE")
- Related skills: `pmoves-nats-subject-audit`, `pmoves-chit-sign`, `pmoves-mesh-preflight`
