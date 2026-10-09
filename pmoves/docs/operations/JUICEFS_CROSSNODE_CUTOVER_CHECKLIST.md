# JuiceFS cross-node cutover — back Jellyfin with the shared FS (turnkey checklist)

**Goal (DARKXSIDE, 2026-08-22):** back Jellyfin (`media.pmoves.ai`) with the **cross-node
shared `pmoves-media`** filesystem (mesh vision), mounted on 5090 + all fleet nodes +
Windows/RustDesk; reachable from mobile via Jellyfin (not a native FS mount). The same shared
FS is the **cross-node file-mover** and — with Tailscale identity — part of skipping GitHub as
PII enters. Memory: `project_juicefs_jellyfin_crossnode_lane`.

This sequences the existing docs into one ordered runbook and marks each step **[operator]** or
**[agent]**. Sources: `juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md` (the blocker
+ order), `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` (pmoves-media is MinIO-backed),
`JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md` (the mount).

## Which JuiceFS (don't conflate)
`pmoves-media` = the cross-node POSIX FS for Jellyfin content (Postgres metadata home on B850,
MinIO-backed on z890). The `pmoves-juicefs-gateway-1` running on the 5090 is the **other**
deployment (S3 gateway: assets/outputs) — not this one.

## Current state (measured 2026-08-22)
- pmoves-media storage backend = MinIO (the old file:// blocker is resolved).
- Jellyfin `/media` binds `${JELLYFIN_MEDIA_DIR:-./data/jellyfin/media}` — a **5090-local dir**,
  NOT the shared FS yet.
- **Blocker:** remote nodes can't reach B850's `supabase-db:5432` — it sits on `internal:true`
  networks, so the published port is recorded but never plumbed (same trap NATS hit at
  `docker-compose.yml:2906`).
- The cross-node DSN still authenticates as the full superuser `supabase_admin` (exposed in
  `ps`/`docker inspect` for 11+ days, un-rotated).

## The ordered cutover

### 1. [operator] Apply the scoped `juicefs_meta` role
SQL is committed (`supabase/initdb/00_3_juicefs_meta_role.sql`, seed-placement fixed in #2614).
Grants DML on the `juicefs_meta` schema only; created `NOLOGIN`.
```
# operator sets the Known Road, then applies via the canonical path (NOT supa-migrate):
KNOWN_ROAD=migrations:handoff:pmoves/docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md \
  make -C pmoves supabase-bootstrap
```
Verify: role exists, `rolsuper=false rolcanlogin=false createrole=false`,
`has_schema_privilege('juicefs_meta','juicefs_meta','USAGE')=true`, `...'CREATE')=false`.
Then **revoke the PUBLIC-inherited grants** before step 2 grants LOGIN (see the handoff's
verification note).

### 2. [operator] Grant the role LOGIN + cut the mount over
Grant `LOGIN` with a **pipeline-delivered** password (CHIT funnel, never hand-edit env.shared),
then re-point the mount to the scoped role — this PR makes that a parameter:
```
META_ROLE=juicefs_meta DB_PASS=<juicefs_meta pw, from pipeline> \
  make -C pmoves juicefs-cross-node-setup JUICEFS_HOST=pmoves-b850-ai-top
```
**Verify a real read** through the new credential (open a file, not just `ls`).

### 3. [operator] Rotate `supabase_admin`
Operator action, CHIT voice pipeline. Rotation is AFTER the cutover is verified (step 2), never
before — until step 2 the mount still uses `supabase_admin`, so rotating first reduces nothing.

### 4. [operator] Expose `supabase-db`, tailnet-bound
Multi-home `supabase-db` onto `pmoves_external` (`internal:false`) so its port is plumbed, bound
to the **tailnet interface only** (not `0.0.0.0`). This is a **`compose:` protected edit** — set
`KNOWN_ROAD=compose:handoff:...` (the 08-18 handoff is the provable reason). Gated behind steps
1–3 by design; the diff is described in the handoff and should NOT be merged-and-applied ahead of
the rotation.

### 5. [agent] Mount `pmoves-media` on the 5090
Once the DB is reachable + the role is live: mount per `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`
(5090 has no host `juicefs` CLI — use the `juicedata/mount:ce-v1.3.0` container).

### 6. [agent] Point Jellyfin at the mount
Set `JELLYFIN_MEDIA_DIR` to the mounted `pmoves-media` path, then:
```
make -C pmoves rebuild-external-svc SVC=jellyfin-ext
```
Add libraries in Jellyfin pointing at the shared content. Verify a title plays end-to-end.

## Staged in this PR (safe now, changes nothing until used)
- `juicefs-cross-node-setup.sh`: `META_ROLE` param (default `supabase_admin`; set `juicefs_meta`
  at step 2). Refreshed the stale file:// header — the real blocker is metadata reachability.
- This checklist.

## Open item
`pmoves-jellyfin-ai` is pinned to a Knuckles JuiceFS path whose shared-mount propagation isn't
present on the 5090 — a separate node-mount decision. The main `pmoves-jellyfin` server (this
lane) is healthy and independent of it.

## Reconciliation & provenance (measured 2026-09-14, SPARK)

### Fleet reality check — the exposure step has NOT run on any node
TCP probe from SPARK across all 11 tailnet nodes (`pmoves-4090/5090/spark/z890/b850-ai-top/
nano-1/kvm4-1/kvm4-2/kvm2/rdna4/elder-melchor`, + `jetson`) on 5432/5433/54322: **zero
Postgres listeners anywhere on the tailnet.** The compose side of step 4 has LANDED (see
below) but no node sets `SUPABASE_DB_BIND` to its tailnet address, so every published db port
stays bound to loopback. The remaining exposure step is exactly: on the meta host, set
`SUPABASE_DB_BIND=<that node's tailnet IP>` and recreate `supabase-db`.

### Step 4 wording is superseded by the landed compose
This checklist (and the 08-18 handoff) said "multi-home onto `pmoves_external`". The compose
that actually landed is stricter: a **dedicated non-internal bridge `pmoves_db_egress`**
(subnet declared canonically in `ensure-overlay-networks` / `docker-compose.base.yml` — no
literals here) carrying only supabase-db, plus a **repo-managed `pg_hba.conf`** whose
tailnet rules admit only `juicefs_meta`, plus the `SUPABASE_DB_BIND` tailnet-bind default of
`127.0.0.1`. Read `supabase-db`'s block in `pmoves/docker-compose.yml` as the mechanism of
record; the prose here predates review P1 that rejected the shared egress network.

### "Meta is on KVM" — reconciled
The 2026-09 operator statement that the meta "is on kvm ready for it" matches **role/schema-side
readiness** (the scoped-role SQL is committed and `JUICEFS_META_PASSWORD` is funnel-delivered),
not exposure. The formatted `pmoves-media` volume's metadata home is **B850** (18 tables, per
the 08-18 handoff). Pointing a cross-node mount at a KVM Postgres that never carried this
volume yields an empty metadata engine or a different volume — the mount preflight in
`juicefs-cross-node-setup.sh` will refuse or the mount will list-and-fail-on-open. Host
selection stays B850 until a deliberate meta-migration lane exists.

### Official-doc provenance (accessed 2026-09-14)
Primary source, current official PostgreSQL best practices (docs have moved; old
`databases/postgres` path now 404s):
- https://juicefs.com/docs/community/postgresql_best_practices/
- canonical markdown: `juicedata/juicefs` → `docs/en/administration/metadata/postgresql_best_practices.md`

| Official guidance (current) | Our state | Verdict |
|---|---|---|
| Pass the password via `META_PASSWORD` env var, never the URL | `juicefs-cross-node-setup.sh` does exactly this | aligned |
| Set connection ceilings per mount: `max_open_conns`, `max_idle_conns`, `max_idle_time`, `max_life_time` URL params | **Not set anywhere** — our DSN runs unlimited | **adopt before fleet-wide mounts** (suggest `max_open_conns=30&max_life_time=3600` per official example; every Postgres client conn is a dedicated server process) |
| Keep server-side SSL enabled; `sslmode=disable` only when the server has none | Recorded decision: `sslmode=disable` because WireGuard encrypts the tailnet transport; role is non-superuser + pg_hba-scoped | recorded deviation, unchanged; the compose comment already says revisit if the DB is ever reachable off-tailnet |
| Poolers (PgBouncer/Pgpool) described generically; **no endorsement of transaction-mode pooling**; JuiceFS metadata ops are transaction-heavy | 08-18 handoff rejected supavisor transaction mode (unprovisioned tenants + prepared statements via lib/pq) | our rejection stands — the official page does not authorize transaction-mode pooling |
| "do not use a multi-server distributed architecture for the JuiceFS metadata" (no distributed-PG/Citus meta) | n/a today | note for any future HA lane |
| pg_hba example scopes one user to one subnet with md5 | ours is stricter (tailnet CIDR + dedicated bridge subnet, role-scoped, repo-managed) | aligned, stricter |

### Tailscale API status
Device enumeration via `api.tailscale.com` (official v2 endpoint, verbatim `Authorization` key)
returns **401** with a well-formed `tskey-api-` key — the funnel-delivered `TAILSCALE_APIKEY`
is stale/revoked (July vintage). Operator rotation item through the CHIT funnel; the probe
above fell back to `node-vocabulary.yaml` + direct TCP.
