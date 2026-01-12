# Dockerfile Non-Root Container Permissions

**Date:** 2025-12-22
**Source:** PR #345 CodeRabbit review

## Issue

Dockerfile hardening added user creation but missed creating directories
needed by entrypoint scripts:
- entrypoint.sh writes to `/models` via `snapshot_download()`
- Directory doesn't exist or has wrong ownership

## Pattern

**Create and chown all directories written to at runtime BEFORE USER directive:**

```dockerfile
# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    mkdir -p /models && \
    chown -R pmoves:pmoves /app /app/vibevoice /models

USER pmoves
```

## Checklist for Dockerfile Hardening

1. **Identify write paths** - grep entrypoint/startup scripts for:
   - File writes
   - `mkdir` commands
   - Model downloads (HuggingFace, etc.)
   - Log directories
   - Cache directories

2. **Create directories** - Add `mkdir -p` for each path

3. **Set ownership** - Add to `chown -R pmoves:pmoves` list

4. **Order matters** - All `mkdir` and `chown` must be BEFORE `USER pmoves`

## Detection

```bash
# Find write operations in entrypoint scripts
grep -E "mkdir|>|>>|download|cache" services/*/entrypoint.sh
```

## Anti-Pattern

```dockerfile
# Bad - USER before mkdir means mkdir runs as non-root
USER pmoves
RUN mkdir -p /models  # Permission denied!
```

## Related

- `.claude/learnings/docker-entrypoint-patterns-2025.md`
- PMOVES Dockerfile hardening standard (UID/GID 65532)
