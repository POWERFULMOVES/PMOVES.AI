# KiloCode Damage-Control Hooks — Quick Reference

> **Status:** 🚧 BLOCKED — Awaiting KiloCode/OpenCode hook API  
> **Estimated activation time:** ~35 minutes when platform support lands

---

## Check Status

```bash
make -C pmoves kilo-parity-check
```

Expected output:
- ✅ 11 items ready
- ⚠️  1 item blocked (hook implementation)
- 0 gaps found

---

## Files

| File | Purpose |
|------|---------|
| `.kilo/hooks/damage-control/patterns.yaml` | 92 security patterns (synced with Claude Code) |
| `.kilo/hooks/damage-control/README.md` | Full documentation + activation plan |
| `.kilo/hooks/IMPLEMENTATION_STATUS.md` | Implementation tracking + acceptance criteria |
| `.kilo/hooks/QUICK_REFERENCE.md` | This file — operator quick reference |
| `.kilo/hooks/damage-control/SYNC_NOTES.md` | Pattern synchronization notes |

---

## What Patterns Block

### Hard Block (Never Execute)
- Destructive file ops: `rm -rf`, `sudo rm`
- Git force ops: `git reset --hard`, `git push --force`
- System destruction: `mkfs`, `dd of=/dev/`
- Cloud ops: `aws ec2 terminate-instances`, `gcloud projects delete`
- Docker mass removal: `docker rm $(docker ps -aq)`
- SQL catastrophic: `DELETE FROM` without WHERE, `DROP DATABASE`

### Ask Before Executing
- Pipeline bypasses: `docker compose up -d`, `docker compose restart`
- Volume operations: `docker volume rm`, `docker volume prune`
- NATS ops: `nats stream delete`, `nats stream purge --all`
- Git operations: `git branch -D`, `git push --delete`
- GitHub workflows: `gh workflow run`
- Secrets funnel: `make secrets-funnel`

### Access Control
- **Zero access** (blocked entirely): `.env*`, `*.pem`, `*.key`, secrets, credentials
- **Read-only**: Lock files, build artifacts, migrations, system directories
- **No-delete**: `.kilo/`, `kilo.json`, licenses, READMEs, git config, Docker config

---

## Known Roads (Correct Paths)

| Raw Command | Use This Instead |
|-------------|------------------|
| `docker system prune -a` | `make -C pmoves docker-prune` |
| `docker volume rm <vol>` | `make -C pmoves volume-reset SERVICE=<name>` |
| `docker compose up -d` | `make -C pmoves up-<service>` |
| `docker compose restart` | `make -C pmoves up-<service>` |
| `netsh interface portproxy` | `make -C pmoves z890-host-setup` |
| Raw `psql` | Use Supabase REST API or `/db:query` skill |
| Raw `clickhouse-client` | Use TensorZero UI (port 4000) or API (port 3030) |

---

## Activation Plan (When Platform Supports Hooks)

### 1. Verify (5 min)
```bash
# Test hook invocation
echo "rm -rf /" | kilo bash --dry-run

# Check for hook API documentation
kilo --help | grep -i hook
```

### 2. Implement (15 min)
Create `.kilo/hooks/pre-tool.sh`:
```bash
#!/bin/bash
# Mirror .claude/hooks/pre-tool.sh structure
# Load patterns from patterns.yaml
# Implement pattern matching
# Add logging to ~/.kilo/logs/security-events.log
```

### 3. Integrate (10 min)
Update `kilo.json`:
```json
{
  "hooks": {
    "preTool": ".kilo/hooks/pre-tool.sh"
  }
}
```

Test with destructive patterns:
```bash
kilo bash "docker compose up -d"  # Should prompt
kilo bash "rm -rf /"               # Should block
```

### 4. Document (5 min)
- Update `.kilo/hooks/damage-control/README.md` — remove BLOCKED status
- Update `KILOCODE_OPERATOR_HOME.md` — add hooks section
- Close issue #2120

---

## Pattern Synchronization

```bash
# Check for differences
diff .claude/hooks/damage-control/patterns.yaml \
     .kilo/hooks/damage-control/patterns.yaml

# After manual review + update:
# 1. Update "Last sync" comment in patterns.yaml
# 2. Update SYNC_NOTES.md with new pattern counts
# 3. Run parity check
make -C pmoves kilo-parity-check
```

Sync frequency: **Monthly** or when major Claude Code patterns change

---

## Examples (When Hooks Are Active)

### Hard Block
```bash
$ kilo bash "rm -rf /"
❌ BLOCKED: Dangerous operation detected: rm -rf /
[exit 1]
```

### Ask Mode
```bash
$ kilo bash "docker compose up -d agent-zero"
⚠️  PIPELINE BYPASS: 'docker compose up -d' skips COMPOSE_ENV_FILES injection.
    Correct path: make -C pmoves up-agents
Proceed anyway? [y/N]: _
```

### Known Roads Guidance
```bash
$ kilo bash "docker volume rm pmoves_neo4j_data"
⚠️  KNOWN ROADS BYPASS: Use `make -C pmoves volume-reset SERVICE=neo4j`
Proceed anyway? [y/N]: _
```

---

## Troubleshooting

### Parity Check Fails
```bash
# Expected: 0 gaps, 1 blocked item
# If gaps > 0, check which files are missing:
make -C pmoves kilo-parity-check | grep "❌"
```

### Hook Not Triggering (After Platform Support Lands)
```bash
# 1. Verify hook is configured
cat kilo.json | grep -A 3 hooks

# 2. Check hook script exists and is executable
ls -la .kilo/hooks/pre-tool.sh
chmod +x .kilo/hooks/pre-tool.sh

# 3. Test with simple blocking pattern
kilo bash "echo 'rm -rf /'"

# 4. Check security event log
tail ~/.kilo/logs/security-events.log
```

### Pattern Mismatch
```bash
# Compare pattern counts
grep -c "^  - pattern:" .claude/hooks/damage-control/patterns.yaml
grep -c "^  - pattern:" .kilo/hooks/damage-control/patterns.yaml

# Should be: Claude ~121, KiloCode ~92
# Difference is expected (omitted Firebase/Vercel/etc.)
```

---

## References

- **Issue:** #2120
- **Full docs:** `.kilo/hooks/damage-control/README.md`
- **Implementation status:** `.kilo/hooks/IMPLEMENTATION_STATUS.md`
- **Sync notes:** `.kilo/hooks/damage-control/SYNC_NOTES.md`
- **Parity check:** `pmoves/mk/kilo.mk` (lines 54-103)
- **Operator home:** `pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md`

---

**Last Updated:** 2026-07-14  
**Platform Status:** ⏳ Awaiting KiloCode/OpenCode hook API
