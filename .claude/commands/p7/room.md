# P7 Room Session Management

Manage room session lifecycle via the P7 room orchestrator API.

## Usage

```
/p7:room <action> <room_id> [options]
```

## Actions

| Action | Description |
|--------|-------------|
| `start` | Start a new room session |
| `pause` | Pause an active room session |
| `resume` | Resume a paused room session |
| `end` | End and archive a room session |
| `status` | Check current room session state |

## Examples

### Start a room session
```
/p7:room start z890-infra
```
```bash
curl -X POST http://localhost:8080/api/v1/rooms/z890-infra/sessions \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "z890-claude"}'
```

### Pause a session
```
/p7:room pause z890-infra --session-id <uuid>
```

### Check status
```
/p7:room status z890-infra
```

## Room Manifests

Rooms are defined in `pmoves/config/rooms/catalog.json`. Each room has a manifest
with `mcp_servers`, `a2a_servers`, and lifecycle states (`planned` → `active` → `review` → `archive`).

See:
- `pmoves/docs/ROOMS_ON_A_STAGE.md` — end-to-end room model
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — manifest interface specification
- `pmoves/docs/AGENTS/AGNOTE4482.md` §P7 — P7 stage manager definition

## Troubleshooting

- **Room not found**: Verify room exists in `pmoves/config/rooms/catalog.json`
- **Session not found**: Use `/p7:room status <room_id>` to list active sessions
- **CHIT signature required**: Rooms transitioning `planned → active` must pass the
  CHIT/room activation checklist (see AGNOTE4482.md)
