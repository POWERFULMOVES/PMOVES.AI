# PMOVES.YT — Google OAuth 2.0 Desktop Client Setup

_Status: Draft • Last updated: 2025-11-08_

This guide walks through provisioning a Google OAuth 2.0 Desktop Client so PMOVES.YT can acquire refresh tokens for the Channel Monitor when running on developer workstations.

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
   - Add scopes: `https://www.googleapis.com/auth/youtube.readonly`.
   - Add test users (the Google accounts you will sign in with during development).
   - Publish the consent screen (test mode is sufficient for development).

## 3. Create an OAuth Desktop Client
1. Go to **APIs & Services → Credentials**.
2. Click **Create credentials → OAuth client ID**.
3. Select **Desktop app** and choose a descriptive name (e.g., `PMOVES.YT Local Dev`).
4. Download the credentials JSON (`client_secret_*.json`). Store it in a safe location outside of version control.

> **Note:** Desktop clients do not require an explicit redirect URI. Google issues a loopback callback automatically (`http://127.0.0.1:<random-port>`). We will use the installed app flow to capture the refresh token on the command line.

## 4. Generate a Refresh Token Locally
Use the following helper script to walk through the installed-app OAuth flow and capture the refresh token. It depends on `google-auth-oauthlib` (already bundled in the PMOVES virtualenv).

```python
#!/usr/bin/env python
"""Exchange a Desktop OAuth client secret for a refresh token."""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRET_PATH = Path("/path/to/client_secret.json")  # update this path
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_SECRET_PATH,
    scopes=SCOPES,
)
credentials = flow.run_local_server(port=0, prompt="consent")

print("Access token:", credentials.token)
print("Refresh token:", credentials.refresh_token)
print("Expires in:", credentials.expiry)
```

1. Save the snippet as `scripts/pmoves_youtube_oauth.py` (outside git) and run it inside the PMOVES virtualenv (`source .venv/bin/activate && python scripts/pmoves_youtube_oauth.py`).
2. Sign in with a test-user Google account when prompted.
3. Copy the `refresh_token`, `token` (access token), and expiry timestamp for later.

## 5. Populate PMOVES Environment Variables
Update `pmoves/env.shared` (or `.env.local`) with the Desktop client credentials so the Channel Monitor can authenticate future refreshes:

```
CHANNEL_MONITOR_GOOGLE_CLIENT_ID=<client_id_from_json>
CHANNEL_MONITOR_GOOGLE_CLIENT_SECRET=<client_secret_from_json>
CHANNEL_MONITOR_GOOGLE_REDIRECT_URI=http://localhost:8097/api/oauth/google/callback
CHANNEL_MONITOR_GOOGLE_SCOPES=https://www.googleapis.com/auth/youtube.readonly
```

Run `make env-setup` afterwards to sync the generated `.env` files.

## 6. Register the Refresh Token with Channel Monitor
Call the Channel Monitor API to persist the refresh token in Supabase:

```bash
curl -X POST http://localhost:8097/api/oauth/google/token \
  -H 'Content-Type: application/json' \
  -d '{
        "user_id": "<supabase_user_uuid>",
        "provider": "youtube",
        "refresh_token": "<refresh_token>",
        "scope": ["https://www.googleapis.com/auth/youtube.readonly"],
        "expires_in": 3600
      }'
```

You can find your Supabase user ID in the `auth.users` table or via the PMOVES UI boot user credentials.

## 7. Add a User Source (Optional)
With the token stored, you can register a dynamic source pointing at a playlist, channel ID, or handle:

```bash
curl -X POST http://localhost:8097/api/monitor/user-source \
  -H 'Content-Type: application/json' \
  -d '{
        "user_id": "<supabase_user_uuid>",
        "provider": "youtube",
        "source_type": "channel",
        "source_identifier": "@pmovesai",  // handles supported
        "namespace": "pmoves",
        "auto_process": true,
        "token_id": "<token_uuid_from_previous_step>"
      }'
```

Run `curl -X POST http://localhost:8097/api/monitor/check-now` to trigger an immediate ingest and confirm rows land in `pmoves.channel_monitoring`.

## 8. Troubleshooting
- **`invalid_client`**: double-check that `CHANNEL_MONITOR_GOOGLE_CLIENT_ID` / `SECRET` match the Desktop client JSON.
- **`redirect_uri_mismatch`**: the helper script uses the loopback installed-app redirect; leave `CHANNEL_MONITOR_GOOGLE_REDIRECT_URI` as-is for the Channel Monitor service.
- **`missing refresh token`**: ensure the consent screen scopes include `youtube.readonly` and you click "Allow" during the flow. Google only issues a refresh token the first time you authorize a scope + client combination; revoke access from https://myaccount.google.com/permissions if you need to re-run the flow.

## 9. Next Steps
- Add the generated credentials to your personal password manager; keep the JSON out of the repository.
- Update the Channel Monitor documentation (`CHANNEL_MONITOR_IMPLEMENTATION.md`) once the flow is verified end-to-end.
- Capture smoke evidence (`make channel-monitor-smoke`) and link it in the PR/issue tracker.
