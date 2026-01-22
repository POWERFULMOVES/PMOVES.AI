# Submodule Review Learnings
**Review Date:** 2026-01-15
**Submodules Reviewed:** 39 submodules in PMOVES.AI

---

## Key Finding: PR Data Mismatch

**Issue:** PMOVES-Open-Notebook PRs (#430, #413, #383) listed in initial scan **do not exist** in the repository.

**Learning:** When cross-referencing PR data:
1. Verify the repository owner/name
2. Check if PRs are in a different fork
3. PRs may be closed/draft and not visible in default listing
4. Timestamps in API responses may be cached

---

## Submodule Status Summary

| Tier | Count | Synced | Diverged | Unpushed |
|------|-------|--------|----------|----------|
| Agent | 3 | 1 | 0 | 2 |
| Media | 6 | 5 | 0 | 1 |
| Worker | 3 | 2 | 0 | 1 |
| LLM | 1 | 1 | 0 | 0 |
| Infra | 2 | 2 | 0 | 0 |
| E2B | 5 | 5 | 0 | 0 |

---

## Submodule Branch Patterns

### 1. Expected Branch: `PMOVES.AI-Edition-Hardened
```
PMOVES-Agent-Zero       → PMOVES.AI-Edition-Hardened ✅
PMOVES-YT               → PMOVES.AI-Edition-Hardened ✅
PMOVES-tensorzero       → PMOVES.AI-Edition-Hardened ✅
```

**Pattern:** Most submodules correctly track the hardened branch.

### 2. Detached HEAD Pattern
```
PMOVES-Archon           → HEAD (detached) 🟠
PMOVES-E2B-Danger-Room  → HEAD (detached) 🟠
```

**Learning:** Detached HEAD occurs when:
- Submodule at specific commit for testing
- Submodule being rebased
- Incomplete merge/rebase operation

**Action:** Checkout appropriate branch:
```bash
cd PMOVES-Archon
git checkout PMOVES.AI-Edition-Hardened
```

### 3. Feature Branch Pattern
```
PMOVES-Jellyfin         → fix/hardened-network-architecture 🟡
PMOVES-Open-Notebook    → v1.3.1-40-g4ecf957 🟡
```

**Learning:** Some submodules on feature branches or version tags.
- May indicate pending PR
- May indicate release tag pinned for stability

---

## Submodule Review Commands

### Check All Submodules
```bash
# Quick status
git submodule status

# Detailed status with branches
git submodule foreach 'echo "Path: $path, Branch: $(git branch --show-current || echo detached)"'
```

### Sync Diverged Submodules
```bash
# For each diverged submodule
cd <submodule-path>
git checkout PMOVES.AI-Edition-Hardened
git pull origin PMOVES.AI-Edition-Hardened
```

### Check Submodule PRs
```bash
# For a specific submodule
gh pr list --repo POWERFULMOVES/<submodule-name> --state open

# For all submodules (with names)
git submodule status | awk '{print $2}' | while read sub; do
    echo "=== $sub ==="
    gh pr list --repo "POWERFULMOVES/$sub" --state open 2>/dev/null || echo "No PRs"
done
```

---

## Patterns for Submodule Management

### 1. Branch Alignment Pattern
```bash
# .gitmodules should define expected branch
[submodule "PMOVES-Agent-Zero"]
    path = PMOVES-Agent-Zero
    branch = PMOVES.AI-Edition-Hardened
```

### 2. Submodule Update Pattern
```bash
# Safe update (preserves local work)
git submodule update --remote --merge

# Force update (discards local changes)
git submodule update --remote --checkout
```

### 3. CI/CD Integration Pattern
```yaml
# .github/workflows/submodule-check.yml
- name: Check submodule branches
  run: |
    git submodule foreach '
      if [ "$(git branch --show-current)" != "PMOVES.AI-Edition-Hardened" ]; then
        echo "::warning::$name is on wrong branch"
      fi
    '
```

---

## Action Items

1. **Fix detached HEAD submodules:**
   - PMOVES-Archon
   - PMOVES-E2B-Danger-Room-Deskdesktop

2. **Verify feature branch submodules:**
   - PMOVES-Jellyfin (fix/hardened-network-architecture)
   - PMOVES-Open-Notebook (v1.3.1-40-g4ecf957)

3. **Document submodule branch expectations** in `.gitmodules`

---

## Related Files
- `pmoves/tools/submodule_reviewer.py` - Automated submodule scanning tool
- `.gitmodules` - Submodule configuration
