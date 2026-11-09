---
name: pmoves-submodule-fleet
description: Audit 58+ git submodules — detached HEADs, commits-behind-tracked-branch, stale gitlink pins. Fast local audit (no network fetch). Use fork-sync.yml for upstream drift.
---

# pmoves-submodule-fleet

PMOVES.AI is a meta-repo with 58+ git submodules (`PMOVES-Archon`, `PMOVES-Agent-Zero`, `skills/*`, etc.). Detached HEADs, drifted gitlinks, and dirty working trees accumulate silently. This skill prints a single-screen audit so a worker can decide whether to propose a batch promotion commit.

## When to use

- Before a "promote submodules" maintenance commit (the recurring `chore(submodules): promote N pointers` pattern in git log)
- After a long-running session where multiple submodule branches advanced upstream
- When `git status` in the top-level shows mystery `(modified content)` lines
- Once a week as fleet hygiene

## How to run

```bash
bash .claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh
```

## What the script does (updated 2026-08-05)

1. Runs `git submodule status` (**top-level only, NOT `--recursive`**) — recursive hangs on 60+ nested submodules
2. Reads `pmoves/config/fork_registry.json` to identify `sync=false` forks and skips them
3. For each submodule: reads `.gitmodules` tracked branch, compares HEAD against it using **local refs only** (no `git fetch` — that hangs)
4. Prints: path, HEAD SHA, behind count, dirty flag, tracked branch name
5. **Always exits 0** — informational

## For upstream drift (fork vs upstream)

This script does NOT fetch from upstream. For fresh upstream drift data, use the GitHub App-powered workflow:

```bash
# Dry-run audit (reports STALE/CRITICAL per fork):
gh workflow run fork-sync.yml --ref main -f dry_run=true -f max_forks=40

# Real sync (creates PRs per fork):
gh workflow run fork-sync.yml --ref main -f dry_run=false -f max_forks=12
```

The fork-sync workflow uses the PMOVES GitHub App token and handles the `.gitmodules` tracked branch automatically.

## Output

```
path                                           | HEAD         | behind    | dirty | tracked-branch
-----------------------------------------------+--------------+-----------+-------+-------------------------
PMOVES-Agent-Zero                              | 70e5953      | 0         | n     | PMOVES.AI-Edition-Hardened
PMOVES-Archon                                  | 3d6e9b3      | 0         | y     | PMOVES.AI-Edition-Hardened
PMOVES-A2UI                                    | 2bac549      | 487       | y     | PMOVES.AI-Edition-Hardened
PMOVES-BoTZ                                    | e1d81eb      | 40        | y     | PMOVES.AI-Edition-Hardened
PMOVES-ClawZ                                   | skip         | skip      | skip  | sync=false
...

Notes:
  - Top-level only (NOT recursive). Use fork-sync.yml for upstream audit.
  - 'skip' = fork_registry.json marks this fork sync=false
  - 'behind' uses local refs only (no network fetch). Run fork-sync for fresh data.
```

## Promoting gitlinks

After fork-sync PRs merge, promote each gitlink ONLY when it's a clean fast-forward:

```bash
cur=$(git ls-tree HEAD <submodule-path> | awk '{print $3}')
new=$(gh api repos/POWERFULMOVES/<fork>/git/ref/heads/PMOVES.AI-Edition-Hardened --jq .object.sha)
gh api repos/POWERFULMOVES/<fork>/compare/$cur...$new --jq .status   # must be "ahead"; "diverged" = STOP
git update-index --cacheinfo 160000,$new,<submodule-path>
```

Commit as `chore(submodules): promote …` and PR. Batch multiple gitlinks per PR.

## Citations

- `.gitmodules` — pointer registry (58+ submodules)
- `pmoves/config/fork_registry.json` — 53 forks with sync=true/false decisions
- `pmoves/docs/operations/GITHUB_APP.md` — GitHub App token Known Road
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim collision check before bulk promotion
- `.claude/skills/fleet-fork-sync/SKILL.md` — the fork-sync workflow skill (companion)
