# PMOVES.AI Submodule Workflow

This document describes the proper workflow for working with PMOVES.AI submodules.

## Branch Strategy

### Branch Flow
```
feature work → PMOVES.AI-Edition-Hardened-v3-clean → PMOVES.AI-Edition-Hardened → main
```

1. **PMOVES.AI-Edition-Hardened-v3-clean** - Staging branch for features
   - All feature work targets this branch first
   - Once verified and stable, merges to PMOVES.AI-Edition-Hardened

2. **PMOVES.AI-Edition-Hardened** - Production-ready hardened branch
   - Only receives merges from v3-clean after verification
   - More conservative, stable deployments

3. **main** - Latest stable release
   - Receives merges from hardened branch after full testing

### Submodule Branch Strategy
- Each submodule fork has a `PMOVES.AI-Edition-Hardened` branch
- Submodules are custom forks for PMOVES.AI integration
- Nested submodules exist (e.g., PMOVES-DoX contains PMOVES-Agent-Zero)

## Submodule Workflow

### Key Principle: Work IN Submodules, Not Worktrees

**DO:**
- Work directly in the submodule directory
- Commit changes to the submodule's hardened branch
- Push to submodule's origin repository
- Then update main repo submodule reference

**DON'T:**
- Create worktrees in main repo for submodule work
- Modify submodule files from main repo worktrees
- Commit submodule changes through main repo

### Correct Workflow Example

```bash
# 1. Work in the submodule
cd PMOVES-Archon
# Make changes...
git add .
git commit -m "feat: add new feature"
git push origin PMOVES.AI-Edition-Hardened
cd ..

# 2. Update main repo reference
git add PMOVES-Archon
git commit -m "chore(submodules): Update PMOVES-Archon reference"
git push origin feature/my-feature
```

### Incorrect Pattern (Avoid This)

```bash
# DON'T DO THIS - Creates worktree for submodule work
git worktree add PMOVES-Archon pmoves-archon-feature
# Work in worktree...
# This breaks submodule workflow!
```

## Directory Structure

### Top-Level PMOVES-* Directories
These are submodules (custom forks):
- `PMOVES-Archon/` - Agent knowledge management
- `PMOVES-Agent-Zero/` - Agent orchestrator
- `PMOVES-BoTZ/` - BoTZ framework
- `PMOVES-Creator/` - Content creation
- `PMOVES-Deep-Serch/` - Deep research orchestrator
- `PMOVES-DoX/` - Document processing
- `PMOVES-HiRAG/` - Hybrid RAG system
- `PMOVES-Jellyfin/` - Media integration
- `PMOVES-Open-Notebook/` - Knowledge base integration
- `PMOVES-Pipecat/` - Voice communication
- `PMOVES-Remote-View/` - Remote viewing
- `PMOVES-Tailscale/` - VPN integration
- `PMOVES-ToKenism-Multi/` - Tokenism framework
- `PMOVES-Wealth/` - Wealth tracking
- `PMOVES.YT/` - YouTube integration
- `PMOVES-A2UI/` - A2UI integration
- `PMOVES-n8n/` - Workflow automation

### Integration Directories
- `pmoves/integrations/archon/` - Archon integration point
- `pmoves/vendor/*` - Vendored dependencies

## Nested Submodules

Some PMOVES submodules contain their own nested submodules:
- **PMOVES-DoX** contains PMOVES-Agent-Zero (hardened variant)
- These nested submodules have `PMOVES.AI-Edition-Hardened` branches

When working with nested submodules:
1. Navigate to the parent submodule first
2. Update nested submodule from within parent
3. Commit parent submodule changes
4. Update main repo reference

## Common Patterns

### Adding a New Submodule
```bash
git submodule add -b PMOVES.AI-Edition-Hardened \
  https://github.com/POWERFULMOVES/PMOVES-NewSubmodule.git \
  PMOVES-NewSubmodule
```

### Updating Submodule References
```bash
# After submodule changes are pushed
git submodule update --remote --recursive
git add PMOVES-Submodule
git commit -m "chore(submodules): Update PMOVES-Submodule reference"
```

### Checking Submodule Status
```bash
git status                    # Show modified submodules
git submodule status          # Detailed submodule status
git diff PMOVES-Submodule     # Show submodule diff
```

## Troubleshooting

### Submodule Shows as "Modified Content"
This means the submodule has uncommitted changes OR is on a different commit than expected.

**Solution:**
```bash
cd PMOVES-Submodule
git status                    # Check what's changed
# Either commit changes or reset to expected commit
git checkout PMOVES.AI-Edition-Hardened
cd ..
```

### Untracked PMOVES-* Directories
If PMOVES-* directories show as untracked but should be submodules:

**Solution:**
```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### Worktree Conflicts
If you accidentally created a worktree for submodule work:

**Solution:**
```bash
git worktree remove incorrect-worktree
git branch -D incorrect-branch
```

## See Also

- `.gitmodules` - Complete submodule configuration
- `.claude/context/submodules.md` - Submodule catalog
- `.claude/context/ci-runners.md` - CI/CD runner configuration
