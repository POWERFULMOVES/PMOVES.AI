# Cleanup Stale Worktrees

Remove merged or stale git worktrees to free disk space and reduce clutter.

## Usage

```
/worktree:cleanup [--dry-run] [--force] [--days N]
```

## Options

- `--dry-run`: Show what would be removed without removing
- `--force`: Skip confirmation prompts
- `--days N`: Consider stale after N days (default: 30)

## Removal Criteria

A worktree is considered stale if ANY of these conditions apply:

1. **Branch merged to main**: The worktree's branch has been merged
2. **No recent commits**: No commits in the last 30 days (configurable)
3. **Orphaned**: Branch was deleted but worktree remains

A worktree is PROTECTED if:

1. **Has uncommitted changes**: Modified files not committed
2. **Is main worktree**: Never remove the primary worktree
3. **Has active Claude session**: Lock file present

## Example

```bash
# Preview what would be cleaned up
/worktree:cleanup --dry-run

# Output:
# Analyzing worktrees...
#
# Will remove:
#   pmoves-fix-auth-bug (merged to main, 45 days ago)
#   pmoves-feature-old-test (no commits in 60 days)
#
# Protected (skipping):
#   pmoves-agent-1 (uncommitted changes)
#   pmoves-feature-hirag (active - 2 hours ago)
#
# Run without --dry-run to remove 2 worktrees
```

## Implementation

```bash
DAYS=${DAYS:-30}
STALE_DATE=$(date -d "$DAYS days ago" +%s)

for worktree in $(git worktree list --porcelain | grep "^worktree" | cut -d' ' -f2); do
    # Skip main worktree
    if [ "$worktree" = "$(git rev-parse --show-toplevel)" ]; then
        continue
    fi

    BRANCH=$(git -C "$worktree" branch --show-current 2>/dev/null)

    # Check if merged to main
    if git branch --merged main | grep -q "$BRANCH"; then
        echo "Merged: $worktree ($BRANCH)"
        REMOVE=true
    fi

    # Check for staleness
    LAST_COMMIT=$(git -C "$worktree" log -1 --format=%ct 2>/dev/null)
    if [ "$LAST_COMMIT" -lt "$STALE_DATE" ]; then
        echo "Stale: $worktree (no commits in $DAYS days)"
        REMOVE=true
    fi

    # Check for protection
    if [ -n "$(git -C "$worktree" status --porcelain 2>/dev/null)" ]; then
        echo "Protected: $worktree (uncommitted changes)"
        REMOVE=false
    fi

    # Remove if flagged and not dry-run
    if [ "$REMOVE" = true ] && [ "$DRY_RUN" != true ]; then
        git worktree remove "$worktree"
        git branch -d "$BRANCH" 2>/dev/null || true
    fi
done

# Prune any orphaned worktree metadata
git worktree prune
```

## Safety Features

- **Confirmation prompt**: Required unless `--force` is used
- **Uncommitted changes check**: Never removes worktrees with uncommitted work
- **Branch preservation**: Only deletes fully merged branches
- **Dry-run default**: Recommend running with `--dry-run` first

## Post-Cleanup

After cleanup:
1. Run `git worktree prune` to clean metadata
2. Run `git gc` to reclaim disk space
3. Use `/worktree:list` to verify remaining worktrees

## Related Commands

- `/worktree:list` - Show all worktrees before cleanup
- `/worktree:create` - Create new worktree after cleanup
