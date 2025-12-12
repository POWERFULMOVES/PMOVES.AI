# PMOVES.AI Testing Strategy

**Comprehensive testing guidelines for Claude Code development workflows.**

## Testing Levels

### 1. Pre-Commit (Developer)

Run before committing changes:

```bash
# Run affected unit tests
pytest -x --tb=short <changed_files>

# Lint Python code
ruff check --fix .

# Type check (optional but recommended)
mypy <service_dir>
```

### 2. Pre-PR (Validation)

Run before creating or updating a PR:

```bash
# Full verification suite
cd pmoves && make verify-all

# Service-specific tests
pytest pmoves/services/<service>/tests/ -v

# Health checks via slash command
/health:check-all
```

### 3. CI Pipeline (Automated)

These run automatically on every PR:

| Check | Description | Requirement |
|-------|-------------|-------------|
| CodeQL Analysis | Security scanning (Python, JS/TS, C/C++, Actions) | Must pass |
| CHIT Contract Check | Schema validation | Must pass |
| SQL Policy Lint | Migration file validation | Must pass |
| CodeRabbit Review | Code quality + docstring coverage | Coverage ≥80% |

---

## PR Testing Documentation Requirements

Every PR **must** include a Testing section (per `.github/pull_request_template.md`):

### Required Elements

1. **Commands executed** with pass/fail status
2. **Affected services** and their health status
3. **Integration points** validated
4. **Manual testing** performed (if applicable)

### Example Testing Section

```markdown
## Testing

### Commands Executed
- `make verify-all` ✅ All smoke tests passing
- `pytest pmoves/services/channel-monitor/tests/` ✅ 12 tests passed
- `/health:check-all` ✅ All 15 services healthy

### Services Validated
- channel-monitor (8097) ✅
- hi-rag-gateway-v2 (8086) ✅
- pmoves-yt (8077) ✅

### Integration Points
- NATS pub/sub validated via `nats pub test.v1 "test"`
- Supabase connection verified

### Manual Testing
- Tested YouTube channel addition via UI
- Verified webhook fires on new content
```

---

## Test Commands Reference

### Full Stack Testing

| Command | Description | When to Use |
|---------|-------------|-------------|
| `make verify-all` | Comprehensive smoke tests | Before PR submission |
| `make smoke` | Core service smoke tests | Quick validation |
| `make smoke-gpu` | GPU-specific smoke tests | GPU service changes |

### Service-Specific Testing

| Command | Description |
|---------|-------------|
| `pytest pmoves/tests/` | Cross-service integration tests |
| `pytest pmoves/services/<svc>/tests/` | Single service unit tests |
| `make channel-monitor-smoke` | Channel monitor validation |
| `make archon-smoke` | Archon service validation |
| `make discord-smoke` | Discord publisher validation |

### Health & Monitoring

| Command | Description |
|---------|-------------|
| `/health:check-all` | All service health endpoints |
| `/deploy:smoke-test` | Deployment smoke tests |
| `make preflight-retro` | Retro-styled readiness check |
| `make monitoring-report` | Generate monitoring report |

---

## Docstring Coverage

CodeRabbit enforces **≥80% docstring coverage** on Python files.

### Check Coverage

```bash
# Find Python files without docstrings
git diff --name-only HEAD~1 | grep '\.py$' | \
  xargs -I {} sh -c 'grep -L "\"\"\"" "{}" 2>/dev/null && echo "{}"'

# Or use interrogate (if installed)
interrogate -vv pmoves/services/<service>/
```

### Docstring Requirements

- **Modules**: Top-level module docstring
- **Classes**: Class-level docstring describing purpose
- **Public Functions**: Docstring with Args, Returns, Raises sections
- **Private Functions**: Optional but recommended for complex logic

### Example Docstring

```python
def process_transcript(video_id: str, language: str = "en") -> dict:
    """Process a video transcript and extract key information.

    Args:
        video_id: YouTube video ID to process.
        language: Target language for transcript (default: "en").

    Returns:
        Dictionary containing:
            - text: Full transcript text
            - segments: List of timed segments
            - summary: AI-generated summary

    Raises:
        TranscriptNotFoundError: If no transcript available.
        ProcessingError: If transcript processing fails.
    """
```

---

## Testing Workflow

### Before PR Submission

1. **Run `/test:pr`** - Executes standard test suite
2. **Review output** - Ensure all tests pass
3. **Copy Testing section** - Add to PR description
4. **Check docstrings** - Ensure ≥80% coverage

### After PR Creation

1. **Monitor CI** - Wait for all checks to pass
2. **Address CodeRabbit** - Fix any flagged issues
3. **Update Testing section** - If you make changes

### Merge Checklist

- [ ] All CI checks passing
- [ ] CodeRabbit approved or issues addressed
- [ ] Testing section complete
- [ ] Docstring coverage ≥80%

---

## Service Health Endpoints

All PMOVES services expose `/healthz` for health checks:

```bash
# Core Services
curl -f http://localhost:8080/healthz  # Agent Zero
curl -f http://localhost:8091/healthz  # Archon
curl -f http://localhost:8086/healthz  # Hi-RAG v2

# Media Services
curl -f http://localhost:8077/healthz  # PMOVES.YT
curl -f http://localhost:8078/healthz  # FFmpeg-Whisper
curl -f http://localhost:8097/healthz  # Channel Monitor

# Storage Services
curl -f http://localhost:6333/collections  # Qdrant
curl -f http://localhost:7700/health       # Meilisearch
curl -f http://localhost:7474/             # Neo4j
```

---

## Troubleshooting

### Tests Failing Locally but Passing in CI

- Check environment variables are set (`make ensure-env-shared`)
- Verify services are running (`docker compose ps`)
- Check service logs (`docker compose logs <service>`)

### Docstring Coverage Below Threshold

- Run `interrogate -vv <path>` to identify missing docstrings
- Focus on public functions and classes
- Use `@coderabbitai generate docstrings` comment on PR

### Health Checks Failing

- Verify Docker Compose profiles are correct
- Check service dependencies (NATS, Supabase, etc.)
- Review Loki logs at http://localhost:3100

---

## Related Commands

- `/test:pr` - Run PR testing workflow
- `/health:check-all` - Check all service health
- `/deploy:smoke-test` - Run deployment smoke tests
- `/deploy:services` - List running services
