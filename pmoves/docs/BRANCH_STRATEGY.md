# PMOVES.AI Branch Strategy

**Created:** 2026-02-16
**Status:** Production branch model

---

## Branch Model

```
feature/* ──► PMOVES.AI-Edition-Hardened-Integrations ──► PMOVES.AI-Edition-Hardened ──► main
   │                        │                                     │                      │
   │                   CI gate runs                          Full audit gate         Release tag
   │                   (fast feedback)                       (security + contract)   (production)
   └── TTL: 14 days
```

### Canonical Branches

| Branch | Purpose | Protection | Merge From |
|--------|---------|------------|------------|
| `main` | Production release | Required reviews, CI pass | Hardened only |
| `PMOVES.AI-Edition-Hardened` | Security-hardened staging | Required reviews, audit gate | Integrations only |
| `PMOVES.AI-Edition-Hardened-Integrations` | Feature aggregation & CI | CI must pass | feature/* branches |

### Feature Branch Conventions

| Pattern | Purpose | TTL | Example |
|---------|---------|-----|---------|
| `feature/*` | New functionality | 14 days | `feature/voice-streaming` |
| `fix/*` | Bug fixes | 7 days | `fix/nats-reconnect` |
| `codex/*` | AI-assisted development | 14 days | `codex/archon-hirag-stability` |
| `chore/*` | Maintenance tasks | 7 days | `chore/dependency-update` |
| `docs/*` | Documentation only | 7 days | `docs/api-reference` |

### Branch TTL Policy

- Feature branches older than their TTL are candidates for archival
- Unmerged branches >30 days are force-archived (tagged + deleted)
- Merged branches are deleted after merge confirmation
- Use `make -C pmoves branch-audit` to list stale branches

---

## Submodule Two-Branch Model

Each PMOVES submodule maintains two long-lived branches:

```
submodule feature/* ──► PMOVES.AI-Edition-Hardened ──► main
                              │                          │
                        Submodule production        Upstream sync
```

| Branch | Purpose |
|--------|---------|
| `PMOVES.AI-Edition-Hardened` | PMOVES-customized, security-hardened fork |
| `main` | Tracks upstream (or serves as release branch for PMOVES-native repos) |

### Submodule Update Flow

```bash
# 1. Work in submodule
cd PMOVES-Agent-Zero
git checkout PMOVES.AI-Edition-Hardened
# ... make changes ...
git commit -m "feat: add NATS reconnect"
git push origin PMOVES.AI-Edition-Hardened

# 2. Update parent repo reference
cd ..
git add PMOVES-Agent-Zero
git commit -m "chore(submodules): update Agent Zero reference"

# 3. Bulk update (CI/automation)
make -C pmoves submodule-sync-all
```

---

## Protection Rules

### `main` Branch

- Require pull request before merging
- Require 1 approval
- Require status checks: `CodeQL`, `CHIT Contract`, `SQL Policy Lint`
- Require linear history (no merge commits)
- No force pushes
- No deletions

### `PMOVES.AI-Edition-Hardened` Branch

- Require pull request before merging
- Require status checks: `integration-gate`, `hardening-validation`
- Require up-to-date branches before merging
- No force pushes

### `PMOVES.AI-Edition-Hardened-Integrations` Branch

- Require status checks: `integration-gate`
- Allow direct pushes from automation (CI bots)
- No force pushes

---

## Merge Flow

### Feature to Integration

```bash
# Create PR targeting integrations branch
gh pr create --base PMOVES.AI-Edition-Hardened-Integrations --title "feat: new capability"

# CI runs integration-gate workflow
# On pass, merge via GitHub UI or:
gh pr merge --squash
```

### Integration to Hardened

```bash
# Create promotion PR
make -C pmoves submodule-promote

# Full audit gate runs (security, contracts, hardening)
# Requires review approval
gh pr merge --merge  # preserve history for audit trail
```

### Hardened to Main

```bash
# Release PR
gh pr create --base main --head PMOVES.AI-Edition-Hardened \
  --title "release: v1.x.x hardened"

# All CI gates must pass
# Tag after merge:
git tag -a v1.x.x -m "Release v1.x.x"
git push origin v1.x.x
```

---

## Branch Cleanup

### Automated Cleanup

```bash
# Audit stale branches (dry-run)
make -C pmoves branch-audit

# Clean up merged/stale branches (dry-run by default)
make -C pmoves branch-cleanup

# Execute cleanup (actually delete)
make -C pmoves branch-cleanup EXECUTE=1
```

### Manual Cleanup

```bash
# Archive a branch before deletion
git tag archive/branch-name branch-name
git push origin archive/branch-name
git push origin --delete branch-name
```

---

## Nested Submodule Handling

Some submodules contain nested submodules:

- **PMOVES-DoX** contains nested `PMOVES-Agent-Zero`

### Recursive Update Flow

```bash
# Update recursively
git submodule update --remote --recursive

# Or target a specific nested submodule
cd PMOVES-DoX
git submodule update --remote PMOVES-Agent-Zero
git add PMOVES-Agent-Zero
git commit -m "chore: update nested Agent Zero"
git push origin PMOVES.AI-Edition-Hardened
cd ..
git add PMOVES-DoX
git commit -m "chore(submodules): update DoX (nested Agent Zero)"
```

---

## See Also

- `.claude/context/submodule-workflow.md` - Detailed submodule workflow
- `pmoves/docs/AGENTS/SUBMODULE_AUDIT_REFERENCE.md` - Audit checklist
- `pmoves/tools/branch_cleanup.py` - Branch cleanup tool
- `.github/workflows/integration-gate.yml` - Integration gate CI
