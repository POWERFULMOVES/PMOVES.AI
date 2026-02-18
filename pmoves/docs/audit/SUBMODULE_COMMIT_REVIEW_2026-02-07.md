# Submodule Commit Review: main vs PMOVES.AI-Edition-Hardened

**Date:** February 7, 2026
**Purpose:** Review commits on main branch not yet in hardened branch

---

## Summary Table

| Submodule | Commits Ahead | Assessment | Recommendation |
|-----------|---------------|-------------|----------------|
| PMOVES-Agent-Zero | 0 | ✅ Aligned | None |
| PMOVES-Archon | 4 | ⚠️ Review | **Merge recommended** |
| PMOVES-DoX | 1 | ❌ Removes auth | **DO NOT MERGE** |
| PMOVES-BoTZ | 4 | ℹ️ Deps only | Optional |
| PMOVES-tensorzero | 0 | ✅ Aligned | None |
| PMOVES-HiRAG | 0 | ✅ Aligned | None |
| PMOVES-Tailscale | 0 | ✅ Aligned | None |
| PMOVES-Wealth | 6 | ✅ Upstream sync | No action needed |
| PMOVES-A2UI | Diverges | ⚠️ Unknown | Check manually |
| PMOVES-Deep-Serch | Diverges | ⚠️ Unknown | Check manually |
| PMOVES-Pipecat | Diverges | ⚠️ Unknown | Check manually |
| PMOVES-n8n | Diverges | ℹ️ Deps | Optional |
| PMOVES-Open-Notebook | Diverges | ⚠️ Unknown | Check manually |

---

## Detailed Review

### ✅ PMOVES-Agent-Zero
**Status:** Aligned (hardened = main)
**Recommendation:** None

---

### ⚠️ PMOVES-Archon (4 commits ahead)

| Commit | Message | Type | Recommendation |
|--------|---------|------|----------------|
| `a27541d` | feat(pmoves): add Claude Code MCP adapter for PMOVES.AI integration | Feature | **MERGE** - Integration improvement |
| `951be3e` | chore(security): add CODEOWNERS configuration | Security | **MERGE** - Security hardening |
| `385b81b` | feat(hardened): Add nested submodule integrations for standalone operation | Feature | **MERGE** - Improves standalone operation |
| `0f8184` | feat(archon): add persona service and API routes for agent creation | Feature | **MERGE** - New persona feature |

**Assessment:** All commits are production-ready. Recommend merging to hardened.

---

### ❌ PMOVES-DoX (1 commit ahead on main)

| Commit | Message | Type | Recommendation |
|--------|---------|------|----------------|
| `bdd1f82` | security: Hardened authentication and input validation (fixes #86) | ⚠️ **MISLEADING** | **DO NOT MERGE** |

**Assessment:** This commit is MISLEADING. Despite its title and description claiming "security hardening," it actually **REMOVES** authentication protections:

**What the commit does:**
- Removes `get_current_user` dependency from all protected endpoints
- Removes JWT authentication from `/search/rebuild`, `/facts`, `/analysis/financials`, `/evidence`, `/ask_question`
- Deletes JWT authentication documentation from SECURITY.md
- Changes `ENVIRONMENT` default from `production` to `development` (less secure)
- Removes startup security guards for production

**Current hardened branch status:**
- Has proper JWT authentication with security defaults
- Protected endpoints require authentication
- Production safeguards in place

**Recommendation:** **DO NOT MERGE**. The hardened branch already has proper security. The `main` branch commit removes security features. This appears to be a development/experimental branch that should NOT go to production.

---

### ℹ️ PMOVES-BoTZ (4 commits ahead)

| Commit | Message | Type | Recommendation |
|--------|---------|------|----------------|
| `7acb272` | feat(observability): Add /healthz, /metrics endpoints | Feature | Optional - nice to have |
| `12a1ccc` | chore(deps): bump the pip group | Deps | Optional - can wait |
| `ed47b76` | chore(deps): bump the uv group | Deps | Optional - can wait |
| `6c9cae` | chore(deps): bump the npm_and_yarn group | Deps | Optional - can wait |

**Assessment:** All dependency updates. Can be batched for later sync.

---

### ✅ PMOVES-Wealth (Review Complete)

**Analysis:** Main branch has 6 commits ahead, but they are primarily upstream Firefly III syncs:
- Most commits merge upstream `firefly-iii:main`
- Commit `234d2bb` explicitly states "Rebase PMOVES.AI-Edition-Hardened onto latest upstream main"
- The hardened branch already has PMOVES-specific changes via PR #17 (merged Jan 27)

**Assessment:** No action needed. The hardened branch is properly configured with PMOVES-specific integrations. The main branch is for upstream sync tracking only.

---

## Recommendations by Priority

### 🔴 HIGH PRIORITY (Merge to Hardened)

1. **PMOVES-Archon** - 4 commits including:
   - CODEOWNERS (security)
   - Claude Code MCP adapter (integration)
   - Nested submodule integrations (standalone operation)
   - Persona service (feature)
2. **PMOVES-Wealth** - GPG signing fix (CI improvement)

### ❌ DO NOT MERGE (Security Regression)

1. **PMOVES-DoX** (`bdd1f82`) - **REMOVES authentication** despite "security" title
   - This commit removes JWT protections from endpoints
   - Hardened branch already has proper security
   - Main branch appears to be development/experimental

### 🟡 MEDIUM PRIORITY (Review & Consider)

1. **PMOVES-BoTZ** - Dependency updates (can be batched)
2. **PMOVES-ToKenism-Multi** - Need to verify HEAD commit
3. **PMOVES-n8n** - Dependency updates

### 🟢 LOW PRIORITY (Can Wait)

1. **PMOVES-A2UI** - Unknown commits, check manually
2. **PMOVES-Deep-Serch** - Unknown commits, check manually
3. **PMOVES-Pipecat** - Unknown commits, check manually
4. **PMOVES-Open-Notebook** - Unknown commits, check manually

---

## Action Items

### Immediate (Today)

1. **PMOVES-Archon**: Create PR to merge 4 commits to hardened
2. ~~**PMOVES-DoX**: Create PR to merge `bdd1f82` (security fix) to hardened~~ → **DO NOT MERGE** (removes authentication)

### This Week

3. Review remaining diverged submodules
4. Create batch PR for dependency updates

### Questions for Review

- Should PMOVES-Wealth upstream Firefly III syncs go to hardened?
- Are there any breaking changes in the commits ahead?
- Do we need to run full CI before syncing?

---

**Next Steps:**
1. Review this document
2. Approve high-priority merges
3. Create PRs main → PMOVES.AI-Edition-Hardened
4. Update submodules in parent PMOVES.AI after merge
