# Docker Desktop WSL2 silent-bind class — per-host operator fix

**Symptom:** A service's compose `ports:` declares a host bind (e.g. `0.0.0.0:8105:3000`), the container is healthy, but the host cannot reach the service. `docker ps` shows only the container-side port (e.g. `3000/tcp`) with no host publish prefix, even though the compose declaration is correct.

**Class:** Docker Desktop on Windows with WSL2 backend silently drops some non-loopback host binds on this host's networking stack. The container starts, the internal port works, the publish line is silently ignored. `docker inspect` may report `HostConfig.PortBindings` populated while `NetworkSettings.Ports` is empty.

**Scope:** Per-host pathology, not a repo-level configuration problem.

## Why not "just change the compose default"

The compose default `${CIPHER_BIND:-0.0.0.0}` (and the equivalent for any pore service: Cipher, A2UI NATS Bridge, etc.) is intentional. Per the MOF (Metal-Organic Framework) topology, every node is a pore in the lattice — services need to be reachable from any other node via Tailscale mesh. Flipping the default to `127.0.0.1` would close the pore to the fleet and regress cross-node connectivity. **Do not edit `pmoves/docker-compose.yml` to fix a host-local binding issue.**

## Operator fix options (pick one)

### Option A — Host-local env override (recommended)

Add the override to your **uncommitted** `pmoves/env.shared` file on the affected host only. This is the secrets-funnel input and is gitignored; it does not propagate to the repo.

```bash
# Append to pmoves/env.shared on the affected host:
CIPHER_BIND=127.0.0.1
# (or any other service exhibiting the same class)
```

Then re-funnel and re-bring-up just the affected service:

```bash
make -C pmoves secrets-funnel
make -C pmoves up-cipher
```

Verify with:

```bash
docker ps --filter name=cipher --format '{{.Names}}\t{{.Ports}}'
# Expect: pmoves-cipher-api-1   0.0.0.0:8105->3000/tcp (or 127.0.0.1:8105->3000/tcp with the override)
curl -fsS http://localhost:8105/health   # Expect HTTP 200 / healthy JSON
```

### Option B — Docker Desktop settings adjustment

Settings → Resources → Network → review WSL integration / mirrored mode. Some Docker Desktop versions need mirrored networking mode enabled for non-loopback binds to take effect from the host. Restart Docker Desktop after changing.

### Option C — Container-side reach (sidecar)

If options A and B fail, reach the service from inside the `pmoves_bus` Docker network using its internal DNS name (`cipher-api:3000`). This requires the client to also run as a container in the same network, so only applicable when the host-Claude process is in fact a container.

## What this is NOT

- Not a repo bug — do not open a PR to flip compose defaults.
- Not a "secrets funnel ran wrong" — `make secrets-funnel` pulls the right env, the issue is downstream in Docker Desktop's port-publish path.
- Not specific to Cipher — applies to any service whose host-bind silently drops on this Docker Desktop host. Cipher is the most common symptom because cross-session memory and trail-signing flows through it.

## Verify after fix

```bash
# 1. Container has a host publish (not bare "3000/tcp"):
docker ps --filter name=<service> --format '{{.Names}}\t{{.Ports}}'

# 2. Host reaches the service:
curl -fsS http://localhost:<host-port>/health

# 3. The compose default is unchanged in main:
grep -nE 'CIPHER_BIND' pmoves/docker-compose.yml
# Expect: - "${CIPHER_BIND:-0.0.0.0}:${CIPHER_PORT:-8105}:3000"
```

## Related

- `pmoves/docs/operations/BRING_UP_WSL2.md` — first-run WSL2 setup
- `pmoves/docs/AGENTS/AGNOTE4482.md` — MOF pore-lattice rationale
- Compose default for Cipher: `pmoves/docker-compose.yml` (search `CIPHER_BIND`)
