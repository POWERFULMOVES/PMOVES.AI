# PMOVES v5 • Creator Pipeline (ComfyUI → MinIO → Webhook → Supabase → Indexer → Publisher)
_Last updated: 2025-09-11_

This doc shows the end‑to‑end creative flow from **ComfyUI** render to **Discord/Jellyfin** publish.

## Overview
1. **ComfyUI** renders an image/video.
2. **Presign microservice** issues PUT/GET URLs for MinIO/S3.
3. **ComfyUI nodes** upload the asset to MinIO (`s3://outputs/comfy/...`).
4. **Render Webhook** posts a completion to `/comfy/webhook`.
5. **Supabase** gets a new `studio_board` row (`submitted` or `approved`).
6. **n8n** notifies reviewers; on approval, **Indexer** ingests → Qdrant/Meili/Neo4j.
7. **Publisher** emits `content.published.v1`, posts **Discord embed**, and refreshes **Jellyfin** (optional).

## Prerequisites & Quick Validation
Before running ComfyUI graphs that upload into this pipeline, confirm the local workstation has the GPU bundle, helper tools, and multimedia codecs expected by the automation scripts that ship with this repo.

| Dependency | Install Script | Key Notes | Validate |
| --- | --- | --- | --- |
| **RVC Voice Conversion bundle** | [`PMOVES ART STUFF/RVC_INSTALLER.bat`](./PMOVES%20ART%20STUFF/RVC_INSTALLER.bat) | Script prompts for GPU target (`[1] NVIDIA` vs `[2] AMD/Intel`) and pulls the matching `RVC1006*.7z` from Hugging Face. Falls back to the NVIDIA archive if the prompt is skipped. Uses the system 7-Zip install to extract and launches `go-web.bat` on completion. | `nvidia-smi` (NVIDIA) or `wmic path win32_VideoController get name` (AMD/Intel) to confirm the GPU; `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"` inside the RVC env to verify CUDA alignment. |
| **7-Zip** | [`PMOVES ART STUFF/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat) | `:ensure_7zip` checks `%PATH%`, `Program Files`, then silently installs `7z%SEVEN_VER%-x64.exe` if absent so other bundles (RVC, ComfyUI portable) can extract archives. | `"%ProgramFiles%\7-Zip\7z.exe" -h` or `7z --help` to verify CLI availability. |
| **Git for Windows** | [`PMOVES ART STUFF/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat) | `:ensure_git` installs `Git-%GIT_VER%-64-bit.exe` silently when `git --version` fails, ensuring ComfyUI custom nodes can be cloned. | `git --version` should return `2.45.0.windows.1` (or later). |
| **Python 3.10 + uv** | [`PMOVES ART STUFF/VIBEVOICE-WEBUI_INSTALLER.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-WEBUI_INSTALLER.bat) | Requires a system Python 3.10 to create `.venv`, then installs `uv` before pinning `torch==2.7.0` (CUDA 12.8 wheels), `triton-windows`, and FlashAttention. Make sure PATH points at Python 3.10 (not 3.11+) before running. | `python --version` → `3.10.x`; `uv --version`; `python -m pip show torch` to confirm `2.7.0+cu128`. |
| **FFmpeg (system-wide)** | [`PMOVES ART STUFF/FFMPEG-INSTALL AS ADMIN.bat`](./PMOVES%20ART%20STUFF/FFMPEG-INSTALL%20AS%20ADMIN.bat) | Must be launched from an **elevated** Windows shell—script checks `net session` and aborts without admin rights. Downloads the Gyan.dev essentials ZIP to `%USERPROFILE%\Documents\ffmpeg`, expands it, and appends `...\bin` to the machine PATH via PowerShell. | `ffmpeg -hide_banner` should print version info. If it fails, re-run the installer as admin or confirm `%PATH%` contains the FFmpeg `bin`. |

> ⚠️ If you rerun these scripts after a GPU driver upgrade or Python reinstall, delete any previously extracted portable folders so the silent installers can rehydrate cleanly.

### Dependency sanity check before ComfyUI uploads
- Verify ComfyUI can launch the portable bundle (`run_nvidia_gpu.bat`) without module errors.
- In the ComfyUI Python prompt, confirm CUDA visibility: `python_embeded\python.exe -c "import torch; print(torch.cuda.is_available())"`.
- Run `ffmpeg -encoders | findstr h264` (Windows) to ensure encoding support for video workflows.
- Run `uv pip list` inside the VibeVoice virtual environment to ensure uv-installed packages are resolvable before rendering or voice conversion nodes execute.

## Services
- Presign: `pmoves-v5/services/presign` (port 8088)
- Render Webhook: `pmoves-v5/services/render-webhook` (port 8085)
- Supabase CE + PostgREST: profiles `data`
- Indexer: profile `workers`
- Publisher: profile `workers`
- n8n: profile `orchestration`

## .env (excerpt)
```
# Presign
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
ALLOWED_BUCKETS=assets,outputs
PRESIGN_SHARED_SECRET=change_me

# Render Webhook
RENDER_WEBHOOK_SHARED_SECRET=change_me
RENDER_AUTO_APPROVE=false

# Publisher enrichments
PUBLISHER_NOTIFY_DISCORD_WEBHOOK=...
PUBLISHER_REFRESH_ON_PUBLISH=true
PUBLISHER_EMBED_COVER=true
```

## Compose snippets
- `compose-presign-snippet.yml`
- `compose-render-webhook-snippet.yml`

```
docker compose --profile data up -d presign
docker compose --profile orchestration up -d render-webhook
```

## ComfyUI graph (minimal)
```
[Generate Image] → [PMOVES • Upload Image (MinIO)] → [PMOVES • Completion Webhook → Supabase]
```

Node inputs:
- Upload Image: `bucket=outputs`, `key_prefix=comfy/`, `filename=<your-name>.png`
- Completion Webhook: `s3_uri`, `presigned_get` (from Upload node), `title`, `namespace=pmoves`, `author=DARKXSIDE`, `tags`

## Approve → Publish
- In Supabase Studio, set `status=approved` (or use `RENDER_AUTO_APPROVE=true`).
- Indexer will ingest; Publisher will post to Discord and link/refresh Jellyfin.
- Audit breadcrumbs are stored in `publisher_audit`.

## Publisher Audit Trail & Incident Playback

Every approval event that reaches the Publisher now lands in the Supabase table `publisher_audit`. The row is keyed by the incoming `content.publish.approved.v1` event ID and captures reviewer context, where the artifact ended up, and whether processing succeeded or failed.

| Column | Notes |
| --- | --- |
| `publish_event_id` | UUID of the inbound approval envelope (`content.publish.approved.v1`). Primary key for the audit row. |
| `approval_event_ts` | Timestamp from the approval envelope. Useful for ordering alongside Supabase row history. |
| `correlation_id` | Correlation chain identifier so you can pivot back to upstream renders or review bots. |
| `artifact_uri` | Original MinIO/S3 URI received from the approval event (may be `NULL` on malformed events). |
| `artifact_path` | Absolute path where the Publisher wrote the file. Set even on download failures so you know the intended target. |
| `namespace` | Logical namespace used for slug + directory derivation. |
| `reviewer` / `reviewed_at` | Reviewer identity (pulled from payload/meta) and when they approved. Falls back to the envelope timestamp if no explicit approval time is present. |
| `status` | `published` or `failed`. Failures include `failure_reason` with the exception string from the publisher. |
| `published_event_id` / `published_at` | Envelope data for the downstream `content.published.v1` emission when it succeeds. |
| `public_url` | Publicly accessible URL recorded for Discord/Jellyfin consumption. |
| `processed_at` / `updated_at` | When the publisher handled the event. These auto-update on retries/upserts. |
| `meta` | JSON payload containing the source `meta`, resolved slug/namespace, Jellyfin refresh notes, pipeline `stage`, etc. |

**Indexes:** `status`, `artifact_path`, `namespace`, `reviewer`, and `processed_at` are indexed for quick forensics across large backlogs.

**Stage breadcrumbs:** `meta->>'stage'` shows which portion of the pipeline handled or failed the event (`validate`, `parse_uri`, `download`, `telemetry`, `persist_rollup`, `emit_event`, `published`). Failures without explicit exception text are labeled `unspecified failure` for audit completeness.

### Playback workflow when something goes wrong

1. **Identify the event** – grab the `publish_event_id` (from logs or n8n) or filter by `artifact_path`/`namespace`:
   ```sql
   select *
   from publisher_audit
   where publish_event_id = '...';
   ```
2. **Check status, failure_reason, and stage** – if the row is `failed`, inspect `failure_reason` alongside `meta->>'stage'` to see which portion of the publisher (`download`, `telemetry`, `emit_event`, etc.) blew up. Jellyfin refresh hiccups appear under `meta->>'jellyfin_refresh_error'`.
3. **Rehydrate the artifact** – use `artifact_uri` to pull from MinIO/S3 (e.g., `mc cp`) or inspect the partially written file at `artifact_path` if the download finished.
4. **Follow the correlation chain** – `correlation_id` lets you query upstream services (render webhook, indexer) for matching entries or envelopes.
5. **Replay downstream effects** – on successful publishes, the `published_event_id`/`published_at` pair helps confirm what Discord/Jellyfin saw. Use the ID to search the NATS event log or your monitoring sink for the emitted envelope.
6. **Document the resolution** – once fixed, upsert a new audit row (same `publish_event_id`) with status `published`. The trigger keeps `updated_at` current so auditors can see when the replay happened.

Because the audit table is append-friendly (via upsert on `publish_event_id`), replays are straightforward: re-run the publisher with the same approval payload and it will overwrite the row with the latest status while preserving the original timestamps for comparison.
