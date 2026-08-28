# Google OAuth Vertical — Design Spec

**Date:** 2026-06-29
**Author:** 5090-CLAUDE (Opus 4.8)
**Status:** Draft — pending operator (DARKXSIDE) review + z890 pair-review
**Lane:** `feat/google-oauth-vertical` (worktree off `main`)
**Parent vision:** Unified startup OAuth onboarding ("sign in, don't paste") across GitHub / Google / Docker / Cloudflare / Supabase, so users never re-enter keys. This spec is the **first vertical** — it proves the pattern the other providers copy. Web "Sign in with Google" (multi-tenant end-user surface) is an explicit **follow-on phase**, not this spec.

---

## 1. Problem

PMOVES has **three contradictory Google-OAuth implementations** plus a manual cookie fallback, and none of them currently work end-to-end on the 5090:

| Path | Redirect model | Token store | State |
|------|----------------|-------------|-------|
| `pmoves/tools/yt_oauth_flow.py` | **fixed** `http://localhost:8199/oauth/callback` (must be pre-registered in Google Console) | Fernet → Supabase `pmoves_core.yt_oauth_cookies` | present, untested; no creds in `env.shared` |
| `docs/.../PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md` | **loopback** installed-app (`127.0.0.1:<random>`, no URI registration) | POST → channel-monitor `:8097/api/oauth/google/token` | Draft doc, inline throwaway script |
| channel-monitor `:8097/api/oauth/google/*` | service-internal | own token table | service down (same missing creds) |
| manual `darkxside.youtube.cookies.txt` | n/a | flat Netscape file | **anonymous-only** → bot-gated |

Symptoms (diagnosed 2026-06-29): `/yt/ingest` → "Sign in to confirm you're not a bot"; "No refresh token stored"; `make yt-cookies-check` → `CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET` not configured. **Live re-verification 2026-06-29 narrowed the root cause to credentials only:** the `pmoves_core.yt_oauth_cookies` table exists, PostgREST already exposes `pmoves_core`, and all pipeline services are healthy — the prior "404 on `pmoves_core`" was historical, not current. The single blocker is the absent OAuth credential set (Google client + `VAULT_ENC_KEY` + Supabase service vars), all confirmed missing via `with-env.sh`.

**Immediate driver:** unblock YouTube ingestion to pull a transcript + frame screenshots from a design video. **Durable goal:** one canonical Google-OAuth acquire path that both consumers (YT cookies, channel-monitor) use, generalizable to other providers.

## 2. Goals / Non-goals

**Goals**
- One canonical Google token-acquire **core**, parameterized by `(scopes, account_label, user_id)`.
- **Loopback installed-app flow** — no per-machine redirect-URI registration, ever.
- One encrypted token store (Supabase, Fernet), keyed for multi-tenancy from day one.
- Both consumers route through the core; retire the divergent flows.
- A single guided **CLI walkthrough** (links to Google Console) replacing the Draft + runbook duplication.
- Fix the PostgREST `pmoves_core` 404.

**Non-goals (explicit, YAGNI)**
- Web "Sign in with Google" button / multi-tenant end-user UI → **follow-on phase** (the store is keyed so this slots in without core rework).
- GitHub / Docker / Cloudflare OAuth → later verticals (this one sets the pattern).
- CHIT-passphrase-at-startup → **z890's lane** (coordinate, do not design here).
- Changing how `env.shared` / secrets-funnel distributes the resulting tokens.

## 3. Design

### 3.1 Acquire core — `pmoves/tools/google_oauth.py`
Generalize `yt_oauth_flow.py` into a provider-agnostic-shaped Google core:

