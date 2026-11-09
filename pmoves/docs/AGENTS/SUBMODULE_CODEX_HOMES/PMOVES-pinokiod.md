# PMOVES-pinokiod

**Submodule:** `PMOVES-pinokiod/`
**Repository:** https://github.com/POWERFULMOVES/PMOVES-pinokiod.git
**Upstream:** pinokiocomputer/pinokiod
**Branch tracked:** `main` (upstream default; no `PMOVES.AI-Edition-Hardened` branch on this fork)

## Scope

The Pinokio daemon/backend.

`pinokiod` is the backend the Pinokio desktop app drives — it owns the app
registry, the process lifecycle, and the local HTTP surface the UI talks to.

Most launcher work never touches it. It matters when the failure is *below* the
script: an app that will not start with no script error, a stale process the UI
cannot kill, or a port that is bound after the app appears stopped.

## Use this when

- A launcher fails and `start.js` is demonstrably fine.
- Diagnosing stale processes or ports on a node running Pinokio.
- Reading how the app registry resolves an entry.

## Requirements

Runs as part of the Pinokio desktop install; not usually run standalone.

## PMOVES companions

- `PMOVES-pinokio/` — the launcher repo itself (`api/` at the root)
- `.claude/PINOKIO_LAUNCHER_GUIDE.md` — the PMOVES launcher rules
- `pmoves/docs/AGENTS/Pinokio-SKILL.md` — the agent-facing Pinokio doc

## Provenance

Forked 2026-08-20. It existed on GitHub with nothing in this repo pointing at
it until #2653 registered it — the same orphan state #2645 cleaned up for
`pbnj`/`PMOVES-pinokio`. The fork-registry ratchet validates submodule to
registry, not fork to submodule, so a dangling fork is invisible to it.
