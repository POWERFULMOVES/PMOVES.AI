# JuiceFS `pmoves-media`: Garage migration plan and runbook

**Status:** PLAN ONLY (2026-09-26). Nothing here has been executed. Every step in §3 is operator-gated.
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
- kvm4-2's profile says it is **over-subscribed**: "resolve before adding data-plane services here".

> **HARD CAUTION: "unused" docker volumes are not garbage.** "Unused" means only "not attached to a running container". The ~140G on kvm4-1 and the ~146G on kvm4-2 (the data-storage node) may be real stores: an old Postgres, an old MinIO, possibly JuiceFS data. **Never prune.**
> - Before any volume is removed, it is identified one by one: owner, contents, last write, and whether any backup or migration depends on it.
> - Each removal needs explicit operator confirmation that names the volume.
> - This is **G0 item "identify KVM docker volumes before declaring capacity"** (§5). Until it passes, the KVM capacity declarations use **free now**, not "free if cleared".

**Spark (tier 1) and the tier-2 nodes:**

| Node | Tier | OS (profile) | Free disk for Garage | Note |
|---|---|---|---|---|
| Spark | 1 | DGX OS 7.5.0, arm64 (`dgx-spark-grace-blackwell.yaml:21,29`) | **COULD-NOT-MEASURE** (the node is down) | **DOWN on 2026-09-27.** arm64: whether the pinned `dxflrs/garage:v2.4.1` digest has an arm64 variant is COULD-NOT-MEASURE. Spark is also a secrets-bundle producer (§1.6) |
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

**How the layout expresses the decided tiers.** A Garage layout has only three per-node inputs: role (storage with a capacity, or gateway with none), zone, and capacity. Tags are labels (`operations/layout.md`, `cookbook/real-world.md` "Best practices"). **There is no availability, priority or preference attribute.** So "always-on carries more of the load" has to be expressed through the two levers below.

1. **Capacity weighting: applied, and it implements the decision.**
   - Tier-1 nodes declare as much capacity as their headroom allows. Tier-2 nodes declare less.
   - The algorithm assigns partitions in proportion to declared capacity, so tier 1 holds a larger share of the replicas.
   - Example 1 in `operations/layout.md` shows the docs' own use of this lever: halve a node's declared capacity to force data off it.
   - **Limit:** weighting shifts proportions. It **cannot guarantee** that a partition keeps 2 replicas on tier 1. Under one zone per node, some partitions will have 2 or 3 replicas on tier-2 nodes. When those nodes sleep or reboot, that partition loses its 2-of-2 read quorum and its write quorum, for **every** client, including KVM Jellyfin. The layout cannot express "prefer tier 1 for quorum" by itself.
2. **Zone grouping: the strongest structural lever. OPEN — OPERATOR, because it departs from "one zone per node".**
   - Give each tier-1 node its own zone (kvm2, kvm4-1, kvm4-2, spark), and put **all tier-2 nodes in one shared zone** (e.g. `lab`).
   - With replicas "on at least 3 distinct zones" (`garage layout show` output in `operations/layout.md`), each partition then has at most one replica in `lab`. At least two of every partition's replicas sit on tier 1.
   - **What this does NOT guarantee:** quorum survives all of tier 2 going down **only while that partition's tier-1 replicas are up**. With Spark down (as on 2026-09-27), every partition whose replicas are {spark, one KVM, lab} runs on a single live replica if `lab` is also down. With consistent RF=3 that means **no reads and no writes** for those partitions. Two tier-1 failures, or one tier-1 failure plus the `lab` zone, stop some partitions whatever the layout is.
   - The cost is that the tier-1 zones must together hold **two copies of everything**.

**What today's measured free space allows.** The figures below are arithmetic on the §1.1 survey, with G1's headroom rule applied: declared capacity ≤ half of measured free space. They are not measurements, and tier-2 capacity is COULD-NOT-MEASURE.

| Tier-1 declared `-c` (G1 half-of-free) | kvm2 | kvm4-1 | kvm4-2 | Spark | KVM total |
|---|---|---|---|---|---|
| Today ("free now") | ~39G | ~7G | ~15G | COULD-NOT-MEASURE (down) | ~61G |
| After volume cleanup (G0 identification and operator confirmation first) | ~39G | ~75G | ~90G | COULD-NOT-MEASURE | ~204G |

