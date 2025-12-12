Run the standard PR testing workflow and document results for PR submission.

## Usage

Run this command before creating or updating a PR to:
- Validate all tests pass
- Check docstring coverage
- Generate the Testing section for the PR description

## Implementation

Execute these steps in order:

### 1. Run Full Verification Suite

```bash
cd /home/pmoves/PMOVES.AI/pmoves && make verify-all
```

This runs:
- Service bring-up checks
- Preflight validation
- Monitoring report
- Core smoke tests
- GPU smoke tests (if available)
- Service-specific smokes (Archon, Channel Monitor, Discord)

### 2. Run Python Tests (if Python files changed)

```bash
# Check what Python files changed
git diff --name-only origin/main | grep '\.py$'

# Run relevant tests
pytest pmoves/tests/ -v --tb=short

# Or run service-specific tests
pytest pmoves/services/<affected-service>/tests/ -v
```

### 3. Check Docstring Coverage

```bash
# List Python files without docstrings
git diff --name-only origin/main | grep '\.py$' | while read f; do
  if [ -f "$f" ] && ! grep -q '"""' "$f"; then
    echo "Missing docstring: $f"
  fi
done

# Or use interrogate if available
interrogate -vv pmoves/services/<service>/
```

Target: **≥80% docstring coverage** (CodeRabbit requirement)

### 4. Check Service Health

```bash
# Quick health check on core services
for port in 8080 8086 8091 8077 8097; do
  status=$(curl -sf http://localhost:$port/healthz && echo "✅" || echo "❌")
  echo "Port $port: $status"
done
```

### 5. Generate Testing Section

Create this content for the PR description:

```markdown
## Testing

### Commands Executed
- `make verify-all` ✅ All smoke tests passing
- `pytest pmoves/tests/` ✅ [X] tests passed
- Service health checks ✅ All services healthy

### Services Validated
- [List services affected by this PR]
- [Include port and health status]

### Integration Points
- [List any NATS subjects, APIs, or databases touched]

### Manual Testing
- [Describe any manual validation performed]
```

### 6. Report Summary

After completing all steps, provide:

| Check | Status |
|-------|--------|
| make verify-all | ✅/❌ |
| pytest | ✅/❌ (N tests) |
| Docstring coverage | ✅/❌ (X%) |
| Service health | ✅/❌ |
| **Ready for PR** | **Yes/No** |

## Quick Reference

### Minimum Required Tests

For documentation-only PRs:
- `make verify-all` or `/health:check-all`

For code changes:
- `make verify-all`
- `pytest` on affected services
- Docstring coverage check

For database migrations:
- All of the above
- SQL lint check (automated in CI)

### Common Issues

**make verify-all fails on GPU tests:**
```bash
# Skip GPU tests if no GPU available
make smoke  # Core tests only
```

**Docstring coverage below 80%:**
```bash
# Add docstrings to flagged files, or
# Comment on PR: @coderabbitai generate docstrings
```

**Services not running:**
```bash
# Start required services
docker compose --profile agents --profile workers up -d
```

## Notes

- Always run from repository root (`/home/pmoves/PMOVES.AI`)
- GPU tests are optional in non-GPU environments
- Copy the generated Testing section to your PR description
- See `.claude/context/testing-strategy.md` for detailed guidelines
