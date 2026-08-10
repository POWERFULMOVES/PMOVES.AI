# JuiceFS `pmoves-media` — file:// → MinIO reformat (cross-node content unblock)

**Status:** Operator-gated runbook (2026-08-07). **Owner lane:** Z890-CLAUDE (storage).
**Investigated by:** z890-claude, read-only, 2026-08-07 — facts below are measured, not assumed.
**Supersedes the risk framing in:** `pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md`

> **Which JuiceFS is this?** The **`pmoves-media` POSIX filesystem** — the cross-node
> *content* mount (`/mnt/media`), Postgres metadata, currently hosted on **b850**. This is
> **NOT** the z890 S3-*gateway* JuiceFS (`assets`/`outputs`/`pmoves-comfyui` buckets) covered
> by `JUICEFS_PHASE3_CUTOVER.md`. Two separate deployments — do not conflate them.

## Measured state (2026-08-07, read-only)

| Fact | Evidence |
|---|---|
| `pmoves-media` mounted + healthy on b850 | `JuiceFS:pmoves-media on /mnt/media type fuse.juicefs` |
| Metadata engine = **Postgres** (standardized, correct) | cmdline: `postgres://…@supabase-db:5432/postgres?search_path=juicefs_meta` |
| Storage backend = **`file://` (single-node)** | bind `/home/pmoves-knuckles/.local/share/juicefs-data → /data` (local chunk dir) |
| **Volume is EMPTY** | `/mnt/media` = `total 0`; `df` = `104K used` of virtual 1.0P (metadata only) |
| z890 has **no** `pmoves-media` mount | z890 runs only `juicefs-gateway` + `juicefs-redis` (a *different*, throwaway `pmoves` volume) |
| nano-1 has the juicefs client | `/usr/local/bin/juicefs` present, ready to mount |

**Why this de-risks the whole thing:** the 08-04 blocker doc treated this as a live-data
migration ("confirm the inventory before any reformat… `juicefs sync` the data"). It is not —
**there is no data.** JuiceFS was never successfully populated; the DARKXSIDE inbox / Jellyfin
were empty because nothing was ever written here, not because content is trapped. Real content
still lives on `z890 I:\MOVIES`, `I:\BEATS BACKUP`, `5090 SEAP`, etc. So this is a **clean
reformat onto MinIO**, not a data move.

## Target end-state

`pmoves-media` re-created with `Storage: minio` pointing at the already-live, tailnet-exposed
MinIO on z890 (`…:9000`, healthy 42h+). Then every `tag:pmoves` node (z890, nano-1, spark,
5090) mounts the *same* volume and sees the *same* bytes — the actual "content → JuiceFS →
Jellyfin / jetson compute" flow the creator pipeline needs.

## Operator gates (why this is not auto-run)

1. **`juicefs destroy` on the empty `pmoves-media`** removes its Postgres-meta entry. Low risk
   (empty), but it mutates the shared `juicefs_meta` schema on `supabase-db`. Operator authorizes.
   > ⚠️ This touches the **JuiceFS meta schema only**. It does **NOT** touch the Supabase
   > `pmoves_supabase-db-data` volume. Never `down -v` / `reset.sh` the database.
2. **Supabase admin password is exposed** — b850's mount has historically passed
   `supabase_admin`'s password as a cleartext CLI arg (visible in `ps` / `docker inspect`).
   **Rotate it** as part of this window (operator action, voice-activated CHIT pipeline — do
   **not** hand-edit `env.shared`). The re-created mount must use `META_PASSWORD`, never inline.
3. **CHIT passphrase** is required for the `META_PASSWORD` form (secrets pipeline). Operator's
   voice-activated vault — runs in the operator's context, not this agent's subprocess.

## Procedure (operator-run; ~10 min, empty volume)

### Step 0 — final safety confirm (read-only)
```bash
# On b850 — confirm STILL empty right before destroy (guard against a late writer):
ssh pmoves@pmoves-b850-ai-top \
  'docker exec juicefs-mount sh -c "ls -la /mnt/media | head; df -h /mnt/media"'
# Expect: total 0, ~104K used. If NOT empty, STOP — this becomes a data migration
# (fall back to the juicefs-sync path in the 08-04 blocker doc).
```

### Step 1 — stop + destroy the empty file:// volume (b850)
```bash
ssh pmoves@pmoves-b850-ai-top '
  docker stop juicefs-mount
  # destroy needs the meta URL; use META_PASSWORD so the secret never hits argv/ps:
  export META_PASSWORD="<supabase_admin pw, from vault — operator context>"
  docker run --rm --network pmoves_data -e META_PASSWORD \
    juicedata/mount:ce-v1.3.0 juicefs destroy --yes \
    "postgres://supabase_admin@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable" \
    <VOLUME_UUID>
'
# VOLUME_UUID printed by `juicefs status` — capture it in Step 0.
```

