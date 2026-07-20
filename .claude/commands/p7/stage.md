# /p7:stage — Operate the P7 room-aware stage manager

Invoke the [`p7-stage` skill](../../skills/p7-stage/SKILL.md) for read/transition/observe
operations on the P7 room lifecycle (port **8120**). For the broader room
manifest schema and CHIT activation checklist, see
[`/p7:room`](./room.md).

## Three operations

| Operation | Purpose | HTTP / NATS |
|---|---|---|
| `claim <room_id>` | read a room's current stage + manifest summary | `GET /api/p7/rooms/{id}` |
| `transition <room_id> <target_stage> --reason "..."` | move a room (gated on `rehearsal → live` via CHIT checklist) | `POST /api/p7/rooms/{id}/transition` |
| `observe` | subscribe to lifecycle events for real-time UI / agent reaction | `nats sub room.session.updated.v1` |

## Usage

```
/p7:stage <operation> [args]
```

The slash command is a thin wrapper that surfaces the curl / nats invocations
the operator or agent would run by hand. The [`p7-stage` skill](../../skills/p7-stage/SKILL.md)
holds the full procedural detail (when to invoke, when NOT to invoke,
common pitfalls, CHIT checklist semantics).

## Examples

### `claim` — read a room's current stage

```
/p7:stage claim 4090-field.room.control
```
```bash
curl -s http://localhost:8120/api/p7/rooms/4090-field.room.control | jq
# → { "catalog_row": { "room_id": "4090-field.room.control", "current_stage": "live", ... },
#     "manifest": { "display_name": "4090 Field Control Room", ... },
#     "manifest_error": null }
```

To list all rooms:
```bash
curl -s http://localhost:8120/api/p7/rooms | jq '.rooms[] | {room_id, current_stage}'
```

### `transition` — move a room to a new stage

```
/p7:stage transition demo.room.rehearsal live --reason "demo room validated"
```
```bash
curl -X POST http://localhost:8120/api/p7/rooms/demo.room.rehearsal/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_stage": "live",
    "reason": "demo room validated end-to-end",
    "requester": "DARKXSIDE"
  }'
```

If the CHIT checklist fails (any of the 7 items from
[`ROOM_MANIFEST_CONTRACT.md`](../../pmoves/docs/ROOM_MANIFEST_CONTRACT.md)):
```json
{
  "error": "chit_checklist_failed",
  "detail": "CHIT activation checklist failed: 1 item(s) unchecked",
  "unchecked": [
    "1. manifest.meta.chit.card_id is missing or empty"
  ]
}
```
Address each `unchecked` item (add the `meta.chit.card_id` to the manifest, set
up the signing card in `pmoves/config/signing_identity_cards.yaml`, set
`PGRST_DB_EXTRA_SEARCH_PATH`, etc.), then retry.

If the state machine rejects (e.g. `rehearsal → review` skipping `live`):
```json
{
  "error": "invalid_transition",
  "detail": "invalid transition: rehearsal → review",
  "valid_next_stages": ["live"]
}
```
Chain transitions through the valid path.

### `observe` — subscribe to room lifecycle events

```
/p7:stage observe
```
```bash
# Subscribe to every room stage transition
nats sub 'room.session.updated.v1'
# → {"v":"1.0.0","room_id":"demo.room.rehearsal","previous_stage":"rehearsal",
#    "new_stage":"live","reason":"...","requester":"...","timestamp":"...","chit":{...}}

# Subscribe to catalog reloads
nats sub 'pmoves.config.rooms.reloaded.v1'
# → {"v":"1.0.0","schema_version":"1.2.0","rooms_loaded":9,"timestamp":"...","chit":{...}}
```

For UIs, the A2UI NATS bridge (`pmoves/services/a2ui-nats-bridge/bridge.py`,
port 9224) auto-forwards these to its `/ws/client` WebSocket consumers as
a `p7-rooms` envelope. See
[`p7-stage` skill](../../skills/p7-stage/SKILL.md#operation-3-observe--subscribe-to-room-lifecycle-events)
for the envelope shape.

## State machine (for reference)

```
rehearsal ──► live ──► review ──► archive
                │        │
                └────────┴──► (review or archive)
```

| from → to | Gated? |
|---|---|
| `rehearsal → live` | **YES** (canonical CHIT checklist) |
| `live → review` | no |
| `live → archive` | no |
| `review → live` | no |
| `review → archive` | no |
| same → same | idempotent no-op |
| `archive → *` | rejected (409) — terminal |

## Common pitfalls

| Symptom | Fix |
|---|---|
| `404` from `/api/p7/rooms/{id}` | Room not in `pmoves/config/rooms/catalog.json`. Add it (schema_version 1.2.0+ requires `current_stage`). |
| `409 invalid_transition` | Read the response's `valid_next_stages`; chain transitions through it. |
| `422 chit_checklist_failed` | The `unchecked` list is operator-actionable. Address each, then retry. |
| NATS subject has no traffic | `curl http://localhost:8120/healthz | jq .nats_connected`. If false, restart `make -C pmoves up-p7`. |
| `meta.chit.card_id is missing` (item 1) | Add `meta.chit.card_id: "<uuid>"` to the room's `*.room.json` AND a matching row in `pmoves/config/signing_identity_cards.yaml`. |
| Port 8120 collision | 8092 is taken by `pdf-ingest` + `publisher-discord`; 8120 should be free. `lsof -i :8120` to confirm. |

## Cross-references

- Skill (full procedural detail): [`.claude/skills/p7-stage/SKILL.md`](../../skills/p7-stage/SKILL.md)
- Sibling command (manifest-level operations): [`.claude/commands/p7/room.md`](./room.md)
- Service spec: [`pmoves/docs/specs/p7-service-spec-2026-07-20.md`](../../pmoves/docs/specs/p7-service-spec-2026-07-20.md)
- Canonical CHIT checklist: [`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](../../pmoves/docs/ROOM_MANIFEST_CONTRACT.md)
- Rooms-on-a-stage model: [`pmoves/docs/ROOMS_ON_A_STAGE.md`](../../pmoves/docs/ROOMS_ON_A_STAGE.md)
- Service code: [`pmoves/services/p7-room-orchestrator/`](../../pmoves/services/p7-room-orchestrator/)
- Service README: [`pmoves/services/p7-room-orchestrator/README.md`](../../pmoves/services/p7-room-orchestrator/README.md)
- A2UI bridge consumer (auto-forwards to WebSocket): [`pmoves/services/a2ui-nats-bridge/bridge.py`](../../pmoves/services/a2ui-nats-bridge/bridge.py)
- AGNOTE lane trail: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (search "Mavis::OPEN-ROOM-LANE")

## What changed in this revision (2026-07-20)

- **New slash command** (sibling to `/p7:room`). `/p7:room` is the
  manifest-level operator interface; `/p7:stage` is the lifecycle-level
  one. The room manifest contract envisions both — `/p7:room` for
  declaring what a room IS, `/p7:stage` for moving it through its life.
- **Backed by the [`p7-stage` skill](../../skills/p7-stage/SKILL.md)** —
  the slash command is a thin invocation surface; the skill is where the
  procedural detail (when / when-not / pitfalls / cross-refs) lives.
- **Three operations**: claim (read), transition (mutate, gated), observe
  (subscribe). Matches the P7 service's `/api/p7/rooms` +
  `/api/p7/rooms/{id}/transition` endpoints and the spec'd NATS subjects.
