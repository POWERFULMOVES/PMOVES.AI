# Create Git Worktree

Create a new git worktree for parallel TAC (Tactical Agentic Coding) development.

## Usage

```
/worktree:create {category} {name}
```

## Categories

| Category | Pattern | Use Case |
|----------|---------|----------|
| `feature` | `pmoves-feature-{name}` | New capabilities |
| `fix` | `pmoves-fix-{issue}` | Bug fixes |
| `agent` | `pmoves-agent-{name}` | TAC parallel development |
| `env` | `pmoves-env-{tier}` | Environment testing |
| `hw` | `pmoves-hw-{target}` | Hardware-specific builds |

## Steps

1. **Validate inputs**: Ensure category is valid and name is alphanumeric with hyphens
2. **Check for conflicts**: Verify worktree doesn't already exist
3. **Create branch**: Create new branch from current HEAD if needed
4. **Create worktree**: `git worktree add ../pmoves-{category}-{name} -b {category}/{name}`
5. **Initialize submodules**: Run `git submodule update --init --recursive`
6. **Report success**: Show worktree path and next steps

## Example

```bash
# Create a feature worktree for Hi-RAG improvements
/worktree:create feature hirag-reranker

# Creates:
# - Branch: feature/hirag-reranker
# - Worktree: ../pmoves-feature-hirag-reranker
```

## Implementation

```bash
# Validate category
VALID_CATEGORIES="feature fix agent env hw"
if ! echo "$VALID_CATEGORIES" | grep -qw "$CATEGORY"; then
    echo "Invalid category. Use: $VALID_CATEGORIES"
    exit 1
fi

# Create worktree
WORKTREE_PATH="../pmoves-${CATEGORY}-${NAME}"
BRANCH_NAME="${CATEGORY}/${NAME}"

git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
cd "$WORKTREE_PATH"
git submodule update --init --recursive
```

## Next Steps After Creation

1. Switch to the new worktree: `/worktree:switch {name}`
2. Start services with different ports to avoid conflicts
3. Set `COMPOSE_PROJECT_NAME=pmoves-{category}-{name}` for Docker isolation

## Port Conflict Avoidance

When running multiple worktrees, use port offsets:
- Main: ports 8080-8099
- Feature worktrees: offset +100 (8180-8199)
- Agent worktrees: offset +200 (8280-8299)

See `.claude/context/git-worktrees.md` for detailed strategy.
