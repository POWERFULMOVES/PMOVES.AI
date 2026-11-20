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
Auth scheme (verified vs official OpenAPI): the declared `CustomAuthentication` securityScheme is the **`X-Emby-Authorization`** header; **`Authorization: MediaBrowser Client="…" … Token="…"`** is the recommended standard form carrying the same token scheme. `/Auth/Keys` is `RequiresElevation` (admin token). The deprecated token-only forms — `X-Emby-Token` header + `api_key` query param — are removal-bound in 12.0 (10.11 added `EnableLegacyAuthorization`, default on). `jellyfin-bridge` now builds the branded `Authorization: MediaBrowser` header (Client/Device = `JELLYFIN_CLIENT_NAME`, default `PMOVES.AI`) and no longer uses `X-Emby-Token`/`api_key`.

## 4. Leaked generated env file (a committed `env.tier-*` carrying live secrets)

A *generated* env file (`env.shared`, `env.tier-*`, `.env.generated`) that is **git-tracked** has been shipping live secrets into history. These files are gitignored + local-only by design, but git keeps tracking files added *before* an ignore rule — which is how `pmoves/env.tier-media` leaked a live `MINIO_SECRET_KEY` + a real `SUPABASE_SERVICE_ROLE_KEY` (closed #1988, untracked in #1992). `secrets_hardening_audit.py` check #9 now fails CI on any such tracked file, so this is caught automatically going forward.

Remediation is **two independent actions — untrack, then rotate.** Untracking stops future leaks; only rotation makes the already-exposed history value inert.

**1. Untrack** (operator-only — these paths are damage-control *zero-access*, so an agent cannot run this; run it yourself via `!`):
```bash
git rm --cached pmoves/env.tier-<tier>     # stays on disk (now-effective gitignore); the .example template stays tracked
git commit -m "chore(secrets): untrack generated <tier>-tier env file (already gitignored)"
```

**2. Rotate every secret the file exposed.** Two gotchas make these NOT a plain `secrets-rotate`:

- **MinIO** — `MINIO_SECRET_KEY`, `MINIO_PASSWORD`, and `MINIO_ROOT_PASSWORD` are three aliases of one canonical value (seeded together by `brand_defaults._ensure_minio_credentials`); after rotating they must all still match, so rotate through the pipeline and confirm with `secrets-funnel`, then `make -C pmoves up-media` to restart MinIO + S3 consumers. Push the new value to the GH/Docker secret copies.
- **Supabase service-role key** — `SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_SERVICE_KEY` alias `SERVICE_ROLE_KEY`, a **JWT signed by `JWT_SECRET`**. Three tools, by role — no single one does it all:
  - **Mint:** `secrets-rotate` (random values only) and `brand_defaults` (which *aliases* SERVICE_ROLE_KEY→SUPABASE_SERVICE_KEY, it does not mint) **cannot** reissue a JWT. Re-sign it with `pmoves/scripts/supabase/generate-keys.sh` (uses `JWT_SECRET`; rotating `JWT_SECRET` itself does a full anon+service reissue — heavier, confirm blast radius). See `.claude/context/credentials-workflow.md`.
  - **Propagate:** `make -C pmoves chit-export && make -C pmoves secrets-funnel` — the funnel runs `brand_defaults`, which re-aliases the new key into `SUPABASE_SERVICE_KEY`.
  - **Apply/verify DB side:** use the **`supabase-db` Postgres MCP** to confirm roles + RLS still validate under the reissued key, then `make -C pmoves supa-restart`. Update the off-box GH/Docker `SERVICE_ROLE_KEY` copies.

---

## 5. Stale local value: which road?

`secrets-local-hydrate` overlays `local.env` only onto keys that are **empty or placeholder** in `env.shared`. If a key already holds a real but stale value, the plain funnel leaves it as it is. Bare `FORCE=1` overwrites **every** key that `local.env` carries, and that includes the node-specific `SUPABASE_*` keys pairing this node's Kong with cipher. Pick the road by where the new value comes from:

| Situation | Road |
|---|---|
| **You mint the new value** on this node | `make -C pmoves secrets-rotate KEY=<K> [VALUE=...]`. It is surgical, works on a single line, and **refuses multi-line values** (see GH_APP_SEC below for PEMs). |
| **The GitHub secret is already rotated**, and you need to replace **one** stale local key | First refresh `local.env` from the producer bundle. On a runner node, re-run `sync-secrets-local.yml`. On a runnerless node, run `make -C pmoves secrets-pull`, then `PYTHONPATH=. python pmoves/tools/emit_local_env.py --cgp <bundle>` (this does not touch `env.shared`). Then run `make -C pmoves secrets-local-hydrate KEYS=<K> FORCE=1` (new in [#3496](https://github.com/POWERFULMOVES/PMOVES.AI/pull/3496)) followed by `make -C pmoves secrets-funnel`. Use `KEYS=A,B` for several keys. Add `--dry-run` through the tool directly to list the key **names** that would change. **Never run bare `FORCE=1` on a node whose own Supabase is live**: it overwrites the node-specific `SUPABASE_*` keys. |
| **Runnerless consumer, whole-bundle refresh** (the node has no node-specific keys of its own to protect) | `make -C pmoves secrets-funnel-from-prod`. It pulls the bundle, refreshes `local.env`, and force-hydrates **all** keys, then re-pins. |

Under `--keys`, keys in `secrets_cleared.yaml` and registry-PINNED keys are still never overlaid, and the tool names them on stderr. It exits `1` only when **none** of the requested keys has a real value in `local.env`.

**GitHub holds duplicate copies of some keys**, once in the repository scope and once in `env:Prod`. Rotate **both**. A workflow that reads the copy you skipped keeps shipping the stale value, and the next funnel restores it. Scopes and caps are covered in [`../security/GITHUB_SECRETS_GUIDE.md`](../security/GITHUB_SECRETS_GUIDE.md) § "Limits and scopes".

### GH_APP_SEC (the PMOVES.AI GitHub App private key)

- **It is a PEM private key**, not a 40-hex string. Store it in `env.shared` as **one line with `\n`-escaped newlines**. A raw multi-line value breaks Docker Compose env-file parsing, and `secrets-rotate` and the hydrate write path both refuse or skip values containing real newlines (the hydrate path warns `Skipping malformed secret` on stderr).
- `make -C pmoves env-shared-repair` collapses raw multi-line PEM values that are already in `env.shared` into the escaped single-line form.
- **Validate before you funnel.** Sign an App JWT with the key and call `GET https://api.github.com/app`. A good key returns `200` with `"slug": "pmoves-ai"`. `make -C pmoves gh-app-token` also exercises the key end to end.
- **Failure signature:** a **40-hex** value in `GH_APP_SEC`. That is the shape of a client secret, not a PEM. It was the stale local value from 2026-11-09 to 2026-11-19 (SPARK handoff, 2026-11-19), and every App-token mint failed while the key was "present". A presence check passes it. Check the shape: it must begin `-----BEGIN` and contain `PRIVATE KEY`.

---

## Jellyfin fork staleness (separate from the key)
`PMOVES-Jellyfin` drifted because it was in **none** of the `fork-sync.yml` sync lists — it was tracked only for GHCR builds + secrets, so the GitHub-App automation never audited it. `fork-sync.yml` is now on `main`; #1998 wires the fork in (app-token `repositories:` + FORKS, pinned to the hardened branch `PMOVES.AI-Edition-Hardened`). As of 2026-07-07 it is **101 behind / 8 ahead** (an earlier `sync/upstream-2026-06-23-merge` caught it up — the "1247 behind" figure is obsolete), which is **within the auto-merge guards** (`ahead_max=20`, `behind_max=1000`). So once #1998 lands, the automation produces a normal sync PR — **no manual CRITICAL overlay-merge needed**; the 8 hardening commits are preserved by the local-git merge. Merge the resulting fork PR with a **merge commit, never squash**. Operator still enables the repo Security policy. See `project_fork_sync_coverage_gap` memory.
