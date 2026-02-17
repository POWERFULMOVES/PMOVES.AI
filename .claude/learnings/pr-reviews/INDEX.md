# PMOVES PR Review Learnings Index
**Last Updated:** 2026-02-16

This directory catalogs learnings from PR reviews to capture patterns and implementation guidance for PMOVES.AI development.

---

## Review Categories

### Security Patterns
- [PR #489 - Security Learnings](./PR-489-learnings.md)
  - Environment variable fallback patterns
  - Credential management anti-patterns
  - AI tool false positive verification
- [Branch Consolidation & Security Audit (Feb 2026)](./branch-consolidation-learnings-2026-02.md)
  - DoX branch reset pattern (386-commit divergence)
  - Dependency-ordered PR merging
  - CodeQL fix patterns, XSS via img.src
  - transcribe-and-fetch security remediation patterns

### Architecture Patterns
- [Tier Branches Learnings](./tier-branches-learnings.md)
  - Multi-tier branch strategy
  - Worktree consolidation patterns
  - Documentation requirements

### Submodule Management
- [Submodule Review Learnings](./submodule-review-learnings.md)
  - Branch alignment patterns
  - Detached HEAD resolution
  - CI/CD integration

---

## Key Patterns to Adopt

### 1. Environment Variable Pattern
```yaml
# Non-sensitive (with default)
VAR_NAME=${VAR_NAME:-default_value}

# Sensitive (no default, forces explicit config)
VAR_NAME=${VAR_NAME:?VAR_NAME not set}
```

### 2. Defensive File Access Pattern
```python
# Always check existence before access
if not path.exists():
    raise RuntimeError(f"Required path not found: {path}")
```

### 3. Submodule Branch Pattern
```bash
# Always verify submodule branch alignment
git submodule foreach 'echo "$name: $(git branch --show-current)"'
```

### 4. Vulnerability Verification Pattern
```bash
# When AI flags a security issue:
1. Check current version vs CVE fix version
2. Run pip-audit or npm audit
3. Check GitHub Security Advisory directly
4. Verify transitive dependencies
```

---

## Tools Created

| Tool | Purpose | Location |
|------|---------|----------|
| `pr_monitor.py` | Track PR comments including out-of-diff | `pmoves/tools/` |
| `submodule_reviewer.py` | Scan 39 submodules for branch status | `pmoves/tools/` |
| `worktree_tracker.py` | Categorize 47 worktrees | `pmoves/tools/` |
| `review_checklist.sh` | Generate review checklist | `pmoves/tools/` |

---

## Current Status Summary

| Category | Count | Action Required |
|----------|-------|-----------------|
| PRs merged (Feb batch) | 5 | #640, #641, #643, #645, #646 |
| PRs fixed, CI re-running | 4 | #633, #634, #642, #644 |
| Submodules synced | 16+ | Agent Zero DoX branch reset (PR #5) |
| Security audits | 1 | transcribe-and-fetch: 3 CRITICAL, 6 HIGH |
| Tier branches | Consolidated | Merged to PMOVES.AI-Edition-Hardened |

---

## Action Items

### High Priority
- [x] Fix ClickHouse credentials in docker-compose.yml (PR #489) — resolved
- [x] Fix Invidious password pattern in docker-compose.yml (PR #489) — resolved
- [x] Consolidate or differentiate tier branches — consolidated to Hardened
- [ ] Rotate Supabase JWT for transcribe-and-fetch (manual, dashboard)
- [ ] Rotate Langfuse/MinIO keys for transcribe-and-fetch (manual)
- [ ] Run `git filter-repo` on transcribe-and-fetch monitoring/*.env (destructive, needs approval)

### Medium Priority
- [ ] Complete CI green on PRs #633, #634, #642, #644
- [ ] transcribe-and-fetch: scrub supabase-agent example config (blocked by damage-control hook)
- [ ] Verify Agent Zero PR #5 merges cleanly

### Low Priority
- [ ] Prune stale worktrees
- [ ] Add Codex quickstart to all `high` priority submodules

---

## How to Use This Catalog

1. **Before creating a PR:** Check relevant patterns in this index
2. **During review:** Reference specific anti-patterns to avoid
3. **After merge:** Add new learnings to appropriate category
4. **Periodically:** Run `./tools/review_checklist.sh` to update status
