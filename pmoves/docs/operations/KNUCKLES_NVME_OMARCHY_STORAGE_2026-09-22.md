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
`POWERFULMOVES/PMOVES-omarchy` branch `quattro` is currently a **byte-identical
mirror of upstream** — the unattended-install answer file is the open item this
lane begins.

## Incident on record (pre-lane, same session)

An unguarded `docker volume rm` deleted the five `pmoves_comfyui-*` named volumes
(~60G: downloaded H3 models + any rendered outputs; outputs are **not** recoverable,
models re-download via `pmoves/tools/comfyui/install/` Aitrepreneur installers).
Root causes: (1) Crush sessions run **without** the Claude Code damage-control
hooks — this harness had zero hooks configured; (2) the bash hook patterns
deliberately exclude `docker rm` from the `rm -rf` net, and `docker volume rm`
has no pattern of its own. Remediation is Phase 5. Videos (~79G, 13× `PXL_*.mp4`)
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

5. **Dead image pins on main block cold bootstrap of the core overlay:**
   - `supabase/studio:2026.08.03-sha-022b374` — pruned from Docker Hub (weekly
     tag churn). Repinned in this lane to `2026.06.03-sha-0bca601` (the
     running-known-good on B850, verified present upstream).
   - `minio/minio` — **the entire Docker Hub repository is deleted** (EOL
     executed; tags API 404s). Identical release verified live on
     `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`; default registry
     repinned in-lane. This is also why MinIO had been down on this node.
6. **JuiceFS write failures were three stacked faults**, not one: (a) the
   `juicefs_meta` role password rotated in-place under the 2-day-old mount;
   (b) the block-store backend (`minio:9000` = the JuiceFS S3 gateway /
   MinIO service) was entirely down; (c) host-network mounts cannot resolve
   in-network service names. Fixes: role password reset to the canonical CHIT
   value (verified), MinIO repinned to Quay + gateway stack restarted, mount
   recreated on the docker network with NVMe1 cache backing.
7. **Supabase fork dependabot wave**: 13/15 PRs landed (admin squash under
   strict linear-history protection, operator-directed); #13 + #30 remain
   CONFLICTING after `@dependabot rebase` requests — pending dependabot's
   rebase; close before promoting the fork gitlink.

### Durability pass — verified against JuiceFS upstream docs (2026-09-22 ~20:00)

The mount now reproduces from a PLAIN `make juicefs-cross-node-setup
JUICEFS_HOST=supabase-db` with zero session knowledge, verified end-to-end
after three script hardenings (all in both the lane worktree and the node
checkout, destined for the lane PR):

- **Role/credential pairing** (`scripts/juicefs-cross-node-setup.sh`): the
  fallback credential IS `juicefs_meta`'s password; when it arrives via
  `JUICEFS_META_PASSWORD` and no role was named, `META_ROLE` now pairs
  automatically. Previously the script defaulted `supabase_admin` and the
  mismatched pair always failed auth.
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
  `scripts/with-env.sh`, so node-shape vars resolve from `.env.local`.
- **Node shape in `pmoves/.env.local`** (gitignored, node-persistent):
  `JUICEFS_NAME=pmoves-media` (the live volume's name — the compose default
  `pmoves` fails format with "cannot update volume name"),
  `JUICEFS_NETWORK=pmoves_data` (host-network mounts cannot resolve the
  `minio` block store), `META_ROLE=juicefs_meta`,
  `DATA_DIR=/mnt/pmoves-nvme1/juicefs-data`.
- **Docs verification**: upstream cache guide explicitly recommends a
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
Script: `deploy/provision/nvme-provision.sh` (format-usb.sh conventions: refuses
root disk, refuses partitioned devices, <2TB guard, `--yes-really` gate,
idempotent re-runs). GPT + ext4 `PMOVES-NVME1`, fstab `nofail`, chown `$SUDO_USER`.

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
   this lane. NVMe1 (ext4) mounts into the new OS by label; JuiceFS remounts via
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
  crush-hooks skill) so `docker volume rm`-class commands are pattern-checked in
  this harness too — closing the gap this session's incident exposed.
- Add a `docker volume rm` pattern (with Known Road pointer) to
  `.claude/hooks/damage-control/patterns.yaml` so the Claude Code side catches it
  as well.

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
