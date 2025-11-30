# Integration Image Maintenance

This guide explains how to publish PMOVES integration container images with tighter control and how to keep credential handling aligned with our security expectations.

## Selective GitHub Action Builds

Use the `Build and publish integration images to GHCR` workflow (`.github/workflows/integrations-ghcr.yml`) when you need multi-arch images produced by CI. The manual trigger now accepts two inputs:

- **integration** – choose a single integration or `all` to rebuild the full matrix. Non-dispatch events (nightly cron) continue to rebuild everything automatically.
- **push_to_dockerhub** – set to `true` when you want the run to publish to Docker Hub in addition to GHCR. The step only executes if the Docker Hub secrets are present.

This reduces unnecessary pushes and keeps our registry audit trail cleaner. Remember to capture smoke or verification evidence whenever you ship security-relevant updates (see `pmoves/docs/SMOKETESTS.md`).

## Local Build Helper

For local validation before pushing through CI, run `scripts/build_integration_image.sh`. Example:

```bash
./scripts/build_integration_image.sh --integration archon --tag dev-$(date +%Y%m%d)
```

Add `--push` once you are satisfied with the build and logged in to the target registry. The script clones the upstream repository, builds the container with the configured Dockerfile/context, and optionally pushes to `ghcr.io/<namespace>`.

Key options:

- `--ref <branch-or-tag>` selects an alternate git ref.
- `--namespace <name>` lets you push to a personal namespace for testing.
- `--context` and `--dockerfile` provide escape hatches when experimenting with custom layouts.

## Credential Hygiene

- Store registry tokens as GitHub Actions secrets (`Settings → Secrets and variables → Actions`). Never hard-code usernames or tokens into workflow files or scripts.
- For local pushes, use short-lived tokens and prefer environment variables (`export CR_PAT=...`) or Docker credential helpers. Log out when finished (`docker logout ghcr.io`).
- Rotate access tokens periodically and remove unused secrets from the repository to limit blast radius.
- Document any security-impacting changes (new scopes, additional registries, etc.) in team status threads and reference updates in PR descriptions per `AGENTS.md`.

Following these practices keeps the publishing pipeline auditable while still giving contributors the control they need to stage and release updates safely.
