# Docker Entrypoint Patterns - Learnings from PR #333

**Date:** 2025-12-19
**PR:** #333 (Hi-RAG Docker Restart Stability)
**Source:** CodeRabbit review (incorrectly flagged as critical)

## Pattern: Two-Phase Startup with exec in Child Script

### The Pattern

```dockerfile
RUN printf '#!/bin/bash\nset -e\n/app/scripts/wait-for-deps.sh /bin/true\nexec /opt/nvidia/nvidia_entrypoint.sh "$@"\n' > /app/entrypoint-wrapper.sh
```

Where `wait-for-deps.sh` ends with:
```bash
exec "$@"
```

### Why This Works (Not a Bug)

CodeRabbit flagged this as a **Critical** bug, claiming the wrapper's second `exec` would never run because `wait-for-deps.sh`'s `exec "$@"` replaces the process.

**This is incorrect.** The `exec` in `wait-for-deps.sh` only replaces the CHILD process, not the parent wrapper.

### Process Flow

1. **Wrapper starts** (PID 1 in container)
2. **Wrapper forks** `/app/scripts/wait-for-deps.sh /bin/true` (new child PID)
3. **wait-for-deps.sh** performs health checks
4. **wait-for-deps.sh** runs `exec /bin/true` - replaces CHILD with `/bin/true`
5. **`/bin/true` exits** with status 0
6. **Wrapper continues** (was waiting for child to exit)
7. **Wrapper runs** `exec /opt/nvidia/nvidia_entrypoint.sh "$@"` - replaces wrapper with NVIDIA entrypoint

### Key Insight

When you **call a script** (not source it), that script runs in a **subshell**. Any `exec` in that script only affects the subshell process, not the parent caller.

```bash
# This works correctly:
/some/script.sh arg1 arg2    # script.sh's exec replaces the child, not parent
echo "This WILL print"       # Parent continues after child exits

# This would NOT work:
source /some/script.sh arg1 arg2  # Sourced scripts run in same process
echo "This won't print if script.sh has exec"
```

### When to Use This Pattern

1. **GPU containers** - Need NVIDIA entrypoint but also dependency waiting
2. **Service readiness** - Wait for databases/services before starting app
3. **Multi-stage initialization** - Each stage does specific setup then exits

### Documentation for Reviewers

When you see wrapper scripts calling child scripts that use `exec`:
- The `exec` only affects the child process
- The parent wrapper continues after the child exits
- This is a valid pattern, not a logic error

## Related Fixes Made

| Issue | Status |
|-------|--------|
| CodeRabbit "Critical: wrapper logic flawed" | ✅ Explained (not a bug) |
| Redundant `import time` inside function | ✅ Fixed |
| Duplicate module imports | ✅ Fixed |
