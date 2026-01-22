# Tier Branches Learnings
**Review Date:** 2026-01-15
**Branches:** pr-tiers/{tier-agent,tier-api,tier-data,tier-llm,tier-media,tier-worker}

---

## Key Finding: Branch Duplication Pattern

**Issue:** All 6 tier branches contain **identical content** with the same commit hash (`4490fcde`).

**Learning:** When planning multi-tier architecture:
1. **Differentiate branches early** - Each tier should have unique commits
2. **Use base branch strategy** - Create a `feat/tier-infrastructure` base, then branch individual tiers from it
3. **Document tier differences** - Each tier should have a README explaining its purpose

---

## Current State Analysis

### What Tier Branches Contain
- 6-tier environment architecture implementation
- Tier-specific environment configuration files
- Network segmentation for security
- YAML anchors for tier-based env file loading

### What's Missing
1. **Tier-specific service differentiation** - All tiers have same services
2. **Documentation** - No README explaining tier structure
3. **Remote presence** - Branches not pushed, cannot create PRs
4. **Recent activity** - Last commit was January 2, 2026 (13 days stale)

---

## Anti-Pattern Detected

```bash
# Current: 6 identical branches
feat/tier-agent-services    → 4490fcde
feat/tier-api-services      → 4490fcde
feat/tier-data-services     → 4490fcde
feat/tier-llm-services      → 4490fcde
feat/tier-media-services    → 4490fcde
feat/tier-worker-services   → 4490fcde
```

**Problem:** No actual differentiation between tiers.

---

## Recommended Pattern

### Option 1: Single PR with Tier Configs
```bash
# One feature branch with tier configurations
feat/tier-architecture
  ├── docker-compose.tier-agent.yml
  ├── docker-compose.tier-api.yml
  ├── docker-compose.tier-data.yml
  ├── docker-compose.tier-llm.yml
  ├── docker-compose.tier-media.yml
  └── docker-compose.tier-worker.yml
```

### Option 2: Individual Tier PRs from Common Base
```bash
# Create infrastructure first
feat/tier-infrastructure (PR #1)

# Then branch individual tiers
feat/tier-agent (PR #2) ← based on PR#1
feat/tier-api   (PR #3) ← based on PR#1
# ... etc
```

---

## Action Items

1. **Consolidate or differentiate:**
   - Option A: Create single PR with all tier configs
   - Option B: Add tier-specific service lists to each branch

2. **Add documentation:**
   ```markdown
   # Tier Architecture

   ## Agent Tier
   Services: Agent Zero, Archon, Mesh Agent
   Purpose: Agent orchestration and control plane

   ## API Tier
   Services: PostgREST, Hi-RAG, Presign
   Purpose: API gateway and data access
   ...
   ```

3. **Push branches to remote** before PR creation

---

## Worktree Management Learning

**Finding:** 47 worktrees exist, many stale.

**Pattern:**
- Active PR worktrees: Keep current
- Tier branches: Consolidate or complete
- TAC review worktrees: Archive after review
- `/tmp/*` worktrees: Safe to prune

**Cleanup command:**
```bash
git worktree prune
git worktree list | grep "/tmp/" | awk '{print $1}' | xargs -I {} git worktree remove {}
```
