# SupaSerch Toolchain Canary

Last updated: 2026-03-05

## Purpose

Keep the SupaSerch Docker build toolchain reproducible while still testing new upstream releases.

- Stable production pin lives in:
  - `pmoves/services/supaserch/Dockerfile`
- Canary automation checks newer releases weekly, then gates candidates with:
  - Docker build (`linux/amd64`)
  - Trivy gate (`HIGH,CRITICAL`, `ignore-unfixed=true`)

Only candidates that pass the gate are proposed as a PR.

## Workflow

File: `.github/workflows/supaserch-toolchain-canary.yml`

Triggers:
- Weekly schedule: Monday 09:00 UTC
- Manual dispatch (`workflow_dispatch`)

Runner lane:
- `runs-on: [self-hosted, Linux, X64, vps]`
- This avoids using the GPU lane for non-GPU build/scan work.

## What the job does

1. Reads the current pinned versions from `pmoves/services/supaserch/Dockerfile`.
2. Resolves candidate versions:
   - default: latest on PyPI
   - optional manual override inputs:
     - `setuptools_version`
     - `wheel_version`
3. Patches the Dockerfile pins in-place (candidate only).
4. Builds `local/pmoves-supaserch:toolchain-canary`.
5. Runs Trivy vulnerability gate.
6. Opens/updates PR `chore/supaserch-toolchain-canary` if candidate passes.

## Manual run

Run with latest candidates:

```bash
gh workflow run supaserch-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened
```

Run with explicit candidate versions:

```bash
gh workflow run supaserch-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened \
  -f setuptools_version=82.0.0 \
  -f wheel_version=0.46.3 \
  -f open_pr=true
```

Dry-run candidate validation without opening PR:

```bash
gh workflow run supaserch-toolchain-canary.yml \
  --repo POWERFULMOVES/PMOVES.AI \
  --ref PMOVES.AI-Edition-Hardened \
  -f open_pr=false
```

## Local parity commands

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

## Merge policy

- Keep exact pins in the Dockerfile (no `>=`).
- Merge canary PR only after CI is green and review is complete.
- Promote through normal production branch flow (`PMOVES.AI-Edition-Hardened` governance).
