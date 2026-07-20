# /p7:room — Room lifecycle via P7 stage manager

Manage the room lifecycle (rehearsal → live → review → archive) via the
**P7** room-aware stage manager (FastAPI service on port **8120**).

## State machine

```
rehearsal ──► live ──► review ──► archive
                │        │
                └────────┴──► (review or archive)
```

- **`rehearsal → live`** is **gated** by the CHIT activation checklist
  (see [Canonical CHIT checklist](../../pmoves/docs/ROOM_MANIFEST_CONTRACT.md#chit-signing-card-activation-checklist)).
  P7 returns `422` with the unchecked items if any fail.
- **`live → review` / `live → archive` / `review → live` / `review → archive`** are ungated.
- **`archive` is terminal** — no further transitions.

The same stage on either side is an idempotent no-op (returns `noop: true`).

## Usage

```
/p7:room <action> <room_id> [options]
```

| Action | Description |
|---|---|
| `list` | List all rooms with their `current_stage` |
| `status` | Get one room's catalog row + manifest |
| `transition` | Transition a room to a new stage (gated on `rehearsal → live`) |
| `reload` | Force P7 to re-read the catalog from disk |

## Examples

### List all rooms

```bash
curl -s http://localhost:8120/api/p7/rooms | jq
```

### Get one room's status

```bash
curl -s http://localhost:8120/api/p7/rooms/z890-infra.room.fabric | jq
```

### Transition a room to `live` (gated — passes CHIT checklist)

```bash
curl -X POST http://localhost:8120/api/p7/rooms/z890-infra.room.fabric/transition \
  -H "Content-Type: application/json" \
  -d '{
    "target_stage": "live",
    "reason": "z890 brought up, all CHIT checks pass",
    "requester": "DARKXSIDE"
  }'
```

If the CHIT checklist fails:

```json
{
  "error": "chit_checklist_failed",
  "detail": "CHIT activation checklist failed: 1 item(s) unchecked",
  "unchecked": [
    "1. manifest.meta.chit.card_id is missing or empty"
  ]
}
```

### Transition live → review (ungated)

```bash
curl -X POST http://localhost:8120/api/p7/rooms/z890-infra.room.fabric/transition \
  -H "Content-Type: application/json" \
  -d '{"target_stage": "review", "reason": "audit pause", "requester": "DARKXSIDE"}'
```

### Reload catalog after manual edit

```bash
curl -X POST http://localhost:8120/api/p7/reload
```

## Healthcheck

```bash
curl -s http://localhost:8120/healthz | jq
# → { "status": "ok", "rooms_loaded": 9, "schema_version": "1.2.0",
#     "nats_connected": true, "service_card_id": null, "chit_require_signature": true }
```

## NATS events (subscribe to see transitions in real-time)

| Subject | Payload fields | When |
|---|---|---|
| `room.session.updated.v1` | `room_id, previous_stage, new_stage, reason, requester, chit{...}` | every transition |
| `p7.nats.launch` | `room_id, agent_id, alter, overlay, manifest_version, chit{...}` | reserved (room entered) |
| `p7.nats.session` | `room_id, session_id, action, agent_id, chit{...}` | reserved (session open/close) |
| `pmoves.config.rooms.reloaded.v1` | `schema_version, rooms_loaded, chit{...}` | on startup + `/api/p7/reload` |

Every payload has a `chit` block. `chit.status` is `signed` if P7 is configured
with a signing key, otherwise `unsigned-local` (per
`pmoves/.claude/BOOTSTRAP.md`).

## Room manifest

Rooms are defined in `pmoves/config/rooms/catalog.json` (schema_version 1.2.0+).
Each row carries `current_stage` (the live source of truth) and references
`manifest` (filename in `pmoves/config/rooms/`).

See:
- `pmoves/docs/ROOMS_ON_A_STAGE.md` — end-to-end room model
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — manifest interface + canonical CHIT checklist
- `pmoves/docs/specs/p7-service-spec-2026-07-20.md` — P7 service spec
- `pmoves/docs/specs/room-manifest-schema-extensions-2026-07-20.md` — schema extensions (operator-approved 2026-07-20)
- `pmoves/docs/AGENTS/AGNOTE4482.md` §P7 — P7 stage manager definition

## Troubleshooting

- **CHIT signature required**: rooms transitioning `rehearsal → live` must pass the
  CHIT/room activation checklist. See
  [`ROOM_MANIFEST_CONTRACT.md`](../../pmoves/docs/ROOM_MANIFEST_CONTRACT.md#chit-signing-card-activation-checklist).
  Most common failure: `meta.chit.card_id` missing from the manifest — add it
  in the manifest's `meta` block, or set up a signing card in
  `pmoves/config/signing_identity_cards.yaml` and reference it.
- **P7 service unreachable**: confirm `make -C pmoves up-p7` (or compose
  equivalent) and that port 8120 is exposed.
- **NATS disconnected**: P7 still serves HTTP transitions (catalog is local-file);
  NATS is the fanout. To reconnect, restart the service or wait for the
  exponential backoff to retry.
- **State-machine rejection (409)**: the requested `from → to` transition is
  not valid. The response body's `valid_next_stages` field tells you what's
  allowed from the current stage.
- **Schema-invalid manifest**: run `python pmoves/scripts/validate_room_manifests.py`
  to see which manifest fails the schema.

## What changed in this revision (2026-07-20)

- **Port 8092 → 8120** (8092 is taken by `pdf-ingest` and `publisher-discord`).
- **State machine vocabulary** is now the rooms-on-a-stage canonical
  `rehearsal/live/review/archive` (was `planned/active/paused/ended/archived`).
- **CHIT check** uses `meta.chit.card_id` (was `chit.capability/handler/integration/trigger`).
- **NATS subjects** are `p7.nats.launch` / `p7.nats.session` / `room.session.updated.v1`
  (was `p7.room.session.{started,checkpoint,ended}.v1`).
- **Endpoint** is `/api/p7/rooms/{id}/transition` (was
  `/api/v1/rooms/{id}/{start|pause|resume|end}`).
- **Catalog writeback**: `current_stage` is updated atomically on every transition.
- See [P7 service spec](../../pmoves/docs/specs/p7-service-spec-2026-07-20.md)
  for the full design.
