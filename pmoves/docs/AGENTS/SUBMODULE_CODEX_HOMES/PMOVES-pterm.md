# PMOVES-pterm

**Submodule:** `PMOVES-pterm/`
**Repository:** https://github.com/POWERFULMOVES/PMOVES-pterm.git
**Upstream:** pinokiocomputer/pterm
**Branch tracked:** `main` (upstream default; no `PMOVES.AI-Edition-Hardened` branch on this fork)

## Scope

The Pinokio terminal CLI.

`pterm` is the command-line surface of Pinokio. PMOVES uses it for the things a
launcher cannot do from inside a `start.js`:

- clipboard read/write
- desktop notifications
- native file/folder picker dialogs
- `pterm start` for testing a script without the desktop app

The `pinokio/app-list`, `pinokio/app-start` and `pinokio/app-stop` commands shell
out to it, and the `pterm` skill wraps it for Windows sessions.

## Use this when

- A launcher needs a host-side capability (clipboard, notification, file dialog).
- You are testing a Pinokio script headlessly.
- `pterm` is not on PATH and a `pinokio/app-*` command fails as a result.

## Requirements

pterm must be on PATH; on Windows it ships with the Pinokio desktop install at `D:\pinokio\`.

## PMOVES companions

- `PMOVES-pinokio/` — the launcher repo itself (`api/` at the root)
- `.claude/PINOKIO_LAUNCHER_GUIDE.md` — the PMOVES launcher rules
- `pmoves/docs/AGENTS/Pinokio-SKILL.md` — the agent-facing Pinokio doc

## Provenance

Forked 2026-08-20. It existed on GitHub with nothing in this repo pointing at
it until #2653 registered it — the same orphan state #2645 cleaned up for
`pbnj`/`PMOVES-pinokio`. The fork-registry ratchet validates submodule to
registry, not fork to submodule, so a dangling fork is invisible to it.
