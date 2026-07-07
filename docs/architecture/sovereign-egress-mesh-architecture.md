# Sovereign Egress & Mesh Architecture

> **Status:** design thesis (2026-07-03). Unifies four networking layers the fleet
> already runs or is building into one privacy/censorship-resistant model. Each
> layer is an independent, swappable component — this doc is the map; the
> component docs are the build detail.

## Thesis

PMOVES networking should be **sovereign and layered**: no single vendor, cloud, or
protocol is load-bearing, and each concern is handled by an independent layer that
can be swapped without touching the others. The four layers below are orthogonal —
they **compose, they do not compete**. A packet can traverse all four, or any
subset, depending on the mission.

The layering mirrors the MOF principle (every node is a pore): a node advertises
whichever layers its hardware supports (an RF node bridges Haven; a VPS concentrates
egress; every node speaks the Tailscale overlay), and the lattice routes around any
missing capability.

## The four layers

| Layer | Concern it owns | Component | In-repo artifact | Status |
|-------|-----------------|-----------|------------------|--------|
| **L1 — Access mesh** | Off-grid RF reach where there is no uplink | **Haven** (Wi-Fi HaLow 802.11ah ~900 MHz, 802.11s + BATMAN-adv) | `docs/Haven-v3.md` (external blueprint) | Not built — reference |
| **L2 — Identity overlay** | Encrypted, identity-addressed L7 routing; bridge dissimilar transports | **Reticulum** (`rnsd`; AutoInterface/UDP/TCP; mandatory encryption) | `docs/Reticulum-Network-Blueprint-v1.md` (external blueprint) | Not built — reference |
| **L3 — Long-haul overlay** | Bridge distant nodes over any internet uplink | **Tailscale / Headscale / WireGuard** | `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md`, `pmoves/configs/tailscale-acl-policy.json` | **Live** (`pmoves-kvm2` + `pmoves-kvm4-1` approved; `pmoves-kvm4-2` advertised, pending one console approve — see runbook) |
| **L4 — Egress privacy** | Public exit-IP ≠ the VPS's Hostinger IP | **Mullvad WG upstream** | `pmoves/docs/operations/MULLVAD_EXIT_UPSTREAM.md`, `deploy/provision/kvm-mullvad-upstream.sh` | **PR #1945** — coded, review-cleared, held for this doc |

Adjacent (not a routing layer, but part of the same sovereign-networking posture):

