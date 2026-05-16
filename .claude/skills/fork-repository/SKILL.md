---
name: fork-repository
description: Fork the running agent N times to branch engineering work into parallel concurrent investigations. Use when a task naturally divides into independent threads (e.g. explore vs verify, multiple subsystems, parallel hypothesis testing). Sourced from skills/pmoves-fork-repository-skill/ (fork of disler/fork-repository-skill).
---

# Fork-Repository Skill (Activation Pointer)

This skill is sourced from the constellation submodule `skills/pmoves-fork-repository-skill/`. Read that submodule's `SKILL.md` (or `README.md`) for full usage:

```
skills/pmoves-fork-repository-skill/SKILL.md
```

## Why activated for PMOVES.AI

PMOVES.AI runs many parallel agent dispatches (Three-Body model: Delivery + Control + Memory bodies; Archon mint QA flow; multi-submodule investigations). The fork-repository pattern formalizes that workflow as a reusable primitive.

## When Claude should invoke

- A request has 2+ genuinely independent sub-problems.
- Investigation needs separated state (different branches, different worktrees).
- Verifying a finding by independent replication.

## Cross-references

- `superpowers:dispatching-parallel-agents` — adjacent skill for general fan-out.
- `superpowers:using-git-worktrees` — worktree isolation primitive.
- `.claude/PATTERNS.md` — PMOVES-specific dispatch patterns.
