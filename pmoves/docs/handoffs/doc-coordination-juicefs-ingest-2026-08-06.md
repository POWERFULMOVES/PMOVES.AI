# Handoff → Mavis-5090 + Crush (bring node docs into the shared JuiceFS)

**From:** z890-claude (active)  **To:** Mavis-5090 (5090 lane) + Crush (SPARK)
**Date:** 2026-08-06  **Lane:** #6 doc-coordination product — real content

The cross-node JuiceFS is **proven and live** (z890 serves it on the tailnet). Any tag:pmoves
node can mount it and every other node sees the files instantly. Bring the scattered
benefit/grant docs into it so all three agents share one view.

## The shared FS (already running on z890)
- Metadata (redis): `redis://z890:6379/1` (no auth)
- Object store (MinIO): `http://z890:9000` (creds baked into fs metadata — clients
  need only the redis URL)
- fs name `pmoves`, UUID `fb41c173…`

## Proposed folder layout (the doc-coordination structure)
```
/docs/SEAP/       ← 5090: C:\Users\russe\Downloads\SEAP (self-employment assistance)
/docs/benefits/   ← SPARK: Epson-scanned unemployment-site docs
/docs/receipts/   ← grocery receipts to feed Firefly III
/docs/grant/      ← PMOVES Care grant materials
```

## Mavis-5090 — mount JuiceFS on Windows, move SEAP in
1. Install **WinFsp** (https://winfsp.dev) + **juicefs.exe** (juicedata/juicefs releases).
2. `juicefs.exe mount redis://z890:6379/1 J: --background`
3. `robocopy "C:\Users\russe\Downloads\SEAP" "J:\docs\SEAP" /E` (copy first; delete source
   only after you confirm it shows on z890).
NOTE: needs the 5090 to reach z890 over the tailnet (tag:pmoves — it is). z890-claude cannot
do this leg directly — `claude-pmoves` SSH is **not authorized on the 5090** (only 4090+jetsons).
Operator can authorize the fleet key on the 5090 if you'd rather z890-claude drive it.

## Crush (SPARK, Linux/ARM64) — scanned docs in
1. Install client: `curl -sSL https://d.juicefs.com/install | sh -` (or the ARM64 binary).
2. `sudo juicefs mount redis://z890:6379/1 /mnt/pmoves-jfs -d`
3. Drop the Epson scans into `/mnt/pmoves-jfs/docs/benefits/`.

## YT persona analysis — NOT needed, already done (context)
`pmoves/docs/research/DARKXSIDE_PLAYLIST_ANALYSIS_2026-07-28.md` (2,028 videos, YouTube Data
API v3 OAuth — proper PMOVES.YT method) exists and feeds `persona/08_darkxside_persona.md`.
That lane is Mavis-5090's and is complete; only a *refresh* (playlist grew since 07-28) remains.
