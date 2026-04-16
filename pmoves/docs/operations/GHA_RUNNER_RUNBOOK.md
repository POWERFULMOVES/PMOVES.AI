# GitHub Actions Runner Runbook

**Phase:** 9G
**Last updated:** 2026-04-16
**Applies to:** `pmoves-github-runner-ctl-1` (monitor) + `gha-runner-{ai-lab,vps,hotfix}` (runners)

## Architecture

Two distinct components, two distinct auth modes:

| Component | Purpose | Auth |
|-----------|---------|------|
| `github-runner-ctl` (monitor) | Queries GitHub's `/actions/runners` API, publishes runner status to NATS | **PAT only** (`GITHUB_PAT` env var, priority 1; `GITHUB_PAT_FILE` priority 2) |
| `gha-runner-*` (runners) | Poll GitHub for workflow jobs, execute on self-hosted hosts | GitHub App cascade (`GH_APP_*`) via `local_cert_runners.py` |

**Do not confuse them.** Fixing the runners (App cascade) does not fix the monitor (PAT). Fixing the monitor does not register runners.

## Symptoms

### Monitor broken
```
$ docker logs pmoves-github-runner-ctl-1 --tail 5
ERROR - Failed to load GitHub PAT from file
IsADirectoryError: [Errno 21] Is a directory: '/run/secrets/github_pat'
ERROR - Failed to get runners for POWERFULMOVES/PMOVES.AI: GitHub PAT not available
```

Root cause: `pmoves/secrets/github_pat` exists on the host as a **directory**, not a file. The compose volume mount `./secrets/github_pat:/run/secrets/github_pat:ro` then exposes it as a directory inside the container, and `open(...)` raises `IsADirectoryError`.

### Runners crash-looping
```
$ docker ps --filter "name=gha-runner"
gha-runner-ai-lab    Restarting (1) 37 seconds ago
gha-runner-vps       Restarting (1) 12 seconds ago
gha-runner-hotfix    Restarting (1) 16 seconds ago
```

Root cause: `POST /actions/runner-registration → 404`. The GitHub App cascade
(`local_cert_runners.py`) is failing to mint a registration token, typically because
container state from a prior GH App reinstall is stale.

---

## Fix A — Monitor (PAT via env var)

This is the Phase 9G deliverable.

### 1. Create fine-grained PAT

1. Go to https://github.com/settings/personal-access-tokens/new
2. Resource owner: your user (or `POWERFULMOVES` org)
3. Repository access: **Only select repositories** → `POWERFULMOVES/PMOVES.AI`
   (or include all repos listed in `GITHUB_REPOSITORIES`)
4. Permissions (repository):
   - **Actions:** Read
   - **Administration:** Read and Write  (required for runner registration queries)
5. Expiration: 90 days (or per your policy)
6. Generate and copy token (format `github_pat_11...` or `ghp_...`)

### 2. Add to env.shared

```bash
# Edit pmoves/env.shared and add:
GITHUB_PAT=github_pat_11XXXXXXXXX
```

`env.shared` is the Docker env_file format (KEY=VALUE, no `export`). See
`pmoves/scripts/with-env.sh` for the canonical loader pattern.

### 3. Cycle the monitor container

```bash
# Recreate github-runner-ctl with the new GITHUB_PAT env var:
bash pmoves/scripts/with-env.sh docker compose \
  -f pmoves/docker-compose.yml \
  --profile orchestration \
  up -d --force-recreate github-runner-ctl
```

The runner-ctl container is in the `orchestration` and `workers` profiles.

### 4. Verify

```bash
# No more IsADirectoryError:
docker logs pmoves-github-runner-ctl-1 --tail 10 2>&1 | grep -i "pat\|runner" | head -5
# Expected: "Loaded GitHub PAT from environment variable"

# Monitor can now query GitHub:
curl -s http://localhost:8104/healthz
# Expected: 200 OK

# NATS alerts for runner status should also resume (separate bug: see Known Gap below).
```

---

## Fix B — Runners (GitHub App cascade)

This is NOT part of Phase 9G. It's the known-road runner cycle.

```bash
make -C pmoves ci-runners-local-cert-down
make -C pmoves ci-runners-local-cert-up
make -C pmoves ci-runners-local-cert-status
```

Expected: 3 runners online with labels `self-hosted, ai-lab` / `self-hosted, vps` / `self-hosted, hotfix`.

### Verify via GitHub API

```bash
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners \
  --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

Expected: all 3 `status: "online"`.

---

## Known Gap — NATSPublisher.publish_alert kwarg mismatch

```
ERROR - Failed to refresh runner status: NATSPublisher.publish_alert() got an unexpected keyword argument 'event_type'
```

The monitor calls `NATSPublisher.publish_alert(event_type=...)` but the current
`NATSPublisher` implementation doesn't accept `event_type`. This blocks NATS alert
emission for runner status changes but does **not** block the monitor from querying
GitHub or serving `/healthz`.

**Scope:** Tracked as a follow-up issue (separate from Phase 9G). Fixing the API
mismatch is a small code change in `services/github-runner-ctl/` but adds review
surface to this PR; it ships separately.

---

## Why not GitHub App for the monitor?

`services/github-runner-ctl/github/client.py:_load_pat()` only supports PAT. The
monitor doesn't use `local_cert_runners.py`'s App-token cascade. This is a
deliberate scope separation:

- Runners need **short-lived registration tokens** (GitHub App is the right fit)
- Monitor needs **long-lived read access to `/actions/runners`** (fine-grained PAT
  is the right fit; App installation tokens would need constant refresh)

Adding App auth to the monitor is a potential future improvement but out of scope
for Phase 9G.

---

## Why `GITHUB_PAT_FILE` is still present

The `GITHUB_PAT_FILE=${GITHUB_PAT_FILE:-/run/secrets/github_pat}` env var is kept
for backward compatibility with production deployments that use Docker secrets. It
is priority 2 in `client.py:_load_pat()` — env-var PAT wins when both are set.

The `./secrets/github_pat:/run/secrets/github_pat:ro` volume mount is also kept,
but the file-path code path becomes dead when `GITHUB_PAT` env var is set (which is
the production-recommended path going forward).

If you want to actively use the file mode instead:
```bash
# Replace the directory with a file:
rm -rf pmoves/secrets/github_pat
echo -n "github_pat_11XXXX" > pmoves/secrets/github_pat
chmod 0600 pmoves/secrets/github_pat
```

Note: `pmoves/secrets/` is gitignored, so the file won't be committed.

---

## Related Files

- `pmoves/services/github-runner-ctl/github/client.py:50-75` — PAT loader
- `pmoves/docker-compose.yml:3730-3746` — runner-ctl service definition
- `pmoves/env.shared.example` — `GITHUB_PAT` documentation (look for "Phase 9G")
- `pmoves/mk/preflight.mk:55-85` — `ci-runners-*` Make targets
- `pmoves/scripts/with-env.sh` — canonical env.shared loader

## NATS Subjects Affected (once publish_alert is fixed)

- `ops.github.runner.status.v1` (planned)
- `ops.github.runner.alert.v1` (planned)

Currently unpublished due to the `NATSPublisher.publish_alert` follow-up issue.
