# Switch to Git Worktree

Change Claude Code's working directory to a different PMOVES worktree.

## Usage

```
/worktree:switch {identifier}
```

## Identifier Options

- **Short name**: `hirag-reranker` (matches pmoves-feature-hirag-reranker)
- **Full name**: `pmoves-feature-hirag-reranker`
- **Category/name**: `feature/hirag-reranker`
- **Path**: `/home/pmoves/pmoves-feature-hirag-reranker`

## Steps

1. **Resolve identifier**: Find matching worktree
2. **Verify exists**: Ensure worktree path is valid
3. **Check status**: Show current branch and uncommitted changes
4. **Change directory**: Update working directory
5. **Load context**: Apply worktree-specific CLAUDE.md if present

## Example

```bash
# Switch to a feature worktree
/worktree:switch hirag-reranker

# Output:
# Switched to: /home/pmoves/pmoves-feature-hirag-reranker
# Branch: feature/hirag-reranker
# Status: Clean (no uncommitted changes)
#
# Note: Docker services may need restart with new COMPOSE_PROJECT_NAME
```

## Implementation

```bash
# Find worktree by identifier
WORKTREE=$(git worktree list | grep -i "$IDENTIFIER" | head -1 | awk '{print $1}')

if [ -z "$WORKTREE" ]; then
    echo "Worktree not found: $IDENTIFIER"
    echo "Available worktrees:"
    git worktree list
    exit 1
fi

# Change to worktree
cd "$WORKTREE"
echo "Switched to: $WORKTREE"
echo "Branch: $(git branch --show-current)"

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "Status: Uncommitted changes present"
else
    echo "Status: Clean"
fi
```

## Docker Considerations

When switching worktrees, running Docker services may conflict:

```bash
# Stop services in current worktree
docker compose down

# Switch worktree
/worktree:switch agent-1

# Set unique project name
export COMPOSE_PROJECT_NAME=pmoves-agent-1

# Start services in new worktree
docker compose up -d
```

## Related Commands

- `/worktree:list` - Show all worktrees
- `/worktree:create` - Create new worktree
