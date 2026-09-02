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

---

## Review-thread follow-up (2026-09-02, B850-CLAUDE assisting)

One P1: under the documented `make -C pmoves up-external` flow the default
`DJANGO_DB_HOST=wger-db` is unreachable. **Confirmed — and it blocks this
change.** `pmoves/docker-compose*.yml` is read-only on B850, so the fix is
handed back to the 5090 with the exact stanza below.

### Measured

```
Makefile:2229  EXTERNAL_DC := docker compose -p $(PROJECT) --project-directory $(CURDIR) \
                              $(COMPOSE_ENV_FILES) -f docker-compose.external.yml
Makefile:4529  up-external:  @$(EXTERNAL_DC) up -d
```

`up-external` loads **only** `docker-compose.external.yml`. In that file
`wger-db` appears twice and both are text — the comment on line 25 and the
`DJANGO_DB_HOST` default on line 31. There is no `wger-db` **service**, so
`up-external` never starts one.

The `wger-db` that does exist (`docker-compose.apps.yml`) is:

```
  wger-db:
    image: postgres:15-alpine
    ...
    profiles: ["health", "wger"]
    networks:
    - pmoves_data
```

while this Wger is on `pmoves_app` + `pmoves_external`. Those are separate
bridges, so even with the apps-tier database up, Docker DNS does not resolve
`wger-db` from the Wger container. `pmoves_data` is not among external.yml's
declared networks either (only `pmoves_app` and `pmoves_external`, both
`external: true`). Net effect: `WGER_DB_PASSWORD` is now a hard `${VAR:?}` gate
and, once satisfied, Wger crash-loops on an unresolvable host — strictly worse
than the SQLite state it replaces, unless an operator hand-attaches a network,
which is exactly the uncommitted manual step this repo's compose is supposed to
remove.

The apply sequence above is affected too: step 2 says to bring `wger-db` up "on
`pmoves_app`", but the apps.yml stanza pins it to `pmoves_data`. That step is not
executable as written.

### Required change (5090 — `pmoves/docker-compose.external.yml`)

Define the database in the same file that starts Wger, on the network Wger is
already on, and gate startup on its health:

```yaml
  wger-db:
    image: postgres:15-alpine
    restart: unless-stopped
    env_file:
      - env.shared
      - env.tier-data
    environment:
      POSTGRES_DB: "${WGER_DB_NAME:-wger}"
      POSTGRES_USER: "${WGER_DB_USER:-wger}"
      POSTGRES_PASSWORD: "${WGER_DB_PASSWORD:?set WGER_DB_PASSWORD in env.tier-data}"
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - wger-db:/var/lib/postgresql/data
    networks:
      pmoves_app:
        aliases:
          - wger-db
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${WGER_DB_USER:-wger} -d ${WGER_DB_NAME:-wger}"]
      interval: 20s
      timeout: 5s
      retries: 5
      start_period: 10s
```

plus `wger-db:` in the file's `volumes:` block (line 291) and, on the `wger`
service:

```yaml
    depends_on:
      wger-db:
        condition: service_healthy
```

Everything runs under `-p pmoves` (`Makefile:90`), so the named volume resolves
to the same `pmoves_wger-db` the apps-tier stanza uses — no data is stranded.

Attaching Wger to `pmoves_data` instead is the worse option: it makes
`up-external` depend on an apps-tier service that is behind
`profiles: ["health","wger"]` and therefore off by default.

### Verified while here (the change's premise is sound)

- `Pmoves-Health-wger/Dockerfile:5` is `FROM ghcr.io/wger/wger:latest` and copies
  no `settings/`, so the image really does run upstream settings and the fork's
  SQLite fallback (`settings/main.py:68-73`) is not in it. The `DJANGO_DB_*`
  requirement is real.
- `DJANGO_DB_DATABASE` is right and `DJANGO_DB_NAME` would be wrong
  (`settings/main.py:60`).
- "`DATABASE_URL` is NOT supported" is right: the string appears nowhere under
  `settings/`.

### Two pre-existing defects found, NOT this lane

1. `docker-compose.yml:5263` gives the apps-tier `wger`
   `DATABASE_URL=postgres://wger:...@wger-db:5432/wger` — dead config by the point
   just above. That stanza also declares no `networks:` (the `tier-api-hardened`
   anchor carries none), so it lands on the project default network while its
   `wger-db` sits on `pmoves_data` — the same unreachability, already on main.
2. `wger` is defined in **both** `docker-compose.apps.yml` and
   `docker-compose.external.yml` under one compose project, so the two
   definitions contend for a single container. Worth reconciling to one owner.
