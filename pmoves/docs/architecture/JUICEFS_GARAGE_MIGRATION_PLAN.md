# JuiceFS `pmoves-media`: Garage migration plan and runbook

**Status:** PLAN ONLY (2026-09-26). Nothing here has been executed. Every step in §3 is operator-gated.
**Lane:** `feat/juicefs-garage-migration`, owner B850-CLAUDE-FUNNEL (Knuckles), register PR #3198.
**Replaces:** the interim MinIO bridge (PR #3192, `pmoves/docker/minio-src/README.md`).
**Decided upstream:** `JUICEFS_OBJECT_STORE_MIGRATION.md` §0.8: Garage, self-hosted on the KVMs. Asymmetric availability accepted.
**Why not Supabase S3:** PR #3199, §12 of the same doc. JuiceFS cannot LIST through storage-api, so `gc`, `fsck` and `destroy` see nothing.

## 0. Scope

| In scope | Out of scope |
|---|---|
| Move the **object data** of JuiceFS `pmoves-media` from MinIO bucket `juicefs` to a Garage bucket on the 3 KVMs | The metadata engine move. It is an input here (§2, gate D1) and gets its own plan |
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

## 1. Target topology

### 1.1 Nodes

| Node | Garage zone | Capacity (`-c`) | vCPU / RAM | Monthly BW cap | Note |
|---|---|---|---|---|---|
| `pmoves-kvm2` | `kvm2` | **COULD-NOT-MEASURE** | 2 / 8 GB | 8 TB | Recorded disk values conflict: 100, 200 or 400 GB. Hosts a CI runner with recurring disk pressure |
| `pmoves-kvm4-1` | `kvm4-1` | **COULD-NOT-MEASURE** | 4 / 16 GB | 16 TB | Recorded disk: 200 or 400 GB |
| `pmoves-kvm4-2` | `kvm4-2` | **COULD-NOT-MEASURE** | 4 / 16 GB | 16 TB | Profile says it is **over-subscribed**: "resolve before adding data-plane services here" |

- vCPU, RAM and bandwidth caps are Hostinger-reported, from `pilots/fordham-hill/06-pilot-observation.md`.
- Conflicting disk records: `research/KVM_HOSTINGER_NETWORK_REPORT.md`, `docs/architecture/kvm-exit-node-hosting-strategy.md`, `pmoves/docs/context/Visionary AI_ Global Network, Local Power.md`.
- **Why capacity is unmeasured:** Tailscale SSH from Knuckles was refused ("tailnet policy does not permit you to SSH as user pmoves-knuckles" on kvm2/kvm4-1, "Host key verification failed" on kvm4-2). No other user was tried.

**Operator measurement (read-only), on each KVM:**
```bash
df -hT / /var/lib 2>/dev/null; lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT; free -g; docker system df
```

**Zones:** one zone per node. The Hostinger report places all three in one region (US-East), so the zones are node-level failure domains, not site-level. A regional outage takes all three. That is the §0.6 "VPS down" case, which §0.8 accepted.

### 1.2 Replication factor: **3**

Quorums are from Garage v2.4.1 `reference-manual/configuration.md`:

| `replication_factor` (consistent mode) | Write / read quorum | One KVM down | Usable capacity (3 nodes) |
|---|---|---|---|
| 2 | 2 / 1 | **read-only** (writes fail) | ~1.5 × node size |
| **3** | 2 / 2 | **reads and writes continue** | = smallest node's `-c` |

- RF=3 is the only setting that meets "no single node offline stops operators" for writes.
- The cost is that each KVM holds a **full copy**: ~85 GB + growth + Garage metadata + snapshots.
- RF cannot be changed safely later (Garage docs: it needs a layout rebuild and full rebalance), so choose it once.
- Keep `consistency_mode = "consistent"`.

### 1.3 `garage.toml` (same on all 3; no secret values in the file)

```toml
replication_factor = 3
consistency_mode   = "consistent"
metadata_dir       = "/var/lib/garage/meta"
data_dir           = "/var/lib/garage/data"
db_engine          = "lmdb"
metadata_auto_snapshot_interval = "6h"
metadata_snapshots_dir = "/var/lib/garage/data/snapshots"   # snapshots need up to 4x meta size

rpc_bind_addr   = "[::]:3901"
rpc_public_addr = "<this node's tailnet address, rendered at deploy>:3901"
rpc_secret_file = "/run/secrets/garage_rpc_secret"

[s3_api]
api_bind_addr = "[::]:3900"
s3_region     = "us-east-1"          # see 1.4: matches JuiceFS's default region

[admin]
api_bind_addr      = "[::]:3903"
admin_token_file   = "/run/secrets/garage_admin_token"
metrics_token_file = "/run/secrets/garage_metrics_token"
```

- **Image:** `dxflrs/garage:v2.4.1` (latest, 2026-09-08). Pin it by digest at deploy time, per F-07.
- **Network:** host networking, per Garage's `cookbook/real-world.md`.
- **Firewall (required, because the KVMs are public exit nodes):** allow 3900/3901/3903 on `tailscale0` only.
- **Firewall gate:** from outside the tailnet, `nc -zv <public addr> 3900` is refused.

### 1.4 S3 endpoint as JuiceFS sees it

| Setting | Value | Why |
|---|---|---|
| `--storage` | `s3` | Garage is a generic S3 target |
| `--bucket` | `http://<ENDPOINT_KVM>:3900/juicefs` | Path-style. JuiceFS uses path-style for non-AWS endpoints by default (`defaultPathStyle()`, `JFS_S3_VHOST_STYLE` unset) |
| Region | Garage `s3_region = "us-east-1"` | Garage rejects any other region with `AuthorizationHeaderMalformed` (`src/api/common/signature/payload.rs:415`). JuiceFS sends `AWS_REGION`, else `us-east-1`. Matching on the server removes a per-client env var that every mount node would otherwise need. Alternative: keep `garage` and set `AWS_REGION=garage` on every client |
| TLS | none on the S3 port. Tailnet transport only | Garage's S3 API has no TLS |
| `<ENDPOINT_KVM>` | **Operator decision D2** | The bucket URL is recorded in metadata and must resolve identically on **every** client (parent §0.2) |

- **Endpoint failover** is metadata-only: `juicefs config "$META" --bucket http://<other-kvm>:3900/juicefs`.
- **Unverified:** whether containers on a Docker bridge network (`pmoves_data`) resolve MagicDNS names. Gate A tests this.

### 1.5 Names

| Object | Name | Note |
|---|---|---|
| Bucket | `juicefs` | Same as MinIO, so the object keys (`pmoves-media/...`) copy 1:1 |
| Key | `juicefs-pmoves-media` | Allowed on bucket `juicefs` only: `--read --write`. No `--owner`, no `--create-bucket` |
| Admin | `admin_token_file` | Never given to JuiceFS |

### 1.6 Secrets funnel (labels only; values never in git, argv logs or transcripts)

| CHIT label | Delivered to | Shape (validate at delivery, not just presence) |
|---|---|---|
| `GARAGE_RPC_SECRET` | 3 KVMs, docker secret `garage_rpc_secret` | 64 hex |
| `GARAGE_ADMIN_TOKEN` | 3 KVMs + operator | base64 of 32 bytes |
| `GARAGE_METRICS_TOKEN` | 3 KVMs + Prometheus | base64 of 32 bytes |
| `JUICEFS_GARAGE_ACCESS_KEY` | the migration context only | `GK` + 24 hex (26 chars) |
| `JUICEFS_GARAGE_SECRET_KEY` | the migration context only | 64 hex |

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
| `juicefs config --secret-key` | Does not read `SECRET_KEY` from env (v1.3.0 `cmd/config.go`), so the secret is on argv | Pass it via `-e` into a `--rm` container and expand it inside `sh -c`. It is then only in the container's argv for seconds, not in `docker inspect` or shell history |
| `juicefs sync minio://USER:PASS@...` | Credentials in the URL (argv) | Same `-e` plus in-container expansion. URL-encode `/` as `%2F` |

## 2. Metadata engine: decision input (**D1, the first operator gate**)

The data move (§3) and the metadata move are **orthogonal**:
- `juicefs dump | load` does not touch objects.
- `juicefs config --storage` does not touch the file tree.

**Availability is decided by where metadata lives:**

| Metadata at | Knuckles down | KVMs down | Matches §0.8? |
|---|---|---|---|
| Supabase PG on Knuckles (today) | **Everyone** loses `pmoves-media`, including KVM Jellyfin | Everyone loses it (no object store) | **No.** This is the inverse of the accepted asymmetry |
| Replicated PG on the KVMs | KVM Jellyfin keeps working | Lab loses it (accepted) | **Yes** |

| Criterion | A. Keep Supabase PG (Knuckles) | **B. Replicated PG on KVMs** (evaluate first, per §0.5) | C. TiKV / etcd |
|---|---|---|---|
| Engine migration | none | none (still Postgres) | yes, new engine |
| Metadata move | none | `juicefs dump --binary` → `juicefs load`, with a write freeze (dump has no snapshot consistency; secrets are omitted unless `--keep-secret-key`) | same |
| HA | none (single `supabase-db`) | Primary + streaming standby: Patroni + etcd on the 3 KVMs, or repmgr with manual promote | native |
| One writable endpoint | n/a | pgx multi-host DSN with `target_session_attrs=read-write`: **COULD-NOT-MEASURE** whether JuiceFS's URL handling passes it through (JuiceFS 1.3 uses pgx v5.7.3). Test in a sandbox. Fallback: HAProxy or a VIP | native |
| KVM RAM | 0 | PG ~1-2 GB per node. kvm4-2 is over-subscribed; kvm2 has 8 GB | TiKV is heavy on 8-16 GB nodes |
| Coupling | Shares `supabase-db` with the app | Dedicated | Dedicated |
| Remote mounts | Need `supabase-db` tailnet exposure (PR #2728, which points at Knuckles) | KVM tailnet endpoint | KVM endpoint |

**Recommendation:** B.
- Run it as its own plan, after §3, so each change has its own rollback.
- If B is chosen, do not merge PR #2728 on momentum.

**This is an operator decision.**

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
  jfs 'juicefs objbench --storage s3 --access-key "$DST_AK" --secret-key "$DST_SK" http://<ENDPOINT_KVM>:3900/juicefs'
  ```
  Every functional test must pass, **including list** (the #3199 failure mode).
- **Sync URL parse proven before pass 1.** A dry run with the exact Step (b) URLs lists both sides and copies nothing:
  ```bash
  jfs 'juicefs sync --dry --no-https "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" "minio://$DST_AK:$DST_SK@<ENDPOINT_KVM>:3900/juicefs/pmoves-media/"'
  ```
  It must exit 0 and report the MinIO keys as pending copies. A `NoSuchBucket` error naming the host means the URL was parsed virtual-host style (P1-2 of the #3200 review). STOP.
- 3900/3901/3903 are closed on the public interfaces.

### Step (b): Copy MinIO → Garage (volume stays live on MinIO)

```bash
# pass 1: live, throttled. Incremental on re-run, NOT resumable (see below)
jfs 'juicefs sync --no-https --threads 8 --bwlimit <Mbps> \
     "minio://$SRC_AK:$SRC_SK@minio:9000/juicefs/pmoves-media/" \
     "minio://$DST_AK:$DST_SK@<ENDPOINT_KVM>:3900/juicefs/pmoves-media/"'
# pass 2 (still before the freeze): re-read and checksum every object on both sides
jfs 'juicefs sync --no-https --check-all --threads 8 "minio://...same src..." "minio://...same dst..."'
```

- **No checkpoint flag.** `--enable-checkpoint` does not exist in the pinned `juicedata/mount:ce-v1.3.0`; it first appears in v1.4.x (v1.4.1 `cmd/sync.go:241`). An interrupted pass 1 is simply re-run. Sync skips keys that already exist on the destination with a matching size, so a re-run re-lists both sides and copies only what is missing or differs. It does not resume mid-object and it re-pays the listing cost. The image is not bumped to v1.4.x for this one flag: every other step, and the live mount, run on ce-v1.3.0.
- **Scheme for the Garage side is `minio://`, never `s3://`.** For `s3://` URLs, JuiceFS sync's `isS3PathType` treats only localhost, IPv4 literals and AWS hosts as path-style. For any other host, such as a MagicDNS name like `pmoves-kvm4-1`, it takes the bucket from the hostname, and every request goes to the wrong bucket. `minio://` is always path-style.
- **`--no-https` on every sync.** Both endpoints are plain HTTP: MinIO on `pmoves_data`, and Garage's S3 port, which has no TLS (§1.4). The flag applies to both sides of the call. Whether sync would fall back to HTTP by itself for an `s3://` endpoint (`supportHTTPS`) is **COULD-NOT-MEASURE**; the plan does not depend on it.
- The `juicefs config --bucket http://<ENDPOINT_KVM>:3900/juicefs` form in c3 and §1.4 is a different parser (the object-store URL of a formatted volume, path-style for non-AWS endpoints). It is correct as written.

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
| c3 | Switch (`juicefs config` put/get/deletes a `testing/` object; do **not** pass `--force`): `jfs 'juicefs config "$META" --storage s3 --bucket http://<ENDPOINT_KVM>:3900/juicefs --access-key "$DST_AK" --secret-key "$DST_SK" --yes'` | exit 0 |
| c4 | `jfs 'juicefs status "$META"'`, then `jfs 'juicefs fsck "$META"'` | `Storage: s3`, the Garage bucket URL, fsck exit 0 and 0 missing blocks |
| c5 | Remount: `make -C pmoves juicefs-mount-local JUICEFS_DATA_DIR=/mnt/pmoves-nvme1/juicefs-data`, then `make -C pmoves juicefs-mount-status` | Mount up; content dirs listed |
| c6 | Verify data | The 3 sample `sha256sum`s match Step 0. A write, `sync`, read-back works. `juicefs gc` (no `--delete`) reports **non-zero** scanned objects; zero is the #3199 false-clean signature |

**Freeze length** = the c2 delta (a full listing of both sides, plus a copy of whatever was written since Gate B) + c3-c5. The listing cost scales with object count, which Step 0 records. So the freeze is **COULD-NOT-MEASURE** until Step 0 runs. Pass 1 and the `--check-all` pass stay **outside** the freeze. Run Gate B as close to the window as practical, so the delta is small.

### Step (d): Rollback (MinIO's `juicefs` bucket is never modified after Step 0)

```bash
# freeze as in c1, then carry back anything written since cutover (no deletes):
jfs 'juicefs sync --no-https --check-new "minio://...garage...@<ENDPOINT_KVM>:3900/juicefs/pmoves-media/" "minio://...minio...@minio:9000/juicefs/pmoves-media/"'
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
| KVM disk | RF=3 needs a full copy per node. kvm2 may be 100 GB with CI-runner pressure. Snapshots need up to 4× metadata size | G1: measured free space ≥ 2× the data on every node. If kvm2 fails G1, **re-decide RF (D3)** before building |
| kvm4-2 over-subscribed | OOM kills Garage | Resolve per its profile before G3 |
| Egress / uplink | Pass 1 saturates Knuckles' uplink. Each `--check-all` pass costs ~85 GB of endpoint-KVM egress | `--bwlimit`, off-hours. An interrupted pass is re-run (incremental by size, not resumable). `--check-all` only outside the freeze |
| Single S3 endpoint (D2) | Endpoint KVM down: S3 API down even though Garage has quorum | Metadata-only `juicefs config --bucket` failover |
| MagicDNS inside Docker bridge networks | The mount can't resolve `<ENDPOINT_KVM>`: the same lists-then-fails shape as §0.2 | Gate A runs objbench inside `pmoves_data` |
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
| G1 | KVM capacity measured (§1.1) with ≥ 2× the data free on each storage node | operator |
| G2 | D2-D6 decided. Funnel labels (§1.6) delivered and shape-checked | operator |
| G3 | Garage up. Gate A passed, including list and the MagicDNS-in-container check | delivery + operator |
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
| D3 | Capacity and headroom per KVM; whether kvm2 stores data | Measure first (§1.1). RF=3 needs all 3 nodes storing |
| D4 | Soak length N | ≥ 14 days, including one deliberate node-down |
| D5 | Garage ports tailnet-only | Yes: `tailscale0` only |
| D6 | Known Road grants for the compose, funnel and egress edits | Grant per PR, as in the table above |
