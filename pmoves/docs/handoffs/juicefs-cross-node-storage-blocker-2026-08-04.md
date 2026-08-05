# JuiceFS cross-node is blocked by the object store, not the metadata (2026-08-04)

**TL;DR:** the fleet's `pmoves-media` volume is formatted with `Storage: "file"`. The
data blocks live on b850's local disk. Metadata standardization (the 2026-08-01
decision) is necessary but **not sufficient** — no other node can ever read this
volume's contents until it is reformatted onto a network-reachable object store.

## How this surfaced

Operator report: JuiceFS clients on phone and PC still show nothing, and files
expected in the DARKXSIDE Room inbox never appeared. Jellyfin is empty for the same
underlying reason — content is supposed to flow content → JuiceFS → Jellyfin.

## Measured state

Read from b850's live `juicefs-mount` container (`juicefs status`, credential never
left the container):

```
Name:        pmoves-media
Storage:     file        <-- local filesystem, NOT object storage
Bucket:      /data/      <-- = /home/pmoves-knuckles/.local/share/juicefs-data on b850
BlockSize:   4096
Compression: none
TrashDays:   1
```

`Storage: file` means JuiceFS writes chunks to a local directory. The metadata engine
(postgres/Supabase) is shareable over the tailnet; **the chunks are not**. A second
node pointed at the same postgres meta would enumerate every filename correctly and
then fail every read with an I/O error, because the blocks are on a disk it cannot
reach. The volume is single-node by construction.

This answers the open question the 2026-08-01 metadata handoff left for crush —
*"is the object storage the same MinIO (tailnet-exposed) or something else?"* It is
neither. It is local file storage.

## What this means for the plan

| Layer | 08-01 decision | Actual blocker |
|---|---|---|
| Metadata | standardize on postgres/Supabase | correct, and already live on b850 |
| **Object store** | left open | **`file://` — must move to MinIO before any cross-node mount** |

Ordering: **reformat/migrate the volume onto MinIO first**, then standardize metadata,
then mount elsewhere. Doing metadata first (as scoped on 08-01) produces a fleet that
looks wired and still cannot read a byte cross-node.

Migration is not a remount — `juicefs format` binds the storage backend into the
volume. Moving backends means creating a volume against MinIO and copying data across
(`juicefs sync`). Per the 08-01 note the redis-meta FS holds only throwaway test
markers, so the only real data at risk is whatever now sits under b850's
`juicefs-data`. **Confirm that inventory before any reformat.**

## Canonical mount recipe (derived from the running b850 container)

The 08-01 handoff lists this as something crush still owes. It is recoverable from
the live container, so it is recorded here:

```
image:      juicedata/mount:ce-v1.3.0
entrypoint: sh -c
command:    exec juicefs mount --enable-xattr "<META_URL>" /mnt/media
privileged: true
network:    pmoves_data          # so supabase-db resolves
restart:    unless-stopped
binds:
  <host>/.local/share/juicefs-data -> /data          (rprivate)
  <host>/pmoves-fs                 -> /mnt/media     (rshared)   # rshared is required
                                                                  # for propagation
```

Meta URL form (postgres):

```
postgres://supabase_admin@supabase-db:5432/postgres?search_path=juicefs_meta&sslmode=disable
```

## Security item — carried over from 08-01 and still live

b850 passes the Supabase admin password as a **cleartext CLI argument**, so it is
visible in `ps` to any local user, and it shows up in `docker inspect` output:

```
CMD=[-c exec juicefs mount --enable-xattr "postgres://supabase_admin:<PASSWORD>@..." /mnt/media]
```

JuiceFS supports `META_PASSWORD`, so the URL can omit the credential entirely. The
`juicefs-mount-pg` target added in this PR uses that form. Two follow-ups remain and
are **operator actions**:

1. Re-create b850's `juicefs-mount` with `META_PASSWORD` instead of the inline URL.
2. **Rotate the Supabase admin password** — it has been exposed in process listings
   and container metadata for at least three days.

## Why the DARKXSIDE inbox is empty

Three independent gaps, all real:

1. **z890 has no filesystem mount at all.** It runs only the S3 gateway
   (`juicefs-gateway` + `juicefs-redis`); there is no `juicefs-mount` container, so
   no POSIX path exists for a phone or PC client to browse.
   `make -C pmoves juicefs-mount-status` returns empty.
2. **z890 is on the deprecated redis meta**, a different volume (`pmoves`) from
   b850's (`pmoves-media`). Even ignoring the storage blocker, they are two unrelated
   filesystems.
3. **There is no inbox.** `pmoves/config/rooms/darkxsides.room.json` has no storage,
   data, or inbox key, and `ROOM_MANIFEST_CONTRACT.md` defines no storage section at
   all. Nothing binds a JuiceFS path to that room, so nothing was ever going to
   deliver files there. Tracked separately.

## Next actions

- [ ] Inventory what actually lives under b850's `juicefs-data` before touching it.
- [ ] Operator decision: reformat `pmoves-media` against tailnet MinIO (see #2337,
      which exposed MinIO on the tailnet and is meta-backend-agnostic).
- [ ] `juicefs sync` the inventoried data onto the new volume.
- [ ] Re-create b850's mount with `META_PASSWORD`; rotate the Supabase admin password.
- [ ] Only then: mount on z890 / spark / nano via `make juicefs-mount-pg`.
- [ ] Separately: define a room storage/inbox contract and bind DARKXSIDE to it.

Related: 2026-08-01 metadata standardization note (local working doc, uncommitted),
PR #2337 (`feat/juicefs-network-storage`).
