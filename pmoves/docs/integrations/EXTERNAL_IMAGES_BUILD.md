# External Integration Image Notes

This note captures how to build or source container images for the first‑class PMOVES integrations (Wger, Firefly III, Open Notebook, Jellyfin) when running them locally via `docker-compose.pmoves-net.yml`.

## Wger (Pmoves-Health-wger)

- Dockerfiles live under `extras/docker/`. Build and publish the production image for both amd64/arm64:

  ```bash
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -f integrations-workspace/Pmoves-Health-wger/extras/docker/production/Dockerfile \
    -t ghcr.io/cataclysm-studios-inc/pmoves-health-wger:2025.11.04 \
    -t ghcr.io/cataclysm-studios-inc/pmoves-health-wger:pmoves-latest \
    --push \
    integrations-workspace/Pmoves-Health-wger
  ```

- Update the version tag as needed. The `pmoves-latest` alias keeps Compose pointing at the most recent release.

## Firefly III (pmoves-firefly-iii)

- A thin wrapper Dockerfile lives at the repo root (inherits from the official `fireflyiii/core` image). Build and publish multi-arch tags:

  ```bash
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t ghcr.io/cataclysm-studios-inc/pmoves-firefly-iii:2025.11.04 \
    -t ghcr.io/cataclysm-studios-inc/pmoves-firefly-iii:pmoves-latest \
    --push \
    integrations-workspace/PMOVES-Firefly-iii
  ```

- The wrapper only adds PMOVES metadata so the runtime stays identical to upstream while remaining reproducible.

## Open Notebook (Pmoves-open-notebook)

- Root-level `Dockerfile` builds the app:

-  ```bash
  make -C integrations-workspace/Pmoves-open-notebook docker-release
  ```

- The Makefile in the fork already builds both architectures (amd64/arm64) via `docker buildx`, tags the image as `ghcr.io/lfnovo/open-notebook:<version>` plus `v1-latest`, and pushes to GHCR. Authenticate first (`make docker-login-ghcr`) which uses `DOCKER_USERNAME` / `DOCKER_PASS`. Override `OPEN_NOTEBOOK_IMAGE` if you want to pin a specific version in Compose.

## Jellyfin (PMOVES-jellyfin)

- The repo includes a minimal Dockerfile extending `jellyfin/jellyfin:10.11.0`. Build and publish:

  ```bash
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t ghcr.io/cataclysm-studios-inc/pmoves-jellyfin:2025.11.04 \
    -t ghcr.io/cataclysm-studios-inc/pmoves-jellyfin:pmoves-latest \
    --push \
    integrations-workspace/PMOVES-jellyfin
  ```

- Customize this Dockerfile if you need bundled plugins or pre-seeded configs; re-run the command afterwards to push a new tag.

## Lowercase naming convention

- GHCR repository names must be lowercase. When configuring the compose files or GHCR workflows, ensure the image references use lowercase paths (e.g., `ghcr.io/cataclysm-studios-inc/pmoves-health-wger:pmoves-latest`).
