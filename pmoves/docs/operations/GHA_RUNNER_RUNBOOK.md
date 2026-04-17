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
```text
$ docker logs pmoves-github-runner-ctl-1 --tail 5
ERROR - Failed to load GitHub PAT from file
IsADirectoryError: [Errno 21] Is a directory: '/run/secrets/github_pat'
ERROR - Failed to get runners for POWERFULMOVES/PMOVES.AI: GitHub PAT not available
```

Root cause: `pmoves/secrets/github_pat` exists on the host as a **directory**, not a file. The compose volume mount `./secrets/github_pat:/run/secrets/github_pat:ro` then exposes it as a directory inside the container, and `open(...)` raises `IsADirectoryError`.

### Runners crash-looping
```text
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

### Primary path — agent-automated via gh CLI (one command)

If `gh` CLI is authenticated on the host with scopes `admin:org` (or
`repo + workflow`), a single Make target handles the entire fix:

```bash
# Sanity check first (dry-run, no writes):
make -C pmoves gha-runner-ctl-check-pat
# Expected: "OK: gh token scopes satisfy {...} requirement."

# Apply the fix (injects GITHUB_PAT + cycles container):
make -C pmoves gha-runner-ctl-setup
```

What the composite target does:
1. `gha-runner-ctl-setup-pat` — reads `gh auth token` value, writes it into
   `pmoves/env.shared` under `GITHUB_PAT=...` (updates in place if already
   present, appends otherwise). Never prints the token.
2. `gha-runner-ctl-cycle` — canonical pipeline:
   a. `make secrets-funnel` — CHIT export regenerates `env.tier-agent` from
      the updated `env.shared` (so the container's `env_file: env.tier-agent`
      carries the new `GITHUB_PAT`)
   b. `$(DC) up -d --force-recreate github-runner-ctl` — recreates the container
   c. Tails the last 15 log lines to confirm `"Loaded GitHub PAT from
      environment variable"`.

**Why secrets-funnel matters:** the `github-runner-ctl` service uses
`<<: *tier-agent-hardened-rw` which loads `env.tier-agent` (not `env.shared`
directly). `secrets-funnel` is the canonical path that regenerates tier env
files from the CHIT manifest + `env.shared`. Skipping it means the container
starts with stale tier-env and `${GITHUB_PAT}` resolves blank.

**Why this path exists:** the `gh` CLI's OAuth token (stored in the keyring
on the host that auth'd with `gh auth login`) already has
`admin:org, repo, workflow` scope for the org-owner account. That covers
the `Actions: Read + Administration: Read/Write` requirement from
`services/github-runner-ctl/github/client.py`. No fine-grained PAT creation
UI walk required.

**Scope verification:** `make gha-runner-ctl-check-pat` exits 2 if
scope is insufficient, with a hint to re-auth:
`gh auth refresh --scopes admin:org,repo,workflow`.

### Fallback path — operator creates fine-grained PAT

If `gh` CLI isn't available or the account auth'd with `gh` is not an
owner/admin of the target org, create a dedicated fine-grained PAT:

1. Go to https://github.com/settings/personal-access-tokens/new
2. Resource owner: your user (or `POWERFULMOVES` org)
3. Repository access: **Only select repositories** → `POWERFULMOVES/PMOVES.AI`
   (or include all repos listed in `GITHUB_REPOSITORIES`)
4. Permissions (repository):
   - **Actions:** Read
   - **Administration:** Read and Write  (required for runner registration queries)
5. Expiration: 90 days (or per your policy)
6. Generate and copy token (format `github_pat_11...` or `ghp_...`)
7. Edit `pmoves/env.shared` and add `GITHUB_PAT=<token>`
8. Cycle via canonical pipeline: `make -C pmoves gha-runner-ctl-cycle`
   (runs `secrets-funnel` → regenerates `env.tier-agent` → recreates container)

### Verify

```bash
# No more IsADirectoryError:
docker logs pmoves-github-runner-ctl-1 --tail 10 2>&1 | grep -i "pat\|runner" | head -5
# Expected: "Loaded GitHub PAT from environment variable"

# Monitor can now query GitHub:
curl -s http://localhost:8104/healthz
# Expected: 200 OK

# NATS alerts for runner status should also resume (separate bug: see Known Gap below).
```

### Secret-sync alternative (CHIT pipeline, currently not wired for this key)

`pmoves/chit/secrets_manifest.yaml` already lists `GITHUB_PAT` as a target
key (env.tier-agent) with `GH_PAT_PUBLISH` as a fallback alias. In theory
`make -C pmoves secrets-sync-trigger` would populate it via the
`sync-secrets-local.yml` GitHub Actions workflow.

In practice this doesn't work for runner-ctl today because:
1. GitHub Actions secret names cannot start with `GITHUB_` (reserved namespace,
   HTTP 422 on `gh secret set GITHUB_PAT`).
2. The alias target `GH_PAT_PUBLISH` is GHCR-scoped (package publishing) —
   insufficient for the runner admin API.

Extending the sync pipeline to carry a dedicated `GH_MONITOR_PAT` source
secret is a Phase 9G.1 follow-up. For now, `make gha-runner-ctl-setup` (or
the fallback operator-PAT path) is authoritative.

---

## Fix B — Runners (GitHub App cascade)

This is NOT part of Phase 9G. It's the known-road runner cycle.

```bash
make -C pmoves ci-runners-local-cert-down
# Load env.shared into the shell so APP_ID/APP_PRIVATE_KEY/RUNNER_* are set:
bash pmoves/scripts/with-env.sh make -C pmoves ci-runners-local-cert-up
make -C pmoves ci-runners-local-cert-status
```

Expected: 3 runners online with labels `self-hosted, ai-lab` / `self-hosted, vps` / `self-hosted, hotfix`.

**Known failure (2026-04-16 observed):** running `ci-runners-local-cert-up`
without the `with-env.sh` prefix exits with `docker run` error 125 because
`APP_ID` and `APP_PRIVATE_KEY` are passed via `-e APP_ID` (which expects
them in the invoking shell's env). `local_cert_runners.py` assumes the
caller has already sourced `env.shared`. The `with-env.sh` wrapper is the
canonical loader (see CLAUDE.md). File as follow-up: teach the tool to
read `env.shared` directly when host env vars are absent.

### Verify via GitHub API

```bash
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners \
  --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

Expected: all 3 `status: "online"`.

---

## Known Gap — NATSPublisher.publish_alert kwarg mismatch

```text
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

- `pmoves/services/github-runner-ctl/github/client.py:50-78` — PAT loader
- `pmoves/docker-compose.yml:3730-3746` — runner-ctl service definition
- `pmoves/env.shared.example` — `GITHUB_PAT` documentation (look for "Phase 9G")
- `pmoves/mk/preflight.mk:55-85` — `ci-runners-*` Make targets
- `pmoves/scripts/with-env.sh` — canonical env.shared loader

## NATS Subjects Affected (once publish_alert is fixed)

- `ops.github.runner.status.v1` (planned)
- `ops.github.runner.alert.v1` (planned)

Currently unpublished due to the `NATSPublisher.publish_alert` follow-up issue.
