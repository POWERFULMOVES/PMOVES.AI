# JuiceFS Object-Store Migration (replace EOL MinIO)

**Status:** Design spec (2026-06-22), **REOPENED 2026-08-24** — see §0. Build deferred; the §4.1 "confirmed" choices are no longer confirmed. **Owner lane:** Z890-CLAUDE (#10 JuiceFS↔MinIO).
**Interim:** PR #1862 repins MinIO (both `docker-compose.yml` and the generated split `docker-compose.core.yml`) to its last real community tag. **Until #1862 merges, a normal bring-up still pulls the broken `RELEASE.2025-12-20…` tag and the data profile cannot start** — this spec does not by itself restore the data tier.
**Related:** `project_supabase_multinode_juicefs_vision` (multi-node dual-write vision), `CAPABILITY_ADAPTIVE_STANDALONE.md` (the data tier this storage layer sits in).

## 0. REVISION 2026-08-24 — both "confirmed" choices reopened

**Status change: the §4.1 choices marked "confirmed" are REOPENED.** Not because
they were badly reasoned — both were correct for the requirement as stated in
June — but because the requirement changed and two facts landed since.

**The new requirement (operator, 2026-08-24):** Jellyfin, PMOVES.YT and media are
to be **hosted on the KVMs**, which is also where egress lives to bypass a slow
local uplink. Local nodes keep working during a VPS outage. No single node
offline should stop operators viewing. That is a *placement and availability*
requirement; §4.1 chose for a single-node stack.

### 0.1 What is actually deployed today (measured, not assumed)

The spec says JuiceFS replaces MinIO via `juicefs gateway`. The `pmoves-media`
filesystem instead runs **on top of MinIO**:

```
"Name": "pmoves-media",  "Storage": "minio",
"Bucket": "http://minio:9000/juicefs"
```

Metadata is PostgreSQL on **b850**, and `pmoves-minio-1` also runs on **b850**.
So both halves of the storage layer sit on one workstation, and no VPS is
involved anywhere. "What if b850 is offline" currently answers: every node loses
`pmoves-media`, and Jellyfin loses its library with it.

This is not a contradiction of the spec so much as its Status line playing out —
"Design spec. **Build deferred.**" The gateway that was to *replace* MinIO was
deferred; the `pmoves-media` content mount shipped meanwhile and picked the
deprecated store as its backend. Both are "JuiceFS", which is what makes the
stack read as though MinIO had already been replaced.
(`JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` warns not to conflate the two
deployments; this is what conflating them looks like in practice.)

### 0.2 New fact — the recorded bucket cannot resolve off-host

`http://minio:9000/juicefs` is a **Docker-internal hostname**. The bucket URL is
baked in at format time, so a remote mount reads that string and cannot resolve
it. `docker-compose.juicefs.yml:39` anticipated this — "`JUICEFS_S3_ENDPOINT` =
the tailnet-reachable MinIO endpoint ... so the URL recorded in metadata resolves
from remote nodes too" — but the single-node fallback was used at format time.

**The existing guard does not catch it.** `juicefs-cross-node-setup.sh:73-82`
refuses `Storage: file` (the 2026-08-04 blocker). Ours is `Storage: minio`, so
preflight **passes**, and the mount then fails on open — the exact
"lists correctly, fails on read" failure the guard was written to prevent. Worse:
a remote node running its own container named `minio` would silently bind a
**different object store**. Any fix here must check the bucket *URL*, not just
the storage *type*.

### 0.3 New fact — MinIO CE is archived, not merely EOL

The spec cites "EOL/archived (Feb 2026)". Since then the repository was
**archived read-only in April 2026**: no releases, no reviewed patches, no
official community binaries, and the admin console reduced to a read-only object
browser. The interim last-real-tag pin (#1862) is now a permanently frozen base.

### 0.4 Reopened choice — data backend

| | |
|---|---|
| §4.1 said | **local volume** (`file://` on a hardened named volume), "simplest durable single-node store" |
| Why it no longer holds | It is *explicitly* single-node. It caused the 2026-08-04 cross-node blocker, and the preflight now refuses `Storage: file` outright. It cannot serve KVM-hosted Jellyfin/PMOVES.YT. |
| Candidate | **Garage** — [design goals](https://garagehq.deuxfleurs.fr/documentation/design/goals/): "a lightweight geo-distributed data store ... made for multi-sites (eg. datacenters, offices, households) interconnected through regular Internet connections." That is this fleet's topology stated literally. Simple duplication rather than erasure coding; S3 API only; explicitly does **not** emulate POSIX — which costs nothing here, because JuiceFS supplies POSIX above it. Reference deployments: 9 nodes / 3 sites, 15 nodes / 3 sites. |
| Alternative | **Cloudflare R2** — managed, and CF is already wired into this fleet (tunnels, Pages, DNS-01). Trades self-hosting for egress economics; worth pricing against the KVM uplink the egress requirement exists to exploit. |

### 0.5 Reopened choice — metadata engine

| | |
|---|---|
| §4.1 said | **Postgres** on `supabase-db`, rationale included "supports the multi-node vision" |
| Why it no longer holds | It does not. JuiceFS's [metadata engine docs](https://juicefs.com/docs/community/databases_for_metadata/) discuss **no** replication, failover or HA for PostgreSQL/MySQL, and [PostgreSQL best practices](https://juicefs.com/docs/community/postgresql_best_practices/) states: *"PostgreSQL does not yet support Multi-Shard (Distributed) transactions, do not use a multi-server distributed architecture for the JuiceFS metadata."* Postgres is a correct **single-server** choice and an incorrect HA one. |
| Candidates | **TiKV** — *"It is recommended to use dedicated TiKV 5.0+ cluster as the metadata engine for JuiceFS"*, the only engine the docs push toward a dedicated cluster. **Redis Sentinel/Cluster** — explicitly supported, with the caveat that Cluster pins one filesystem's metadata to a single instance. **etcd** — documented as HA. |
| Migration cost | Bounded, and this is the load-bearing fact: `juicefs dump <old> \| juicefs load <new>`, and **object data is untouched** — no re-upload of the pool. `dump` has no snapshot consistency, so writes must be suspended for the cutover. |

### 0.6 The constraint that cannot be engineered away

The requirement has two directions — *VPS down, lab keeps working* and *node down,
operators keep viewing*. **One strongly-consistent metadata store cannot be
writable on both sides of a partition.** Quorum lives on one side: 2 KVM + 1 local
means losing the KVMs leaves 1/3 and local mounts fail regardless of engine.

What the docs *do* offer is partial, and it is worth being precise rather than
promising symmetry:

- **Reads** — JuiceFS [client cache](https://juicefs.com/docs/community/guide/cache/):
  cached blocks stay readable when the object store is unreachable; uncached
  reads need connectivity. A large `--cache-dir`/`--cache-size` on lab nodes
  turns "VPS down" into "cold data unavailable" rather than "filesystem down".
- **Writes** — `--writeback` persists writes to local cache and uploads
  asynchronously, so writes survive a VPS outage. Documented cost: data loss if
  the cache filesystem fails before upload.

So the honest shape is **asymmetric**: quorum and object storage on the VPS side
(uptime + egress, which is where they are wanted anyway); lab nodes as caching
clients that degrade to cached-reads + buffered-writes during an outage. If true
both-directions availability is required, that needs **two filesystems** with
object-level replication, not one shared metadata store — a materially larger
design, and it should be chosen deliberately rather than discovered.

### 0.7 Consequences for work in flight

- **PR #2728** (Step 4: multi-home `supabase-db` onto `pmoves_external`, publish
  the DB port tailnet-bound) assumes **b850 stays the metadata host**. If
  metadata moves to a KVM, that PR is pointed the wrong way and should not merge
  on momentum. It is not wrong today — it is scoped to a topology under review.
- The `pmoves-media` volume needs a **reformat or a bucket-URL correction**
  regardless of the engine decision; §0.2 blocks every remote mount on its own.
- The cross-node preflight should gain a **bucket-URL reachability check** to
  close the gap in §0.2.

### 0.8 What this revision does NOT decide

Engine and backend are left open on purpose. This section replaces "confirmed"
with the evidence needed to choose, and names the requirement each choice must
now satisfy. §4.1 stays below, unedited, as the record of what was decided in
June and why — the reasoning was sound for a single-node stack and should not be
retconned.

---

## 1. Problem

MinIO Community Edition is **EOL / archived (Feb 2026)** and MinIO **stopped publishing `minio/minio` community images after `RELEASE.2025-09-07`**. The compose was pinned to a phantom `RELEASE.2025-12-20…` tag that 404s on Docker Hub, which broke every data-tier bring-up (found during the capability-adaptive Phase 3 live verify on Z890). PR #1862 repins to the last real tag as a band-aid, but the object store is now on a dead, unmaintained, unpatched base. JuiceFS was always the intended replacement (the "JuiceFS vision") but was **never wired in** — zero references in any compose/Makefile/docs today.

## 2. Goal

Replace the `minio:9000` S3 endpoint with a **maintained, S3-compatible** object store backed by **JuiceFS**, with **minimal consumer churn** (consumers keep talking S3 to the same DNS/endpoint), a **data-migration path** for existing buckets, and a **rollback** during cutover. Set the foundation for the multi-node dual-write storage vision.

## 3. Current MinIO surface (what must keep working)

**S3 consumers** (`MINIO_ENDPOINT=minio:9000`, on `pmoves_data`): `presign`, `pdf-ingest`, `transcribe-backend`, `ffmpeg-whisper`, `media-video`, `media-audio`, `pmoves-yt`, `comfy-watcher` — plus `render-webhook` and `model-registry` (per service comments). 
**Buckets:** `assets`, `outputs` (created by `make brand-defaults`), `pmoves-comfyui` (comfy), YT uses `assets`/`outputs`. 
**Public links:** `comfy-watcher` sets `PUBLIC_BASE_URL=http://minio:9000` → presigned/public URLs embed the endpoint; cutover must rewrite this. 
**Ops:** `make brand-defaults` (`mc mb` bucket create), backup via `mc mirror`. 
**Hardening:** MinIO uses the `*tier-data-hardened` anchor (non-root 65532, read-only, security_opt) — the replacement must too.

## 4. JuiceFS architecture

JuiceFS = a POSIX/object filesystem that splits **metadata** from **data**, plus a built-in **S3 gateway**:

```
S3 consumers ──S3──▶ juicefs-gateway (:9000, S3-compatible)
                          │
            ┌─────────────┴─────────────┐
        metadata engine            data backend
       (Postgres or Redis)     (local volume; later: replicated/object)
```

- **S3 gateway:** `juicefs gateway` serves an S3-compatible API (MinIO-derived gateway code) → **drop-in for `minio:9000`**. Consumers change only the endpoint host (or none, if we keep the service DNS name). **Must start with `--multi-buckets`** — JuiceFS Community Edition's gateway otherwise exposes only a single bucket named after the filesystem; `--multi-buckets` is required to serve the existing `assets`/`outputs`/`pmoves-comfyui` buckets (each becomes a top-level dir in the FS). Also set `--keep-etag` for S3 clients that rely on ETags.
- **Metadata engine:** transactional KV/DB holding the filesystem tree + chunk index.
- **Data backend:** where chunks live.

### 4.1 Component choices (confirmed 2026-06-28 — **metadata engine and data backend REOPENED 2026-08-24, see §0.4/§0.5**)

> Left unedited as the record of the June decision. The S3-gateway and image
> rows still stand; the two rows below them do not.

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Metadata engine | **Postgres** on `supabase-db` (schema `juicefs_meta`) | Operator decision 2026-06-28. Already in the stack; transactional; supports the multi-node vision. The Redis PoC metadata engine has been retired — the compose now defaults to the Postgres DSN. The `juicefs_meta` schema ships in `supabase/initdb/00_2_juicefs_meta_schema.sql`. |
| Data backend | **local volume** initially (`file://` on a hardened named volume) | Simplest durable single-node store; the multi-node dual-write/replicated backend is the follow-on vision. |
| S3 gateway | `juicefs gateway --multi-buckets --keep-etag` on **:9000** | Drop-in endpoint; `--multi-buckets` is REQUIRED on CE to keep the multiple buckets `assets`/`outputs`/`pmoves-comfyui` (else only one FS-named bucket is exposed). |
| Image | pinned `juicedata/juicefs` (or build) per F-07 supply-chain | Maintained, unlike MinIO community. |

## 5. Drop-in strategy (minimal churn)

Two options (pick in review):
1. **Keep the DNS name** — name the gateway service so consumers still resolve `minio:9000` (alias/rename), zero consumer env changes. Lowest churn; slightly confusing naming.
2. **New endpoint var** — introduce `S3_ENDPOINT`/`OBJECT_STORE_ENDPOINT` defaulting to `juicefs-gateway:9000`, repoint each consumer's `MINIO_ENDPOINT`. Cleaner long-term; touches ~10 services.

Recommended: **(2)** with a compatibility default so unmigrated consumers still work, migrate consumers incrementally. `PUBLIC_BASE_URL` (comfy) updates to the gateway endpoint.

## 6. Data migration

For existing data: `mc mirror` (or `rclone`) from the running MinIO (`local/<bucket>`) into the JuiceFS gateway buckets, per bucket (`assets`, `outputs`, `pmoves-comfyui`). On fresh nodes (no MinIO data) just (re)create buckets via the existing `brand-defaults` flow pointed at the gateway. Verify object counts/sizes before flipping consumers.

## 7. Dependency ordering & hardening

Bring-up order: **supabase-db (healthy) → juicefs format (one-time, retry loop) → juicefs-gateway (healthy) → S3 consumers**. The `juicefs-format` service has a built-in 15-retry wait loop (2s interval) for Postgres readiness. `make up-juicefs` pre-checks that `supabase-db` is running. Apply the `*tier-data-hardened` anchor to the gateway, mirroring MinIO.

## 8. Rollback

Keep MinIO (last-real-tag pin from #1862) **available behind a profile/flag** through cutover. If the gateway misbehaves, repoint `*_ENDPOINT` back to `minio:9000`. Only remove MinIO after the gateway is validated across all consumers + a backup cycle.

## 9. Phased plan

- **Phase 1 — PoC:** add `juicefs-gateway` + metadata engine to compose (hardened, pinned, dep-ordered); format the FS; create `assets`/`outputs`; repoint **one** consumer (`presign`) via the new endpoint var; verify put/get + presigned URL.
- **Phase 2 — migrate consumers:** repoint the remaining S3 consumers + `PUBLIC_BASE_URL`; update `brand-defaults` bucket creation to target the gateway; keep MinIO as fallback.
- **Phase 3 — data + cutover:** `mc mirror` existing buckets into JuiceFS; validate; flip defaults to the gateway; MinIO behind a disabled profile.
- **Phase 4 — decommission + multi-node:** remove MinIO; design the replicated/dual-write backend for the multi-node vision.

## 10. Verification

- PoC: `presign` issues working URLs against the gateway; `mc ls`/S3 SDK put/get round-trips.
- Per-phase: each repointed consumer's health + a functional object op.
- Cutover: object parity (counts/sizes) MinIO vs JuiceFS; all consumers green on `service_health_check`.

## 11. Open questions (resolve in review)

- ~~Metadata engine: dedicated Postgres DB vs Redis vs reuse `supabase-db` (blast-radius/coupling).~~ **Resolved 2026-06-28: Postgres on `supabase-db`, schema `juicefs_meta` (namespaced, no coupling to app schemas). Redis PoC retired.**
- Backend durability single-node now vs jumping to a replicated backend for multi-node.
- Naming: keep `minio:9000` DNS (drop-in) vs new `juicefs-gateway` endpoint var.
- Presigned-URL semantics parity (expiry, signature) between MinIO and the JuiceFS gateway.
- Capacity/quota + backup cadence for the JuiceFS volume.
