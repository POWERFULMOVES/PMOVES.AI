# B850-CLAUDE — Node Profile

> Operational reference for the Claude agent running on the **B850 "Knuckles"** workstation. Load at session start; sibling of `pmoves/docs/NODE_PROFILES/4090-CLAUDE.md`.

## Identity

- **Node**: B850 "Knuckles" (Gigabyte B850 AI TOP motherboard)
- **Hostname**: `pmoves-b850-ai-top`
- **Tailscale IP**: `100.122.182.3`
- **Canonical AGNOTE name**: `B850-CLAUDE (Knuckles)` (use this exact form in `AGNOTE4482PHI.t1.md` CLAIM/RELEASE entries)
- **OS**: Ubuntu 24.04.4 LTS (kernel `6.8.0-117-generic`, x86_64)
- **CHIT integration**: partial (consumes signed trails; does not directly sign yet)

> **Identity hygiene**: B850 ≠ Z890. Z890 is a separate multi-boot workstation (RTX 3090 Ti). B850 is the R9700-target box per `pmoves/docs/operations/TOPOLOGY.md` (annotated alias landed via PR #1501). Prior session entries in the AGNOTE register that mis-attributed B850 work to `Z890-CLAUDE` have been corrected in PR #1496 (May 2026 sweep) and PR #1504 (March 2026 sweep).

## Hardware

Verified via `lspci -nn -d 1002:`, `/sys/class/dmi/id/*`, `lscpu`, `free -h` on 2026-05-16:

| Component | Value | Source |
|-----------|-------|--------|
| Motherboard | **Gigabyte B850 AI TOP** | `/sys/class/dmi/id/board_name` |
| BIOS | F4 / 2025-02-17 (AMI) | `/sys/class/dmi/id/bios_version` |
| CPU | AMD Ryzen 7 9850X3D (8C / 16T) | `lscpu` |
| RAM | 30 GiB usable (32 GB DIMM; ~2 GB hardware-reserved) | `free -h` — see TOPOLOGY.md L81 which says "32GB DDR5" (DIMM spec); both are correct at different precision |
| GPU 1 | **AMD Radeon AI PRO R9700** (PCI `1002:7551`, rev c0, gfx1201, RDNA4) | `lspci -nn -d 1002:7551` @ `04:00.0` |
| iGPU | AMD Rembrandt iGPU (PCI `1002:13c0` @ `12:00.0`) — NOT used for ROCm | same scan |
| PCIe slot 2 (x16) | **Empty at kernel level** — 2nd R9700 operator-pending | `lspci -tv` |
| NVMe | Samsung S4LV008 (Pascal) @ `01.2` | `lspci -tv` |
| NICs | Marvell Aquantia AQC113C (×2, 10 GbE) @ `08:00.0` + `0e:00.0` | `lspci -tv` |

**GPU note**: card0 in `/sys/class/drm/` is still pointed at `simple-framebuffer.0` (UEFI fallback), not the full amdgpu driver path. The ROCm installer (`deploy/provision/rdna4-gpu-install.sh`) will pull `amdgpu-dkms` which fixes the binding.

## Role in the mesh

**CLI orchestrator** per user signal 2026-05-16: *"claude master of cli and can run agent zero from here scope massive still as you can connect to agent zero and archon from cli."*

B850 is the host the Claude Code CLI runs from. It drives multi-node coordination via Tailscale-reachable remote services. It is NOT a heavyweight inference producer until ROCm Phase-C completes (CO-5 — operator-pending).

Per `.claude/PATTERNS.md` § "Node-affinity team aggregations" (PR #1498), B850-CLAUDE participates in:

| Team | Co-members | Skills owned |
|------|-----------|--------------|
| **Substrate** | 4090 | `pmoves-mesh-preflight`, `pmoves-submodule-fleet` |
| **Doc steward** | 5090 | `pmoves-living-docs-refresh`, `pmoves-submodule-fleet` |

The PATTERNS section names "Z890" for these teams — that's the legacy reference. B850 Knuckles is the actual host running these workflows; Z890 (3090 Ti box) and B850 are distinct nodes.

## Current state (2026-05-17)

- **Vanilla Ubuntu, no GPU drivers installed**: ROCm 7.1 + amdgpu-dkms still needed. `/dev/kfd` exists (kernel-side KFD) but full driver stack pending.
- **Docker**: NOT installed. Any local containerized service (Agent Zero, Archon, channel-monitor) deferred until Docker bringup.
- **uv**: ✅ Installed at `~/snap/code-insiders/2398/.local/bin/uv` (v0.11.14). ⚠️ Snap-versioned path — will shift on VS Code snap update. Add `PATH=$HOME/snap/code-insiders/current/.local/bin:$PATH` to `.bashrc` for stability. Per the memory note `feedback_bringup_venv_uv.md`, bringup tooling lives in `pmoves/.venv-pmoves/` via uv.
- **`pmoves/.venv-pmoves/`**: ✅ Populated. Contains `glances` 4.5.4, `psutil`, `PyYAML` (per Wave-0 venv-bringup target landed in PR #1496).
- **System binaries gap**: `make` NOT installed (`check_prereqs.sh` flags this). Operator action via `sudo apt install build-essential`.
- **`gh` CLI**: ✅ Installed at `~/snap/code-insiders/2398/.local/bin/gh` (v2.92.0) and authenticated. Same snap-path caveat as `uv` above.

## Connected services from this node

All probed via Tailscale on 2026-05-16:

| Target | Address | State | Notes |
|--------|---------|-------|-------|
| **Agent Zero** | `http://pmoves-powerfulmoves:8080` | ✅ live (v0.9.8.2) | NATS-connected to JetStream `AGENTZERO` stream; 14 REST endpoints + 16 MCP commands. See [`pmoves/docs/operations/AGENT_ZERO_API.md`](../operations/AGENT_ZERO_API.md). |
| **Archon** | `http://pmoves-powerfulmoves:8091` | ✅ live | `/healthz` returns 200. Mint flow (Wave 2 service-side) still pending. |
| Channel Monitor | `:8097` | ❌ not running | Service down on every Tailscale peer probed. Required for the YouTube playlist research path. |
| TensorZero gateway | `:3030` | ⏸ untested from B850 | If needed by a local Agent Zero variant, reach via Tailscale. |
| NATS | `:4222` / `:8222` monitor | ⏸ untested | Probably reachable on 5090; not required from B850 CLI until Agent Zero MCP needs it. |

> CLI orchestration pattern: `curl http://pmoves-powerfulmoves:8080/mcp/commands` to enumerate; `curl -XPOST http://pmoves-powerfulmoves:8080/mcp/execute -d '{...}'` to act. See AGENT_ZERO_API.md for canonical examples.

## CO carry-over state (2026-05-15 → 2026-05-17)

Tracked in this session's task list; on-disk evidence in AGNOTE register entries (search `B850-CLAUDE`).

| CO | Description | State |
|----|-------------|-------|
| CO-1 | Submodule init (50+ submodules) | ✅ Done (no PR — local op) |
| CO-2 | Profile naming drift (workstation_5090 → desktop-9950xd) | ✅ Already-resolved on main (apply_profile.sh default is `desktop-9950xd`; `workstation_5090.yaml` marked DEPRECATED `alias_of`) |
| CO-3 | ClaWZ fork sync (27,974 commits behind upstream) | ✅ PR #1511 MERGED |
| CO-4 | GLM-5V-Turbo SDK MODELS dict | ✅ Self-resolved by CO-3 (upstream's `extensions/zai/openclaw.plugin.json:79` includes `glm-5v-turbo`) |
| **CO-5** | **ROCm Phase-C bringup** | ⏸ **Operator-pending sudo** — `sudo bash deploy/provision/rdna4-gpu-install.sh` |
| **CO-6** | **2nd R9700 slot verification** | ⏸ **Post-ROCm + possible reboot** — BIOS / PCIe bifurcation / hardware seating check |
| CO-7 | Local AZ bringup on B850 | ✅ Closed via CO-7a (use remote AZ from CLI; user pivot 2026-05-16) |
| CO-7a | Connect to remote AZ from B850 CLI | ✅ Closed (Tailscale-reachable AZ at pmoves-powerfulmoves:8080) |
| **CO-8** | **YouTube playlist research** | 🟡 **Owner: Agent Zero** (per user 2026-05-16 "has permissions") — awaits playlist URL or channel-monitor bringup |
| **CO-9** | **AZ → Archon mint orchestration** | 🟡 **Owner: Agent Zero** — downstream of CO-8 |

## Provisioning (`b850-*` make targets)

Run on B850 itself (the targets refuse to run on other hosts; override with `IS_B850_LOCAL=1`). Each one asks for sudo. Run them from your own account, not from a root login.

| Step | Target | Script |
|------|--------|--------|
| 1 | `make -C pmoves b850-bootstrap` | `deploy/provision/b850-bootstrap.sh`: Docker, uv (sha256-verified), gh, bringup venv, `/opt/pmoves` checkout + `profile.yaml` |
| 2 | `make -C pmoves b850-gpu-install` | `deploy/provision/rdna4-gpu-install.sh --dual-gpu` (ROCm, amdgpu-dkms, llama.cpp HIP at `LLAMA_CPP_PIN`) |
| 3 | reboot | |
| 4 | `make -C pmoves b850-postinstall` | `deploy/provision/rdna4-postinstall.sh --model-pull`. Exit 0 = pass. Exit 1 = a finding. Exit 3 = could not measure: rocm-smi or jq unusable. Without a model the output reads "CONFIGURED, NOT STARTED", and the step still passes (exit 0). |
| any | `make -C pmoves b850-health` | GPU + llama-server + ROCm metrics |

**`/opt/pmoves` layout.** `/opt/pmoves` is a PMOVES.AI git checkout owned by the operator, which is the layout `hostinger-kvm-setup.sh` and `rdna4-gpu-install.sh` expect. `profile.yaml` and `.node-config` live at the checkout root, and `.gitignore` ignores both.

**Migrating the legacy layout.** Older bootstraps created `/opt/pmoves/{bin,data,etc,lib,logs}` + `profile.yaml`, owned by the `pmoves` user, with no `.git`. B850 still has this layout. The bootstrap now detects it before installing anything. It stops with exit 1 and prints the exact commands. It never moves the directory itself. The migration moves the directory and deletes nothing:

```bash
sudo mv /opt/pmoves /opt/pmoves.legacy-$(date -u +%Y%m%dT%H%M%SZ)
make -C pmoves b850-bootstrap          # clones the checkout, writes a fresh profile.yaml
# optional: keep the OLD profile instead of the regenerated one
sudo install -m 0644 -o "$USER" -g "$(id -gn)" /opt/pmoves.legacy-<ts>/profile.yaml /opt/pmoves/profile.yaml
```

Check `/opt/pmoves.legacy-<ts>/data` before removing the legacy tree.

## Common tasks from B850 CLI

- **Probe AZ**: `curl -s http://pmoves-powerfulmoves:8080/healthz | jq '.nats'`
- **List AZ MCP commands**: `curl -s http://pmoves-powerfulmoves:8080/mcp/commands | jq '.commands[].name'`
- **Trigger YouTube ingest** (when playlist URL provided): see AGENT_ZERO_API.md `POST /mcp/execute` with `ingest.youtube`
- **Submit task to AZ**: `curl -XPOST http://pmoves-powerfulmoves:8080/tasks -H 'content-type: application/json' -d '{"message": "...", "metadata": {...}}'`
- **Bringup venv**: `make -C pmoves venv-bringup` (after `make` is installed); falls back to `INCLUDE_BRINGUP=1 bash pmoves/scripts/create_venv.sh`
- **Mesh health**: `bash .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh` (PR #1496-landed skill)
- **File CLAIM**: append to `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` as `B850-CLAUDE (Knuckles)` per the canonical format. Use `pmoves-chit-sign` skill for signing once implemented.

## Cross-references

- **Sibling profile**: [`pmoves/docs/NODE_PROFILES/4090-CLAUDE.md`](./4090-CLAUDE.md) — pattern source
- **AZ API doc**: [`pmoves/docs/operations/AGENT_ZERO_API.md`](../operations/AGENT_ZERO_API.md) — companion doc landing in this same PR
- **Topology row**: `pmoves/docs/operations/TOPOLOGY.md` (R9700 Workstation row annotated with B850 alias via PR #1501)
- **Bringup memory**: [`~/.claude/projects/-home-pmoves-knuckles-pinokio-api-PMOVES-AI/memory/feedback_bringup_venv_uv.md`](../../../../../.claude/projects/-home-pmoves-knuckles-pinokio-api-PMOVES-AI/memory/feedback_bringup_venv_uv.md) — venv + uv convention
- **Node identity memory**: same dir, `user_node_identity_b850_knuckles.md`
- **Convergence checklist**: `pmoves/docs/AGENTS/AGNOTE_CONVERGENCE_CHECKLIST_2026-05-16.md` (PR #1496-landed)
- **Profile YAML**: `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` (PR #1504 updated `node_id: pmoves-b850`)
