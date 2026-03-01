# PR Monitor

Monitor PR merge readiness including actionable, nitpick, and out-of-diff review learnings.

## Arguments

- `$ARGUMENTS` - Optional: `--strict` for gate mode, `--chit` for CGP packet, `--floos` for full FlOO$ parity

## Instructions

Parse `$ARGUMENTS` and run the appropriate Make target from the `pmoves/` directory.

### Default (no args)

Collect current PR state and review learnings.

1. Run `make -C pmoves pr-monitor`
2. Display generated artifacts:
   - `pmoves/docs/logs/pr_monitor_latest.json` — raw PR state snapshot
   - `pmoves/docs/logs/pr_monitor_learnings_latest.md` — human-readable learnings
3. Summarize: open PRs count, actionable comments, nitpicks, out-of-diff items

### `--chit`

Generate a CHIT-encoded CGP packet from PR learnings for Graphiti trail handoff.

1. Run `make -C pmoves pr-monitor` (if not already fresh)
2. Run `make -C pmoves pr-monitor-chit-packet`
3. Display: `pmoves/docs/logs/pr_monitor_learnings_latest.cgp.json`

### `--strict`

Gate mode — exit 0 required before merge approval.

1. Run `make -C pmoves pr-monitor-strict`
2. If exit code is non-zero, list blocking items
3. If exit code is 0, confirm merge readiness

### `--floos`

Full FlOO$ parity check — validates the `pr-monitor-graphiti-chit` skill pairing pipeline.

1. Run `make -C pmoves chit-flow-pr-monitor-strict`
2. Report: DAG validity, dependency satisfaction, CHIT encoding status, Graphiti sync

## Examples

```bash
# Quick PR status check
/pr-monitor

# Generate CHIT packet for handoff
/pr-monitor --chit

# Pre-merge gate check
/pr-monitor --strict

# Full FlOO$ pipeline validation
/pr-monitor --floos
```

## Related

- `/chit:floos validate pr-monitor-graphiti-chit` — Validate the FlOO$ pipeline DAG
- `/chit:encode` — Encode data as CGP v2 packet
- `/github:pr-review` — Review a specific PR
