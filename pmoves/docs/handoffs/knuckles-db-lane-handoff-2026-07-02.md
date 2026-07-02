# Handoff: DB-lane live-apply — Z890 → Knuckles (B850)

**For:** B850-CLAUDE (Knuckles) — DB lane
**From:** 4090-CLAUDE
**Date:** 2026-07-02
**Reason for reassignment:** Z890 is being **reinstalled (Windows)** and is offline. The
Supabase DB-lane apply work that was parked with Z890 (handoffs #1907 → #1909, #1920)
now belongs to Knuckles until Z890 returns.
**Requires:** the data-tier (`supabase-db`) up + host-reachable, and operator
authorization / Known Road for `pmoves/supabase/migrations/` writes (gated readOnlyPath).

---

## Live state on `main` (verified 2026-07-02, via `gh` Contents API)

| Item | State |
|------|-------|
| Voice v5_16 mirror — `20260628000000_voice_catalog.sql` | ✅ present in `supabase/migrations/` |
| Voice v5_17 mirror — `20260628000100_fix_yt_oauth_cookies_rls.sql` | ✅ present |
| Voice anon-grant corrective — `20260630000000_voice_catalog_anon_grant.sql` | ✅ present |
| `20250204000000_channel_monitor_tables.sql` P1 breaker | ❌ **still broken** — `jwt_claim_role()` at lines 105/126/131 |
| v5_18 currency correctives mirror | ❌ **not yet mirrored** into `supabase/migrations/` |
| Live `supabase-bootstrap` (apply to a running DB) | ❌ **deferred** by Z890 (CHIT/data-tier gate) — never run |

**Net:** all voice schema is in the bootstrap path, but **nothing has been applied to a
live DB yet**, and two source writes remain. Until the live apply runs, `voice_profiles`
is empty and the flute-gateway S1 registry (#1922) **graceful-degrades to `DEFAULT_PROVIDER`**
— a default voice works, but persona/profile routing (Dr. Bean / Mr. Clean / PowerPuff)
won't resolve. **This apply is the single gate on 4090's "first persona voice".**

---

## Action 1 — patch the P1 bootstrap-breaker (REQUIRED before any bootstrap)

`pmoves/supabase/migrations/20250204000000_channel_monitor_tables.sql` creates **3 policies
with `jwt_claim_role()`, which is undefined repo-wide**. On a fresh `supabase-bootstrap` this
migration sorts early and **aborts under `ON_ERROR_STOP`** before any later corrective can run
(Codex caught this on #1919 — v5_18 alone cannot fix a fresh bootstrap).

It is a *broken* migration that never successfully applies on fresh DBs, so patching in place
is fixing, not rewriting applied history. Replace each of the 3 occurrences:
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
on `pmoves.user_tokens`, `pmoves.user_sources`, `pmoves.channel_monitoring` (lines ~103–131).
`20250204…` is already in the sql-policy-lint allowlist — no lint change needed for it.

## Action 2 — mirror v5_18 into the ledgered apply path

```
make -C pmoves db-apply-migration SRC=db/v5_18_rls_currency_correctives.sql \
  DST=20260630020000_rls_currency_correctives.sql
```
(`db-apply-migration` is the sanctioned Known Road make target — the mirror runs inside `make`,
the sanctioned readOnlyPath bypass; do NOT `cp` by hand, the bash hook hard-blocks it.)
This sorts AFTER the base migrations, so it modernizes the P2/P3 patterns and idempotently
re-asserts P1 for existing DBs. Then **allowlist it** in `.github/workflows/sql-policy-lint.yml`
(it uses service_role `USING(true)` + `TO anon` — reviewed-safe, same as the voice migs):
```
"pmoves/supabase/migrations/20260630020000_rls_currency_correctives.sql"
```

## Action 3 — run the live apply + verify

```
make -C pmoves supabase-bootstrap          # or supabase-bootstrap-no-start
```
This iterates `supabase/migrations/*.sql` then `supabase/initdb/*.sql`, idempotent via the
`public.pmoves_bootstrap_history (kind, filename)` ledger (already-applied rows are skipped —
safe re-run). It applies, in one pass:
- the voice schema (v5_16/v5_17 + anon-grant) → **creates + seeds `pmoves_core.voice_profiles`**,
- the currency correctives (Action 2),
- the P1 fix (Action 1).

Verify no policy still references the dead accessors, and `voice_profiles` exists:
```sql
SELECT polname, polrelid::regclass FROM pg_policy
  WHERE pg_get_expr(polqual, polrelid) ILIKE '%jwt_claim_role%'
     OR pg_get_expr(polqual, polrelid) ILIKE '%request.jwt.claim%';   -- expect 0 rows

SELECT count(*) FROM pmoves_core.voice_profiles;                       -- expect > 0
```

## Action 4 — signal 4090 (unblocks the first persona voice)

Once `voice_profiles` is populated, drop a RELEASE line in `AGNOTE4482PHI.t1.md` noting the
live apply landed. That flips 4090's flute-gateway S1 registry from `DEFAULT_PROVIDER`
degradation to real profile-driven routing — 4090 can then run the persona voice slice (S3).

---

## Notes

- **`supabase-db` MCP** (#1918): once `SUPABASE_DB_URI` is set + Claude Code restarted on the
  data-tier host, the MCP can apply these directly to the live DB and run RLS/policy inspection.
  The **file** changes (Actions 1–2) are still required for fleet reproducibility (fresh
  bootstrap on every node), independent of the MCP path.
- **Cipher lane (already yours):** the follow-up to bump the PMOVES.AI superproject gitlink for
  `Pmoves-cipher` → new `main` tip (after PR #5 merged) is still open — a separate superproject PR.
- **Do not sidestep the guard.** `supabase/migrations/` is operator-gated; route the writes via
  the `db-apply-migration` Known Road target or the `supabase-db` MCP.

## Cross-refs
- Source corrective: **#1919** (`pmoves/db/v5_18_rls_currency_correctives.sql` — the exact SQL to mirror)
- MCP: **#1918** (`supabase-db` Postgres MCP)
- Prior Z890 handoffs (superseded by this): `z890-rls-currency-apply-2026-06-30.md` (#1920),
  `z890-voice-migration-apply-gate-2026-06-29.md` (#1907, mirror done via #1909)
- Audit memory: `reference_supabase_rls_accessor_idiom`
