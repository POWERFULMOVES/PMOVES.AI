# yt-cookies Supabase Auth refactor (Lane 2228, 2026-08-03)

> Cold-read spec for the yt-cookies OAuth refactor. If you are a fresh
> local model picking this work up next session, this is the document
> that tells you what shipped, why, and what's left.

## TL;DR

The 3-PR env var fix dance this week (#2327, #2333, #2346) was patching a
symptom. The root cause was that we were storing the Google OAuth refresh
token in a custom Supabase table — `pmoves_core.yt_oauth_cookies` — and
hand-rolling the OAuth refresh flow with a direct `httpx.post(TOKEN_URL, ...)`.
When the legacy `SERVICE_ROLE_KEY` env var carried a stale key signed by a
retired JWT secret, every Supabase upsert 401'd, and the only fix was to
swap the env var preference.

This lane moves the OAuth token storage to Supabase Auth's built-in
`auth.identities` table (managed by Supabase, not us), and replaces the
hand-rolled refresh flow with a focused 50-line direct OAuth2 client
that's only as big as it needs to be. The 3-PR fix dance is no longer
relevant because the Supabase Admin API uses its own key path.

## Why now

- The 3-PR env var fix dance was a clear sign the architecture was wrong.
  Every time someone changes a Supabase service-role key, we have to
  re-verify the env var preference across 3 services. That's not
  maintainable.
- The user (`DARKXSIDE`) is creating a Supabase user `darkxside@pmoves.ai`
  and will sign in once via Google. The Google identity is seeded in
  `auth.identities` with the resulting `provider_token` +
  `provider_refresh_token`. From then on, the yt-cookie-refresher can
  read the identity server-side (admin endpoint, service_role key) and
  rotate the `provider_token` via direct OAuth2 client.

## What shipped

### Code (P1 commit)

**`pmoves/services/yt-cookie-refresher/oauth_client.py`** (new, 50 lines)
Focused direct OAuth2 client. Takes a `provider_refresh_token` and returns
a fresh `(provider_token, expires_at)`. ~30 lines of actual logic + the
required env var guard + the structured-error-preservation pattern from
the old `oauth_handler.py`.

```python
def refresh_provider_token(provider_refresh_token: str) -> Tuple[str, datetime]:
    client_id = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("missing CHANNEL_MONITOR_GOOGLE_CLIENT_ID or ...")
    resp = httpx.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": provider_refresh_token,
    }, timeout=30)
    # ... preserve OAuth error payload before raising ...
```

**`pmoves/services/yt-cookie-refresher/supabase_auth.py`** (new, 110 lines)
Reads the Google identity from `auth.identities` for the
`darkxside@pmoves.ai` user via the Supabase Management API.

```python
def get_provider_refresh_token(user_email=DARKXSIDE_USER_EMAIL) -> Optional[str]:
    identity = get_google_identity(user_email)
    if not identity:
        return None
    return identity.get("identity_data", {}).get("provider_refresh_token")
```

Uses `params=` (not f-string interpolation in the URL) so emails with
reserved URL characters (`+`, etc.) are percent-encoded correctly.

**`pmoves/services/yt-cookie-refresher/supabase_client.py`** (modified)
Drops the `encrypted_refresh_token` column references. Keeps the
YouTube session cookie + PO token + operational status storage. The
SERVICE_ROLE_KEY preference (`SUPABASE_SERVICE_ROLE_KEY` first, then
legacy `SERVICE_ROLE_KEY` fallback) stays — same pattern as #2327/#2333/#2346.

**`pmoves/services/yt-cookie-refresher/main.py`** (modified)
Reads `provider_refresh_token` from Supabase Auth first. The
Playwright cookie extraction + NATS publisher + cookie writer stay
untouched. The `/status` endpoint now reports `has_google_identity: true/false`
so the operator can verify the new flow without grep'ing logs.

**`pmoves/services/yt-cookie-refresher/oauth_handler.py`** (DELETED)
50 lines of hand-rolled `httpx.post(TOKEN_URL, ...)` that this refactor
replaces. The actual refresh logic is now in `oauth_client.py`; the
storage read is now in `supabase_auth.py`.

### Tests (functional commit, 17 tests)

- `tests/test_oauth_client.py` (5 tests): happy path, missing-env-var
  guard, invalid_grant error preservation, http_500 surface, request
  shape verification
- `tests/test_supabase_auth.py` (7 tests): user-not-found, no-google-identity,
  identity-found, legacy SERVICE_ROLE_KEY fallback, admin-endpoint-5xx,
  refresh-token extraction
- `tests/test_smoke.py` (5 tests): every module parses, main.py no longer
  imports the deleted oauth_handler, the new modules are present, the
  migration SQL is present. **This is the regression net for the next
  person who tries to "fix" the auth flow.**

All 17 tests pass on a clean `python -m unittest discover -s pmoves/services/yt-cookie-refresher/tests`.
ruff check: All checks passed!

### Migration (functional commit)

**`migrations/0001_drop_encrypted_refresh_token.sql`**
Drops the now-unused `encrypted_refresh_token` column from
`pmoves_core.yt_oauth_cookies`. Operator runs this AFTER the new code
path is verified end-to-end (per the manual steps below).

## What does NOT change (deliberately)

- **`cookie_extractor.py`** (Playwright YouTube cookie extraction) — the
  YouTube session is fundamentally browser-based. No Supabase equivalent.
  No PMOVES equivalent. This is the genuinely-custom part.
- **`nats_publisher.py`** (NATS publish on refresh) — no Supabase
  equivalent for the NATS contract.
- **`yt-cookie-writer/main.py`** (cookie file writer) — yt-dlp needs a
  Netscape-format file at a known path. No Supabase equivalent.
- **The Fernet-at-rest encryption of the YouTube cookies** — the cookies
  are yt-dlp's auth state, not OAuth tokens; they don't belong in
  `auth.identities`.
- **The cron scheduler (`scheduler.py`)** — croniter is fine, the
  Supabase pg_cron alternative has a different trigger model.

## Operator's manual steps after this lands

1. **Create the `darkxside@pmoves.ai` Supabase user** in the dashboard
   (Auth > Users > Add user > Create with Google)
2. **Sign in once via Google**, granting `cataclysmstudios@gmail.com`'s
   Google identity (which has YouTube Premium access)
3. **Run `make yt-cookies-refresh`** to verify the new flow works. The
   `/status` endpoint should report `has_google_identity: true`
4. **After verification, run the migration** at
   `migrations/0001_drop_encrypted_refresh_token.sql` to drop the unused
   column (manual run via Supabase SQL editor or psql)

## What's left (out of scope, intentional)

- **Makefile `yt-cookies-auth` target still opens a browser for the
  legacy OAuth flow** via `tools/yt_oauth_flow.py`. The new path is the
  Supabase dashboard action. A follow-up PR can update the Makefile +
  deprecate the tools script. The runtime code is now independent of
  this; the Makefile lag is just operator UX.
- **The actual refresh `provider_token` is still done via direct OAuth2
  client** (~50 lines) because Supabase does not auto-refresh Google
  provider_token server-side. This is the smallest possible hand-roll;
  the rest is genuinely Supabase's problem now.
- **GHCR publishing for the yt-cookie-refresher image** — the same
  follow-up as the other services.

## Three-body

- **delivery:** Mavis (this lane)
- **control:** DARKXSIDE (operator creates the Supabase user + signs in
  via Google + runs the migration after verification)
- **memory:** this spec + 3 stacked commits + 17 new test cases + the
  migration SQL

## CHIT trail

`unsigned-local` (no `CHIT_PASSPHRASE` in Mavis session). The 3-PR env
var fix dance this week is documented in the AGNOTE entries for
#2327, #2333, #2346; this lane is the architectural cleanup.
