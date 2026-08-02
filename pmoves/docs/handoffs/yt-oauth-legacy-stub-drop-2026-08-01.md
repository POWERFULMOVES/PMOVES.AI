# Handoff: drop legacy public.yt_oauth_cookies stub (unblocks YT playlist lane)

**Symptom (operator, 2026-08-01):** `make yt-cookies-auth` completes Google
OAuth consent, then dies on
`PGRST204: Could not find the 'access_token_expires_at' column of 'yt_oauth_cookies'`
— tokens from the successful consent are discarded. Crush hit the same wall
on the PMOVES.YT lane.

**Root cause (verified live on 5090):** TWO tables named `yt_oauth_cookies`:

- `pmoves_core.yt_oauth_cookies` — the real one (migration
  `20260417000000_yt_oauth_cookies.sql`, has `access_token_expires_at` and
  the full 14-column shape the writer/refresher/OAuth tool expect).
- `public.yt_oauth_cookies` — a 4-column legacy stub (user_id,
  encrypted_token, created_at, updated_at), **0 rows**, created before the
  migration ledger; no migration or seed recreates it.

PostgREST resolves the unqualified REST path `/rest/v1/yt_oauth_cookies` to
`public` first, so the stub SHADOWS the real table and every upsert 400s.

**Fix:** migration `20260801000000_drop_legacy_public_yt_oauth_cookies.sql` —
`DROP TABLE IF EXISTS public.yt_oauth_cookies;` + `NOTIFY pgrst, 'reload
schema';`. Idempotent; zero data risk (stub empty, count verified).

**Why the Known Road:** damage-control gates both raw `DROP TABLE` in bash
(correctly) and writes to `pmoves/supabase/migrations/` — this handoff is the
tracked reason for `KNOWN_ROAD=migrations:handoff:yt-oauth-legacy-stub-drop-2026-08-01.md`.

**After apply:** operator reruns `make -C pmoves yt-cookies-auth` (one more
browser consent — the previous tokens were never stored), then the
cookie-writer/refresher take over and the playlist lane unblocks.
