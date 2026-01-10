# List Git Worktrees

Display all PMOVES git worktrees with status and branch information.

## Usage

```
/worktree:list
```

## Output Format

```
PMOVES.AI Worktrees
===================

Main:
  Path:   /home/pmoves/PMOVES.AI
  Branch: main
  Commit: a7fe9cc docs: update README and add comprehensive release notes

Worktrees:
  pmoves-feature-hirag-reranker
    Path:   /home/pmoves/pmoves-feature-hirag-reranker
    Branch: feature/hirag-reranker
    Commit: 1234567 feat: add cross-encoder reranking
    Age:    2 days ago

  pmoves-agent-1
    Path:   /home/pmoves/pmoves-agent-1
    Branch: agent/parallel-task-1
    Commit: abcdef0 wip: researching model options
    Age:    1 hour ago
    Status: Active Claude session

Summary: 3 worktrees (1 main, 2 active)
```

## Implementation

```bash
echo "PMOVES.AI Worktrees"
echo "==================="
echo ""

git worktree list --porcelain | while read -r line; do
    case "$line" in
        worktree*)
            WORKTREE_PATH="${line#worktree }"
            ;;
        HEAD*)
            HEAD="${line#HEAD }"
            ;;
        branch*)
            BRANCH="${line#branch refs/heads/}"
            echo "  $(basename "$WORKTREE_PATH")"
            echo "    Path:   $WORKTREE_PATH"
            echo "    Branch: $BRANCH"
            COMMIT_MSG=$(git -C "$WORKTREE_PATH" log -1 --format="%h %s" 2>/dev/null)
            echo "    Commit: $COMMIT_MSG"
            echo ""
            ;;
    esac
done
```

## Related Commands

- `/worktree:create` - Create new worktree
- `/worktree:switch` - Switch to a worktree
- `/worktree:cleanup` - Remove stale worktrees

## Notes

- Worktrees with uncommitted changes are marked
- Active Claude sessions are detected via lock files
- Main worktree is always shown first
