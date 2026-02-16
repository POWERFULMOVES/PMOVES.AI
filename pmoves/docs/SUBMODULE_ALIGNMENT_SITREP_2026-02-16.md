# Submodule Alignment SITREP
_Generated: 2026-02-16 03:00:49Z_

## Summary
- Declared submodules in `.gitmodules`: **49**
- Uninitialized submodules (`git submodule status` prefix `-`): **0**
- Drifted submodules (`+`): **0**
- Conflict submodules (`U`): **0**
- Recursive status exit code: **128**

## Critical Blockers
- Recursive traversal currently fails: **True**
- Recursive error:
  - `fatal: no submodule mapping found in .gitmodules for path 'PMOVES-E2B-Danger-Room-Deskdesktop'
fatal: failed to recurse into submodule 'PMOVES-A2UI'`

## Duplicate URL Groups (Canonical-vs-Alias Paths)
- `https://github.com/POWERFULMOVES/PMOVES-A2UI.git`
  - `PMOVES-A2UI` (branch `PMOVES.AI-Edition-Hardened`)
  - `research/A2UI` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-AgentGym.git`
  - `PMOVES-AgentGym` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/agentgym` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-Archon.git`
  - `PMOVES-Archon` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/integrations/archon` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-Danger-infra.git`
  - `PMOVES-Danger-infra` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/e2b-infra` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-E2B-Danger-Room-Desktop.git`
  - `PMOVES-E2B-Danger-Room-Desktop` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/e2b-desktop` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-E2b-Spells.git`
  - `PMOVES-E2b-Spells` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/e2b-spells` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/PMOVES-surf.git`
  - `PMOVES-surf` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves-surf` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/e2b-surf` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/Pmoves-AgentGym-RL.git`
  - `Pmoves-AgentGym-RL` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/agentgym-rl` (branch `PMOVES.AI-Edition-Hardened`)
- `https://github.com/POWERFULMOVES/pmoves-e2b-mcp-server.git`
  - `pmoves-e2b-mcp-server` (branch `PMOVES.AI-Edition-Hardened`)
  - `pmoves/vendor/e2b-mcp-server` (branch `PMOVES.AI-Edition-Hardened`)

## Initialization State
### Uninitialized
- _none_

### Drifted
- _none_

### Conflicts
- _none_

## Dirty Worktrees (Local Changes)
- `PMOVES-Archon` (1 changed entries)
- `PMOVES-HiRAG` (1 changed entries)

## Legacy Name Hits (Action Required)
- _none_

## Alias/Compatibility Path Hits (Review Required)
- _none_

## Documentation Legacy Hits (Archive/Update)
- `PMOVES-E2B-Danger-Room-Deskdesktop`
  - `.claude/learnings/pr-reviews/INDEX.md`
  - `.claude/learnings/pr-reviews/submodule-review-learnings.md`
  - `pmoves/docs/AGENTS/WORKTREE_SUBMODULE_AUDIT_SITREP_2026-02-16.md`
  - `pmoves/docs/E2B_INTEGRATION.md`
- `PMOVES-Firefly-iii`
  - `.claude/context/submodules.md`
  - `.claude/learnings/session7-stargate-plan-2025-12.md`
  - `docs/PMOVES.AI-Edition-Hardened-Summary.md`
  - `docs/SUBMODULES-ARE-CORE.md`
  - `pmoves/docs/NEXT_STEPS.md`
  - `pmoves/docs/SUBMODULE_AUDIT_2026-02-07.md`
  - `pmoves/docs/SUBMODULE_HARDENED_ALIGNMENT_2026-02-07.md`
- `pmoves/pmoves/vendor/e2b`
  - `pmoves/docs/E2B_INTEGRATION.md`
  - `pmoves/docs/services/e2b/README.md`

## Production Decision Guidance
1. Keep compatibility path mappings active in `.gitmodules` until all legacy gitlinks are removed from index and no runtime file depends on alias paths.
2. Keep recursive submodule checks enabled and treat any new unmapped nested gitlink as a release blocker.
3. Split cleanup into targeted PR waves:
   - Wave A: metadata integrity + deterministic submodule checks.
   - Wave B: canonical path migration (alias removal with scripted updates).
   - Wave C: docs/context regeneration and archived legacy references.
4. For production branch protection, gate on non-recursive integrity plus recursive metadata integrity; allow optional uninitialized submodules only where explicitly documented.
