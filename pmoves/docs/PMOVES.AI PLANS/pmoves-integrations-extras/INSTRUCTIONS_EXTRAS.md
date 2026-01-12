## Badges & Watcher

- Add the **CI badge** to your README using `.github/README-badge-snippet.md`.
- To enable live **n8n flows watching**, include `compose/docker-compose.flows-watcher.yml` in your Compose up:
  ```bash
  docker compose -f compose/docker-compose.core.yml \                 -f compose/docker-compose.wger.yml \                 -f compose/docker-compose.firefly.yml \                 -f compose/docker-compose.flows-watcher.yml \                 --profile wger --profile firefly up -d
  ```
