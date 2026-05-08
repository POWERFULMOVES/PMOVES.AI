# Fleet Inventory — Live (Phase 1)

> Live ground-truth inventory captured 2026-05-07 from Z890 against the active Tailscale fleet.
> Companion to `TOPOLOGY.md` (master) — this doc reconciles drift; `TOPOLOGY.md` is updated in a follow-up PR after operator review.

**Probe date:** 2026-05-07
**Probed from:** Z890 (`pmoves-z890`, Windows 11 Pro 26200)
**Method:** `make -C pmoves fleet-status` (canonical) + per-host SSH probes via Tailscale hostnames
**Skipped per `.claude` memory:** KVM2, KVM4-2 (console-injection PENDING — `cloudflare_dns_steps.md`, `hostinger_ssh_decision.md`)

---

## TL;DR — Drift Summary

| Node | Field | TOPOLOGY.md says | Live measurement | Status |
|------|-------|------------------|------------------|--------|
| Z890 | vCPU / RAM | 32C / 128GB | **20C / 32GB** | DRIFT (doc wrong) |
| Z890 | Static IP on `Ethernet 4` | not documented | **stale static on disconnected adapter, same /24 as primary NIC** | NEW — same-subnet collision causes Docker port-bind + WSL2 DNS failures |
| Z890 | Kong host port bind | not measured | **fails silently** | NEW — `NetworkSettings.Ports` empty for 8000/8001 despite container up; hi-rag 8086 binds OK from same daemon |
| Z890 | edge-functions DNS | not measured | **`Temporary failure in name resolution`** | NEW — restart-looping every ~30s |
| Jetson #1 (`pmoves-nano`) | last-seen | "Dormant 108d" (memory `project_lan_topology.md` 2026-03-25) | **online** | RESOLVED — Tailscale active per fleet-status |
| Stale Tailscale entries | n/a | not flagged | `nvsync-powerfulmoves`, `powerfulmoves`, `nvsync-pmoves-spark`, `pmoves-pro`, `pmoves-botz` | All offline; candidates for `/fleet:stale-nodes` cleanup |

---

## Per-Node Cards

### Z890 — `pmoves-z890` (Windows 11 Pro)

**Source:** Self-probe + `docker inspect` + memory `project_lan_topology.md` for NIC layout.

| Field | Value | TOPOLOGY.md drift |
|-------|-------|-------------------|
| OS | Windows 11 Pro 26200 (kernel `MINGW64_NT-10.0-26200` via MSYS) | — |
| Architecture | x86_64 | — |
| vCPU | **20** (`nproc` from MSYS) | doc says 32 → DRIFT |
| RAM | **32 GB** (`MemTotal: 32985900 kB`) | doc says 128 → DRIFT |
| GPU | RTX 3090 Ti (24GB VRAM) — per memory, not re-probed | matches doc |
| Primary NIC | `Pmoves-network-ether` — `<LAN_PRIMARY_IP>` (active) | doc lists "LAN (dual NIC)" |
| Secondary NIC | `Ethernet 4` — `<LAN_GHOST_IP>` (**disconnected, static, same /24 as primary**) | not documented; root cause of Phase 2 fix |
| Tailscale hostname | `pmoves-z890` | matches |
| Multi-boot status | Win11 active; Ubuntu/Pop/Fedora/Cachy/Nix slots provisioned | per `deploy/provision/z890/` (not re-verified) |

**Live Docker symptoms (verified 2026-05-07 from this probe):**

```
docker inspect pmoves-supabase-kong-1 --format '{{json .NetworkSettings.Ports}}'
{"8000/tcp":[],"8001/tcp":[]}                                   ← bug: container exposes, no host bind

docker logs pmoves-supabase-edge-functions-1 --tail 8
Error: main worker boot error
  ...
  3: Import 'https://deno.land/std@0.131.0/http/server.ts' failed:
       error sending request for url ...:
       dns error: failed to lookup address information:
       Temporary failure in name resolution

docker ps | grep -E 'kong|hi-rag'
pmoves-supabase-kong-1     Up 8 hours (healthy)  8000-8001/tcp           ← unbound
pmoves-hi-rag-gateway-v2-1 Up 9 hours (healthy)  0.0.0.0:8086->8086/tcp  ← bound, OK
```

