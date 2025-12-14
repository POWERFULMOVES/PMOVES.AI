# CI: Build and Publish Integration Images (GHCR)

This repo includes a GitHub Actions workflow that builds and publishes Docker images for key integrations (Agent Zero, Archon, Archon UI, Open Notebook, Jellyfin, Firefly III, Wger, PMOVES.YT) to GHCR on demand and nightly.

## Workflow

- File: `.github/workflows/integrations-ghcr.yml`
- Triggers: manual (workflow_dispatch) and nightly (cron).
- Matrix builds (excerpt):
  - `agent-zero` → `ghcr.io/<NAMESPACE>/pmoves-agent-zero:pmoves-latest`
  - `archon` → `ghcr.io/<NAMESPACE>/pmoves-archon:pmoves-latest` (builds from `pmoves/services/archon/Dockerfile`, which vendors the POWERFULMOVES Archon fork)
  - `archon-ui` → `ghcr.io/<NAMESPACE>/pmoves-archon-ui:pmoves-latest`
  - `open-notebook` → `ghcr.io/<NAMESPACE>/pmoves-open-notebook:pmoves-latest`
  - `jellyfin` → `ghcr.io/<NAMESPACE>/pmoves-jellyfin:pmoves-latest`
  - `firefly-iii` → `ghcr.io/<NAMESPACE>/pmoves-firefly-iii:pmoves-latest`
  - `wger` → `ghcr.io/<NAMESPACE>/pmoves-health-wger:pmoves-latest`
  - `pmoves-yt` → `ghcr.io/<NAMESPACE>/pmoves-yt:pmoves-latest`
  - Additional tags: `YYYYMMDD-<sha7>` for reproducibility.

## Namespace and Permissions

- By default, images push under `ghcr.io/<repo_owner>`.
- To push under a different org (e.g., `cataclysm-studios-inc`), set the repository secret `CI_GHCR_NAMESPACE` (legacy `GHCR_NAMESPACE` is still honored) and ensure the workflow’s `GITHUB_TOKEN` (or a PAT) has `packages:write` scope in that org.

### Optional Docker Hub Push

- If you also want to push to Docker Hub, add secrets:
  - `CI_DOCKERHUB_USERNAME` (legacy `DOCKERHUB_USERNAME`)
  - `CI_DOCKERHUB_TOKEN` (legacy `DOCKERHUB_TOKEN`)
  - Optional `CI_DOCKERHUB_NAMESPACE` (legacy `DOCKERHUB_NAMESPACE`, defaults to the username value)
- The workflow will log in and append Docker Hub tags alongside GHCR tags.

### Secret Sync Helper

- CI secrets are sourced from the same single-env files used locally (`pmoves/env.shared` and generated overlays), and mirrored into GitHub Secrets.
- To validate/generate the overlays from the CHIT bundle:
  - `python -m pmoves.tools.onboarding_helper status`
  - `python -m pmoves.tools.onboarding_helper generate`
- To push secrets to GitHub:
  - `./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev --dry-run`
  - `./pmoves/tools/push-categorized-secrets.sh --env Dev --dry-run`

## Extending to Other Integrations

Edit the `matrix.include` in `.github/workflows/integrations-ghcr.yml` and add entries for each integration:

```
- name: open-notebook
  git_url: https://github.com/lfnovo/open-notebook.git
  ref: main
  context: .
  dockerfile: Dockerfile
  image_name: pmoves-open-notebook
```

If an integration needs a non-root context or Dockerfile path, set `context` and `dockerfile` accordingly.

## Architectures

- Multi-arch builds are enabled: `linux/amd64, linux/arm64` (suitable for x86_64 servers and Jetson/ARM64 nodes).

## Using the Published Images

- `pmoves/env.shared.example` defines defaults:
  - `AGENT_ZERO_IMAGE`, `ARCHON_IMAGE` point to GHCR tags `pmoves-latest`.
- Compose overrides switch between local builds and published images; see `pmoves/docker-compose.agents.images.yml`.

## Status in the Console

- The PMOVES console links to Agent Zero and Archon and shows health badges.
- You can customize the health endpoints via:
  - `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` (default `/healthz`)
  - `NEXT_PUBLIC_ARCHON_HEALTH_PATH` (default `/healthz`)
