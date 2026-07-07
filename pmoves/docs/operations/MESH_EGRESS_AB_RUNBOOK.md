# Mesh Egress A/B + Capacity Runbook

> Operator guide for `deploy/provision/mesh-egress-ab.sh` and the
> `mesh-egress-ab` / `mesh-egress-measure` / `mesh-capacity` make targets.
> Born from the **Fordham Hill community-mesh pilot** — prove with numbers what
> a PMOVES exit node buys a household, and size how many homes the fleet carries.
>
> Cost/rate figures here are **DRAFT — REQUIRES LEGAL REVIEW**.

## What this answers

1. **What does routing through a community exit node cost/buy me** vs. my raw home uplink? (throughput, latency, jitter, TTFB, and the public IP identity change)
2. **How many resident homes can one node — and the fleet — carry?**
3. **Does a real participant count fit** the capacity we have?

## The honest framing (do not oversell)

On an **already-fast** home line (e.g. Fordham Hill Fios ~520 Mbps), routing through an exit node **lowers** peak throughput — one extra secure hop costs ~40% and ~35 ms. That is expected and fine: a demanding home only *uses* ~50 Mbps, so 305 Mbps through the mesh is ample. The exit node's real wins are **cost pooling, a stable portable datacenter IP, resilience on degraded/expensive links (Starlink), privacy (Mullvad L4), and platform (agents + MANET)** — not raw peak on a good line. The one place it also wins on *speed* is a **slow/CGNAT link**, where the KVM's 450–845 Mbps headroom beats the local pipe. Measure it; let the numbers talk.

## Quick start

### A. CLI node (4090 / z890 / KVM / any Linux/mac) — full auto A/B

```bash
make -C pmoves mesh-egress-ab
```

Measures direct vs. every approved exit node and **self-restores** your prior exit node on exit (safe set→test→restore — a bad node can't strand the box).

### B. Android / SLATE (Starlink Mini) — portable measure + compare

The Tailscale Android app has no CLI, so toggle the exit node **by hand in the app** between two measures, then diff:

```bash
# 1) exit node OFF in the Tailscale app, then:
bash deploy/provision/mesh-egress-ab.sh measure --label starlink-direct --save direct.json

# 2) turn the exit node ON (pick pmoves-kvm4-1) in the app, then:
bash deploy/provision/mesh-egress-ab.sh measure --label via-kvm4-1 --save viakvm.json

# 3) side-by-side A/B:
bash deploy/provision/mesh-egress-ab.sh compare direct.json viakvm.json
```

This is the flow that captures the **degraded-link win** for the pilot: on Starlink, `via-kvm4-1` should show higher throughput than `starlink-direct`.

> Termux setup on SLATE: `pkg install curl coreutils` (awk + curl). No root needed.

### C. Capacity planning

```bash
# how many homes fit on kvm4-1, and does 200 participants fit?
make -C pmoves mesh-capacity DOWN=845 HOMES=200
```

`DOWN` is a node's measured downlink Mbps (from `mesh-egress-ab ab`); `HOMES` is the participant count. Output is an oversubscription table (1:1 → 50:1) with the effective per-home budget and a FITS / needs-N-more-nodes verdict, anchored to the repo's conservative **10 Mbps/home** budget (`FLEET_CAPACITY_ANALYSIS.md §6`).

## Grounded capacity snapshot (measured this pilot)

| Node | Down | Up | Homes @ 10 Mbps/home (5:1) | Homes @ 20:1 |
|------|-----:|---:|---------------------------:|-------------:|
| kvm4-1 | 845 | 347 | ~84 | ~338 |
| kvm4-2 | 683 | 704 | ~68 | ~273 |
| kvm2   | 448 | 372 | ~45 | ~179 |
| **Fleet** | **1,976** | **1,423** | **~197** | **~790** |

A Fordham Hill building is a few hundred units → **even one node covers a building conservatively; the 3-node fleet covers it several times over**, and every node added grows the pool (the mesh strengthens with participation).

## Coordination — tooling · skills · agents · teams

| Layer | Who / what | Role |
|-------|-----------|------|
| Tooling | `mesh-egress-ab.sh` + `mesh-*` make targets | the measurement + planner |
| Skill | `mesh-egress-ab` | agent/operator entry point |
| Agent | `vps-deployer` | runs `ab` from a fleet node; provisions/rebalances exit nodes (Hostinger + Tailscale MCP) |
| Team | Fleet | pairs with `fleet:status`, `fleet:acl-audit`, `exit-node-healthcheck.sh` (Mullvad egress/leak) |
| Data | `pmoves/docs/pilots/fordham-hill/` | capacity feeds the Wealth ledger + Tokenism contribution model |

## Related

- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md` — exit-node lifecycle, auto-approve
- `pmoves/docs/operations/FLEET_CAPACITY_ANALYSIS.md` — per-home budget + concurrency model
- `deploy/provision/exit-node-healthcheck.sh` — L4 Mullvad egress + leak check
- `pmoves/docs/pilots/fordham-hill/` — pilot convergence package
