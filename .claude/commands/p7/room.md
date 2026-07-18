# P7 Room and Session Management

Manage persistent room stage and transient session state through the P7 room
orchestrator on port 8122.

## Usage

```text
/p7:room <action> <room_id> [target]
```

| Action | API operation | Description |
|---|---|---|
| `list` | `GET /api/v1/rooms` | List rooms and current state |
| `status` | `GET /api/v1/rooms/{room_id}` | Get one room's status |
| `start` | `POST /api/v1/rooms/{room_id}/start` | Start or roll over a transient session |
| `pause` | `POST /api/v1/rooms/{room_id}/pause` | Pause an active session |
| `resume` | `POST /api/v1/rooms/{room_id}/resume` | Resume a paused session |
| `end` | `POST /api/v1/rooms/{room_id}/end` | End an active or paused session |
| `archive-session` | `POST /api/v1/rooms/{room_id}/archive-session` | Archive an ended session |
| `stage` | `POST /api/v1/rooms/{room_id}/stage` | Transition persistent stage to `live`, `review`, or `archive` |

Examples:

```bash
curl -X POST http://localhost:8122/api/v1/rooms/z890-infra.room.fabric/start \
  -H "Authorization: Bearer $P7_CONTROL_TOKEN"
curl -X POST http://localhost:8122/api/v1/rooms/z890-infra.room.fabric/stage \
  -H "Authorization: Bearer $P7_CONTROL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target":"live","proof":{"card_id":"<uuid>","nonce":"<random-16+-chars>","issued_at":<unix-seconds>,"signature":"<base64-ed25519-signature>"}}'
curl http://localhost:8122/api/v1/rooms/z890-infra.room.fabric
```

Room stage is `rehearsal -> live -> review -> archive`. Session state is
`planned -> active <-> paused -> ended -> archived`. Starting a rehearsal session
does not promote the room to live.

Mutating HTTP operations require the P7 control bearer token. Before
`rehearsal -> live`, verify the room activation checklist in
`pmoves/docs/ROOMS_ON_A_STAGE.md`: signing card, registry reachability, topology
toggles, PostgREST schema exposure, durable audit persistence, and fresh
nonce-bound Ed25519 proof-of-possession must all pass. The canonical signed
message format is documented in `pmoves/services/p7-room-orchestrator/README.md`.

NATS clients may publish commands to `p7.nats.launch` and `p7.nats.session`.
Consumers should observe versioned `p7.room.*.v1` facts rather than treating a
command publication as proof that a transition succeeded.
