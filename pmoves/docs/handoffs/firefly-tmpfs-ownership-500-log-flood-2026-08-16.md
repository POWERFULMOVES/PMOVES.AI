# Firefly III — tmpfs ownership breaks Laravel cache → HTTP 500 on every request + 10.7 GB log flood

**Node:** z890 · **Found:** 2026-08-16 by z890-claude while triaging `D:` at 100% full
**Change class:** Known Road — `compose:handoff:firefly-tmpfs-ownership-500-log-flood-2026-08-16.md`
**File touched:** `pmoves/docker-compose.external.yml` (firefly `tmpfs:` options only)

---

## Symptom chain (measured, in this order)

1. `D:` (3.7 TB, hosts the repo **and** `DockerData`) hit **100% — 0 bytes free**. Writes to the
   repo began failing with `ENOSPC`.
2. `make -C pmoves docker-prune` reclaimed **7 MB**. `D:` stayed at 0.
   *Pruning frees space **inside** the vhdx; it cannot shrink the file.*
3. Largest consumer inside the Docker VM: **`pmoves-firefly` = 10.7 GB** in a single
   `*-json.log`, still growing (**~2 MB / 5 min** measured).
4. Log content is one repeating Laravel stack trace plus a `500` access-log line per probe:

```
production.ERROR: file_put_contents(/var/www/html/storage/framework/cache/data/6c/61/<hash>):
  Failed to open stream: No such file or directory
172.30.2.20 - - "GET / HTTP/1.1" 500 1029 "-" "Blackbox Exporter/0.25.0"
```

**Firefly has been returning HTTP 500 on every request**, and Blackbox Exporter polls it on a
loop — a broken service multiplied by a monitoring probe = unbounded identical stack traces.
The disk-fill was the *symptom*; the 500 is the defect.

## Root cause

`pmoves/docker-compose.external.yml:109-113` mounts **tmpfs** over three Laravel runtime dirs:

```yaml
    tmpfs:
      - /tmp:noexec,nosuid
      - /var/www/html/storage/framework/sessions:noexec,nosuid
      - /var/www/html/storage/framework/views:noexec,nosuid
      - /var/www/html/storage/framework/cache:noexec,nosuid
```

Observed inside the container:

```
tmpfs on /var/www/html/storage/framework/cache type tmpfs (rw,nosuid,nodev,noexec,relatime,mode=775)
drwxrwxr-x 2 root root 40 ... cache        <- tmpfs: EMPTY + root-owned
drwxrwxr-x 2 www-data www-data 4096 ... testing   <- untouched sibling, for contrast
ls: cannot access '.../cache/data': No such file or directory
```

A tmpfs mount is **empty on every container start and owned by `root`**. Firefly's php-fpm
workers run as **`www-data` (uid=33, gid=33)**, which therefore cannot create the `data/`
subdirectory Laravel's file cache store requires. Every request fails the same way.

The tmpfs mounts are a *hardening* measure (`noexec,nosuid`). The hardening is not wrong — it
was simply applied without giving the runtime user ownership, so it silently disabled the app.

## Fix (per official Docker documentation)

Docker's tmpfs reference lists `uid`, `gid`, `mode`, `size`, `noexec`, `nosuid` as supported
options and states that setting permissions on tmpfs "may cause them to reset after container
restart", **recommending `uid`/`gid` for this case**. That is exactly this failure.

Set the tmpfs owner to the runtime user and tighten the mode, **keeping `noexec,nosuid`**:

```yaml
    tmpfs:
      - /tmp:noexec,nosuid
      - /var/www/html/storage/framework/sessions:noexec,nosuid,uid=33,gid=33,mode=0770
      - /var/www/html/storage/framework/views:noexec,nosuid,uid=33,gid=33,mode=0770
      - /var/www/html/storage/framework/cache:noexec,nosuid,uid=33,gid=33,mode=0770
```

- `uid=33,gid=33` — `www-data`; lets Laravel create `cache/data/**` itself (its `FileStore`
  creates the tree on demand once the mount is writable).
- `mode=0770` — tightens the current `775` (removes world-read) while keeping owner+group write.
- `noexec,nosuid` — **retained**; the hardening intent is preserved, not traded away.

`/tmp` is deliberately left alone: it is root-writable and world-writable by convention, and
nothing reported a failure there.

### Deliberately NOT bundled: tmpfs `size=` limits

An unbounded tmpfs can consume RAM, and Docker supports `size=`. It is **not** included here
because a too-small value would produce a *new* outage of the same shape, and no measurement of
Firefly's steady-state cache/session footprint exists yet. Track as a follow-up: observe usage,
then set a bound with headroom. Fixing a live 500 and introducing an unvalidated limit are two
changes and should not ride together.

## Verification

```bash
make -C pmoves up-external        # recreate so the new tmpfs options apply (firefly is in this stack)
docker exec pmoves-firefly sh -c 'ls -ld /var/www/html/storage/framework/cache'   # expect www-data
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:8075/                  # expect 200, not 500
```

Then confirm the log stops growing (it was ~2 MB / 5 min).

## The wider finding this surfaced

**Container log rotation only applies to containers created after the fix.** `#2420` baked
`json-file` rotation (`max-size: 10m`, `max-file: 3`) into the compose tier anchors on
**2026-08-05**, but Docker fixes log configuration **at container-creation time**. Measured on
z890 2026-08-16:

- **18** containers have rotation (created since the fix)
- **30** containers have `LogConfig.Config = {}` — **unbounded** (all predate it)

`pmoves-firefly` (created 2026-07-21), `pmoves-tensorzero-clickhouse-1` and
`pmoves-hi-rag-gateway-v2-1` (both 2026-07-31) are in the unbounded set. `#2420` shipped without
a backfill step, so a correct fix has been sitting inert on two-thirds of the fleet's containers.
**Recreate them to apply it** — that is the backfill, and it belongs on every node, not just z890.

Secondary: `pmoves-tensorzero-clickhouse-1` still carries `<level>trace</level>` with 1.8 GB of
internal `/var/log/clickhouse-server` — separate from Docker log rotation, which never sees it.