**Diagnosis confirmed:** selective port-bind failure + DNS resolver failure on the same daemon. Same-subnet ghost on `Ethernet 4` is the documented cause; Phase 2 fix below.

---

### DGX Spark — `pmoves-spark` (Linux Arm)

**Probe attempted, blocked.** Status: `online` per `tailscale status`, but SSH probe with username `spark` returned `Permission denied (publickey,password)` and `tailscale ssh` failed `host key verification` (host key not yet trusted on Z890).

**TOPOLOGY.md claims (unverified live):**
- 20-core Arm (10x Cortex-X925 + 10x Cortex-A725) + GB10 Grace-Blackwell
- 128GB unified LPDDR5X
- Tailscale `pmoves-spark` ✓ (matches live fleet-status)

**Action to unblock:** push `pmoves-claw` SSH pubkey to `spark@pmoves-spark:~/.ssh/authorized_keys`, **or** enable Tailscale SSH on the Spark side (`tailscale up --ssh`) and accept host key from Z890. Then re-run probe.

---

### POWERFULMOVES (5090 Linux) — `pmoves-powerfulmoves`

**Probe attempted, blocked.** Status: `online` per `tailscale status`, but SSH on port 22 returned `Connection refused` (sshd not listening on Linux side from Z890 path; Tailscale SSH returned `dial tcp ... actively refused` matching the hosted SSH service being down).

**TOPOLOGY.md claims (unverified live):**
- RTX 5090 (32GB)
- 24C / 64GB
- Linux + Windows dual-entry: `pmoves-powerfulmoves` (Linux) + `pmoves-5090` (Windows, also online)

**Action to unblock:** start sshd on 5090 Linux side (`sudo systemctl enable --now ssh`), or connect via Windows side (`pmoves-5090`, also online) and shell into the Linux partition from there. The 5090 Windows entry is reachable; consider probing via that path next round.

---

### KVM4-1 — `pmoves-kvm4-1` (Hostinger VPS, Linux)

**Probe attempted, blocked.** Damage-control hook denied SSH-to-production-VPS without explicit per-session authorization. The denial is **correct** under fleet security policy (`feedback_use_mcp_tools_not_raw_api.md`) — production reads route through MCP tools, not raw SSH.

**TOPOLOGY.md claims (unverified live):**
- 8C / 16GB
- API Gateway + Tailscale Egress Exit Node (Phase 9Q)
- Cost: $10/mo

**Action to unblock:** either (a) operator explicitly grants `Bash(ssh root@pmoves-kvm4-1:*)` for this session, or (b) probe via the Hostinger MCP server (`mcp__hostinger-mcp__*` tool family) which has audited read access. Option (b) is the canonical Known Road.

---

### Jetson Orin #1 — `pmoves-nano` (Linux Arm, sm_87)

**Probe attempted, blocked.** Same damage-control denial as KVM4-1 (production-read class). Status: `online` per `tailscale status` — this **resolves the 108-day dormancy** flag in memory `project_lan_topology.md`.

**TOPOLOGY.md claims (unverified live):**
- Orin Nano sm_87
- L4T pre-JetPack 7.0 (reflash scheduled per `deploy/provision/jetson/`)
- SSH: `pmovesnvme@<lan-ip>` documented

**Action to unblock:** operator authorizes `Bash(ssh pmovesnvme@pmoves-nano:*)`, then re-run probe + `cat /etc/nv_tegra_release` for JetPack version.

---

### Jetson Orin #2 — `pmoves-nemotron-2` (pending)

Per TOPOLOGY.md and memory `project_jetson_jetpack7.md`: not yet on Tailscale. Phase B reflash + enrollment pending. **Out of scope this probe** — confirmed via fleet-status (no online matching entry).

---

### 4090 Laptop — `pmoves-laptop`

**Status: offline at probe time** (`pmoves-laptop windows offline, last`). Per memory `project_lan_topology.md`, this matches the documented "WiFi 7, conditionally LAN-attached" pattern — the 4090 is on-fleet only when physically connected. No drift, no action.

---

### Codex Node

**Unidentified.** Plan called it out as `codex@<some-host>`, asked to confirm which node. Online linux entries that could be candidates: `pmoveseldermelchor`. Probe attempt against `codex@pmoveseldermelchor` was cancelled when other parallel probes hit blockers; not retried because user has not confirmed the binding. **Action:** operator confirms whether `pmoveseldermelchor` is the codex node, or names the correct hostname.

