# Submodule Sync Progress - 2026-02-07

**Purpose:** Track progress of syncing commits from main to PMOVES.AI-Edition-Hardened

---

## Completed

| Task ID | Submodule | Description | Status | PR |
|----------|-----------|-------------|--------|-----|
| #37 | PMOVES-Archon | 4 commits to sync | ✅ **MERGED** | #7 |
| #38 | PMOVES-DoX | Security fix analysis | ✅ Complete | N/A (DO NOT MERGE) |
| #39 | PMOVES-Wealth | 6 commits reviewed | ✅ Complete | N/A (upstream sync) |
| #46 | Infrastructure | Create worktrees | ✅ Complete | N/A |
| #47 | CodeRabbit Review | Address PR #7 comments | ✅ Complete | #7 |
| #48 | PMOVES-A2UI | Analyze upstream commits | ✅ Complete | N/A (keep hardened) |
| #51 | PMOVES-Open-Notebook | Analyze divergence | ✅ Complete | N/A (hardened ahead) |
| #49 | PMOVES-Pipecat | Cherry-pick PMOVES.AI integration | ✅ Complete | `9be1ee29` |

---

## PMOVES-Pipecat Analysis Result

**Commit:** `a74aa0cc` on origin/main (ahead of hardened)

**Finding:** Adds PMOVES.AI integration patterns to Pipecat

Includes:
- `pmoves_announcer` - NATS announcer for service discovery
- `pmoves_common` - shared types (ServiceTier, HealthStatus)
- `pmoves_health` - health check decorators
- `pmoves_registry` - service registry
- `.coderabbit.yaml` - PR review configuration
- `docker-compose.pmoves.yml` - PMOVES deployment config
- `chit/secrets_manifest_v2.yaml` - CHIT secrets
- `env.tier-media` - media tier environment
- `envared` - environment helper script

**Action:** Cherry-picked to PMOVES.AI-Edition-Hardened

**Status:** ✅ Merged as commit `9be1ee29`

**Parent commit:** `09519a74` - submodule reference updated

---

## PMOVES-n8n Analysis Result

**Commit:** `651e58b` on origin/main (ahead of hardened)

**Finding:** Adds PMOVES.AI integration patterns to n8n

Includes:
- `pmoves_announcer` - NATS announcer for service discovery
- `pmoves_common` - shared types (ServiceTier, HealthStatus)
- `pmoves_health` - health check decorators
- `pmoves_registry` - service registry
- `.coderabbit.yaml` - PR review configuration
- `docker-compose.pmoves.yml` - PMOVES deployment config
- `chit/secrets_manifest_v2.yaml` - CHIT secrets
- `env.shared` - shared environment configuration
- `env.tier-worker` - worker tier environment

**Security Fix:** Removes hardcoded credential defaults:
- Neo4j: removed `neo4j:neo4j` default
- MinIO: removed `minioadmin:minioadmin` default
- ClickHouse: removed `tensorzero:tensorzero` default

**Action:** Cherry-picked to PMOVES.AI-Edition-Hardened

**Status:** ✅ Merged as commit `06653c8`

**Parent commit:** `7feb05c9` - submodule reference updated

---

## PMOVES-BoTZ Analysis Result

**Finding:** PMOVES.AI-Edition-Hardened is **AHEAD** of origin/main by 10 commits

Hardened includes (not on main):
- `2b00d40` - fix: Use preauthkeys endpoint for device enrollment and fix datetime deprecation
- `9fa25c9` - feat: Add VPN MCP server for Headscale and RustDesk integration
- `8461b77` - feat(observability): Add integration health checks
- `06af743` - fix(integration): Standardize TensorZero port to :3030
- `fb97c0b` - fix(code-quality): Address CodeRabbit PR #47 review comments
- `6f05504` - feat(observability): Add /healthz, /metrics endpoints and USER directives
- `e530b8f` - fix(security): escape pipe chars in regex patterns

**Note:** The only commit on main (`c600224`) is a duplicate of `6f05504` which already exists in hardened with additional CodeRabbit review fixes.

**Action:** No merge needed - Hardened branch is correct and ahead

**Status:** ✅ Already on hardened branch

---

## PMOVES-A2UI Analysis Result

**Finding:** Upstream library (ava-cassiopeia/A2UI)

- Hardened branch has PMOVES security fix (non-root USER in Dockerfiles)
- Main has 9 upstream commits but would lose security fix

**Action:** Keep hardened branch - security fix takes priority

**Status:** ✅ Already on hardened branch

---

## PMOVES-Open-Notebook Analysis Result

**Finding:** PMOVES.AI-Edition-Hardened is **AHEAD** of origin/main

- Hardened is the default branch (origin/HEAD)
- Contains: non-root USER security fix, API file_path initialization, PMOVES.AI integration
- origin/main has only 2 CI commits (GitHub App auth) already superseded

**Action:** No merge needed - hardened branch is correct and ahead

**Status:** ✅ Already on hardened branch

---

## Summary: PMOVES-Archon PR #7

**Merged:** 2026-02-07T22:35:41Z

**Commits synced:**
1. `a27541d` - feat(pmoves): add Claude Code MCP adapter for PMOVES.AI integration
2. `951be3e` - chore(security): add CODEOWNERS configuration
3. `385b81b` - feat(hardened): Add nested submodule integrations for standalone operation
4. `0f81842` - feat(archon): add persona service and API routes for agent creation

**Changes:** 94 files changed, 38,742 insertions(+), 4,004 deletions(-)

**Key Features Added:**
- Claude Code MCP adapter for TAC command execution
- CODEOWNERS for PR review routing
- 7 nested submodules (Agent-Zero, BoTZ, HiRAG, Deep-Serch, docling, BotZ-gateway, tensorzero)
- Persona service (457 lines) + API routes (369 lines)
- Behavior weights validation (0.0-1.0 range)
- Proper 404/500 error handling
- Agent Zero response validation

---

## PMOVES-DoX Analysis Result

**Commit:** `bdd1f82c` on main branch

**Finding:** This commit **REMOVES** JWT authentication despite "security" in title.

**Action:** **DO NOT MERGE** - The hardened branch already has proper security.

**Status:** ✅ Hardened branch is correct

---

## PMOVES-Wealth Analysis Result

**Commits:** 6 ahead on main

**Finding:** All commits are upstream Firefly III syncs.

**Action:** No merge needed - hardened branch is correct.

**Status:** ✅ Already on hardened branch

---

## Next Submodules to Review

| Priority | Submodule | Commits Ahead | Type |
|----------|-----------|---------------|------|
| HIGH | PMOVES-A2UI | TBD | Unknown |
| HIGH | PMOVES-Deep-Serch | TBD | Unknown |
| HIGH | PMOVES-Pipecat | TBD | Unknown |
| MEDIUM | PMOVES-n8n | TBD | Dependency updates |
| MEDIUM | PMOVES-Open-Notebook | TBD | Unknown |

---

## Worktrees Status

**Location:** `/home/pmoves/submodule-worktrees/`

**Available for analysis:**
- PMOVES-A2UI
- PMOVES-Deep-Serch
- PMOVES-Pipecat
- PMOVES-n8n
- PMOVES-Open-Notebook

---

**Next Steps:**
1. Update parent submodule reference for PMOVES-Archon
2. Analyze PMOVES-A2UI (HIGH PRIORITY)
3. Analyze PMOVES-Deep-Serch (HIGH PRIORITY)
