# PR #366 Self-Hosted Runner Migration - Learnings

**Date:** 2025-12-27
**PR:** #366 - Self-Hosted Runner Migration
**Review:** CodeRabbit automated review analysis

## Summary

Migrated GitHub Actions workflows from `ubuntu-latest` to self-hosted runners.
This commit addresses CodeRabbit review feedback.

## Fixes Applied

| Category | File | Fix |
|----------|------|-----|
| In-Scope | `.github/workflows/chit-contract.yml` | Added `permissions: contents: read` |
| In-Scope | `.github/workflows/python-tests.yml` | Added `permissions: contents: read` |
| In-Scope | `.github/workflows/webhook-smoke.yml` | Added `permissions: contents: read` |
| Tech Debt | `.gitmodules` | Fixed e2b submodule path |
| Tech Debt | `pmoves/Makefile` | Added `SCRIPTS := scripts` variable |
| Tech Debt | `pmoves/Makefile` | Removed `cd pmoves &&` from test targets |
| Tech Debt | `pmoves/Makefile` | Added `all`, `test` targets and `.DEFAULT_GOAL` |

## Key Learnings

1. **GitHub Actions Permissions:** Always include explicit `permissions:` blocks for least privilege
2. **Git Submodules:** Use `git submodule add` CLI, never edit `.gitmodules` manually
3. **Makefile `make -C`:** Never use `cd` in recipes when using `make -C <dir>`
4. **Makefile Standards:** Include `all`, `test`, `clean` targets and `.DEFAULT_GOAL`
