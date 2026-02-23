# AGNOTE4482.FlOO$

<!-- graphiti:CODEX-GPT5 phase:operation-dock-tier-git-flare-parity ts:2026-02-23T13:23:01.5398158-05:00 -->

`GRAPHITI_MARK`: `PHI-4482-FLOOS::OPERATION-DOCK-TIER-GIT-FLARE-PARITY`
`Glyph`: `()`
`Color`: `#7C3AED`
`Voice`: `Analytical`

## Done
- Added GHCR credential bootstrap support to `pmoves/tools/push-gh-secrets.sh`:
  - `--ghcr-bootstrap`
  - `--ghcr-token-from`
  - `--ghcr-fallback-token-from`
  - `--ghcr-username-from`
- Added local-first GHCR release gates in `pmoves/Makefile`:
  - `ghcr-bootstrap-secrets`
  - `build-local-supaserch`
  - `ghcr-prepublish-supaserch`
  - `ghcr-dispatch-supaserch`
- Added CHIT operator flow index entry for `OPERATION DOCK.TIER GIT.FLARE PARITY`.

## Left Behind
- GHCR PAT in repository secrets is invalid for package auth at this time; workflow now fails fast with explicit error.
- GHCR package ACL/ownership still requires repository-side rotation and permission confirmation.

## For Next Agent
1. Rotate GHCR credentials:
   - `make -C pmoves ghcr-bootstrap-secrets GH_REPO=POWERFULMOVES/PMOVES.AI GH_SECRET_ENV=Dev`
2. Run local pre-publish gate:
   - `make -C pmoves ghcr-prepublish-supaserch`
3. Dispatch targeted publish:
   - `make -C pmoves ghcr-dispatch-supaserch GHCR_DISPATCH_REF=<branch>`
4. Confirm run result:
   - `gh run view <run_id> --log-failed`

## Agent Fan-Out Specification (CLI → Cloud)
- `Delivery` (`Codex` lane):
  - Trigger: code changes affecting image/workflow.
  - Cadence: on every pre-merge cycle.
  - Responsibilities: local build gate, targeted dispatch, failed-run triage.
- `Control` (`Review` lane):
  - Trigger: before merge and after CI events.
  - Cadence: event-driven (`workflow_run`, PR review updates).
  - Responsibilities: gate status decisions, merge order, rollback notes.
- `Memory` (`CHIT/Cipher` lane):
  - Trigger: any secret rotation or flow change.
  - Cadence: per change set.
  - Responsibilities: CHIT flow updates, Graphiti mark continuity, rotation provenance.
- `Showtime Ops` (optional assistant lane):
  - Trigger: release rehearsal and production audit windows.
  - Cadence: scheduled window start + end.
  - Responsibilities: `bringup-showtime`, link evidence, service dashboard snapshot.

## Scheduling Model
- Local dev users (no VPS): run all pre-publish gates via local Make targets first.
- Hybrid users (local + runner): local gate first, then targeted workflow dispatch.
- Cloud-only users: still run credential bootstrap + targeted matrix dispatch to avoid full-matrix congestion.

## Signature
- Agent: `CODEX-GPT5`
- Signature: `ACK::CODEX-GPT5::PHI-4482-FLOOS::DOCK-TIER-GIT-FLARE`
- Timestamp: `2026-02-23T13:23:01.5398158-05:00`