---

### Skipped: KVM2, KVM4-2

Per memory `feedback_session_beats.md` + `hostinger_ssh_decision.md`: both nodes have **console-injection PENDING** for the regenerated SSH key (2026-04-02). Probing via SSH from Z890 will fail until the operator pastes the new pubkey via Hostinger console. Out of scope this phase.

KVM2 RustDesk relay status, however, is **healthy** as observed in fleet-status:
```
=== RustDesk Relay (KVM2) ===
  hbbs (21116): REACHABLE
  hbbr (21117): REACHABLE
```
This corroborates Phase 3 readiness (relay operational, only client-side migration remains).

---

### Stale Tailscale Entries (Cleanup Candidates)

Per `pmoves/docs/TAILSCALE_NODE_HYGIENE.md` (offline > 60 days = stale):

| Hostname | OS | Likely meaning |
|----------|----|----------------|
| `0a120cdf31cc`, `13eeb550425c`, `2871444ae72428` | linux | Container-generated random hostnames; abandoned ephemeral nodes |
| `nvsync-powerfulmoves` | windows | Old name for 5090 Windows side; superseded by `pmoves-5090` |
| `nvsync-pmoves-spark` | linux | Old name for Spark; superseded by `pmoves-spark` |
| `powerfulmoves` | windows | Pre-rename 5090 entry |
| `pmoves-pro` | linux | Unknown; possibly retired dev box |
| `pmoves-botz` | linux | Per memory, BoTZ standalone host (legacy/archived per 2026-04-19) |
| `russells-tab-s8-ultra`, `pixel-10-pro-xl` | android | Mobile devices; expected to come and go |
| `laptop-lrhmh8lf` | windows | Unknown laptop |

**Action:** run `/fleet:stale-nodes` for triaged cleanup proposal; do not auto-delete.

---

## Phase 2 — Z890 Dual-NIC Fix Runbook (operator-executed)

> **Why this can't be automated by the agent:** modifying NIC IP assignments requires elevated PowerShell on Z890 and is a shared-system change. Auto mode policy: agent prepares the runbook; operator executes.
>
> **Reversibility:** every step has an inverse. Option B (disable adapter) is the safest fallback if anything misbehaves.

### Operator substitutions (private values — not committed)

The runbook below uses placeholders for LAN-private values. Look up actual values from operator's local Cipher Memory entry `project_lan_topology.md` (or by running `Get-NetIPAddress -InterfaceAlias "Ethernet 4"` and `Get-NetIPAddress -InterfaceAlias "Pmoves-network-ether"`) before running each command:

| Placeholder | What to substitute |
|---|---|
| `<LAN_GHOST_IP>` | Static IP currently on `Ethernet 4` (the disconnected adapter — RFC1918 address) |
| `<LAN_PRIMARY_IP>` | Active IP on `Pmoves-network-ether` (primary NIC, same /24 as ghost) |
| `<LAN_PREFIX>` | LAN /24 CIDR prefix shared by both adapters |

These values are intentionally not in this committed doc — see `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` and the topology-leakage hook (`pmoves/scripts/hooks/damage-control/`) for the public-repo IP-redaction policy.

### Pre-flight (record before changing anything)

Run from elevated PowerShell on Z890:

```powershell
# 1. Snapshot current NIC state
Get-NetIPAddress -InterfaceAlias "Ethernet 4" | Format-Table InterfaceAlias, IPAddress, PrefixLength, AddressState
Get-NetIPAddress -InterfaceAlias "Pmoves-network-ether" | Format-Table InterfaceAlias, IPAddress, PrefixLength, AddressState

# 2. Snapshot routes claiming the LAN /24
Get-NetRoute -DestinationPrefix "<LAN_PREFIX>"

# 3. Snapshot Docker pre-state (to confirm reproduction post-fix)
docker inspect pmoves-supabase-kong-1 --format '{{json .NetworkSettings.Ports}}'
docker logs pmoves-supabase-edge-functions-1 --tail 5
```

Expected pre-state matches what this doc captured at probe time (Kong empty Ports map, edge-functions name-resolution failure).

### Apply (Option A: re-IP `Ethernet 4` to a dedicated direct-link subnet)

Preserves the original intent of `Ethernet 4` as the future Z890↔5090 high-bandwidth direct link.

