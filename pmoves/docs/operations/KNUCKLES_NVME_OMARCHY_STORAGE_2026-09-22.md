# Knuckles NVMe + Omarchy Storage Lane — 2026-09-22

**Lane:** `infra/knuckles-nvme-omarchy-storage` (worktree `.claude/worktrees/knuckles-nvme-omarchy`, off `origin/main` @ 816660dd9)
**Owner:** CRUSH-GLM52 (Knuckles) · **Operator decisions:** DARKXSIDE/POWERFULMOVES, locked 2026-09-22
**Status:** PLAN — provisioning script committed to the lane; execution begins on operator `--yes-really`

## Situation (measured 2026-09-22)

- Root disk `/dev/nvme0n1p2` (916G) at **100% / 8.4G free** after cache triage.
  Consumers: `/home` 544G (pinokio 201G, ai-tools 112G, Downloads 79G, .lmstudio 71G,
  .conda 37G), Docker `/var/lib/docker` ~245G (162G images, 72G volumes, 65 running containers).
- Two blank 4TB NVMe drives present: `/dev/nvme1n1`, `/dev/nvme2n1` — no partitions,
  no filesystems, never mounted.
- JuiceFS (`~/pmoves-fs`, 1PB logical) mounted via the `juicefs-mount` container; cache
  backing dir `~/.local/share/juicefs-data` **on the root disk**, bounded to ~13G by
  `scripts/juicefs-cache-bounds.sh` measuring that disk's free space.

## Operator-locked layout

| Drive | Purpose |
|---|---|
| **NVMe1** (`/dev/nvme1n1`) | Creator pipeline store: ComfyUI H3 models/input/output/custom_nodes + JuiceFS cache backing (bounds auto-scale to the drive) |
| **NVMe2** (`/dev/nvme2n1`) | **Bare-metal Omarchy seat** — the intended future knuckles OS ("close to agent OS"; upstream ships `AGENTS.md`/`CLAUDE.md`). Full PMOVES stack + CHIT-aware configuration deployed on top. Drive stays **unformatted** — the OS installer partitions it. |
| Docker data-root | Stays on root disk this lane; migration is its own risk-gated lane later (operator choice) |

