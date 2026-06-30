# PMOVES.YT — Google OAuth 2.0 Desktop Client Setup

_Status: Canonical • Last updated: 2026-06-29_

This is the single canonical walkthrough for provisioning Google OAuth so PMOVES.YT can acquire and refresh a YouTube token (used by the cookie-refresher and Channel Monitor). The acquire flow uses `google-auth-oauthlib`'s **loopback installed-app flow** on an ephemeral `127.0.0.1` port — a **Desktop** OAuth client, with **nothing to register** (no redirect URI).

## 1. Prerequisites
- Google Cloud project (create one at https://console.cloud.google.com if you do not already have a PMOVES sandbox).
- Project Owner/Editor rights to manage OAuth consent and APIs.
- Local PMOVES compose stack running (at minimum: `make -C pmoves up channel-monitor up-yt`).

## 2. Enable APIs & Consent Screen
1. Open the Google Cloud Console for your project.
2. Navigate to **APIs & Services → Library** and enable **YouTube Data API v3**.
3. Under **OAuth consent screen**, configure the application:
   - User type: **External** (unless you are using a Google Workspace org).
   - App name, support email, developer contact information.
   - Add scope: `https://www.googleapis.com/auth/youtube.readonly`.
   - Add test users (the Google accounts you will sign in with — the **darkxside** YouTube account).
   - Publish the consent screen (test mode is sufficient for development).

## 3. Create an OAuth Desktop Client

> **Reuse first:** PMOVES already has a **Desktop** Google client — the one the `google-workspace` MCP skill uses, stored as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (GitHub secrets + `env.shared`). The acquire flow accepts it directly (no new client needed). To reuse it, just confirm **YouTube Data API v3** is enabled on *that* client's project and `youtube.readonly` is on its consent screen (§2). Only create a new client below if you want a dedicated YT one.

1. Go to **APIs & Services → Credentials**.
2. Click **Create credentials → OAuth client ID**.
3. Select **Desktop app** and choose a descriptive name (e.g., `PMOVES.YT Desktop`).
4. Note the client ID and secret (you will push them through the secrets-funnel, not download the JSON into the repo).

> **Why Desktop (not Web):** Desktop clients accept any `http://127.0.0.1:<port>` loopback redirect with **no redirect-URI registration**. The acquire flow binds an ephemeral port (`run_local_server(port=0)`), so there is no fixed `:8199` redirect to register and onboarding a new machine needs no console round-trip. A **Web** client would reject the loopback redirect — use Desktop.

## 4. Acquire the Refresh Token (one command)
Once the credentials are in `env.shared` (§5), run the one-click bootstrap:

```bash
make -C pmoves yt-cookies-bootstrap
```

It runs `tools/yt_oauth_flow.py auth`, which uses `google-auth-oauthlib`'s loopback flow: a browser tab opens for Google consent on an ephemeral `127.0.0.1` port (click **Allow**), the library exchanges the code, and the first cookie harvest is triggered. No throwaway script, no manual redirect handling.

Other subcommands:
- `make -C pmoves yt-cookies-status` — show stored token + cookie state.
- `make -C pmoves yt-cookies-revoke` — revoke + delete the stored row (forces re-consent).

## 5. Populate PMOVES Environment Variables (via the secrets-funnel)
Set these through the secrets-funnel pipeline (they land in `pmoves/env.shared` — never hand-edit secrets in a chat or paste them into terminals):

```
GOOGLE_OAUTH_CLIENT_ID=<desktop_client_id>.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-<desktop_client_secret>
VAULT_ENC_KEY=<fernet key>          # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SERVICE_ROLE_KEY=<supabase service-role key>
SUPABASE_URL=http://supabase-kong:8000
```

> **Client id/secret resolution order:** `GOOGLE_OAUTH_CLIENT_ID/SECRET` (dedicated) → `GOOGLE_CLIENT_ID/SECRET` (the shared google-workspace Desktop client — already in GitHub secrets) → `CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET` (legacy). If you reuse the workspace client you only need `VAULT_ENC_KEY`, `SERVICE_ROLE_KEY`, and `SUPABASE_URL` newly funneled. Verify with `make -C pmoves yt-cookies-check`.

## 6. Token Storage
The CLI stores the token **directly** in `pmoves_core.yt_oauth_cookies` (Fernet-encrypted with `VAULT_ENC_KEY`), keyed by `user_id`. No manual `curl` to channel-monitor is needed — the cookie-refresher and channel-monitor both read this row.

## 7. Add a User Source (Optional)
With the token stored, you can register a dynamic source pointing at a playlist, channel ID, or handle via the Channel Monitor API:

```bash
curl -X POST http://localhost:8097/api/monitor/user-source \
  -H 'Content-Type: application/json' \
  -d '{
        "user_id": "<supabase_user_uuid>",
        "provider": "youtube",
        "source_type": "channel",
        "source_identifier": "@pmovesai",
        "namespace": "pmoves",
        "auto_process": true
      }'
```

Run `curl -X POST http://localhost:8097/api/monitor/check-now` to trigger an immediate ingest.

## 8. Troubleshooting
- **`invalid_client`**: the client id/secret don't match the Desktop client. Re-check the funnel values via `make -C pmoves yt-cookies-check`.
- **`redirect_uri_mismatch`**: Desktop clients accept any `127.0.0.1` loopback port — this error means the client is a **Web** type, not **Desktop**. Create a Desktop client (§3).
- **`missing refresh token`**: Google only issues a refresh token the first time you authorize a scope + client combination. If none is returned, revoke access at https://myaccount.google.com/permissions and re-run `make -C pmoves yt-cookies-auth`.
- **`No OAuth credentials stored` is fine on first run** (a clean empty read). A PostgREST **404** instead means the schema cache is stale: `docker exec pmoves-supabase-db-1 psql -U postgres -d postgres -c "NOTIFY pgrst, 'reload schema';"`.

## 9. Next Steps
- Capture smoke evidence (`make -C pmoves yt-cookies-status` + a `/yt/ingest` round-trip) and link it in the PR/issue tracker.
- This Google vertical is the reference pattern for the broader "sign in, don't paste" onboarding (GitHub / Docker / Cloudflare verticals + web sign-in are follow-on phases).
