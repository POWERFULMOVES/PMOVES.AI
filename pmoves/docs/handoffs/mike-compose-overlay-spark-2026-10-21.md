# Operator apply: `pmoves/docker-compose.mike.yml` (PMOVES-Mike on SPARK)

**Why this is a handoff.** `pmoves/docker-compose*.yml` sits in the guard's
`readOnlyPaths` class, under the `compose` road. The delivery agent that wrote
PR #3397 could not open that road. Its file grant was refused: the
`.known-road-active` write was denied by both the write guard and the
session's permission classifier. So the overlay is staged here verbatim, and
this tracked file is also the provable reason for applying it:

```bash
KNOWN_ROAD=compose:handoff:mike-compose-overlay-spark-2026-10-21.md   # session env, or the file grant
# then create pmoves/docker-compose.mike.yml with EXACTLY the YAML below, and:
make -C pmoves mike-config     # renders + validates; starts nothing
```

`pmoves/mk/mike.mk` (`up-mike`, `down-mike`, `mike-status`, `mike-config`,
`mike-logs`) already references this path. Until the file exists, those
targets fail at compose parse time with "no such file". They do not fall
back to anything.

Context: `pmoves/docs/integrations/MIKE_INTEGRATION.md`.

## File content

```yaml
# PMOVES.AI overlay for PMOVES-Mike (MikeOSS legal-AI platform) on SPARK.
#
# NOT a standalone file. Layered on the submodule's own compose by the Known
# Road only (pmoves/mk/mike.mk):
#   make -C pmoves up-mike | down-mike | mike-status | mike-config | mike-logs
#
# What this overlay changes, and why:
#   1. EVERY published port is re-bound to ${MIKE_BIND:-127.0.0.1} and remapped
#      into the 18300-18399 block. Upstream publishes gateway/backend/frontend
#      on 0.0.0.0 and uses 54322/9000/9001/6379/3000/3001 -- all already taken
#      on SPARK. `ports: !override` REPLACES the upstream list; a plain merge
#      would ADD a second binding and collide.
#   2. Compose project `pmoves-mike` namespaces containers, volumes and the
#      default network. Mike declares no container_name.
#   3. Browser-facing URLs (GoTrue links, presigned storage URLs) follow the
#      remapped ports so signup completes on SPARK.
#   4. Node-local secrets come from pmoves/env.mike (gitignored, funneled).
#   5. Upstream Sentry telemetry is OFF by default (upstream default is ON).
#
# Port map (host side, loopback by default):
#   18300 frontend        18301 backend        18321 Supabase gateway
#   18322 Postgres        18325 Mailpit UI/API 18326 Mailpit SMTP
#   18379 Redis           18390 RustFS S3      18391 RustFS console
#
# The JWT secret, anon/service_role keys, Postgres password and RustFS admin
# pair are UPSTREAM'S WELL-KNOWN LOCAL DEMO VALUES. Acceptable only while every
# port is loopback-bound; `make up-mike` refuses MIKE_BIND != 127.0.0.1 unless
# MIKE_DEMO_CREDS_ROTATED=1. See MIKE_INTEGRATION.md § Secrets.

services:
  db:
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_DB_PORT:-18322}:5432"

  auth:
    environment:
      API_EXTERNAL_URL: ${MIKE_SUPABASE_PUBLIC_URL:-http://localhost:18321}
      GOTRUE_SITE_URL: ${MIKE_FRONTEND_URL:-http://localhost:18300}
      GOTRUE_EXTERNAL_GOOGLE_ENABLED: ${MIKE_GOOGLE_AUTH_ENABLED:-false}
      GOTRUE_EXTERNAL_GOOGLE_REDIRECT_URI: ${MIKE_SUPABASE_PUBLIC_URL:-http://localhost:18321}/auth/v1/callback

  gateway:
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_GATEWAY_PORT:-18321}:8000"

  mailpit:
    # Upstream pins `latest`; PMOVES pins the release whose REST API is
    # documented in MIKE_INTEGRATION.md (TitanMail MCP's local test inbox).
    image: ${MIKE_MAILPIT_IMAGE:-axllent/mailpit:v1.31.6}
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_MAILPIT_PORT:-18325}:8025"
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_MAILPIT_SMTP_PORT:-18326}:1025"

  storage:
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_STORAGE_PORT:-18390}:9000"
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_STORAGE_CONSOLE_PORT:-18391}:9001"

  redis:
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_REDIS_PORT:-18379}:6379"

  workflow-sync:
    image: ${MIKE_BACKEND_IMAGE:-pmoves-mike-backend:local}
    env_file:
      - path: ${MIKE_ENV_FILE:?MIKE_ENV_FILE must point at pmoves/env.mike (set by make up-mike)}
        required: true

  backend:
    image: ${MIKE_BACKEND_IMAGE:-pmoves-mike-backend:local}
    env_file:
      - path: ${MIKE_ENV_FILE:?MIKE_ENV_FILE must point at pmoves/env.mike (set by make up-mike)}
        required: true
    environment:
      - FRONTEND_URL=${MIKE_FRONTEND_URL:-http://localhost:18300}
      - API_PUBLIC_URL=${MIKE_FRONTEND_URL:-http://localhost:18300}/api
      - R2_PUBLIC_ENDPOINT_URL=${MIKE_STORAGE_PUBLIC_URL:-http://localhost:18390}
      - OLLAMA_BASE_URL=${MIKE_OLLAMA_BASE_URL:-http://host.docker.internal:11434/v1}
      - SENTRY_DISABLED=${MIKE_SENTRY_DISABLED:-true}
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_BACKEND_PORT:-18301}:3001"

  frontend:
    image: ${MIKE_FRONTEND_IMAGE:-pmoves-mike-frontend:local}
    build:
      args:
        NEXT_PUBLIC_SENTRY_DISABLED: ${MIKE_SENTRY_DISABLED:-true}
    environment:
      - SENTRY_DISABLED=${MIKE_SENTRY_DISABLED:-true}
    ports: !override
      - "${MIKE_BIND:-127.0.0.1}:${MIKE_FRONTEND_PORT:-18300}:3000"
```

## Checks after applying

1. `make -C pmoves mike-config` should print `OK: pmoves-mike compose renders`.
   It needs `pmoves/env.mike`: `cp pmoves/env.mike.example pmoves/env.mike`
   is enough to render.
2. Before `up-mike`, check that no host port in `18300-18391` appears in
   `docker compose ... config --format json | jq '.services[].ports'` without
   the `127.0.0.1` host_ip.
3. `make -C pmoves up-mike && make -C pmoves mike-status` should return
   backend `{"ok":true}`, gateway `200`, and mailpit `200`.
