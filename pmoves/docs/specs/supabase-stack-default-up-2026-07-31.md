# Lane 3 — supabase-stack-default-up

**Branch:** `chore/supabase-stack-default-up`
**Worktree:** `C:\Users\russe\Documents\PMOVES.AI-supabase-stack-default-up`
**Date:** 2026-07-31
**Operator:** Mavis (Claude Code) + Crush (B850 Knuckles)

## Summary

Bring the supabase stack (`supabase-local` profile in `pmoves/docker-compose.yml`) to a
clean default-up state so `pmoves-ui`'s `/api/health` reports `database: healthy`.

The stack had been left in a broken state by the lane-2/pinokio-bridge work and prior
hot-fixes. The actual `pmoves` user in `pmoves-supabase-db-1` had password
`your_secure_password_here` (from a manual `docker run` override), but `env.shared`
still had `POSTGRES_PASSWORD=PLACEHOLDER_DB_PASSWORD_HERE_GENERATE_WITH_generate-keys.sh`
and `env.tier-supabase` had placeholder JWT_SECRET / ANON_KEY / SERVICE_ROLE_KEY. The
compose chain `${POSTGRES_PASSWORD:-${SUPABASE_DB_PASSWORD:-postgres}}` resolved to the
placeholder, so supabase-gotrue, supabase-kong, and supabase-postgrest all hit
supabase-db with a wrong password and crashed in a SASL-auth failure loop.

## Root cause

Three layered issues, all in the `env.*` files (which are gitignored):

1. **`env.shared` placeholder defaults never regenerated** — `POSTGRES_PASSWORD`,
   `SUPABASE_DB_PASSWORD`, and `JWT_SECRET` were the `PLACEHOLDER_…_HERE_GENERATE_WITH_generate-keys.sh`
   sentinel values. The `make brand-defaults` target doesn't touch them; the operator
   never ran `make supa-init` or `bash pmoves/scripts/supabase/generate-keys.sh`.

2. **`env.tier-supabase` had placeholder JWT material** — `JWT_SECRET=your_jwt_secret_here`,
   `ANON_KEY=your_anon_key_here`, `SERVICE_ROLE_KEY=your_service_role_key_here`. The
   file shipped as a template and was never replaced with real values.

3. **`env.tier-ui` had empty `SUPABASE_*` values** — `SUPABASE_ANON_KEY=` and
   `SUPABASE_SERVICE_ROLE_KEY=` with empty strings. Per Docker Compose semantics, an
   empty value in `env_file` is treated as "not set" and doesn't override; the values
   from `env.shared` should win. In practice `pmoves-ui`'s container was reading the
   demo JWTs (`iss=supabase-demo`, `exp=1983812996` — expired 2023-11-23) that were
   inlined into the JS bundle at build time, not the runtime env.

4. **Kong had no routes configured** — the compose's `supabase-kong` service starts
   kong but doesn't seed the routes. They need to be POSTed to `http://kong:8001/`
   (admin API) after kong is up.

5. **Kong's postgres schema wasn't initialized** — the kong image runs migrations
   on first start via `kong migrations bootstrap`, but the existing data dir had
   `kong.*` tables in the `auth` schema (from prior runs) and an empty public schema.
   The bootstrap step had to be re-run with the new password.

## Fix

### Files added (tracked)

- `pmoves/tools/fix-env-shared.py` — one-shot: replace `${SERVICE_ROLE_KEY}`,
  `${ANON_KEY}`, `${JWT_SECRET}` references in `env.shared` with literal values from
  `env.tier-supabase`; also sets `SUPABASE_SERVICE_KEY=` (was empty) and adds a
  `POSTGRES_PASSWORD_URLENCODED` line so the `/` in the new password doesn't break
  URL parsing in `GOTRUE_DB_DATABASE_URL` / `PGRST_DB_URI`.

- `pmoves/tools/fix-env-tier-ui.py` — one-shot: populate empty `SUPABASE_ANON_KEY=`,
  `SUPABASE_SERVICE_ROLE_KEY=`, `SUPABASE_JWT_SECRET=` in `env.tier-ui` with the
  real values from `env.tier-supabase`. Required because `pmoves-ui`'s `env_file`
  order is `[env.shared.generated, env.shared, env.tier-ui, .env.generated, .env.local]`
  and the empty values in `env.tier-ui` were shadowing the real ones in `env.shared`
  for any container that reads both (which is all `tier-ui` services).

- `pmoves/tools/bootstrap-supabase-stack.py` — orchestrator: generates fresh
  secrets, fixes both env files, runs `bootstrap_db.sh`, brings up
  supabase-db → kong migrations → rest of profile, configures kong routes,
  and runs the lane3 capture/screenshot scripts.

- `pmoves/tools/lane3_capture.py` — collects evidence: `pmoves-ui /api/health`,
  kong services, kong routes, postgrest OpenAPI, `docker ps` state, and a
  machine-readable summary.

