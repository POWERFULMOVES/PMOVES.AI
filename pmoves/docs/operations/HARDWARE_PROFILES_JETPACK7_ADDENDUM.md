# Hardware Profiles — JetPack 7.0 + Z890 Multi-Boot Addendum

**Status:** 2026-04-21 — Companion to `.claude/context/hardware-profiles.md`.

The canonical `hardware-profiles.md` is in the damage-control `readOnlyPaths`
tree (`.claude/context/`), so this addendum captures the session-plan updates
until a tooling-approved merge can happen. `TOPOLOGY.md` already links here.

## JetPack 7.0 Rollout (deprecates JetPack 6.2.1)

| Property | Value |
|---------|-------|
| L4T release | r37 |
| Base OS | Ubuntu 24.04 |
| CUDA | 12.8 (matches 5090) |
| PyTorch base image | `dustynv/pytorch:2.8-r37.0-cu128-24.04` |
| Canonical image | `nvcr.io/nvidia/l4t-jetpack:r37.0.0` |
| Reflash runbook | `deploy/provision/jetson/README.md` |
| Time per device | ~45 min |
| Doc-side drift-verified | 2026-04-28 (USB Provisioning Sweep — no findings against `jetpack7-reflash.sh` / `post-flash-bootstrap.sh` / `verify-jetson-fleet.sh`) |
| nemotron-1 reflash | ⏳ operator-pending (Phase C of USB Provisioning Sweep) |
| nemotron-2 reflash | ⏳ operator-pending (Phase C of USB Provisioning Sweep) |
| Hard prerequisite | x86_64 Ubuntu 22.04 host with NVIDIA SDK Manager CLI — Z890 currently Win11; Path A live USB or Path B Pop!_OS 22.04 slot |

**Deprecated:** `nvcr.io/nvidia/l4t-jetpack:r36.4.4` (JetPack 6.2.1).
**Migration path:**

```bash
# On x86 Ubuntu 22.04 host with SDK Manager installed, Jetson in recovery mode:
make -C pmoves jetson-reflash DEVICE=nemotron-1
make -C pmoves jetson-reflash DEVICE=nemotron-2

# Verify from trusted node:
make -C pmoves jetson-verify DEVICE=nemotron-1
make -C pmoves jetson-verify DEVICE=nemotron-2
```

## AMD R9700 (RDNA4) Rollout — Sibling to JetPack 7

The USB Provisioning Sweep (2026-04-28) bundles AMD R9700 first-flash with the
Jetson reflash since both share the Ubuntu 22.04 build-host prerequisite.

| Property | Value |
|---------|-------|
| Build USB tool | `deploy/provision/build-usb.sh` (auto-detects Ubuntu vs Proxmox ISO; refuses devices > 512 GB) |
| Cloud-init seed | `deploy/provision/autoinstall/rdna4-workstation.yaml` |
| GPU stack installer | `deploy/provision/rdna4-gpu-install.sh` (sourced by `hostinger-kvm-setup.sh rdna4-workstation`) |
| ROCm version | 7.1 |
| llama.cpp fork | `tlee933/llama.cpp-rdna4-gfx1201` pinned at `a6e76c64` |
| Server | `llama-server` on `:8080` (OpenAI-compat) |
| Metrics | rocm-smi Prometheus exporter on `:9835` |
| Default model | `bartowski/gemma-2-27b-it-GGUF` (script default) — operator should override to Gemma 4 31B for fleet parity via `make rdna4-model-pull HF_REPO=bartowski/google_gemma-4-31B-it-GGUF FILE=gemma-4-31b-it-Q4_K_M.gguf` |
| Doc-side drift-verified | 2026-04-28 — 5 doc-only path/flag drifts in plan vs filesystem; 1 real script bug fixed (`rdna4-gpu-install.sh:51` missing `log_section` function) |
| pmoves-rdna4 first flash | ⏳ operator-pending (Phase B of USB Provisioning Sweep) |
| Node doc | [`pmoves/docs/AGENTS/AGNOTE-pmoves-rdna4.md`](../AGENTS/AGNOTE-pmoves-rdna4.md) |

## Z890 Multi-Boot Slot Map

Z890 is a **multi-boot workstation** after the session-plan rebuild.
Partition layout source: `deploy/provision/z890/pxe/distro-manifest.yaml`.

| Partition | Slot | Size | Post-install script |
|-----------|------|------|---------------------|
| 1 | EFI | 1 GiB | — |
| 2 | Windows MSR | 16 MiB | — |
| 3 | Windows 11 23H2 | 300 GiB | `windows11-post.ps1` |
| 4 | Shared exFAT | 500 GiB | cross-OS data partition |
| 5 | Ubuntu 24.04 | 200 GiB | `ubuntu-24.04-post.sh` |
| 6 | Pop!_OS 22.04 | 150 GiB | `pop-os-22.04-post.sh` |
| 7 | Fedora / Nobara 40 | 150 GiB | `fedora-nobara-post.sh` |
| 8 | CachyOS | 150 GiB | `cachyos-post.sh` |
| 9 | NixOS 23.11 | 200 GiB | `nixos-post.nix` + common/*.sh |
| 10 | swap | 32 GiB | shared by Linux slots |

**Tailscale hostnames** follow the pattern `pmoves-z890-<distro>` so every
slot is individually addressable in the admin console and ACLs.

**Common modules** (`deploy/provision/z890/common/`) run after per-distro
baseline for all Linux slots:

| Module | Purpose |
|--------|---------|
| `00-glances-profile.sh` | Write `/opt/pmoves/profile.yaml` (hardware truth layer) |
| `10-tailscale-enroll.sh` | Join tailnet with distro-specific tags |
| `20-docker-install.sh` | Docker CE + compose v2 (distro-aware) |
| `30-nvidia-drivers.sh` | RTX 3090 Ti driver + nvidia-container-toolkit |
| `40-repo-clone.sh` | Clone PMOVES.AI + env-setup + secrets-funnel |
| `50-bootstrap-node.sh` | Delegate to `pmoves/scripts/claws/bootstrap-node.sh` |
| `99-explain.sh` | Phase 1 stub for playlist guidance (Phase 2 → Hi-RAG v2) |
| `99-verify.sh` | Full verification sweep (6 categories) |

## Cross-Node Dockerfile Parity After Reflash

Once both Jetsons are on JetPack 7.0 + CUDA 12.8, the fleet can share a
single base image strategy between 5090 and Jetson:

```dockerfile
# 5090 + Jetsons share this base tag
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

# PyTorch with CUDA 12.8 (works on both)
FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime
```

This removes the branching logic in Dockerfiles that previously had to
account for `CUDA 12.4 (JetPack 6.2.1) vs CUDA 12.8 (5090)`.

## Related Reading

- `deploy/provision/jetson/README.md` — reflash runbook
- `deploy/provision/z890/README.md` — multi-boot runbook
- `pmoves/docs/operations/TOPOLOGY.md` — updated node inventory
- `pmoves/bootstrap/registry.json` (section `jetson-fleet`) — env var contract
- Sibling file: `deploy/provision/jetson/arm64-jetpack7-compose-fragment.yaml` —
  arm64 compose service entries to merge into the canonical override during a
  tooling-approved session
