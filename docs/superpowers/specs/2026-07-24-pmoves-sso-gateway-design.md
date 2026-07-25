# PMOVES SSO Gateway — Design Spec

**Date:** 2026-07-24
**Goal:** A user who authenticates once against Supabase GoTrue reaches wger (Health), Firefly III (Wealth), Open-Notebook, and Jellyfin **already logged in** — "auth once, access all." Supabase stays the single identity provider; the Supabase `JWT_SECRET` and BoTZ's shipped `validate_jwt` pattern are reused.

**Approved decisions (brainstorm 2026-07-24):**
- Login: **GitHub OAuth (primary) + email/password (fallback)**, both via GoTrue.
- Validator: **custom FastAPI forward-auth service** (`pmoves-sso-auth`), reusing BoTZ's `validate_jwt`.
- Reverse proxy: **Traefik** with the ForwardAuth middleware.
- Routing: **subdomains** (`health/wealth/notebook/media.pmoves.ai`); session cookie scoped to `.pmoves.ai`.
- Scope: **all 4 apps in Phase 1** (Jellyfin included via `jellyfin-plugin-sso` against minimal OIDC endpoints on the auth service).

## Architecture

```
Browser ──HTTPS──> Traefik (edge, pmoves_external, TLS)
   │  Host: {health,wealth,notebook,media}.pmoves.ai
   ▼
 ForwardAuth middleware ──subrequest──> pmoves-sso-auth (FastAPI)  GET /auth/verify
   • no/invalid pmoves_session cookie → 302 https://auth.pmoves.ai/login?rd=<orig>
   • valid cookie → 200 + headers: Remote-User, X-Auth-Email, X-Auth-Subject
   ▼ (on 200, Traefik forwards to the app with those headers injected)
 App (wger | firefly | open-notebook | jellyfin) trusts the injected identity
```

Login/session issuance (also on `auth.pmoves.ai`, same service):
```
GET  /login          → page: "Sign in with GitHub" + email/password form
  GitHub  → 302 GoTrue /authorize?provider=github&redirect_to=/callback
  email/pw→ POST /login → GoTrue /auth/v1/token?grant_type=password
GET  /callback       → exchange GoTrue code/token → Set-Cookie pmoves_session=<supabase access_jwt>
                       (HttpOnly, Secure, SameSite=Lax, Domain=.pmoves.ai) → 302 back to rd
GET  /logout         → clear cookie → 302 GoTrue logout
```

## Components

### 1. `pmoves-sso-auth` (new service — `pmoves/services/sso-auth/`)
FastAPI app. Responsibilities and endpoints:
- **`GET /auth/verify`** — Traefik ForwardAuth target. Reads `pmoves_session` cookie, runs `validate_jwt(cookie, SUPABASE_JWT_SECRET, alg=HS256)` (lifted from `PMOVES-BoTZ/features/mcp_bridge/auth.py`). On success → `200` with response headers `Remote-User` (GoTrue `email` or `sub`), `X-Auth-Email` (email), `X-Auth-Subject` (`sub`). On failure/absent → `401` (Traefik converts to the configured redirect). Near-zero latency; no network calls on the hot path (HS256 local verify).
- **`GET /login`** — renders login page (GitHub button + email/pw form), carries `rd` (return destination).
- **`POST /login`** — email/pw → GoTrue `/auth/v1/token?grant_type=password` → set cookie → redirect `rd`.
- **`GET /callback`** — GoTrue OAuth callback (GitHub) → obtain session → set cookie → redirect `rd`.
- **`GET /logout`** — clear cookie, GoTrue signout.
- **`GET /healthz`** — liveness.
- **OIDC-for-Jellyfin subset** (only consumed by `jellyfin-plugin-sso`): `GET /.well-known/openid-configuration`, `GET /oidc/authorize` (reuses the same GoTrue login → issues an OIDC `code`), `POST /oidc/token` (returns an `id_token` minted from the validated Supabase identity), `GET /oidc/userinfo`. This is a *thin adapter over the already-validated session*, not a general OIDC provider — scoped to Jellyfin's client_id only.

Config (env, from the pipeline): `SUPABASE_JWT_SECRET` (alias of `JWT_SECRET`), `GOTRUE_URL` (internal `http://supabase-gotrue:9999` / external `https://supabase.pmoves.ai`), `SSO_COOKIE_DOMAIN=.pmoves.ai`, `SSO_SESSION_TTL`, `JELLYFIN_OIDC_CLIENT_ID`/`_SECRET`. No new secrets minted — reuses `JWT_SECRET`.

### 2. Traefik (`pmoves-traefik` — `pmoves/docker-compose.traefik.yml`)
- Edge on `pmoves_external`; entrypoints `:80`→`:443` redirect. TLS via **Cloudflare DNS-01** for `*.pmoves.ai` (Cloudflare is the existing DNS per the fleet setup); mesh-internal access (Tailscale/Headscale hostnames) is the reachability path, DNS-01 is the cert path.
- One router per app (Host rule → app service), all attached to the shared `forward-auth@docker` middleware pointing at `pmoves-sso-auth:8080/auth/verify`, `authResponseHeaders: Remote-User,X-Auth-Email,X-Auth-Subject`.
- `auth.pmoves.ai` router → `pmoves-sso-auth` **without** the ForwardAuth middleware (login must be reachable unauthenticated).
- Apps drop their host `ports:` — reachable only through Traefik.

