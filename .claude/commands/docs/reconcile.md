# Reconcile Living Documents

Check and update living document metadata (Production Audit Dashboard + P2 Tracker).

## Arguments

- `$ARGUMENTS` - Optional flags: `--check` (read-only, default), `--update` (write changes), `--json` (machine output)

## Instructions

1. Parse `$ARGUMENTS`. If empty, default to `--check` (read-only mode).
2. Run the reconciliation via Make target:
   ```bash
   make -C pmoves docs-reconcile-check    # if --check or default
   make -C pmoves docs-reconcile          # if --update
   make -C pmoves docs-reconcile-json     # if --json
   ```
3. Report to the user:
   - Dashboard commit SHA vs current HEAD (and commit drift count)
   - Days since last dashboard update
   - Number of stale tracker items flagged for review
   - If `--update`: which metadata fields were changed

4. If stale findings exist and mode is `--check`, suggest running with `--update`.

## Example

```bash
# Check if documents are fresh (read-only)
/docs:reconcile

# Update stale dashboard metadata
/docs:reconcile --update

# Machine-readable report
/docs:reconcile --json
```

## Related

- `/deploy:audit-layers` - Full static audit certification (includes docs-reconcile-check)
- `/chit:sign-trail` - Sign Graphiti trail after audit work
- `/test:pr` - PR testing workflow
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` - Production audit dashboard
- `pmoves/docs/security/P2_SUBMODULE_TRACKER.md` - P2 issue tracker
