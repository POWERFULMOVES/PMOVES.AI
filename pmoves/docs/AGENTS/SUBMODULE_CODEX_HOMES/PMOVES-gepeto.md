# PMOVES-gepeto

**Submodule:** `PMOVES-gepeto/`
**Repository:** https://github.com/POWERFULMOVES/PMOVES-gepeto.git
**Upstream:** pinokiocomputer/gepeto
**Branch tracked:** `main` (upstream default; no `PMOVES.AI-Edition-Hardened` branch on this fork)

## Scope

The Pinokio launcher-script generator.

`gepeto` generates Pinokio launcher scripts — the `install.js` / `start.js` /
`pinokio.js` set that turns a repo into a 1-click app.

PMOVES uses it as the starting point for new launchers, which are then hardened
by hand against `.claude/PINOKIO_LAUNCHER_GUIDE.md` (the URL-capture pattern in
`start.js` in particular).

## Use this when

- Standing up a launcher for a new app or demo.
- A generated script needs to be reconciled against the PMOVES launcher rules.

## Note on skills

The `gepeto` skill is a plugin skill, not a `.claude/commands/` entry, so this
submodule's `skills[]` in `submodule_skill_registry.json` is deliberately empty.
Listing a command file that does not exist is what produced the dangling skill
references tracked in #2637.

## Requirements

Node.js. Generates scripts; running them needs the Pinokio desktop app.

## PMOVES companions

- `PMOVES-pinokio/` — the launcher repo itself (`api/` at the root)
- `.claude/PINOKIO_LAUNCHER_GUIDE.md` — the PMOVES launcher rules
- `pmoves/docs/AGENTS/Pinokio-SKILL.md` — the agent-facing Pinokio doc

## Provenance

Forked 2026-08-20. It existed on GitHub with nothing in this repo pointing at
it until #2653 registered it — the same orphan state #2645 cleaned up for
`pbnj`/`PMOVES-pinokio`. The fork-registry ratchet validates submodule to
registry, not fork to submodule, so a dangling fork is invisible to it.
