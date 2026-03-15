# PR Hedge Trim

Classify, fix, and resolve CodeRabbit review threads on open PRs.

## Arguments

- `$ARGUMENTS` - PR number(s) or flags: `--batch 935,936`, `--dry-run`, `--no-trail`

## Instructions

Parse `$ARGUMENTS` and execute the hedge trim cycle.

### Single PR (default)

Trim a single PR: analyze threads, apply fixes interactively, resolve addressed threads.

1. Run `make -C pmoves pr-trim-analyze PR=<number>`
2. Read the generated classification at `pmoves/docs/logs/pr_trim_<N>_threads.json`
3. Display the classification table to the user
4. For each **actionable** thread:
   - Read the file and line referenced
   - Apply the fix
   - Explain the change to the user
5. After all actionable threads are addressed, commit + push
6. Run `make -C pmoves pr-trim-resolve PR=<number> RESOLVE_ACTIONABLE=1`
7. Unless `--no-trail`: `make -C pmoves sign-trail SUMMARY="PR Hedge Trim: resolved K threads on PR #N"`

### Batch mode (`--batch`)

Trim multiple PRs in sequence.

1. Parse comma-separated PR numbers from `--batch`
2. Execute single-PR flow for each, in order
3. After all PRs trimmed, display summary table

### Dry-run mode (`--dry-run`)

Analyze only — classify threads but do not resolve or fix.

1. Run `make -C pmoves pr-trim-analyze PR=<number>`
2. Display classification table
3. Do not resolve threads, do not sign trail

### Report mode (`--report`)

Generate a detailed markdown report for a PR.

1. Run `make -C pmoves pr-trim-report PR=<number>`
2. Display: `pmoves/docs/logs/pr_trim_<N>_summary.md`

## Examples

```bash
# Trim a single PR
/pr-trim 934

# Batch trim multiple PRs
/pr-trim --batch 935,936,937

# Dry-run analysis only
/pr-trim 934 --dry-run

# Skip Graphiti trail signing
/pr-trim 934 --no-trail

# Generate detailed report
/pr-trim 934 --report
```

## Related

- `/pr-monitor` — Monitor PR merge readiness (read-only)
- `/chit:floos validate pr-monitor-graphiti-chit` — Validate the FlOO$ pipeline DAG
- `make -C pmoves pr-trim PR=<number>` — CLI equivalent of full cycle