Doctrine anchors: `pmoves/docs/operations/UNATTENDED_NODE_BOOTSTRAP.md` (bootstrap_flavor
axis; omarchy = fresh workstations / community class / "PMOVES GOES HAM"),
`pmoves/docs/services/FLEET_TERMINAL_STRATEGY.md` (#2963), HYPERAGINTZ W2-4
(PMOVES-omarchy = Danger-Room host-OS candidate). Fork
`POWERFULMOVES/PMOVES-omarchy` branch `quattro` carries no PMOVES delta, but it
is a STALE mirror: 0 ahead / 145 behind `omacom/omarchy` (GitHub compare,
2026-10-01). The unattended-install answer file is the open item this lane
begins. The disk partitioner itself lives in `omacom/omarchy-iso`, which has no
PMOVES fork.

## Incident on record (pre-lane, same session)

A raw `docker volume rm` (blocked in Claude Code; Known Road `make -C pmoves volume-reset SERVICE=<name>`) deleted the five `pmoves_comfyui-*` named volumes
(~60G: downloaded H3 models + any rendered outputs; outputs are **not** recoverable,
models re-download via `pmoves/tools/comfyui/install/` Aitrepreneur installers).
Root causes: (1) Crush sessions run **without** the Claude Code damage-control
hooks — this harness had zero hooks configured; (2) the bash hook patterns
deliberately exclude `docker rm` from the `rm -rf` net. Correction (2026-10-01):
the Claude Code side DOES block the raw volume removal and routes it to the Known
Road `make -C pmoves volume-reset SERVICE=<name>` (`.claude/hooks/pre-tool.sh:17`, since #275;
`.claude/hooks/damage-control/patterns.yaml:306-320`). The gap was Crush alone.
Remediation is Phase 5. Videos (~79G, 13× `PXL_*.mp4`)
move to JuiceFS `knuckles/downloads/` (rsync --remove-source-files,
operator-approved).

### Findings during the video move (2026-09-22 ~11:00-11:40)

1. **JuiceFS write failure root cause.** First move attempt died at 608M with
   `Input/output error`: the JuiceFS cache backing dir was on the root disk, whose
   free space (0.9%) fell below the mount's `--free-space-ratio 0.014` guard —
   cache writes fail, the mount rejects writes mount-wide. Zero video data lost
   (all sources intact; rsync removed nothing). Sequencing lesson now baked into
   the phases: **Phase 1 (NVMe1) + Phase 3 (cache repoint) before bulk JuiceFS
   writes.** JuiceFS purged its own cache recovering ~13G.
2. **`~/ai-tools` (112G, LM Studio `lmstudio-community` models) vanished at
   ~11:32** — outside this session. **Operator confirmed 2026-09-22: it was
   them.** Closed as operator-authorized removal.
3. Root disk after both events + cache triage: **116G free (87%)**.
4. **VS Code Insiders snap-refresh crash (12:14)** killed the session's child
   shells mid-lane (second video-move death; sources again untouched). Fix:
   snap-level hold + `update.mode: none`; long-running transfers now launch
   detached (`setsid`) so editor crashes cannot kill them.

### Findings during stack bring-up (2026-09-22 ~19:00-20:00)

5. **Image pins that failed to pull during bring-up:**
   - `supabase/studio:2026.08.03-sha-022b374` failed to pull on 2026-09-22 and
     was first read as "pruned from Docker Hub". **That was wrong:** on
     2026-10-01 the tag resolves (`docker manifest inspect` rc=0, Hub tags API
     200). The failed pull fits this node's known exit-node egress fault, not
     tag deletion. The lane's downgrade to `2026.06.03-sha-0bca601` was
     **dropped in review**; main's pin stands. (B850 still RUNS the 06.03 image
     it already had; a recreate would move it to main's pin.)
   - `minio/minio`: the Docker Hub repository is deleted. The lane first
     repinned to `quay.io/minio/minio`, but main later measured Quay as 401
     anonymously (2026-09-26) and moved to a locally built
     `ghcr.io/powerfulmoves/pmoves-minio:RELEASE.2025-09-07T16-13-09Z-src`
     (#3192). The rebased lane keeps **main's** pin and carries no MinIO change.
     The Quay pin is what brought MinIO back on this node on 2026-09-22.
6. **JuiceFS write failures were three stacked faults**, not one: (a) the
   `juicefs_meta` role password rotated in-place under the 2-day-old mount;
   (b) the block-store backend (`minio:9000` = the JuiceFS S3 gateway /
   MinIO service) was entirely down; (c) host-network mounts cannot resolve
   in-network service names. Fixes: role password reset to the canonical CHIT
   value (verified), MinIO started from the Quay image (node-local, since
   superseded on main, see 5) + gateway stack restarted, mount
   recreated on the docker network with NVMe1 cache backing.
7. **Supabase fork dependabot wave**: 13/15 PRs landed (admin squash under
   strict linear-history protection, operator-directed); #13 + #30 remain
   CONFLICTING after `@dependabot rebase` requests — pending dependabot's
   rebase; close before promoting the fork gitlink. The gitlink promotion
   (10451c28a -> 511f6118f, an 848-commit upstream sync that also changes the
   edge-functions code bind-mounted from the root checkout) was **removed from
   this lane in review** and belongs in its own lane.

### Durability pass — verified against JuiceFS upstream docs (2026-09-22 ~20:00)

On B850 the mount reproduces from a plain `make juicefs-cross-node-setup
JUICEFS_HOST=supabase-db`, verified end-to-end on 2026-09-22. That run relied
on node-local state in the gitignored `pmoves/.env.local` (listed below,
including `META_ROLE=juicefs_meta`), so it was **not** a zero-knowledge
reproduction. Review of the lane PR found the original automatic pairing rule
dead (a default was assigned before the rule could see "no role named") and the
make recipe defeating it a second time. Steward decision (2026-10-01): follow the
documented precedent instead of repairing the automation, so the role is named
explicitly. Covered by `pmoves/tests/scripts/test_juicefs_cross_node_role_pairing.py`. A fresh
clone still needs the node shape (`JUICEFS_NETWORK`, `JUICEFS_NAME`, cache dir)
from `.env.local`. The script hardenings:

- **Role/credential pairing** (`scripts/juicefs-cross-node-setup.sh`): an
  explicit `META_ROLE` always wins (empty counts as not named). The funnel
  credential `JUICEFS_META_PASSWORD` is `juicefs_meta`'s password, so using it
  with no role named now **fails loudly** and points at the runbook invocation
  (`META_ROLE=juicefs_meta`, `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md:92-102`). It is
  never silently paired, and never with `supabase_admin`, which was the defect:
  that mismatched pair always failed auth. An explicit `DB_PASS` with no role
  keeps the back-compat `supabase_admin` default and prints that it did. The
  test proves the script-level behaviour and the recipe's forwarding shape; it
  does not exercise a live mount.
- **Preflight diagnostics**: the storage probe used to die silently
  (`2>/dev/null` + `set -euo pipefail`) before printing anything. It now
  captures both streams, redacts the credential, and prints the real error.
  First re-run immediately surfaced the true failure (DNS, not auth).
- **Stale-endpoint guard**: a killed mount container leaves the FUSE endpoint
  dead; user-level `fusermount` cannot clear container-created mounts. The
  script detects this and prints the exact `sudo umount -l` fix instead of
  docker's misleading "mkdir: file exists".
- **Recipe env plumbing** (`mk/egress.mk`): the target dropped its forced
  `META_ROLE=supabase_admin` default and now runs the script under
  `scripts/with-env.sh`, so node-shape vars resolve from `.env.local`. Because
  with-env.sh re-sources `.env.local` over the caller's environment, values
  named on the make command line are forwarded as `JFS_SETUP_META_ROLE` /
  `JFS_SETUP_DB_PASS` (names no env file sets) so the node file cannot silently
  replace them, and the recipe no longer resolves the funnel fallback into
  `DB_PASS` itself (that made every run look like an explicit `DB_PASS`).
- **Provenance for the script and recipe changes** (attribution, operator rule
  2026-10-01). Vendor-sourced items should be re-checked when the vendor changes;
  originated items are ours to test and evolve:
  - *Metadata DSN and password handling*: JuiceFS v1.3.0 (the pinned
    `juicedata/mount:ce-v1.3.0`), `docs/en/reference/how_to_set_up_metadata_engine.md`,
    section "PostgreSQL". It gives the DSN form
    `postgres://[username][:<password>]@<host>[:5432]/<database-name>[?parameters]`,
    says `search_path` must be in the connection string for a non-public schema
    (one schema only), and supports `META_PASSWORD` in place of an inline
    password. The same tree's
    `docs/en/administration/metadata/postgresql_best_practices.md`, "Passing
    sensitive information via environment variables", recommends `META_PASSWORD`.
    <https://github.com/juicedata/juicefs/tree/v1.3.0/docs/en>
  - *Role*: to JuiceFS the role is only the DSN username; the vendor docs do not
    choose one. `juicefs_meta` is PMOVES's scoped role
    (`pmoves/supabase/initdb/00_3_juicefs_meta_role.sql`), and
    `JUICEFS_META_PASSWORD` is its funnel slot
    (`JUICEFS_META_CREDENTIAL_RUNBOOK.md:22`). Role selection follows the PMOVES
    precedent `JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md:92-102` (name `META_ROLE`
    explicitly). The automatic pairing the Crush lane originated on 2026-09-22
    (PR #3150) was removed in favour of that precedent. The fail-loud refusal
    is Originated: B850-CLAUDE / nvme-3150-rebase, 2026-10-01 (no upstream
    precedent; checked: JuiceFS v1.3.0 metadata-engine and PostgreSQL
    best-practices docs, and the PMOVES JuiceFS runbooks).
  - *Redaction*: GNU grep manual, 2.1.2 Matching Control (`-F`/`--fixed-strings`:
    "Interpret patterns as fixed strings, not regular expressions"; `-v`); POSIX
    `grep -F`. <https://www.gnu.org/software/grep/manual/grep.html#Matching-Control>
  - *Env precedence*: `pmoves/scripts/with-env.sh:55` (`set -a`) and `:85` (loads
    `.env.local` last) are why a caller's `META_ROLE` is replaced. The wrapper form
    is with-env.sh's documented entry point (`:143`). The `JFS_SETUP_*`
    forwarding names: **Originated:** B850-CLAUDE / nvme-3150-rebase, 2026-10-01
    (no upstream precedent found; checked: every recipe in `pmoves/Makefile` and
    `pmoves/mk/*.mk` that calls with-env.sh).
  - *Stale-FUSE-endpoint guard*: the fix it prints (`sudo umount -l`) is the
    vendor's force unmount. JuiceFS v1.3.0
    `docs/en/administration/troubleshooting.md:201-202` ("Unmount error"): on
    Linux `juicefs umount --force` is translated to `umount --lazy`. It is
    spelled out because this host runs JuiceFS in a container and has no juicefs
    CLI. Also umount(8) `-l`, fusermount(1) `-u -z`. The observation that
    container-created mounts are absent from `/etc/mtab`: **Originated:** Crush
    lane, 2026-09-22, PR #3150, measured on Knuckles.
  - *Preflight output capture*: **Originated:** Crush lane, 2026-09-22, PR #3150.
    Upstream precedent was not searched in this pass.
  - *`--network ${JUICEFS_NETWORK:-host}`*: Docker docs (github.com/docker/docs
    @ main, 2026-10-01): `content/manuals/engine/network/drivers/bridge.md:49`
    "User-defined bridges provide automatic DNS resolution between containers",
    while host networking "shares the host's networking namespace"
    (`drivers/host.md:12-13`). So a mount that must reach the `minio` service by
    name joins the compose network.
  - *`DATA_DIR` must not fail silently*: Docker docs, "Bind mounts" > "Syntax":
    with `--volume`, a missing source "Docker automatically creates" as a
    directory. That it ends up root-owned follows from a rootful daemon creating
    it; this is inferred, not quoted.
  - *`JUICEFS_DATA_DIR` alias*: the name `make juicefs-mount-local` already reads
    (`pmoves/mk/egress.mk:395`).
- **Node shape in `pmoves/.env.local`** (gitignored, node-persistent):
  `JUICEFS_NAME=pmoves-media` (the live volume's name — the compose default
  `pmoves` fails format with "cannot update volume name"),
  `JUICEFS_NETWORK=pmoves_data` (host-network mounts cannot resolve the
  `minio` block store), `META_ROLE=juicefs_meta`,
  `DATA_DIR=/mnt/pmoves-nvme1/juicefs-data`.
- **Docs verification**: the upstream cache guide (JuiceFS v1.3.0
  `docs/en/guide/cache.md:232`, section "Cache directory") explicitly recommends a
  dedicated high-performance disk, never the system disk — the NVMe move is
  the documented pattern. `--cache-size` MiB semantics and `--free-space-ratio`
  confirmed; the measured bounds on NVMe1: 100 GiB cache of 3665 GiB free.
  The docs' "upload first, then commit" write path confirms the video-failure
  mechanism (I/O error at close) while the MinIO backend was down.
- **Mount verified live**: write test OK (205 MB/s), `restart: unless-stopped`,
  cache container-path `/data` backed by `/mnt/pmoves-nvme1/juicefs-data`.
  Videos (13 files, 79G) moving detached to `knuckles/downloads/`.

## Phases

### Phase 1 — Provision NVMe1 (operator hands, root)
```bash
# verify the device is the blank 4TB (no partitions):
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT /dev/nvme1n1
sudo bash deploy/provision/nvme-provision.sh \
  --device=/dev/nvme1n1 --mount=/mnt/pmoves-nvme1 \
  --role=creator-store --yes-really
```
Script: `deploy/provision/nvme-provision.sh`. GPT + ext4 `PMOVES-NVME1`, fstab
`nofail` by UUID, chown `$SUDO_USER`. Reconciled 2026-10-01 against Omarchy
(`omacom/omarchy-iso` @ 86c0778, `PMOVES-omarchy` @ 947e2fc) and the man pages,
with every step attributed in the script header and inline:
- **Root guard:** strips a btrfs subvolume suffix (omarchy
  `bin/omarchy-system-factory-reset:58`), walks PKNAME to the whole disk
  (omarchy-iso configurator:364-368), fails closed, and refuses the root disk
  and its partitions (`deploy/provision/format-usb.sh:46-50`). The earlier digit-strip
  missed btrfs/LUKS/LVM sources.
- **Re-runs:** a drive already carrying one ext4 `PMOVES-NVME1` partition exits 0
  "already provisioned". That check runs BEFORE the partitioned-device refusal;
  the old order refused its own result, so the earlier "idempotent" claim was
  false.
- **Partition name** read via omarchy-iso `partition_path` (`nvme1n1p1`, never
  `nvme1n11`).
- **New steps:** a `wipefs -af` on the new partition before mke2fs
  (configurator:726-729), and a `--dry-run` mode (configurator:686-692).
- **fstab:** the entry is matched on field 2 (fstab(5)), backed up, newline-guarded,
  then `systemctl daemon-reload` (systemd-fstab-generator(8)) and
  `findmnt --verify`.
- **Mount:** `mount -T <fstab> <mountpoint>` + `mountpoint -q` (mount(8),
  mountpoint(1), configurator:762-781), never `mount -a`.
- **Blank check, before any write (delta review P1):** refuses a target when
  the disk itself or anything on it carries a filesystem, RAID, LVM or crypto
  signature, or is mounted. It reads lsblk FSTYPE/MOUNTPOINTS plus a
  `blkid -p --no-part-details -u filesystem,raid,crypto,other` probe
  (blkid(8): the probe bypasses the cache). Before this, a disk holding a
  whole-disk filesystem or PV with no partition table was wiped. The root guard
  now takes EVERY disk under / (lsblk(8) `-s`/`--inverse`, plus the members
  sharing a btrfs root's filesystem UUID), so the second disk of an md, LVM or
  btrfs root is refused.
- **In use without a signature, and foreign partitions (review of 9339f5f52):**
  - a disk is refused if any child is not TYPE `part` (a plain dm-crypt or
    dm-linear mapping), or if a sysfs `holders` entry claims it or a partition
    (linux `block/holder.c:41-50` at tag v7.2, bd_link_disk_holder);
  - a lone partition resumes only if its GPT name (lsblk PARTLABEL) is the
    script's own label;
  - `blkid -p` exits other than 0/2 fail closed as root (blkid(8) EXIT STATUS);
  - a non-root `--dry-run` cannot run the probe, so it says INCONCLUSIVE and
    exits 3 instead of reporting the disk blank.
- **fstab preflight (final review):** a line that already uses the mountpoint is
  resolved to a device BEFORE any write: TAG=value specs via findfs(8), the
  `/dev/disk/by-*` names mapped to their tags, and other `/dev` paths via
  `readlink -f`. If it is not this script's partition, or it resolves to
  nothing, the script refuses before partitioning. Before this fix, a stale line
  left a formatted, unmounted disk. Equivalent specs for the same partition
  (`LABEL=`, `PARTUUID=`, `UUID=`, by-uuid) are accepted on adoption.
- **Ownership on re-runs:** an already-provisioned drive is re-owned only when
  `SUDO_USER` names a user. As plain root it is left alone.
- **Originated policy, kept:** refusing partitioned drives (except one
  unformatted partition from an interrupted run) and the 2 TB floor.
Covered by `pmoves/tests/scripts/test_nvme_provision.py` (stubbed tools only; no
disk is touched).

### Phase 2 — Creator pipeline onto NVMe1 (no root needed)
```bash
mkdir -p /mnt/pmoves-nvme1/comfyui-h3/{models,input,output,custom_nodes,user}
# seed from the pinokio H3 app's current dirs, then replace with symlinks:
for d in models input output custom_nodes user; do
  rsync -a ~/pinokio/api/minimax-h3-pinokio.git/app/$d/ /mnt/pmoves-nvme1/comfyui-h3/$d/
  rm -rf ~/pinokio/api/minimax-h3-pinokio.git/app/$d
  ln -s /mnt/pmoves-nvme1/comfyui-h3/$d ~/pinokio/api/minimax-h3-pinokio.git/app/$d
done
# re-download the H3 model set (~30-60G) via pmoves/tools/comfyui/install/ Aitrepreneur
# installers into /mnt/pmoves-nvme1/comfyui-h3/models (replaces the deleted volumes)
```

### Phase 3 — JuiceFS cache onto NVMe1 (make target, after video transfer completes)
```bash
docker rm -f juicefs-mount   # recreate path; the make target runs the container fresh
make -C pmoves juicefs-mount-local JUICEFS_DATA_DIR=/mnt/pmoves-nvme1/juicefs-data
make -C pmoves juicefs-mount-status
```
Lane change: `pmoves/mk/egress.mk` now honors `JUICEFS_DATA_DIR` (default unchanged:
`~/.local/share/juicefs-data`). `juicefs-cache-bounds.sh` already auto-scales
`--cache-size` to the measured drive — on a 3.6T drive the ~13G bound lifts to the
100G ceiling (drive-local fraction). Old root-disk cache dir can be removed once
the new mount is verified: `rm -rf ~/.local/share/juicefs-data`.

### Phase 4 — Omarchy seat on NVMe2 (operator hands; doctrine work starts here)
1. Boot the Omarchy install media (upstream ISO or `PMOVES-omarchy` install
   scripts), target **`/dev/nvme2n1` only**, keep NVMe1 untouched.
2. Validate the seat: Hyprland on the real R9700 (RDNA4/mesa), Ghostty, the
   agentic surfaces upstream ships (`AGENTS.md`, `CLAUDE.md`).
3. PMOVES layer per `UNATTENDED_NODE_BOOTSTRAP.md` §omarchy: Pinokio8 +
   `pmoves-fleet`/`pmoves-services` launchers (PMOVES-pinokio PR #12 pending),
   hermes-pmoves, community deployment class (self-host, local-model defaults).
4. **Fork work begins:** the `quattro` branch is a clean upstream mirror — the
   PMOVES unattended answer file + CHIT-aware bootstrap (secrets-funnel equivalent
   on Arch) land as PRs against `POWERFULMOVES/PMOVES-omarchy`, reviewed through
   this lane. NVMe1 (ext4) mounts into the new OS by UUID, the way Omarchy writes
   its own fstab (omarchy-iso `orchestrator/phases_impl.py:846-857`); a factory
   reset restores the installer's fstab, so the PMOVES layer must re-apply that
   line. JuiceFS remounts via
   the same make path; creator pipeline data survives the OS switch untouched.
5. Root disk becomes free for reassignment once the switch is proven (Docker
   migration lane, or full decommission of the Ubuntu seat).

### Phase 5 — Governance gap: Crush damage-control parity
- **Alignment first**: the cipher-token/launcher remediation is ALREADY in flight as
  the operator's lanes — PR #3145 (`feat/cipher-identity-bind`: per-agent cipher
  bearer bind in launchers, kimi TS_Z890 fix, mcp-project-roster.sh) and PR #3149
  (crush-pmoves parity). This lane does NOT duplicate them; the remaining local
  gap after those land is only the Crush-side damage-control hook port.
- Port the damage-control gate to Crush hooks (`crush.json` `hooks`, see the
  crush-hooks skill) so the blocked volume-removal class (Known Road
  `make -C pmoves volume-reset SERVICE=<name>`) is pattern-checked in this harness too, closing the gap this
  session's incident exposed.
- ~~Add a volume-removal pattern to the Claude Code guard~~: already present
  (`.claude/hooks/damage-control/patterns.yaml:306-320`, Known Road
  `make -C pmoves volume-reset SERVICE=<name>`), so nothing to add on that side.

### Phase 6 — Close out
- Verify: `df -h / /mnt/pmoves-nvme1`, `make -C pmoves juicefs-mount-status`,
  ComfyUI H3 smoke (render from `pmoves/tools/comfyui/workflows/`), JuiceFS
  videos readable at `~/pmoves-fs/knuckles/downloads/`.
- `make -C pmoves sign-trail`, `make -C pmoves register-release`.

## Risks / notes
- **Docker data-root stays on root this lane.** After the video move (~76G) and
  volume deletion (~60G), root holds ~144G free — adequate for the current stack;
  the Omarchy switch re-homes Docker anyway.
- Register/known-roads trail caveat stands (2026-09-19 NOTE): the trail records
  command strings, not authorized writes — the CLAIM row below records the
  incident explicitly rather than relying on any trail.
- Omarchy installer is interactive upstream; the unattended path is the fork's
  open item — Phase 4 step 1 may be manual on first iteration.
