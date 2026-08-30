# Z890 Multi-Boot Bootstrap — Operator Runbook

**Intent:** Reimage a single physical Z890 workstation into a multi-boot slot-per-distro
layout (Windows 11 + Ubuntu 24.04 + Pop!_OS 22.04 + Fedora/Nobara 40 + CachyOS + NixOS 23.11),
then bring any slot to PMOVES-ready state from fresh install with a single post-install script.

**Sibling runbook:** `../jetson/README.md` (JetPack 7.0 reflash for Nemotron/NemoClaw).

---

## Prerequisites

1. **Fresh external NVMe** (≥ 2 TB recommended, see `pxe/distro-manifest.yaml:partition_layout`)
2. **USB media source** for fallback installers (plan ships ~8 GB per installer)
3. **5090 PC online** with netboot.xyz for the PXE path (optional — USB path works standalone)
4. **Tailscale auth keys** generated per-distro via `make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-<distro>`
5. **CHIT_PASSPHRASE** (voice-activated) exported in the shell where `fleet-enroll` runs

## Architecture

```
deploy/provision/z890/
├── README.md                       (this file)
├── pxe/
│   ├── netboot-menu-pmoves.ipxe    iPXE chainload menu
│   └── distro-manifest.yaml        ISO URLs, checksums, partition layout
├── media/
│   ├── prepare-usb.sh              Fallback per-device USB installer
│   └── prepare-nvme-target.sh      Pre-partition external NVMe as install target
├── common/
│   ├── 00-glances-profile.sh       Hardware probe → profile.yaml
│   ├── 10-tailscale-enroll.sh      Join tailnet with distro-specific tags
│   ├── 20-docker-install.sh        Docker CE + compose v2 (distro-aware)
│   ├── 30-nvidia-drivers.sh        NVIDIA 3090 Ti driver + container toolkit
│   ├── 40-repo-clone.sh            Clone PMOVES.AI + env-setup + secrets-funnel
│   ├── 50-bootstrap-node.sh        Delegate to claws/bootstrap-node.sh
│   ├── 99-explain.sh               Playlist guidance (Phase 1 stub, Phase 2 Hi-RAG)
│   └── 99-verify.sh                Post-install verification battery
├── ubuntu-24.04-post.sh            Ubuntu orchestrator (primary slot)
├── pop-os-22.04-post.sh            Pop!_OS orchestrator (NVIDIA preloaded)
├── fedora-nobara-post.sh           Fedora + Nobara orchestrator
├── cachyos-post.sh                 CachyOS orchestrator (rolling)
├── nixos-post.nix                  NixOS configuration fragment
└── windows11-post.ps1              Windows 11 orchestrator (extends windows_bootstrap.ps1)
```

## Ordering — First Install

### Step 1: Prepare the NVMe install target

On any running Linux machine (could be the Z890 on an existing Linux slot, or a laptop):

```bash
# Audit: dry-run to see what will be written
sudo bash deploy/provision/z890/media/prepare-nvme-target.sh --device /dev/nvme0n1 --dry-run

# Commit: actually partition (will prompt for 'PARTITION' confirmation)
sudo bash deploy/provision/z890/media/prepare-nvme-target.sh --device /dev/nvme0n1
```

This creates the 10-partition GPT layout documented in `pxe/distro-manifest.yaml`:
EFI + MSR + Windows + shared exFAT + 5 Linux slots + swap.

### Step 2: Install Windows 11 FIRST

Windows installer is aggressive about reclaiming space. Install it *before* any Linux distro:

