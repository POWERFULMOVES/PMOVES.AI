# Creator Collab Lane Workflow (Mavis)

Lane workflow for the `feat/creator-collab-lane` worktree. Mirrors the
openroom-adapter cadence (3 stacked commits per slice: P1 + functional +
docs) and the cron-driven progress pattern (state file at
`pmoves/tools/creator-collab-state.json`, self-reminder cron).

## Goals

1. **Slices ship independently and are auditable.** Each slice is a
   reviewable unit; AGNOTE entries record what changed and why.
2. **The lane can pause + resume.** If I (Mavis) go silent, the cron
   reminds me to continue. The state file records which slice is in
   progress so the next cron tick picks up where I left off.
3. **The lane self-disarms.** When all 7 slices are SHIPPED (or the
   operator pauses the lane), the cron stops itself.

## Slice plan (7 slices, additive)

| # | Slice | State |
|---|---|---|
| 1 | Contract extension (room_purpose, creator_surface, hardware_requirements, pinokio_app_refs) | SHIPPED 2026-07-27 |
| 2 | Pinokio bridge skill (pinokio-bridge-skill + Python adapter) | pending |
| 3 | NATS pipeline (comfy.collab.* + room.presence.v1 + room.directory.v1) | pending |
| 4 | Pinokio apps registry (curated/ + user/ + discovery tool + gepeto wrapper) | pending |
| 5 | creator-studio.room.collab.json + E2E smoke | partial (manifest + schema landed; smoke + Pinokio apps registry land together) |
| 6 | pmoves-helpdesk-skill + room-suggest-skill + pmoves.room.helpdesk.json | pending |
| 7 | Fordham ↔ PMOVES-helpdesk E2E (full cross-room flow + visual evidence) | pending |

## Pattern: 3 stacked commits per slice

For each non-trivial slice:
1. **P1 commit** — security / correctness / real-bug fixes. If the
   slice has no P1, this is omitted and we go straight to functional.
2. **Functional commit** — main code, schema, manifest, skill, NATS
   subjects. The "what changed" commit.
3. **Docs commit** — AGNOTE RELEASE entry + state cache update +
   spec doc (if the slice introduces a new one).

The PR head is `feat/creator-collab-lane` (the worktree branch, not a
stacked `creator-collab-N` per slice). Slices merge into the worktree
via `--no-ff` from a short-lived slice branch.

## Files

- `pmoves/tools/creator-collab-workflow.md` — this doc
- `pmoves/tools/creator-collab-state.json` — slice status cache
  (regenerated each commit)
- `pmoves/contracts/schemas/room/room.manifest.v1.schema.json` —
  schema (slice 1 added 4 top-level fields)
- `pmoves/scripts/validate_room_manifests.py` — validator (unchanged
  for slice 1; pinokio-app-registry check lands in slice 5a)
- `pmoves/config/rooms/creator-studio.room.collab.json` — slice 5
  seed (the first room that uses the new fields end-to-end)
- `pmoves/config/pinokio-apps/curated/<slug>.yaml` — slice 5a
  registry (12 entries)
- `pmoves/config/pinokio-apps/user/<slug>.yaml` — user-added apps
  (populated by the discovery tool from `D:\pinokio\api\`)

## Self-reminder cron

The cron fires every 30 minutes while the lane is active. Setup:

```python
mavis cron self --every 30m --prompt "creator-collab: continue next slice or check state"
```

The cron prompt itself is below.

---

## Cron prompt template

```text
creator-collab lane progress tick (Mavis).

Step 1: read pmoves/tools/creator-collab-workflow.md (this doc).
Step 2: read pmoves/tools/creator-collab-state.json (current slice
        status + which slice is in progress).
Step 3: if the in-progress slice is mid-commit, finish it.
Step 4: pick the next pending slice from the table. Verify dependencies
        (slices 2/3/4/5/6/7 build on slice 1's schema additions).
Step 5: write a 3-stacked-commit set on a short-lived slice branch,
        merge into feat/creator-collab-lane with --no-ff.
Step 6: push, update state, append AGNOTE entry, re-check.
Step 7: if all 7 slices are SHIPPED, post a closing summary on the
        PR and disarm the cron (mavis cron update --enabled false).

Constraints:
- No force-push. Always lands as a new commit on the existing branch.
- No bypassing CI. If a check fails, address it in a follow-up
  commit (do not skip).
- Always verify locally before push: run validate_room_manifests.py
  for slice 1/5/6 (manifest changes), the relevant test suite for
  the slice's domain.
- For slices that ship a new room manifest or change the OpenRoom
  surface, take Playwright screenshots to
  pmoves/docs/evidence/creator-collab-<date>/screenshots/.
- Don't touch feat-auto-* worktrees (operator's auto-mode).
- Bucket 'owner' for design / signoff / governance threads; don't
  fix in this lane.
```
