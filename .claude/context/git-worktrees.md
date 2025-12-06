# Git Worktrees for Parallel Claude Code CLI Development

**Git worktrees** enable multiple Claude Code CLI instances to work on different features simultaneously without conflicts. This is a key TAC (Tactical Agentic Coding) pattern from IndyDevDan for scaling development.

## Purpose

Traditional git workflow: one working directory per repository
- Switching branches disrupts ongoing work
- Can't have multiple features in-progress simultaneously
- Manual stashing/branching overhead

**Git worktrees** solution:
- Multiple working directories from single `.git` repository
- Each worktree has its own branch
- Independent file state (no conflicts)
- Separate Claude Code CLI sessions per worktree
- Parallel development without interference

## Use Cases for PMOVES

### Parallel Feature Development

Work on multiple PMOVES features simultaneously:

**Main directory:** Refactoring Hi-RAG v2
**Worktree 1:** Adding TensorZero metrics dashboard
**Worktree 2:** Implementing new NATS event subjects
**Worktree 3:** Bug fix in Agent Zero MCP API

Each has independent:
- File state
- Docker compose environments (different ports)
- Claude Code CLI context
- Git branch

### Testing Different Approaches

Try alternative implementations in parallel:

**Main:** Current Hi-RAG architecture
**Worktree A:** Experiment with different reranking model
**Worktree B:** Test alternative CHIT geometry approach

Compare results, merge winner, discard others.

### Long-Running Features

Keep main branch clean while developing large features:

**Main:** Stable PMOVES.AI for daily operations
**Worktree:** Multi-week feature development

Pull updates from main without disrupting feature work.

## Basic Workflow

### Create a Worktree

```bash
# From PMOVES.AI repository root
git worktree add ../pmoves-feature-name feature/name

# Creates:
# - New directory: ../pmoves-feature-name
# - New branch: feature/name (or uses existing)
# - Isolated working tree
```

**Example:**
```bash
git worktree add ../pmoves-tensorzero-dashboard feature/tensorzero-dashboard
cd ../pmoves-tensorzero-dashboard
# Now in separate working directory with feature/tensorzero-dashboard branch
```

### Start Claude Code CLI in Worktree

```bash
cd ../pmoves-tensorzero-dashboard
claude

# Claude Code CLI reads .claude/ directory from this worktree
# Has full PMOVES context (CLAUDE.md, commands, etc.)
# Works independently from main repository
```

### Work Normally

```bash
# Make changes
# Run tests
# Commit to feature branch

git add .
git commit -m "feat: add TensorZero metrics dashboard"

# Push feature branch
git push origin feature/tensorzero-dashboard
```

### List Worktrees

```bash
git worktree list

# Output:
# /home/pmoves/PMOVES.AI        b15b048 [PMOVES.AI-Edition-Hardened]
# /home/pmoves/pmoves-tz-dash   a1b2c3d [feature/tensorzero-dashboard]
```

### Remove Worktree

```bash
# When feature is complete and merged
git worktree remove ../pmoves-tensorzero-dashboard

# Or manually
rm -rf ../pmoves-tensorzero-dashboard
git worktree prune
```

## Advanced Patterns

### Worktree with Different Services Running

Each worktree can run different docker compose profiles:

**Main repository:**
```bash
cd /home/pmoves/PMOVES.AI/pmoves
docker compose up -d  # Ports 8080-8099
```

**Worktree 1:**
```bash
cd /home/pmoves/pmoves-feature-hirag/pmoves
# Override ports to avoid conflicts
HIRAG_V2_HOST_PORT=9086 docker compose up hi-rag-v2
```

**Worktree 2:**
```bash
cd /home/pmoves/pmoves-feature-agents/pmoves
AGENT_ZERO_PORT=9080 docker compose --profile agents up
```

### Shared .git Database

All worktrees share the same `.git` database:

**Benefits:**
- Instant branch creation (no re-cloning)
- Shared git history
- Minimal disk space (only working files duplicated)

**Implications:**
- `git fetch` in one worktree updates all
- `.git/config` shared across worktrees
- Careful with `git clean -fdx` (affects worktrees)

### Per-Worktree Configuration

Each worktree can have independent:

**`.env` files:**
```bash
# Main: .env with production-like config
# Worktree 1: .env with debug logging enabled
# Worktree 2: .env with different model providers
```

**Docker compose overrides:**
```bash
# Main: docker-compose.yml
# Worktree: docker-compose.override.yml with port changes
```

**Claude Code CLI config:**
```bash
# Each worktree has same .claude/ but different running services
```

## PMOVES-Specific Patterns

### Submodule Coordination

PMOVES uses git submodules (Agent Zero, Archon, etc.):

```bash
# Worktree inherits submodule state from main repo
cd ../pmoves-feature-agents

# Update submodule in worktree
git submodule update --init --recursive

# Changes to submodules are visible across worktrees
# (submodules share .git database)
```

### Branch Strategy

**Main branch patterns:**
```bash
# Feature branches for worktrees
git worktree add ../pmoves-feat-X feature/X

# Hotfix branches
git worktree add ../pmoves-hotfix-bug hotfix/critical-bug

# Release branches
git worktree add ../pmoves-release-v1.2 release/v1.2
```

### Monorepo Structure

PMOVES monorepo with worktrees:

```
/home/pmoves/
├── PMOVES.AI/                      # Main repository
│   ├── .git/                       # Shared git database
│   ├── .claude/                    # Shared Claude context
│   └── pmoves/                     # Services
│
├── pmoves-feature-hirag/           # Worktree 1
│   ├── .git → ../PMOVES.AI/.git   # Symlink to main .git
│   ├── .claude/                    # Same context
│   └── pmoves/                     # Independent file state
│
└── pmoves-feature-agents/          # Worktree 2
    ├── .git → ../PMOVES.AI/.git
    ├── .claude/
    └── pmoves/
```