1. Boot the Windows 11 23H2 ISO (use Rufus to burn per-device USB)
2. Select "Custom install" → install into partition 3 (WIN)
3. Complete first-time OOBE
4. After login, run as Administrator:
   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy/provision/z890/windows11-post.ps1 -TailscaleAuthKey tskey-xxx
   ```
5. Reboot once when prompted.

### Step 3: Install Ubuntu 24.04 (primary Linux slot)

Either path:

**A. PXE (preferred when 5090 is up):**
```bash
# From 5090 node — serves the iPXE menu at the Z890's TFTP/HTTP root
make -C pmoves z890-pxe-serve
# Then boot Z890 and choose F12 → PXE boot
```

**B. USB fallback (reliable, works offline):**
```bash
# From any Linux host
make -C pmoves z890-media-usb DISTRO=ubuntu-24.04 DEVICE=/dev/sdX
```

Install into partition 5 (UBUNTU). After first login:

```bash
# Generate an auth key on a trusted node (NOT the Z890 being enrolled):
make -C pmoves fleet-enroll ROLE=workstation DEVICE=z890-ubuntu
# Copy the TAILSCALE_AUTHKEY it prints, then on the Z890:

sudo TAILSCALE_AUTHKEY=tskey-xxx bash /path/to/deploy/provision/z890/ubuntu-24.04-post.sh
```

Reboot if prompted (NVIDIA driver activation).

### Step 4: Add remaining Linux distros incrementally

Repeat Step 3 for each distro slot using its specific post-install script:

| Slot | Post-install script |
|------|---------------------|
| 6 — Pop!_OS      | `pop-os-22.04-post.sh` |
| 7 — Fedora/Nobara| `fedora-nobara-post.sh` |
| 8 — CachyOS      | `cachyos-post.sh` |
| 9 — NixOS        | Import `nixos-post.nix` → `nixos-rebuild switch` → then run common/*.sh |

## Verification

After any slot comes up:

```bash
# On the Z890, in the slot you just brought up
sudo bash /opt/pmoves/deploy/provision/z890/common/99-verify.sh

# Or equivalently via Make once the repo is cloned
make -C pmoves z890-verify
```

Six categories checked: profile.yaml, Tailscale, Docker, NVIDIA, NATS leaf,
Hi-RAG roundtrip. Exit 0 = slot is PMOVES-ready.

## Playlist Guidance (Phase 1 stub / Phase 2 Hi-RAG)

```bash
# Phase 1 (now): prints pointers to distro-manifest.yaml
bash deploy/provision/z890/common/99-explain.sh --step 3 --topic "nvidia driver"

# Phase 2 (after 5090-claude's YT-pipeline fix PR merges):
# Replace 99-explain.sh with live Hi-RAG v2 query implementation.
# Playlist to ingest: https://www.youtube.com/playlist?list=PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8
/yt:add-playlist https://www.youtube.com/playlist?list=PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8
```

## Recovery

- **Bad Linux install:** partitions 5-9 are independent; reinstall any one without touching others
- **Windows slot broken:** reinstall Windows into partition 3; `efibootmgr` will re-register
- **EFI table corrupted:** boot any Linux USB → `efibootmgr --create --disk /dev/nvme0n1 --part 1 ...`
- **All NVMe lost:** re-run Step 1. The manifest is the source of truth for the rebuild.

## Known Risks

See the plan document (§ Open Risks) for the complete list. Highlights:

1. **PXE chicken-and-egg** if Z890 is the 5090's DHCP host. Fallback: `z890-media-usb`.
2. **NixOS declarative** — common/*.sh scripts are no-ops for packages; Nix owns that.
3. **Windows slot placement** — always install Windows BEFORE any Linux slot.
4. **Phase 2 playlist content** may recommend distros outside our list; review before adding.

## References

- Plan document: Z890 Multi-Boot Bootstrap + Jetson JetPack 7 Update (this session's working plan)
- `pxe/distro-manifest.yaml` — canonical ISO/checksum/partition source
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — Tailscale + RustDesk enrollment
- `pmoves/scripts/claws/bootstrap-node.sh` — reused verbatim by `common/50-bootstrap-node.sh`
- `pmoves/scripts/z890_host_setup.ps1` — reused verbatim by `windows11-post.ps1`
- Sibling runbook: `../jetson/README.md`
