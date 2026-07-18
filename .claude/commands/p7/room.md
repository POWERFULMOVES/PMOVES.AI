# P7 Room and Session Management

Manage persistent room stage and transient session state through the P7 room
orchestrator on port 8122.

## Usage

```text
/p7:room <action> <room_id> [target]
```

| Action | API operation |
|---|---|
| `list` | `GET /api/v1/rooms` |
| `status` | `GET /api/v1/rooms/{room_id}` |
| `start` | Start a transient session |
| `pause` | Pause an active session |
| `resume` | Resume a paused session |
| `end` | End an active or paused session |
| `archive-session` | Archive an ended session |
| `stage` | Transition persistent room stage to `live`, `review`, or `archive` |

Examples:

```bash
curl -X POST http://localhost:8122/api/v1/rooms/z890-infra.room.fabric/start
curl -X POST http://localhost:8122/api/v1/rooms/z890-infra.room.fabric/stage \
  -H "Content-Type: application/json" \
  -d '{"target":"live"}'
curl http://localhost:8122/api/v1/rooms/z890-infra.room.fabric
```

Room stage is `rehearsal -> live -> review -> archive`. Session state is
`planned -> active <-> paused -> ended -> archived`. Starting a rehearsal session
does not promote the room to live.

Before `rehearsal -> live`, verify the room activation checklist in
`pmoves/docs/ROOMS_ON_A_STAGE.md`: signing card, registry reachability, topology
toggles, PostgREST schema exposure, and durable audit persistence must all pass.

NATS clients may publish commands to `p7.nats.launch` and `p7.nats.session`.
Consumers should observe versioned `p7.room.*.v1` facts rather than treating a
command publication as proof that a transition succeeded.
