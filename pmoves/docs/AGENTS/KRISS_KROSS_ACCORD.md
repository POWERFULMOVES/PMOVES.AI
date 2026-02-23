# KRISS KROSS Accord
_Last updated: 2026-02-23_

Purpose: prevent agent collisions by converting overlap into a controlled
overlay workflow.

## Roles (Codex-led window)

- `Codex` (`DJ/Lead`)
  - owns implementation lane and merge-ready weave
  - authors Codex command mappings
  - decides parity completeness for release
- `Claude` (`Counterpoint/Scout`)
  - audits checks/comments/failures
  - proposes focused diffs in integration branch
  - supplies evidence packets for Codex weave

## KRISS KROSS handshake

1. `CLAIM`
   - each agent posts branch, scope, and TTL.
2. `OVERLAY`
   - owner/scout split is declared with one `overlay_id`.
3. `WEAVE`
   - scout sends candidate patches + evidence.
   - owner performs final integration in target branch.
4. `RELEASE`
   - owner signs release.
   - scout signs ack.

## Required fields

- `overlay_id`
- `lane_owner`
- `scout_agent`
- `target_branch`
- `scope`
- `evidence_paths`
- `parity_report_path`
- `agent_signature`

## CODEX WEAVE checklist

1. Resolve string/port/env drift against source-of-truth docs (`AGENTS.md` + compose).
2. Run parity coverage check:
   - `make -C pmoves codex-parity-check`
3. Update command map and rerun report.
4. Record release signature in AGNOTE lane.
