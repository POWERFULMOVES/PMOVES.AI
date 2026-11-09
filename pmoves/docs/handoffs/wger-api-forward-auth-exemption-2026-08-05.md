# Known Road: wger API forward-auth exemption with auth-bypass protection

**Domain:** compose · **File:** `pmoves/docker-compose.external.yml`
**Date:** 2026-08-05 · **Proposed by:** CRUSH-GLM52 (Z890) · **Reason class:** security

## Why

wger's Traefik router (`health`) has a single rule `Host(`health.pmoves.ai`)` with
no path constraint. The wger phone app authenticates via `Authorization: Token <key>`
against `/api/v2/` — it has no browser session and can't follow the interactive
redirect that `pmoves-auth-redirect` produces. Exempting `/api/` from forward-auth
is needed, but doing so naively opens a full auth bypass:

wger runs `WGER_ALLOW_REMOTE_USER=True` with `WGER_REMOTE_USER_HEADER=Remote-User`.
A bare `/api/` exemption would let anyone send `Remote-User: <username>` and be
authenticated as that user with no token at all.

## The change (two pieces)

### 1. strip-client-auth-headers middleware (dynamic.yml — no road needed)

New middleware that blanks `Remote-User`, `X-Auth-Email`, `X-Auth-Subject`,
`X-Forward-Auth-Secret` from all inbound requests. On forward-auth routes,
`authResponseHeaders` re-adds the trusted values afterwards, so SSO routes
are unchanged. On non-forward-auth routes, client-supplied headers cannot survive.

### 2. Split router for API path (docker-compose.external.yml — this road)

Add a second Traefik router `health-api` with higher priority that matches
`PathPrefix(`/api/`)`, applies `strip-client-auth-headers@file` but NOT
`pmoves-forward-auth`. The web UI router stays on forward-auth.

```
health-api.rule      = Host(`health.pmoves.ai`) && PathPrefix(`/api/`)
health-api.priority  = 100
health-api.service   = health
health-api.middlewares = strip-client-auth-headers@file
```

Also apply `strip-client-auth-headers` as the FIRST middleware on every existing
router (health, wealth, notebook) so client-supplied headers never survive on
any route.

## Verify after

- `GET /api/v2/` with `Remote-User: admin` → 401 (wger's own token auth, no bypass)
- `GET /` in browser → SSO redirect (forward-auth still works)
- wger phone app with valid token → 200 (token auth path works)

## Note

This is the template for every native-client app (Jellyfin, etc.). Getting it
right here sets the pattern for all future API exemptions.
