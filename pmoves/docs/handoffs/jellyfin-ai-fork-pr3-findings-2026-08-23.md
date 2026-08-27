# Jellyfin-AI fork PR #3 — 7 review findings (2026-08-23)

**Status:** **HISTORICAL — RESOLVED. Do not action this as an open lane.**
Written 2026-08-23 as a brief for `POWERFULMOVES/Pmoves-Jellyfin-AI-Media-Stack#3`.
Both lanes closed the next day: fork PR #3 merged 2026-08-24 12:38Z, and
PMOVES.AI#2695 merged 2026-08-24 16:27Z, after which the gitlink advanced and
the ARM64 validation was recorded. The findings below are **already applied**.
Applying them again would re-edit fixed code.

Kept as a record of *why* the fixes were made — in particular the canonical-copy
decision in the next section, which is still load-bearing for anyone choosing
where to edit this stack.

**Domains needed (at the time):** `compose` (the stack's `docker-compose.yml`) and `dockerfile` (audio-processor, dashboard)

## Canonical copy — settled before touching anything

Three candidate paths existed. `pmoves/docker-compose.jellyfin-ai.yml` in PMOVES.AI#2695 resolves build contexts and volume mounts to:

```
${PMOVES_JELLYFIN_AI_ROOT:-../Pmoves-Jellyfin-AI-Media-Stack/Cataclysm_Provisioning_Bundle/provisioning_bundle/docker-stacks/jellyfin-ai}
```

So the **fork bundle** at `Cataclysm_Provisioning_Bundle/provisioning_bundle/docker-stacks/jellyfin-ai/` is canonical and is where all fixes land. The parent's `CATACLYSM_STUDIOS_INC/L4-PLATFORM/provisions/docker-stacks/jellyfin-ai/` copy is retired by #2695. The fork-root `docker-compose.yml` is a separate standalone stack file, not the build source.

## Findings

### P1-1 — duplicate YAML keys (verified)

`docker-compose.yml` defines `media-stack` twice under `networks:` (lines 6 and 9) and `environment:` twice in `audio-processor` (lines 118 and 127). Verified with a duplicate-detecting SafeLoader:

```
DUPLICATE KEYS: ['media-stack']
DUPLICATE KEYS: ['environment']
```

Compose v2 rejects duplicate mapping keys, so the file does not parse at all.

Both are verbatim copy-paste from the drift absorption. The **second** `environment:` block is a strict superset — it repeats the first seven vars and adds `NEO4J_USER`, `NEO4J_PASSWORD`, `QWEN_AUDIO_URL`, `PROCESSING_INTERVAL` — so removing the FIRST block preserves everything. The two `media-stack` blocks are identical.

### P1-2 — dashboard published port

The Dockerfile switched to `nginxinc/nginx-unprivileged`, which listens on **8080**, but this stack's compose still publishes `3001:80`. Requests reach an unused container port.

(PMOVES.AI#2695 already corrected the parent compose `8400:80` -> `8400:8080`; the fork's own compose was not updated.)

### P1-3 — FFmpeg archive is architecture-hardcoded

`audio-processor/Dockerfile` downloads the `linux64` archive unconditionally. On ARM64 nodes — Jetson and SPARK are both in this fleet — that installs x86-64 binaries, and because `/opt/ffmpeg/bin` precedes the system path, it shadows any architecture-native ffmpeg. Fails only on the ARM half of a split deployment.

### P1-4 — Redis default cannot resolve

`audio-processor/main.py` defaults `REDIS_HOST` to `jellyfin-redis`, but the compose service is `redis` and supplies no `REDIS_HOST`. `_init_clients` then disables caching silently, so every library item is re-analyzed and re-inserted on every pass.

### P2-5 — backup restore uses a container path as a host path

`scripts/jellyfin_backup.sh`: Jellyfin reports a backup `Path` under `/config` (container). The script uses it directly as a host directory, so restore copies into `/config/...` on the host or fails on permissions.

### P2-6 — runbook documents an unsupported flag

`jellyfin-ai-media-stack-guide.md` documents `--upload`; the script supports only `--no-upload` and uploads by default. The documented command always exits with `Unknown option for backup: --upload`.

### P2-7 — `--stack-root` does not recompute dependent paths

`ARCHIVE_DIR`, `JELLYFIN_CONFIG_PATH` and `JELLYFIN_CACHE_PATH` are derived from the script's original location before the override is applied, so `--stack-root` is silently partial.

## Verification plan

- duplicate-key SafeLoader scan returns clean
- `docker compose config` parses the stack
- dashboard `EXPOSE`/listen port matches the published mapping
- ffmpeg archive selection keyed on `TARGETARCH`/`uname -m`, both branches present
- `REDIS_HOST` default matches the compose service name
- backup script: restore path translated container -> host; `--stack-root` recomputes dependents
- runbook flag matches the script's actual option set
