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
