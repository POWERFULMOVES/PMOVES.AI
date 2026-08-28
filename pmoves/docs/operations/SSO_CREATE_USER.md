# SSO — create an email/password user (interim sign-in)

Lets DARKXSIDE sign in to the SSO-gated services (`health` / `wealth` / `notebook`.pmoves.ai)
at **`https://auth.pmoves.ai/login`** with email + password.

## Why this, not GitHub

The login page's "Sign in with GitHub" button is a dead link (points at the internal
`supabase-gotrue:9999`) and GoTrue has no GitHub provider wired. GitHub OAuth is
**intentionally not the path** — Tailscale identity is the long-term SSO, and email/password
is the interim while Google Workspace + Titan MCP get set up. See memory
`project_sso_auth_architecture_decision`.

Jellyfin (`media.pmoves.ai`) does **not** use this — it has its own accounts.

## Why the admin API (not self-signup, not the PostgREST MCP)

- GoTrue here has **no SMTP** and `MAILER_AUTOCONFIRM=false`, so a self-service signup creates
  a user that can never confirm and never logs in. The **admin API with `email_confirm: true`**
  creates an already-confirmed user and sends no mail.
- This is the documented mechanism: `supabase.auth.admin.createUser({email, password,
  email_confirm: true})` (Supabase docs) == `POST /auth/v1/admin/users` with the SERVICE_ROLE
  key. Admin methods require SERVICE_ROLE.
- **Do NOT** create the user via the `pmoves-supabase` MCP / PostgREST or a raw `INSERT` into
  `auth.users`: GoTrue must hash the password and create the `auth.identities` row. A direct
  insert yields a user that cannot authenticate. PostgREST is for table data, not auth.

## Run it

```bash
make -C pmoves sso-create-user
```
- Loads `SUPABASE_SERVICE_ROLE_KEY` from the env tier via `with-env.sh` (source-only).
- Prompts for email + password (password hidden, entered twice).
- Secrets never touch argv / `ps` / env files / chat — the key rides a `curl -K` config file
  (chmod 600) and the JSON body (with the password) rides `--data @file` (chmod 600); both are
  removed on exit.

Path used: `POST $KONG_URL/auth/v1/admin/users` (default `KONG_URL=http://localhost:8000`, the
Supabase Kong on this node, which routes `/auth/v1` → GoTrue). Override `KONG_URL` for another node.

## Verify

Open `https://auth.pmoves.ai/login`, sign in with the email/password. A protected service
(`https://health.pmoves.ai`) should then load instead of bouncing to login.

## Notes

- Re-running for an existing email is a no-op (HTTP 422, reported, nothing changed).
- Password reset is a separate admin call (`PUT /auth/v1/admin/users/<id>`), deliberately not
  in this script.
- Related gap (separate lane): the `pmoves-supabase` MCP (`postgrestRequest`) currently returns
  `fetch failed` — its configured endpoint isn't reachable; needs a config check. Not required
  for this task (auth-user creation goes through GoTrue, not PostgREST).
