# PR #366 Self-Hosted Runner Migration - Learnings

**Date:** 2025-12-27
**PR:** #366 - Self-Hosted Runner Migration
**Review:** CodeRabbit automated review analysis

## Summary

Migrated 5 GitHub Actions workflows from `ubuntu-latest` to self-hosted runners (`[self-hosted, vps]` for CPU, `[self-hosted, ai-lab, gpu]` for GPU). This PR review identified 3 in-scope issues (missing permissions) and 4 out-of-diff technical debt items.

---

## In-Scope Fixes (Must Merge)

### 1. GitHub Actions Permissions

1. **GitHub Actions Permissions:** Always include explicit `permissions:` blocks for least privilege
2. **Git Submodules:** Use `git submodule add` CLI, never edit `.gitmodules` manually
3. **Makefile `make -C`:** Never use `cd` in recipes when using `make -C <dir>`
4. **Makefile Standards:** Include `all`, `test`, `clean` targets and `.DEFAULT_GOAL`

## Runner Labels Reference

| Runner Type | Label | Usage |
|-------------|-------|-------|
| CPU (VPS) | `[self-hosted, vps]` | General CI, Python tests, contract checks |
| GPU (AI Lab) | `[self-hosted, ai-lab, gpu]` | ML models, CUDA workloads, TTS |

## Pre-Merge Checklist

- [x] All workflows have `permissions: contents: read`
- [x] .gitmodules paths are correct
- [x] Makefile test targets work with `make -C pmoves`
- [x] Makefile has standard targets (all, test, clean)
- [ ] CI passes on self-hosted runners
- [ ] Smoke tests pass locally

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

## References

- [GitHub Actions Security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [POSIX Makefile Conventions](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/make.html)
- [Git Submodules](https://git-scm.com/docs/git-submodule)
