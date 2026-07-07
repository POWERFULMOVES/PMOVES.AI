---
name: mesh-egress-ab
description: Measure what a PMOVES exit node buys a household vs its raw local uplink (A/B), and map participating homes onto measured node capacity. Use for the Fordham Hill community-mesh pilot, exit-node speed/selection checks, and capacity planning.
---

# mesh-egress-ab

Repeatable, node-agnostic egress measurement + capacity planning. Born from the Fordham Hill pilot: prove — with numbers, not claims — what routing a household through a community-run KVM exit node costs and buys versus its own local uplink, and size how many resident homes the fleet can carry.

Script: `deploy/provision/mesh-egress-ab.sh` (portable — `curl` + `awk` only for `measure`/`capacity`; adds the `tailscale` CLI for auto `ab`). Runs on Linux, macOS, and Android/Termux.

## When to use

- **Pilot demos / field data** — capture a clean direct-vs-mesh A/B at a resident's location (e.g. SLATE on the Starlink Mini).
- **Exit-node selection** — which of kvm2 / kvm4-1 / kvm4-2 is fastest *right now* (results vary run-to-run; measure, don't assume).
- **Capacity planning** — map a participant count onto a node's measured uplink before onboarding homes.
- **After any exit-node or Mullvad change** — confirm egress still flows and where it exits.

## How to invoke

```bash
# Auto A/B: direct vs every approved exit node, self-restoring (CLI node)
make -C pmoves mesh-egress-ab
#   or: bash deploy/provision/mesh-egress-ab.sh ab

# Portable measure of the CURRENT egress (Android/SLATE: toggle exit in the
# Tailscale app between runs, then diff the two snapshots)
bash deploy/provision/mesh-egress-ab.sh measure --label starlink-direct   --save direct.json
bash deploy/provision/mesh-egress-ab.sh measure --label starlink-via-kvm  --save viakvm.json
bash deploy/provision/mesh-egress-ab.sh compare direct.json viakvm.json

# Capacity: how many homes fit on a node, and does a participant count fit?
make -C pmoves mesh-capacity DOWN=845 HOMES=200
```

## Output

`measure` reports public IP + org, download/upload Mbps, latency, jitter, TTFB.
`ab` prints the same for direct + each exit node, then restores.
`capacity` prints an oversubscription table (1:1 / 5:1 / 10:1 / 20:1 / 50:1) with the effective per-home budget and a FITS/needs-more-nodes verdict, anchored to the repo's own 10 Mbps/home budget.

## Coordination (tooling · skills · agents · teams)

- **Operator / resident node** (SLATE, 4090, any home): runs `measure`/`compare` — no privileges needed.
- **`vps-deployer` agent**: runs `ab` from a fleet node and provisions/rebalances exit nodes via Hostinger + Tailscale MCP.
- **Fleet team**: pairs with `fleet:status`, `fleet:acl-audit`, and `deploy/provision/exit-node-healthcheck.sh` (L4 Mullvad egress/leak check).
- **Capacity output** feeds `pmoves/docs/pilots/fordham-hill/` and the PMOVES-Wealth community ledger + Tokenism contribution model.

## Citations

- `deploy/provision/mesh-egress-ab.sh` — the tool
- `pmoves/docs/operations/MESH_EGRESS_AB_RUNBOOK.md` — operator guide
- `pmoves/docs/operations/FLEET_CAPACITY_ANALYSIS.md` §6 — per-home budget basis
- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md` — exit-node lifecycle
- `pmoves/mk/egress.mk` — `mesh-egress-ab` / `mesh-egress-measure` / `mesh-capacity` targets