- **The tension.** The volume needs ~85 GB × 3 = ~255 GB of replica space, before growth.
  - **Today** the KVMs can hold at most ~61G of that, about a quarter. Spark's share is unknown while it is down. Most quorum-bearing replicas would sit on tier 2. That is the opposite of the decided tiering, and it persists until the KVM volumes are identified and, only with confirmation, cleaned up, or until Spark's capacity is measured and declared.
  - **Zone grouping today, KVMs only** (Spark excluded while down): usable U ≤ ~23 GB, by the formula above over zones {kvm2 39, kvm4-1 7, kvm4-2 15, lab large}. That is **below the ~85 GB needed**, so zone grouping is not an option until cleanup or until Spark adds capacity.
  - **After cleanup, KVMs only:** zone grouping gives U ≤ ~102 GB. That fits ~85 GB with thin headroom for growth. Spark raises the bound by an amount that cannot be computed until its free space is measured.
  - One-zone-per-node with capacity weighting fits the data today, because tier 2 supplies the capacity. It trades away the quorum guarantee for as long as tier 1 stays small.
- **Tier-2 availability hazards (named, not decided).**
  - Desktops and Windows nodes sleep, take update reboots, and may not start Docker Desktop until someone logs in.
  - Which tier-2 nodes are actually up 24/7 is COULD-NOT-MEASURE, because no profile records uptime.
  - A tier-2 node that holds replicas also works against the §0.8 asymmetry ("operators keep viewing when the lab is down"). This plan names that; it does not resolve it.

### 1.3 `garage.toml` (same on every storage node; no secret values in the file)

```toml
replication_factor = 3
consistency_mode   = "consistent"
metadata_dir       = "/var/lib/garage/meta"
data_dir           = "/var/lib/garage/data"
db_engine          = "lmdb"
metadata_auto_snapshot_interval = "6h"
metadata_snapshots_dir = "/var/lib/garage/snapshots"   # sibling of data_dir, not inside it; up to 4x meta size

rpc_bind_addr   = "[::]:3901"                          # peers dial rpc_public_addr; firewall-gated below
rpc_public_addr = "<this node's tailnet address, rendered at deploy>:3901"
rpc_secret_file = "/run/secrets/pmoves_garage_rpc_secret"

[s3_api]
api_bind_addr = "<this node's tailnet address>:3900"   # never [::]: the KVMs are public exit nodes
s3_region     = "us-east-1"          # see 1.4: matches JuiceFS's default region

[admin]
api_bind_addr      = "<this node's tailnet address>:3903"
admin_token_file   = "/run/secrets/pmoves_garage_admin_token"
metrics_token_file = "/run/secrets/pmoves_garage_metrics_token"
```

- **Image:** `dxflrs/garage:v2.4.1` (latest, 2026-09-08). Pin it by digest at deploy time, per F-07.
- **Network:** host networking, per Garage's `cookbook/real-world.md`.
- **Snapshots dir:** `/var/lib/garage/snapshots` is a sibling of `data_dir`. It must not sit inside `data_dir`, which Garage manages as its block store.
- **Bind addresses:** the S3 and admin APIs bind to the node's tailnet address, so they are not listening on the public interface at all. A bind to a tailnet address fails if `tailscaled` is not up when Garage starts. The deploy must order Garage after Tailscale, or rely on a restart policy. RPC stays on `[::]`, because peers reach it at `rpc_public_addr`. It is protected by the firewall rule and the gate below.
- **Firewall (required on every storage node, and critical on the KVMs because they are public exit nodes):** allow 3900/3901/3903 on `tailscale0` only. Tier-2 nodes sit behind residential NAT, but the same rule applies. No port-forward for 3900/3901/3903 may exist on any router in front of them.
- **Hostinger firewall today (Hostinger REST, read-only, 2026-09-27):** no Hostinger firewall rule mentions 3900, 3901 or 3903, and no drop rules exist. The API does not expose the default policy. So whether these ports are closed on the public addresses is **COULD-NOT-MEASURE** from the API.
- **External port-probe gate (REQUIRED; OPEN — OPERATOR):** before Gate A passes, probe **all three ports (3900, 3901, 3903) on every KVM's public address from a host outside the tailnet**. Every probe must be refused or time out. One open port fails the gate. A probe from inside the tailnet proves nothing, because tailnet traffic is allowed by design. Who runs the probe, and from which outside host, is an operator decision.

