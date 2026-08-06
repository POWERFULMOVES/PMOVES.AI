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
4. **Reclaims stale buildx builders (>24h)** — see below; this is the one that actually recovers tens of GB
5. Skips volume prune (banned by fleet policy)
6. Reports disk usage before/after
7. Checks if daemon.json + compose tier anchors have log rotation (reports if not)

## The BuildKit builder leak — read this before diagnosing a full disk

`docker system df` will tell you **"Build Cache: 0B"** on a node that is 100% full because of build cache. Do not trust it.

`setup-buildx-action` creates a **new builder per CI run** and never removes it. Each builder is a running container plus a named `buildx_buildkit_builder-<uuid>_state` volume, and **the cache lives inside that volume** — outside everything the usual prunes can see:

| Command | Why it misses the leak |
|---|---|
| `docker system prune -af` | Skips volumes entirely |
| `docker builder prune -af` | Clears cache *inside* builders, leaves the builders and their volumes standing |
| `docker volume rm buildx_…` | Cannot remove a volume attached to a **running** container — and every leaked builder is running |

The builder itself has to go first: `docker buildx rm <builder>`. Step 4 of the script does this for anything older than 24h (the floor protects an in-flight build).

Measured 2026-08-06: kvm4-1 reached **193G/0 free** this way; kvm2 was holding **15 builders alive for four weeks (33GB)** and dropped from 61% to 26% once they were removed.

## Which hosts are cleaned automatically

`.github/workflows/runner-maintenance.yml` runs nightly at 03:00 UTC, one job per **physical host**, keyed on a label only that host carries — `b850`, `spark`, `kvm4-1`, `kvm4-2`.

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
