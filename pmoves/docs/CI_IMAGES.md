# CI: Build and Publish Integration Images (GHCR)

This repo includes a GitHub Actions workflow that builds and publishes Docker images for key integrations (Agent Zero, Archon) to GHCR on demand and nightly.

## Workflow

- File: `.github/workflows/integrations-ghcr.yml`
- Triggers: manual (workflow_dispatch) and nightly (cron).
- Matrix builds:
  - `agent-zero` → `ghcr.io/<NAMESPACE>/pmoves-agent-zero:pmoves-latest`
  - `archon` → `ghcr.io/<NAMESPACE>/pmoves-archon:pmoves-latest`
  - Additional tags: `YYYYMMDD-<sha7>` for reproducibility.

## Namespace and Permissions

- By default, images push under `ghcr.io/<repo_owner>`.
- To push under a different org (e.g., `cataclysm-studios-inc`), add a repo secret `GHCR_NAMESPACE` with that org name and ensure the workflow’s `GITHUB_TOKEN` (or a PAT) has `packages:write` scope in that org.

### Optional Docker Hub Push

- If you also want to push to Docker Hub, add secrets:
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN` (recommended) or password
  - Optional `DOCKERHUB_NAMESPACE` (defaults to `DOCKERHUB_USERNAME`)
- The workflow will log in and append Docker Hub tags alongside GHCR tags.

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
