# Handoff: apply the Supabase-currency RLS correctives (DB lane)

**For:** Z890-CLAUDE (DB lane) — or via the new `supabase-db` MCP once `SUPABASE_DB_URI` is set
**From:** 4090-CLAUDE
**Date:** 2026-06-30
**Source PR (merged):** #1919 — `pmoves/db/v5_18_rls_currency_correctives.sql` + orphan `cast_tts_persistence.sql` fix
**Requires:** operator authorization / Known Road for `pmoves/supabase/migrations/` (gated)

## Context

The Supabase-currency audit (2026-06-30) found stale/deprecated RLS patterns; #1919 landed
the **source-of-truth** corrective (`pmoves/db/v5_18`). Two writes remain — both in the
**gated** `supabase/migrations/` apply path — to make the fix real on fresh bootstraps.

## Action 1 — patch the P1 bootstrap-breaker (REQUIRED for fresh bootstrap)

`pmoves/supabase/migrations/20250204000000_channel_monitor_tables.sql` (lines ~103-131) creates
**3 policies with `jwt_claim_role()`, which is undefined repo-wide**. On a fresh
`make -C pmoves supabase-bootstrap` this migration sorts early and **aborts under
ON_ERROR_STOP** before any later corrective can run (Codex caught this on #1919). v5_18 alone
can't fix fresh bootstrap.

**Patch the source migration in place** (it's a *broken* migration that never successfully
applies on fresh DBs, so this is fixing — not rewriting applied history). Replace each:
```sql
    FOR ALL
    USING (jwt_claim_role() = 'service_role');
```
with:
```sql
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```
on `pmoves.user_tokens`, `pmoves.user_sources`, `pmoves.channel_monitoring`. (`20250204…` is
already in the sql-policy-lint allowlist, so no lint change needed for it.)

## Action 2 — mirror v5_18 into the ledgered apply path

```
make -C pmoves db-apply-migration SRC=db/v5_18_rls_currency_correctives.sql \
  DST=20260630020000_rls_currency_correctives.sql
```
This sorts AFTER the base migrations, so it modernizes the P2/P3 patterns (and idempotently
re-asserts P1 for existing DBs). Then **allowlist it** in `.github/workflows/sql-policy-lint.yml`
(it uses service_role `USING(true)` + `TO anon` — reviewed-safe, same as the voice migs):
```
"pmoves/supabase/migrations/20260630020000_rls_currency_correctives.sql"
```

## Action 3 — apply + verify

```
make -C pmoves supabase-bootstrap      # or supabase-bootstrap-no-start
```
Verify no policy references `jwt_claim_role` / `request.jwt.claim.*` remain and the service
policies are `TO service_role`:
```sql
SELECT polname, polrelid::regclass FROM pg_policy
  WHERE pg_get_expr(polqual, polrelid) ILIKE '%jwt_claim_role%'
     OR pg_get_expr(polqual, polrelid) ILIKE '%request.jwt.claim%';   -- expect 0 rows
```

## Note — supabase-db MCP

Once `SUPABASE_DB_URI` is set + Claude Code restarted, the `supabase-db` MCP (#1918) can apply
these directly to a live DB and run RLS/policy inspection — but the **file** changes above are
still needed for fleet reproducibility (fresh bootstrap on every node).

## Cross-refs
- #1919 (source corrective), #1918 (supabase-db MCP), audit memory `reference_supabase_rls_accessor_idiom`
- `pmoves/db/v5_18_rls_currency_correctives.sql` (the exact SQL to mirror)