```powershell
# Remove the same-subnet ghost
Remove-NetIPAddress -InterfaceAlias "Ethernet 4" -IPAddress <LAN_GHOST_IP> -Confirm:$false

# Move to dedicated /24 (10.99.99.0/24 is unused per current topology)
New-NetIPAddress -InterfaceAlias "Ethernet 4" -IPAddress 10.99.99.1 -PrefixLength 24
```

### Apply (Option B: disable `Ethernet 4` entirely — simpler if direct-link not yet used)

```powershell
Disable-NetAdapter -Name "Ethernet 4" -Confirm:$false
```

### Refresh Docker (either option)

```bash
# From Git Bash / WSL
make -C pmoves supa-restart
```

### Verify (all six MUST pass for Phase 2 done)

```powershell
# 1. Ethernet 4 either off or on the new subnet
Get-NetIPAddress -InterfaceAlias "Ethernet 4"   # → 10.99.99.1/24, OR no IP

# 2. Only one adapter owns the LAN /24
Get-NetRoute -DestinationPrefix "<LAN_PREFIX>"   # → ONE row, InterfaceAlias = Pmoves-network-ether
```

```bash
# 3. Kong has host port binding now
docker inspect pmoves-supabase-kong-1 --format '{{json .NetworkSettings.Ports}}'
# Expected: {"8000/tcp":[{"HostIp":"0.0.0.0","HostPort":"8000"}],"8001/tcp":[...]}

# 4. Kong gateway responds
curl -fsS http://localhost:8000/   # → HTTP response (not connection refused)

# 5. edge-functions stopped failing DNS
docker logs pmoves-supabase-edge-functions-1 --tail 20   # → no "Temporary failure in name resolution"

# 6. No restart loop
docker ps --filter status=restarting   # → empty
```

### Rollback (if Phase 2 makes things worse)

```powershell
# Reverse Option A
Remove-NetIPAddress -InterfaceAlias "Ethernet 4" -IPAddress 10.99.99.1 -Confirm:$false
New-NetIPAddress -InterfaceAlias "Ethernet 4" -IPAddress <LAN_GHOST_IP> -PrefixLength 24

# Reverse Option B
Enable-NetAdapter -Name "Ethernet 4" -Confirm:$false
```

---

## Phase 3+ — Out of Scope This Probe (per plan)

| Phase | Description | Gating |
|-------|-------------|--------|
| 3 | RustDesk Pub → KVM2 self-hosted client migration | Phase 2 verified pass; Known Road `make -C pmoves fleet-rustdesk-fix` |
| 4 | Headscale stand-up (displace Tailscale hosted control plane) | Phase 3 stable; per `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/PMOVES-Headscale.md` |
| 5 | Capacity-class compute placement (TensorZero routing rules) | Phase 1 inventory complete (this doc); per-class fallback table in plan |

---

## Follow-Up PR — TOPOLOGY.md Reconciliation

After operator confirms Phase 2 verified, open a PR that updates `TOPOLOGY.md`:

1. Z890 row: `32C / 128GB` → `20C / 32GB`
2. Z890 row: add NIC layout footnote (primary on LAN; secondary `Ethernet 4` moved to dedicated `10.99.99.0/24` direct-link to 5090 if Option A, or `disabled` if Option B)
3. Drop "Dormant 108d" implication from `pmoves-nano`
4. Add stale-Tailscale-entry cleanup checklist sourced from this doc

This reconciliation is intentionally **separate** from the Phase 2 fix PR so the network change is reversible without doc churn.

---

## Access Blockers Surfaced (operator decisions needed)

To complete a 100% Phase 1 probe in a future round, one or more of these must be unblocked:

1. **Spark SSH key trust** — push `pmoves-claw` pubkey to `spark@pmoves-spark`, OR enable Tailscale SSH on Spark.
2. **5090 Linux sshd** — `sudo systemctl enable --now ssh` on the Linux partition; alternatively probe via the `pmoves-5090` Windows entry.
3. **KVM4-1 production read** — operator authorizes `Bash(ssh root@pmoves-kvm4-1:*)` per-session, OR uses Hostinger MCP for the read.
4. **Jetson production read** — same as above for `pmovesnvme@pmoves-nano`.
5. **Codex node binding** — confirm hostname (candidate: `pmoveseldermelchor`).

Each row above is one decision; none are blocking Phase 2 (the Z890 fix), which can proceed today.
