# PR #366 Self-Hosted Runner Migration - Learnings

**Date:** 2025-12-27
**PR:** #366 - Self-Hosted Runner Migration
**Review:** CodeRabbit automated review analysis

## Summary

Migrated 5 GitHub Actions workflows from `ubuntu-latest` to self-hosted runners (`[self-hosted, vps]` for CPU, `[self-hosted, ai-lab, gpu]` for GPU). This PR review identified 3 in-scope issues (missing permissions) and 4 out-of-diff technical debt items.

---

## In-Scope Fixes (Must Merge)

### 1. GitHub Actions Permissions

**Pattern:** Always include explicit `permissions:` blocks in workflows.

**Fixed Files:**
- `.github/workflows/chit-contract.yml`
- `.github/workflows/python-tests.yml`
- `.github/workflows/webhook-smoke.yml`

**Change:**
```yaml
# After `on:` section, before `jobs:`:
permissions:
  contents: read
```

**Why:** GitHub Actions defaults to `write-all` permissions for backward compatibility. Explicitly declaring `contents: read` follows the principle of least privilege and prevents workflows from accidentally having repository write access.

**Reference:** [GitHub Actions - Default permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token)

---

## Out-of-Diff Fixes (Technical Debt)

### 2. Git Submodule Path Duplication

**File:** `.gitmodules`

**Problem:** Path duplication in e2b submodule:
```ini
[submodule "pmoves/pmoves/vendor/e2b"]    # WRONG
    path = pmoves/pmoves/vendor/e2b        # WRONG
```

**Fixed:**
```ini
[submodule "pmoves/vendor/e2b"]            # CORRECT
    path = pmoves/vendor/e2b                # CORRECT
```

**Why:** When adding submodules manually, it's easy to duplicate path components. The correct approach is to use `git submodule add` CLI which validates paths automatically.

**Lesson:** Never edit `.gitmodules` manually. Use:
```bash
git submodule add <url> <path>
```

---

### 3. Makefile Working Directory Context

**File:** `pmoves/Makefile`

**Problem:** Test-smoke targets used `cd pmoves && pytest ...`
```makefile
test-smoke:
    cd pmoves && pytest tests/smoke/ -v -m smoke
```

**Why it fails:** When invoked via `make -C pmoves`, the working directory is already `pmoves/`. The `cd pmoves` tries to change into `pmoves/pmoves/` which doesn't exist.

**Fixed:**
```makefile
test-smoke:
    pytest tests/smoke/ -v -m smoke
```

**Lesson:** When using `make -C <dir>`, never use `cd <dir>` in recipes. The working directory is already set to `<dir>`.

---

### 4. Makefile Undefined Variables

**File:** `pmoves/Makefile`

**Problem:** `$(SCRIPTS)` variable was used but not defined.

**Fixed:** Added at line 44:
```makefile
PYTHON ?= python3
SCRIPTS := scripts
SINGLE_ENV_MODE ?= 1
```

**Lesson:** Define all Makefile variables before use. Group related variable definitions together near the top of the file.

---

### 5. Makefile Standard Targets

**File:** `pmoves/Makefile`

**Problem:** Missing conventional `all` and `test` targets.

**Fixed:** Added after line 70:
```makefile
# -------- Standard Makefile targets ----------
.PHONY: all
all: help ## Default target - show help

.PHONY: test
test: test-smoke ## Run pytest smoke tests

.DEFAULT_GOAL := help
```

**Lesson:** POSIX Makefiles should include:
- `all` - default target (should show help)
- `test` - alias to project's test suite
- `clean` - remove build artifacts (already existed)
- `.DEFAULT_GOAL` - explicit default behavior

---

## Runner Labels Reference

| Runner Type | Label | Usage |
|-------------|-------|-------|
| CPU (VPS) | `[self-hosted, vps]` | General CI, Python tests, contract checks |
| GPU (AI Lab) | `[self-hosted, ai-lab, gpu]` | ML models, CUDA workloads, TTS |

---

## Pre-Merge Checklist

- [x] All workflows have `permissions: contents: read`
- [x] .gitmodules paths are correct
- [x] Makefile test targets work with `make -C pmoves`
- [x] Makefile has standard targets (all, test, clean)
- [ ] CI passes on self-hosted runners
- [ ] Smoke tests pass locally

---

## Commands for Validation

```bash
# Validate workflow syntax
actionlint .github/workflows/*.yml

# Validate Makefile syntax
make -n -C pmoves test-smoke

# Verify submodule paths
grep "^path=" .gitmodules | sort | uniq -d

# Run pytest smoke tests
cd pmoves && make test-smoke
```

---

## References

- [GitHub Actions Security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [POSIX Makefile Conventions](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/make.html)
- [Git Submodules](https://git-scm.com/docs/git-submodule)
