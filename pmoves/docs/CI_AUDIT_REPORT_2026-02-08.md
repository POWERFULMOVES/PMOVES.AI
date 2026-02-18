> **Superseded by [Production Audit Dashboard](PRODUCTION_AUDIT_DASHBOARD.md)** — This document is retained for historical reference.

# CI/CD Audit Report - PMOVES.AI

**Date:** 2026-02-08
**Auditor:** Claude Code (PR #606 preparation)
**Status:** ⚠️ **ACTION REQUIRED**

---

## Executive Summary

The CI/CD infrastructure has been successfully migrated to self-hosted runners, but there are **critical issues** with GHCR image builds that must be addressed before production deployment.

---

## Self-Hosted Runner Status ✅

| Runner Type | Status | Location | Purpose |
|-------------|--------|----------|---------|
| `vps` | ✅ Online | Internal | General CI/CD |
| `ai-lab` | ✅ Online | Internal | AI/ML workloads |
| `gpu` | ✅ Online | Internal | GPU builds |

**Workflows on self-hosted:** 16/16 (100%)

---

## Workflow Inventory (14 Total)

| Workflow | Runner | Status | Notes |
|----------|--------|--------|-------|
| `build-images.yml` | self-hosted | ✅ | Multi-arch builds |
| `chit-contract.yml` | self-hosted (ai-lab) | ✅ | CHIT schema validation |
| `codeql.yml` | self-hosted (vps) | ✅ | Security analysis |
| `deploy-gateway-agent.yml` | self-hosted (vps) | ✅ | Gateway deployment |
| `env-preflight.yml` | self-hosted (vps) | ✅ | Environment validation |
| `hardening-validation.yml` | self-hosted (vps) | ✅ | Container security |
| `integrations-ghcr.yml` | self-hosted (vps) | ❌ **FAILING** | GHCR builds |
| `python-tests.yml` | self-hosted (vps) | ✅ | Python test suite |
| `self-hosted-builds-hardened.yml` | self-hosted (gpu) | ⚠️ Cancelled | GPU builds (old) |
| `self-hosted-builds.yml` | self-hosted (gpu) | ✅ | GPU builds |
| `sql-policy-lint.yml` | self-hosted (vps) | ✅ | SQL linting |
| `sync-secrets-local.yml` | self-hosted (vps) | ⚠️ Expected to fail | Local-only |
| `webhook-smoke.yml` | self-hosted (vps) | ✅ | Webhook validation |
| `yt-dlp-bump.yml` | self-hosted (vps) | ✅ | Dependency updates |

---

## Critical Issue: GHCR Image Builds ❌

### Problem
- **integrations-ghcr.yml** has been failing consistently (last 5 runs: all failed)
- **No GHCR images found** for `ghcr.io/powerfulmoves/pmoves-*`
- Image manifest inspection returns: `manifest unknown`

### Expected Images (from workflow matrix)
| Image Name | Purpose | Status |
|------------|---------|--------|
| `pmoves-agent-zero` | Agent Zero service | ❌ Not found |
| `pmoves-archon` | Archon service | ❌ Not found |
| `pmoves-archon-ui` | Archon UI | ❌ Not found |
| `pmoves-open-notebook` | Open Notebook | ❌ Not found |
| `pmoves-wger` | Wger fitness | ❌ Not found |
| `pmoves-firefly-iii` | Firefly III | ❌ Not found |
| `pmoves-jellyfin` | Jellyfin | ❌ Not found |
| `pmoves-yt` | YouTube ingestion | ❌ Not found |
| `pmoves-deepresearch` | Deep Research | ❌ Not found |
| `pmoves-supaserch` | SupaSerch | ❌ Not found |

### Root Cause Analysis (Required)
1. **Permissions:** Verify `GH_PAT_PUBLISH` has `packages:write` scope
2. **Registry settings:** Check if GHCR is enabled for the org
3. **Workflow authentication:** Verify `contents: read` and `packages: write` permissions
4. **Build logs:** Access runner logs for specific error messages

### Recommended Actions
1. **Immediate:** Manually trigger `integrations-ghcr.yml` with debug logging
2. **Verify PAT:** Ensure `GH_PAT_PUBLISH` token has correct scopes
3. **Check org settings:** Verify container registry is enabled
4. **Alternative:** Consider Docker Hub as fallback if GHCR cannot be fixed

---

## CodeRabbit Integration ⏳

| Item | Status |
|------|--------|
| App Installation | ✅ Installed |
| PR #606 Review | ⏳ Processing |
| CLI Access | ⚠️ Requires OAuth (not programmatic) |

### Notes
- CodeRabbit bot has posted "review in progress" comment
- CLI requires browser-based OAuth authentication
- Review should complete automatically via GitHub App integration

---

## PR #606 Status

| Item | Status |
|------|--------|
| Merge Conflicts | ✅ Resolved |
| Submodules Synced | ✅ Complete |
| Mergeable | ✅ Yes |
| Merge State | ✅ CLEAN |
| Review Comments | ✅ None (or pending CodeRabbit) |

---

## Checklist Before Production Deployment

- [ ] **Fix GHCR builds** - Critical blocker
- [ ] **Complete CodeRabbit review** - Address any findings
- [ ] **Verify all workflow triggers** - Ensure they fire on correct branches
- [ ] **Test runner connectivity** - Verify all 3 runners are accessible
- [ ] **Check secret permissions** - Ensure all required secrets are set
- [ ] **Validate container hardening** - Run hardening-validation.yml on all images
- [ ] **Document CI access** - Create runbook for CI troubleshooting

---

## Next Steps

1. **HIGH PRIORITY:** Fix GHCR image builds
   - Check PAT scopes in GitHub Settings
   - Review workflow logs on runner
   - Test with manual workflow dispatch

2. **MEDIUM PRIORITY:** Complete CodeRabbit review
   - Wait for automated review to complete
   - Address any critical findings
   - Update learnings catalog

3. **LOW PRIORITY:** CI documentation
   - Create troubleshooting guide
   - Document runner maintenance procedures
   - Add onboarding guide for new workflows

---

**Audit Completed:** 2026-02-08 18:45 UTC
**Next Audit:** After GHCR fix is deployed
