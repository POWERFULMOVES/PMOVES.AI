# Submodule Review Tasks - 2026-02-07

**Purpose:** Track progress of syncing commits from main to PMOVES.AI-Edition-Hardened

---

## Task Overview

| Task ID | Submodule | Description | Status | Dependencies |
|----------|-----------|-------------|--------|--------------|
| #38 | PMOVES-DoX | Security fix (HIGH PRIORITY) | Pending | None |
| #37 | PMOVES-Archon | 4 commits to sync | Pending | None |
| #39 | PMOVES-Wealth | 6 commits to review | Pending | None |
| #40 | PMOVES-BoTZ | Dependency updates | Pending | None |
| #41 | PMOVES-A2UI | Analyze divergence | Pending | None |
| #42 | PMOVES-Deep-Serch | Analyze divergence | Pending | None |
| #43 | PMOVES-Pipecat | Analyze divergence | Pending | None |
| #44 | PMOVES-n8n | Analyze divergence | Pending | None |
| #45 | PMOVES-Open-Notebook | Analyze divergence | Pending | None |
| #46 | Infrastructure | Create worktrees | Pending | None |

---

## HIGH PRIORITY

### Task #38: PMOVES-DoX Security Fix 🔴

**Commit:** `bdd1f82c`
**Message:** security: Hardened authentication and input validation (fixes #86)
**Type:** Security fix
**Recommendation:** Merge immediately to hardened

**Steps:**
1. Clone/verify the commit
2. Confirm security fix details
3. Create PR: main → PMOVES.AI-Edition-Hardened
4. Merge after CI passes
5. Update parent submodule reference

---

### Task #37: PMOVES-Archon Sync ⚠️

**Commits:** 4 ahead
| Commit | Message | Type |
|--------|---------|------|
| `a27541d` | Claude Code MCP adapter | Feature |
| `951be3e` | CODEOWNERS config | Security |
| `385b81b` | Nested submodule integrations | Feature |
| `0f8184` | Persona service | Feature |

**Steps:**
1. Review each commit for production readiness
2. Test persona service functionality
3. Verify MCP adapter integration
4. Create PR: main → PMOVES.AI-Edition-Hardened
5. Merge after validation

---

### Task #39: PMOVES-Wealth Review ⚠️

**Commits:** 6 ahead
- PMOVES integration features
- Upstream Firefly III syncs
- GPG signing fix

**Steps:**
1. Analyze each commit
2. Identify which are PMOVES-specific vs upstream
3. Determine sync strategy
4. Create PR if needed

---

## MEDIUM PRIORITY

### Task #40: PMOVES-BoTZ Dependency Updates

**Commits:** 4 (all dependabot)
**Type:** Dependency updates

**Steps:**
1. Review changelog for breaking changes
2. Determine if batch merge is safe
3. Create PR or defer for batch update

---

## DIVERGENCE ANALYSIS (Unknown commits)

### Task #41: PMOVES-A2UI
- Clone and compare branches
- Identify commits ahead
- Categorize by type

### Task #42: PMOVES-Deep-Serch
- Clone and compare branches
- Identify commits ahead
- Categorize by type

### Task #43: PMOVES-Pipecat
- Clone and compare branches
- Identify commits ahead
- Categorize by type

### Task #44: PMOVES-n8n
- Clone and compare branches
- Likely dependency updates
- Categorize by type

### Task #45: PMOVES-Open-Notebook
- Clone and compare branches
- Identify commits ahead
- Categorize by type

---

## Worktree Setup

**Location:** `/home/pmoves/submodule-worktrees/`

**Structure:**
```
submodule-worktrees/
├── PMOVES-DoX/
├── PMOVES-Archon/
├── PMOVES-Wealth/
├── PMOVES-A2UI/
├── PMOVES-Deep-Serch/
└── ...
```

**Benefits:**
- Parallel processing without conflicts
- Isolated testing environments
- No main repo disruption
- Easy cleanup

---

## Progress Tracking

| Task | Assigned | In Progress | Completed | Blocked |
|------|----------|-------------|-----------|---------|
| #38 (DoX Security) | | | | |
| #37 (Archon) | | | | |
| #39 (Wealth) | | | | |
| #40 (BoTZ) | | | | |
| #41 (A2UI) | | | | |
| #42 (Deep-Serch) | | | | |
| #43 (Pipecat) | | | | |
| #44 (n8n) | | | | |
| #45 (Open-Notebook) | | | | |
| #46 (Worktrees) | | | | |

---

**Next:** Create worktrees infrastructure and assign agents to begin parallel analysis.