## Collaboration Patterns

### Parallel Review with Multiple Claudes

**Scenario:** Large PR needs review

```bash
# Developer: Main work
cd /home/pmoves/PMOVES.AI
claude  # Claude reviewing architecture

# Separate terminal: Detailed code review
git worktree add ../pmoves-pr-review pr/feature-branch
cd ../pmoves-pr-review
claude  # Second Claude instance reviewing specific files
```

Each Claude instance:
- Independent context
- Can run tests without interfering
- Different focus areas

### A/B Testing Implementations

```bash
# Approach A
git worktree add ../pmoves-approach-a feature/approach-a
cd ../pmoves-approach-a
# Implement approach A, run benchmarks

# Approach B
git worktree add ../pmoves-approach-b feature/approach-b
cd ../pmoves-approach-b
# Implement approach B, run benchmarks

# Compare results, merge winner
```

## Best Practices

### Naming Convention

```bash
# Feature development
git worktree add ../pmoves-feature-{name} feature/{name}

# Bug fixes
git worktree add ../pmoves-fix-{issue} fix/{issue-number}

# Experiments
git worktree add ../pmoves-exp-{idea} experiment/{idea}
```

### Cleanup Regularly

```bash
# List all worktrees
git worktree list

# Remove completed features
git worktree remove ../pmoves-feature-done

# Prune stale worktrees
git worktree prune
```

### Avoid Conflicts

**Don't:**
- Check out same branch in multiple worktrees
- Run same service on same ports
- Modify `.git` directly from worktrees

**Do:**
- Use unique branches per worktree
- Override ports in worktree-specific configs
- Use `git worktree` commands for management

### Share Common Files

Files that should be consistent across worktrees:

- `.claude/` directory (Claude context)
- `pmoves/env.shared.example`
- Documentation
- CI/CD configs

Changes propagate automatically (shared .git database).

## Troubleshooting

### Worktree Locked

```
error: 'remove' cannot be used with worktree locked
```

**Solution:**
```bash
git worktree unlock ../pmoves-feature-name
git worktree remove ../pmoves-feature-name
```

### Port Conflicts

**Problem:** Services in different worktrees compete for ports

**Solution:** Override ports per worktree
```bash
# Worktree 1
export HIRAG_V2_HOST_PORT=9086

# Worktree 2
export HIRAG_V2_HOST_PORT=10086
```

### Submodule Issues

**Problem:** Submodule state inconsistent

**Solution:** Update in each worktree
```bash
cd ../pmoves-feature-X
git submodule update --init --recursive
```

### Disk Space

**Problem:** Multiple worktrees consume disk space

**Reality:** Only working files duplicated, `.git` shared
- Main repo: 5 GB
- Each worktree: +2 GB (working files only)
- 5 worktrees ≈ 15 GB (not 25 GB)

**Cleanup:**
```bash
git worktree remove ../pmoves-old-feature
git worktree prune
git gc --aggressive  # Cleanup .git database
```

## Integration with Claude Code CLI

### Each Worktree Gets Own Claude Session

```bash
# Terminal 1: Main repository
cd /home/pmoves/PMOVES.AI
claude
# > /search:hirag "architecture patterns"
# > /health:check-all

# Terminal 2: Worktree feature
cd /home/pmoves/pmoves-feature-tz
claude
# > /deploy:up
# > /search:supaserch "TensorZero metrics"

# Both Claudes have same .claude/ context
# But work independently on different code
```

### Worktree-Specific Commands

Add worktree-aware slash commands:

**`.claude/commands/worktree/list.md`:**
```markdown
List all git worktrees in PMOVES repository.

Usage: /worktree:list

Implementation:
git worktree list
```

**`.claude/commands/worktree/create.md`:**
```markdown
Create new worktree for feature development.

Usage: /worktree:create {feature-name}

Implementation:
git worktree add ../pmoves-feature-{name} feature/{name}
```

## Real-World Example

**Scenario:** Implement TensorZero dashboard while fixing Hi-RAG bug

```bash
# Main repository: Continue normal work
cd /home/pmoves/PMOVES.AI
# Working on documentation

# Urgent bug fix needed
git worktree add ../pmoves-fix-hirag-crash hotfix/hirag-crash
cd ../pmoves-fix-hirag-crash
claude
# Claude helps debug and fix bug
# Run tests, commit, push PR
# Done, back to main work

# New feature requested
git worktree add ../pmoves-tz-dashboard feature/tensorzero-dashboard
cd ../pmoves-tz-dashboard
claude
# Claude builds TensorZero UI dashboard
# Long-running development, no rush
# Meanwhile, main repo still available for other work

# Later: Merge both when ready
cd /home/pmoves/PMOVES.AI
git checkout main
git merge hotfix/hirag-crash
git merge feature/tensorzero-dashboard

# Cleanup worktrees
git worktree remove ../pmoves-fix-hirag-crash
git worktree remove ../pmoves-tz-dashboard
```

## Summary

Git worktrees enable:
- ✅ Multiple Claude Code CLI instances working simultaneously
- ✅ Parallel feature development without branch switching
- ✅ Independent docker compose environments
- ✅ A/B testing different approaches
- ✅ Urgent fixes without disrupting current work
- ✅ Shared .claude/ context across all worktrees

**Key command:**
```bash
git worktree add ../pmoves-{feature-name} feature/{feature-name}
```

This is a powerful TAC pattern for scaling Claude Code CLI development in PMOVES.AI!