### 1.3a Garage on Windows nodes (5090; the 4090 if it runs Windows)

Every item in this subsection is **COULD-NOT-MEASURE** until someone tries it on the node.

- **Runtime.** A Linux container under Docker Desktop (WSL2 backend), using the same `dxflrs/garage` digest pin as the Linux nodes.
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
  - **(i) One tier-1 node's tailnet name** is recorded as the endpoint, with failover through `juicefs config --bucket`. Spark being down on 2026-09-27 shows that the chosen node can be the one that is down.
  - **(ii) A name that resolves on each client to that client's own local Garage.** The earlier objection to this, that per-client gateways "spread `rpc_secret` to every lab node", no longer applies: in the fleet-wide layout every storage node already holds `rpc_secret`. Whether one name can resolve per node, and resolve inside Docker bridge networks, is COULD-NOT-MEASURE.
- **Unverified:** whether containers on a Docker bridge network (`pmoves_data`) resolve MagicDNS names. Gate A tests this.

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
1. The `pmoves/chit/secrets_manifest_v2.yaml` entry.
2. `REGISTRY` in `pmoves/tools/chit_manifest_register.py` (tier `data`, `required: False`).
3. The bundle map in `.github/workflows/sync-secrets-local.yml`.
4. The GitHub secret itself.

**Key-print hazards:**

| Command | Hazard | Handling |
|---|---|---|
| `garage key create` | **Prints the secret key to stdout** (`print_key_info`) | Operator context only. Redirect stdout to a `umask 077` intake file, feed that file to the funnel, then `shred -u` it. Never run it in an agent session |
| `garage key import --yes <GK..> <secret>` | Secret on argv | Alternative when the funnel generates the key. Run it on the KVM, not over a logged channel |
| `garage key info --show-secret` | Prints the secret | Do not use |
| `juicefs config --secret-key` | Does not read `SECRET_KEY` from env (v1.3.0 `cmd/config.go`), so the secret is on argv | Pass it in through the `jfs()` env file (§3) and expand it inside `sh -c`. It is then in the juicefs process argv for the seconds the call runs |
| `juicefs sync minio://AK:SK@...` | juicefs sync 1.3.0 reads object-store credentials **only from the URL**. There are no `SRC_*`/`DST_*` env vars in JuiceFS. The `SRC_AK`-style names in §3 are plain shell variables, expanded by `sh -c` inside the container | URL-encode `/` as `%2F` in the URL form. The exposure is stated below; it cannot be avoided with 1.3.0 |

**Real exposure window (do not understate it):**
- **Container environment.** Anything passed with `-e` or `--env-file` is stored in the container's recorded config, in its environment list. It is readable through `docker inspect` by anyone with Docker socket access, for the **whole lifetime of the container**. With `--rm`, that lifetime is the call: seconds for `status`, `config` and `fsck`, and **hours** for a sync pass.
- **Process argv.** Container processes are host processes. For the whole of every sync pass, the expanded `minio://AK:SK@...` URLs sit in the juicefs argv, readable by host `ps` and `/proc/<pid>/cmdline`. That is hours per pass. Any collector that records process command lines will capture them.
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
- `META_PASSWORD` comes from the funnel (`JUICEFS_META_PASSWORD`). `SRC_*` are the MinIO credentials and `DST_*` are `JUICEFS_GARAGE_*`, exported in this shell only and never echoed.
- A failed gate means STOP.
- Exit-code doctrine: 0 clean / 1 findings / 3 could-not-measure. Call the tools directly, because `make` collapses exit codes.

