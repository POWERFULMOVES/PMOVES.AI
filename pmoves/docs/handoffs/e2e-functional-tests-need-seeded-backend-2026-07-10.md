# Handoff — E2E functional tests need a seeded backend in CI

**Date:** 2026-07-10
**Status:** deferred (non-required check; not a blocker)
**Owner:** UI / test-infra lane

## What's fixed (this PR, #2044)
- **Lint (ESLint)** — `LiveStageBadge.tsx` setState-in-effect → `useSyncExternalStore`. Green.
- **E2E build break** — `globals.css:116` comment contained `--cata-*/--void`; the `*/` closed the CSS comment early and broke the Playwright WebServer build (`CssSyntaxError: Unknown word usages`). Fixed. The dev/prod build no longer breaks — this was the failure that would have bitten every UI/room build.

## What remains (deferred — this handoff)
Fixing the CSS build break **unmasked** pre-existing functional E2E failures that the build error had been hiding (the build died before the tests ran):

- `e2e/archon-prompts.spec.ts`, `e2e/chat.spec.ts`, `e2e/ingest.spec.ts` — `toBeVisible` timeouts, "element(s) not found".
- Root cause: these specs drive real features (Archon prompt list, Agent-Zero chat, ingest) against a backend at `http://127.0.0.1:54321` (Supabase) using playwright test keys (`playwright.config.*` webServer env). **The E2E CI job does not start/seed Supabase**, so the data-dependent elements never render.

## Options for the follow-up PR
1. **Seed the backend in the E2E job** — add a `supabase start` (or a Supabase service container) + fixture seed step before `playwright test`. Makes the functional specs meaningful in CI.
2. **Split the suite** — tag backend-dependent specs (`@backend`) and run only smoke/render specs in the default CI job; run `@backend` in a separate job that stands up the stack (or against a live environment).
3. **Resilient skips** — have backend-dependent specs `test.skip()` when the backend is unreachable, so CI reflects "skipped, not failed".

Recommended: **#2 (split)** — keeps fast render/smoke coverage green in CI while running the heavier integration specs against a real stack, consistent with PMOVES's "run against live services" pattern.

## Note
E2E (Playwright) is a **non-required** check (required set: merge-gate, python-tests, hardening-validation, verify, submodule-gitlink-gate), so this does not block merges. It should be addressed before E2E is treated as a trustworthy signal.
