# Handoff — SSO forward-auth: browser login-redirect from `/auth/verify` (2026-08-19)

**Node:** 5090 (POWERFULMOVES) · **Lane:** notebook SSO (Lane 3, BLOCKER 2) · **Author:** 5090-CLAUDE (Claude Opus 4.8)

## Symptom (from the 2026-08-14 cutover attempt)

Hitting an SSO-gated edge host (`notebook.pmoves.ai`, `health.pmoves.ai`, `wealth.pmoves.ai`)
**without a session returned a hard `401` with no login redirect** — even for a browser
(`Accept: text/html`). The user was locked out with a dead 401 instead of being sent to the
login page. This was the second of the two cutover blockers (the first, the empty Cloudflare
DNS token, is tracked separately and is operator-gated).

## Root cause

The redirect-on-401 was delegated to a Traefik **`errors` middleware** (`pmoves-auth-redirect`
in `pmoves/config/traefik/dynamic.yml`), chained after `pmoves-forward-auth` on the
notebook/health/wealth routers:

```yaml
pmoves-auth-redirect:
  errors:
    status: ["401"]
    service: sso-auth@docker
    query: "/login?rd=https://{host}{uri}"
```

Two independent defects made this never work as a login redirect (confirmed against current
Traefik docs):

1. **An `errors` middleware is not a redirect.** It fetches the `query` path from `service`
   and returns that body **while keeping the original `401` status**. Best case the browser
   got `401 + login-HTML`; it never got a `3xx` to follow.
2. **`{host}`/`{uri}` are not valid `errors`-middleware placeholders.** The `query` substitutes
   only `{status}`. So `rd` became the literal string `https://{host}{uri}`, which the login
   page's `_safe_rd` open-redirect guard correctly rejects → post-login always landed at `/`,
   never back at the originally-requested page.

## Fix (this change)

Move the browser-vs-API decision **into `/auth/verify`** and let Traefik pass the response
through (a forwardAuth server's non-2xx response is returned to the client unchanged — so a
`302` emitted here becomes a real browser redirect):

- `pmoves/services/sso-auth/app.py`
  - `/auth/verify` now returns, on no/invalid session, `_unauthenticated_response(request)`.
  - `_unauthenticated_response`: **`302` to `{PUBLIC_BASE_URL}/login?rd=<original>` for
    `Accept: text/html` requests; bare `401` for everything else** (XHR/fetch/API — a 302 to
    an HTML login page would corrupt an API response and mask the auth failure).
  - `<original>` is rebuilt from the `X-Forwarded-Proto/Host/Uri` headers Traefik injects onto
    the forward-auth sub-request, then run through the existing `_safe_rd` guard so a spoofed
    `X-Forwarded-Host` cannot turn login into an open redirect. The `Location` host is always
    our own `PUBLIC_BASE_URL` (trusted config), never the forwarded host.
- `pmoves/config/traefik/dynamic.yml` — removed the `pmoves-auth-redirect` errors middleware
  (wrong tool; it would now also corrupt genuine API `401`s).
- `pmoves/docker-compose.external.yml` — dropped `pmoves-auth-redirect@file` from the
  `health`, `wealth`, and `notebook` router middleware chains (now
  `strip-client-auth-headers@file,pmoves-forward-auth@file`).

Generic across every forward-auth app — nothing notebook- or Jellyfin-specific. No secrets
involved. `/oidc/*` (the Jellyfin OIDC IdP path) is untouched.

## Tests

`pmoves/services/sso-auth/tests/test_login.py` adds coverage for the browser/API split and
the `rd` reconstruction (302 to `/login` with the forwarded URL as `rd`; bare 401 without
`text/html`; spoofed `X-Forwarded-Host` collapses to a safe `rd`). Existing verify tests
(200 + `Remote-User`, bare-401-without-session, forward-auth-secret) still pass.

## Deploy (operator-gated)

Recreate Traefik + sso-auth to pick up the dynamic-config and image changes:
`make -C pmoves up-edge` (does not touch the standalone Open Notebook on `:8503`). This is
independent of the notebook-ext cutover, which remains separately operator-gated (dual-writer
`surreal_data` hazard).

## Still-open Lane 3 blockers (NOT in this change)

- **BLOCKER 1 (cert):** the Cloudflare DNS token (`CLOUDFLARE_DNS_API_TOKEN`) is empty in
  `env.shared` → Traefik serves the default cert → DNS-01 never completes. `pmoves.ai` **is**
  Cloudflare-authoritative (`alex/dara.ns.cloudflare.com`, verified 2026-08-19), so a
  Zone:DNS:Edit token on `pmoves.ai` supplied via the secrets pipeline will issue the cert.
  Operator-gated.
- `notebook.pmoves.ai` has no public DNS record (fine for DNS-01 and the local hosts entry;
  needed later for public browser reach).
