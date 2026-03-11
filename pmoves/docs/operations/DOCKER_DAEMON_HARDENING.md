# Docker Daemon Hardening Recommendations

Operational recommendations for Docker daemon configuration on PMOVES.AI hosts.
These settings are daemon-level and cannot be enforced by CI — they require host admin action.

## Content Trust (Image Signing)

**CIS Benchmark:** 4.5 — "Enable Content trust for Docker"

Content trust ensures that only signed images are pulled from registries.

### Enable Globally

Add to `/etc/docker/daemon.json` (Linux) or Docker Desktop settings:

```json
{
  "content-trust": {
    "mode": "enforce"
  }
}
```

Or set the environment variable for all Docker CLI sessions:

```bash
# Add to /etc/environment or shell profile
export DOCKER_CONTENT_TRUST=1
```

### CI Coverage

The `hardening-validation.yml` workflow sets `DOCKER_CONTENT_TRUST=1` at the
job level for the Docker Bench job. This ensures CI itself practices content
trust during image pulls.

**Note:** SHA-pinned images (`image@sha256:...`) bypass content trust entirely —
they are already verified by digest, which is a stronger guarantee than signature
verification alone.

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
- [Docker Live Restore](https://docs.docker.com/engine/containers/live-restore/)
- PMOVES.AI Known Roads: `make -C pmoves docker-prune` / `make -C pmoves docker-prune-all`
