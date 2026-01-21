# PMOVES PR Review Learnings Index
**Last Updated:** 2026-01-15

This directory catalogs learnings from PR reviews to capture patterns and implementation guidance for PMOVES.AI development.

---

## Review Categories

### Security Patterns
- [PR #489 - Security Learnings](./PR-489-learnings.md)
  - Environment variable fallback patterns
  - Credential management anti-patterns
  - AI tool false positive verification

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
| Open PRs | 3 | PR #489 has 2 MAJOR security issues |
| Submodules synced | 16 | 3 need branch fix (detached HEAD) |
| Tier branches | 6 | All identical - need consolidation |
| TAC reviews | 11 | Review completion pending |

---

## Action Items

### High Priority
- [ ] Fix ClickHouse credentials in docker-compose.yml (PR #489)
- [ ] Fix Invidious password pattern in docker-compose.yml (PR #489)
- [ ] Consolidate or differentiate tier branches

### Medium Priority
- [ ] Fix detached HEAD in PMOVES-Archon submodule
- [ ] Fix detached HEAD in PMOVES-E2B-Danger-Room-Deskdesktop
- [ ] Verify PMOVES-Jellyfin feature branch status

### Low Priority
- [ ] Prune /tmp/observability-restore worktree
- [ ] Push tier branches to remote (if keeping separate)
- [ ] Add documentation to tier branches

---

## How to Use This Catalog

1. **Before creating a PR:** Check relevant patterns in this index
2. **During review:** Reference specific anti-patterns to avoid
3. **After merge:** Add new learnings to appropriate category
4. **Periodically:** Run `./tools/review_checklist.sh` to update status
