# Docker Daemon Hardening Recommendations

Operational recommendations for Docker daemon configuration on PMOVES.AI hosts.
These settings are daemon-level and cannot be enforced by CI — they require host admin action.

## Image Provenance And Hardened Bases

Docker Content Trust is no longer the primary recommendation for PMOVES images.
Use immutable image digests plus Sigstore/cosign verification for PMOVES-built images,
and prefer Docker Hardened Images or similarly minimized bases for runtime workloads.

### Recommended Baseline

- Pin production image references by digest where operationally practical:
  `image@sha256:...`
- Verify PMOVES-built images with Sigstore/cosign before promotion.
- Keep builder and runtime stages separate so compilers and package managers do not
  ship in the final runtime image.
- Prefer hardened/minimal runtime bases and non-root users.

### PMOVES CI Coverage

The `integrations-ghcr.yml` workflow signs GHCR-published images with cosign and
verifies the resulting digest after push. This is the repo's primary provenance
control for PMOVES-built images.

### Hardened Images And Packages

When adopting Docker Hardened Images:

- Pin the hardened base image by digest, not tag.
- Align package installation with the hardened base's documented package manager.
  For current Docker Hardened Images guidance, that means following the base-specific
  flow rather than assuming Debian/Ubuntu `apt` semantics will carry over.
- Treat hardened-package adoption as an image-by-image migration so builds stay
  reproducible and scanners keep clean signal.

### Legacy Note

Docker's Content Trust documentation is still useful historical context, but it is
not the forward-looking control PMOVES should optimize around. Prefer digest pinning,
cosign signatures, and registry attestations instead.

## Self-Hosted GitHub Actions Runners

For this repo's public PR surface:

- Run untrusted pull request image validation on GitHub-hosted runners.
- Reserve self-hosted runners for trusted `push` and `workflow_dispatch` paths.
- Prefer dedicated runner labels/groups for image builds over broad generic
  self-hosted pools.
- Use ephemeral runners where feasible; otherwise schedule aggressive image/container
  cleanup and review daemon exposure regularly.

## Live Restore

**CIS Benchmark:** 2.14 — "Ensure containers are restricted from acquiring new privileges"

Live restore keeps containers running during Docker daemon restarts and upgrades.
Without it, a daemon restart (e.g., for updates) kills all running containers.

### Enable

Add to `/etc/docker/daemon.json`:

```json
{
  "live-restore": true
}
```

Then restart the daemon:

```bash
sudo systemctl restart docker
```

### Caveats

- Incompatible with Docker Swarm mode
- Containers may lose network connectivity briefly during daemon restart
- Not available on Docker Desktop (Windows/macOS)

## Log Rotation

**The other half of the recurring disk-full failures.** With the default
`json-file` driver and no rotation, container logs grow **unbounded** at
`/var/lib/docker/containers/<id>/<id>-json.log` until they exhaust the root
filesystem — independent of image/build-cache churn. On long-lived fleet nodes
(SPARK, ai-lab/Z890, KVM4) this is a standing exhaustion risk.

Fix it at the **daemon level** so it applies to every container (composed or
ad-hoc) without per-service edits:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" }
}
```

### Per-node-class sizing

| Node class | max-size | max-file | Rationale |
|---|---|---|---|
| ai-lab / Z890 (workstation + runner + inference) | `50m` | `2` | tight root, many services |
| SPARK (full PMOVES.AI node) | `50m` | `3` | full stack |
| KVM4 data tier (VPS) | `100m` | `5` | deeper retention for prod debugging |
| Dev / 4090 (Docker Desktop) | `20m` | `2` | local only |

### Checking a node against its own class

`make -C pmoves docker-host-policy-check` defaults to the `50m` baseline. On a
class documented above it, pass the class ceiling — otherwise the gate rejects
a correctly-provisioned node for honouring the table above:

```bash
# KVM4 data tier
PMOVES_LOG_MAX_SIZE_CEILING_MB=100 make -C pmoves docker-host-policy-check
python pmoves/tools/docker_host_policy_check.py --max-size-ceiling-mb 100
```

Raising the ceiling does not disable the check: a container with no `max-size`
at all is an offender at any ceiling, and anything above the ceiling still
fails.

> **Drift, unresolved (2026-08-21):** the table above sizes ai-lab / Z890 at
> `50m`/`2`, but `deploy/provision/z890/nixos-post.nix` provisions `100m`/`3`.
> One of the two is wrong; which one is a node-owner call, so it is recorded
> here rather than silently reconciled.

> Daemon-level `log-opts` apply only to containers **created after** the change.
> Recreate (`docker compose up -d --force-recreate`) or let natural restarts
> roll existing containers onto the new limits. A per-service compose
> `logging:` block can override the daemon default where one service needs more.

Doc: <https://docs.docker.com/engine/logging/drivers/json-file/>

## Canonical `daemon.json` And Apply Runbook

A version-controlled baseline lives at **`deploy/provision/daemon.json`**,
combining the safe, low-risk settings — log rotation + live restore:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" },
  "live-restore": true
}
```