- **Flow:** build on the canonical **`google-auth-oauthlib`** library — `InstalledAppFlow.from_client_config(...).run_local_server(port=0, prompt="consent")` → loopback `127.0.0.1:<random>`. This **replaces** the existing hand-rolled `http.server` callback + manual code-exchange (`_OAuthCallbackHandler`, `_build_auth_url`, `_exchange_code`) — ~80 lines of bespoke OAuth security code deleted in favor of the audited library. Removes the fixed `:8199` redirect and its console-registration requirement. Adds `google-auth-oauthlib` as a declared dependency (currently absent).
- **Inputs (env):** `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`. **Back-compat aliases:** fall back to `CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET` so no secret churn (the YT refresh already reuses channel-monitor's client per Phase 9Q.2).
- **Encryption:** `VAULT_ENC_KEY` (Fernet) — unchanged.
- **Subcommands:** `auth` (consent + store), `status`, `refresh` (mint access token from stored refresh token), `revoke`.
- **Params:** `--scopes` (default `youtube.readonly`), `--account-label` (e.g. `darkxside`), `--user-id` (default = operator UUID from env).

`yt_oauth_flow.py` becomes a thin shim re-exporting the core (or is replaced and its Make targets re-pointed) — no behavior lost, callers unaffected.

### 3.2 Token store — Supabase, multi-tenant-keyed
- Table `pmoves_core.yt_oauth_cookies` (kept; name is incidental), columns include `user_id`, `provider`, `scope_set`, Fernet-encrypted `refresh_token`, `expires_at`, timestamps.
- **Key:** `(user_id, provider, scope_set)`. CLI writes one row under a fixed operator `user_id`; the future web surface writes rows for other users under the **same** store + RLS. **This is the multi-tenant seam** — option 2 adds a surface, not a new store.
- **Why Supabase over the CHIT bundle:** OAuth refresh tokens are per-user and rotate; the CHIT bundle (`env.cgp.json`) is for static org-wide API keys. Mixing them breaks the rotation model.

### 3.3 PostgREST exposure (the 404 fix) — **VERIFIED ALREADY SATISFIED (2026-06-29)**
Original decision was to add `pmoves_core` to `PGRST_DB_SCHEMAS`. **Verification on the live 5090 found it already exposed:** both `docker-compose.yml:660` and `docker-compose.core.yml:493` default `PGRST_DB_SCHEMAS=${SUPABASE_SCHEMA:-public,pmoves_core}`, `SUPABASE_SCHEMA` is **not** overridden, and `pmoves_core.yt_oauth_cookies` **exists** (`to_regclass` non-null). The prior-session 404 was historical (pre-migration / pre-creds), not a current blocker.

**Remaining task (verify-only, no config change):** PostgREST caches the schema at startup (container is 35h old). Confirm the running instance actually serves the table; if it 404s, trigger a schema-cache reload (`NOTIFY pgrst, 'reload schema'`) or restart PostgREST — **no env/secret change**. Also audit that exposing `pmoves_core` doesn't surface other tables without RLS.

### 3.4 Consumers route through the core
- **YT cookie chain:** `yt-cookie-refresher` calls `google_oauth refresh` for an access token → harvests cookies → `yt-cookie-writer` writes the Netscape file `pmoves-yt` already reads. (Cookie chain unchanged; only the token source is canonicalized.)
- **channel-monitor:** reads the same token row instead of running its own Google flow. (May be a follow-up commit if channel-monitor stays down; not on the ingest critical path.)

### 3.5 Consent surface — guided CLI walkthrough
Reconcile the Draft `PMOVES_YT_GOOGLE_OAUTH_DESKTOP_SETUP.md` + `YT_COOKIES_RUNBOOK.md` into **one** canonical operator walkthrough that:
1. Links to Google Console steps: enable **YouTube Data API v3** → create **Desktop** OAuth client → copy client ID/secret. (Desktop client = loopback; no redirect URI to register.)
2. Operator pushes `GOOGLE_OAUTH_CLIENT_ID/SECRET` + `VAULT_ENC_KEY` + Supabase `SERVICE_ROLE_KEY`/`SUPABASE_URL` through the **secrets-funnel** (never chat).
3. `make -C pmoves yt-cookies-check` confirms presence.
4. `make -C pmoves yt-cookies-bootstrap` → consent (operator clicks **Allow**) → store → first cookie harvest.
5. `make -C pmoves yt-cookies-status` verifies token + authenticated cookie file.

## 4. Data flow

```
operator → Google Console (one-time: enable API + Desktop client)
         → secrets-funnel: GOOGLE_OAUTH_CLIENT_ID/SECRET, VAULT_ENC_KEY, SUPABASE_*  → env.shared
google_oauth.py auth → loopback consent (Allow) → refresh_token
         → Fernet(VAULT_ENC_KEY) → Supabase pmoves_core.yt_oauth_cookies (user_id, provider, scope_set)
yt-cookie-refresher → google_oauth.py refresh → access_token → Playwright harvest
         → NATS ingest.cookies.refreshed.v1 → yt-cookie-writer → darkxside.youtube.cookies.txt (AUTH cookies)
pmoves-yt /yt/ingest → yt-dlp --cookies <file> → MinIO assets/yt/{vid}/raw.mp4 → ffmpeg-whisper transcribe
```

## 5. Error handling
- **Missing creds:** `yt-cookies-check` fails fast with the funnel command to run (no secret values printed).
- **`invalid_grant` / expired refresh:** `revoke` → re-`auth`; documented in the walkthrough.
- **PostgREST 404 after fix:** surfaces as a clear "schema not exposed — restart PostgREST" message, not a silent empty result.
- **Consent without refresh token:** Google only issues a refresh token on first authorization of a scope+client; walkthrough instructs revoke-then-retry at `myaccount.google.com/permissions`.
- No secret values in logs or error text.

## 6. Testing
- Unit: `google_oauth.py` token encrypt/decrypt round-trip (Fernet), store upsert keying, refresh-from-stored, alias env fallback — all without real Google calls (mock the flow).
- Integration (operator-gated, can't be CI-automated): full `yt-cookies-bootstrap` → `status` green → `/yt/ingest` on the design video returns transcript + frames.
- Regression: existing `yt_oauth_flow.py` callers/Make targets still resolve after the shim.

## 7. Coordination
- **z890** owns the broader secrets/OAuth/CHIT-passphrase infra history → **pair-review required** before merge; CHIT-passphrase-at-startup stays their lane.
- **CLAIM** the lane in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` before implementation (collision-avoidance protocol).
- Secrets strictly through the funnel pipeline; `env.tier-*`/`env.shared` zero-access is deliberate.

## 8. Operator critical path (parallelizable now)
1. Google Console: enable YouTube Data API v3 + create a **Desktop** OAuth client (or reuse the existing channel-monitor client).
2. Funnel: `GOOGLE_OAUTH_CLIENT_ID/SECRET` (= channel-monitor's), `VAULT_ENC_KEY` (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), Supabase `SERVICE_ROLE_KEY`/`SUPABASE_URL`.
3. After implementation lands: `make -C pmoves yt-cookies-bootstrap` → click **Allow**.

## 9. Follow-on phases (out of scope here)
- **P2 — Web "Sign in with Google"** (multi-tenant): per-user rows + RLS + Supabase auth join; reuses §3.1 core + §3.2 store unchanged.
- **P3 — GitHub / Docker / Cloudflare verticals:** copy the loopback-acquire + encrypted-store pattern.
- **P4 — Startup onboarding wizard + CHIT passphrase bootstrap** (z890-led): the unified "authorize once at startup" surface.
