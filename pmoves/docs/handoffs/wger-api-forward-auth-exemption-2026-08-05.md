# wger API must bypass forward-auth — and doing it naively is an auth bypass (2026-08-05)

**Brief for `KNOWN_ROAD=compose:handoff:wger-api-forward-auth-exemption-2026-08-05.md`.**

## Why the change is needed

The PMOVES-Health phone app must keep working once `health.pmoves.ai` goes behind SSO.

wger's Traefik router has **no path constraint**
(`docker-compose.external.yml:42-46`):

```
traefik.http.routers.health.rule        = Host(`health.pmoves.ai`)
traefik.http.routers.health.middlewares = pmoves-forward-auth@file,pmoves-auth-redirect@file
```

So `/api/v2/` is guarded too. The wger mobile app authenticates with
`Authorization: Token <key>` against the REST API — it has no browser session and
cannot follow an interactive redirect. Sequence today would be: app sends token →
Traefik calls `/auth/verify` → no `pmoves_session` cookie → 401 → `pmoves-auth-redirect`
converts it into a redirect to the login page → **the app receives HTML instead of
JSON and breaks.**

Same failure class as Jellyfin's native clients, which is why Jellyfin is deliberately
excluded from forward-auth (`external.yml:210-212`).

## Why the obvious fix is dangerous

Simply exempting `/api/` from forward-auth creates a **full authentication bypass.**

wger runs with (`external.yml:20-21`):

```
WGER_ALLOW_REMOTE_USER: "True"
WGER_REMOTE_USER_HEADER: "Remote-User"
```

Django's `RemoteUserMiddleware` applies to **every** path — there is no path scoping.
The only thing preventing header forgery today is `authResponseHeaders` in
`config/traefik/dynamic.yml:10`, which **overwrites** `Remote-User` with the value the
auth service returns. That protection exists **only on routes that actually run
forward-auth.**

Verified there is no second line of defence:

- The mounted nginx conf (`integrations/pr-kits/wger/nginx.conf:10-14`) sets
  `Host`, `X-Real-IP`, `X-Forwarded-For/Proto/Host` and **does not strip
  `Remote-User`**. nginx forwards unknown hyphenated headers by default.
- `config/traefik/dynamic.yml` has **no header-strip middleware** at all.

So a bare `/api/` exemption means an unauthenticated internet client could send:

```
GET /api/v2/... HTTP/1.1
Host: health.pmoves.ai
Remote-User: <any username>
```

and be authenticated as that user with **no token**. Introduced while trying to make
the phone app work.

## The change

Two parts. Part 1 is worth having on its own merit.

**1. `strip-client-auth-headers` middleware (`config/traefik/dynamic.yml`)** — removes
`Remote-User`, `X-Auth-Email`, `X-Auth-Subject`, `X-Forward-Auth-Secret` from
**inbound** requests. Applied as the **first** middleware on every router.

On forward-auth routes this changes nothing observable: the strip runs first, then
`pmoves-forward-auth` re-adds the trusted values from the auth response. What it buys
is that a client-supplied auth header can never survive on **any** route — including
routes added later by someone who does not know this invariant exists. Defence in
depth rather than relying on every future author remembering.

**2. A second router for the API path** (`docker-compose.external.yml`) — higher
priority, strip middleware, **no** forward-auth:

```
traefik.http.routers.health-api.rule        = Host(`health.pmoves.ai`) && PathPrefix(`/api/`)
traefik.http.routers.health-api.priority    = 100
traefik.http.routers.health-api.service     = health
traefik.http.routers.health-api.middlewares = strip-client-auth-headers@file
```

Explicit `priority` rather than relying on Traefik's rule-length ordering, so the
intent survives a future edit to either rule.

Result: browser hits the web UI and gets one SSO login; the phone app hits `/api/` and
authenticates with its own token, exactly as designed. Neither can forge `Remote-User`.

## Security note on what this deliberately accepts

`/api/v2/` becomes reachable from the internet with only wger's token auth in front of
it — it is no longer behind SSO. That is the necessary trade for native-app support,
and it is the same trade Jellyfin already makes. The API is still authenticated, just
not by the gateway. If that is later judged unacceptable, the alternative is issuing
app tokens from `sso-auth` and dropping wger's own token auth — a much larger change,
and it needs the multi-client work `sso-auth` does not have yet
(`oidc.py:77-80` is hardcoded to a single client).

## Template value

Every app with native (non-browser) clients needs this exact shape: strip inbound auth
headers globally, exempt the API path from forward-auth, let the app's own token auth
run. Getting it right here sets the pattern for Jellyfin and anything else with a
mobile client.

## Verification

- `docker compose config` parses with both routers present.
- Traefik picks `health-api` for `/api/...` and `health` for everything else.
- After deploy: `curl -H 'Remote-User: someone' https://health.pmoves.ai/api/v2/...`
  must **not** authenticate.
- Phone app can log in with a token while the browser is redirected to
  `auth.pmoves.ai`.
