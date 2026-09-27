# pmoves-disk-cleanup — Fleet Docker Disk Cleanup + Log Rotation

Prevents the recurring disk-fill issue across all PMOVES nodes (Linux + Windows).

## Quick start

### Linux (SPARK, KVMs, B850, Jetson)

```bash
# From any PMOVES.AI checkout:
bash pmoves/scripts/pmoves-disk-cleanup.sh

# For daemon-level log rotation (needs root):
sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh
```

### Windows (Z890, 5090, 4090, Desktop, Missling-Link, Slate)

```powershell
# From PowerShell (Admin) in a PMOVES.AI checkout:

# 1. Disk cleanup (safe — no volumes touched):
docker container prune -f
docker image prune -f
docker builder prune --all -f

# 2. Log rotation — Docker Desktop Settings:
#    Open Docker Desktop → Settings → Docker Engine
#    Add to the JSON config:
#    "log-driver": "json-file",
#    "log-opts": { "max-size": "10m", "max-file": "3" }
#    Click "Apply & Restart"

# OR via PowerShell (writes daemon.json directly):
$path = "$env:USERPROFILE\.docker\daemon.json"
$config = if (Test-Path $path) { Get-Content $path | ConvertFrom-Json } else { @{} }
$config | Add-Member -NotePropertyName "log-driver" -NotePropertyValue "json-file" -Force
$config | Add-Member -NotePropertyName "log-opts" -NotePropertyValue @{ "max-size" = "10m"; "max-file" = "3" } -Force
$config | ConvertTo-Json -Depth 10 | Set-Content $path
# Then restart Docker Desktop
```

## What the scripts do

### pmoves-disk-cleanup.sh (Linux, no root needed)

1. Removes stopped containers (unblocks image deletion)
2. Removes dangling images
3. Prunes ALL build cache
4. **Reclaims inactive buildx builders and their orphaned `buildx_buildkit_*_state` volumes** (`docker buildx rm --all-inactive` + a name-filtered dangling-volume sweep). This **deletes the shared CI cache** (`buildx_buildkit_pmoves-shared0_state`) when no job is using it — the next build on that host starts cold. Right for a sick node; routine bounding is the nightly cap below.
5. Skips volume prune (banned by fleet policy)
6. Reports disk usage before/after
7. Checks if daemon.json + compose tier anchors have log rotation (reports if not)

## The BuildKit builder leak — read this before diagnosing a full disk

`docker system df` will tell you **"Build Cache: 0B"** on a node that is full of build cache. Do not trust it. BuildKit cache for a `docker-container` builder lives inside that builder's `buildx_buildkit_<node>_state` volume, outside everything the usual prunes can see.

There have been two shapes of this leak.

**Before #2021 — one builder per CI run.** `setup-buildx-action` created a new builder (`builder-<uuid>`) per run and never removed it: a running container plus a `buildx_buildkit_builder-<uuid>_state` volume each. Measured 2026-08-06: kvm4-1 reached **193G/0 free**; kvm2 held **15 builders for four weeks (33GB)**. Fixed by the `pmoves-buildx` action (one reused builder, `pmoves-shared`); the nightly reclaim of `buildx_buildkit_builder-*` remains as a safety net.

**After #2021 — one shared builder, unbounded between jobs.** `pmoves-shared` is created at the start of each job and removed at the end with `keep-state`, so between jobs there is a volume (`buildx_buildkit_pmoves-shared0_state`) and **no builder**. Measured 2026-09-27: **139.5GB on kvm4-1, 146.4GB on kvm4-2**, growing 5-9 GiB/day against a 30GB GC cap, while the nightly maintenance succeeded:

| Command | Why it misses the shared volume |
|---|---|
| `docker system prune -af` | Skips volumes entirely |
| `docker builder prune -af` | Reaches only the **default** builder (0B on those hosts) |
| the `buildx_buildkit_builder-*` reclaim loop | Matches only the old per-run names |

**The fix:** [`deploy/provision/pmoves-buildx-cap.sh`](../../../deploy/provision/pmoves-buildx-cap.sh) re-attaches `pmoves-shared` by name (node `pmoves-shared0`, so it mounts the kept volume), runs `docker buildx prune --builder pmoves-shared --all` down to the cap, and detaches with `--keep-state`. It never removes the volume. The action's BuildKit GC config also gained an `all = true` catch-all rule: the single `keepDuration = 168h`, `all = false` rule could never select anything in daily use (`buildx du` on kvm4-2 showed 155.5GB, all of it reclaimable). It runs in every build job (right after attach, from the `pmoves-buildx` action), nightly from `runner-maintenance.yml` and `fleet-docker-cleanup.yml`, and daily from the `docker-fleet-cleanup.sh` systemd timer. Details and the single cap source: [`deploy/runners/BUILDX_PROVISIONING.md`](../../../deploy/runners/BUILDX_PROVISIONING.md).

To bound one host by hand: `bash deploy/provision/pmoves-buildx-cap.sh` (exit 0 bounded or nothing to do, 1 failed, 3 docker unavailable).

## Which hosts are cleaned automatically

`.github/workflows/runner-maintenance.yml` runs nightly at 03:00 UTC, one job per **physical host**, keyed on a label only that host carries — `b850`, `spark`, `kvm4-1`, `kvm4-2`. Its last step bounds the shared builder with `pmoves-buildx-cap.sh`.

Host labels must be unambiguous or coverage silently rots: `kvm4` is carried by *both* VPS runners, so the single job it replaced landed on whichever was free (kvm4-2 usually won; kvm4-1 filled to 100%). `ai-lab` is carried by both b850 runners *and* SPARK, with the same hazard.

**pmoves-kvm2 has no registered runner** and is therefore **not covered** — run the script by hand there. It is no longer a build host, so it accrues no new BuildKit state. If a runner is ever registered on kvm2, add `kvm2` to the workflow matrix.

### pmoves-daemon-log-rotation.sh (Linux, needs root)

1. Reads `/etc/docker/daemon.json` (preserves existing config)
2. Adds `log-driver: json-file` + `log-opts: {max-size: 10m, max-file: 3}`
3. Restarts dockerd

## Log rotation config

Every container gets capped at **30MB of logs** (3 files × 10MB). This prevents the unbounded log growth that fills disks on long-running services (edge-functions restart loops, agent-zero verbose logging, etc.).

Applied at two levels:
- **Docker daemon** (`daemon.json`) — catches ALL containers including non-compose ones
- **Compose tier anchors** (`docker-compose.yml`) — belt + suspenders for PMOVES services

## Fleet deployment

| Node type | Nodes | Method |
|---|---|---|
| Linux with PMOVES checkout | SPARK, KVM4-1, KVM4-2, B850 | Nightly via `runner-maintenance.yml`; manually `make -C pmoves disk-cleanup && sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh` |
| Linux, no runner registered | KVM2 | **Manual only** — `make -C pmoves disk-cleanup` (no nightly job; see above) |
| Linux without checkout | Jetsons | Copy script via Tailscale SCP or run via Agent Zero `/mcp/execute` |
| Windows (Docker Desktop) | Z890, 5090, 4090, Desktop, Missling-Link, Slate | Docker Desktop Settings → Docker Engine JSON, or PowerShell one-liner above |
