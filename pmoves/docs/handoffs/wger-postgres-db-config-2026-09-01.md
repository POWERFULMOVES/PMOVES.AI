# Handoff — wger: wire DJANGO_DB_* so the pmoves-latest image boots (SQLite → postgres)

**Node:** 5090 · **Lane:** wger update (operator-approved 2026-09-01) · **Author:** 5090-CLAUDE

## Why

`ghcr.io/powerfulmoves/pmoves-health-wger:pmoves-latest` is built `FROM ghcr.io/wger/wger` and
only adds labels + a healthcheck — it does **not** bake the fork's `settings/` (the fork's
sqlite fallback lives there). So the container runs **upstream** `settings/main.py`, which
requires `DJANGO_DB_*` with no default → `ImproperlyConfigured: Set the DJANGO_DB_ENGINE`
crash-loop (observed this session). The `wger` service in `docker-compose.external.yml` sets
**no DB env at all**, and the running (rolled-back) wger is on **ephemeral SQLite** — there is
no `wger-db` running.

## What this change does

Adds `DJANGO_DB_*` to the `wger` service pointing at the fleet's canonical `wger-db` postgres
(`docker-compose.apps.yml:45-83` — `postgres:15`, db/user `wger`, password `${WGER_DB_PASSWORD}`,
persistent `wger-db` volume). Note the var is **`DJANGO_DB_DATABASE`** (not `DJANGO_DB_NAME`) —
that exact name is what upstream wger reads. `DATABASE_URL` is NOT supported by wger.

## Apply sequence (operator / steward — deliberate; this is a SQLite→postgres move)

1. Ensure `WGER_DB_PASSWORD` is in `env.tier-data` (secrets pipeline — never inline).
2. Bring up `wger-db` (it's in `apps.yml`, currently not running) on `pmoves_app`.
3. `docker pull ghcr.io/powerfulmoves/pmoves-health-wger:pmoves-latest`
4. `make -C pmoves rebuild-external-svc SVC=wger`
5. First boot runs Django migrations against the empty postgres — wger starts **fresh**
   (the ephemeral SQLite had no persistent volume, so there is no user data to migrate;
   confirm this is acceptable before applying).

## Follow-up (NOT in this change) — SSO multi-user auto-provisioning

The service sets `WGER_ALLOW_REMOTE_USER`/`WGER_REMOTE_USER_HEADER`, which the **upstream**
image does **not** read. Upstream uses `AUTH_PROXY_HEADER` / `AUTH_PROXY_USER_EMAIL_HEADER` /
`AUTH_PROXY_CREATE_UNKNOWN_USER` / `AUTH_PROXY_TRUSTED_IPS`. Wiring those (with `AUTH_PROXY_TRUSTED_IPS`
scoped to the wger-nginx/Traefik source, NOT `0.0.0.0/0`) makes SSO identities auto-provision
distinct wger users. Deferred because the trusted-IPs value needs the proxy's real source range.
