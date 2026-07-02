# Cross-Node ai-lab Runner — Known Road brief (2026-06-11)

**Provable reason for `KNOWN_ROAD=compose:handoff:cross-compat-runner-2026-06-11.md`.**

## Why
`pmoves/docker/runner/docker-compose.4090.yml` (#1602) is hardcoded to the 4090
(`container_name: pmoves-4090-runner-N`, `RUNNER_NAME_PREFIX: pmoves-4090`,
`LABELS` with no node sub-label). The Z890 infra node has no registered runner, so
`sync-secrets-local.yml` (which writes `local.env` on an ai-lab runner targeted by
node sub-label) can't hydrate Z890's env from GitHub secrets — blocking the
services-up preflight (auth-alignment).

Operator directive (2026-06-11): the runners matrix "should be cross compat" — one
parameterized compose for **every** Docker host, not a per-node file.

## What
New `pmoves/docker/runner/docker-compose.runner.yml` — the 4090 compose, fully
env-parameterized:
- `RUNNER_NODE` → name prefix `pmoves-${RUNNER_NODE}`, container `pmoves-${RUNNER_NODE}-runner-N`,
  and a `${RUNNER_NODE}` **sub-label** (what `sync-secrets-local` targets)
- `RUNNER_EXTRA_LABELS` → optional `gpu,cuda,…`
- `RUNNER_ACCESS_TOKEN` → repo-scoped PAT (GITHUB_PAT / `gh auth token`)

Runs on Docker Desktop (Windows nodes via WSL2) or native Engine (Linux nodes) —
the same file. `docker-compose.4090.yml` is superseded (kept until the make targets
migrate).

## Bring-up
```
RUNNER_NODE=z890 RUNNER_ACCESS_TOKEN=$(gh auth token) \
  docker compose -f docker/runner/docker-compose.runner.yml up -d
```
Then `make -C pmoves secrets-sync-trigger` targeting `z890` hydrates Z890's local env.

## Risk
Low — additive new compose + handoff. No existing service touched. The runner image
(`myoung34/github-runner`) is the established #1602 choice (image change out of scope).
