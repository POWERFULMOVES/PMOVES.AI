# Autodetect: Provisioning an Unknown System

Short operator runbook for provisioning PMOVES.AI on hardware whose specs
are not yet known — fresh machines, donated systems, community-operator
devices, or the first node in a new cluster.

The autodetect tool samples CPU, RAM, GPU, disk, NIC speed, OS, and
platform hints (Proxmox, DGX OS, Tailscale, Docker), then suggests the
appropriate `hostinger-kvm-setup.sh --node-type`.

---

## When to Use

- **Fresh hardware arrived** — a new rig (e.g., the 9850X3D + R9700 RDNA4 workstation coming online 2026-04-19) and you need to confirm its class before running the full provisioner.
- **Unknown-spec node-operator machine** — a community member joining the PMOVES mesh with a box whose details weren't captured in advance.
- **Onboarding a donated / inherited system** — verify it meets the minimum bar before wiring it into Tailscale + runners.
- **First node in a new Proxmox cluster** — confirm ≥10 GbE + ≥2 NVMe + ≥64 GB RAM before investing in cluster setup.

Do NOT use for:
- Known hosts (KVM4-1, KVM4-2, KVM2, 5090) where the node-type is already documented. Pass the explicit value.
- Windows / WSL hosts. This is a Linux-only tool.

---

## Prereqs

- Linux (Debian / Ubuntu 22.04+ / Proxmox 8+ preferred; works on most distros).
- Root access (`sudo`). Required for `lspci`, `lsblk`, and NIC speed reads.
- Internet access (only if `--install-glances` is used — all core detection works without Glances).

---

## Commands

### 1. Interactive report + suggestion

```bash
sudo bash deploy/provision/glances-autodetect.sh
```

Prints a human-readable report of CPU, RAM, GPU, disks, NICs, platform hints, then emits a suggested node-type with a confidence level (`high` / `medium` / `low`) and rationale.

### 2. Structured JSON for scripting / audit

```bash
sudo bash deploy/provision/glances-autodetect.sh --json
# OR write to a file:
sudo bash deploy/provision/glances-autodetect.sh --json-file=/tmp/specs.json
```

JSON schema is documented in the script header. Stable — never broken between patch versions.

### 3. Quiet single-line for command substitution

```bash
NODE_TYPE="$(sudo bash deploy/provision/glances-autodetect.sh --suggest)"
echo "Autodetect says: $NODE_TYPE"
```

### 4. Install Glances first (optional)

```bash
sudo bash deploy/provision/glances-autodetect.sh --install-glances
```

Tries `apt-get install glances`, then falls back to `pip install --break-system-packages glances`. Glances is a supplement — core spec detection works fine without it.

### 5. Full provisioning via autodetect

```bash
sudo PMOVES_AUTODETECT=1 bash deploy/provision/hostinger-kvm-setup.sh auto
# OR equivalently:
sudo bash deploy/provision/hostinger-kvm-setup.sh auto
```

The provisioner calls `glances-autodetect.sh --suggest` during preflight. If detection returns `unknown`, the run fails with instructions to pass the node-type explicitly — no silent defaults.

---

## Confidence Levels

| Confidence | Meaning | Action |
|---|---|---|
| `high` | Specific hardware signature matched (DGX OS + ARM64, PVE installed, RDNA4 PCI IDs, RTX 5090 model string) | Proceed with suggested value |
| `medium` | Pattern matched but generation/variant inferred, not proven (e.g., multi-AMD-GPU but no gfx1201 model string; cluster-capable NIC/NVMe/RAM but no other hints) | Sanity-check the rationale; override if needed |
| `low` | Fallback match or no pattern matched — hostname-based KVM guess, or `unknown` | **Verify manually before provisioning.** Re-run without `--suggest` for the full spec report. |

---

## Example Outputs

### RDNA4 workstation (Ryzen 9 9850X3D + 2x Radeon AI Pro R9700)

```
CPU:       AMD Ryzen 9 9850X3D (8 phys / 16 logical)
RAM:       32 GB
GPUs:      2 (amd)
           - [amd] AMD/ATI Navi 48 [Radeon AI Pro R9700] (32 GB VRAM)
           - [amd] AMD/ATI Navi 48 [Radeon AI Pro R9700] (32 GB VRAM)
Suggested node-type: rdna4-workstation
Confidence:          high
Rationale:           Detected 2x AMD Radeon RDNA4 (Navi 48/gfx1201) + AMD Ryzen 9 9850X3D + 32 GB RAM
```

