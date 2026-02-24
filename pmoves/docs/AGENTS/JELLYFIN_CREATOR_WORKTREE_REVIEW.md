# Jellyfin Creator Worktree Review
_Last updated: 2026-02-24_

## Objective
Run a production-grade review for the Creator pipeline where PMOVES.YT, Jellyfin, CHIT/Geometry, Supabase, Neo4j, TensorZero, GPU Orchestrator, and transcribe-and-fetch stay in parity across local and promotion branches.

## Worktree Setup
Use an isolated worktree for review/patches:

```bash
git worktree add ../PMOVES.AI-jellyfin-review -b review/jellyfin-creator-parity
```

Inside the worktree:

```bash
cd ../PMOVES.AI-jellyfin-review
make -C pmoves jellyfin-stack-prod
make -C pmoves jellyfin-stack-prod-verify
```

## Team Lanes
### Lane A — Runtime/Topology (Codex)
- Scope: compose wiring, network parity, endpoint health, env contracts.
- Files: `pmoves/docker-compose.yml`, `pmoves/docker-compose.jellyfin-ai.yml`, `pmoves/env.jellyfin-ai.example`, `pmoves/Makefile`.
- Required checks:
  - `make -C pmoves jellyfin-stack-prod`
  - `make -C pmoves jellyfin-verify`
  - `make -C pmoves jellyfin-parity-audit`

### Lane B — PMOVES.YT ↔ Jellyfin bridge (Claude)
- Scope: mapping/linking/playback path, extractor stability, smoke parity.
- Files: `pmoves/services/pmoves-yt/yt.py`, `pmoves/docs/PMOVES.AI PLANS/JELLYFIN_BRIDGE_INTEGRATION.md`, `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/PMOVES_YT.md`.
- Required checks:
  - `make -C pmoves yt-jellyfin-smoke`
  - endpoint probes: `8093`, `8077`, `8300`

### Lane C — Unified Auth + CHIT Graph (BoTZ)
- Scope: JWT unification and CHIT attestation through BoTZ gateway.
- Branch owner: Claude (see `C:\Users\russe\.claude\plans\twinkly-roaming-star.md`).
- Required outcome:
  - BoTZ gateway validates Supabase JWT and emits graphiti-signed trail events.
  - PMOVES lane references BoTZ PR and verifies parity assumptions remain true.

### Lane D — Source Expansion (transcribe-and-fetch + BoTZ)
- Scope: ingestion lanes for SoundCloud + Google Drive into Creator pipeline.
- SoundCloud path: onboard sources using `pmoves/tools/register_media_source.py` with `--platform soundcloud`.
- Google Drive path: mount/sync lane into Jellyfin media root (rclone/drive-sync), then route through PMOVES ingest events.

## Merge Order
1. Lane A (runtime/topology + prod stack targeting)
2. Lane B (bridge + extractor stability)
3. Lane C (BoTZ unified auth + CHIT attestation PR)
4. Lane D (source expansion)

## Release Gate (must be green)
```bash
make -C pmoves jellyfin-stack-prod-verify
```

If production dependencies are intentionally offline, use:
```bash
make -C pmoves jellyfin-parity-audit
```
and attach an explicit risk note to the PR reviewer section.

