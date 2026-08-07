# Handoff: harden `juicefs-mount` — credential exposure, undetectable wedge, hardcoded paths

**For:** B850-CLAUDE (this lane) · **Coordinates with:** Z890 JuiceFS-core lane
**Date:** 2026-08-07
**File:** `pmoves/docker-compose.juicefs-mount.yml` (protected — `KNOWN_ROAD=compose:handoff:juicefs-mount-hardening-2026-08-07.md`)
**Verified against:** upstream JuiceFS docs (links inline) + the `ce-v1.3.0` binary itself

## Context

B850's `juicefs-mount` reported `Up 5 days` while its entire namespace was
unreadable. Investigating that surfaced three defects in the committed overlay.
None of them is the cross-node `Storage: file` problem — that one is Z890's lane
and is **not** addressed here. These are independent and fixable without
touching live data.

## Observed failure

```
juicefs[18] <ERROR>: failed to connect to `user=supabase_admin database=postgres`:
  lookup supabase-db on 127.0.0.11:53: server misbehaving
```

The Supabase stack was removed from this node, so Docker DNS can no longer
resolve `supabase-db`, so the Postgres metadata engine is unreachable. The mount
process stays alive and the FUSE mount stays attached; every metadata operation
hangs.

Metadata is **not lost** — it lives in the `juicefs_meta` schema inside the
intact `pmoves_supabase-db-data` volume (147 MB). Restoring the data tier
recovers the mount with no filesystem work.

## Defect 1 — metadata password in the container command line

The META-URL interpolates `${SUPABASE_DB_PASSWORD}` directly:

```yaml
"postgres://supabase_admin:${SUPABASE_DB_PASSWORD}@localhost:5432/postgres?..."
```

Anything that can run `docker inspect` or read `/proc/<pid>/cmdline` can read
the Supabase admin password. It also lands in `docker ps --no-trunc` output and
in any log that captures the container spec.

**Fix:** pass it out-of-band via `META_PASSWORD`, which upstream documents for
exactly this purpose ([metadata engines][meta]):

```bash
export META_PASSWORD="..."
juicefs mount "postgres://user@host:5432/db?..." /mnt   # no password in the URL
```

`META_PASSWORD_FILE` is the alternative if a mounted file is preferred.

Keep `search_path=juicefs_meta` — JuiceFS defaults to the `public` schema and
will not find this volume's tables without it.

## Defect 2 — the wedge is undetectable

The service has **no healthcheck**, which is why `docker ps` showed `Up 5 days`
for a dead filesystem.

The upstream Docker example ([docker pattern][docker]) probes `/mnt/.control`.
**That probe does not work for this failure mode.** Measured on the wedged
mount, 2026-08-07:

| Probe | Path | Result |
|---|---|---|
| `cat /mnt/media/.control` | answered by the FUSE client itself | **OK** |
| `ls /mnt/media/` | GetAttr → metadata engine | **hangs** |
| `stat /mnt/media/video` | GetAttr → metadata engine | **EIO** |

`.control` is a virtual file the client serves locally; it never touches the
metadata engine, so it reports healthy while nothing is readable.

**Fix:** probe something that forces a metadata round-trip, and bound it:

```yaml
test: ["CMD-SHELL", "timeout 10 ls ${JUICEFS_MOUNT_POINT} >/dev/null 2>&1 || exit 1"]
```

The `timeout` is load-bearing. An unbounded probe against a wedged FUSE mount
hangs forever instead of reporting unhealthy — trading one silent failure for
another.

## Defect 3 — one operator's home directory, hardcoded

```yaml
device: /home/pmoves-knuckles/pmoves-fs
```

Committed, and wrong on every other node. It appears three times.

**Fix:** require `JUICEFS_MOUNT_POINT` (`:?`, absolute). Compose does not expand
`~`, and the `local` volume driver rejects a relative device, so the failure
would otherwise be obscure.

Also parameterize the metadata host/port (`JUICEFS_META_HOST`/`_PORT`,
defaulting to `localhost`) — the running container reaches Postgres over the
`pmoves_data` docker network while this file assumes `network_mode: host`.

## Also applied

Declare the documented container requirements — `/dev/fuse`, `SYS_ADMIN`,
`apparmor:unconfined` ([docker pattern][docker]). `privileged: true` already
implies them, but declaring them keeps the service correct if `privileged` is
ever narrowed, which it should be: privileged is far broader than a FUSE mount
requires.

## Explicitly NOT in scope

- **`Storage: file` → shared object store.** Upstream is unambiguous that a
  `file` volume "cannot be mounted by other clients within the network and can
  only be used on a single machine" ([object storage][obj]). That is the real
  cross-node blocker and it belongs to Z890's JuiceFS-core lane.
- **The repoint itself.** For the record, it needs **no reformat**: the
  `ce-v1.3.0` binary's `juicefs config` accepts `--storage` and `--bucket`
  ("Only flags explicitly specified are changed"). A doc summary claiming
  otherwise is wrong. The real constraint is that `config` moves the *pointer*,
  not the *bytes* — `juicefs sync` must run first or every existing file 404s.
- **Rotating the exposed password.** Required, but it is a live-credential
  operation with its own blast radius. This change stops the *ongoing* exposure;
  rotation closes the *past* exposure and should be sequenced with the operator.

## Verification

- `docker compose config` parses with the overlay
- `juicefs config --help` from `ce-v1.3.0` confirms `--storage` / `--bucket`
- Healthcheck asserted against the live wedged mount: `.control` passes while
  `ls` hangs — i.e. the new probe catches what the upstream example misses

[meta]: https://juicefs.com/docs/community/databases_for_metadata/
[obj]: https://juicefs.com/docs/community/reference/how_to_set_up_object_storage/
[docker]: https://juicefs.com/docs/community/juicefs_on_docker/