Riskier hardening (`icc: false`, `userland-proxy: false`) is **intentionally
excluded** — they change container networking semantics and need per-fleet
testing before adoption. An explicit `"storage-driver": "overlay2"` may be
added **only after** confirming `docker info` already reports `overlay2` on the
host — pinning a different driver orphans existing images.

### Apply by lane — never change a running daemon unilaterally

`daemon.json` changes need `systemctl restart docker`, which (even with
`live-restore`) briefly cycles the daemon. Coordinate per lane:

**VPS (KVM4-1/-2, KVM2) — via Hostinger MCP + `vps-deployer` (never raw SSH guessing):**

```bash
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true
# KVM4 data tier: bump to max-size 100m / max-file 5 before installing
sudo install -m 0644 deploy/provision/daemon.json /etc/docker/daemon.json
jq empty /etc/docker/daemon.json            # validate JSON before applying
sudo systemctl reload docker                # SIGHUP re-reads daemon.json WITHOUT
                                            # cycling running containers
```

> **Reload, don't restart, to apply config.** `systemctl reload docker` (SIGHUP)
> re-reads `daemon.json` and applies `log-opts` (to new containers) and enables
> `live-restore` **without stopping running containers**. A `restart` *before*
> `live-restore` is already active will cycle containers — the setting isn't live
> yet — so use `reload` for the rollout. Existing containers keep their old
> `log-opts` until recreated; new containers pick up the limits immediately.
> If a host genuinely needs a `restart` for an unrelated reason, do it in a
> maintenance window. (`reload` applies our options; a few daemon options are
> restart-only, but `log-opts`/`live-restore` are not.)

**ai-lab / Z890 — COORDINATED (claim in `AGNOTE4482PHI.t1.md` first):**
Z890 is workstation + GPU runner + inference host. Apply off-peak (~midnight
UTC), drain CI first (`docker ps | grep -q runner` returns nothing), give a
5-minute warning, confirm no in-flight build, then `systemctl reload docker`
(not restart). Use `max-file: 2`.

**Dev nodes / 4090 (Docker Desktop):** set via Settings → Docker Engine (JSON),
`max-size: 20m`. Desktop ignores `live-restore`.

### Verify

```bash
docker info --format '{{.LoggingDriver}}'   # json-file
docker run --rm hello-world >/dev/null       # create a fresh container
docker inspect $(docker ps -lq) --format '{{json .HostConfig.LogConfig}}'
# -> {"Type":"json-file","Config":{"max-file":"3","max-size":"50m"}}
df -h /var/lib/docker
```

### Rollback

```bash
sudo cp /etc/docker/daemon.json.bak /etc/docker/daemon.json && sudo systemctl reload docker
```

## Stale Container Cleanup

Docker Bench flagged a privileged container (`epic_blackwell`) on the ai-lab
runner host. This is a stale container unrelated to PMOVES.AI services.

### Recommended Cleanup

```bash
# List all containers (including stopped)
docker ps -a

# Remove stale containers
docker container prune

# For periodic cleanup, add a cron job or systemd timer:
# 0 3 * * 0  docker container prune -f --filter "until=168h"
```

### Runner Host Hygiene

Self-hosted GitHub Actions runners accumulate containers and images over time.
Schedule periodic cleanup:

```bash
# Remove stopped containers older than 7 days
docker container prune -f --filter "until=168h"

# Remove dangling images
docker image prune -f

# Full cleanup (safe — excludes volumes)
# Equivalent to: make -C pmoves docker-prune
docker system prune -f --filter "until=72h"
```

## Reference

- [CIS Docker Benchmark v2.0.0](https://www.cisecurity.org/benchmark/docker)
- [Docker Content Trust documentation](https://docs.docker.com/engine/security/trust/)
- [Docker Hardened Images: image digests](https://docs.docker.com/dhi/core-concepts/digests/)
- [Docker Hardened Images: code signing](https://docs.docker.com/dhi/core-concepts/signatures/)
- [Docker Hardened Images: hardened packages](https://docs.docker.com/dhi/how-to/hardened-packages/)
- [Docker Live Restore](https://docs.docker.com/engine/containers/live-restore/)
- [Docker json-file logging driver](https://docs.docker.com/engine/logging/drivers/json-file/)
- Canonical fleet daemon config: `deploy/provision/daemon.json`
- PMOVES.AI Known Roads: `make -C pmoves docker-prune` / `make -C pmoves docker-prune-all`
