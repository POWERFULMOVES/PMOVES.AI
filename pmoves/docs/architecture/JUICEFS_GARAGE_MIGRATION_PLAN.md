# JuiceFS `pmoves-media`: Garage migration plan and runbook

**Status:** Step 0 baseline MEASURED (2026-10-01, read-only, see "Step 0 record" in §3). **Phase A approved by the operator (2026-10-01)**; its agent-doable prep is done (§7). Steps (a)-(e) NOT executed; Step (a) is blocked on the operator items in §7 and the gates in the Step 0 record. Phase B (cutover, Steps c-e) is a separate go. Every step in §3 is operator-gated.
**Lane:** `feat/juicefs-garage-migration`, owner B850-CLAUDE-FUNNEL (Knuckles), register PR #3198.
**Replaces:** the interim MinIO bridge (PR #3192, `pmoves/docker/minio-src/README.md`).
**Decided upstream:** `JUICEFS_OBJECT_STORE_MIGRATION.md` §0.8: Garage, self-hosted; asymmetric availability accepted. Broadened by operator direction (2026-09-27) to a **fleet-wide** Garage mesh with decided availability tiers (§1.0, §1.1). **D1 decided: replicated Postgres** (§2).
**Why not Supabase S3:** PR #3199, §12 of the same doc. JuiceFS cannot LIST through storage-api, so `gc`, `fsck` and `destroy` see nothing.

## 0. Scope

| In scope | Out of scope |
|---|---|
| Move the **object data** of JuiceFS `pmoves-media` from MinIO bucket `juicefs` to a Garage bucket on the fleet-wide Garage cluster (§1) | The metadata engine move. D1 is decided (replicated Postgres, §2); the move gets its own follow-on plan |
| `juicefs config` switch of the volume's storage, plus rollback | MinIO's **other** buckets (`assets`, `outputs`, `pmoves-comfyui`) and their ~10 S3 consumers (parent §3/§5/§9) |
| Retiring MinIO's **`juicefs` bucket role** after a soak | Deleting `pmoves_minio-data`. Only an explicit operator deletion does that |

**Today (from the inputs; not re-measured by this lane):**

| Item | Value | Source |
|---|---|---|
| Volume | `pmoves-media`, `Storage: minio`, `Bucket: http://minio:9000/juicefs` | parent §0.1 |
| Metadata | Postgres `supabase-db` on Knuckles, schema `juicefs_meta`, role `juicefs_meta` | PR #3150 notes |
| Object store | MinIO `RELEASE.2025-09-07T16-13-09Z` (source build) on volume `pmoves_minio-data`, Knuckles | PR #3192 |
| Size | ~85 GB on the MinIO volume; JuiceFS reports ~76 GB used | operator brief |
| Mount | `juicefs-mount` on `pmoves_data`, cache on NVMe1 `/mnt/pmoves-nvme1/juicefs-data` | PR #3150 |
| Object layout | `pmoves-media/chunks/...` (data), `pmoves-media/meta/` (hourly metadata auto-backup), `pmoves-media/juicefs_uuid` | JuiceFS `development/internals.md`, `metadata_dump_load.md` |

The 85 vs 76 GB gap is unexplained. It could be trash, leaked objects, auto-backups or MinIO overhead. Step 0 measures it before anything is copied.

## 1. Target topology: a fleet-wide Garage mesh

### 1.0 Operator direction, and the prior art it aligns with

**Operator direction (2026-09-27):** "each node should be able to run file share; it will happen across the mesh. This is the point: Google Drive is on each; we are looking for our own."

- **The Garage cluster is fleet-wide.** Every capable PMOVES node is both a Garage storage node and a JuiceFS client over the Tailscale mesh. That covers Knuckles/B850, 5090, 4090, Z890, Spark and the three KVMs.
- **What runs on the mesh.** File sharing is an application on the mesh, and that is allowed. NATS stays off the mesh, and this plan routes nothing else through it.
- **Relation to parent §0.8.** This broadens "Garage, self-hosted on the KVMs". The KVMs stay in the layout as the always-on tier (§1.2), and the lab nodes join them.
- **The migration itself (§3) is unchanged:** sync, then `juicefs config --storage`, then gates and rollback. Only the target layout changes.
  - The first cut can start from whichever nodes are ready. The rest join later through layout changes (`garage layout assign`, then `garage layout apply --version N+1`).
  - Garage moves partitions on its own after each apply. Its algorithm "prioritizes moving less data between nodes over achieving equal distribution of load" (Garage v2.4.1 `operations/layout.md`, "Understanding unexpected layout calculations").

**Prior art.** This plan builds on these earlier decisions; it does not replace them.

| Source | What it already settled |
|---|---|
| `pmoves/docs/architecture/UNIVERSAL_MEDIA_ARCHITECTURE.md` (2026-07-28) | "Every node (5090, Z890, Knuckles, KVM4-2, SPARK) sees the same content library". Layer 2 is a JuiceFS POSIX mount "shared across mesh". Data backend "MinIO (Phase 1-2) → Garage/SeaweedFS (Phase 5)". Gaps it lists: no `tag:storage`, and no disk-capacity tracking ("profiles have `storage: \"NVMe SSD\"` labels, no sizes"). Phase 7 adds `pmoves_core.node_storage_status` for capacity planning |
| `pmoves/docs/handoffs/MEDIA_DATA_ARCHITECTURE_PLAN.md` | Mode B: one JuiceFS POSIX mount, fleet-wide. Storage services behind a Tailscale sidecar with `tag:storage`. Step 5: "Replace EOL MinIO backend (Garage/SeaweedFS/external S3) — consumers insulated" |
| `pmoves/docs/architecture/FLEET_ACCESS_NATS_HUB.md` §4 (lines 80-115) | Storage services get a Tailscale sidecar (`network_mode: service:ts-...`, ephemeral `tag:storage` key). "NATS is *not* co-located with inference or storage concerns" (line 68) |
| PR #2288 (merged) | JuiceFS Phase 1 POSIX mount, the cross-node recipe, and a Tailscale `tag:storage` ACL. The presence of `tag:storage` in the live ACL was not re-verified by this lane |
| `juicefs-cross-node-setup` (`pmoves/mk/egress.mk:318`) | The canonical client-mount road for a node that does not host metadata (`META_ROLE=juicefs_meta`) |
| Parent §0.4 | Garage's design target is "multi-sites (eg. datacenters, offices, households) interconnected through regular Internet connections". Reference deployments: 9 nodes / 3 sites, and 15 nodes / 3 sites |

### 1.1 Nodes and availability tiers

**Tiers: DECIDED by the operator (2026-09-27): "always-on nodes carry more of the load."**

| Tier | Nodes | Status |
|---|---|---|
| **1: always-on** | `pmoves-kvm2`, `pmoves-kvm4-1`, `pmoves-kvm4-2`, Spark | DECIDED |
| **2: desktop** | 5090, Z890, Knuckles (B850), 4090 | DECIDED |

All nodes have a tier.

**"Always-on" is a class, not a guarantee.** On 2026-09-27, when the tiers were decided, **Spark was DOWN**. A tier-1 node can be unavailable, and this is a live example of the plan's own availability risk. None of the layout or quorum reasoning in §1.2 assumes that every tier-1 node is up.

**Tier 1 (KVMs), measured:**

| Node | Plan / total disk | Root fs | Free now | Unused docker volumes | Free if cleared | RAM total / avail | vCPU | BW cap / month |
|---|---|---|---|---|---|---|---|---|
| `pmoves-kvm2` | KVM 2 / 100 GB | ext4 96G, 19% used | **78G** | ~0 | ~78G | 7G / 5G | 2 | 8 TB |
| `pmoves-kvm4-1` | KVM 4 / 200 GB | ext4 193G, 93% used | **15G** | 139.5G (15 of 21 volumes unused) | ~150G | 15G / 11G | 4 | 16 TB |
| `pmoves-kvm4-2` | KVM 4 / 200 GB | ext4 193G, 85% used | **31G** | 146.4G (0 of 3 volumes in use) + 3.6G images | ~180G | 15G / 12G | 4 | 16 TB |

- **Sources:**
  - Plan, total disk, vCPU and RAM come from the Hostinger REST API (read-only GETs, 2026-09-27, all HTTP 200). They supersede the conflicting recorded values of 100, 200 and 400 GB in `research/KVM_HOSTINGER_NETWORK_REPORT.md`, `docs/architecture/kvm-exit-node-hosting-strategy.md` and `pmoves/docs/context/Visionary AI_ Global Network, Local Power.md`.
  - Root fs, free space, docker volumes and RAM available come from the KVM shell survey: run as root, read-only, 2026-09-27, nothing changed.
  - Bandwidth caps are Hostinger-reported, from `pilots/fordham-hill/06-pilot-observation.md`.
- **Topology facts:**
  - None of the three has a separate data disk or an attached Hostinger volume. The only way to add disk is a plan upgrade: KVM 8 has 400 GB, 8 vCPU and 32 GB RAM.
  - All three are in Hostinger `data_center_id` 17 (Hostinger REST, read-only, 2026-09-27). Their zones are node-level failure domains, not site-level ones. A data-center outage takes all three, which is the §0.6 "VPS down" case that §0.8 accepted.
  - `tailscale ping` between every KVM pair is direct, at 1-5 ms (survey, 2026-09-27).
  - **kvm4-1 accepted NO inbound tailnet connection** to a listening test port. Clients on kvm4-2 and Knuckles timed out (peer session, 2026-09-27). The cause is **COULD-NOT-MEASURE**; it was not investigated. Garage RPC on 3901 must accept inbound connections from every peer, so this is a **G0 / Gate A BLOCKER for kvm4-1 as a Garage node**.
- kvm4-2's profile says it is **over-subscribed**: "resolve before adding data-plane services here".

**Hostinger 7-day metrics** (peer session, read-only, 336 samples per node, 2026-09-27):

| Node | Free disk | 7-day growth | Note |
|---|---|---|---|
| kvm2 | ~82 GB | — | — |
| kvm4-1 | ~21 GB | **+35 GiB** | Full in about a week at this rate |
| kvm4-2 | ~38 GB (dipped to ~19) | **+64 GiB** | Rebooted around 2026-09-23 |

- **Disk.** The kvm4s grow 5-9 GiB/day. The writer is now identified as **BuildKit build cache** (the HARD CAUTION below). Until the cache is capped or pruned through the build-cache road, KVM declared capacity is **tiny**, and it may shrink before this plan runs. That ops item is **owned outside this plan**. It feeds D3.
- **Network.** Peak 30-minute throughput is ≤ 39 Mbit/s against a ~300 Mbit/s port, and monthly transfer is ~5% of the allowance. These are averages, so they are a **floor for usage, not a measure of capacity**. The iperf3 measurements (§3 Time and bandwidth, D8) show that the binding constraint is **Knuckles' uplink**, at ~18 Mbit/s, not the KVM ports.
- These metrics differ slightly from the shell survey above (for example kvm4-1 at 15G vs ~21G). They were taken at different times, on a disk that is filling.

> **HARD CAUTION: reclaim build cache, never delete volumes.** The kvm4s' growth and their "unused" space have been identified (peer session, read-only, 2026-09-27). It is **one** volume: the BuildKit state volume `buildx_buildkit_pmoves-shared0_state`, ~140 GB on kvm4-1 and ~146 GB on kvm4-2. The other "unused" volumes are empty. No MinIO, JuiceFS or PGDATA store is among them.
> - Space is reclaimed **through the build-cache road**: a builder GC cap, or `buildx prune`, run by the builder's owner. It is **not** reclaimed by deleting a docker volume, and never by a blanket prune.
> - That ops item is **owned outside this plan**. This plan only consumes the result.
> - This is the **G0 item "KVM build cache reclaimed through the build-cache road before declaring capacity"** (§5). Until it passes, the KVM capacity declarations use **free now**, not "free if cleared".

**Spark (tier 1) and the tier-2 nodes:**

| Node | Tier | OS (profile) | Free disk for Garage | Note |
|---|---|---|---|---|
| Spark | 1 | DGX OS 7.5.0, arm64 (`dgx-spark-grace-blackwell.yaml:21,29`) | **COULD-NOT-MEASURE** (the node is down) | **DOWN on 2026-09-27.** arm64: the fork image is built for arm64 (§6.2); whether it runs well on Spark is COULD-NOT-MEASURE. Spark is also a secrets-bundle producer (§1.6) |
| Knuckles / B850 | 2 | linux (`workstation-9850x3d-dual-r9700.yaml:29`) | **COULD-NOT-MEASURE** | Hosts `supabase-db` and MinIO today. The NVMe1 seat is in #3150. It is the other secrets-bundle producer |
| Z890 | 2 | not recorded in `z890-coordinator.yaml` | **COULD-NOT-MEASURE** | — |
| 5090 | 2 | windows (`workstation_5090.yaml:32`) | **COULD-NOT-MEASURE** | Windows: see §1.3a |
| 4090 | 2 | not recorded in `laptop-4090.yaml` | **COULD-NOT-MEASURE** | Laptop. If it runs Windows, §1.3a applies |

**D3: OPEN — per-node capacity declarations for each fleet node.**
- Each node is its own zone by default (§1.2 covers the one exception under consideration). Each node declares its own `-c`.
- The declaration is bounded by that node's measured free space, minus headroom (G1).
- Record each declaration in the node's profile under `pmoves/config/profiles/`. `UNIVERSAL_MEDIA_ARCHITECTURE.md` already names the missing sizes there as a gap.
- The KVM sizes are one input among many, not a blocker. The earlier verdict, "a 3-KVM RF=3 cluster caps at the smallest node", described a KVM-only layout. That layout is no longer the plan.

**Operator measurement (read-only) for every node that has not been surveyed:**
```bash
df -hT / /var/lib 2>/dev/null; lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT; free -g; docker system df
```

### 1.2 Replication, capacity and how the layout expresses the tiers

**Replication:** RF=3, `consistency_mode = "consistent"`, one zone per node by default. Quorums are from Garage v2.4.1 `reference-manual/configuration.md` (quorum table):

| `replication_factor` (consistent mode) | Write / read quorum | One replica of a partition down |
|---|---|---|
| 2 | 2 / 1 | **read-only** for that partition (writes fail) |
| **3** | 2 / 2 | **reads and writes continue** |

- RF=3 is the only consistent setting in which one node offline stops neither reads nor writes.
- RF cannot be changed safely later: that needs a layout rebuild and a full rebalance (same doc). So choose it once.

**Capacity semantics** (corrects the earlier "usable = smallest node's `-c`"):
- **What the Garage docs say.** Garage "will **always** store the three copies of your data on nodes at different locations", and usable capacity is bounded by what each zone can hold (`cookbook/real-world.md`, the 4-node, 3-location example: 1.5 TB usable out of 6.5 TB raw). In `operations/layout.md` Example 1, adding a node to one zone adds nothing, because "the two other zones still need to store a full copy of everything".
- **Exactly 3 zones at RF=3:** every zone holds a full copy, and usable capacity equals the smallest zone's capacity.
- **N > 3 zones of mixed sizes:** usable capacity is the largest U for which the per-zone sum of min(zone capacity, U) is at least 3U. When no zone exceeds a third of the total, that is roughly sum ÷ 3.
  - This formula is **derived here** from the docs' "different zones" rule. It is not stated in that form in the v2.4.1 docs.
  - **Gate:** read the authoritative figure from `garage layout show` before `layout apply`. The docs show it printing "Usable capacity / total cluster capacity" and "Effective capacity (replication factor 3)".

**How the layout expresses the decided tiers.** A Garage layout has only three per-node inputs: role (storage with a capacity, or gateway with none), zone, and capacity. Tags are labels (`operations/layout.md`, `cookbook/real-world.md` "Best practices"). **There is no per-node availability, priority or preference attribute.** There is one cluster-level parameter, zone redundancy (`garage layout config -r`), and the "distinct zones" guarantee below depends on it staying `maximum` (review N2). So "always-on carries more of the load" has to be expressed through the two levers below.

1. **Capacity weighting: applied, and it implements the decision.**
   - Tier-1 nodes declare as much capacity as their headroom allows. Tier-2 nodes declare less.
   - Each node's share of partitions is **bounded by** its declared capacity, so tier 1 can hold a larger share of the replicas. The share is not strictly proportional: the algorithm first maximizes usable capacity, then minimizes data movement (`operations/layout.md` L99).
   - Example 1 in `operations/layout.md` shows the docs' own use of this lever: halve a node's declared capacity to force data off it.
   - **Limit:** weighting shifts proportions. It **cannot guarantee** that a partition keeps 2 replicas on tier 1. Under one zone per node, some partitions will have 2 or 3 replicas on tier-2 nodes. When those nodes sleep or reboot, that partition loses its 2-of-2 read quorum and its write quorum, for **every** client, including KVM Jellyfin. The layout cannot express "prefer tier 1 for quorum" by itself.
2. **Zone grouping: the strongest structural lever. OPEN — OPERATOR, because it departs from "one zone per node".**
   - Give each tier-1 node its own zone (kvm2, kvm4-1, kvm4-2, spark), and put **all tier-2 nodes in one shared zone** (e.g. `lab`).
   - With replicas "on at least 3 distinct zones" (`garage layout show` output in `operations/layout.md`), each partition then has at most one replica in `lab`. This holds **only while zone redundancy is `maximum`**, which Gate A and G1 check. At least two of every partition's replicas sit on tier 1.
   - **What this does NOT guarantee:** quorum survives all of tier 2 going down **only while that partition's tier-1 replicas are up**. With Spark down (as on 2026-09-27), every partition whose replicas are {spark, one KVM, lab} runs on a single live replica if `lab` is also down. With consistent RF=3 that means **no reads and no writes** for those partitions. Two tier-1 failures, or one tier-1 failure plus the `lab` zone, stop some partitions whatever the layout is.
   - The cost is that the tier-1 zones must together hold **two copies of everything**.
   - **Limit shared by both levers (§6.1 row 22).** A bucket's object index is not sharded: it lives on RF nodes "chosen at random", and "there is no way of choosing which nodes" (`reference-manual/known-issues/` "Buckets are not sharded"). Capacity weighting does not move the index of bucket `juicefs`, so its index replicas may sit on tier-2 nodes. Under zone grouping, at most one index replica can sit in `lab`. Where the index lands after `bucket create` is COULD-NOT-MEASURE (no documented command).

**Emergency lever, operator-only (§6.1 row 4): `consistency_mode = "degraded"`.** `reference-manual/configuration/` `consistency_mode`: `degraded` lowers the read quorum to 1, so reads continue with one replica of a partition up (the Spark-down plus `lab`-down case above). The cost is the loss of read-after-write consistency. It is never the default. It must be set identically on every node (§6.1 row 3), so switching it is a fleet-wide re-render and restart, and switching back is the same.

**What today's measured free space allows.** The figures below are arithmetic on the §1.1 survey, with G1's headroom rule applied: declared capacity ≤ half of measured free space. They are not measurements, and tier-2 capacity is COULD-NOT-MEASURE.

| Tier-1 declared `-c` (G1 half-of-free) | kvm2 | kvm4-1 | kvm4-2 | Spark | KVM total |
|---|---|---|---|---|---|
| Today ("free now") | ~39G | ~7G | ~15G | COULD-NOT-MEASURE (down) | ~61G |
| After build-cache reclaim (G0; through the build-cache road, never volume deletion) | ~39G | ~75G | ~90G | COULD-NOT-MEASURE | ~204G |

- **The tension.** The volume needs ~85 GB × 3 = ~255 GB of replica space, before growth.
  - **Today** the KVMs can hold at most ~61G of that, about a quarter. Spark's share is unknown while it is down. Most quorum-bearing replicas would sit on tier 2. That is the opposite of the decided tiering, and it persists until the KVM build cache is reclaimed through the build-cache road, or until Spark's capacity is measured and declared.
  - **Zone grouping today, KVMs only** (Spark excluded while down): usable U ≤ ~23 GB, by the formula above over zones {kvm2 39, kvm4-1 7, kvm4-2 15, lab large}. That is **below the ~85 GB needed**, so zone grouping is not an option until the build cache is reclaimed or Spark adds capacity.
  - **After build-cache reclaim, KVMs only:** zone grouping gives U ≤ ~102 GB. That fits ~85 GB with thin headroom for growth. Spark raises the bound by an amount that cannot be computed until its free space is measured.
  - One-zone-per-node with capacity weighting fits the data today, because tier 2 supplies the capacity. It trades away the quorum guarantee for as long as tier 1 stays small.
- **Tier-2 availability hazards (named, not decided).**
  - Desktops and Windows nodes sleep, take update reboots, and may not start Docker Desktop until someone logs in.
  - Which tier-2 nodes are actually up 24/7 is COULD-NOT-MEASURE, because no profile records uptime.
  - A tier-2 node that holds replicas also works against the §0.8 asymmetry ("operators keep viewing when the lab is down"). This plan names that; it does not resolve it.

### 1.3 `garage.toml` (rendered per node; no secret values in the file)

The tracked template is `pmoves/config/garage/garage.toml.tmpl`. `make -C pmoves garage-render GARAGE_TIER=1|2 [GARAGE_PEERS=<file>]` renders it to the gitignored `pmoves/config/garage/rendered/garage.toml` (`pmoves/tools/garage_render_config.py`, tested in `pmoves/tools/tests/test_garage_render_config.py`). The rendered shape:

```toml
replication_factor = 3                                  # identical on every node (§6.1 row 3)
consistency_mode   = "consistent"
metadata_dir       = "/var/lib/garage/meta"
data_dir           = "/var/lib/garage/data"
metadata_snapshots_dir = "/var/lib/garage/snapshots"   # sibling of data_dir, not inside it; up to 4x meta size
metadata_auto_snapshot_interval = "6h"
db_engine          = "lmdb"                             # tier 1; "sqlite" on tier 2 (operator decision, §6.1 row 15)
compression_level  = "none"                             # ciphertext is incompressible (§6.1 row 18)

rpc_secret_file = "/run/secrets/pmoves_garage_rpc_secret"
rpc_bind_addr   = "<this node's tailnet IPv4>:3901"
rpc_public_addr = "<this node's tailnet IPv4>:3901"
bootstrap_peers = ["<node id>@<peer tailnet IPv4>:3901", ...]   # tracked membership (§6.1 row 12)

[s3_api]
api_bind_addr = "<this node's tailnet IPv4>:3900"      # never [::]: the KVMs are public exit nodes
s3_region     = "us-east-1"          # see 1.4: matches JuiceFS's default region

# no [s3_web]: 3902 is never bound (§6.1 row 8)

[admin]
api_bind_addr         = "<this node's tailnet IPv4>:3903"
admin_token_file      = "/run/secrets/pmoves_garage_admin_token"
metrics_token_file    = "/run/secrets/pmoves_garage_metrics_token"
metrics_require_token = true                            # §6.1 row 6
```

- **Image:** ~~`dxflrs/garage:v2.4.1`~~ **superseded 2026-10-01 by operator direction:** build from the PMOVES fork `POWERFULMOVES/PMOVES-garage` (`PMOVES.AI-Edition-Hardened`, cut at upstream tag `v2.4.1`), push to GHCR, pin by digest per F-07. See §6.2 and §7.
- **Network:** host networking, per Garage's `cookbook/real-world.md`.
- **Snapshots dir:** `/var/lib/garage/snapshots` is a sibling of `data_dir`. It must not sit inside `data_dir`, which Garage manages as its block store.
- **Bind addresses (RPC: operator decision, §6.3):** S3, admin **and RPC** all bind to the node's tailnet address, so nothing listens on a public interface. (Changed 2026-10-01 from RPC on `[::]`: peers dial `rpc_public_addr`, which is the same tailnet address, and the CLI dials `rpc_public_addr` too, per v2.4.1 `src/garage/main.rs`, so nothing needs the wildcard bind.) A bind to a tailnet address fails if `tailscaled` is not up when Garage starts; the compose service relies on `restart: unless-stopped`. The renderer refuses any address outside `100.64.0.0/10`. The firewall rule and the external probe below are still required.
- **Firewall (required on every storage node, and critical on the KVMs because they are public exit nodes):** allow 3900/3901/3903 on `tailscale0` only. Tier-2 nodes sit behind residential NAT, but the same rule applies. No port-forward for 3900/3901/3903 may exist on any router in front of them.
- **Hostinger firewall today (Hostinger REST, read-only, 2026-09-27):** no Hostinger firewall rule mentions 3900, 3901 or 3903, and no drop rules exist. The API does not expose the default policy. So whether these ports are closed on the public addresses is **COULD-NOT-MEASURE** from the API.
- **Baseline probe, before any Garage exists (2026-10-01, B850-CLAUDE from Knuckles, read-only TCP connects, 4 s timeout).** Target: each KVM's public IPv4 as reported in `tailscale status --json` `CurAddr` (direct paths, no exit node in use on Knuckles; addresses not recorded here). Knuckles reaches the internet over its residential uplink, not the tailnet, so this is an outside-the-tailnet vantage.

  | Node | 3900 | 3901 | 3903 | Controls: 22, 80, 443 |
  |---|---|---|---|---|
  | kvm2 | timeout | timeout | timeout | timeout |
  | kvm4-1 | timeout | timeout | timeout | timeout |
  | kvm4-2 | timeout | timeout | timeout | timeout |

  The same socket code reached `github.com:443` and `:22` (outbound path healthy). Every port timed out rather than being refused, including 22, 80 and 443, which is the signature of an inbound default-drop on the KVMs' public IPv4, the policy the Hostinger API does not expose. **This does not pass the gate:** nothing listens on 3900/3901/3903 yet, the KVMs' public IPv6 addresses were not probed, and the gate is defined on running Garage nodes.
- **External port-probe gate (REQUIRED; OPEN — OPERATOR):** before Gate A passes, probe **all three ports (3900, 3901, 3903) on every KVM's public address from a host outside the tailnet**. Every probe must be refused or time out. One open port fails the gate. A probe from inside the tailnet proves nothing, because tailnet traffic is allowed by design. Who runs the probe, and from which outside host, is an operator decision.

### 1.3a Garage on Windows nodes (5090; the 4090 if it runs Windows)

Every item in this subsection is **COULD-NOT-MEASURE** until someone tries it on the node.

- **Runtime.** A Linux container under Docker Desktop (WSL2 backend), using the same fork image digest pin as the Linux nodes (§6.2).
- **Secrets.** `pmoves_garage_rpc_secret` and the admin and metrics tokens are delivered by the funnel, as for any node. The funnel's Windows delivery route for these labels is unverified. It is the same gap as KVM delivery (§1.6, G2).
- **Networking.** Garage's cookbook uses host networking, and §1.3 binds to the node's tailnet address. Inside Docker Desktop's VM, neither the host's tailnet interface nor host networking can be assumed.
  - Prior-art fit: the **Tailscale sidecar** pattern (`FLEET_ACCESS_NATS_HUB.md` §4). The Garage container gets its own tailnet identity with `tag:storage`, and `rpc_public_addr` is the sidecar's tailnet address.
- **Disk.** Keep `metadata_dir` (LMDB) on a volume inside the Docker Desktop VM, not on a bind-mounted Windows drive. LMDB behaviour over the Windows-to-WSL file share is unverified. The VM disk's size cap bounds the node's declared capacity.
- **Availability.** Docker Desktop normally starts at user login, not at boot. That is a tier-2 availability hazard (§1.2).

### 1.4 S3 endpoint as JuiceFS sees it

| Setting | Value | Why |
|---|---|---|
| `--storage` | `s3` | Garage is a generic S3 target |
| `--bucket` | `http://<ENDPOINT>:3900/juicefs` | Path-style. JuiceFS uses path-style for non-AWS endpoints by default (`defaultPathStyle()`, `JFS_S3_VHOST_STYLE` unset) |
| Region | Garage `s3_region = "us-east-1"` | Garage rejects any other region with `AuthorizationHeaderMalformed` (`src/api/common/signature/payload.rs:415`). JuiceFS sends `AWS_REGION`, else `us-east-1`. Matching on the server removes a per-client env var that every mount node would otherwise need. Alternative: keep `garage` and set `AWS_REGION=garage` on every client |
| TLS | none on the S3 port. Tailnet transport only | Garage's S3 API has no TLS |
| `<ENDPOINT>` | **Operator decision D2** (reopened by the fleet-wide layout; see below) | The bucket URL is recorded in metadata and must resolve identically on **every** client (parent §0.2) |

- **Endpoint failover** is metadata-only: `juicefs config "$META" --bucket http://<other-node>:3900/juicefs`. It is a separate, gated drill (§3 Step e), not part of the node-down test.
- **D2 options (not decided):**
  - **(i) One tier-1 node's tailnet IPv4** (not its MagicDNS name, which does not resolve in the bridge) is recorded as the endpoint, with failover through `juicefs config --bucket`. Spark being down on 2026-09-27 shows that the chosen node can be the one that is down.
  - **(ii) A name that resolves on each client to that client's own local Garage.** The earlier objection to this, that per-client gateways "spread `rpc_secret` to every lab node", no longer applies: in the fleet-wide layout every storage node already holds `rpc_secret`. Whether one name can resolve per node, and resolve inside Docker bridge networks, is COULD-NOT-MEASURE.
- **MagicDNS does NOT resolve inside a Docker bridge network (measured, peer session, 2026-09-27).** Clients had to use `tailscale ip -4`. So every runbook container on `pmoves_data` (the `jfs()` helper, and the mount) must address Garage in one of two ways:
  - **(a) The endpoint's tailnet IPv4, resolved on the host.** This is the plan's default. Set `ENDPOINT="$(tailscale ip -4 <endpoint-node>)"` on the host before any `jfs` call. The container keeps `pmoves_data`, so `minio` and `supabase-db` still resolve.
  - **(b) Host networking.** Then the container loses the `pmoves_data` names (`minio`, `supabase-db`).
- Gate A records which of the two is used. With (a), the bucket URL stored in metadata (c3) is a tailnet IP. A node's tailnet IP is stable unless the node is re-registered, and a re-registration then needs a `juicefs config --bucket` change.
- D2 option (ii), a per-node name, now needs a name that resolves inside the bridge. MagicDNS cannot be that name.

### 1.5 Names

| Object | Name | Note |
|---|---|---|
| Bucket | `juicefs` | Same as MinIO, so the object keys (`pmoves-media/...`) copy 1:1 |
| Key | `juicefs-pmoves-media` | Allowed on bucket `juicefs` only: `--read --write`. No `--owner`, no `--create-bucket` |
| Admin | `admin_token_file` | Never given to JuiceFS |

### 1.6 Secrets funnel (labels only; values never in git, argv logs or transcripts)

| CHIT label | Delivered to | Docker secret | Shape (validate at delivery, not just presence) | Manifest check possible |
|---|---|---|---|---|
| `GARAGE_RPC_SECRET` | every storage node (§1.1) | `pmoves_garage_rpc_secret` | 64 hex | `min_length: 64` |
| `GARAGE_ADMIN_TOKEN` | every storage node + operator | `pmoves_garage_admin_token` | base64 of 32 bytes (44 chars) | `min_length: 44` |
| `GARAGE_METRICS_TOKEN` | every storage node + Prometheus | `pmoves_garage_metrics_token` | base64 of 32 bytes (44 chars) | `min_length: 44` |
| `JUICEFS_GARAGE_ACCESS_KEY` | the migration context (Knuckles, operator) | — | `GK` + 24 hex (26 chars) | `prefix: GK`, `min_length: 26` |
| `JUICEFS_GARAGE_SECRET_KEY` | the migration context, **and later the D1 metadata move** (§2). It must stay deliverable after this plan closes | — | 64 hex | `min_length: 64` |

- **Secret names** follow the manifest's existing docker-secret convention: a `pmoves_` prefix, as in `pmoves_juicefs_meta_password` (`pmoves/chit/secrets_manifest_v2.yaml:239`). The `garage.toml` paths in §1.3 use the same names.
- **What the manifest can enforce:** only `min_length` and `prefix`. Hex format, base64 format and exact length are **not enforced**. A value of 26 or more characters that starts with `GK` passes, even if it is not hex or is too long. At intake, the operator checks length and character class by hand, without printing the value (the E2B truncation precedent).
- **Why the secret key outlives this plan:** `juicefs dump` omits the storage secret key unless `--keep-secret-key` is passed. After `juicefs load` into the replicated cluster (D1, §2), the Garage secret has to be re-injected with `juicefs config --secret-key`. So `JUICEFS_GARAGE_SECRET_KEY` cannot be treated as migration-only.

**Delivery vehicle to the storage nodes: unconfirmed (G2, COULD-NOT-MEASURE).** No confirmed route exists today for delivering the `GARAGE_*` labels to the KVMs, and none is verified for the Windows nodes.
- `.github/workflows/sync-secrets-local.yml` runs on `[self-hosted, ai-lab, <target>]`, with default target `spark`. Target labels must match `[a-z0-9][a-z0-9-]*`.
- No KVM runner carrying the `ai-lab` label is known. kvm2 hosts a CI runner, but its labels were not verified.
- G2 must name the mechanism for **each** storage node before any `GARAGE_*` secret is delivered. That could be a runner label added to the workflow, or an operator-run delivery on the node over a non-logged channel. Until then, per-node delivery is COULD-NOT-MEASURE, not assumed.

**Bundle producer: never Spark alone.** Spark and b850 (Knuckles) are the secrets-bundle producers, and the workflow's default target is `spark`. Spark was **down** on 2026-09-27. If Garage secret delivery is routed through the bundle, **b850 is the named fallback producer**. A delivery path that works only when Spark is up fails G2.

**Mount nodes do NOT need the Garage key.** JuiceFS stores storage credentials in the volume's format record in the metadata DB, so anyone who can read `juicefs_meta` has this key. That is why it is bucket-scoped.

**Route (all 4, or delivery stops one hop short):**
1. The `pmoves/chit/secrets_manifest_v2.yaml` entry. **OPERATOR:** the manifest is zero-access to agents; `make -C pmoves chit-manifest-register` writes the five entries from `REGISTRY` (its `--check` lists them as pending today).
2. `REGISTRY` in `pmoves/tools/chit_manifest_register.py` (tier `data`, `required: False`, the `min_length`/`prefix` of the table above). **DONE in #3241.**
3. The bundle map in `.github/workflows/sync-secrets-local.yml`. **DONE in #3241.**
4. The GitHub secret itself. **OPERATOR.**

**Last hop: env file to the files Garage mounts.** The funnel projects these labels into `env.tier-data`, and its docker-secret output is one JSON map (`chit.write_docker_secrets`). No funnel step writes the per-file 0600 form the compose overlay mounts. `make -C pmoves garage-secrets` (`garage_render_config.py materialize`) is that step: it parses (never sources) `GARAGE_ENV_FILE` (default `env.tier-data`), checks the exact shape of each value (64 hex; at least 44 base64 characters), writes all three files 0600 in a 0700 dir or none of them, and prints only label names and lengths. `make -C pmoves garage-preflight` then checks owner and mode. It is an operator-context target: agents cannot read tier env files.

**Key-print hazards:**

| Command | Hazard | Handling |
|---|---|---|
| `garage key create` | **Prints the secret key to stdout** (`print_key_info`) | Operator context only. Redirect stdout to a `umask 077` intake file, feed that file to the funnel, then `shred -u` it. Never run it in an agent session |
| `garage key import -n juicefs-pmoves-media --yes <GK..> <secret>` | Secret on argv | Alternative when the funnel generates the key. Run it on a storage node, not over a logged channel. Syntax **measured** from v2.4.1 source (`src/garage/cli/structs.rs` `KeyImportOpt`): positional `key_id secret_key`, `-n` name (default "Imported key"), `--yes`. **Without `-n`, the later `bucket allow --key juicefs-pmoves-media` does not match the key** (§6.1 row 9). An admin API `ImportKey` call keeps the secret out of argv |
| `garage key info --show-secret` | Prints the secret | Do not use |
| `juicefs config --secret-key` | Does not read `SECRET_KEY` from env (v1.3.0 `cmd/config.go`), so the secret is on argv | Pass it in through the `jfs()` env file (§3) and expand it inside `sh -c`. It is then in the juicefs process argv for the seconds the call runs |
| `juicefs sync minio://AK:SK@...` | There are no `SRC_*`/`DST_*` env vars in JuiceFS. The `SRC_AK`-style names in §3 are plain shell variables, expanded by `sh -c` inside the container. **However,** a `minio://` URL **without userinfo** falls back to `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` from the environment (JuiceFS `pkg/object/minio.go:71-76`). That fallback is one set of variables, so it covers **one side** of a sync | The Garage side uses the env fallback: its URL has no userinfo, and the key comes from the `dst` env file. Only the MinIO credential stays in argv, URL-encoded (`/` as `%2F`). The Garage key outlives this plan (D1 re-injection), so it is the credential to keep out of argv |

**Real exposure window (do not understate it):**
- **Container environment.** Anything passed with `-e` or `--env-file` is stored in the container's recorded config, in its environment list. It is readable through `docker inspect` by anyone with Docker socket access, for the **whole lifetime of the container**. With `--rm`, that lifetime is the call: seconds for `status`, `config` and `fsck`, and **hours** for a sync pass.
- **Process argv.** Container processes are host processes. For the whole of every sync pass, the expanded **MinIO** URL (`minio://AK:SK@minio:9000/...`) sits in the juicefs argv, readable by host `ps` and `/proc/<pid>/cmdline`. The Garage key does not, because it reaches sync through the env fallback (N1); it stays only in the container's environment list. That is hours per pass. Any collector that records process command lines will capture them.
- **Mitigations:**
  - Run sync passes only on Knuckles, in the operator context.
  - Confirm that no cmdline-recording collector runs during the passes.
  - Pass each call only the credential sets it needs (the §3 `jfs()` helper takes the set names).
  - If command-line capture cannot be ruled out, rotate the Garage key after the soak: create a new key, switch with `juicefs config --access-key/--secret-key`, then delete the old key.
  - The MinIO credential used as the sync source gets the same treatment when the MinIO `juicefs` role is retired.
- **Shell history.** Never type a credential at a prompt that records history. Prefer the funnel-backed env-file fill in §3. If a value must be typed, first turn history off with `set +o history`, or set `HISTCONTROL=ignorespace` and begin the line with a space.

## 2. Metadata engine: **D1 DECIDED: replicated Postgres** (operator)

The data move (§3) and the metadata move are **orthogonal**:
- `juicefs dump | load` does not touch objects.
- `juicefs config --storage` does not touch the file tree.

**Availability is decided by where metadata lives:**

| Metadata at | Knuckles down | Tier 1 (KVMs) down | Matches §0.8? |
|---|---|---|---|
| Supabase PG on Knuckles (today, until the follow-on move) | **Everyone** loses `pmoves-media`, including KVM Jellyfin | Depends on where the replicas sit (§1.2) | **No.** This is the inverse of the accepted asymmetry |
| **Replicated PG on tier 1 (DECIDED)** | KVM Jellyfin keeps working, **if** the Garage partitions it reads keep quorum without Knuckles (§1.2) | Lab loses it (accepted) | **Yes** |

**What D1 fixes, and what it leaves to the follow-on plan:**

1. **Sequencing.** The data move (this runbook) comes first; the metadata move comes second. That means two freezes, each with its own rollback. **Never combine them.** Each change must be separately reversible, and neither rollback may depend on the other change having succeeded.
2. **Scope.** The metadata move is a **separate follow-on plan**. It is not written here. This section records only the constraints that plan inherits.
3. **Freeze.** `juicefs dump` is not snapshot-consistent. The dump/load freeze stops **all** mounts and gateways on `pmoves-media` (the same c1 discipline as §3, including the stale-session rule).
4. **Secret key.** `juicefs dump` omits the storage secret key unless `--keep-secret-key` is passed. Do not pass it, because that writes the Garage secret into the dump file.
   - After `juicefs load` into the replicated cluster, re-inject the key with `juicefs config --secret-key`, through the §3 env-file route.
   - So `JUICEFS_GARAGE_SECRET_KEY` must **stay deliverable** after this plan closes (§1.6).
5. **One writable endpoint.**
   - A pgx multi-host DSN with `target_session_attrs=read-write` passes through JuiceFS's `newSQLMeta` (JuiceFS `pkg/meta/sql.go:405-451`, per the #3200 review).
   - **Failover behaviour is COULD-NOT-MEASURE.** JuiceFS defaults `max_life_time=0`, so pooled connections are never recycled and can stay pinned to a demoted primary.
   - **Sandbox test before adoption:**
     - Set `max_life_time` in the meta URL.
     - Kill the primary while a mount is writing.
     - Observe whether writes resume on the new primary, and how long that takes.
   - Run it in a sandbox (`make -C pmoves sandbox-preflight`, then `sandbox-create`), never against the live metadata. If the sandbox is unavailable, the result is COULD-NOT-MEASURE; it is not a pass.
   - The fallback, if the DSN route fails, is a single endpoint in front of the cluster (HAProxy or a VIP) that follows the leader.
6. **HA manager: Patroni, preferred over repmgr with manual promote.** `pmoves/docs/operations/rto-rpo-targets.md:86` says: "Never run two writable primaries. If read-replicas/HA are added, use a fencing token / single-writer election (e.g., Patroni) — never accept two primaries." A manual promote has no fencing, so it cannot meet that rule.
   - Patroni's DCS quorum (for example etcd) must tolerate one tier-1 node being down. Spark was down on 2026-09-27, so this is a real case, not a hypothetical. The follow-on plan sizes this.
7. **RAM.** PG takes ~1-2 GB per node. Measured available RAM: kvm2 5G, kvm4-1 11G, kvm4-2 12G (§1.1). kvm4-2 is over-subscribed per its profile. Garage also runs on the same nodes.
8. **PR #2728 (MERGED 2026-08-25).** It publishes `supabase-db` tailnet-bound, so remote nodes can mount while metadata is on Knuckles.
   - Under D1, #2728 is the **interim** path. It stays in use until the metadata move lands.
   - After the move, JuiceFS no longer needs a tailnet-exposed `supabase-db`. The follow-on plan must **retire that exposure**, unless another consumer depends on it. Which other consumers use it is COULD-NOT-MEASURE here.
   - The old advice not to merge #2728 on momentum is moot, because it merged.

**The evaluation record (why B):**

| Criterion | A. Keep Supabase PG (Knuckles) | **B. Replicated PG on tier 1: DECIDED** | C. TiKV / etcd |
|---|---|---|---|
| Engine migration | none | none (still Postgres) | yes, new engine |
| Metadata move | none | `juicefs dump --binary` → `juicefs load`, all mounts frozen | same |
| HA | none (single `supabase-db`) | Primary + streaming standby under Patroni (fencing) | native |
| One writable endpoint | n/a | Multi-host DSN passes through. Failover is COULD-NOT-MEASURE (item 5) | native |
| Coupling | Shares `supabase-db` with the app | Dedicated | Dedicated |
| Remote mounts | `supabase-db` tailnet exposure (#2728, merged) | Tier-1 tailnet endpoint | Tier-1 endpoint |

## 3. Migration runbook

**Conventions:**
- Run from Knuckles, in the operator context.
- A failed gate means STOP.
- Exit-code doctrine: 0 clean / 1 findings / 3 could-not-measure. Call the tools directly, because `make` collapses exit codes.

**Credentials: one env file per credential set, and each call gets only the sets it needs** (review P2-2; the exposure window is in §1.6).

| Set | File contents (variable names) | Funnel source | Used by |
|---|---|---|---|
| `meta` | `META_PASSWORD` | `JUICEFS_META_PASSWORD` | status, gc, fsck, config |
| `dst` | `DST_AK`, `DST_SK`, **and the same two values again as `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`** | `JUICEFS_GARAGE_ACCESS_KEY`, `JUICEFS_GARAGE_SECRET_KEY` | objbench and config (cutover) through `DST_*`. Sync through the `MINIO_*` env fallback: the Garage URL carries **no userinfo** (review N1) |
| `src` | `SRC_AK`, `SRC_SK`, raw values | The MinIO credential the volume was formatted with. The manifest carries both `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` and `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`; which pair this volume uses is recorded at Step 0 (COULD-NOT-MEASURE here) | config (rollback) |
| `srcurl` | `SRC_AK`, `SRC_SK`, **URL-encoded** (`/` as `%2F`) | same | sync (the URL form) |

```bash
JFS_IMG=juicedata/mount:ce-v1.3.0
META='postgres://juicefs_meta@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable'   # no password in it
JFS_ENV=/dev/shm/jfs-migration                                                  # tmpfs, removed at the end
# jfs <sets> '<command>'   <sets> is a comma list, e.g.  meta | dst | srcurl,dst | meta,dst | meta,src
jfs() { local f a=(); for f in ${1//,/ }; do a+=(--env-file "$JFS_ENV/$f"); done; shift
        docker run --rm --network pmoves_data -e META="$META" "${a[@]}" "$JFS_IMG" sh -c "$*"; }
```

**Filling the files.**
- Turn history off first: `set +o history`. Or set `HISTCONTROL=ignorespace` and begin each line with a space.
- Write each file inside a `( umask 077; ... )` subshell, straight from the funnel. The canonical loader resolves a label with `bash pmoves/scripts/with-env.sh printenv <LABEL>`, inside a command substitution that feeds a `printf` redirected into the file. `printf` is a shell builtin, so the value never appears in a process argv.
- Never `echo` a value, and never type one at a history-recording prompt.
- At the end of the session, `shred -u` every file in `$JFS_ENV` and remove the directory.

### Step 0: Baseline (read-only)

```bash
jfs meta 'juicefs status "$META"'      # record UUID, Storage=minio, Bucket, BlockSize, Sessions (host, mount point)
jfs meta 'juicefs gc "$META"'          # NO --delete: reports leaked/pending objects only
# live mount shape on EACH mounting node (never print the container's environment list):
docker inspect juicefs-mount --format '{{.HostConfig.NetworkMode}} {{json .Config.Entrypoint}} {{json .Config.Cmd}}'
# object inventory via mc inside the minio container (mc ships in the #3192 image; alias as `make backup` uses):
docker exec pmoves-minio-1 mc ls <alias>/juicefs/
docker exec pmoves-minio-1 mc du --recursive <alias>/juicefs/pmoves-media/
```

**Gate 0:**
- Only the `pmoves-media/` prefix exists.
- Object count and bytes are recorded, and the 85 vs 76 GB gap is explained.
- `sha256sum` of 3 sample files is recorded.
- A metadata backup exists: `juicefs dump --binary` to NVMe1, plus a `pg_dump -n juicefs_meta` via its Known Road.
- **Live mount shape recorded, per mounting node:** the network (`pmoves_data` expected), the meta role in the recorded command line (`juicefs_meta@` expected), the cache dir, and **which make target created the mount**. c5 must reproduce exactly this shape.
- The MinIO credential pair the volume uses is identified by label, for the `src`/`srcurl` files.

#### Step 0 record (measured 2026-10-01, B850-CLAUDE on Knuckles, read-only)

Nothing was written, deleted or reconfigured. Credentials were never printed: MinIO listings used an
in-container `MC_HOST_*` alias expanded inside `sh -c`, `juicefs status` ran in the existing
`juicefs-mount` container with its own `META_PASSWORD`, and the credential pair was identified by
comparing 12-char sha256 prefixes, not values.

| Item | Measured | How |
|---|---|---|
| Volume | `pmoves-media`, UUID `72fbf356-3a13-4c50-889c-e0bd703e2459`, `Storage: minio`, `Bucket: http://minio:9000/juicefs`, BlockSize 4096 KiB, Compression none, TrashDays 1 | `juicefs status` |
| **Encryption** | **`EncryptAlgo: aes256gcm-rsa`.** Objects are client-side encrypted; the RSA key lives in the format record. Not in the plan's inputs | `juicefs status` |
| JuiceFS used | 80,926,846,976 B (75.37 GiB), 57 inodes (20 regular files; 13 content files under `knuckles/downloads/`) | `juicefs status`, `find` on the mount |
| Sessions | 2: the S3 gateway (`pmoves-juicefs-gateway-1`) and `juicefs-mount` at `~/pmoves-fs` (the operator's home on Knuckles) | `juicefs status` |
| MinIO image | `pmoves/minio:RELEASE.2025-09-07T16-13-09Z-src`, healthy, on `pmoves_bus`, `pmoves_data`, `pmoves_external` | `docker inspect` |
| MinIO volume | `pmoves_minio-data`, 79.4 GiB total: `juicefs/` 75.7 GiB, `assets/` 3.7 GiB, `outputs/` and `pmoves-comfyui/` 4 KiB each, `.minio.sys` 11.8 MiB | `du` on a read-only mount of the volume |
| Bucket `juicefs` | **19,328 objects, 80,926,852,230 B.** Only prefix `pmoves-media/`. `chunks/`: 19,304 objects, 80,926,635,709 B. `meta/`: 24 objects, 216,521 B (hourly auto-backups). No other keys | `mc du --json`, `mc ls --recursive` |
| Garage | **None.** No container, no volume | `docker ps -a`, `docker volume ls` |
| Credential pair | The volume's access key equals `MINIO_ROOT_USER`, which equals `MINIO_ACCESS_KEY` (same value). So the `src` set is the **MinIO root** credential, not a bucket-scoped one | sha256-prefix comparison |
| Live mount shape | network `pmoves_data`; meta `postgres://juicefs_meta@supabase-db…` (password via env); cache `/data/jfsCache` on `/mnt/pmoves-nvme1/juicefs-data`; `--cache-size 102400 --free-space-ratio 0.100`; restart `unless-stopped`; created 2026-09-22. No compose label, so it was a `docker run`; **which make target created it is COULD-NOT-MEASURE** (the B850 bring-back runbook's command emits helper-sized cache flags, not these) | `docker inspect` (env list not printed) |
| Knuckles disk | root 147 GiB free of 916 GiB (84% used); NVMe1 `/mnt/pmoves-nvme1` 3.5 TiB free of 3.6 TiB | `df -hT` |
| Tailnet | kvm2, kvm4-1, kvm4-2 active (direct); **Spark offline** | `tailscale status` |

**The 85 vs 76 GB gap is explained: there is no gap.** "~85 GB" is the MinIO volume's 79.4 GiB
read as decimal GB (≈85.3 GB). Of that, 3.7 GiB is the `assets` bucket. The `juicefs` bucket's
chunk bytes (80,926,635,709) match JuiceFS `UsedSpace` (80,926,846,976) to within 0.0003%.
The copy is therefore **80.93 GB**, not 85.

**Gate 0 checksums** (recorded for c6 and for Gate B spot-checks):

| Sample | sha256 |
|---|---|
| file, inode 8207 (49,599,344 B) | `2adb728e697c83ec35ce6ef6a05a9fea91ff8d73819c9c84a5606e883c115e68` |
| file, inode 8204 (56,612,762 B) | `26d76e03a9baaf2bcd2a455ef7bb84a79a4a46881e894a3b99e4ba415bd77482` |
| file, inode 8201 (70,409,759 B) | `0393e1c618d449a42091f1158a41a6d687f749c26b34ebd636eab925116bd5f9` |
| object `pmoves-media/chunks/0/16/16385_0_303` | `86ed552ac1a4121c2737415e4794302c40077bf748a19585b034fe4f8e7effcf` |
| object `pmoves-media/chunks/0/25/25182_3_4194304` | `ae05835af515c6e36184f38affe8af009d9e6a9e3425485b3307ce9b623bbbce` |
| object `pmoves-media/chunks/0/25/25788_9_4194304` | `291c01948e0621a246d0d2b0a90bddc32ea7adc97e9ef240ac6fb6aee5cdc2a7` |

Object checksums are of ciphertext (the volume is encrypted), so they compare bytes 1:1 across stores.
File samples are named by JuiceFS inode, not by path: the paths are the operator's personal media, and this is a public repo. JuiceFS inodes survive the object-store switch (c3 changes only the format record), so c6 resolves them on the mount with `find ~/pmoves-fs -inum <n>`.

**Gate 0 items still open:** the metadata backup (`juicefs dump --binary` to NVMe1 plus
`pg_dump -n juicefs_meta`) was not taken by this read-only pass; `juicefs gc` (no `--delete`)
was not run.

**Step (a) is blocked, as of 2026-10-01, on:**
1. **Compose grant.** No Garage compose definition exists. It needs `compose:pr:<N>` for this
   lane's PR. The grant active on Knuckles at measurement time named a different, already-merged PR
   and was not used.
2. **G2: the `GARAGE_*` / `JUICEFS_GARAGE_*` funnel labels.** `REGISTRY` and the bundle map now
   carry them (#3241). The manifest entries (`make -C pmoves chit-manifest-register`), the values
   and the GitHub secrets are operator actions, and the per-node delivery vehicle is still G2.
3. **D2, D3 (and D7) open.** With Spark offline and kvm4-1 still a G0 blocker, a 3-zone first cut
   is at most kvm2 + kvm4-2 + one tier-2 node. Knuckles' NVMe1 (3.5 TiB free) is the obvious
   tier-2 candidate, but declaring it is D3.
4. **`garage key create` is operator-context only** (§1.6). An agent session cannot complete
   Step (a) by itself.
5. **External port probe** (§1.3) is OPEN — OPERATOR, and is part of Gate A.
6. **#3150 still OPEN** (G0).
7. **No published image yet.** The fork now has tags, the Hardened branch and protection, and its CI workflow is open as `POWERFULMOVES/PMOVES-garage#1` (§6.2, §7). The digest exists only after that PR merges and the workflow runs on Hardened.

### Step (a): Stand up Garage, bucket, key

```bash
# each first-cut storage node (deploy under a Known Road grant, §5): secrets from the funnel
# first start with no peers: make -C pmoves garage-render GARAGE_TIER=<1|2>; make -C pmoves up-garage
garage node id                                     # collect one `<id>@<tailnet ip>:3901` per node (public keys, not secrets)
# write all ids to a peers file, re-render every node with GARAGE_PEERS=<file>, restart (bootstrap_peers, §6.1 row 12)
# one assign per node: zone per §1.2 (own zone by default; `lab` only if zone grouping is chosen),
# capacity = that node's D3 declaration (§1.1), tag = node name. Tier 1 declares as much as its headroom allows.
garage layout assign <id-kvm2>   -z kvm2   -c <declared>G -t kvm2
garage layout assign <id-kvm4-1> -z kvm4-1 -c <declared>G -t kvm4-1
garage layout assign <id-kvm4-2> -z kvm4-2 -c <declared>G -t kvm4-2
garage layout assign <id-node>   -z <zone> -c <declared>G -t <node>   # Spark, and each tier-2 node, when ready
garage layout show                                 # read BEFORE applying: "Usable capacity" / "Effective capacity" >= ~85 GB + growth,
                                                   # "Zone redundancy: maximum", "Partitions are replicated 3 times on at least 3 distinct zones"
# NEVER run `garage layout config -r` (zone redundancy): lowering it voids the one-replica-per-zone reasoning in §1.2
garage layout apply --version 1
garage bucket create juicefs
(umask 077; garage key create juicefs-pmoves-media > "$INTAKE")   # hazard, §1.6
# scoped, expiring admin tokens (§6.1 row 7); each PRINTS a token, so operator context and intake file only:
(umask 077; garage admin-token create --expires-in 30d --scope GetClusterStatus,GetBucketInfo,GetKeyInfo,ListBuckets,ListKeys migration > "$INTAKE_ADMIN")
(umask 077; garage admin-token create --scope Metrics prometheus > "$INTAKE_METRICS")
garage bucket allow --read --write juicefs --key juicefs-pmoves-media
```

**Gate A:**
- `garage status` shows every first-cut node HEALTHY in its declared zone, with the layout at version 1. The first cut needs at least 3 zones for RF=3.
- The applied layout's "Effective capacity (replication factor 3)" covers ~85 GB plus growth.
- `garage layout show` prints **"Zone redundancy: maximum"** and **"Partitions are replicated 3 times on at least 3 distinct zones"** (review N2).
- **Config parity (§6.1 row 3):** `replication_factor` and `consistency_mode` are identical in every node's rendered `garage.toml` (diff the rendered files; both come from one template, so a difference means a stale render).
- `garage bucket info juicefs` lists the key with RW.
- **Addressing choice recorded:** (a) the tailnet IPv4 resolved on the host, or (b) host networking (§1.4; MagicDNS does not resolve inside the bridge, measured). `<ENDPOINT>` below is the tailnet IPv4 under (a).
- **kvm4-1 inbound reachability (BLOCKER):** before kvm4-1 joins the layout, a connection from kvm4-2 and from Knuckles to kvm4-1:3901 over the tailnet must succeed. On 2026-09-27 a test port timed out, cause COULD-NOT-MEASURE. If it still fails, kvm4-1 stays out of the first cut.
- Functional test from Knuckles **inside `pmoves_data`**, addressing Garage by tailnet IP:
  ```bash
  jfs dst 'juicefs objbench --storage s3 --access-key "$DST_AK" --secret-key "$DST_SK" http://<ENDPOINT>:3900/juicefs'
  ```
  Every functional test must pass, **including list** (the #3199 failure mode).
- **Sync URL parse proven before pass 1.** A dry run with the exact Step (b) URLs lists both sides and copies nothing:
  ```bash
  jfs srcurl,dst 'juicefs sync --dry --no-https "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" "minio://<ENDPOINT>:3900/juicefs/pmoves-media/"'
  ```
  This is the exact Step (b) form: MinIO userinfo in the URL, and no userinfo on the Garage URL, whose key comes from `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` in the `dst` env file. It must exit 0 and report the MinIO keys as pending copies. An auth error on the Garage side means the env fallback did not engage. STOP. A `NoSuchBucket` error naming the host means the URL was parsed virtual-host style (P1-2 of the #3200 review). STOP.
- **External port probe (§1.3, required):** 3900, 3901 and 3903 are refused or time out on every storage node's public address (every KVM; each tier-2 node's router address), probed from a host outside the tailnet. All three ports on every node; one open port fails Gate A.

### Step (b): Copy MinIO → Garage (volume stays live on MinIO)

```bash
# pass 1: live, throttled. Incremental on re-run, NOT resumable (see below)
jfs srcurl,dst 'juicefs sync --no-https --threads 8 --bwlimit <Mbps> \
     "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" \
     "minio://<ENDPOINT>:3900/juicefs/pmoves-media/"'
# pass 2 (still before the freeze): re-read and checksum every object on both sides
jfs srcurl,dst 'juicefs sync --no-https --check-all --threads 8 "minio://...same src..." "minio://...same dst..."'
```

- **No checkpoint flag.** `--enable-checkpoint` does not exist in the pinned `juicedata/mount:ce-v1.3.0`; it first appears in v1.4.x (v1.4.1 `cmd/sync.go:241`). An interrupted pass 1 is simply re-run. Sync skips keys that already exist on the destination with a matching size, so a re-run re-lists both sides and copies only what is missing or differs. It does not resume mid-object and it re-pays the listing cost. The image is not bumped to v1.4.x for this one flag: every other step, and the live mount, run on ce-v1.3.0.
- **Scheme for the Garage side is `minio://`, never `s3://`.** For `s3://` URLs, JuiceFS sync's `isS3PathType` treats only localhost, IPv4 literals and AWS hosts as path-style. For any other host, such as a MagicDNS name like `pmoves-kvm4-1`, it takes the bucket from the hostname, and every request goes to the wrong bucket. `minio://` is always path-style.
- **`--no-https` on every sync.** Both endpoints are plain HTTP: MinIO on `pmoves_data`, and Garage's S3 port, which has no TLS (§1.4). The flag applies to both sides of the call. Whether sync would fall back to HTTP by itself for an `s3://` endpoint (`supportHTTPS`) is **COULD-NOT-MEASURE**; the plan does not depend on it.
- The `juicefs config --bucket http://<ENDPOINT>:3900/juicefs` form in c3 and §1.4 is a different parser (the object-store URL of a formatted volume, path-style for non-AWS endpoints). It is correct as written.

**Gate B:**
- Pass 2 (`--check-all`) reports **0 failed**. This full verification runs here, before the freeze, never inside it.
- Object count and bytes in `garage bucket info juicefs` are ≥ the Step 0 figures.
- `garage stats` shows no resync backlog. Read it before declaring one: on the defaults the resync queue can grow faster than it clears (`reference-manual/known-issues/` "Resync tranquility is conservative by default", §6.1 row 23). The operator-tunable levers, per node, are `garage worker set -a resync-worker-count <N>` and `garage worker set -a resync-tranquility 0`; record any value set and restore the defaults after Gate B.
- `--delete-src` and `--delete-dst` are never used.

### Step (c): Cutover with a short write freeze

| # | Action | Gate |
|---|---|---|
| c1 | Stop every writer: `juicefs-mount` on each mounting node, plus any gateway on `pmoves-media` | `jfs meta 'juicefs status "$META"'` shows no active Sessions. **A crashed client's session lingers** until it expires. Confirm that the listed host and process are really gone, and wait for expiry, or clean up stale sessions only through a JuiceFS-supported path. **Never force through** with a session listed |
| c2 | Final delta only: `jfs srcurl,dst 'juicefs sync --no-https --check-new --threads 8 "minio://...same src..." "minio://...same dst..."'`. `--check-new` checksums only the objects it copies now; everything else was verified by Gate B's `--check-all`. **Never `--check-all` inside the freeze**: it re-reads every object on both sides | 0 failed |
| c3 | Switch (`juicefs config` put/get/deletes a `testing/` object; do **not** pass `--force`): `jfs meta,dst 'juicefs config "$META" --storage s3 --bucket http://<ENDPOINT>:3900/juicefs --access-key "$DST_AK" --secret-key "$DST_SK" --yes'` | exit 0 |
| c4 | `jfs meta 'juicefs status "$META"'`, then `jfs meta 'juicefs fsck "$META"'` | `Storage: s3`, the Garage bucket URL, fsck exit 0 and 0 missing blocks |
| c5 | Remount **each** mounting node through the **same make target and env shape that created its live mount** (Step 0 record). With #3150, the `pmoves_data` / `juicefs_meta` shape is the one its durable-mount path creates; use the target #3150 names for it. On main, neither road reproduces that shape: `juicefs-mount-local` uses `--network host` with `supabase_admin` and ignores `JUICEFS_DATA_DIR` (`pmoves/mk/egress.mk:376-402`), and `juicefs-cross-node-setup.sh` also uses `--network host` (lines 78 and 115) (review N4). The data-dir override lands only with #3150, which is OPEN, so #3150 is a G0 precondition. Then `make -C pmoves juicefs-mount-status` | Mount up; content dirs listed. `jfs meta 'juicefs status "$META"'` sessions show the **expected host and mount point** for every node. The mount container's recorded command line shows the expected role (`juicefs_meta@`) and network (`pmoves_data`), matching Step 0 |
| c6 | Verify data | The 3 sample `sha256sum`s match Step 0. A write, `sync`, read-back works. `juicefs gc` (no `--delete`) reports **non-zero** scanned objects; zero is the #3199 false-clean signature |

**Freeze length** = the c2 delta (a full listing of both sides, plus a copy of whatever was written since Gate B) + c3-c5. The listing cost scales with object count, which Step 0 records. So the freeze is **COULD-NOT-MEASURE** until Step 0 runs. Pass 1 and the `--check-all` pass stay **outside** the freeze. Run Gate B as close to the window as practical, so the delta is small.

### Step (d): Rollback (MinIO's `juicefs` bucket receives no writes after c1, except this carry-back)

```bash
# freeze as in c1, then carry back anything written since cutover (no deletes):
jfs srcurl,dst 'juicefs sync --no-https --check-new "minio://<ENDPOINT>:3900/juicefs/pmoves-media/" "minio://...minio...@minio:9000/juicefs/pmoves-media/"'
jfs meta,src 'juicefs config "$META" --storage minio --bucket http://minio:9000/juicefs --access-key "$SRC_AK" --secret-key "$SRC_SK" --yes'
jfs meta 'juicefs fsck "$META"'
jfs meta 'juicefs gc "$META"'     # NO --delete; now scans MinIO
```

**Gate D:**
- `Storage: minio`, and fsck is clean.
- `juicefs gc` with no delete flag, now running against MinIO, reports a **non-zero** count of scanned objects. Zero is the #3199 false-clean signature.
- After a remount (the same c5 target and shape), the write/read test passes.

**The invariant, stated exactly.** MinIO's `juicefs` bucket takes live writes until c1, and pass 1 and pass 2 run while it is still live. From c1 on, nothing writes to it except this rollback's carry-back, which never deletes. "Unmodified after Step 0" was false.

**Precondition for the whole soak:** MinIO stays running and the `-src` image stays present, because the #3192 `up-minio` pre-check refuses to start without it.

### Step (e): Soak, then retire MinIO's `juicefs` role

| Phase | Action | Gate |
|---|---|---|
| Soak, N days (**D4**) | Daily `juicefs fsck` (read-only), `garage status`, `garage stats`, `garage layout history` (§6.1 row 11: with disconnected nodes, old layout versions can stay active; run it after every layout change too) | 0 fsck errors. Every storage node in the layout HEALTHY, or its absence explained. Spark down counts as an absence |
| Node-down test (once, deliberate) | Stop **one** storage node that is **NOT the S3 endpoint** (D2). First confirm with `garage status` that every other storage node is up; with Spark already down, a second stop is a two-node failure, which is a different test. Run it once on a tier-1 node and once on a tier-2 node | Reads **and writes** continue from every client (RF=3: one replica per partition lost) |
| Endpoint-failover drill (separate, gated: G6a) | In an agreed window, and with a c1-style freeze: `jfs meta 'juicefs config "$META" --bucket http://<other-node>:3900/juicefs'`, remount through the c5 target, run c6, then switch back the same way | Every step exits 0. c6 passes on both the failover endpoint and the restored one. Never combined with the node-down test |
| Retire | JuiceFS no longer uses `minio:9000/juicefs`. MinIO itself stays up for `assets`/`outputs`/`pmoves-comfyui` until the parent §9 consumer migration | Operator sign-off |
| What "retire" means | Bucket `juicefs` data is **kept** and volume `pmoves_minio-data` is **kept** | — |
| Delete | Only on a separate, explicit operator instruction naming `pmoves_minio-data`. Never `down -v` | — |

### Time and bandwidth for ~85 GB

**Measured 2026-09-26 (read-only `tailscale ping`, Knuckles → KVM, direct IPv6 path, not DERP):**

| Target | Steady RTT | First contact |
|---|---|---|
| kvm2 | 35-48 ms | 58 ms |
| kvm4-1 | 51-112 ms | 457 ms |
| kvm4-2 | 139-249 ms | 915 ms |

- **KVM↔KVM RTT: measured.** `tailscale ping` between every pair is direct, at 1-5 ms (KVM shell survey, root, read-only, 2026-09-27).
- **Throughput: MEASURED** (operator-approved containerised iperf3, single stream, 2026-09-27):

| Path | Throughput |
|---|---|
| kvm4-1 → kvm2 | 383 Mbit/s |
| kvm2 → kvm4-2 | 345 Mbit/s |
| Knuckles → kvm2 | **19 Mbit/s** |
| Knuckles → kvm4-2 | **18 Mbit/s** |

- **The binding constraint is Knuckles' uplink,** at ~18 Mbit/s, because the source MinIO is on Knuckles. KVM↔KVM replication runs at roughly 20× that rate.
- **Not measured:**
  - The reverse direction (KVM → Knuckles), which `--check-all` reads use. Its time below assumes it is similar.
  - The kvm4-1 inbound path. It is blocked; see §1.1.
  - Tier-2 residential links.
- The earlier "without iperf3" fallback piped data over SSH. It is removed, because §1.1 records that SSH from Knuckles is refused.

**Estimate:** 85 GB = 680,000 Mbit. It crosses Knuckles' uplink **once**, into the endpoint node. Garage then replicates between the storage nodes in the layout.

| Link | Pass 1 (Knuckles uplink → endpoint) | Each `--check-all` pass (storage nodes → Knuckles) |
|---|---|---|
| **~18 Mbit/s (measured Knuckles uplink)** | **~10.5 h** | **~10.5 h** (reverse direction assumed similar; not measured) |
| 100 Mbit/s (hypothetical only) | ~1.9 h | ~1.9 h |

- **`--check-all` is not free.** It re-reads every object on both sides. The MinIO side is local. The Garage side is ~85 GB read back to Knuckles per pass. That is egress from the endpoint **and from other storage nodes**, because reads can pull blocks from any replica holder.
- **Budget two `--check-all` passes:** Gate B's pass 2, plus one re-run if pass 2 is interrupted or reports failures. That is ~85 GB of extra egress each, about **10.5 h** each at the measured ~18 Mbit/s. The c2 delta (`--check-new`) re-reads only what it copies.
- **Traffic, total:** ~85 GB inbound to the endpoint node, ~170 GB of replication between storage nodes, and ~85-170 GB of check-all egress from the storage nodes. The KVM share is small against the 8-16 TB monthly caps. Replication to tier-2 nodes lands on residential **downlinks**, which have no measured throughput.
- **Wall clock before the freeze** ≈ pass 1 + one or two check-all passes. At the measured ~18 Mbit/s that is **~21-31.5 h**. None of it is inside the freeze. Pass 1 saturates Knuckles' residential uplink for ~10.5 h unless `--bwlimit` is set below the line rate, which makes it longer still.

## 4. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Metadata stays on Knuckles until the D1 follow-on lands | Knuckles down means KVM Jellyfin down too. This is the inverse of §0.8 | D1 is decided (§2). Run the follow-on plan after this one. Do not call KVM viewing highly available until it lands |
| A tier-1 node is down (Spark, 2026-09-27) | "Always-on" is a class, not a guarantee. A down tier-1 node plus one more failure stops the partitions they share (§1.2) | Soak and node-down tests start from `garage status`. Spark is never a sole secrets producer (§1.6) |
| Tier-2 replicas carry quorum | Under one zone per node, desktops that sleep or reboot hold quorum-bearing replicas. That is worst today, while tier 1 can declare only ~61G | Capacity weighting (applied). Zone grouping (OPEN, D7). KVM build-cache reclaim through the build-cache road (G0; owned outside this plan) |
| Asymmetric availability (accepted, §0.8) | Region or VPS down: the lab loses `pmoves-media` entirely. It fails; it does not degrade (§0.6) | Accepted. The cache helps bandwidth, not availability |
| KVM disk | Free now: kvm2 78G, kvm4-1 15G, kvm4-2 31G (survey, 2026-09-27). ~286G is BuildKit state (`buildx_buildkit_pmoves-shared0_state`) on the kvm4s. Snapshots need up to 4× metadata size | Declare capacity from **free now** (D3). Reclaim through the build-cache road (a GC cap, or `buildx prune`), never by deleting volumes (§1.1 HARD caution, G0) |
| kvm4-2 over-subscribed | OOM kills Garage | Resolve per its profile before G3 |
| Egress / uplink | Pass 1 saturates Knuckles' uplink. Each `--check-all` pass costs ~85 GB of endpoint-KVM egress | `--bwlimit`, off-hours. An interrupted pass is re-run (incremental by size, not resumable). `--check-all` only outside the freeze |
| Single S3 endpoint (D2) | Endpoint node down: the S3 API is down even though Garage has quorum | Metadata-only `juicefs config --bucket` failover, rehearsed as its own gated drill (G6a). D2 option (ii) is also available |
| MagicDNS inside Docker bridge networks | **Measured: it does not resolve.** A name-based `<ENDPOINT>` fails inside `pmoves_data`, the same lists-then-fails shape as §0.2 | Use the tailnet IPv4 resolved on the host, or host networking (§1.4). The choice is recorded in Gate A |
| kvm4-1 inbound tailnet | No inbound tailnet connection accepted (measured); cause COULD-NOT-MEASURE. Garage RPC 3901 would be unreachable | G0 / Gate A BLOCKER: kvm4-1 stays out of the layout until inbound 3901 works |
| Credential funnel | Truncated or mis-shaped key (the E2B precedent). A secret printed into a transcript | Shape checks (§1.6). `key create` output goes to the intake file only. Complete the 4-place route |
| Keys stored in metadata | Anyone with `juicefs_meta` read access has the Garage key | Bucket-scoped key, no owner rights. Rotate with `juicefs config --access-key/--secret-key` |
| `.env`-based guards | Node shape lives in gitignored `pmoves/.env.local`: `JUICEFS_NAME=pmoves-media`, `JUICEFS_NETWORK=pmoves_data` (there only so the mount resolves `minio`), `META_ROLE`, `DATA_DIR`. An empty exported shell var shadows the env files | Re-decide `JUICEFS_NETWORK` after cutover: metadata needs `supabase-db`, Garage needs its tailnet IP (MagicDNS does not resolve in the bridge). Verify with `env -u` |
| Cross-node preflight gap | `juicefs-cross-node-setup.sh` refuses only `Storage: file` and never checks that the bucket URL resolves | Follow-up (parent §0.7): a bucket-URL reachability check |
| Garage version drift | Mixed versions in the cluster | Digest pin. Upgrade per Garage `operations/upgrading.md` |

## 5. Rollout gates and Known Road grants

| Gate | Condition | Owner |
|---|---|---|
| **D1** | **DECIDED: replicated Postgres** (§2). Sequencing: this data move first, then the metadata move under its own follow-on plan | operator (done) |
| G0 | This plan merged. The #3192 bridge live, so MinIO is readable. **#3150 merged** (the durable mount and data-dir override that c5 relies on; OPEN today). Step 0 baseline recorded, including the live mount shape. **KVM build cache reclaimed through the build-cache road before declaring capacity:** the space is `buildx_buildkit_pmoves-shared0_state`, reclaimed with a GC cap or `buildx prune` by its owner, outside this plan. Never by volume deletion. **kvm4-1 BLOCKER:** inbound tailnet connections to kvm4-1 must work (3901 reachable from every peer), or kvm4-1 stays out of the first cut | operator |
| G1 | D3: each first-cut storage node has measured free space and a declared capacity of at most half of it, recorded in its profile. `df -i` on each `data_dir` filesystem is recorded too: ext4 is an accepted deviation from the vendor's XFS recommendation (§6.1 row 14), and inodes are its limit. The applied layout's effective capacity covers ~85 GB plus growth, and `garage layout show` prints "Zone redundancy: maximum" and "Partitions are replicated 3 times on at least 3 distinct zones" | operator |
| G2 | D2, D4-D7 decided. Funnel labels (§1.6) delivered to every first-cut storage node and shape-checked, with a named delivery vehicle per node (COULD-NOT-MEASURE today). The route does not depend on Spark alone; b850 is the fallback producer | operator |
| G3 | Garage up. Gate A passed, including list, the recorded addressing choice (tailnet IP or host networking), the kvm4-1 inbound check, the `--dry` sync parse check, and the **external probe of 3900/3901/3903** on every storage node's public address (who probes is OPEN — OPERATOR) | delivery + operator |
| G4 | Gate B passed: `--check-all`, 0 failed | delivery |
| G5 | Cutover window agreed. Step (c) gates passed | operator |
| G6 | N-day soak passed, including the node-down test on a non-endpoint node. MinIO's `juicefs` role retired | operator |
| G6a | Endpoint-failover drill (Step e) passed, as a separate gated step | operator |

**Known Road grants needed later.** Check each path first with `python3 .claude/skills/known-roads/roads.py check <path>`.

| Change | Road |
|---|---|
| New Garage compose file for the storage nodes (Linux host-network variant and Windows sidecar variant); any `pmoves/docker-compose*.yml` or overlay edit | `compose:pr:<N>` |
| Funnel manifests and `.github/workflows/sync-secrets-local.yml` | funnel road, per path check |
| `pmoves/mk/egress.mk` or the `JUICEFS_NETWORK` handling for the post-cutover mount | per path check |
| `juicefs config` on the live volume; stopping mounts; firewall on any storage node; removal of any KVM docker volume | operator action, not an agent action |

### Operator decisions

| # | Decision | Status |
|---|---|---|
| **D1** | Metadata engine (§2) | **DECIDED: replicated Postgres**, Patroni preferred. A separate follow-on plan, run after this one |
| Tiers | Availability tiers (§1.1) | **DECIDED:** tier 1 (always-on) = kvm2, kvm4-1, kvm4-2, Spark. Tier 2 (desktop) = 5090, Z890, Knuckles, 4090 |
| Topology | Fleet-wide Garage mesh (§1.0) | **DECIDED:** every capable node is a storage node and a JuiceFS client. NATS stays off the mesh |
| D2 | What the recorded bucket URL names (§1.4) | OPEN: (i) one tier-1 node with `juicefs config --bucket` failover, or (ii) a per-node local name |
| D3 | Per-node capacity declarations for each fleet node (§1.1) | **OPEN — per-node capacity declarations for each fleet node.** KVM declared capacity stays **tiny** until the BuildKit build cache (`buildx_buildkit_pmoves-shared0_state`, 5-9 GiB/day on the kvm4s) is capped or pruned through the build-cache road. That ops item is owned outside this plan. Every other node is COULD-NOT-MEASURE |
| D4 | Soak length N | Recommendation: ≥ 14 days, including the non-endpoint node-down test and the separate failover drill |
| D5 | Garage ports tailnet-only | Recommendation: yes. `tailscale0` only, with S3/admin bound to the tailnet address (§1.3). The external probe is a required gate; who runs it is **OPEN — OPERATOR** |
| D6 | Known Road grants for the compose, funnel and egress edits | Recommendation: grant per PR, as in the table above |
| D7 | Zone grouping (all tier-2 nodes in one `lab` zone) vs one zone per node (§1.2) | **OPEN — OPERATOR.** Not viable today: usable ≤ ~23 GB until the KVM build cache is reclaimed or Spark is measured |
| D8 | Throughput | **MEASURED** (containerised iperf3, 2026-09-27): KVM↔KVM 345-383 Mbit/s. Knuckles → KVM 18-19 Mbit/s, which is the binding constraint: ~9.5-10 h per full pass of the measured 80.93 GB (Step 0 record; the earlier ~10.5 h assumed 85 GB) |

## 6. Reconciliation against Garage's official documentation (2026-10-01)

**Method.** Every row cites the vendor page and section, relative to `https://garagehq.deuxfleurs.fr/documentation/`. The pages are the
v2.4.1 docs: `doc/book/` at upstream tag `v2.4.1` (commit `268334bd2`), which the site serves.
Every URL cited returned HTTP 200 on 2026-10-01. Where the docs are silent, the row cites the
v2.4.1 source instead and says so.

**Neither vendor documents this pairing.** JuiceFS's object-storage guide (`juicedata/juicefs`
`docs/en/reference/how_to_set_up_object_storage.md`, main) does not mention Garage, and
Garage's `connect/fs/` page does not mention JuiceFS. Compatibility rests on Gate A's
`objbench`, list included.

### 6.1 Gap table

| # | Topic | Our plan | Vendor docs (page, section) | Gap | Fix |
|---|---|---|---|---|---|
| 1 | Minimum topology | Fleet-wide mesh, ≥3 zones in the first cut (§1.2, Gate A) | `cookbook/real-world/` "Prerequisites": at least three machines, each "directly reachable by all other machines"; a mesh VPN is acceptable | None. Tailscale fills the mesh-VPN role | — |
| 2 | Zones and capacity | Usable ≈ smallest zone at exactly 3 zones; derived formula for N>3 (§1.2) | `cookbook/real-world/` "Prerequisites": 3 copies "always" in different locations, so the 4-node example yields 1.5 TB usable; `operations/layout/` Example 1 | None. Our derivation agrees, and Gate A reads the authoritative figure from `layout show` | — |
| 3 | `replication_factor` | 3, never changed later (§1.2) | `reference-manual/configuration/` `replication_factor`: must be identical in every node's config ("Never run a Garage cluster where that is not the case"). A change means deleting the layout files on all nodes plus a full rebalance, "not officially supported" | The plan does not require the value to match on every node | Gate A: diff the rendered `garage.toml` across nodes; `replication_factor` and `consistency_mode` must be identical |
| 4 | `consistency_mode` | `consistent`, quorum 2/2 at RF=3 (§1.2) | `reference-manual/configuration/` `consistency_mode`: the quorum table matches (consistent, RF 3: W2/R2). `degraded` lowers the read quorum to 1 | None on the setting. The docs offer `degraded` as an outage lever: reads continue with one replica up | Name `degraded` in §1.2 as an operator-only emergency lever for the Spark-down plus `lab`-down case, with its cost (no read-after-write consistency). Do not make it the default |
| 5 | Secret files | `rpc_secret_file`, `admin_token_file`, `metrics_token_file` under `/run/secrets/` (§1.3) | `reference-manual/configuration/` `rpc_secret`, `admin_token`, `metrics_token`, `allow_world_readable_secrets`: file forms are supported, and Garage checks secret-file permissions. Source `src/garage/secrets.rs:144`: **refuses to start if `mode & 0o077 != 0`** ("expected 0600") | **Blocker if missed.** Compose (non-swarm) secrets are bind mounts that keep the host file's mode, so a 0644 host file stops Garage at boot | Each node's secret files are 0600 (or 0400) and owned by `GARAGE_UID`. The container runs as that uid with every capability dropped: root without `CAP_DAC_OVERRIDE` could not read another uid's 0600 file. `make -C pmoves garage-preflight` stats the files (it never reads them) and checks presence, owner and mode before `up`. Never set `allow_world_readable_secrets` or `GARAGE_ALLOW_WORLD_READABLE_SECRETS` |
| 6 | Metrics auth | `metrics_token_file` set (§1.3) | `reference-manual/configuration/` `metrics_require_token` (since v2.0.0) | Without `metrics_require_token = true`, an unset or unread token leaves `/metrics` open | Add `metrics_require_token = true` to `[admin]` |
| 7 | Admin token | One static `admin_token_file`, full scope (§1.3, §1.6) | `reference-manual/configuration/` `admin_token`: since v2.0, dynamic admin tokens carry an **expiry and a scope**; the static token is full scope with no expiry. `reference-manual/admin-api/` shows `--scope ... CreateBucket,CreateKey,AllowBucketKey` | The plan uses only the full-scope static token | Keep the static token for bootstrap. Mint a scoped, expiring token for the migration context (Step a) and one for Prometheus |
| 8 | Ports | 3900 S3, 3901 RPC, 3903 admin; no 3902 (§1.3) | `quick-start/` and `cookbook/real-world/` configs: 3900 S3, 3901 RPC, 3902 `[s3_web]`, 3903 admin | None. `[s3_web]` is omitted on purpose, so 3902 is not bound; the external probe covers 3900/3901/3903 | Note in §1.3 that `[s3_web]` is intentionally absent |
| 9 | Key and bucket commands | `key create`, `bucket create`, `bucket allow --read --write` (Step a); `key import` syntax COULD-NOT-MEASURE (§1.6) | `quick-start/` "Creating buckets and keys": `garage key create <name>` prints `Key ID: GK` + 24 hex and the secret; then `bucket allow ... --key <name>`. Source: the key ID is GK + hex of 12 random bytes (`src/model/key_table.rs:149`). `key import` (`structs.rs` `KeyImportOpt`) takes `key_id secret_key`, `-n` name (default "Imported key") and `--yes`. It accepts any ID of ≥8 chars from `[A-Za-z0-9._-]` and any secret of ≥16 graphic chars | The plan's `key import --yes <GK..> <secret>` omits `-n`. The key would be named "Imported key", and Step (a)'s `bucket allow --key juicefs-pmoves-media` would not match it | Fixed inline in §1.6. The funnel shape check (`GK` + 24 hex) is right for `key create`. An imported key need not match it, so if the funnel generates the key, it must generate the same shape |
| 10 | Layout commands | `layout assign <id> -z -c -t`, `layout show`, `layout apply --version 1`; never `layout config -r` (Step a) | `cookbook/real-world/` "Creating a cluster layout"; `operations/layout/`; `reference-manual/known-issues/` "Tag assignment": repeat `-t` for each tag (a comma-separated list becomes one string) | None with one tag per node | If a second tag is added, repeat `-t` |
| 11 | Layout eviction | Node-down test; layout changes as nodes join (§1.0, Step e) | `reference-manual/known-issues/` "Layout updates might require manual intervention": with disconnected nodes, old layout versions can stay active; diagnose with `garage layout history` | The plan never mentions `layout history` | Add `garage layout history` to the Step (e) soak gate and to every layout change |
| 12 | Node connect | `node id`, then `node connect <id>@<peer>:3901` (Step a) | `cookbook/real-world/` "Connecting nodes together": nodes discover each other transitively. `reference-manual/configuration/` `bootstrap_peers` declares peers in config | A manual connect lives in a session, not in config | Prefer `bootstrap_peers` in the rendered `garage.toml`, so membership is tracked config and not node-local state |
| 13 | Docker networking | Host networking on Linux; Tailscale sidecar on Windows (§1.3, §1.3a) | `cookbook/real-world/` "Starting Garage using Docker": host networking, because Docker's network indirection "would prevent Garage nodes from communicating" | None on Linux. The Windows sidecar is outside the vendor's documented path | Keep §1.3a as COULD-NOT-MEASURE |
| 14 | Filesystem for `data_dir` | Root fs on each node. The KVMs and Knuckles' NVMe1 are ext4 (§1.1, Step 0 record) | `cookbook/real-world/` "Best practices": **XFS is recommended** for data and "EXT4 is not recommended" (inode limits at large object counts). BTRFS or ZFS is preferred for metadata | Every measured candidate is ext4 | Inode pressure at this scale is small (~19k objects, ~80k 1 MiB blocks), so ext4 is acceptable for the first cut. Record it as an accepted deviation and check `df -i` in G1 |
| 15 | `db_engine` and LMDB | `lmdb` on every node, 6h snapshots (§1.3) | `reference-manual/configuration/` `db_engine`; `cookbook/real-world/` "Best practices"; `reference-manual/known-issues/` "LMDB metadata corruption": LMDB corrupts after an unclean shutdown or power loss and is "generally not recoverable"; Sqlite is "more robust" | Tier-2 desktops sleep, reboot and lose power (§1.2), which is LMDB's failure case | Set `db_engine` per node (the database is local): `lmdb` on tier 1, **`sqlite` on tier-2 desktops**. This is an operator decision |
| 16 | Snapshots | `metadata_snapshots_dir` as a sibling of `data_dir` (§1.3) | `reference-manual/configuration/` `metadata_snapshots_dir`: up to 4× the metadata size. `known-issues/`: prefer built-in snapshots over filesystem snapshots | None | — |
| 17 | `block_size` | Not set (1 MiB default) | `reference-manual/configuration/` `block_size`: 1 MiB default; 10 MiB recommended for large files on fast links. `known-issues/` "Very big objects" | JuiceFS writes objects no larger than its own 4 MiB block, so each object becomes 4 Garage blocks. Links from Knuckles run at ~18 Mbit/s, which is not "fast" | Keep 1 MiB for the first cut. The setting affects only new uploads, so it can be revisited without a rewrite |
| 18 | Compression | Not set (zstd level 1 by default) | `reference-manual/configuration/` `compression_level`: `'none'` disables zstd; the value is set per node | **The volume is `aes256gcm-rsa` encrypted** (Step 0 record), so blocks are incompressible ciphertext, and zstd spends CPU for nothing on the 2-vCPU kvm2 | `compression_level = "none"` on every node |
| 19 | Region | `s3_region = "us-east-1"` (§1.4) | `reference-manual/configuration/` `s3_region`: other regions fail with `AuthorizationHeaderMalformed` | None | — |
| 20 | Addressing style | Path-style, with the `minio://` scheme for sync (§1.4, Step b) | `reference-manual/configuration/` `root_domain`: "path-style requests are always enabled". `reference-manual/s3-compatibility/` "High-level features": path-style is implemented | None. No `root_domain` is needed | — |
| 21 | S3 operations JuiceFS uses | List was the #3199 failure | `reference-manual/s3-compatibility/` "Core endpoints": ListObjects, ListObjectsV2, DeleteObject, DeleteObjects and Head/Get/PutObject are implemented, as are all "Multipart Upload endpoints" | None on paper, but neither vendor documents the pairing | Keep Gate A's `objbench` mandatory, list included |
| 22 | Single-bucket hotspot | One bucket, `juicefs` (§1.5) | `reference-manual/known-issues/` "Buckets are not sharded": a bucket's object index lives on RF nodes "chosen at random", and "there is no way of choosing which nodes" | **The index nodes for bucket `juicefs` may be tier-2 nodes**, whatever the capacity weighting; lever 1 in §1.2 does not move them | Record this in §1.2 as a limit of lever 1. Under zone grouping (D7), at most one index replica can sit in `lab`. Index placement after `bucket create` is COULD-NOT-MEASURE (no documented command) |
| 23 | Resync speed | Gate B: "no resync backlog" | `reference-manual/known-issues/` "Resync tranquility is conservative by default": the queue can grow faster than it clears. Tune with `garage worker set -a resync-worker-count N` and `resync-tranquility 0` | On the defaults, Gate B can stall during an 80 GB ingest | Add the worker settings to Step (b) as an operator-tunable. Read `garage stats` before declaring a backlog |
| 24 | Node count | 8 nodes | `reference-manual/known-issues/` "Node count limitation": problems start above 10 × RF (30 nodes at RF=3) | None | — |
| 25 | RF=1 shortcut | — | `reference-manual/known-issues/` "Metadata and data have the same replication factor": do not use RF=1 | A single-node "stand it up on Knuckles first" shortcut would break this rule, and RF cannot be changed later (row 3) | Never stand up an RF=1 or single-node cluster as a staging step for this volume |

### 6.2 Build and pin (the fork)

**Fork facts.** Measured 2026-10-01 before Phase A, then after the fork prep, using `gh repo view`, `gh api .../branches/*/protection` and `git ls-remote`.

| Item | Before | After the fork prep (2026-10-01) |
|---|---|---|
| Repo | `POWERFULMOVES/PMOVES-garage`, a GitHub fork of `deuxfleurs-org/garage` (the GitHub mirror of `git.deuxfleurs.fr/Deuxfleurs/garage`) | unchanged |
| Branches | `main-v2` only (the default), unprotected, identical to upstream `main-v2` (`5ad1de0b0`) | `main-v2` unchanged, plus `PMOVES.AI-Edition-Hardened` at `268334bd2` (= `v2.4.1^{commit}`) |
| Tags | none | all 91 upstream tags pushed (no `.github/` at `v2.4.1`, so the pushes triggered nothing) |
| Protection | none | `main-v2` and Hardened carry the fleet standard policy, the same body `branch-protection-sync.yml` `policy()` sends: PR required (0 reviews, dismiss stale), no force-push, no deletion, conversation resolution, `require_last_push_approval: false`. Read back field by field, and it matches PMOVES-registry's Hardened protection (#3206 precedent) |
| Image CI | none | `POWERFULMOVES/PMOVES-garage#1` (open, not merged): `.github/workflows/pmoves-ghcr.yml` and `PMOVES.AI_INTEGRATION.md` |

**How the image is built.** The repo's own `Dockerfile` (`FROM scratch` plus `COPY result/bin/garage`) packages a Nix build; it does not compile anything. Rather than replace it with a multi-stage Dockerfile, the fork CI runs **upstream's own release recipe**:
- `nix-build --attr releasePackages.${ARCH} --argstr git_version <tag or sha>`, then `script/not-dynamic.sh`, then `script/test-smoke.sh` on amd64. These are the `build`, `check is static binary` and `integration tests` steps of `.woodpecker/release.yaml` at `v2.4.1`, with the substituters from `nix/nix.conf`.
- The image is built from the upstream `Dockerfile`, unchanged, for amd64 and arm64. Both arches cross-compile on one amd64 runner, as upstream's matrix does.
- Each arch is pushed by digest, then merged into one manifest list at `ghcr.io/powerfulmoves/pmoves-garage/garage`. Upstream uses kaniko and `manifest-tool` for this step.
- GHCR naming and `GITHUB_TOKEN` auth follow the PMOVES fork precedent `POWERFULMOVES/PMOVES-DoX` `.github/workflows/docker-publish.yml`.
- PR runs build without pushing. The step summary prints the manifest-list digest to pin.
- arm64 is built, so Spark has an image. Whether Garage runs well on Spark is still COULD-NOT-MEASURE.

**Pin to the release, not the branch tip.**
- Cut `PMOVES.AI-Edition-Hardened` from tag `v2.4.1` (`268334bd2`), not from `main-v2`.
- The upstream tags have to be pushed to the fork first.

**fork-sync conflicts with a release pin.**
- `fork-sync.yml` merges the upstream default branch into the branch named in the third FORKS column. If that column is empty, it uses the `.gitmodules` branch.
- With `branch = PMOVES.AI-Edition-Hardened` in `.gitmodules`, **sync would merge unreleased `main-v2` into Hardened.**
- So the mapping must set the override to `main-v2` (`deuxfleurs-org/garage|PMOVES-garage|main-v2`). Then only the parity branch is synced, and Hardened moves only by deliberate, tag-based promotion.

**Does the fork change D2/D3?** No. The endpoint choice (D2) and per-node capacity (D3) are topology decisions. The fork changes only where the binary comes from. It does add build work before Gate A: a multi-arch image, a GHCR publish, and a digest pin.

### 6.3 RPC bind address: OPEN — OPERATOR (recommendation: option A)

**What the vendor docs say** (`reference-manual/configuration/`, v2.4.1):
- `rpc_bind_addr`: "The address and port on which to bind for inter-cluster communications". The only constraint stated is on the **port**: it "should be the same one that other nodes will use to contact the node, even in the case of a NAT". Nothing requires a wildcard address.
- `rpc_public_addr`: "The address and port that other nodes need to use to contact this node for RPC calls. This parameter is optional but recommended." Peers learn it, and `bootstrap_peers` entries come from `garage node id` only when it is set (`bootstrap_peers` section).
- `rpc_public_addr_subnet`: used only when `rpc_public_addr` is unset; it filters autodiscovered addresses to a subnet.
- `rpc_bind_outgoing`: pre-binds outgoing sockets to the `rpc_bind_addr` IP, for hosts with several addresses where only one reaches the peers. Disabled by default.
- `cookbook/real-world/` "Configuration": the example uses `rpc_bind_addr = "[::]:3901"` with `rpc_public_addr = "<this node's public IP>:3901"`. That example assumes nodes on public addresses; ours reach each other only over the tailnet.
- Source, v2.4.1 `src/garage/main.rs` (CLI connect): the CLI dials `rpc_public_addr` when it is set, and otherwise `127.0.0.1:<rpc_bind_addr port>`. So binding off loopback requires `rpc_public_addr`, which every option below sets.

**Measured on Knuckles (2026-10-01, interface classes only; no addresses recorded):**
- IPv4: `tailscale0` (100.64.0.0/10), `wlp8s0` (RFC 1918, behind residential NAT), `docker0` and 13 `br-*` bridges (RFC 1918), `lo`.
- **IPv6: `wlp8s0` carries 2 global-scope addresses.** Residential NAT does not cover IPv6, so on this node a `[::]` bind is reachable from the IPv6 internet unless the router or a host firewall drops it.
- `net.ipv4.ip_nonlocal_bind = 0` and `net.ipv6.ip_nonlocal_bind = 0`: a bind to the tailnet address fails until `tailscale0` has it.
- `docker.service` has no `After=` ordering on `tailscaled.service`, and both are enabled. At boot Docker can start the container before the tailnet address exists.
- Nothing listens on 3900-3903 today. No exit node is in use.

| Option | `rpc_bind_addr` | `rpc_public_addr` | Exposure | Boot behaviour | Per-node render |
|---|---|---|---|---|---|
| **A (current template)** | `<tailnet IPv4>:3901` | `<tailnet IPv4>:3901` | Listens on `tailscale0` only. A firewall mistake cannot expose 3901, because nothing listens elsewhere | Bind fails until `tailscaled` has the address; `restart: unless-stopped` retries until it does. Garage logs a bind error meanwhile | Yes (already done by `garage-render`) |
| B (vendor cookbook shape) | `[::]:3901` | `<tailnet IPv4>:3901` | Listens on every interface, including the KVMs' public addresses and Knuckles' global IPv6. Safety rests entirely on the `tailscale0`-only firewall rule on every node, and on the router for tier 2 | No boot dependency | Yes (`rpc_public_addr`) |
| C (shared config) | `[::]:3901` | unset; `rpc_public_addr_subnet = "100.64.0.0/10"` | Same as B | No boot dependency | No for RPC, but S3 and admin still bind per node in our design, so the render does not go away |

RPC traffic is authenticated and encrypted with `rpc_secret`, so B/C expose an authenticated protocol rather than open data. It is still a listener on public addresses of public exit nodes, which is what §1.3 and D5 rule out.

**Recommendation: A.** It is the only option where the external probe gate (§1.3) is a second check rather than the only one, and it costs nothing the docs require: the port is the same everywhere, and `rpc_public_addr` is set as recommended. The boot-order gap is real; if the restart loop proves noisy, the fix is an ordering drop-in for `docker.service` (`After=tailscaled.service`), an operator host change, not a wildcard bind. `rpc_bind_outgoing` is not needed: outgoing connections to 100.64.0.0/10 already leave through `tailscale0`.

**Decision text for the operator:** "RPC binds the node's tailnet IPv4 (option A, §6.3). Accepted: a node whose `tailscaled` starts after Docker restarts Garage until the address exists."

## 7. PMOVES-garage integration checklist (precedent: #3206, PMOVES-registry / PMOVES-spynel)

Status as of 2026-10-01 (Phase A agent prep, updated after the first fleet review). Protection status comes from `python3 .claude/skills/known-roads/roads.py check <path>`.

| # | Item | Path or place | Protection | Status |
|---|---|---|---|---|
| 1 | Push the upstream tags to the fork; cut `PMOVES.AI-Edition-Hardened` from `v2.4.1` | fork repo | — | **DONE** (§6.2) |
| 2 | Hardened overlay: image CI (amd64 + arm64) and `PMOVES.AI_INTEGRATION.md` | fork, hardened branch | — | **PR OPEN**: `POWERFULMOVES/PMOVES-garage#1`. Not merged; operator review |
| 3 | Branch protection on `main-v2` and Hardened | GitHub API | — | **DONE**, read back (§6.2). `branch-protection-sync.yml` audits it via `.gitmodules` |
| 4 | `.gitmodules` entry: path `PMOVES-garage`, `branch = PMOVES.AI-Edition-Hardened`, `ignore = all` | `.gitmodules` | `noDeletePaths` only | **DONE** in #3241 |
| 5 | Submodule gitlink at the Hardened commit | `PMOVES-garage` | none | **DONE** at `268334bd2`. That is an ancestor of Hardened after #1 merges (any merge style), so there is no SIDEWAYS drift. Advance it when the image is published |
| 6 | Registry entry: `upstream: deuxfleurs-org/garage`, `sync: true`, `branch: PMOVES.AI-Edition-Hardened` | `pmoves/config/fork_registry.json` | none | **DONE**. `fork_registry_ratchet.py`: 83/83 decided |
| 7 | Audit-list entry and mapping `deuxfleurs-org/garage\|PMOVES-garage\|main-v2` | `.github/workflows/fork-sync.yml` | `noDeletePaths` only | **DONE**. The override is `main-v2`, not Hardened |
| 8 | Section and summary row | `.claude/context/submodules.md` | **`readOnlyPaths`, no Known Road** | **OPERATOR.** The patch is posted on #3241. Re-checked with `git apply --check` after merging main into the branch (2026-10-01): applies cleanly |
| 9 | GHCR build of the hardened image, digest recorded | fork CI | — | **PENDING** on item 2 merging and the first run on Hardened |
| 10 | Compose service | `pmoves/docker-compose.garage.yml` | `readOnlyPaths`, road `compose` | **PREPARED, NOT WRITTEN.** Waits for the grant `compose:pr:3241` |
| 10a | Config template, renderer and secret-mode preflight; make targets | `pmoves/config/garage/garage.toml.tmpl`, `pmoves/tools/garage_render_config.py`, `pmoves/mk/garage.mk` | none / `noDeletePaths` | **DONE** in #3241, with tests. The compose-driven targets refuse with the grant name until item 10 lands |
| 10b | Secret files from the tier env file: `make -C pmoves garage-secrets` (§1.6 "Last hop") | `pmoves/tools/garage_render_config.py materialize` | none | **DONE** in #3241, with tests. Operator-run (reads `env.tier-data`) |
| 11 | Funnel labels (§1.6) | `REGISTRY` in `chit_manifest_register.py`, the bundle map in `sync-secrets-local.yml`; the CHIT secrets manifest | `noDeletePaths`; manifest zero-access, no road | **REGISTRY and bundle map DONE** in #3241. Manifest write, values, GitHub secrets: **OPERATOR** (G2) |
| 12 | RPC bind address | `garage.toml.tmpl` | none | **OPEN — OPERATOR** (§6.3; recommendation A, which is what the template does today) |

**Operator-only items (Phase A):**
1. Write the five manifest entries from `REGISTRY`: `make -C pmoves chit-manifest-register`, then `make -C pmoves chit-manifest-sync`. Generate the three cluster values in operator context (`openssl rand -hex 32` for `GARAGE_RPC_SECRET`; `openssl rand -base64 32` for each token, per `cookbook/real-world.md` and `quick-start/`), set them as GitHub secrets, and name the delivery vehicle for each storage node (G2).
2. After the first node is up: `garage key create` and `garage admin-token create` in operator context, output to a `umask 077` intake file only (§1.6, Step a). The key pair then goes in as `JUICEFS_GARAGE_ACCESS_KEY` / `JUICEFS_GARAGE_SECRET_KEY`.
3. Run the external port probe of 3900, 3901 and 3903 on every storage node's public address, IPv4 and IPv6, from outside the tailnet, once Garage is listening (§1.3; today's baseline is recorded there and does not pass the gate).
4. Grant `compose:pr:3241` for `pmoves/docker-compose.garage.yml`.
5. Apply the `.claude/context/submodules.md` patch (item 8).
6. Decide the RPC bind address (§6.3).
