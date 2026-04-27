# Fresh-Install Runbook: PMOVES Fleet (Linux track)

Bootable USB provisioning for Linux targets:

1. **9850X3D + dual R9700** — Ubuntu 24.04 Server + ROCm 7.1 + llama.cpp HIP
2. **New Proxmox host** — Debian 13 + PVE 9 answer-file auto-install
3. **DGX Spark** — no USB; stock DGX OS retained, apply overlay via SSH after boot

Windows tracks (Z890, 5090, 4090) are documented separately in `fresh-install-fleet-windows.md`.

## Prerequisites

On the build host (any Linux with root, or Windows WSL2):

```bash
sudo apt install -y xorriso sgdisk coreutils jq curl
# For Proxmox auto-install, also install the assistant (Debian/Ubuntu):
sudo apt install -y proxmox-auto-install-assistant
```

Two USB sticks (32 GB+ recommended, FAT32-formattable) and the 4 TB external drive on hand.

Set these environment variables (match the target node):
- `TAILSCALE_AUTHKEY` — reusable Tailscale pre-auth key (from admin console)
- `CHIT_PASSPHRASE` — optional, for signed provisioning beacons
- `GITHUB_PAT` — required for GitHub Actions runner install on new nodes

## Step 1 — Format the USBs and 4 TB external

**USB 1 + 2** (install media):
```bash
sudo bash deploy/provision/format-usb.sh --device=/dev/sdb --role=install-media --yes-really
sudo bash deploy/provision/format-usb.sh --device=/dev/sdc --role=install-media --yes-really
```

**4 TB external** (PBS backup target for the eventual Proxmox cluster):
```bash
sudo bash deploy/provision/format-usb.sh --device=/dev/sdd --role=pbs-store --yes-really
```

Safety: the format script refuses to touch the system disk and applies a size-band check per role.

## Step 2 — Download ISOs

SHAs in `pmoves/configs/os-images.yaml` are placeholders; verify against upstream
before each run.

```bash
# Ubuntu 24.04 Server amd64
curl -fLO https://releases.ubuntu.com/24.04/ubuntu-24.04.2-live-server-amd64.iso
curl -fsSL https://releases.ubuntu.com/24.04/SHA256SUMS | grep live-server-amd64 | sha256sum -c -

# Proxmox VE 9
curl -fLO https://enterprise.proxmox.com/iso/proxmox-ve_9.0-1.iso
# Verify against https://www.proxmox.com/en/downloads (SHA256 listed on page)
```

## Step 3 — Build and burn installer USBs

**Target A — 9850X3D + dual R9700 (Ubuntu 24.04 autoinstall):**
```bash
sudo bash deploy/provision/build-usb.sh \
  --iso=$PWD/ubuntu-24.04.2-live-server-amd64.iso \
  --autoinstall=deploy/provision/autoinstall/rdna4-workstation.yaml \
  --device=/dev/sdb \
  --hostname=pmoves-9850x3d-r9700 \
  --ssh-keys-from-github=POWERFULMOVES
```

**Target B — New Proxmox host (PVE 9 auto-install):**
```bash
sudo bash deploy/provision/build-usb.sh \
  --iso=$PWD/proxmox-ve_9.0-1.iso \
  --autoinstall=deploy/provision/autoinstall/pve-cluster-node.toml \
  --device=/dev/sdc \
  --hostname=pmoves-pve-01 \
  --generate-root-password \
  --ssh-keys-from-github=POWERFULMOVES
```

The generated Proxmox root password is written to `./root-password-<timestamp>.txt` in
the directory where you run the command. Record it, then delete the file.

Use `--dry-run` first to validate; the script refuses to write to devices >512 GB
unless you pass `--allow-large-device --yes-really` (protects the 4 TB external).

## Step 4 — Pre-reinstall data migration (Z890 only)

The Z890 host (this CLI box) is hitting disk pressure. Before any Windows
reinstall, stage data onto the 4 TB external:

- `.claude/worktrees/` (all)
- Any uncommitted work across worktrees (`git status` per tree first)
- Docker volumes relevant to local dev
- `D:\pinokio\api\*` (creator pipeline data)
- Model caches (`D:\huggingface_cache`, `%APPDATA%\.cache\huggingface`)

Do NOT copy secrets (`.env`, credential files) — regenerate post-reinstall via
`make -C pmoves secrets-funnel`.

## Step 5 — Install

1. Insert the installer USB, boot the target machine, select the USB in UEFI.
2. Autoinstall runs unattended. Expect:
   - Ubuntu: ~8-12 min to first-boot login prompt
   - Proxmox: ~5-8 min, then automatic reboot
3. First-boot hook clones PMOVES.AI and runs `hostinger-kvm-setup.sh` with the
   matching `--node-type`. Watch `/var/log/pmoves-first-boot.log` (Ubuntu) or
   `/var/log/pmoves-pve-first-boot.log` (Proxmox) to track progress.

## Step 6 — Fleet enrollment

After first boot completes:

```bash
# On an operator machine with CHIT_PASSPHRASE available:
make -C pmoves fleet-enroll ROLE=owner DEVICE=pmoves-9850x3d-r9700
make -C pmoves fleet-enroll ROLE=owner DEVICE=pmoves-pve-01
```

Paste/scan the QR on the target node to complete the tailnet join. Verify:

```bash
tailscale status | grep pmoves-9850x3d-r9700
```

## Step 7 — Smoke tests

**RDNA4 workstation:**
```bash
ssh pmoves@pmoves-9850x3d-r9700
rocminfo | head -40                              # should list gfx1201 GPUs
curl http://localhost:8080/v1/models             # llama-server responds
curl http://localhost:9835/ | head -20           # rocm-smi metrics
```

**PVE host:**
```bash
ssh root@pmoves-pve-01
pveversion                                        # PVE 9.x
pvecm status                                      # (no cluster yet — Phase G creates it)
```

## Troubleshooting

- **USB won't boot**: verify UEFI (not legacy BIOS) + Secure Boot disabled on
  RDNA4 workstation (ROCm DKMS needs it off).
- **Autoinstall stalls**: check `/var/log/installer/autoinstall-user-data` on
  the target — syntax errors in user-data land there.
- **First-boot hook fails**: SSH in, run `/usr/local/sbin/pmoves-first-boot.sh`
  manually to surface the error. Check network + `git` availability.
- **amdgpu-dkms won't build**: kernel headers must match the running kernel
  (`apt install linux-headers-$(uname -r)`). Reboot after ROCm install.

## Next phase

After both Linux targets are up, proceed to:
- **Phase C** — register the new hardware in the profile + registry files (5-file atomic commit).
- **Phase G** — create the Proxmox cluster, add the PVE host, set up PBS on the 4 TB external.
- **Phase H** — consider activating Headscale on KVM2 (deferred).
