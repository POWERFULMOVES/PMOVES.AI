# Handoff: Apply voice migrations `v5_16` + `v5_17` (DB-apply gate)

**For:** Z890-CLAUDE (DB lane)
**From:** 4090-CLAUDE
**Date:** 2026-06-29
**Requires:** operator authorization / Known Road for `pmoves/supabase/migrations/` (zero-access readOnlyPath)
**Branch:** new branch off `main`, e.g. `feat/voice-migrations-applied`
**Status of blocker:** ✅ **UNBLOCKED** — #1902 fixed the `jwt_claim_role` apply-failure in `v5_16`; both files are now apply-safe.

---

## TL;DR

`pmoves/db/v5_16_voice_catalog.sql` and `pmoves/db/v5_17_fix_yt_oauth_cookies_rls.sql`
are merged to `main` but **will never reach a database** — nothing in the repo applies
`pmoves/db/v5_*.sql`. To actually apply them, mirror each into `pmoves/supabase/migrations/`
(the only auto-applied, ledgered path), then run `make -C pmoves supabase-bootstrap`.

## The gate (verified 2026-06-29 against `origin/main`)

`make -C pmoves supabase-bootstrap` (and `supabase-bootstrap-no-start`) iterate **only**:

1. `pmoves/supabase/migrations/*.sql`
2. `pmoves/supabase/initdb/*.sql`

…tracked idempotently in `public.pmoves_bootstrap_history (kind, filename)` — already-applied
files are skipped, so re-running is safe.

**There is no loop for `pmoves/db/v5_*.sql` anywhere in `pmoves/Makefile`.** Those files are
versioned source-of-truth / manual-reference only. The established pattern for getting a
`db/v5_*` schema into the applied set is to **mirror it into `supabase/migrations/` or
`supabase/initdb/`** — precedent: `v5_15` consciousness content is mirrored as
`pmoves/supabase/initdb/13_consciousness_theories.sql`.

`pmoves/scripts/apply_migrations_docker.sh` is the same story — it globs only
`supabase/migrations/*.sql`.

## The fix (Z890 action)

Both files are **migrations** (DDL + RLS + grants, corrective), so `supabase/migrations/`
is the correct home (timestamped, applied in `LC_ALL=C sort` order).

1. Mirror `pmoves/db/v5_16_voice_catalog.sql` →
   `pmoves/supabase/migrations/20260628000000_voice_catalog.sql`
2. Mirror `pmoves/db/v5_17_fix_yt_oauth_cookies_rls.sql` →
   `pmoves/supabase/migrations/20260628000100_fix_yt_oauth_cookies_rls.sql`
   (timestamp **after** the existing `20260417000000_yt_oauth_cookies.sql` it corrects, and
   after the `voice_catalog` mirror).

Copy verbatim — do not edit the SQL. Keep `pmoves/db/v5_16`/`v5_17` as the versioned
source-of-truth (same dual-home convention as v5_12/v5_15).

3. Apply: `make -C pmoves supabase-bootstrap`
   (or `supabase-bootstrap-no-start` against an already-running DB).

## Dependency / ordering notes (verified)

- `v5_16` does `CREATE SCHEMA IF NOT EXISTS pmoves_core` and has **no hard FK** to personas
  or consciousness tables — grounding refs (`persona_ids` → v5_12 `personas.persona_id`,
  `consciousness_theory_id` → v5_15 `consciousness_theories.id`) are **soft-ref JSONB**, not
  `REFERENCES`. So `v5_16` applies standalone; it does **not** require v5_12/v5_15 applied first.
- Its only `REFERENCES` is the self-contained `voice_profile_grants → voice_profiles(id)`.
- Both files use the correct post-#1902 idiom: `auth.uid()` for owner, policies `TO service_role`
  for the service bypass. **No `jwt_claim_role()`** (undefined repo-wide → would abort
  `CREATE POLICY`) and **no `request.jwt.claim.*` GUCs** (removed in PostgREST 9.0).
- Files are `CREATE ... IF NOT EXISTS` / `DROP POLICY IF EXISTS` + `CREATE POLICY` → safe to
  re-run; the bootstrap ledger also guards against double-apply.

## Verification (after apply)

```sql
-- tables present
\dt pmoves_core.voice_profile*
-- RLS enabled + service bypass + owner policies
SELECT polname, polcmd FROM pg_policy
  WHERE polrelid = 'pmoves_core.voice_profiles'::regclass;
-- yt_oauth_cookies now service-role-targeted (not the dead GUC policy)
SELECT polname FROM pg_policy
  WHERE polrelid = 'pmoves_core.yt_oauth_cookies'::regclass;
```

Expect: `voice_profiles` + `voice_profile_grants` tables; a `..._service_bypass` policy
`FOR ALL TO service_role`, owner insert/update policies, read policy; and
`yt_oauth_cookies_service_role_all` targeting `service_role`.

## Why this is the durable fix (not one-off psql)

A one-off `docker exec … psql < pmoves/db/v5_16…` would apply it once but leave every fresh
DB / CI bootstrap / new node missing the voice schema. Mirroring into the ledgered
`supabase/migrations/` path makes voice part of the standard bootstrap on every node —
which the multi-engine voice feature (host-or-standalone topology, S1c discovery shim,
S3 "Try a voice") depends on.

## Cross-refs

- Spec: `docs/superpowers/specs/2026-06-26-voice-agents-design.md` (§9 S1-gate)
- Schema source-of-truth: `pmoves/db/v5_16_voice_catalog.sql`, `pmoves/db/v5_17_fix_yt_oauth_cookies_rls.sql`
- Bootstrap target: `pmoves/Makefile` → `supabase-bootstrap` (~line 636)
- Precedent mirror: `pmoves/supabase/initdb/13_consciousness_theories.sql`
- Unblocking PR: #1902 (jwt_claim_role apply-blocker fix)
