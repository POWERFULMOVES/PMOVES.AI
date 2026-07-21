# Media Hosting + Cross-Stack Data — MinIO→JuiceFS + Jellyfin over Tailscale

**Status:** plan for review (read-only research). **Lane:** JuiceFS-core is **Z890's** (`AGNOTE4482PHI.t1.md:1058`, `[[project_supabase_multinode_juicefs_vision]]`) — coordinate, don't claim it. Claim the **media/publisher/Jellyfin** lane.

## Why now
MinIO is **EOL (archived Feb 2026)** — already flagged in `pmoves/docker-compose.yml:1281`. JuiceFS replacing it is fixing an acknowledged problem, not a greenfield want. `POWERFULMOVES/PMOVES-juicefs` fork exists but is **not wired** (no submodule, no compose, no code refs). Design already specced in `research/SUPABASE_SYNC_HANDOFF_2026-06-09.md:58-86` + `pmoves/docs/architecture/FLEET_ACCESS_NATS_HUB.md`.

## MinIO consumer map (blast radius)
- **boto3 (already S3-generic, dual-read `S3_ENDPOINT`/`AWS_*`):** presign (`services/presign/api.py:22-40`), ffmpeg-whisper (`server.py:292-337`), pdf-ingest. → **env-only repoint.**
- **minio-SDK (S3-protocol, hardcoded `MINIO_*` names):** comfy-watcher (`watcher.py:140-191`, creator artifacts → `pmoves-comfyui`), publisher (`publisher.py:1152-1207`, the S3→Jellyfin seam), pmoves-yt (`YT_BUCKET`), AgentGym. → **env-only repoint.**
- Buckets: assets, outputs, cataclysm-*, pmoves-comfyui, agentgym-*.

## JuiceFS integration — two modes
- **Mode A (drop-in):** JuiceFS **S3 gateway** as a replacement endpoint. boto3 = true env swap; minio-SDK = env swap (SDK is S3). **Spike-verify the only 2 non-trivial S3 features:** presign `generate_presigned_post` (`presign/api.py:184-200`) + comfy-watcher `presigned_get_object` (`watcher.py:191`) — JuiceFS gateway is an S3 *subset*. Don't claim 100% MinIO parity.
- **Mode B (the prize):** JuiceFS **POSIX mount** shared by artifact store + Jellyfin media. `publisher`'s `fget_object()` download (`publisher.py:1187`) collapses to a hardlink/path-ref → **zero-copy publish, fleet-wide media visibility.**

## Tailscale exposure (mesh-private, no Funnel)
- **Jellyfin (:8096):** Tailscale **Serve** → `https://<node>.<tailnet>.ts.net` (members-only); set `JELLYFIN_PublishedServerUrl` to the MagicDNS URL.
- **JuiceFS gateway:** **sidecar** pattern (`network_mode: service:ts-juicefs`, `tag:storage`, ephemeral key) per `FLEET_ACCESS_NATS_HUB.md:85-115` — sidesteps the internal-net DNAT bug class. Grant `tag:pmoves → tag:storage`.
- **ACL prereq:** add `tag:storage`/`tag:hub`/`tag:inference` to `tagOwners` in `pmoves/configs/tailscale-acl-policy.json` FIRST (else tagged auth keys are rejected). Re-tag is destructive/staged/operator-gated.

## Clients
Web UI (zero-install, any tailnet browser) + native Jellyfin apps (Android/iOS/AndroidTV/FireTV/Roku/Kodi/Media Player) on tailnet devices pointed at the MagicDNS URL. `jellyfin-bridge` = read/search facade (complements `publisher` = writes).

## PMOVES.YT + creator flow
ComfyUI → comfy-watcher → MinIO `pmoves-comfyui` + NATS `artifact_uri: s3://…`; PMOVES.YT → `YT_BUCKET`, transcode via ffmpeg-whisper. On `content.publish.approved.v1`, **publisher** fetches → Jellyfin media dir → library refresh. Mode A keeps `s3://` URIs (gateway-resolved, zero pipeline change); Mode B = same JuiceFS mount, publisher hardlinks.

## Phased plan (Z890-coordinated)
0. **Decide (Z890):** metadata engine (Postgres-in-tier-data vs Redis); keep MinIO as JuiceFS blob backend initially (handoff §5.3). Land `tag:storage` in tagOwners.
1. **Augment (Mode A):** stand up JuiceFS+gateway behind `ts-juicefs`; spike presign-POST + presigned-GET; repoint one test consumer.
2. **Migrate consumers** via `make secrets-funnel` (env repoint), bucket-by-bucket: presign→ffmpeg-whisper→pdf-ingest→pmoves-yt→comfy-watcher→publisher→AgentGym. MinIO stays as backend.
3. **Mode B media path:** mount JuiceFS into publisher+Jellyfin; refactor publisher to hardlink (watch PUID/PGID + inotify on JuiceFS).
4. **Tailscale:** Serve Jellyfin, sidecar JuiceFS.
5. **Replace EOL MinIO backend** (Garage/SeaweedFS/external S3) — consumers insulated (they see gateway/mount only).

**Top risks:** MinIO EOL (Phase 5); JuiceFS S3 gateway ≠ full MinIO (presign-POST/ACL/multipart — Phase 1 gate); ACL tagOwners ordering; Z890 lane collision (claim register); cutover consistency (bucket-by-bucket, never big-bang).
