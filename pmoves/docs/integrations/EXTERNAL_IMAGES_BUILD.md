# External Integration Image Notes

This note captures how to build or source container images for the first‑class PMOVES integrations (Wger, Firefly III, Open Notebook, Jellyfin) when running them locally via `docker-compose.pmoves-net.yml`.

## Wger (Pmoves-Health-wger)

- Dockerfiles live under `extras/docker/`.
- Use the production variant when building locally:

  ```bash
  docker build \
    -f integrations-workspace/Pmoves-Health-wger/extras/docker/production/Dockerfile \
    -t ghcr.io/powerfulmoves/pmoves-health-wger:main \
    integrations-workspace/Pmoves-Health-wger
  ```

- After publishing via GHCR, keep the repository name lowercase (`powerfulmoves/pmoves-health-wger`).

## Firefly III (pmoves-firefly-iii)

- The repository does **not** include a Dockerfile. Use the upstream official image instead of building from source.
- Recommended image: `fireflyiii/core:latest` (or a pinned version).
- Adjust `docker-compose.pmoves-net.yml` to reference the upstream image and set required environment variables (database, APP_KEY, etc.).
- If you prefer to ship a custom image, add a Dockerfile in your fork (e.g., extend the official image) before publishing to GHCR.

## Open Notebook (Pmoves-open-notebook)

- Root-level `Dockerfile` builds the app:

  ```bash
  docker build \
    -t ghcr.io/powerfulmoves/pmoves-open-notebook:main \
    integrations-workspace/Pmoves-open-notebook
  ```

- Ensure the build context contains the project root so the Dockerfile can copy the necessary source files.

## Jellyfin (PMOVES-jellyfin)

- The repository does **not** ship a Dockerfile. Use the official `jellyfin/jellyfin` image or create a minimal Dockerfile in your fork that wraps it.
- If you require customisations (plugins, pre-configured volumes, etc.), add a Dockerfile first and then publish the customised image to GHCR.

## Lowercase naming convention

- GHCR repository names must be lowercase. When configuring the compose files or GHCR workflows, ensure the image references use lowercase paths (e.g., `ghcr.io/powerfulmoves/pmoves-health-wger:main`).

