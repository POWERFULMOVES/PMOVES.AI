# Fleet Capacity Analysis — Y1-Y5 Sizing & UNFCU Readiness

**Last updated:** 2026-04-19
**Status:** Living document — revisit quarterly and before any major service addition
**Owners:** z890-claude, z890-codex (infra lane)

---

## 1. Purpose

This document maps the **Cataclysm Studios 5-Year Financial Model** user
projections onto concrete per-node Agent Zero / ClawZ capacity across the
PMOVES.AI fleet. It identifies critical pre-UNFCU fixes, the Y3 scale
cliff, and the Proxmox cluster phasing needed to carry the business from
Y1 pilot through Y5 platform maturity.

It is written to answer three operator questions:

1. **Can the current fleet carry UNFCU's Y2 pilot (2,000 users)?**
2. **Where does the fleet fall over (the scale cliff), and when?**
3. **What has to ship BEFORE UNFCU goes live, not after?**

---

## 2. Business Scale Targets

Source: `CATACLYSM_STUDIOS_INC/PMOVES-5-Year-Financial-Model.md`.

| Year | End users | Nodes | Communities | Disaster sites |
|------|----------:|------:|------------:|---------------:|
| Y1   |       500 |    25 |           1 |              1 |
| Y2   |     2,000 |   100 |           3 |              3 |
| Y3   |     8,000 |   300 |          10 |             10 |
| Y4   |    25,000 |   800 |          30 |             25 |
| Y5   |    80,000 | 2,000 |         100 |             50 |

**Critical distinction:** "Nodes" in the financial model are
**community-operator-owned edge compute** (Raspberry Pi, Jetson) deployed
into communities and disaster sites. They are **NOT** part of the PMOVES
core fleet. The core fleet must carry the control plane, central
inference, knowledge base, and orchestration load for all of them.

---

## 3. Hardware Inventory (Owned + Incoming)

| Node                           | CPU / RAM                | GPU / VRAM                  | Role                                   |
|--------------------------------|--------------------------|-----------------------------|----------------------------------------|
| Z890                           | 32C / 128 GB             | RTX 3090 Ti 24 GB           | Win11 dev + Pinokio creator            |
| 5090 PC                        | 24C / 64 GB              | RTX 5090 32 GB              | Mixed Win11 + WSL2 + Docker            |
| 4090 laptop                    | ? / ? (unknown)          | RTX 4090                    | Secondary creator Win11                |
| **DGX Spark (new)**            | 20C Arm / 128 GB unified | GB10 (128 GB shared)        | Heavy inference target                 |
| **9850X3D + 2× R9700 (new)**   | 8C / 32 GB               | 2× R9700 (64 GB total)      | ROCm llama.cpp HIP                     |
| 2× Jetson Orin Nano            | 8C Arm / 8 GB shared     | integrated                  | Edge / Claws                           |
| New PVE host (TBD)             | ≥8C / ≥64 GB             | none                        | Hypervisor                             |
| KVM4-1 (Hostinger)             | 8 vCPU / 16 GB           | —                           | API gateway + YT egress exit           |
| KVM4-2 (Hostinger)             | 8 vCPU / 16 GB           | —                           | Data tier (**OVER-SUBSCRIBED** ~29 GB declared) |
| KVM2 (Hostinger)               | 4 vCPU / 8 GB            | —                           | nginx/SSL + RustDesk relay             |

Additional detail on the Hostinger KVMs lives in
[`FLEET_REMOTE_ACCESS_RUNBOOK.md`](./FLEET_REMOTE_ACCESS_RUNBOOK.md);
node-to-service-to-route mapping is the authoritative
[`TOPOLOGY.md`](./TOPOLOGY.md).

---

## 4. Per-Node Concurrent Agent Zero / ClawZ Capacity

