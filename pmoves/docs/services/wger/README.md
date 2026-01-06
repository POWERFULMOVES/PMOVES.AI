# Wger External Service

The PMOVES external stack now mirrors the upstream production deployment model by pairing the
`cataclysm-wger` Django container with an Nginx reverse proxy that serves collected static and media
assets, matching the official guidance from the Wger Docker project.

## Runtime layout

- `cataclysm-wger` (Django + Gunicorn) – builds fixtures, runs migrations, and writes static artefacts
  into `/home/wger/static` and uploaded media into `/home/wger/media`.
- `cataclysm-wger-nginx` (Nginx 1.27) – serves `/static/` and `/media/` from the shared volumes and
  proxies application traffic to `cataclysm-wger:8000`.

Both containers join the shared `cataclysm-net` network. The host continues to expose the service on
`http://localhost:8000` via the proxy, so existing automation targets (n8n sync, CGP smokes) keep
working.

## Image + Branding Defaults

- Compose now points at `ghcr.io/cataclysm-studios-inc/pmoves-health-wger:pmoves-latest` by default. Override it with
  `WGER_IMAGE` if you publish a branded build elsewhere (same shape as the upstream production Dockerfile).
- `make up-external-wger` calls `scripts/wger_brand_defaults.sh` after the containers start. The helper
  now waits for Django to finish migrations (including the `django_site` bootstrap) before touching the
  database, then updates the `Site` record, seed gym row, and admin profile so the very first login already
  carries PMOVES branding. Tune the values via (and review the upstream guidance in the
  [official Wger documentation](https://wger.readthedocs.io/en/latest/)):
  - `WGER_SITE_URL` / `WGER_FROM_EMAIL` (propagated directly into Django settings)
  - `WGER_BRAND_SITE_NAME`, `WGER_BRAND_GYM_NAME`, `WGER_BRAND_GYM_CITY`
  - `WGER_BRAND_ADMIN_*` (first name, last name, email, username) and `WGER_BRAND_WAIT_SECS` if you
    need a longer bootstrap wait.
- Re-run `make wger-brand-defaults` whenever you reset the SQLite volume or want to apply different
  copy—it's idempotent and only touches the site/gym/admin rows.

### API surface

- The upstream OpenAPI description (`pmoves/docs/services/wger/wger.yaml`) is checked in so downstream
  services can autogenerate API clients. Point `openapi-python-client`, `oapi-codegen`, etc. at that
  file to scaffold strongly-typed helpers instead of hand-rolling HTTP calls.
- Keep the spec in sync whenever the Wger image revs; regenerate with `python manage.py generateschema`
  inside the container and drop the updated YAML back into `pmoves/docs/services/wger/`.

### Login & security defaults

- The upstream bootstrap resets the `admin` account password to `adminadmin`. Change it immediately
  after first login (`/en/auth/user/change-password/`) and/or set custom credentials via the
  `WGER_BRAND_ADMIN_*` env knobs before starting the stack.
- Django Axes rate limiting ships enabled by default (database handler + cache timeout). For production,
  point `DJANGO_CACHE_*` at Redis or Memcached so lockouts persist beyond the process lifetime; refer to
  the upstream security checklist in the [Wger docs](https://wger.readthedocs.io/en/latest/admin/).
- The production settings expose `DJANGO_CACHE_TIMEOUT` (default 300 s) so the context processor can
  safely read `CACHE_TIMEOUT`. Tweak it alongside the cache backend if you harden the stack.
- Branding automation lives in `pmoves/scripts/wger_brand_defaults.sh`; consult that script when you
  need to customize additional first-login fixtures beyond site/admin/gym metadata.

## Operations

### Bring up Wger with static assets

- Local compose (development): `make integrations-up-wger` starts Postgres + Wger in the new integrations stack. Use
  `make integrations-up-all` if you also want Firefly and the n8n flows watcher online.
- Legacy external bundle: keep `docker-compose.external.yml` around if you need the nginx proxy variant or published images. Run
  `DOCKER_CONFIG=$PWD/.docker-nocreds docker compose -p pmoves -f docker-compose.external.yml up -d wger wger-nginx`.

Collectstatic runs automatically during the Django bootstrap path. If you need to refresh the
artefacts (for example, after an upstream theme update) recreate the containers or run
`make integrations-down && make integrations-up-wger` (or rerun the external compose command).

### Verifying the proxy / API

- With the nginx bundle: `curl -I http://localhost:8000` should return a `302` redirect with `Server: nginx` and the static asset check should return `200`.
- With the integrations stack: the Django service is exposed directly on `http://localhost:8000`; use `/api/v2/` to verify the REST API (`curl -s http://localhost:8000/api/v2/ | jq`).

If either check fails, inspect the proxy logs with `docker logs cataclysm-wger-nginx` and confirm that
`cataclysm-wger` finished its bootstrap (look for `static files copied` in the Django logs). Re-run
`make wger-brand-defaults` if you need to reapply the PMOVES copy after wiping the volumes.

### n8n automation assets

- Workflow exports are stored under `pmoves/integrations/health-wger/n8n/flows/`. Drop JSON files there and start the watcher with `make integrations-up-all` (or run `make integrations-import-flows` once) to sync them into n8n.