| Concern | Component | In-repo | Status |
|---------|-----------|---------|--------|
| Remote device access | **RustDesk self-host** + one-command enrollment | `pmoves/docs/operations/RUSTDESK_ENROLLMENT.md`, `pmoves/scripts/fleet/rustdesk-enroll.{sh,ps1}` | **Merged** (#1946) — relay on KVM2 |

## How the layers compose

### Scenario A — everyday fleet egress (L3 + L4)

The common case: a fleet client wants its public egress IP to be Mullvad's, not the
Hostinger VPS IP. No Haven/Reticulum involved.

```text
fleet client ──Tailscale (WG)──▶ KVM exit node ──Mullvad WG──▶ internet
              L3 long-haul        L4 egress-privacy
```

The KVM re-encapsulates only the traffic it *forwards in from Tailscale* (policy
routing on `iif tailscale0`); its own SSH/control plane keeps the naked uplink so a
tunnel flap can't strand it. A fail-closed kill-switch drops forwarded traffic if the
Mullvad tunnel is down. Detail: `MULLVAD_EXIT_UPSTREAM.md`.

### Scenario B — off-grid access joins the fleet (L1 + L3)

A Haven HaLow mesh gives RF reach with no uplink; a gateway node with both a HaLow
radio and an internet uplink bridges the island into the tailnet.

```text
EUD ──WiFi──▶ Haven HaLow mesh (802.11s/BATMAN) ──▶ gateway node ──Tailscale──▶ fleet
     L1 access mesh                                                L3 long-haul
```

Haven's own stack is `HaLow wlan0 → bat0 (BATMAN-adv) → br-ahwlan (Linux bridge)`,
and anything bridged into `br-ahwlan` (HaLow, LoRa, Ethernet) is interchangeable.

### Scenario C — identity overlay across everything (L2 over L1/L3)

Reticulum rides on top of whatever is underneath, giving encrypted, identity-addressed
routing independent of the transport. Its own **Long-Haul** guidance uses the *exact*
fleet substrate:

```text
Node A rnsd  TCPServerInterface  Listen = A's Tailscale IP (100.x.x.x):4243
Node B rnsd  TCPClientInterface  Target = A's Tailscale IP (100.x.x.x):4243
             → stable Reticulum bridge between segments, over the tailnet
```

So a PMOVES node runs `rnsd` with a `TCPClientInterface` pointed at a KVM's tailnet
IP to join fleet Reticulum segments — while that KVM's Mullvad upstream (L4)
anonymizes the public egress. Reticulum binds a Linux interface, so on a Haven node it
binds `br-ahwlan` and travels over HaLow with **no config change**.

### Scenario D — full stack (L1 + L2 + L3 + L4)

An off-grid team on Haven RF, running Reticulum for encrypted identity routing (e.g.
ATAK-over-Reticulum, no TAK server), bridged to the fleet over Tailscale, egressing to
the internet through a Mullvad-upstreamed KVM:

```text
ATAK/EUD ─ Haven HaLow ─ Reticulum overlay ─ gateway ─ Tailscale ─ KVM ─ Mullvad ─ internet
           L1            L2                            L3          L4
```

## PMOVES node / role mapping

| Node role | Layers it plays |
|-----------|-----------------|
| **KVM VPS (kvm2, kvm4-1, kvm4-2)** | L3 exit-node concentrator + **L4 Mullvad egress** (kvm4-1 = designated egress per Phase-9Q; kvm2 = plain-TS fallback + RustDesk relay) |
| **Fleet compute (SPARK, 5090, 4090, Knuckles)** | L3 tailnet members; optional L2 `rnsd` hosts |
| **Haven gateway node (future)** | L1 HaLow bridge + L3 uplink into the tailnet |
| **RNode / EUD (future)** | L1 access; L2 Reticulum client (MeshChat/Sideband) |

## Threat model — what each layer buys

| Adversary / failure | Defended by |
|---------------------|-------------|
| Correlating fleet traffic to the Hostinger VPS IP | **L4** Mullvad egress (public IP = Mullvad) |
| Passive observer on the local/RF segment | **L2** Reticulum (encrypted-by-default, origin-obfuscated) + Haven WPA3-SAE |
| Internet uplink cut / censored | **L1** Haven off-grid RF reach; **L3** any-uplink overlay |
| Vendor lock-in / cloud dependency | whole stack is self-hostable (Headscale, self-host RustDesk, self-host WG upstream) |
| A bad exit node stranding a box | L3/L4 set→test→auto-revert; L4 management stays on naked uplink |
| Losing remote access to a node | RustDesk self-host relay (adjacent) |

**Layer boundaries matter:** L4 (Mullvad) hides *where* you egress, not *who* you are;
L2 (Reticulum) hides *who/what*, not *where the exit is*. Neither replaces the other —
that is why they stack.

## Component status & roadmap

1. **L3 live** — all three KVMs are approved Tailscale exit nodes; scale via a
   `tag:exit` reusable authkey (auto-approve). See `TAILSCALE_EXIT_NODE_RUNBOOK.md`.
2. **L4 next** — merge PR #1945 (review-cleared, thread-clean) as the egress
   component; then stage the Mullvad `.conf` secret and canary kvm4-1 with
   `exit-node-healthcheck.sh --mode egress`. Secret path: the manifest is
   machine-emitted, value via `make secrets-rotate` — see the Mullvad doc.
3. **L1/L2 reference only** — Haven + Reticulum are external open blueprints
   (`docs/*.md`); no fleet build committed. First fleet step if pursued: run `rnsd`
   with a `TCPClientInterface` at a KVM tailnet IP (pure L2-over-L3, no new hardware)
   to prove the identity overlay before any RF/L1 build.
4. **Remote access merged** — RustDesk enrollment (#1946) covers operator reachability
   across the fleet independent of the routing layers.

## References

- **L4 egress:** `pmoves/docs/operations/MULLVAD_EXIT_UPSTREAM.md`, `deploy/provision/kvm-mullvad-upstream.sh`, `deploy/provision/exit-node-healthcheck.sh` (PR #1945)
- **L3 overlay:** `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md`, `docs/architecture/kvm-exit-node-hosting-strategy.md`, `docs/architecture/network-tier-segmentation.md`
- **L1/L2 blueprints:** `docs/Haven-v3.md`, `docs/Reticulum-Network-Blueprint-v1.md` (upstream: `github.com/buildwithparallel/haven-manet-ip-mesh-radio`, `github.com/buildwithparallel/reticulum-rnodes`)
- **Remote access:** `pmoves/docs/operations/RUSTDESK_ENROLLMENT.md`, `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` (#1946)
- **Memory:** `project_tailscale_exit_nodes`, `project_haven_reticulum_mesh`