### 3. Per-app integration
| App | Mechanism | Change |
|---|---|---|
| **firefly** (Laravel) | `AUTHENTICATION_GUARD=remote_user_guard`, `AUTHENTICATION_GUARD_HEADER=Remote-User`, `AUTHENTICATION_GUARD_EMAIL=X-Auth-Email` | compose env only; auto-provisions the user on first header-auth. **Firefly has NO native OIDC** (open FR #10662) — remote-user IS the documented SSO path. **Disable Firefly MFA** when remote-user is on. |
| **wger** (Django) | `RemoteUserMiddleware` in `MIDDLEWARE`, `REMOTE_USER` trust; `WGER_ALLOW_REMOTE_USER=True` in the PMOVES wger fork | fork config + compose env |
| **open-notebook** (Streamlit fork) | replace `PasswordAuthMiddleware` with `RemoteUserMiddleware` in `PMOVES-Open-Notebook/api/auth.py` — trust `Remote-User` (fallback to the existing token for non-proxied access) | fork code. **Confirmed password-only, no OIDC/SSO upstream** — header-trust is the only option. |
| **jellyfin** | install an OIDC SSO plugin, configured against the auth service's OIDC subset; auto-provision Jellyfin users from the Supabase `sub`/email | plugin baked into the PMOVES jellyfin fork image at a PINNED version. **Primary: `Ezeqielle/jellyfin-plugin-oidc`** (actively maintained — v1.0.8 2026-07-15, pushed 2026-07-23; generic-OIDC). **Fallback: `9p4/jellyfin-plugin-sso`** (archived 2026-05-12 but battle-tested, 1461★, generic-OIDC, ≥10.8) if Ezeqielle proves too thin. Jellyfin has NO native OIDC (open FR #16470) and no trusted-header auth, so an OIDC plugin is the only path. **Caveat:** OIDC plugins cover the **web UI only** — Jellyfin *mobile apps* still use native login (out of scope for browser-seamless Phase 1). |

**Current-docs validation (2026-07-24):** the header-based forward-auth is the *correct common denominator*, not a shortcut — Firefly III and Open-Notebook have **no OIDC at all**, so trusted-header is their only SSO; wger uses Django's `RemoteUserMiddleware`; only Jellyfin requires OIDC (hence the auth-service OIDC subset). No simpler unified solution exists given this heterogeneity. Sources: Firefly III authentication docs + FRs #10662/#6514; open-notebook README (password-only); jellyfin-plugin-sso (archived, generic-OIDC).

Only the reverse proxy is trusted to set `Remote-User`; apps must reject the header on any path not fronted by Traefik (defence-in-depth — bind app ports to the Traefik network only).

## Data flow — session lifecycle
1. Unauthenticated request to `health.pmoves.ai` → Traefik ForwardAuth → `/auth/verify` 401 → 302 to `auth.pmoves.ai/login?rd=health.pmoves.ai`.
2. User signs in (GitHub or email/pw) → GoTrue issues Supabase JWT → cookie `pmoves_session` set on `.pmoves.ai`.
3. Redirect back → ForwardAuth now `200` + `Remote-User` → app auto-logs-in.
4. Same cookie satisfies `wealth/notebook/media.pmoves.ai` — no re-login (that IS the SSO).
5. JWT ~1h; **Phase 1:** on expiry `/auth/verify` returns 401 → transparent re-login (GoTrue session is still valid, so the redirect round-trip is invisible when the GoTrue cookie persists). **Enhancement (out of Phase 1):** silent refresh via a second HttpOnly `pmoves_refresh` cookie holding the GoTrue refresh token, exchanged in `/auth/verify` before the access JWT expires.

## Error handling
- Expired/invalid JWT → 401 → redirect to login (never a 500).
- GoTrue unreachable → login page shows a clear error; `/auth/verify` fails-closed (401) so apps stay protected.
- App up but header missing (misconfig) → app denies; Traefik logs the missing `Remote-User`.
- Jellyfin OIDC failure → falls back to Jellyfin's native login (not locked out).

## Security
- Cookie: HttpOnly, Secure, SameSite=Lax, `Domain=.pmoves.ai`.
- Apps trust `Remote-User` **only** from Traefik — app containers do not publish host ports; only Traefik is on their network edge.
- Reuse the single `SUPABASE_JWT_SECRET`; no new long-lived secret. HS256 today; the asymmetric-JWT (JWKS) migration (separate design) later swaps the verify path only.
- Forward-auth is fail-closed.

## Testing
- Unit: `/auth/verify` with valid / expired / tampered / absent cookie → 200+headers / 401.
- Integration: login (both methods) sets a valid cookie; a second app request with the cookie returns 200 without re-login.
- Per-app: header-auth auto-provisions + logs in the user (firefly, wger, open-notebook); Jellyfin OIDC round-trip creates + logs in the user.
- Negative: direct app access bypassing Traefik with a forged `Remote-User` is rejected.

## Scope / phasing
**Phase 1 (this spec):** Traefik + `pmoves-sso-auth` + all 4 apps (wger, firefly, open-notebook header-auth; jellyfin via OIDC subset). Delivers true one-login-all-apps.
**Out of scope (separate specs):** asymmetric JWKS migration; 2FA; adding further apps; the firefly tmpfs-hardening 500 fix (tracked separately, unblocks firefly serving at all).

## Global constraints
- Supabase GoTrue is the ONLY IdP; reuse `JWT_SECRET`/`SUPABASE_JWT_SECRET` (no new IdP, no separate user store).
- Reuse BoTZ's `validate_jwt` (HS256) — do not reimplement JWT verification.
- Apps are PMOVES forks — prefer config/env over code; code changes only where no header-auth config exists (open-notebook middleware).
- Follow the env pipeline (example → manifest → funnel); never inline secrets.
- Compose/Dockerfile/migration edits go through their Known-Road domains.
- Prerequisite: firefly must actually serve (its tmpfs 500 fix) before its SSO can be validated end-to-end.
