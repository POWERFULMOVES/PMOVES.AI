# Handoff — GoTrue auth-schema repair (blocks SSO login e2e)

**Date:** 2026-07-25 · **Node:** Z890 · **Needs:** DB superuser access

## Summary
The PMOVES SSO gateway (PR #2, `feat/sso-gateway-apps`) is verified correct **up to the GoTrue boundary**. The full `login → 4-app` e2e is blocked by a **pre-existing broken GoTrue/auth-schema state on this node**, unrelated to the SSO code. GoTrue is currently **stable (healthy, non-crashing)** but cannot authenticate anyone.

## Root cause (two compounding issues)
1. **Wrong DB role + empty search_path.** GoTrue's `GOTRUE_DB_DATABASE_URL` (`docker-compose.yml:596`) connects as `${POSTGRES_USER}` = **`pmoves`** (a superuser role whose `search_path` is empty), instead of the conventional **`supabase_auth_admin`** (which ships with `search_path=auth`). So GoTrue's unqualified `users`/`identities` queries resolve in `public`, find nothing, and 500 (`relation "..." does not exist`, 42P01). The tables DO exist in `pmoves.auth`.
2. **Forked/mismatched auth migration set.** When `search_path=auth` is injected, GoTrue proceeds to run migrations and **crash-loops** on `add_oauth_clients_table` (`column "client_id" does not exist`, 42703) — the schema was seeded with a **non-stock** table set (`custom_oauth_providers`, `oauth_authorizations`, `oauth_client_states`) that conflicts with this GoTrue image's expected migrations.

Also relevant: `supabase_auth_admin`'s password does **not** equal `POSTGRES_PASSWORD` on this node (repointing GoTrue to it fails SASL auth, 28P01) — so the role repoint additionally needs that password reset.

## Repair (superuser required — agent is zero-access to DB superuser creds)
Do NOT `DROP SCHEMA auth CASCADE` — it would drop `auth.uid()`/`auth.role()` and cascade-drop RLS policies across every table. Instead, reconcile GoTrue's migration state to this image:
1. As a DB superuser (`pmoves` or `supabase_admin`), inspect `auth.schema_migrations` vs the GoTrue image's `migrations/` set; drop/reconcile the conflicting non-stock oauth tables so `add_oauth_clients_table` (and any following) apply cleanly — or align the GoTrue image version to the seeded schema.
2. Move GoTrue to least privilege: `ALTER ROLE supabase_auth_admin WITH PASSWORD '<POSTGRES_PASSWORD>';` then set `GOTRUE_DB_DATABASE_URL` role → `supabase_auth_admin` (it already has `search_path=auth`), and recreate GoTrue. This fixes BOTH issues (search_path + off the superuser role) properly.
3. Verify: `POST http://supabase-gotrue:9999/signup` → 200; then the SSO login e2e completes.

## SSO gateway status (unchanged by this)
Code-complete + live-verified to the GoTrue boundary. The live run caught + fixed two real compose bugs (both committed on `feat/sso-gateway-apps`):
- `sso-auth` was not on `pmoves_api` → could not reach GoTrue at all.
- `SSO_FORWARD_AUTH_SECRET`/`OIDC_SIGNING_KEY` were absent from the `environment:` block → never reached the container.
Plus: OIDC RS256 key self-provisions (`/oidc/jwks` live), all unit + security checks green.
