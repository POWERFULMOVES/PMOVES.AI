---
name: pr-monitor
description: >
  FlOO$ PR monitor flow — capture merge blockers and review learnings for
  open PRs, classify them (actionable / nitpick / out-of-diff), encode the
  learnings as a CHIT packet, and gate merge readiness through the strict
  flow. Harness-neutral companion to the pr-monitor-graphiti-chit skill
  pairing (pmoves/configs/skill-pairings.yaml). Wraps the canonical make
  targets and adds the retry loop the GitHub API needs on flaky links
  (measured on B850 2026-09-22: three consecutive `error connecting to
  api.github.com` failures inside one pr-monitor run, full recovery on
  retry — the tool itself has no retry).
---

# pr-monitor — FlOO$ PR review flow

## When to invoke

- After opening a PR (this lane's own PRs included)
- Before any merge attempt (`chit-flow-pr-monitor-strict` is the merge gate)
- When `make -C pmoves pr-monitor` dies on transient GitHub API errors

## The flow (pairing: `pr-monitor-graphiti-chit`)

1. **Monitor with retry.** The tool iterates every open PR; one transient
   API error kills the whole run, so drive it with a retry wrapper:

   ```bash
   cd pmoves
   for i in 1 2 3 4 5; do
     make pr-monitor && break
     echo "[pr-monitor-skill] attempt $i failed — backing off 20s"
     sleep 20
   done
   ```

2. **Read the artifacts** (regenerated each run, never committed by default):

   - `pmoves/docs/logs/pr_monitor_latest.json` — machine record
   - `pmoves/docs/logs/pr_monitor_learnings_latest.md` — review learnings

3. **Classify** every thread into the four buckets (see
   `pmoves/docs/templates/PR_LEARNINGS.template.md` for the full taxonomy):
   missed-signal / fix-pattern / wrong-suggestion / already-addressed.
   Route other lanes' actionables to their authors — do not widen your own
   lane to absorb them.

4. **Encode the CHIT packet** (only when learnings are worth carrying):

   ```bash
   make pr-monitor-chit-packet
   ```

   → `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json`

5. **Gate** before merge:

   ```bash
   make chit-flow-pr-monitor-strict
   ```

   Strict RED is correct behavior while other lanes' actionables remain —
   the gate reports them; it is not yours to force green.

## Artifacts and subjects

| Artifact | Path |
|---|---|
| Monitor report | `pmoves/docs/logs/pr_monitor_latest.json` |
| Learnings | `pmoves/docs/logs/pr_monitor_learnings_latest.md` |
| CHIT packet | `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json` |
| NATS completion | `skills.pipeline.pr-monitor-graphiti-chit.v1` |

## Provenance

- Pairing definition: `pmoves/configs/skill-pairings.yaml` §pr-monitor-graphiti-chit
- Make targets: `pmoves/mk/preflight.mk` (pr-monitor, pr-monitor-strict),
  `pmoves/mk/codex.mk` (chit-flow-pr-monitor-strict, pr-monitor-chit-packet)
- Tool: `pmoves/tools/pr_monitor.py`
- This skill replaces the Claude-Code-command-only access path with a
  harness-neutral surface (any agent with bash + the repo can run it).
