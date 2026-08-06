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
4. Prunes dangling volumes (safe — only orphans)
5. Reports disk usage before/after
6. Checks if daemon.json + compose tier anchors have log rotation (reports if not)

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
| Linux with PMOVES checkout | SPARK, KVM4-1, KVM4-2, KVM2, B850 | `make -C pmoves disk-cleanup && sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh` |
| Linux without checkout | Jetsons | Copy script via Tailscale SCP or run via Agent Zero `/mcp/execute` |
| Windows (Docker Desktop) | Z890, 5090, 4090, Desktop, Missling-Link, Slate | Docker Desktop Settings → Docker Engine JSON, or PowerShell one-liner above |
