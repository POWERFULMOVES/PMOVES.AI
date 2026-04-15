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
- PMOVES.AI Known Roads: `make -C pmoves docker-prune` / `make -C pmoves docker-prune-all`
