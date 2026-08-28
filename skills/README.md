# PMOVES.AI Skills Constellation

POWERFULMOVES forks of upstream agent-skill repositories. Each entry is a git submodule under `skills/` that tracks an upstream skill library, lets us layer PMOVES-specific changes, and stays discoverable as a single constellation.

## Tier

**Tier 2 — On-Demand (Major Subsystem).** Load this README first. Load a specific skill submodule's CLAUDE.md / README only when working in that skill's domain.

## Constellation

| Submodule | Path | Upstream | Purpose | Status |
|-----------|------|----------|---------|--------|
| `PMOVES-skills` | `skills/PMOVES-skills/` | [vercel-labs/skills](https://github.com/vercel-labs/skills) | **The package** — `npx skills add owner/repo`, installs skills into any of 75+ agent harnesses | ✅ Tracks `PMOVES.AI-Edition-Hardened` |
| `PMOVES-awesome-agent-skills` | `skills/PMOVES-awesome-agent-skills/` | [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | Curated index of skills/tools/tutorials for AI coding agents | ✅ Added (2026-05-09) |
| `pmoves-fork-repository-skill` | `skills/pmoves-fork-repository-skill/` | [disler/fork-repository-skill](https://github.com/disler/fork-repository-skill) | Fork the running agent N times to branch engineering work | ✅ Activated (2026-05-15) — pointer at `.claude/skills/fork-repository/` |
| `PMOVES-agent-sandbox-skill` | `skills/PMOVES-agent-sandbox-skill/` | [disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill) | Manage isolated execution environments for agents | ✅ Activated (2026-05-15) — pointer at `.claude/skills/agent-sandbox/` |
| `Pmoves-claude-d3js-skill` | `skills/Pmoves-claude-d3js-skill/` | [chrisvoncsefalvay/claude-d3js-skill](https://github.com/chrisvoncsefalvay/claude-d3js-skill) | D3.js skill — Claude-driven data visualization | ✅ Activated (2026-05-15) — pointer at `.claude/skills/claude-d3js/` |

### Sources live inside the package fork

`PMOVES-skills` carries a `sources/` overlay on `PMOVES.AI-Edition-Hardened`
holding the skill-source forks as submodules — including the two the parent repo
no longer tracks directly:

| source | upstream |
|---|---|
| `Pmoves-Claude-skills` | [anthropics/skills](https://github.com/anthropics/skills) |
| `Pmoves-Minimax-skills` | [MiniMax-AI/skills](https://github.com/MiniMax-AI/skills) (MIT, 17 skills + a pptx-plugin) |

`main` on that fork stays byte-identical to upstream so fork-sync is always a
fast-forward. See `sources/README.md` there for the branch contract.

### Correction (2026-08-20): there was no "recentering"

This file previously stated that *"the skills library that was at
`MiniMax-AI/skills` moved to `vercel-labs/skills`"*, and on that basis filed
`POWERFULMOVES/Pmoves-Minimax-skills` as a **deprecated pre-recenter URL** not
worth adding as a submodule.

That is wrong, and the consequence was real: a live MIT library of 17 skills sat
forked and referenced by nothing.

No move happened. Both repositories are alive and unrelated:

| | `MiniMax-AI/skills` | `vercel-labs/skills` |
|---|---|---|
| what it is | a **collection** of skills | a **tool** — "the open agent skills tool - npx skills" |
| stars | 13,403 | 29,327 |
| last push | 2026-04-18 | 2026-08-18 |

`MiniMax-AI/skills`' HEAD commit does not exist anywhere in `vercel-labs/skills` —
they share no history, which a genuine repository move would have preserved. One
installs skills; the other is a source of them.

Separately, `Pmoves-skills` was never a name for either. It was the **Anthropic**
fork, renamed to `Pmoves-Claude-skills`. Because GitHub repository names are
case-insensitive, the name it vacated was immediately taken by `PMOVES-skills`,
so the old `skills/Pmoves-skills` submodule silently began resolving to the
vercel-labs CLI instead of the Anthropic library. That duplicate entry is removed;
the Anthropic fork is tracked under `sources/` above.

## Adding more skill forks (future)

All five entries in the constellation table landed across two singleton rounds on 2026-05-09 (z890), with the 6th (PMOVES-skills) added in 2026-08-17. Adding new external skill forks crosses an untrusted-code-integration boundary that requires both:

1. A damage-control allowlist entry if any read-only path is touched (see `.claude/hooks/damage-control/patterns.yaml`).
2. **Per-URL Bash-tool authorization** — the runtime gates each external repo URL separately, even after general approval. The cleanest path is for an operator to run the singleton add as a `! <command>` in a Claude Code prompt, or directly in a shell.

The `.claude/context/submodules.md` registry is the canonical map of these forks; `pmoves/configs/submodule_skill_registry.json` carries context-tag injection rules.

## Activation paths

How each skill becomes available to a Claude Code session:

- **`PMOVES-skills/`** — the package itself. `npx skills add <owner>/<repo>` installs a source's skills into the target harness's directory (`.claude/skills/`, `.agents/skills/`, `.minimax/skills/`, …). Its `sources/` overlay holds the forks it installs from.
- **`PMOVES-skills/sources/Pmoves-Claude-skills/`** — the Anthropic library. Most of its skills are already published as plugins (e.g. `superpowers:*`); the fork is a reference for *authoring* new ones, and ships the `spec/` and `template/`.
- **`PMOVES-skills/sources/Pmoves-Minimax-skills/`** — MiniMax's 17-skill MIT library plus a pptx-plugin.
- **`PMOVES-awesome-agent-skills/`** — read as documentation; entries link out to upstream skill repos.
- **`pmoves-fork-repository-skill/`** — registers as a Claude Code skill; activate via the skill registry once added to `.claude/skills/` or imported as a plugin.
- **`PMOVES-agent-sandbox-skill/`** — same activation path as fork-repository-skill.
- **`Pmoves-claude-d3js-skill/`** — Claude Code skill for D3.js visualization; activate via the skill registry.

## KiloCode skills

The constellation above is for **Claude Code** skill submodules under `skills/` and `.claude/skills/`.

KiloCode GLM skills live in a separate native directory: `.kilocode/skills/`. These are not git submodules; they are tracked directly in the monorepo so KiloCode can load them via `kilo.json`:

- `.kilocode/skills/kilocode-bringup-audit/` — tiered bring-up/health validation
- `.kilocode/skills/kilocode-agent-trails/` — AGENT TRAILS roguelike navigation

Future KiloCode skill forks can be added here if they need to be shared across repos; for now the native `.kilocode/skills/` path is the canonical location.

## Cross-references

- Root `CLAUDE.md` — keystone, points here as Tier-2 constellation
- `.claude/CLAUDE.md` — context loading priority (Tier 2 entry references this README)
- `.claude/context/submodules.md` — comprehensive submodule registry (pending the proposal in `pmoves/docs/proposals/`)
- `PMOVES-agents.md/` — sibling Tier-2 always-relevant submodule for AGENTS.md format reference
- `pmoves/configs/submodule_skill_registry.json` — context-tag injection registry; new skill submodules should be registered here once they have CLAUDE.md files
- `pmoves/docs/AGENTS/KILOCODE_OPERATOR_HOME.md` — KiloCode cold-start runbook