```bash
JFS_IMG=juicedata/mount:ce-v1.3.0
META='postgres://juicefs_meta@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable'
jfs() { docker run --rm --network pmoves_data -e META="$META" -e META_PASSWORD \
          -e SRC_AK -e SRC_SK -e DST_AK -e DST_SK "$JFS_IMG" sh -c "$*"; }
```

### Step 0: Baseline (read-only)

```bash
jfs 'juicefs status "$META"'      # record UUID, Storage=minio, Bucket, BlockSize, Sessions
jfs 'juicefs gc "$META"'          # NO --delete: reports leaked/pending objects only
# object inventory via mc inside the minio container (mc ships in the #3192 image; alias as `make backup` uses):
docker exec pmoves-minio-1 mc ls <alias>/juicefs/
docker exec pmoves-minio-1 mc du --recursive <alias>/juicefs/pmoves-media/
```

**Gate 0:**
- Only the `pmoves-media/` prefix exists.
- Object count and bytes are recorded, and the 85 vs 76 GB gap is explained.
- `sha256sum` of 3 sample files is recorded.
- A metadata backup exists: `juicefs dump --binary` to NVMe1, plus a `pg_dump -n juicefs_meta` via its Known Road.

### Step (a): Stand up Garage, bucket, key

```bash
# each KVM (deploy under a Known Road grant, §5): host net, secrets from the funnel
garage node id                                     # collect 3 ids
garage node connect <id>@<peer tailnet addr>:3901  # from one node, for the other two
garage layout assign <id-kvm2>   -z kvm2   -c <measured>G -t kvm2
garage layout assign <id-kvm4-1> -z kvm4-1 -c <measured>G -t kvm4-1
garage layout assign <id-kvm4-2> -z kvm4-2 -c <measured>G -t kvm4-2
garage layout show                                 # read before applying
garage layout apply --version 1
garage bucket create juicefs
(umask 077; garage key create juicefs-pmoves-media > "$INTAKE")   # hazard, §1.6
garage bucket allow --read --write juicefs --key juicefs-pmoves-media
```

