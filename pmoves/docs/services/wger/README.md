# Wger External Service

The PMOVES external stack now mirrors the upstream production deployment model by pairing the
`pmoves-wger` Django container with an Nginx reverse proxy that serves collected static and media
assets, matching the official guidance from the Wger Docker project.citeturn0search0

## Runtime layout

- `pmoves-wger` (Django + Gunicorn) – builds fixtures, runs migrations, and writes static artefacts
  into `/home/wger/static` and uploaded media into `/home/wger/media`.
- `pmoves-wger-nginx` (Nginx 1.27) – serves `/static/` and `/media/` from the shared volumes and
  proxies application traffic to `pmoves-wger:8000`.

Both containers join the shared `pmoves-net` network. The host continues to expose the service on
`http://localhost:8000` via the proxy, so existing automation targets (n8n sync, CGP smokes) keep
working.

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

If either check fails, inspect the proxy logs with `docker logs pmoves-wger-nginx` and confirm that
`pmoves-wger` finished its bootstrap (look for `static files copied` in the Django logs).

### n8n automation assets

- Workflow exports are stored under `pmoves/integrations/health-wger/n8n/flows/`. Drop JSON files there and start the watcher with `make integrations-up-all` (or run `make integrations-import-flows` once) to sync them into n8n.
