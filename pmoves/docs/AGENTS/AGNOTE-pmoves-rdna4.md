# AGNOTE: AMD R9700 (RDNA4) Inference Node

## Node: pmoves-rdna4
- **Hardware**: AMD Ryzen 9 9850X3D (8C, 3D V-Cache) + 32 GB DDR5
- **GPU**: 2× AMD Radeon AI PRO R9700 (32 GB VRAM each, 64 GB total, RDNA4 / `gfx1201`)
- **Role**: ROCm-backed inference node, llama.cpp HIP fork (`tlee933/llama.cpp-rdna4-gfx1201` pinned at `a6e76c64`)
- **Server**: `llama-server` on `:8080` (OpenAI-compat: `/v1/chat/completions`, `/v1/models`)
- **Access**: Tailscale `tag:pmoves`, `tag:gpu`, `tag:rdna4`, `tag:production`; ports 8080 (llama-server) + 9835 (rocm-smi exporter)
- **Provider**: TensorZero `llamacpp_rocm` provider points at `http://pmoves-rdna4:8080/v1` (registers post first-boot validation)
- **Default Model**: TBD — capture from `make rdna4-model-pull` after first flash. Script default is `bartowski/gemma-2-27b-it-GGUF`; addendum target is Gemma 4 31B Q4 (single-card) or Gemma 4 31B FP16 (dual-card tensor-split).
- **NATS Subjects**: `mesh.gpu.status.v1` participation (same five mesh.gpu.* streams as DGX Spark — see `pmoves/nats/mesh_gpu_streams.yaml`)
- **Hardware profile**: `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` *(create on first capacity benchmark)*
- **Make integration**: `pmoves/mk/amd-rdna4.mk` (six targets: `rdna4-ssh`, `rdna4-rocm-status`, `rdna4-gpu-status`, `rdna4-llamacpp-status`, `rdna4-llamacpp-up`, `rdna4-model-pull`)
- **Provisioning**: `deploy/provision/rdna4-gpu-install.sh` (sourced by `deploy/provision/hostinger-kvm-setup.sh rdna4-workstation`); cloud-init seed `deploy/provision/autoinstall/rdna4-workstation.yaml`
- **Reflash runbook**: build USB via `deploy/provision/build-usb.sh --iso=ubuntu-24.04...iso --autoinstall=deploy/provision/autoinstall/rdna4-workstation.yaml --device=/dev/sdX`

## Canonical Working Contract
- `pmoves/docs/operations/HARDWARE_PROFILES_JETPACK7_ADDENDUM.md` — fleet-parity addendum (CUDA 12.8 vs ROCm 7.1)
- `pmoves/docs/operations/TOPOLOGY.md` lines 75-97 — RDNA4 node block

The node carries the ROCm side of PMOVES inference parity:
- llama.cpp HIP backend with `gfx1201` kernels (Ollama bundled ROCm v6 cannot serve R9700 as of 2026-04)
- `llama-server` is the OpenAI-compatible surface (drop-in for vLLM/Ollama clients)
- Dual-card tensor-split (`--split-mode row --tensor-split 0.5,0.5`) for FP16 31B-class models
- rocm-smi Prometheus exporter on `:9835` for fleet observability parity with NVIDIA `nvidia-smi` exporter

## Status
- ✅ Hardware profile defined in TOPOLOGY (lines 75-97)
- ✅ Cloud-init autoinstall (`rdna4-workstation.yaml`) — ZFS-mirror or ext4 fallback, SSH key-only
- ✅ ROCm 7.1 + llama.cpp HIP installer (`rdna4-gpu-install.sh`)
- ✅ Make integration (`pmoves/mk/amd-rdna4.mk`)
- ✅ Hostinger node-type wired (`rdna4-workstation` case in `hostinger-kvm-setup.sh`)
- ✅ Tailscale tag scaffolding (`tag:rdna4`)
- ✅ rocm-smi Prometheus exporter (systemd, `:9835`)
- ⏳ USB flash + first boot — pending operator (Phase B of USB Provisioning Sweep)
- ⏳ Tailscale enrollment via `make -C pmoves fleet-enroll ROLE=workstation DEVICE=pmoves-rdna4`
- ⏳ ROCm + dual-GPU verification (`rocm-smi --showmeminfo vram --showuse`)
- ⏳ TensorZero `llamacpp_rocm` provider registration in `tensorzero.toml`
- ⏳ Model registry seed entry (`pmoves/supabase/initdb/12_model_registry_seed.sql`)
- ⏳ `signing_identity_cards.yaml` row for `rdna4-runner` (label: `self-hosted, ai-lab, gpu, rocm, rdna4`)
- ⏳ Hardware profile YAML — `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml`
- ⏳ Capacity benchmark vs RTX 5090 (~99 tok/s for 7B Q4 reference, target Gemma 4 31B Q4 throughput)
- ⏳ `rocm_claw` agent profile activation after first heartbeat on `mesh.gpu.status.v1`

## Three-Body Pattern
- **Delivery**: `z890-claude` (USB flash, post-install hooks, capacity benchmarks)
- **Control**: `make -C pmoves rdna4-rocm-status` + `rdna4-gpu-status` + `rdna4-llamacpp-status` + `fleet-status` gates
- **Memory**: This AGNOTE + AGNOTE4482 USB Provisioning Sweep section + Cipher snapshot of first capacity benchmark

## Near-Term Lane
1. Operator boots AMD box from prepared USB (Phase B1-B2 of USB Provisioning Sweep)
2. First-boot systemd unit (`pmoves-first-boot.service`) clones repo + invokes `hostinger-kvm-setup.sh rdna4-workstation`
3. Reboot to load `amdgpu-dkms`; verify `rocminfo | grep gfx1201`
4. Pull a model: `make -C pmoves rdna4-model-pull HF_REPO=bartowski/google_gemma-4-31B-it-GGUF FILE=gemma-4-31b-it-Q4_K_M.gguf`
5. Start llama-server: `make -C pmoves rdna4-llamacpp-up` (sets `--tensor-split 0.5,0.5` for dual-card)
6. Register TensorZero provider; add `weight = 0.0` cascade variant for safe rollout
7. Add `rdna4-runner` card to `signing_identity_cards.yaml`; populate `rdna4_claw` agent profile after first `mesh.gpu.status.v1` event
8. First capacity benchmark — establish tok/s for {Q4 single-card, FP16 dual-card} on Gemma 4 31B; record in TOPOLOGY

## Known Risks
1. **`amdgpu-dkms` requires reboot** — first-boot script runs ROCm install but llama-server won't start until kernel module loads. Reboot before `rdna4-llamacpp-up`.
2. **gfx1201 is RDNA4-only** — Ollama bundled ROCm cannot serve this hardware; do NOT attempt Ollama installation as a fallback.
3. **ZFS-mirror requires 2× NVMe** — autoinstall fails on single-NVMe boxes. Manual edit to `storage: { layout: { name: direct } }` in `rdna4-workstation.yaml` before USB build if only one NVMe present.
4. **Default model drift** — `rdna4-gpu-install.sh:37` defaults to Gemma 2 27B; addendum / TOPOLOGY assume Gemma 4 31B. First post-install `make rdna4-model-pull` should target Gemma 4 explicitly.

Added: 2026-04-28