**Sizing unit:** 2 GB RAM per active Agent Zero or ClawZ worker (empirical
estimate — see [Verification](#9-verification) to tighten with real
Prometheus numbers).

| Node             | Usable RAM after OS + other services                            | Concurrent A0/ClawZ cap | Notes                                         |
|------------------|------------------------------------------------------------------|------------------------:|-----------------------------------------------|
| Z890             | ~80 GB (32 Pinokio + 16 OS reserve)                              |                     ~40 | Biggest, but Win11 host via WSL2              |
| 5090 PC          | ~40 GB                                                           |                     ~20 | Mixed Win11 + WSL2                            |
| 4090 laptop      | 20-50 GB                                                         |                   10-25 | RAM unknown — measure before committing      |
| DGX Spark        | 8 GB (Nemotron3 120B FP8 loaded) or ~100 GB (small models only)  |                    3-50 | Primary inference target                      |
| 9850X3D + R9700  | ~12 GB (llama-server + OS reserve)                               |                      ~6 | Inference-first; few A0 workers               |
| Jetson (each)    | ~4 GB                                                            |                       2 | Edge Claws                                    |
| KVM4-1           | ~6 GB (stack eats 10)                                            |                      ~3 | Tight                                         |
| KVM4-2           | **-13 GB (over-subscribed)**                                     |                       0 | **MUST FIX before UNFCU**                     |
| KVM2             | ~4 GB                                                            |                      ~2 | Less after Headscale deploy                   |
| **FLEET TOTAL**  | —                                                                |   **~90-150 concurrent** | Depends on DGX Spark mode                     |

The 60-slot range on DGX Spark (3 vs. 50) dominates the fleet-total
variability. Nemotron3 120B FP8 resident ⇒ small worker headroom; small
models only ⇒ abundant headroom. Policy for which mode to run when is
captured in [`MODEL_ONBOARDING.md`](./MODEL_ONBOARDING.md).

---

## 5. Y1-Y5 Demand vs. Fleet Capacity

Assumption: **10% peak concurrency** (industry-typical for asynchronous
AI workloads with short turn-taking patterns).

| Year | Users  | Peak concurrent | Fleet cap   | Gap                               |
|------|-------:|----------------:|-------------|-----------------------------------|
| Y1   |    500 |              50 | 90-150      | 2-3x headroom                     |
| Y2   |  2,000 |             200 | 90-150      | **break-even** — optimize         |
| Y3   |  8,000 |             800 | 90-150      | **6-9x underprovisioned**         |
| Y4   | 25,000 |           2,500 | 90-150      | ~20x underprovisioned             |
| Y5   | 80,000 |           8,000 | 90-150      | ~60x underprovisioned             |

**Read:**

- Fleet carries **Y1 comfortably** and **Y2 at break-even** with the new
  hardware landed.
- **Y3 is the scale cliff.** The fix is not "buy more Z890s." The fix is
  Proxmox scale-out + cloud GPU burst + community-edge offload (pushing
  inference toward the community-operator Pi/Jetson nodes that are
  already counted in the financial model).
- By Y4-Y5, the core fleet is a control plane / training-and-distillation
  factory / enterprise tenant host. End-user inference is served from
  community edge + cloud burst.

---

## 6. Exit-Node Product (B2B2C) Capacity Math

PMOVES offers exit-node service as a product line (separate from the
platform). Hostinger KVMs deliver ~1 Gbps symmetrical; 10 Mbps/user peak
budget yields ~100 concurrent users per KVM.

| Year | Exit users | KVMs needed | VPS cost    | Revenue @ $5/user/mo |
|------|-----------:|------------:|-------------|----------------------:|
| Y1   |         50 |           1 | $5-10       |              $2.5K/mo |
| Y2   |        200 |           2 | $10-20      |               $10K/mo |
| Y3   |        800 |           8 | $40-80      |               $40K/mo |
| Y4   |      2,500 |          25 | $125-250    |              $125K/mo |
| Y5   |      8,000 |          80 | $400-800    |              $400K/mo |

**Hard architectural rule:** Do **NOT** colocate exit-node user traffic
with the PMOVES API traffic. KVM4-1 currently runs both the API gateway
and YT egress; adding paying exit-node users to that box would couple
product uptime to API uptime. **Split the exit-node tier to dedicated
VPS fleet before the user-facing product launches.**

---

## 7. Critical Pre-UNFCU Fixes

These must land BEFORE UNFCU Y2 pilot goes live, not after.

| Problem                                                | Fix                                                                                                          |
|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| KVM4-2 over-subscribed (~29 GB declared on 16 GB box)  | Upgrade to Hostinger 32 GB tier **OR** split Supabase to new VPS **OR** migrate data tier to on-prem         |
| No concurrency caps on Agent Zero                      | Add `AGENT_ZERO_MAX_WORKERS=4` env var (or tuned value from measured footprint)                               |
| YT egress + future user exit traffic share KVM4-1      | Split tier **BEFORE** user product launches                                                                  |
| No Agent Zero horizontal scaling pattern               | Proxmox + VM templates = tenant-per-stack                                                                    |
| No load/capacity baseline                              | Add `k6` or `vegeta` smoke: 100 req/s × 10 min against Hi-RAG + A0 MCP                                       |

---

## 8. Proxmox Cluster Phasing (Y1 → Y5)

### Phase 1 (Y1-Y2, now through UNFCU pilot)

- New PVE host stands up as sole hypervisor.
- 9850X3D + R9700 runs bare-metal (maximum ROCm performance, no
  virtualization tax).
- DGX Spark standalone (its own OS, its own stack).
- Hostinger KVMs unchanged in role.
- **Goal:** carry Y1-Y2 without platform rewrite.

### Phase 2 (Y3, 10 communities online)

- Add PVE host #2. Candidate hardware: 5090 PC reinstalled as hypervisor,
  or new HW — decision deferred until 5090 PC creator workload is migrated.
- Ceph or ZFS replication between PVE hosts.
- **Live-migratable UNFCU VMs = enterprise HA story** (this is the
  capability that justifies the enterprise tier of UNFCU's contract).

### Phase 3 (Y4-Y5)

- PVE host #3.
- Dedicated exit-node VPS fleet (separate from platform KVMs — see §6).
- Cloud GPU burst contract (~$5-20K/mo budget line) for peak demand
  beyond on-prem capacity.
- Community-edge inference offload is now load-bearing, not experimental.

---

## 9. Verification

This doc is only useful if its numbers stay honest. Three measurements
should be re-run before every major capacity decision.

### 9.1 Real Agent Zero footprint (Prometheus)

The 2 GB/worker sizing unit is an estimate. Tighten with:

```bash
# Average resident memory per Agent Zero worker over the last hour
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=avg(container_memory_working_set_bytes{name=~"agent-zero.*"}) / 1024 / 1024'

# Peak over last 24h (sizing for worst case, not average)
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=max_over_time(container_memory_working_set_bytes{name=~"agent-zero.*"}[24h]) / 1024 / 1024'
```

Update the "concurrent A0/ClawZ cap" column of §4 whenever the measured
footprint drifts more than 25% from the 2 GB assumption.

### 9.2 Load / capacity baseline

No load test exists today. Add one of:

**k6:**

```bash
# Install (one-off, host-side)
choco install k6   # Windows
# or: brew install k6
sudo apt install -y k6  # Debian/Ubuntu (Hostinger KVMs)

# 100 req/s × 10 min against Hi-RAG v2
k6 run --vus 20 --duration 10m - <<'EOF'
import http from 'k6/http';
export default function () {
  http.post('http://localhost:8086/hirag/query',
    JSON.stringify({query: 'test', top_k: 10, rerank: true}),
    {headers: {'Content-Type': 'application/json'}});
}
EOF
```

**vegeta:**

```bash
echo "POST http://localhost:8086/hirag/query
Content-Type: application/json
@hirag_query.json" | vegeta attack -rate=100 -duration=10m | vegeta report
```

Run both Hi-RAG and A0 MCP targets. File the result in
`pmoves/docs/operations/LOAD_TEST_BASELINE.md` (create on first run).

### 9.3 KVM4-2 over-subscription verification

```bash
# Sum declared memory of containers on KVM4-2 (run on the box)
ssh kvm4-2 'docker stats --no-stream --format "{{.Name}} {{.MemUsage}}"'

# Compare to host capacity
ssh kvm4-2 'free -h'
```

If the sum of container limits (or peak working set) exceeds the 16 GB
host, the box is OOM-risk. Current declared sum is ~29 GB — **actively
over-subscribed today**. One of the §7 three options must ship before
UNFCU onboarding.

---

## 10. See Also

- [`TOPOLOGY.md`](./TOPOLOGY.md) — master topology (nodes, services, routes, DNS)
- [`MODEL_ONBOARDING.md`](./MODEL_ONBOARDING.md) — model registry + VRAM budget estimation
- [`FLEET_REMOTE_ACCESS_RUNBOOK.md`](./FLEET_REMOTE_ACCESS_RUNBOOK.md) — fleet node access, Tailscale + RustDesk
- `CATACLYSM_STUDIOS_INC/PMOVES-5-Year-Financial-Model.md` — source of user and node projections

---

## 11. When to Revisit This Doc

Revisit and update this document:

- **Quarterly** — routine freshness cadence.
- **Before adding any major service** — new service = new resident
  footprint = capacity column drift.
- **When hardware lands or leaves the fleet** — DGX Spark arriving,
  9850X3D+R9700 arriving, 4090 laptop RAM finally measured, new PVE
  host online, a KVM decommissioned.
- **Before an enterprise client contract is signed** — UNFCU was the
  forcing function for v1 of this doc; the next enterprise client will
  be the forcing function for v2.
- **After any load / capacity test run** — the numbers in §4 and §5 are
  best-guess until measured; measurement updates beat guess updates.
- **When the financial model is revised** — user/node projection
  changes ripple directly into §2 and §5.

End of document.
