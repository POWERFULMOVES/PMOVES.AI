# JuiceFS Cross-Node Mount Runbook — 4090 / 5090

> **Status:** operator-run. Authored by z890-claude 2026-08-09.
> **Goal:** mount the shared JuiceFS filesystem on the 4090 and 5090 so both can
> read/write fleet content, with a **per-host bounded cache** so neither inherits
> the JuiceFS 100 GiB default (or streams every read from tailnet MinIO).

The JuiceFS metadata + storage home is **B850** (the data-tier host). Bring it
back first (`B850_BRINGBACK_RUNBOOK.md`) — the mounts below fail if B850 is not
up and reachable over the tailnet.

---

## 0. Confirm the canonical volume BEFORE mounting

There are two JuiceFS volumes and **only one is cross-node-capable**:

| Volume | Storage backend | Meta | Cross-node? |
|--------|-----------------|------|-------------|
| **`pmoves`** | **minio** (tailnet MinIO) | Postgres (`juicefs_meta`) | ✅ **yes — mount this** |
| `pmoves-media` | `file` (host-local disk blocks) | — | ❌ no — lists filenames, I/O-errors every read |

`pmoves` is minio-backed, Postgres-meta, writable (mirror-confirmed on SPARK).
`pmoves-media` is formatted with `Storage:"file"`, so its data blocks live on the
formatting host's local disk and are unreachable from any other node — the
cross-node setup script **refuses** it unless you set `ALLOW_FILE_STORAGE=1`
(don't, for the shared mount). Verify before mounting:

```bash
make -C pmoves juicefs-storage-check
# Expect Storage: minio (or a MinIO bucket). If it reports Storage:"file", STOP —
# you are pointed at the wrong volume. See the storage blocker handoff.
```

---

## 1. Prerequisites (per node)

- Node is on the Tailscale mesh (`make -C pmoves fleet-status` shows it online —
  the Known Road; it redacts IPs, unlike raw `tailscale status`).
- Docker is installed and running.
- The Supabase DB (JuiceFS meta) on B850 is reachable **by MagicDNS hostname**,
  never a literal Tailscale/LAN IP (committed docs carry no literal IPs; the
  DARKXSIDE egress floor fails closed on literal IPs).

---

## 2. Mount sequence (run on each node — 4090, then 5090)

```bash
# On the target node (4090 / 5090). JUICEFS_HOST is the MagicDNS hostname of the
# JuiceFS meta host (B850) — use the name confirmed in B850_BRINGBACK_RUNBOOK.md.
# DB_PASS is the Supabase DB password, sourced from the CHIT secrets pipeline
# (exported as an env var so it reaches JuiceFS via META_PASSWORD and never
# appears in `ps` / `docker inspect`).
export DB_PASS=...          # from the CHIT secrets pipeline — do not paste on a shared CLI

make -C pmoves juicefs-cross-node-setup \
  JUICEFS_HOST=pmoves-b850-ai-top \
  DB_PASS="$DB_PASS"
```

This target (`pmoves/mk/egress.mk` → `pmoves/scripts/juicefs-cross-node-setup.sh`):
1. Pulls `juicedata/mount:ce-v1.3.0`.
2. Runs a **storage preflight** — refuses to proceed on a `file`-backed volume.
3. **Computes per-host bounded cache flags** via `scripts/juicefs-cache-bounds.sh`
   (measures the `/data` volume's host backing dir) so the 4090/5090 do **not**
   inherit the 100 GiB default and caching does not self-disable on a full disk.
4. Mounts at `$HOME/pmoves-fs` (override with `MOUNT_POINT=`).

The setup echoes the chosen cache bounds, e.g.:

```
Cache bounds: --cache-dir /data --cache-size 102400 --free-space-ratio 0.100
```

On a near-full node the helper drops `--free-space-ratio` below 0.1 (keeping
caching enabled) and warns that the mount is too small to hold a large working
set — heed that warning before relying on the node for heavy reads.

---

## 3. Verify (per node)

```bash
make -C pmoves juicefs-mount-status      # container up + content dirs visible
ls "$HOME/pmoves-fs"                      # lists shared content

# Read-path proof (the file-backed volume fails HERE with an I/O error):
cat "$HOME/pmoves-fs"/**/<some-small-file> >/dev/null && echo "READ OK"

# Cache is actually being used (not self-disabled):
docker exec juicefs-mount sh -c 'du -sh /data/jfsCache 2>/dev/null || du -sh /var/jfsCache'
# Expect a NON-trivial size after a few reads (bounded, not zero-because-disabled).
```

**T3 pass criteria:** 4090 and 5090 both mount the **minio-backed `pmoves`**
volume; a read of a real file succeeds (no I/O error); `jfsCache` grows to a
non-trivial size (cache bounded and active, not self-disabled).

---

## Windows note (5090)

The 5090 is a Windows host. The Docker-based `juicefs-cross-node-setup` path
assumes a Linux Docker host. For a native Windows mount, the alternative is
**WinFsp + `juicefs.exe`** pointed at the same Postgres meta DSN (MagicDNS host,
not an IP) with the same `--cache-dir/--cache-size/--free-space-ratio` bounds
from `scripts/juicefs-cache-bounds.sh` (run it under Git Bash / WSL to compute the
numbers, then pass them to `juicefs.exe mount`). Pick whichever runtime matches
how the 5090 runs ComfyUI (WSL2 vs native).

---

## Related

- Data-tier host bring-up → `B850_BRINGBACK_RUNBOOK.md`.
- Storage-backend gotcha (`file` vs `minio`) →
  `pmoves/docs/handoffs/juicefs-cross-node-storage-blocker-2026-08-04.md`.
- Cache-bounds helper → `pmoves/scripts/juicefs-cache-bounds.sh`.
