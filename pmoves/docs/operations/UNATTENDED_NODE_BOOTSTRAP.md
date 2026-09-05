# Unattended Node Bootstrap — 4 Deployment Classes × 4 OS Bases

**Status:** PROPOSAL v0 (2026-09-05) — lane 2 of the 2026-09-05 sequencing (1→3→4→2)
**Context:** proxmox backup + redeploy on fresh machines is imminent. Licenses in hand:
Windows 11 Pro, Windows 11 IoT, GrapheneOS (device), omarchy (Arch, PMOVES fork quattro).
Every node validates exactly one class; the fleet covers all four.

## The two axes (do not conflate)

1. **`deployment_class`** (pmoves/config/deployment_classes.yaml) — the LICENSE axis:
   private-mesh · community · school · enterprise. Already wired into 13 profiles.
2. **`bootstrap_flavor`** (NEW, proposed) — the OS/BASE axis: `windows-pro` · `windows-iot` ·
   `omarchy` · `linux-server`. Determines which unattended path runs. Unset = unset
   (declare-never-infer, same posture as deployment_class).

## The matrix

| Node (validation seat) | bootstrap_flavor | deployment_class | Unattended path |
|---|---|---|---|
| elder-melchor | windows-pro | private-mesh | winget + `make -C pmoves hermes-bootstrap` (WSL2 make) |
| z890 | windows-pro | private-mesh | same, GPU extras (3090 Ti) |
| 5090 | windows-pro | private-mesh | same, MiniMax H3 lane pending release |
| KVM4-1/4-2, KVM2 | linux-server | private-mesh | cloud-init → `make node-bringup` (headless: tmux+Atuin per FLEET_TERMINAL_STRATEGY) |
| fresh workstations | **omarchy** | **community** (Fordham Hill pilot seats) | PMOVES-omarchy unattended install → hermes-pmoves launcher |
| edge/tablet seats | windows-iot | **school** | IoT unattend.xml + learner-safe defaults (requires_ack=false only) |
| hosted/VPS path | linux-server | **enterprise** | images carry commercial-OK components only (hosted_path: true) |

## Unattended path specs (v0)

### windows-pro (elder-melchor, z890, 5090)
1. winget bootstrap: git, docker-desktop, node, uv → `hermes` via install.sh in WSL
2. `git clone --recurse-submodules --depth 1` PMOVES.AI
3. `make -C pmoves hermes-bootstrap` (profile pmoves-hermes-<node> + MCP + CHIT)
4. Gateway as login item (proven on elder-melchor), terminal: PMOVES Wave fork (Win10 1809+)
5. Validation gate: `make doctor` + sentinel announces on NATS → pmoves-fleet shows the node

### linux-server (KVMs, enterprise VPS path)
1. cloud-init: docker, git, jq, tmux, atuin
2. repo clone (shallow) + `make node-bringup` (services per node purpose)
3. Headless agents: tmux+Atuin lingua franca; hermes gateway via systemd unit
4. Enterprise VPS: only requires_ack=false components baked in (deployment_classes gate)

### omarchy (fresh workstations — PMOVES GOES HAM target)
1. PMOVES-omarchy fork (quattro) unattended install: scripted disk + user + Hyprland
2. PMOVES app layer: Ghostty (patch-fork theme) + Wave fork + hermes-pmoves via Pinokio8
3. `pmoves-fleet` + `pmoves-services` launchers from PMOVES-pinokio (PR #12 pending)
4. community class: self-host everything, local-model defaults (Ollama), no paid tiers

### windows-iot (edge/tablet seats)
1. IoT unattend.xml (answer file) + PMOVES provisioning package
2. Learner-safe defaults ONLY (school class: requires_ack discouraged → ship none)
3. Kiosk-mode launcher → Pinokio → curated PMOVES apps

## Open items
- [ ] `bootstrap_flavor` field added to profiles + loader test (mirrors deployment_class coupling test)
- [ ] PMOVES-omarchy unattended-install script (fork has the pieces; needs PMOVES answer file)
- [ ] windows-iot unattend.xml + provisioning pkg (no operator seat yet — validation deferred)
- [ ] GrapheneOS seat: phone-class node (Vanadium browser as agent surface) — separate track
- [ ] per-flavor `make bootstrap-<flavor>` targets (OPS RULE: documented make targets only)
