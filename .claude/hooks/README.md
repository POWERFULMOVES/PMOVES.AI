# Claude Code CLI Hooks

Optional hooks for Claude Code CLI to provide security validation and NATS observability.

## Purpose

**Pre-tool hook (`pre-tool.sh`):**
- Validates commands before execution
- Blocks dangerous operations (rm -rf /, DROP DATABASE, etc.)
- Warns about potentially risky operations
- Logs security events

**Post-tool hook (`post-tool.sh`):**
- Publishes tool execution to NATS (`claude.code.tool.executed.v1`)
- Enables observability in PMOVES monitoring dashboards
- Falls back to local logging if NATS unavailable

## Installation

### Option 1: Claude Code CLI Settings (Recommended)

Configure hooks in Claude Code CLI settings:

```json
{
  "hooks": {
    "preToolExecution": ".claude/hooks/pre-tool.sh",
    "postToolExecution": ".claude/hooks/post-tool.sh"
  }
}
```

### Option 2: Environment Variables

```bash
export CLAUDE_PRE_TOOL_HOOK="$PWD/.claude/hooks/pre-tool.sh"
export CLAUDE_POST_TOOL_HOOK="$PWD/.claude/hooks/post-tool.sh"
```

### Option 3: Manual Execution (Testing)

Test hooks manually:

```bash
# Test pre-tool hook
./.claude/hooks/pre-tool.sh "Bash" "echo 'test command'"

# Test with blocked pattern
./.claude/hooks/pre-tool.sh "Bash" "rm -rf /"

# Test post-tool hook
./.claude/hooks/post-tool.sh "Bash" "success"
```

## Pre-Tool Hook: Security Validation

### Blocked Patterns

The following operations are **always blocked**:

- `rm -rf /` - Recursive root deletion
- `DROP DATABASE` / `DROP TABLE` / `TRUNCATE TABLE` - Database destruction
- `supabase db reset --force` - Forced database reset
- `docker system prune -a` - Remove all Docker resources
- `docker volume rm` - Volume deletion
- `> /dev/sda` - Writing to raw disk
- `dd if=/dev/zero` - Disk wiping
- `mkfs.*` - Filesystem formatting

### Warnings (Not Blocked)

The following trigger **warnings** but don't block:

- Writing to `/etc/` directory
- Overly permissive chmod (777, 666)
- Modifying sensitive files (`.ssh/`, `.env`, files with "password" in path)

### Security Event Logging

Blocked operations are logged to: `$HOME/.claude/logs/security-events.log`

```
[2025-12-06T12:00:00Z] BLOCKED: Bash - Pattern: rm -rf / - User: pmoves
```

## Post-Tool Hook: NATS Observability

### Event Format

Published to NATS subject: `claude.code.tool.executed.v1`

```json
{
  "tool": "Bash",
  "status": "success",
  "timestamp": "2025-12-06T12:00:00Z",
  "user": "pmoves",
  "session_id": "1733501234",
  "hostname": "pmoves-dev"
}
```

### NATS Configuration

Set environment variables:

```bash
export NATS_URL="nats://localhost:4222"  # Default
```

### Fallback: Local Logging

If `nats-cli` is not installed or NATS is unavailable, events are logged locally:

**Location:** `$HOME/.claude/logs/tool-events.jsonl`

```jsonl
{"tool": "Bash", "status": "success", "timestamp": "2025-12-06T12:00:00Z", ...}
{"tool": "Read", "status": "success", "timestamp": "2025-12-06T12:01:00Z", ...}
```

## Monitoring Hook Events

### Subscribe to NATS Events

```bash
# Watch all Claude CLI tool events
nats sub "claude.code.tool.executed.v1"

# Filter specific tool
nats sub "claude.code.tool.executed.v1" | grep '"tool":"Bash"'
```

### Query Prometheus Metrics (Future)

If integrated with Prometheus:

```promql
# Tool execution count
sum(rate(claude_code_tool_executions_total[5m])) by (tool)

# Blocked operations
sum(rate(claude_code_pre_hook_blocks_total[5m])) by (pattern)
```

### View Local Logs

```bash
# Security events
tail -f ~/.claude/logs/security-events.log

# Tool events (if NATS unavailable)
tail -f ~/.claude/logs/tool-events.jsonl | jq .
```

## Customization

### Add Custom Blocked Patterns

Edit `pre-tool.sh`:

```bash
declare -a BLOCKED_PATTERNS=(
    # ... existing patterns ...
    "your-custom-pattern"
    "another-dangerous-command"
)
```

### Add Custom Event Metadata

Edit `post-tool.sh` to include additional context:

```bash
PAYLOAD=$(cat <<EOF
{
  "tool": "$TOOL_NAME",
  "status": "$TOOL_STATUS",
  "timestamp": "$TIMESTAMP",
  "user": "$USER",
  "custom_field": "your_value",
  "project": "PMOVES.AI"
}
EOF
)
```

## Troubleshooting

**Hooks not executing:**
- Check file permissions: `ls -l .claude/hooks/*.sh` (should be executable)
- Verify Claude Code CLI configuration
- Check hook output: Hooks log to stderr

**NATS connection failed:**
- Hooks fall back to local logging automatically
- Check NATS is running: `nats server info`
- Verify NATS_URL environment variable

**False positive blocks:**
- Review blocked pattern list in `pre-tool.sh`
- Comment out overly aggressive patterns
- Report issues for refinement

## Integration with PMOVES Monitoring

Once services are running, hook events flow into:

1. **NATS** → `claude.code.tool.executed.v1` subject
2. **Supabase** → Store events for historical analysis (optional)
3. **Grafana** → Dashboard showing Claude CLI activity (optional)
4. **Discord** → Notifications for blocked operations (optional)

## Disabling Hooks

To temporarily disable:

**Option 1: Remove from settings**
```json
{
  "hooks": {}
}
```

**Option 2: Rename files**
```bash
mv .claude/hooks/pre-tool.sh .claude/hooks/pre-tool.sh.disabled
mv .claude/hooks/post-tool.sh .claude/hooks/post-tool.sh.disabled
```

**Option 3: Empty hook script**
```bash
echo '#!/bin/bash\nexit 0' > .claude/hooks/pre-tool.sh
```

## Best Practices

1. **Keep hooks fast** - They run on every tool execution
2. **Fail gracefully** - Post-hook always exits 0 (doesn't block Claude)
3. **Log comprehensively** - Both security events and tool usage
4. **Review logs regularly** - Check for security incidents
5. **Update patterns** - Add new dangerous patterns as discovered

## Security Notes

- Hooks run with **user permissions** (not root)
- Pre-hook can **block execution** (security gate)
- Post-hook **cannot block** (observability only)
- Logs contain **potentially sensitive info** (command parameters)
- Rotate logs periodically to manage disk space

## Contributing

When adding new blocked patterns:
1. Test thoroughly (avoid false positives)
2. Document why pattern is dangerous
3. Consider if warning is sufficient vs. blocking
4. Update this README with new patterns