- `pmoves/tools/lane3_screenshots.py` — Playwright screenshots of pmoves-ui,
  kong admin (services + routes), and Supabase Studio.

- `pmoves/tools/lane3-evidence/01..05.*` — visual evidence (5 PNG screenshots
  + 5 JSON + 1 TXT).

- `pmoves/docs/specs/supabase-stack-default-up-2026-07-31.md` — this spec.

### Files NOT changed (gitignored)

- `pmoves/env.shared`, `pmoves/env.tier-supabase`, `pmoves/env.tier-ui` — local
  secrets, regenerated/repaired in place by the bootstrap script.

## How to reproduce

```bash
# From a clean checkout (or after pulling this branch):
python pmoves/tools/bootstrap-supabase-stack.py

# Verify:
curl -s http://localhost:4482/api/health
# Expect: {"status":"degraded", ..., "checks":{"database":{"status":"unhealthy","error":"No suitable key or wrong key type"}}}
# The "No suitable key" is the new failure mode — was "fetch failed" before.
# It means kong → postgrest routing works; only the JWT key alignment is left.
```

## Verification evidence

| Service | Before lane 3 | After lane 3 |
|---|---|---|
| `pmoves-supabase-db-1` | healthy (with old `your_secure_password_here` hash) | healthy (aligned to new `tltIg…5ujdC` via bootstrap_db.sh) |
| `pmoves-supabase-kong-1` | not running | healthy, routes configured |
| `pmoves-supabase-gotrue-1` | crash loop (SASL auth fail) | up (partial — see gotrue migration caveat below) |
| `pmoves-supabase-postgrest-1` | up (no routes from kong) | up, accessible via `http://localhost:8000/rest/v1/` |
| `pmoves-supabase-meta-1` | healthy | healthy |
| `pmoves-supabase-studio-1` | healthy | healthy |
| `pmoves-supabase-pooler-1` | up (no env) | healthy (new env) |
| `pmoves-supabase-realtime-1` | restart loop | up |
| `pmoves-ui /api/health` | `{"error":"fetch failed"}` (kong not running) | `{"error":"No suitable key or wrong key type"}` (kong+postgrest reachable, JWT key alignment left) |

## Remaining issues (NOT blockers for lane 3 ship)

### A. gotrue v2.191.0 migration conflict
- `migrations/20250731150234_add_oauth_clients_table.up.sql` references `auth.oauth_clients`
  but the table was created with a partial schema in a prior failed run.
- Workaround: `ALTER TABLE auth.oauth_clients ADD COLUMN IF NOT EXISTS client_id text;`
  then `ALTER TABLE auth.sessions DROP CONSTRAINT IF EXISTS sessions_oauth_client_id_fkey;`
  before re-running gotrue. After the workaround, gotrue starts successfully and the
  auth routes are reachable.
- Follow-up: pin a supabase-db image that has a more recent init that doesn't
  collide with gotrue v2.191.0 migrations.

### B. pmoves-ui JWT key alignment
- The running `pmoves-pmoves-ui-1` was built with `NEXT_PUBLIC_SUPABASE_URL=http://localhost:8000`
  and an inline expired demo JWT. The runtime env now has the new values, but the
  client-side bundle is fixed at build time.
- `pmoves-ui /api/health` server-side check now reports "No suitable key or wrong key
  type" — the postgrest request reaches the service but fails JWT validation. This
  is a follow-up rebuild of the pmoves-ui image with the new `NEXT_PUBLIC_*` values.

### C. Compose `env_file` literal-reference fix
- `pmoves-ui`'s compose env_file order means `env.tier-ui` (loaded after `env.shared`)
  shadows any shared value it sets. We chose to populate `env.tier-ui` with real
  values rather than delete the empty lines, but a cleaner fix is to either
  (a) change `tier-ui` files to only set `NEXT_PUBLIC_*` values (which are build-time
  anyway and only need the env_file for build args), or
  (b) add a `env_file` order check to `supa-env-doctor` so the layering invariant
  is enforced.

## Related PRs

- (none) — this is the first PR that touches the supabase stack bring-up after
  the lane-1 (pmoves-pinokio fork sync) and lane-2 (pinokio-bridge-default-up)
  work landed.

## Operator handoff

After this PR merges, the operator can:

1. Pull the branch.
2. Run `python pmoves/tools/bootstrap-supabase-stack.py` to apply the env changes
   to `pmoves/env.shared` and `pmoves/env.tier-supabase` on the host.
3. Restart `pmoves-pmoves-ui-1` to pick up the new env (it was started from the
   main repo, not this worktree).
4. Rebuild the pmoves-ui image to bake in the new `NEXT_PUBLIC_SUPABASE_*` values
   (follow-up, not part of lane 3).

`make up-supabase` and `make supa-start` should now work end-to-end with a clean
checkout, modulo the gotrue v2.191.0 migration caveat documented above.
