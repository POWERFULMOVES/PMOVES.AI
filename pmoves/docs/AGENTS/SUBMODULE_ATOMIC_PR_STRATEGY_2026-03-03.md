# Submodule Atomic PR Strategy (2026-03-03)

## Scope

Production-lane closeout for currently dirty submodules and parent evidence refresh, with atomic commits and deterministic local validation.

## Required Context

- Branch posture: `PMOVES.AI-Edition-Hardened` remains production release lane.
- Sprint posture: keep M2 creator/publishing active while closing production audit gates.
- Operator sequence remains fixed: `env-setup -> env-check -> supa-start -> supabase-bootstrap -> up -> smoke -> smoke-gpu`.

## Lane Ownership (KRISS KROSS)

- `Codex`: implement code/doc fixes, run local validation, produce atomic commits, open/update PRs.
- `Claude`: parallel PR review lane, comment triage, merge execution once checks and review gates are satisfied.
- Collision rule: no shared-file edits in parallel; if overlap appears, pause and rebase before further edits.

## Atomic Commit Plan

1. `PMOVES-transcribe-and-fetch`
- Add nested submodule mapping (`.gitmodules`) for recursive integrity.
- Add `PMOVES.AI_INTEGRATION.md` dossier for PMOVES integration contract and validation path.

2. `PMOVES-Open-Notebook`
- Keep auth fail-closed in tests and inject bearer header in API client tests.

3. `Pmoves-cipher`
- Make memAgent env-var tests deterministic across platforms.
- Skip bash tool test suite on Windows where `/bin/bash` is unavailable.

4. `PMOVES-DoX`
- Sync chart processor test with current sync API (`process_charts` no longer async).
- Fix cache expiry boundary in dispatcher (`>=` at expiration edge).

5. Parent repo (`PMOVES.AI`)
- Update submodule gitlinks after submodule commits.
- Commit deterministic evidence refresh:
  - `pmoves/docs/SUBMODULE_LAYER_VALIDATION.md`
  - `pmoves/docs/SUBMODULE_LAYER_RUNALL.md`
  - `pmoves/docs/evidence/submodule_layer/*`
  - `pmoves/docs/evidence/submodule_layer_validation.json`
  - `pmoves/docs/evidence/submodule_layer_runall.json`
  - `pmoves/docs/evidence/submodule_test_matrix*.md|json`

## Validation Gate Pack

Submodule-local checks:

- `PMOVES-Open-Notebook`: `uv run --project . python -m pytest -q tests --maxfail=1` -> expected pass.
- `Pmoves-cipher`: `npx vitest run src/core/brain/memAgent/__test__/loader.test.ts src/core/brain/tools/definitions/system/__test__/bash.test.ts` -> expected pass with Windows bash suite skipped.
- `PMOVES-DoX`: targeted tests currently reproduce pre-existing stale expectation in `backend/tests/test_agent_dispatcher.py` (`_pending_tasks` removed in current implementation).

Parent deterministic checks:

- `make -C pmoves submodule-layer-validate-all-strict`
- `make -C pmoves submodule-integrity-strict`

## PR Order

1. Submodule PR: `PMOVES-transcribe-and-fetch`
2. Submodule PR: `PMOVES-Open-Notebook`
3. Submodule PR: `Pmoves-cipher`
4. Submodule PR: `PMOVES-DoX`
5. Parent PR: gitlinks + validation evidence

If CI queue starvation blocks merge, preserve latest `main` runs and cancel stale queued/pending non-main runs first.

## Handoff Notes

- DoX has a known packaging/test-env friction in `uv run` (editable build discovery on flat-layout). Use targeted venv-backed pytest invocation for local reproduction until packaging metadata is normalized.
- Keep test-failure triage explicit in PR notes when failure is pre-existing and outside the change set.
