# Fordham Hill — Pilot Observation (solo operator, no agent on any home)

> The operator (DARKXSIDE) is the **sole** operator. SLATE is just a phone — no
> agent runs on it, and no software runs at any resident's home. So pilot
> observation must be driven entirely from the **infrastructure side**: the exit
> node self-reports, and the VPS host is queried by API. This is how one person
> watches a whole building's worth of households.

## Three observation layers (all agent-free at the edge)

| Layer | Source | Sees | How |
|-------|--------|------|-----|
| **1. VM host** | **Hostinger MCP** `VPS_getMetricsV1` | CPU, RAM, disk, in/out bandwidth, uptime — per KVM, historical | API call, zero SSH, zero agent |
| **2. Exit node** | **`exit-node-observer.sh`** on the KVM | mesh peers online, exit throughput (tailscale0), load/mem, Mullvad(L4) state, monthly-bw headroom | cron/systemd on the VPS → `--prom` to Grafana (PR #1822) |
| **3. Operator spot-check** | **`mesh-egress-ab.sh measure`** | direct-vs-mesh A/B at a point of presence (e.g. SLATE on Starlink) | operator runs by hand, occasionally |

Layers 1+2 run continuously with **nothing on any household device**; layer 3 is the
operator's occasional field measurement. Together they answer "is the pilot healthy,
who's connected, how loaded is the node, are we near capacity" without an agent fleet.

## Live-proven this session (kvm4-1, id 1184789, 31.97.42.207)

**Hostinger MCP (24h):** CPU steady **~4%**, RAM **~2.0 GB / 16 GB (~12%)**, uptime
**~78 days**, in/out traffic ~130–390 MB per 30-min sample.
**On-VPS observer (live):** **17/25 mesh peers online**, exit advertised, throughput
~1 Mbps (current light load), load **0.27 / 4 cores**, mem **12.3%**, Mullvad **off**.

**Cross-validation:** the observer's mem 12.3% matches Hostinger's ~12.5% independently —
two separate observation layers agreeing is the verification property we want.
**Headline:** at current load the node is **nearly idle** — compute is nowhere near the
constraint; capacity is bounded by bandwidth, not CPU/RAM.

## Real KVM inventory (Hostinger-authoritative — corrects TOPOLOGY.md)

| Node | id | Plan | vCPU / RAM | Monthly BW cap | IPv4 |
|------|----|------|-----------|----------------|------|
| kvm2   | 630926  | KVM 2 | 2 / 8 GB  | 8 TB  | 167.88.38.57 |
| kvm4-1 | 1184789 | KVM 4 | 4 / 16 GB | 16 TB | 31.97.42.207 |
| kvm4-2 | 1125072 | KVM 4 | 4 / 16 GB | 16 TB | 167.88.39.80 |

> Note: TOPOLOGY.md listed kvm4 nodes as 8C; Hostinger reports **4 vCPU / 16 GB**. The
> API is authoritative.

## Capacity has TWO constraints, not one

Earlier capacity work modeled **throughput** (Mbps → ~84 homes/kvm4-1 conservative). The
Hostinger data adds the **monthly bandwidth cap** as an independent ceiling:

- kvm4 nodes: **16 TB/mo**. At typical US household usage **~200–400 GB/mo**, that's
  **~40–80 homes/node** on the bandwidth cap alone.
- This **brackets** the throughput-based ~84 — two independent constraints converging on
  **~40–80 homes/node** is a far more defensible pilot figure than either alone.
- **Plan the pilot to the lower bound (~40 homes/kvm4 node)** for headroom; the 3-node
  fleet then comfortably carries a Fordham Hill building, and every node added lifts both
  ceilings.

## Resident dashboard — viewable on a passed-around tablet, over the mesh

SLATE is a **Galaxy Tab S11 Ultra passed around for viewing** — no terminal, no login.
So the observation is rendered as a **calm, non-technical web page served over Tailscale**
(tailnet-private HTTPS, *not* public Funnel). Any tablet/phone on the tailnet opens the URL
in a browser and sees the pilot at a glance; it auto-refreshes every 60s.

- **URL (open on SLATE's browser):** `https://pmoves-kvm4-1.tailcad9b4.ts.net/`
- Shows: homes on the network, % of hub capacity used, community savings /mo + /yr,
  live network speed, privacy state, "all good / needs a look" status, and a plain-language
  "what is this" note. **Numbers residents see are REAL** — from
  `/opt/pilot-dashboard/pilot.conf` (operator edits `HOMES=` as households enroll), never
  hardcoded. Given the fraud context, honesty of the displayed figures is a design rule.
- **Served from:** `pilot-dashboard-serve.sh` on the KVM → systemd static server on
  127.0.0.1:8899 + cron refresh (observer→generator→`index.html`) + `tailscale serve`.

```bash
# deploy/update on a hub
for f in exit-node-observer pilot-dashboard-gen pilot-dashboard-serve; do
  scp deploy/provision/$f.sh root@pmoves-kvm4-1:/opt/pilot-dashboard/ ; done
ssh root@pmoves-kvm4-1 'bash /opt/pilot-dashboard/pilot-dashboard-serve.sh'
# update the household count residents see
ssh root@pmoves-kvm4-1 'sed -i "s/^HOMES=.*/HOMES=32/" /opt/pilot-dashboard/pilot.conf'
```

Verified: reachable over the tailnet (HTTP 200 from another tailnet node → SLATE reaches
it identically). Tailnet-only, no public exposure.

## Operator quick reference

```bash
# Layer 2 — observe an exit node (runs the observer on the VPS over SSH)
make -C pmoves exit-node-observe NODE=pmoves-kvm4-1
make -C pmoves exit-node-observe NODE=pmoves-kvm4-1 FMT=--prom   # -> Grafana textfile

# Layer 1 — VM metrics are pulled via Hostinger MCP (VPS_getMetricsV1) by the operator
#           or a fleet agent; no install needed. Bandwidth-cap tracking lives here
#           (the on-VPS observer shows n/a unless vnstat is installed on the KVM).

# Layer 3 — operator field A/B (see MESH_EGRESS_AB_RUNBOOK.md)
bash deploy/provision/mesh-egress-ab.sh measure --label starlink-direct --save d.json
```

To make the on-VPS observer continuous: install a systemd timer (or cron `* * * * *`)
running `exit-node-observer.sh --prom`; node-exporter's textfile collector picks up
`/var/lib/node_exporter/textfile_collector/pmoves_exit_node.prom` → Grafana. For monthly
bandwidth on the node itself, `apt install vnstat`; otherwise use Hostinger MCP.

## Citations

- `deploy/provision/exit-node-observer.sh` — on-VPS observer
- `deploy/provision/mesh-egress-ab.sh` — operator A/B + capacity
- Hostinger MCP `VPS_getMetricsV1` / `VPS_getVirtualMachinesV1` — VM-level, agent-free
- `pmoves/mk/egress.mk` — `exit-node-observe` target
- `01-capacity-comparison.md` — throughput capacity model (this doc adds the bw-cap dimension)
