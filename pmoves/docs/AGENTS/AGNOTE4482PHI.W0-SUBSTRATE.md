# AGNOTE4482PHI — W0 Substrate: Cross-Platform Node Onboarding

GRAPHITI_MARK: `PHI-4482-W0::SUBSTRATE-NODE-ONBOARDING::PMOVES`

> **Parent:** [AGNOTE4482.md](./AGNOTE4482.md) | **Claim Register:** [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md) | **Roadmap:** [AGNOTE4482_ROADMAP_W1-W5.md](./AGNOTE4482_ROADMAP_W1-W5.md)
> **Author:** z890-claude (Z890 infra session, 2026-05-09)
> **Status:** OPEN — claim-able by 4090-CLAUDE / shift crew / Z890-CLAUDE / Codex
> **Trigger:** Z890 dual-NIC fix (PR #1432, commit `4a970a71`) revealed a system-agnostic gap; user is rolling out new systems through Unifi networking and needs accurate-config-on-first-boot.

---

## Why W0 (and Why Not W1–W5)

The W1–W5 roadmap (`AGNOTE4482_ROADMAP_W1-W5.md`) covers **audience-facing** work:

- W1 — Agent theming + cross-machine terminal
- W2 — P7 IDE + Codespaces
- W3 — Discord classrooms
- W4 — Website + waitlist
- W5 — Enterprise + civi-box release

This work is **substrate** — it sits beneath W1. Cross-platform node onboarding is the layer that decides which compose stack runs where, which model bundle the host can host, and whether the host's network is sane enough to bind container ports. Without it, every new node onboarding is a hand-rolled audit.

W0 is therefore **foundational**, not parallel. Calling it W0 instead of inserting it into W1–W5 keeps the existing wave numbering stable.

---

## Lane Goal

Stand up a unified hardware-scan + network-sanity probe that runs on **any** new PMOVES node — Linux, Windows, macOS, Jetson, VPS — and produces:

1. A stable JSON inventory (CPU, RAM, GPU, NICs, disks, platform hints).
2. A draft hardware profile YAML (matching `pmoves/config/profiles/*.yaml` schema) the operator can review and commit.
3. A per-host network-sanity report including same-subnet ghost detection (the bug behind the Z890 dual-NIC fix).
4. Optional Unifi controller cross-check that compares each host's self-reported adapters against what the managed switch sees.

Output of (2) feeds room manifest binding. Output of (3) catches the same-subnet ghost class **before** Docker silently breaks. Output of (4) catches MAC/VLAN drift the controller sees but the host doesn't.

---

## Reuse Signal — What Already Exists (and Where)

| Asset | Location | Reuse |
|---|---|---|
| `glances-autodetect.sh` (700 lines, Linux) | `feat/glances-autodetect` worktree, not yet on main | **Direct.** Bash hardware probe; emits stable JSON; maps to `suggested_node_type` |
| `phase-c-hw-profiles/*.yaml` | `feat/phase-c-hw-profiles` worktree, not yet on main | **Direct.** YAML profile schema (DGX Spark GB10, dual-R9700 workstation); destination contract for auto-write |
| `hostinger-kvm-setup.sh`, `kvm2-exit-node.sh` | same worktree | VPS-class onboarding companions |
| `pmoves/scripts/env_check.ps1` | already on main | Windows env probe — extend, do not replace |
| `pmoves/config/profiles/jetson-orin-nano.yaml` | already on main | Single-profile-on-main, useful as schema reference |
| `pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md` | landing in companion PR `docs/same-subnet-ghost-pattern` | Pattern reference for PR-4 detector logic |
| `pmoves/docs/operations/FLEET_INVENTORY_LIVE.md` Phase 2 | on `feature/launch-readiness-stage-0` (PR #1432) | Worked example (Z890 instance) |
| `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` | already on main | Confirms separation: hardware profile is **not** the room manifest; room manifests are audience-facing surfaces. Hardware profiles bind separately. |

---

## Gap (What W0 Adds That Doesn't Exist Yet)

1. **Windows hardware-detection parity** — no PowerShell mirror of `glances-autodetect.sh`. The Z890 (Windows 11 Pro) is currently un-probable by the existing tooling.
2. **Same-subnet ghost detector** — neither `glances-autodetect` nor `env_check.ps1` flags the dual-NIC collision. This is the proactive layer that prevents the next Z890-class incident.
3. **Unifi controller awareness** — zero references to Unifi/Ubiquiti anywhere in the repo (verified by `grep` against `pmoves/scripts`, `pmoves/config`, `pmoves/docs`). Adding this catches phantom MACs and VLAN drift.
4. **Profile auto-write** — `glances-autodetect` only suggests a `suggested_node_type` string. Auto-generating a draft profile YAML closes the scan→profile→room-manifest loop.
5. **None of the above is on `main`** — the two reusable assets are stranded in worktrees 20+ days old. Landing them is its own PR pair before any new code can build on them.

---

## PR Series (Atomic, Targeted, Claim-able)

Each PR is independently mergeable. Dependencies are explicit. Claim by adding a CLAIM entry in [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md) § Active Claim Register naming the PR number and your agent ID.

### PR-1 — Land `glances-autodetect.sh` on main

**Branch base:** `feat/glances-autodetect` (currently in worktree at `.worktrees/glances-autodetect`).
**Files:** `deploy/provision/glances-autodetect.sh`, `deploy/provision/hostinger-kvm-setup.sh`, `deploy/provision/kvm2-exit-node.sh`, `deploy/runbooks/autodetect-unknown-system.md`.
**Verify:** JSON output schema documented in script header; `bash glances-autodetect.sh --json` produces the documented shape on a Linux node.
**Atomic:** yes — Linux hardware detection only, no Windows yet.
**Blocks:** PR-3, PR-4, PR-5, PR-6.

### PR-2 — Land `phase-c-hw-profiles` on main

**Branch base:** `feat/phase-c-hw-profiles` (currently in worktree at `.worktrees/phase-c-hw-profiles`).
**Files:** `pmoves/config/profiles/dgx-spark-grace-blackwell.yaml`, `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml`, `pmoves/config/gpu-models.yaml` updates, profile schema if defined separately.
**Verify:** schema fields (`hardware.cpu`, `hardware.gpu`, `model_bundles`, `compose_overrides`, `tailscale.role`) match what PR-6 will produce.
**Atomic:** yes — declarative schema only.
**Blocks:** PR-6.

### PR-3 — Windows companion `glances-autodetect.ps1`

**Files:** `deploy/provision/glances-autodetect.ps1` (new).
**Probes:** `Get-CimInstance Win32_Processor`, `Win32_PhysicalMemory`, `Get-NetAdapter`, `Get-NetIPAddress`, `nvidia-smi`, GPU via WMI.
**Output:** identical JSON schema to `glances-autodetect.sh`. PR-6 must not need to know which platform produced the JSON.
**Test target:** Z890 (Windows 11 Pro) producing JSON identical-shape to a Linux node JSON.
**Atomic:** yes.
**Depends on:** PR-1 (so the schema is on main and treated as canonical).

### PR-4 — Same-subnet ghost detector module

**Files:** detector function added to both `glances-autodetect.sh` and `glances-autodetect.ps1`.
**Output:** appends `nic_collisions: [{primary: "...", ghost: "...", subnet: "..."}]` to the JSON. Empty array on healthy hosts.
**Reference:** in-script comments cite [`SAME_SUBNET_GHOST_PATTERN.md`](../operations/SAME_SUBNET_GHOST_PATTERN.md) for diagnosis logic.
**Atomic:** yes.
**Depends on:** PR-1, PR-3, and the pattern doc landing.

### PR-5 — Unifi probe layer

**Files:** `deploy/provision/unifi-probe.{sh,ps1}` (or `--unifi` flag on autodetect).
**Inputs:** `UNIFI_API_KEY` and `UNIFI_CONTROLLER_URL` env vars. If absent → skip gracefully (no failure).
**Output:** `unifi_topology: {...}` block appended to the JSON. Includes per-host adapter cross-check (Unifi-seen MAC vs host-reported MAC), VLAN assignment vs host-reported VLAN, devices-on-controller-but-not-in-host-list, devices-on-host-but-not-in-controller-list.
**Atomic:** yes.
**Depends on:** PR-1.

### PR-6 — Auto-write profile YAML from JSON

**Files:** `deploy/provision/json-to-profile.py` (new, cross-platform Python).
**Behavior:** consumes the JSON from PR-1/PR-3 output, generates draft `pmoves/config/profiles/<hostname>.yaml` matching the PR-2 schema. Maps `suggested_node_type` to `tailscale.role`. Copies CPU/RAM/GPU/NIC counts. Leaves `model_bundles` and `compose_overrides` as TODO comments for operator review.
**Closes:** scan → JSON → profile YAML → ready for room manifest binding loop.
**Atomic:** yes.
**Depends on:** PR-1 + PR-2.

---

## Out of Scope (W0 Defers)

- **Auto-applying profiles** to compose stack startup. PR-6 generates a *draft*; an operator commits it. Auto-apply is a downstream concern.
- **Same-subnet ghost auto-fix.** PR-4 detects only; the fix per `SAME_SUBNET_GHOST_PATTERN.md` requires elevated privileges and is operator-executed (per the same policy that gated the Z890 Phase 2 runbook).
- **Headscale takeover of Tailscale enrollment.** Phase 4 of FLEET_INVENTORY_LIVE.md, separate concern.
- **macOS hardware probes.** Defer until a macOS PMOVES node is in fleet (no current member).
- **Jetson-specific JetPack version detection.** Already covered by `deploy/provision/jetson/`; keep separate.

---

## Worked Example — The Z890 Trigger

The Z890 (Windows 11 Pro, dual-NIC, 20C/32GB, RTX 3090 Ti, primary `Pmoves-network-ether`) hit the same-subnet ghost class on 2026-05-07 when a disconnected `Ethernet 4` adapter held a stale static address inside the active LAN /24. Result: `pmoves-supabase-kong-1` showed empty `NetworkSettings.Ports` for 8000/8001 while `pmoves-hi-rag-gateway-v2-1` bound 8086 successfully on the same daemon, and `pmoves-supabase-edge-functions-1` looped on `Temporary failure in name resolution`.

If PR-4 had existed, the JSON output of `glances-autodetect.ps1` on Z890 would have included:

```json
"nic_collisions": [
  {
    "primary": "Pmoves-network-ether (<LAN_PRIMARY_IP>)",
    "ghost":   "Ethernet 4 (<LAN_GHOST_IP>) [Disconnected]",
    "subnet":  "<LAN_PREFIX>"
  }
]
```

…and the operator would have seen the collision before any container drama. That's the W0 prevention story in one paragraph.

The Z890 fix runbook itself ([`FLEET_INVENTORY_LIVE.md`](../operations/FLEET_INVENTORY_LIVE.md) Phase 2) remains the worked example for the Windows applied instance. The platform-agnostic version is [`SAME_SUBNET_GHOST_PATTERN.md`](../operations/SAME_SUBNET_GHOST_PATTERN.md).

---

## Handoff Notes

**Recommended primary owner:** 4090-CLAUDE (per `feedback_operator_agent_approval_gates.md` and the precedent of 4090-CLAUDE handling cross-fleet operability work). The 4090 has the breadth — Windows laptop access, Linux dev tooling, Jetson reach — that this lane needs to validate.

**Alternative owners:**
- Z890-CLAUDE (this session, on Z890) — has live access to the trigger node and could validate PR-3 output directly. Less reach for non-Windows platforms.
- Codex — strong cross-platform tooling; would need access to a Windows node for PR-3 testing.
- Shift crew — distributed, would split PR series across crew members.

**Village Rule reminder:** any agent claiming any PR in this series posts a CLAIM entry in `AGNOTE4482PHI.t1.md` § Active Claim Register **before** opening the PR, naming both their agent ID and the PR number scope (e.g., `CLAIM 4090-CLAUDE scope: W0 PR-1 (glances-autodetect to main) + PR-3 (Windows companion)`).

**Required handoff fields when releasing:**

- `graphiti_mark` — `PHI-4482-W0::<your-PR-tag>::PMOVES`
- `branch` and `pr_numbers`
- `scope`
- `risks`
- `next_actions`
- `chit_artifact_path` (CHIT-encoded handoff payload, no plaintext secrets)
- `agent_signature`

---

## Open Questions for Operator

These are not blocking — they can be answered during PR-1 / PR-2 review.

1. **Default for the dedicated direct-link CIDR** if Option A of the same-subnet fix is chosen. The Z890 runbook proposed `10.99.99.0/24`. Should that be a fleet-wide convention codified in `pmoves/docs/operations/SAME_SUBNET_GHOST_PATTERN.md` § Fix?
2. **Unifi controller URL canonical location.** Operator's Unifi controller is presumably on-LAN. Should `UNIFI_CONTROLLER_URL` and `UNIFI_API_KEY` go through the secrets-funnel (same as other fleet credentials), or are they per-host overrides?
3. **Profile YAML naming convention.** PR-6 produces `<hostname>.yaml`. Should the convention be `<hostname>.yaml`, `<tailscale-name>.yaml`, or `<suggested-node-type>-<hostname>.yaml`? Existing profiles use class-name-based naming (`dgx-spark-grace-blackwell`, `workstation-9850x3d-dual-r9700`); class-name is more reusable across hosts.

---

## Related Refs

- [AGNOTE4482.md](./AGNOTE4482.md) — Audit gateway + convergence waves (parent)
- [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md) — Active Claim Register
- [AGNOTE4482_ROADMAP_W1-W5.md](./AGNOTE4482_ROADMAP_W1-W5.md) — W1–W5 roadmap (this is W0, foundational beneath)
- [FLEET_INVENTORY_LIVE.md](../operations/FLEET_INVENTORY_LIVE.md) — Z890 Phase 2 worked example
- [SAME_SUBNET_GHOST_PATTERN.md](../operations/SAME_SUBNET_GHOST_PATTERN.md) — Cross-platform pattern reference (companion PR)
- [ROOM_MANIFEST_CONTRACT.md](../ROOM_MANIFEST_CONTRACT.md) — Room manifest schema (separate concern from hardware profile, but the destination of the binding chain)
- [project_z890_kong_bind_real_root_cause.md](../../../../C%3A/Users/DARKXSIDE/.claude/projects/D--PMOVES-AI-PMOVES-AI/memory/project_z890_kong_bind_real_root_cause.md) — operator memory on Docker Desktop 29.4.0 bug interaction (read alongside same-subnet ghost — they are *separate* root causes that surfaced concurrently on Z890)
