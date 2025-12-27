# Resume PMOVES Agent Session

Resume a previous agent session with full context preservation.

## Arguments

- `$ARGUMENTS` - Session ID to resume (or "list" to show recent sessions)

## Instructions

### List Sessions

If argument is "list" or empty:
```python
from pmoves_botz.features.agent_sdk import PMOVESSessionManager

manager = PMOVESSessionManager()
sessions = await manager.list_sessions(limit=10)
for s in sessions:
    print(f"{s.session_id}: {s.agent_id} ({s.status}) - {s.created_at}")
```

### Resume Session

1. Load session state from storage (file/Supabase/SurrealDB)
2. Restore agent configuration and context
3. Continue from last checkpoint:

```python
from pmoves_botz.features.agent_sdk import PMOVESSessionManager

manager = PMOVESSessionManager()
async for message in manager.resume(
    session_id="$ARGUMENTS",
    task="Continue from where we left off"
):
    print(message.content)
```

### Session States

| State | Description |
|-------|-------------|
| `active` | Currently running |
| `paused` | Suspended, can resume |
| `completed` | Finished successfully |
| `failed` | Terminated with error |
| `forked` | Branched into new session |

### Storage Backends

Sessions are stored based on `SESSION_STORAGE` env var:
- `file` (default): `~/.pmoves/sessions/`
- `supabase`: `agent_sessions` table
- `surrealdb`: Open Notebook integration

## Example

```bash
/agent-sdk:resume list
# Shows: session-abc123: pmoves-researcher-1703123456 (paused) - 2025-01-15

/agent-sdk:resume session-abc123
# Resumes session with full context
# Agent continues from last checkpoint
```