**Gate A:**
- `garage status` shows 3 HEALTHY nodes and 3 zones, with the layout at version 1.
- `garage bucket info juicefs` lists the key with RW.
- Functional test from Knuckles **inside `pmoves_data`**, which also proves MagicDNS resolution:
  ```bash
  jfs 'juicefs objbench --storage s3 --access-key "$DST_AK" --secret-key "$DST_SK" http://<ENDPOINT>:3900/juicefs'
  ```
  Every functional test must pass, **including list** (the #3199 failure mode).
- **Sync URL parse proven before pass 1.** A dry run with the exact Step (b) URLs lists both sides and copies nothing:
  ```bash
  jfs 'juicefs sync --dry --no-https "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" "minio://$DST_AK:$DST_SK@<ENDPOINT>:3900/juicefs/pmoves-media/"'
  ```
  It must exit 0 and report the MinIO keys as pending copies. A `NoSuchBucket` error naming the host means the URL was parsed virtual-host style (P1-2 of the #3200 review). STOP.
- **External port probe (§1.3, required):** 3900, 3901 and 3903 are refused or time out on every KVM's public address, probed from a host outside the tailnet. All three ports on all three nodes; one open port fails Gate A.

### Step (b): Copy MinIO → Garage (volume stays live on MinIO)

```bash
# pass 1: live, throttled. Incremental on re-run, NOT resumable (see below)
jfs 'juicefs sync --no-https --threads 8 --bwlimit <Mbps> \
     "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" \
     "minio://$DST_AK:$DST_SK@<ENDPOINT>:3900/juicefs/pmoves-media/"'
# pass 2 (still before the freeze): re-read and checksum every object on both sides
jfs 'juicefs sync --no-https --check-all --threads 8 "minio://...same src..." "minio://...same dst..."'
```

- **No checkpoint flag.** `--enable-checkpoint` does not exist in the pinned `juicedata/mount:ce-v1.3.0`; it first appears in v1.4.x (v1.4.1 `cmd/sync.go:241`). An interrupted pass 1 is simply re-run. Sync skips keys that already exist on the destination with a matching size, so a re-run re-lists both sides and copies only what is missing or differs. It does not resume mid-object and it re-pays the listing cost. The image is not bumped to v1.4.x for this one flag: every other step, and the live mount, run on ce-v1.3.0.
- **Scheme for the Garage side is `minio://`, never `s3://`.** For `s3://` URLs, JuiceFS sync's `isS3PathType` treats only localhost, IPv4 literals and AWS hosts as path-style. For any other host, such as a MagicDNS name like `pmoves-kvm4-1`, it takes the bucket from the hostname, and every request goes to the wrong bucket. `minio://` is always path-style.
- **`--no-https` on every sync.** Both endpoints are plain HTTP: MinIO on `pmoves_data`, and Garage's S3 port, which has no TLS (§1.4). The flag applies to both sides of the call. Whether sync would fall back to HTTP by itself for an `s3://` endpoint (`supportHTTPS`) is **COULD-NOT-MEASURE**; the plan does not depend on it.
- The `juicefs config --bucket http://<ENDPOINT>:3900/juicefs` form in c3 and §1.4 is a different parser (the object-store URL of a formatted volume, path-style for non-AWS endpoints). It is correct as written.

**Gate B:**
- Pass 2 (`--check-all`) reports **0 failed**. This full verification runs here, before the freeze, never inside it.
- Object count and bytes in `garage bucket info juicefs` are ≥ the Step 0 figures.
- `garage stats` shows no resync backlog.
- `--delete-src` and `--delete-dst` are never used.

### Step (c): Cutover with a short write freeze

| # | Action | Gate |
|---|---|---|
| c1 | Stop every writer: `juicefs-mount` on each mounting node, plus any gateway on `pmoves-media` | `jfs 'juicefs status "$META"'` shows no active Sessions |
| c2 | Final delta only: `jfs 'juicefs sync --no-https --check-new --threads 8 "minio://...same src..." "minio://...same dst..."'`. `--check-new` checksums only the objects it copies now; everything else was verified by Gate B's `--check-all`. **Never `--check-all` inside the freeze**: it re-reads every object on both sides | 0 failed |
| c3 | Switch (`juicefs config` put/get/deletes a `testing/` object; do **not** pass `--force`): `jfs 'juicefs config "$META" --storage s3 --bucket http://<ENDPOINT>:3900/juicefs --access-key "$DST_AK" --secret-key "$DST_SK" --yes'` | exit 0 |
| c4 | `jfs 'juicefs status "$META"'`, then `jfs 'juicefs fsck "$META"'` | `Storage: s3`, the Garage bucket URL, fsck exit 0 and 0 missing blocks |
| c5 | Remount: `make -C pmoves juicefs-mount-local JUICEFS_DATA_DIR=/mnt/pmoves-nvme1/juicefs-data`, then `make -C pmoves juicefs-mount-status` | Mount up; content dirs listed |
| c6 | Verify data | The 3 sample `sha256sum`s match Step 0. A write, `sync`, read-back works. `juicefs gc` (no `--delete`) reports **non-zero** scanned objects; zero is the #3199 false-clean signature |

**Freeze length** = the c2 delta (a full listing of both sides, plus a copy of whatever was written since Gate B) + c3-c5. The listing cost scales with object count, which Step 0 records. So the freeze is **COULD-NOT-MEASURE** until Step 0 runs. Pass 1 and the `--check-all` pass stay **outside** the freeze. Run Gate B as close to the window as practical, so the delta is small.

### Step (d): Rollback (MinIO's `juicefs` bucket is never modified after Step 0)

```bash
# freeze as in c1, then carry back anything written since cutover (no deletes):
jfs 'juicefs sync --no-https --check-new "minio://...garage...@<ENDPOINT>:3900/juicefs/pmoves-media/" "minio://...minio...@minio:9000/juicefs/pmoves-media/"'
jfs 'juicefs config "$META" --storage minio --bucket http://minio:9000/juicefs --access-key "$SRC_AK" --secret-key "$SRC_SK" --yes'
jfs 'juicefs fsck "$META"'
```

**Gate D:** `Storage: minio`, fsck is clean, and after remount the write/read test passes.

**Precondition for the whole soak:** MinIO stays running and the `-src` image stays present, because the #3192 `up-minio` pre-check refuses to start without it.

### Step (e): Soak, then retire MinIO's `juicefs` role

| Phase | Action | Gate |
|---|---|---|
| Soak, N days (**D4**) | Daily `juicefs fsck` (read-only), `garage status`, `garage stats`. Stop one KVM once, deliberately | 0 fsck errors. 3 healthy nodes. Reads **and writes** continue with one node down (RF=3) |
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

- **KVM↔KVM RTT:** COULD-NOT-MEASURE from Knuckles.
- **Throughput:** COULD-NOT-MEASURE (no SSH). Operator commands, one-shot and leaving nothing persistent:

```bash
# on a KVM:          iperf3 -s -1
# on Knuckles:       iperf3 -c pmoves-kvm4-1 -t 20 ; iperf3 -c pmoves-kvm4-1 -t 20 -R
# without iperf3:    dd if=/dev/zero bs=1M count=256 | ssh <user>@pmoves-kvm4-1 'cat >/dev/null'
# on each KVM, KVM<->KVM RTT:  tailscale ping -c 3 pmoves-kvm2 ; tailscale ping -c 3 pmoves-kvm4-1 ; tailscale ping -c 3 pmoves-kvm4-2
```

**Estimate:** 85 GB = 680,000 Mbit. It crosses Knuckles' uplink **once**; Garage then replicates KVM↔KVM.

| Sustained link | Pass 1 (Knuckles uplink → endpoint KVM) | Each `--check-all` pass (endpoint KVM egress → Knuckles) |
|---|---|---|
| 10 Mbit/s | ~18.9 h | ~18.9 h |
| 50 Mbit/s | ~3.8 h | ~3.8 h |
| 100 Mbit/s | ~1.9 h | ~1.9 h |
| 500 Mbit/s | ~23 min | ~23 min |

- **`--check-all` is not free.** It re-reads every object on both sides. The MinIO side is local. The Garage side is ~85 GB of **egress from the endpoint KVM** back to Knuckles per pass.
- **Budget two `--check-all` passes:** Gate B's pass 2, plus one re-run if pass 2 is interrupted or reports failures. That is ~85 GB of extra KVM egress each, about 1.9 h each at 100 Mbit/s. The c2 delta (`--check-new`) re-reads only what it copies.
- **KVM traffic, total:** ~85 GB inbound to the endpoint node, ~170 GB of replication between KVMs, and ~85-170 GB of check-all egress. That is small against the 8-16 TB monthly caps.
- **Wall clock before the freeze** ≈ pass 1 + one or two check-all passes. At 100 Mbit/s that is ~3.8-5.7 h. None of it is inside the freeze.

## 4. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Metadata stays on Knuckles (D1 not taken) | Knuckles down means KVM Jellyfin down too. This is the inverse of §0.8 | Take D1 next. Do not call KVM viewing highly available until then |
| Asymmetric availability (accepted, §0.8) | Region or VPS down: the lab loses `pmoves-media` entirely. It fails; it does not degrade (§0.6) | Accepted. The cache helps bandwidth, not availability |
| KVM disk | RF=3 needs a full copy per node. kvm2 is 100 GB **total** (Hostinger REST, 2026-09-27), and it has CI-runner pressure. The kvm4s are 200 GB total each. Snapshots need up to 4× metadata size | RF=3 as specified is **infeasible** (§1.1 D3). The operator chooses (a) KVM 8 upgrade, (b) RF=2 on the kvm4s, or (c) add a disk-bearing node, before G1 |
| kvm4-2 over-subscribed | OOM kills Garage | Resolve per its profile before G3 |
| Egress / uplink | Pass 1 saturates Knuckles' uplink. Each `--check-all` pass costs ~85 GB of endpoint-KVM egress | `--bwlimit`, off-hours. An interrupted pass is re-run (incremental by size, not resumable). `--check-all` only outside the freeze |
| Single S3 endpoint (D2) | Endpoint KVM down: S3 API down even though Garage has quorum | Metadata-only `juicefs config --bucket` failover |
| MagicDNS inside Docker bridge networks | The mount can't resolve `<ENDPOINT>`: the same lists-then-fails shape as §0.2 | Gate A runs objbench inside `pmoves_data` |
| Credential funnel | Truncated or mis-shaped key (the E2B precedent). A secret printed into a transcript | Shape checks (§1.6). `key create` output goes to the intake file only. Complete the 4-place route |
| Keys stored in metadata | Anyone with `juicefs_meta` read access has the Garage key | Bucket-scoped key, no owner rights. Rotate with `juicefs config --access-key/--secret-key` |
| `.env`-based guards | Node shape lives in gitignored `pmoves/.env.local`: `JUICEFS_NAME=pmoves-media`, `JUICEFS_NETWORK=pmoves_data` (there only so the mount resolves `minio`), `META_ROLE`, `DATA_DIR`. An empty exported shell var shadows the env files | Re-decide `JUICEFS_NETWORK` after cutover: metadata needs `supabase-db`, Garage needs MagicDNS. Verify with `env -u` |
| Cross-node preflight gap | `juicefs-cross-node-setup.sh` refuses only `Storage: file` and never checks that the bucket URL resolves | Follow-up (parent §0.7): a bucket-URL reachability check |
| Garage version drift | Mixed versions in the cluster | Digest pin. Upgrade per Garage `operations/upgrading.md` |

## 5. Rollout gates and Known Road grants

| Gate | Condition | Owner |
|---|---|---|
| **D1** | Metadata engine decided (§2). This is the first gate; it sets the order of everything else | operator |
| G0 | This plan merged. The #3192 bridge live, so MinIO is readable. Step 0 baseline recorded | operator |
| G1 | D3 decided (§1.1: option a, b or c). Free space after the OS measured on every storage node (the peer shell survey is pending), with ≥ 2× the data free on each | operator |
| G2 | D2-D6 decided. Funnel labels (§1.6) delivered and shape-checked | operator |
| G3 | Garage up. Gate A passed, including list, the MagicDNS-in-container check, the `--dry` sync parse check, and the **external probe of 3900/3901/3903** on every KVM (OPEN — OPERATOR) | delivery + operator |
| G4 | Gate B passed: `--check-all`, 0 failed | delivery |
| G5 | Cutover window agreed. Step (c) gates passed | operator |
| G6 | N-day soak passed, including the node-down test. MinIO's `juicefs` role retired | operator |

**Known Road grants needed later.** Check each path first with `python3 .claude/skills/known-roads/roads.py check <path>`.

| Change | Road |
|---|---|
| New Garage compose file for the KVMs; any `pmoves/docker-compose*.yml` or overlay edit | `compose:pr:<N>` |
| Funnel manifests and `.github/workflows/sync-secrets-local.yml` | funnel road, per path check |
| `pmoves/mk/egress.mk` or the `JUICEFS_NETWORK` handling for the post-cutover mount | per path check |
| `juicefs config` on the live volume; stopping mounts; KVM firewall | operator action, not an agent action |

### Open operator decisions

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Metadata engine (§2). **First gate** | B, replicated Postgres on the KVMs, as its own plan after §3 |
| D2 | Which KVM serves the recorded bucket URL | The largest healthy node with the lowest measured RTT. Fail over with `juicefs config --bucket`. Not per-client Garage gateways, which would spread `rpc_secret` to every lab node |
| D3 | Capacity: RF=3 as specified is **infeasible** on 100/200/200 GB total disk (§1.1) | **OPEN — OPERATOR.** Options (a) KVM 8 upgrade (kvm2 only or all three), (b) RF=2 on the two kvm4s (read-only while one is down), (c) add a disk-bearing node such as Knuckles or the 5090. No recommendation made |
| D4 | Soak length N | ≥ 14 days, including one deliberate node-down |
| D5 | Garage ports tailnet-only | Yes: `tailscale0` only, S3/admin bound to the tailnet address (§1.3). The external probe is a required gate; who runs it is **OPEN — OPERATOR** |
| D6 | Known Road grants for the compose, funnel and egress edits | Grant per PR, as in the table above |
