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

```bash
DOCKER_CONFIG=$PWD/.docker-nocreds \
  docker compose -p pmoves -f docker-compose.external.yml up -d wger wger-nginx
```

Collectstatic runs automatically during the Django bootstrap path. If you need to refresh the
artefacts (for example, after an upstream theme update) recreate the containers or run
`docker compose ... up -d --force-recreate wger`.

### Verifying the proxy

- `curl -I http://localhost:8000` should return a `302` redirect with `Server: nginx`.
- `curl -I http://localhost:8000/static/images/logos/logo-font.svg` must respond `200`.

If either check fails, inspect the proxy logs with `docker logs pmoves-wger-nginx` and confirm that
`pmoves-wger` finished its bootstrap (look for `static files copied` in the Django logs).
