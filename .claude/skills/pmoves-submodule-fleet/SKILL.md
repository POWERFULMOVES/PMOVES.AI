---
name: pmoves-submodule-fleet
description: Audit 25+ git submodules — detached HEADs, commits-behind-main, stale gitlink pins. Propose batch promotion.
---

# pmoves-submodule-fleet

PMOVES.AI is a meta-repo with 25+ git submodules (`PMOVES-Archon`, `PMOVES-Agent-Zero`, `skills/*`, etc.). Detached HEADs, drifted gitlinks, and dirty working trees accumulate silently. This skill prints a single-screen audit so a worker can decide whether to propose a batch promotion commit.

## When to use

- Before a "promote submodules" maintenance commit (the recurring `chore(submodules): promote N pointers` pattern in git log)
- After a long-running session where multiple submodule branches advanced upstream
- When `git status` in the top-level shows mystery `(modified content)` lines
- Once a week as fleet hygiene

## How to run

```bash
bash .claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh
```

The script:

1. Runs `git submodule status --recursive` to enumerate every submodule pointer.
2. For each submodule: best-effort `git fetch --quiet origin`, then computes:
   - Current HEAD short SHA
   - `behind` count vs `origin/main` (fallback to `origin/master` if main absent)
   - `dirty` flag from `git status --short`
3. Prints one informational line per submodule. **Always exits 0** — never blocks.

## Output

```
PMOVES-Archon                | HEAD=a1b2c3d | behind=4  | dirty=n
PMOVES-Agent-Zero            | HEAD=e5f6789 | behind=12 | dirty=y
skills/Pmoves-skills         | HEAD=0011223 | behind=0  | dirty=n
...
```

Use this to author the batch-promotion commit body. Confirm collision-free against the Active Claim Register before pushing.

## Citations

- `.gitmodules` — pointer registry
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim collision check before bulk promotion
- Recent commit pattern: `chore(submodules): promote N top-level + nested archon pointers`
