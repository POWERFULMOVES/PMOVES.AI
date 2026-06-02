# Jetson JetPack 7.0 Reflash Runbook

**Intent:** Reflash both Jetson Orin Nano devices (Nemotron, NemoClaw — UNFCU
enterprise client) from stale JetPack 6.2.1 → JetPack 7.0 (L4T r37, Ubuntu 24.04,
CUDA 12.8). Matches the 5090's CUDA 12.8 stack so the fleet can share Docker
base images and TensorRT toolchains.

**Sibling runbook:** `../z890/README.md` (Z890 multi-boot bootstrap).

**Fast path:** `deploy/runbooks/jetson-refresh-day.md`

**Helper agent:** `.claude/agents/jetson-refresh-operator.md`

**Why JetPack 7.0 vs in-place 6.x bump?** The user explicitly chose a full
reflash for CUDA 12.8 parity with 5090 and access to the latest NVIDIA
container ecosystem on Ubuntu 24.04. Not reversible without another full
reflash, so schedule during maintenance.

---

## Prerequisites

1. **x86 Ubuntu 22.04 host** with NVIDIA SDK Manager installed (download from
   https://developer.nvidia.com/sdk-manager). **Ubuntu 24.04 is NOT supported
   by SDK Manager at time of writing (2026-04).**
2. **USB-C cable** from host to Jetson recovery port
3. **Jetson in recovery mode** — hold the RECOVERY button while powering on
4. **NVIDIA Developer account** (free) — SDK Manager requires login
5. **Tailscale auth keys** per Jetson via `make -C pmoves fleet-enroll ROLE=edge DEVICE=nemotron-N`
6. **Maintenance window** — full reflash is ~45 min per device, blocking.
   **Avoid during UNFCU demos.**

## Architecture

```
deploy/provision/jetson/
├── README.md                       (this file)
├── jetpack7-reflash.sh             Host-side SDK Manager driver
├── post-flash-bootstrap.sh         Runs ON Jetson after first boot
├── verify-jetson-fleet.sh          Verification from a trusted host
├── nemotron-branding/
│   ├── motd.txt                    /etc/motd banner (Nemotron theme)
│   ├── plymouth-theme/             Boot splash (populate with brand assets)
│   └── README.md                   Branding docs
└── archive/                        JetPack 6.2.1 rollback image cache (populate manually)
```

## Reflash Procedure (per device)

### Step 1: Generate Tailscale auth key

On a trusted PMOVES node (NOT the Jetson being reflashed):

```bash
make -C pmoves fleet-enroll ROLE=edge DEVICE=nemotron-1
# Capture the TAILSCALE_AUTHKEY from output
```

### Step 2: Put Jetson in recovery mode

1. Power off the Jetson completely
2. Connect USB-C from the x86 Ubuntu 22.04 host to the Jetson's recovery port
3. Hold the **RECOVERY** button (physical button on the module)
4. Apply power while still holding RECOVERY
5. Release RECOVERY after 2 seconds
6. Verify on the host: `lsusb | grep -i nvidia` — should show NVIDIA Corp. APX

### Step 3: Run the reflash driver

```bash
# On the x86 Ubuntu 22.04 host:
sudo TAILSCALE_AUTHKEY=tskey-xxx \
  bash deploy/provision/jetson/jetpack7-reflash.sh --device nemotron-1
```

The script:
1. Verifies the host is Ubuntu 22.04 x86_64
2. Confirms SDK Manager CLI is installed
3. Checks that the Jetson is in recovery mode (USB ID match)
4. Invokes `sdkmanager --cli install ...` (~45 min, DO NOT INTERRUPT)
5. Waits for the Jetson to boot + appear on network
6. Copies `post-flash-bootstrap.sh` over SCP and executes on the Jetson

### Step 4: Verify

From the same trusted host (Z890 or another node that can SSH to the Jetson):

```bash
make -C pmoves jetson-verify DEVICE=nemotron-1
```

Seven checks: JetPack version, CUDA 12.8, Docker + GPU, Tailscale online,
NATS reachable, compose services, mesh announce.

### Step 5: Repeat for nemotron-2

Exact same flow. No overlap with nemotron-1 — each is an independent reflash.

## Post-Flash Branding

`post-flash-bootstrap.sh` automatically:
- Sets hostname (nemotron-1 / nemotron-2)
- Installs `/etc/motd` with the ASCII-art NEMOTRON banner (see `nemotron-branding/motd.txt`)
- Copies the Plymouth theme (if populated) to `/usr/share/plymouth/themes/nemotron/`
- Installs the NVIDIA container toolkit
- Joins the Tailnet with tags: `tag:pmoves`, `tag:jetson`, `tag:nemotron`, `tag:edge`, `tag:arm64`
- Clones `/opt/pmoves`
- Installs Ollama + pulls `gemma2:2b` (configurable via `PRELOAD_MODEL`)

## Recovery / Rollback

**If JetPack 7.0 causes issues on a device:**

1. Re-enter recovery mode (hold RECOVERY, apply power)
2. Run `jetpack7-reflash.sh --jetpack 6.2.1 --device nemotron-N` (rollback path)
3. For full disaster recovery, keep a JetPack 6.2.1 SD card image in
   `archive/` — the user should burn + store this BEFORE starting.

**If SDK Manager can't see the device:**

- Check `lsusb` output on the host — recovery-mode Jetson shows as NVIDIA Corp.
- Try a different USB-C port or cable (power-only cables won't work)
- Physical recovery-mode button may need to be held for the full boot sequence,
  not just at power-on — consult the Jetson Orin Nano developer kit manual

## Known Risks

1. **Ubuntu 22.04 x86 host requirement** — SDK Manager is picky. 24.04 won't work.
2. **~45 min per device, non-interruptible** — schedule during demos blackout.
3. **JetPack 7.0 API surface changes** — some JetPack 6.x code may need updates.
4. **Arm64 Docker registry pulls** — ensure the host can fetch arm64 images;
   slow WAN uplinks will extend first-boot time substantially.

## Verification Checklist

After both devices reflashed and verified:

```bash
# Fleet-wide check — should show both nemotron-N online
make -C pmoves fleet-status | grep nemotron

# FlOO$ pipelines reachable — edge nodes can participate in skill chains
make -C pmoves floos-status

# Live mesh announce observation
nats sub 'mesh.gpu.status.v1' &
# ...should see periodic status from pmoves-nemotron-1 and pmoves-nemotron-2
```

## References

- Plan: "Z890 Multi-Boot Bootstrap + Jetson JetPack 7 Update" session plan
- Memory: `project_jetson_nemotron_unfcu.md` — UNFCU client + Jetson theme context
- Memory: `project_jetson_lan_topology.md` — physical LAN / RustDesk setup
- `../z890/README.md` — sibling Z890 multi-boot runbook
- `.claude/context/hardware-profiles.md` — fleet hardware catalog (update JetPack version there after reflash)
- NVIDIA docs: https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html
