# Whole-drive storage — Option A: SMB media (Jellyfin) + JuiceFS-on-N: (new/doc content)

**Date:** 2026-08-07  **Owner lane:** z890-claude (storage) + OPERATOR (elevated/vault/data-move)
**Decision (operator, 2026-08-07):** Option A — share existing media drives via SMB over Tailscale
for Jellyfin; use JuiceFS (MinIO-backed on N:) for **new** pipeline + doc content. Grounded in
measured capacities + official JuiceFS docs (see `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md`).

## Why this split (the capacity fact)
`I:` = 8.9T, **1.8T free** (7.1T of movies). JuiceFS stores data as **chunks in MinIO**, so
ingesting the existing 7.1T library needs 7T+ of *free* object-store space — z890's total free
across all drives (~3.5T) is **less than the library itself**. So existing media can't go on
JuiceFS without a dedicated 9TB+ disk. Existing full drives → SMB (zero-copy). JuiceFS → new
content that grows into the free space on **N:** (1.1T free).

## Measured state (2026-08-07)
- MinIO (`pmoves-minio-1`) backs to **`D:/pmoves-storage/minio`** via `MINIO_DATA_DIR` — but D: is
  94% full (249G). Compose already supports relocating it: `docker-compose.yml:1446`
  `${MINIO_DATA_DIR:-minio-data}:/data`.
- SMB shares already exist for `E, J, M, N` (+ `D:` as CATACLYSMSTUDIOS-NETWORK-DRIVE-4TB). **`I:` is
  NOT shared** (only the `I$` admin default).
- Movies at `I:\MOVIES`; music at `I:\BEATS BACKUP` (both confirmed present).
- Jellyfin media mount (`docker-compose.external.yml:236`) = `${JELLYFIN_MEDIA_DIR:-./data/jellyfin/media}:/media`
  — unset, so Jellyfin points at an empty repo path (why it's bare).

---

## Part A1 — SMB-share I: for cross-node media  *(OPERATOR, elevated)*
Match the existing E/J/M/N share pattern. Read-only for media is safest:
```powershell
# elevated PowerShell on z890:
New-SmbShare -Name "I" -Path "I:\" -ReadAccess "Everyone"
# (or scope -ReadAccess to a specific fleet account instead of Everyone)
```
Other nodes reach it over Tailscale: `\\<z890-tailscale-host>\I\MOVIES`. Tailscale encrypts the
transport; keep the share **read-only** so a remote node can't mutate the library.

## Part A2 — Jellyfin sees the movies  *(z890-claude wiring + OPERATOR Docker Desktop)*
1. **Docker Desktop file sharing** (OPERATOR): add `I:` to Docker Desktop → Settings → Resources →
   File Sharing (Docker Desktop can't bind a drive it hasn't been granted).
2. **Media dir** (config): set `JELLYFIN_MEDIA_DIR=I:/` so `I:\MOVIES` + `I:\BEATS BACKUP` mount at
   `/media`. Set it through the env pipeline (env.example/brand default → regen), **not** by hand-editing
   `env.shared`. Bind the real path directly — Docker Desktop does **not** traverse Windows junctions
   (a junction shows as one stub inside the container).
3. `make -C pmoves up-jellyfin` (or the jellyfin service target) → complete the Startup Wizard →
   add libraries pointing at `/media/MOVIES`, `/media/BEATS BACKUP`.
4. Cross-node Jellyfin (5090) instead mounts the A1 SMB share.

## Part A3 — JuiceFS content volume backed by N:  *(z890-claude design + OPERATOR vault + data-move)*
The "agents + users see/move files" cross-node volume, on N: (1.1T free), NOT the b850 file:// one.

1. **Relocate MinIO onto N:** (D: is full; this benefits everything). Set `MINIO_DATA_DIR=N:/pmoves-storage/minio`
   via the env pipeline. Stop MinIO, move `D:/pmoves-storage/minio` → `N:/pmoves-storage/minio`
   (`robocopy /E /MOVE`), `docker compose up -d --force-recreate minio` (OPERATOR: data-move + recreate).
2. **Format a fresh JuiceFS volume against that MinIO** (path-style bucket by Tailscale hostname,
   postgres meta, `META_PASSWORD`) — per `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` §2, but a NEW
   volume (e.g. `pmoves-content`) rather than reusing the empty b850 `pmoves-media`. OPERATOR vault:
   MinIO creds + Supabase-admin meta password.
3. **Mount cross-node via the Tailscale client:** nano-1 already has `/usr/local/bin/juicefs`; z890
   adds a POSIX mount. Prove the cross-node byte (write on z890, read on nano-1).
4. Growth: monitor N: — this volume grows with new pipeline/doc content; it does **not** hold the
   existing 7TB library (that stays on I: via SMB).

## What runs where
| Content | Mechanism | Where |
|---|---|---|
| Existing movies/music (7.1T) | **SMB over Tailscale** (read-only) | `I:` served from z890 |
| Jellyfin libraries | bind `I:` locally (z890) / SMB (other nodes) | z890 + fleet |
| **New** pipeline + doc content ("agents+users move files") | **JuiceFS** (MinIO on N:, postgres meta) | cross-node, tailnet |
| Backups | `Z:` (5090) | separate — not an object store |

## Split of labor
| Step | Owner | Gate |
|---|---|---|
| A1 SMB-share I: | OPERATOR | elevated PowerShell |
| A2.1 Docker Desktop share I: | OPERATOR | Docker Desktop setting |
| A2.2 JELLYFIN_MEDIA_DIR wiring | z890-claude | env pipeline (no secrets) |
| A3.1 MINIO_DATA_DIR→N: wiring | z890-claude | env pipeline (no secrets) |
| A3.1 MinIO data-move + recreate | OPERATOR | data-move |
| A3.2 juicefs format (new vol) | z890-claude *with* OPERATOR vault | MinIO + meta creds |
| A3.3 cross-node mount + prove | z890-claude | — |

## References
- `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` (the juicefs format/mount mechanics + META_PASSWORD)
- Official: JuiceFS local-storage = single-node; multi-drive needs MinIO/RAID/LVM or `--shards`; MinIO path-style bucket by DNS/hostname
- `project_jellyfin_wizard_never_completed`, `project_content_studio_storage_layout` (memory)
