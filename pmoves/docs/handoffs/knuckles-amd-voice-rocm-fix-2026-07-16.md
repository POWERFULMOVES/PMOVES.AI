# Handoff — Knuckles AMD ROCm voice override: runtime fixes

**Node:** B850 "Knuckles" (dual R9700, RDNA4/gfx1201)
**Agent:** B850-CLAUDE
**Date:** 2026-07-16
**Upstream handoff:** CRUSH "Knuckles Convergence" entry in `docs/AGENT_TRAIL.md`
**File opened:** `pmoves/docker-compose.amd-voice.yml` (untracked/new — authored by CRUSH, never committed)

## Why this Known Road

CRUSH left `docker-compose.amd-voice.yml` behind with an explicit caveat:

> "**Flute-Gateway compose integration**: AMD override exists but full build hasn't been tested
> end-to-end... Test `make up-voice-amd` with a full Docker build to validate the ROCm override
> works in practice (not just YAML validation)."

Docker is running on Knuckles, which has the actual RDNA4 hardware, so the untested claim was
testable here. Testing it found the override **cannot work as written**. These are the fixes.

## Bugs found (each verified on this node, not inferred)

### 1. `driver: amd` device reservation — container never starts

```yaml
deploy: {resources: {reservations: {devices: [{driver: amd, count: 1, capabilities: [gpu]}]}}}
```

Docker's device-reservation API only implements the `nvidia` driver. `driver: amd` **passes
`docker compose config`** — which is exactly why the "YAML validated" claim held — but fails at
container start:

```
Error response from daemon: failed to discover GPU vendor from CDI: no known GPU vendor found
```

**Fix:** drop the `reservations.devices` block (keep `limits`). ROCm is wired through
`/dev/kfd` + `/dev/dri` passthrough, which needs no reservation. Verified: container starts and
sees both render nodes.

### 2. `group_add: video` — EACCES on `/dev/kfd`

`group_add` resolves group *names* against the **container image's** `/etc/group`, not the host's.

| | `render` | `video` |
|---|---|---|
| host (Knuckles) | **110** ← owns `/dev/kfd` | 44 |
| container (alpine) | *(absent)* | 27 |

No value of `video` ever equals the host's `render` gid, so the container cannot open `/dev/kfd`.
Probed with `os.open('/dev/kfd', O_RDWR)`, distinguishing errnos:

```
group_add=video -> EACCES_PERMISSION_DENIED
group_add=110   -> OPEN_OK
```

**Fix:** numeric GID, parameterized as `${RENDER_GID:-110}` since the gid is host-specific.
Operators find theirs with `getent group render | cut -d: -f3`.

> Probe caveat for whoever re-tests: `/dev/kfd` is ioctl-only and rejects `read()` regardless of
> permission, so a `head -c1 /dev/kfd` probe reports a **false** denial even for a correct gid.
> Use `os.open(O_RDWR)` and check for `EACCES` specifically.

## Verified on this node

- Host: `/dev/kfd` gid 110 (`render`); `/dev/dri/renderD128`, `renderD129` (dual R9700).
- Corrected override: container starts, ROCm devices present, `/dev/kfd` opens `O_RDWR`.

## Still NOT verified (unchanged from CRUSH's caveat)

Neither CRUSH's version nor this fix has run **Ultimate TTS with a real ROCm base image**. The
fixes prove the *container can start and reach the GPU devices*; they do not prove the TTS engine
synthesizes audio on RDNA4. `HSA_OVERRIDE_GFX_VERSION=12.0.1` and the chatterbox/fish/voxcpm
compatibility matrix remain CRUSH's untested claims. A full `make up-voice-amd` build is still the
open gate.

## Scope

`compose:` opens only `pmoves/docker-compose*.yml`. No migrations, contracts, or secrets touched.
