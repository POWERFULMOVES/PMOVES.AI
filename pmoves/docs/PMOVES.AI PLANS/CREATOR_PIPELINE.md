# PMOVES v5 • Creator Pipeline (ComfyUI → MinIO → Webhook → Supabase → Indexer → Publisher)
_Last updated: 2025-12-14_

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
Before running ComfyUI graphs that upload into this pipeline, confirm the local workstation has the GPU bundle, helper tools, and multimedia codecs expected by the automation scripts that ship with this repo. Follow the [one-click bring-up flow](../../creator/README.md#one-click-bring-up-flow) first, then verify the dependencies below.

| Dependency | Install Script | Key Notes | Validate |
| --- | --- | --- | --- |
| **RVC Voice Conversion bundle** | [`RVC_INSTALLER.bat`](../../creator/installers/RVC_INSTALLER.bat) | Script prompts for GPU target (`[1] NVIDIA` vs `[2] AMD/Intel`) and pulls the matching `RVC1006*.7z` from Hugging Face. Falls back to the NVIDIA archive if the prompt is skipped. Uses the system 7-Zip install to extract and launches `go-web.bat` on completion. | `nvidia-smi` (NVIDIA) or `wmic path win32_VideoController get name` (AMD/Intel) to confirm the GPU; `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"` inside the RVC env to verify CUDA alignment. |
| **7-Zip** | [`VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`](../../creator/installers/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat) | `:ensure_7zip` checks `%PATH%`, `Program Files`, then silently installs `7z%SEVEN_VER%-x64.exe` if absent so other bundles (RVC, ComfyUI portable) can extract archives. | `"%ProgramFiles%\7-Zip\7z.exe" -h` or `7z --help` to verify CLI availability. |
| **Git for Windows** | [`VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`](../../creator/installers/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat) | `:ensure_git` installs `Git-%GIT_VER%-64-bit.exe` silently when `git --version` fails, ensuring ComfyUI custom nodes can be cloned. | `git --version` should return `2.45.0.windows.1` (or later). |
| **Python 3.11 + uv** | [`VIBEVOICE-WEBUI_INSTALLER.bat`](../../creator/installers/VIBEVOICE-WEBUI_INSTALLER.bat) | Requires a system Python 3.11 to create `.venv`, then installs `uv` before pinning `torch==2.7.0` (CUDA 12.8 wheels), `triton-windows`, and FlashAttention. Make sure PATH points at Python 3.11 before running. | `python --version` → `3.11.x`; `uv --version`; `python -m pip show torch` to confirm `2.7.0+cu128`. |
| **FFmpeg (system-wide)** | [`FFMPEG-INSTALL AS ADMIN.bat`](../../creator/installers/FFMPEG-INSTALL%20AS%20ADMIN.bat) | Must be launched from an **elevated** Windows shell—script checks `net session` and aborts without admin rights. Downloads the Gyan.dev essentials ZIP to `%USERPROFILE%\Documents\ffmpeg`, expands it, and appends `...\bin` to the machine PATH via PowerShell. | `ffmpeg -hide_banner` should print version info. If it fails, re-run the installer as admin or confirm `%PATH%` contains the FFmpeg `bin`. |

> ⚠️ If you rerun these scripts after a GPU driver upgrade or Python reinstall, delete any previously extracted portable folders so the silent installers can rehydrate cleanly.

### Dependency sanity check before ComfyUI uploads
- Verify ComfyUI can launch the portable bundle (`run_nvidia_gpu.bat`) without module errors.
- In the ComfyUI Python prompt, confirm CUDA visibility: `python_embeded\python.exe -c "import torch; print(torch.cuda.is_available())"`.
- Run `ffmpeg -encoders | findstr h264` (Windows) to ensure encoding support for video workflows.
- Run `uv pip list` inside the VibeVoice virtual environment to ensure uv-installed packages are resolvable before rendering or voice conversion nodes execute.

### Creative Tutorials & Automation Hooks
- Tutorials and installers live under `pmoves/creator/` (WAN Animate 2.2, Qwen Image Edit+, VibeVoice TTS, WAN installer notes). Follow them to seed ComfyUI graphs and audio pipelines; they are prerequisites for the upcoming creative automations.
- Shipping n8n flows live in `pmoves/n8n/flows/` today:
  - `health_weekly_to_cgp.webhook.json` (Wger sync → `health.weekly.summary.v1`)
  - `finance_monthly_to_cgp.webhook.json` (Firefly sync → `finance.monthly.summary.v1`)
  - `wger_sync_to_supabase.json` and `firefly_sync_to_supabase.json` (baseline upsert helpers)
- Creative WAN/Qwen/VibeVoice flows ship under `pmoves/n8n/flows/wan_to_cgp.webhook.json`, `qwen_to_cgp.webhook.json`, and `vibevoice_to_cgp.webhook.json`. Pair them with the tutorials so the ComfyUI outputs post straight into Supabase and hi-rag v2.
- Persona-to-movie automation will combine WAN + VibeVoice flows with persona prompt templates (Supabase `persona_prompts`) to storyboard, voice, and animate PMOVES avatars. Until those flows land, use the tutorials plus `tools/integrations/events_to_cgp.py` to push manual CGPs for QA.
- Scheduling: when flows are active, use n8n cron nodes or ComfyUI Manager webhooks to trigger daily persona drops.

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

## Creator tool bundles

### QWEN image-edit bundle
- **One-click installers:**
  - Linux/RunPod: [`QWEN-IMAGE-EDIT-AUTO_INSTALL-RUNPOD.sh`](./PMOVES%20ART%20STUFF/QWEN-IMAGE-EDIT-AUTO_INSTALL-RUNPOD.sh)
  - Windows (ComfyUI Manager import): [`QWEN-IMAGE-EDIT-COMFYUI-MANAGER_AUTO_INSTALL (1).bat`](./PMOVES%20ART%20STUFF/QWEN-IMAGE-EDIT-COMFYUI-MANAGER_AUTO_INSTALL%20(1).bat)
  - Windows (models + nodes only): [`QWEN-IMAGE-EDIT-MODELS-NODES_INSTALL (1).bat`](./PMOVES%20ART%20STUFF/QWEN-IMAGE-EDIT-MODELS-NODES_INSTALL%20(1).bat)
- **Models pulled:** Qwen2.5-VL 7B instruct GGUF pair (mmproj + UD `MODEL_VERSION`, defaults to `Q8_0`), Qwen Image Edit UNet GGUF, Qwen VAE, Lightning LoRAs (8-step and 4-step), and upscale helpers (4x-ClearRealityV1, RealESRGAN_x4plus_anime_6B).
- **Custom nodes cloned:** ComfyUI-Manager, ComfyUI-GGUF, rgthree-comfy, ComfyUI-Easy-Use, ComfyUI-KJNodes, UltimateSDUpscale, ComfyUI_essentials, wlsh_nodes, comfyui-vrgamedevgirl, RES4LYF, ComfyUI-Crystools.
- **Installer toggles:**
  - `INSTALL_ALL_NODES=true` to pip install every node requirement instead of the curated list.
  - `ALLOW_SAM2=true` if you need Impact-Pack’s SAM2 support (forces Torch ≥ 2.5.1; disabled by default to keep CUDA 12.1 builds stable).
  - `MANAGER_ENABLE_MATRIX=true` if you rely on ComfyUI-Manager’s Matrix bridge (disables the urllib3<2 pin). Leave `false` for standard creator machines.
- **Manual finalize steps:** The RunPod script auto-runs constrained pip installs for `RES4LYF` and `ComfyUI-Crystools`. If you add extra nodes, rerun `manual_finalize_node "<folder>"` (defined in the script) after editing their requirements to respect the shared Torch/OpenCV pins.
- **Graph import:** Use ComfyUI-Manager → *Install Workflow* and point at the shared `.json` exports in this folder for the ready-made Qwen edit graph.
- **Output tagging before upload/webhook:**
  - Apply a `workflow:qwen-image-edit` tag plus `medium:image` and the active LoRA (e.g., `lora:qwen-lightning-8step`).
  - Include any palette/style keywords used in your prompt (e.g., `style:neon`, `mood:moody`).
  - Set the filename to `<creator>-<concept>-<YYYYMMDD>.png` so downstream namespace + slug math stays deterministic.

### VibeVoice + RVC voice bundle
- **One-click installers:**
  - All-in-one Windows portable ComfyUI: [`VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat)
  - Existing ComfyUI add-on: [`VIBEVOICE-RVC-NODES_INSTALL.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-RVC-NODES_INSTALL.bat)
  - Standalone VibeVoice WebUI launcher: [`VIBEVOICE-WEBUI_INSTALLER.bat`](./PMOVES%20ART%20STUFF/VIBEVOICE-WEBUI_INSTALLER.bat)
  - Local RVC voice-cloning toolkit: [`RVC_INSTALLER.bat`](./PMOVES%20ART%20STUFF/RVC_INSTALLER.bat)
- **Custom nodes cloned:** ComfyUI-Manager, rgthree-comfy, Enemyx-net VibeVoice-ComfyUI (multi-speaker + VibeVoice-Large graph components), and diodiogod TTS-Audio-Suite for file handling/transcoding.
- **Voice/WebUI helpers:** `RVC_INSTALLER.bat` prompts for GPU family (NVIDIA vs AMD/Intel) before pulling the matching 7z package and launching `go-web.bat`. Pair this with the VibeVoice WebUI installer if you want a browser-based TTS front-end instead of Comfy-only graphs.
- **Graph import:** The provided [`VIBEVOICE-RVC_VOICE_CLONING.json`](./PMOVES%20ART%20STUFF/VIBEVOICE-RVC_VOICE_CLONING.json) includes pre-wired TTS → RVC conversion → `SaveAudio VibeVoice` nodes. Import via ComfyUI-Manager or drop into `ComfyUI/input/graphs/`.
- **Output tagging before upload/webhook:**
  - Tag with `workflow:vibevoice-tts`, `medium:audio`, and the speaker/model (e.g., `voice:vibevoice-large`, `voice:rvc-<alias>`).
  - Capture language or emotion toggles you applied (`lang:en`, `tone:warm`).
  - Use filenames like `<creator>-<character>-take<##>.wav` to keep MinIO keys sortable and to tie back to Supabase revisions.

## Workflow metadata → pipeline mapping

### Image-edit (QWEN) expectations
- **Bucket / keying:** Upload finished PNGs to `outputs` with `key_prefix=comfy/qwen/<creator_handle>/` so Studio and Publisher can derive namespaces without manual overrides.
- **Namespace convention:** Use `pmoves.art.<creator_handle>` unless the render belongs to a campaign; in that case append the project slug (`pmoves.art.darkxside.nightmarket`). Namespaces become part of the Jellyfin directory path, so keep them lowercase and `.`-delimited.
- **Webhook payload:**
  - Required: `bucket`, `key`, `s3_uri`, `presigned_get`, `title`, `namespace`, `author`, `tags` (comma-separated in-node → array server-side).
  - Optional but recommended: `graph_hash` (ComfyUI Manager shows this) to anchor reproducibility, and `auto_approve=true` only when QA has already signed off on batch outputs.
- **Tag hygiene:** Convert prompt metadata into structured tags—`model:qwen2.5-vl-7b`, `sampler:lightning-8step`, `resolution:2048x2048`. The Indexer reads these tags when building search facets.
- **Post-upload check:** Verify the `PMOVES • Completion Webhook → Supabase` node response echoes `"status": "submitted"`. If you expect instant approvals, set `RENDER_AUTO_APPROVE=true` in the environment or toggle the node’s `auto_approve` boolean.

### Voice/TTS (VibeVoice + RVC) expectations
- **Bucket / keying:** Route WAV/FLAC renders through `PMOVES • Upload File Path (MinIO)` into `outputs/audio/vibevoice/<creator_handle>/`. Keep extensions consistent with the codec you export; Comfy’s SaveAudio node defaults to WAV (`audio/wav`).
- **Namespace convention:** Prefix audio drops with `pmoves.audio.<creator_handle>` and optionally suffix the IP/character (`pmoves.audio.darkxside.voidpunk`). Audio namespaces must stay in sync with Jellyfin libraries for auto-refreshes.
- **Webhook payload:**
  - Required: `bucket`, `key`, `s3_uri`, `presigned_get`, `title`, `namespace`, `author`, `tags`.
  - Recommended fields for audio: embed `tags` such as `duration:90s`, `bpm:120`, `tts:enabled`, `rvc:model-rvc1006` so downstream orchestrations can branch (e.g., auto-generate lyric cards).
  - If the workflow exported multiple takes, call the webhook once per asset so each Supabase row maps 1:1 with a MinIO object. Include `graph_hash` only when the Comfy graph matches the default `VIBEVOICE-RVC_VOICE_CLONING.json` to fast-track diffing later.
- **Manual finalize:** When you extend the bundle with extra audio effect nodes, rerun `VIBEVOICE-RVC-NODES_INSTALL.bat` so their requirements get pinned alongside VibeVoice. For RVC WebUI-based conversions, remember to manually upload the converted WAV through the Comfy graph (or drag-drop into Comfy’s input folder and use `Upload File Path`) before triggering the webhook.
- **Publishing reminder:** Audio artifacts won’t auto-approve—double-check `RENDER_AUTO_APPROVE` or manually flip the Supabase row once the mix passes review. Jellyfin refresh uses the namespace path, so keep naming consistent before approving.

## Geometry Bus & Avatar Playback
- Domain events (health + finance) already ship `geometry.cgp.v1` packets through `services/common/cgp_mappers.py`, so constellations appear in the Geometry UI as soon as the flows fire. Set `CHIT_PERSIST_DB=true` and supply Postgres creds if you want Supabase to store the packets for replay.
- Creative webhooks (WAN/Qwen/VibeVoice) automatically transform payloads into `geometry.cgp.v1` packets via the n8n flows; use `tools/integrations/events_to_cgp.py` only for manual backfills or legacy payloads.

### VibeVoice (realtime TTS) runtime options
- **Preferred (creator workstation / Pinokio):** follow `pmoves/docs/ARTSTUFF/realtime/README.md` and point Flute at it via `VIBEVOICE_URL=http://host.docker.internal:<PORT>`.
- **Optional (Docker profile, pulls weights):** `make -C pmoves up-vibevoice` runs the service from `pmoves/docker-compose.voice.yml` (profile: `voice`). For in-Docker routing, set `VIBEVOICE_URL=http://vibevoice:3000`.

### Ultimate TTS Studio (SUP3R Edition) UI (creator workstation)
- If you want a unified voice UI (multiple engines including VibeVoice), use:
  - `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition` (typically via Pinokio).
  - See `pmoves/docs/ARTSTUFF/Ultimate-TTS-Studio-SUP3R-EditionREADME.md`.
- Treat this as a creator-workstation tool that emits audio artifacts into the same pipeline (upload → webhook → Supabase → n8n → CHIT/publisher).
- PMOVES avatars: the Supabase table `persona_avatar` (namespace, persona_slug, avatar URIs, geometry_constellation_id, meta) now ships via migration `2025-10-20_persona_avatar.sql`. Populate rows with WAN outputs and matching geometry IDs to light up the Avatars panel (`make -C pmoves web-geometry`). Coordinate with the Geometry UI repo on any additional columns before extending the schema.
- Demo (current stack): trigger `make -C pmoves demo-health-cgp`, `make -C pmoves demo-finance-cgp`, and fire the creative webhooks (`wan-to-cgp`, `qwen-to-cgp`, `vibevoice-to-cgp`). Open the Geometry UI to inspect constellations with jump links. Record screenshots or CGP exports in `pmoves/docs/logs/` for regression tracking.

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
