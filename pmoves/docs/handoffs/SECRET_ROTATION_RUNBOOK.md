# Secret Rotation Runbook — `make secrets-rotate`

`make -C pmoves secrets-rotate KEY=<env.shared key> [VALUE=<minted>] [LEN=48]` is the Known Road for rotating a single secret. It surgically replaces one `KEY=` line in `env.shared` (generates a `random_urlsafe` value when `VALUE` is omitted; refuses multi-line values), then runs `chit-export` (encode → CGP bundle) + `secrets-funnel` (propagate to tier files). It does **not** auto-restart services — it prints the remaining steps.

Rotation makes the git-history value **inert** (that's the fix); history-purge is optional. `bootstrap_env.py` is chitBypass-allowed, so this runs as an elevated agent command — no hand-editing of `env.shared`.

> Generated values use `token_urlsafe` → URL-safe Base64 charset (alphanumerics plus `-` and `_`; **no `/` or `+`**), avoiding connection-string URL-encode fragility.

---

## 1. Render webhook shared secret (internal HMAC)
```bash
make -C pmoves secrets-rotate KEY=RENDER_WEBHOOK_SHARED_SECRET LEN=32
make -C pmoves up-workers && make -C pmoves up        # restart render-webhook + UI TOGETHER
```
⚠️ Verifier **fails open if blank** (`render-webhook/webhook.py:62`) — the surgical replace never blanks it, but restart both sides close in time. Also update the GH Actions secret `RENDER_WEBHOOK_SHARED_SECRET` (`sync-secrets-local.yml`).

## 2. Postgres / Supabase DB password
```bash
make -C pmoves secrets-rotate KEY=SUPABASE_DB_PASSWORD LEN=48
make -C pmoves supa-bootstrap-db     # ALTER postgres/supabase_admin/authenticator roles to new value
make -C pmoves supa-restart          # bounce all DB consumers with fresh env
make -C pmoves supa-status && make -C pmoves supa-health
```
Then push the new value to GH secret `SERVICE_PASSWORD_POSTGRES` + docker secret `pmoves_service_password_postgres`. (Per the operator steer, Supabase owns its DB credential; `supa-bootstrap-db` is the Supabase-native ALTER path.)

## 3. Jellyfin API key (external — minted via `/Auth/Keys`, no OAuth)
Mint first (scripted create→verify→revoke, zero-downtime; needs one admin token):
```bash
POST /Auth/Keys?app=jellyfin-bridge-<ts>   ;  GET /Auth/Keys → new key value
make -C pmoves secrets-rotate KEY=JELLYFIN_API_KEY VALUE=<new-key>
make -C pmoves up-<media/jellyfin-bridge>          # restart consumers (+ jellyfin-ai)
# verify jellyfin-bridge /System/Info → 200, THEN: DELETE /Auth/Keys/{old_key}
```
Follow-up: `jellyfin-bridge` uses deprecated `X-Emby-Token`/`api_key` — 10.11 added `EnableLegacyAuthorization` (default on), removal planned for 12.0. Migrate to `Authorization: MediaBrowser Token="..."`.

---

## Jellyfin fork staleness (separate from the key)
`PMOVES-Jellyfin` is 1247 behind upstream because it's in **none** of the sync lists and `fork-sync.yml` isn't on `main` (worktree-only). Fix: land `fork-sync.yml` on main → add `PMOVES-Jellyfin` to FORKS + `_app-token repositories:` + `TRACKED_SUBMODULES` → **manual CRITICAL overlay-merge** (1247 > 1000 guard; preserve the 6 hardening commits) → operator enables the repo Security policy. The App provides auth, not discovery. See `project_fork_sync_coverage_gap` memory.
