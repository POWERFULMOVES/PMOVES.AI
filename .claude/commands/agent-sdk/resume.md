# Resume PMOVES Agent Session

Resume a previous agent session with full context preservation.

## Usage

Use this command when:
- Continuing an interrupted task
- Resuming from a previous checkpoint
- Picking up work from an earlier session

## Implementation

Execute via PMOVES CLI:

```bash
pmoves agent-sdk resume list
# List recent sessions

pmoves agent-sdk resume session-abc123
# Resume specific session with full context

pmoves agent-sdk resume session-abc123 "Continue the analysis"
# Resume with additional task context
```

### Arguments

- `session-id` - Session ID to resume, or "list" to show recent sessions

### Options

- `--task` - Additional task context for resumption (optional)

## What It Does

- ✅ Lists recent sessions with status
- ✅ Loads session state from storage
- ✅ Restores agent configuration and context
- ✅ Continues from last checkpoint
- ✅ Preserves conversation history
- ✅ Maintains tool execution state

### Session States

| State | Description | Can Resume |
|-------|-------------|------------|
| `active` | Currently running | ❌ Already running |
| `paused` | Suspended, can resume | ✅ Ready to resume |
| `completed` | Finished successfully | ✅ Can fork new session |
| `failed` | Terminated with error | ✅ Can retry |
| `forked` | Branched into new session | ❌ Use child session |

### Storage Backends

Sessions are stored based on `SESSION_STORAGE` env var:
- `file` (default): `~/.pmoves/sessions/`
- `supabase`: `agent_sessions` table
- `surrealdb`: Open Notebook integration

## Example

```bash
$ pmoves agent-sdk resume list

📋 Recent Sessions:
   session-abc123: pmoves-researcher-1735123456 (paused) - 2025-01-15 14:23:01
   session-def456: pmoves-code-reviewer-1735123490 (completed) - 2025-01-15 15:10:22
   session-ghi789: pmoves-researcher-1735123456 (failed) - 2025-01-15 16:05:33

$ pmoves agent-sdk resume session-abc123

🔄 Loading session: session-abc123
📦 Agent: pmoves-researcher-1735123456
📝 Last Task: "Analyze PMOVES architecture"
✅ Context restored from checkpoint

Continuing from where we left off...
[Agent continues with full conversation history]
```

## Related Commands

- `pmoves agent-sdk create` - Create new agent instance
- `pmoves agent-sdk run` - Execute task with agent
- `pmoves agent-sdk list` - List all agents
- `pmoves agent-sdk status` - Check agent status

## Notes

- **Session ID Required**: Use `list` argument to find session IDs
- **Context Preservation**: Full conversation history and tool state restored
- **Checkpoint System**: Agents auto-save progress at key milestones
- **Storage Location**: Configured via `SESSION_STORAGE` environment variable

## Troubleshooting

**"Session not found"**
- Verify session ID with: `pmoves agent-sdk resume list`
- Check storage backend is accessible (file system, Supabase, etc.)

**"Session state corrupted"**
- Session may have been interrupted during save
- Try creating new session instead: `pmoves agent-sdk create`

**"Cannot resume active session"**
- Session is currently running in another process
- Wait for completion or use `pmoves agent-sdk status` to check

**"Storage backend unavailable"**
- Check `SESSION_STORAGE` environment variable
- Verify backend connectivity:
  - File: Check `~/.pmoves/sessions/` exists
  - Supabase: Test connection with `psql`
  - SurrealDB: Verify Open Notebook is running
