# Python Images Toolchain Canary

Last updated: 2026-03-05

## Purpose

Keep production Python image builds reproducible while still testing new upstream toolchain releases.

- Stable production pins live in these Dockerfiles:
  - `pmoves/services/supaserch/Dockerfile`
  - `pmoves/services/deepresearch/Dockerfile`
  - `pmoves/services/pmoves-yt/Dockerfile`
  - `pmoves/services/archon/Dockerfile`
- Canary automation checks newer `setuptools`/`wheel` releases weekly, then gates candidates with:
  - Docker build (`linux/amd64`) per image
  - Trivy gate (`HIGH,CRITICAL`, `ignore-unfixed=true`) per image

Only candidates that pass all image gates are proposed as a PR.

## Workflow

File: `.github/workflows/python-images-toolchain-canary.yml`

Triggers:
- Weekly schedule: Monday 09:00 UTC
- Manual dispatch (`workflow_dispatch`)

Runner lane:
- `runs-on: [self-hosted, Linux, X64, vps]`
- This avoids using the GPU lane for non-GPU build/scan work.

## What the job does

1. Reads current pinned versions from `pmoves/services/supaserch/Dockerfile`.
2. Resolves candidate versions:
   - default: latest on PyPI
   - optional manual override inputs:
     - `setuptools_version`
     - `wheel_version`
3. Patches all managed Dockerfiles to the candidate versions.
4. Builds and scans each managed image.
5. Opens/updates PR `chore/python-images-toolchain-canary` if all gates pass.

## Production release scope note

This canary updates the local Python-backed GHCR integration images in `PMOVES.AI`.

When the canary PR opens, the repo’s normal `integrations-ghcr.yml` PR checks still run and validate the full GHCR integration matrix for production release workflows.

For local-first production release validation across all in-repo GHCR integrations (not just Python images), use:

```bash
make -C pmoves ghcr-prepublish-inrepo
make -C pmoves ghcr-dispatch-all GHCR_DISPATCH_REF=<branch> GHCR_NAMESPACE=<org-namespace>
```

## Manual run

Run with latest candidates:

```bash
gh workflow run python-images-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened
```

Run with explicit candidate versions:

```bash
gh workflow run python-images-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened \
  -f setuptools_version=82.0.0 \
  -f wheel_version=0.46.3 \
  -f open_pr=true
```

Dry-run candidate validation without opening PR:

```bash
gh workflow run python-images-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened \
  -f open_pr=false
```

## Local parity commands

Example for one image (`supaserch`):

```bash
docker buildx build --platform linux/amd64 \
  -f pmoves/services/supaserch/Dockerfile \
  -t local/pmoves-supaserch:toolchain-canary \
  pmoves/services --load

docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.57.1 image \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --format table \
  --exit-code 1 \
  local/pmoves-supaserch:toolchain-canary
```

Repeat for the other managed images (`deepresearch`, `pmoves-yt`, `archon`) using their Dockerfiles/contexts.

## Merge policy

- Keep exact pins in Dockerfiles (no `>=`).
- Merge canary PR only after CI is green and review is complete.
- Promote through normal production branch flow (`PMOVES.AI-Edition-Hardened` governance).