### DGX Spark (NVIDIA GB10 Grace + ARM64)

```
OS:        ubuntu 24.04 (kernel 6.11.0-...)
Arch:      aarch64
Platform hints:  is_dgx_os: true
Suggested node-type: dgx-spark
Confidence:          high
Rationale:           Detected DGX OS + ARM64 (aarch64) — DGX Spark-class device
```

### Proxmox member (already provisioned)

```
OS:        debian 13 (kernel 6.8.12-pve-...)
Platform hints:  is_pve: true
Suggested node-type: pve-member
Confidence:          high
Rationale:           Detected /etc/pve or pveversion — host is already a Proxmox node
```

### Fresh PVE-capable host (10 GbE + NVMe)

```
NICs:      3 (max speed: 10000 Mb/s)
Disks:     3 (NVMe count: 2)
RAM:       128 GB
Suggested node-type: pve-member-fresh
Confidence:          medium
Rationale:           Detected ≥10 GbE NIC (10000 Mb/s) + 2x NVMe + 128 GB RAM — candidate for fresh PVE host
```

### Hostinger KVM-class (ambiguous)

```
CPU cores: 6 logical
RAM:       12 GB
Suggested node-type: kvm4-1
Confidence:          low
Rationale:           Detected Hostinger KVM-class specs (6 vCPU, 12 GB RAM) — defaulting to kvm4-1; override manually if this is kvm4-2 or kvm2
```

Hostname hints (`kvm4-1`, `kvm4-2`, `kvm2` substrings) bump confidence to `medium` when they match.

---

## Troubleshooting

### `glances` won't install

The script falls back gracefully — core spec detection uses `lscpu`, `lspci`, `lsblk`, `/etc/os-release`, `/sys/class/net/*/speed`, and `nvidia-smi`. Glances is a supplement, not a requirement.

If `--install-glances` fails with a PEP 668 error (`externally-managed-environment`), the script already passes `--break-system-packages` to pip as a fallback. If both apt and pip fail, just skip the flag and proceed — the tool still works.

### `lspci: command not found`

```bash
sudo apt-get install -y pciutils
```

Without `lspci`, AMD/Intel GPU detection falls back to empty. NVIDIA detection via `nvidia-smi` still works.

### `nvidia-smi` not found on an NVIDIA box

Drivers aren't installed yet. The script falls back to `lspci` parsing — you'll get the PCI ID and model string but `vram_gb` will be 0. Install drivers (for non-DGX systems: `apt-get install -y nvidia-driver-550`) then re-run for accurate VRAM.

### Suggestion is `unknown`

Review the full report — the rationale line lists every dimension that contributed to the decision. Common causes:
- Unusual CPU vendor (e.g., Ampere Altra ARM) not covered by heuristics
- Single-GPU AMD box (doesn't match RDNA4-workstation's ≥2 GPU rule)
- Low-spec cloud VM (fewer than 4 vCPU or less than 8 GB RAM)

Pick a node-type manually and pass it explicitly:
```bash
sudo bash deploy/provision/hostinger-kvm-setup.sh kvm4-1
```

### Root required error

```
[ERROR] This script must be run as root (sudo) for accurate hardware detection.
```

The script reads `/sys/class/net/*/speed` and runs `lspci -v` — both need root for reliable output. `sudo` is non-negotiable.

---

## Override Cheat-Sheet

If autodetect is wrong (which happens when heuristics lose), override manually:

```bash
# Ignore autodetect entirely:
sudo bash deploy/provision/hostinger-kvm-setup.sh kvm4-2

# Run autodetect first to see the report, then override:
sudo bash deploy/provision/glances-autodetect.sh    # read the report
sudo bash deploy/provision/hostinger-kvm-setup.sh kvm2    # commit to your choice
```

There is no silent fallback — passing `auto` to the provisioner with an `unknown` suggestion fails with a non-zero exit code. This is intentional. We do not want to auto-provision a donated rig as a `kvm4-1` when it might be a GPU workstation.