### Step 2 — format `pmoves-media` onto MinIO
```bash
# MinIO is already tailnet-live on z890 (…:9000). Use the fleet MinIO creds (from vault).
export META_PASSWORD="<supabase_admin pw>"
docker run --rm --network pmoves_data \
  -e META_PASSWORD -e MINIO_USER -e MINIO_PASSWORD \
  juicedata/mount:ce-v1.3.0 sh -c '
    juicefs format \
      --storage minio \
      --bucket http://<Z890_TAILSCALE_HOST>:9000/pmoves-media \
      --access-key "$MINIO_USER" --secret-key "$MINIO_PASSWORD" \
      "postgres://supabase_admin@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable" \
      pmoves-media
  '
# Note: bucket host = z890 by *Tailscale hostname* (not literal IP) so every node resolves it.
# The MinIO `pmoves-media` bucket must exist first (mc mb -p) — see Step 2a.
```

### Step 2a — ensure the MinIO bucket exists
```bash
docker run --rm --network pmoves_data \
  -e MC_HOST_z=http://$MINIO_USER:$MINIO_PASSWORD@minio:9000 \
  minio/mc mb -p z/pmoves-media || true
```

### Step 3 — re-create b850's mount with `META_PASSWORD` (no inline secret)
Use the repo target that already implements the `META_PASSWORD` form (added in the #2337 line):
```bash
ssh pmoves@pmoves-b850-ai-top 'cd /opt/pmoves && make -C pmoves juicefs-mount-pg'
# verify:
ssh pmoves@pmoves-b850-ai-top 'make -C pmoves juicefs-mount-status'
# `juicefs status` should now report Storage: minio, Bucket: http://<z890>:9000/pmoves-media
ssh pmoves@pmoves-b850-ai-top 'make -C pmoves juicefs-storage-check'   # must NOT say file
```

### Step 4 — mount cross-node + prove one byte crosses
```bash
# On z890 (S3 gateway host — add the POSIX mount):
make -C pmoves juicefs-mount-pg   # or juicefs-mount-local
echo "hello-from-z890" > /mnt/pmoves-media/_crossnode_probe.txt

# On nano-1 (client already installed):
ssh pmovesnvme@pmoves-nano-1 \
  'sudo juicefs mount --enable-xattr \
     "postgres://supabase_admin@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable" \
     /mnt/pmoves-media -d && cat /mnt/pmoves-media/_crossnode_probe.txt'
# Expect: hello-from-z890  ← the byte written on z890, read on the jetson. Blocker cleared.
```

### Step 5 — rotate the Supabase admin password
Operator action, voice-activated CHIT pipeline (the exposure window has been open since ~08-01).
Do **not** hand-edit `env.shared`; regen through the manifest → funnel path. After rotation,
Step 3's mount picks up the new `META_PASSWORD` on next re-create.

## What this unblocks (creator pipeline)
- **content → JuiceFS → Jellyfin**: point Jellyfin libraries at the cross-node `/mnt/pmoves-media`
  (still needs the Jellyfin bind-mount fix — Docker Desktop won't traverse Windows junctions;
  see the Jellyfin bare-wizard memory).
- **jetson file-based compute**: nano-1 can read ingested content for batch Whisper / YOLO
  (the NATS-streamed STT path does not need this; the *file* path does).
- **DARKXSIDE inbox**: still needs a room storage/inbox contract (tracked separately — the room
  manifest has no storage key; `ROOM_MANIFEST_CONTRACT.md` defines no storage section).

## Verification checklist
- [ ] Step 0 confirms volume still empty immediately before destroy
- [ ] `juicefs-storage-check` reports `Storage: minio` (not `file`) after Step 3
- [ ] Cross-node probe byte written on z890 reads back on nano-1 (Step 4)
- [ ] b850 mount re-created with `META_PASSWORD` (no secret in `ps` / `docker inspect`)
- [ ] Supabase admin password rotated through the CHIT pipeline (Step 5)
- [ ] `pmoves_supabase-db-data` volume never touched (only `juicefs_meta` schema mutated)

## References
- `pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md` (the file:// finding; risk framing now corrected — empty volume)
- `pmoves/docs/operations/JUICEFS_PHASE3_CUTOVER.md` (the *other*, S3-gateway JuiceFS — do not conflate)
- `pmoves/docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md`
- PR #2337 (`feat/juicefs-network-storage` — exposed MinIO on the tailnet; `juicefs-mount-pg` `META_PASSWORD` target)
- `pmoves/mk/egress.mk` (`juicefs-storage-check`, `juicefs-mount-status`, `juicefs-mount-pg`)
