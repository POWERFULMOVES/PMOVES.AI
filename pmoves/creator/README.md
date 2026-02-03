# PMOVES Creator Bundle

All ComfyUI-centric assets for WAN Animate, Qwen Image Edit+, and VibeVoice now live under `pmoves/creator/`. This bundle keeps the one-click installers, tutorial walkthroughs, and ready-to-import workflows that feed the creative n8n automations (`wan_to_cgp`, `qwen_to_cgp`, `vibevoice_to_cgp`).

## Directory Map

| Path | Contents | Notes |
| --- | --- | --- |
| `installers/` | One-click Windows/RunPod installers (`*.bat`, `*.sh`) for ComfyUI portable bundles, RVC helpers, FFmpeg, and supporting scripts. | Run from the render workstation; they lay down the portable ComfyUI stacks referenced in the tutorials. |
| `tutorials/` | Markdown guides (`*_tutorial.md`, `waninstall guide.md`, operator notes) plus supplemental write-ups (`imageedit.md`, `mumpitz*.md`). | Follow these before wiring the n8n webhooks; they define expected directories, prompts, and environment overrides. |
| `workflows/` | ComfyUI workflow exports (`*.json`) for WAN/Qwen/VibeVoice plus curated ADV Patreon graphs. | Import via ComfyUI Manager (Windows) or drop into `ComfyUI/input/graphs/` when using the portable builds. |
| `resources/ADV_Patreon/` | Additional ZIP-ready content (datasets, WAN LoRAs, workflow variants) referenced in the tutorials. | Keep this synced if you rely on Patreon-only graph updates. |

## One-Click Bring-Up Flow

Use this sequence on a clean render workstation (Windows portable bundles) or a RunPod host (the `*_RUNPOD.sh` installers). All paths assume the **ComfyUI portable** layout recommended in the tutorials.

1. **Prep the workspace**
   - Extract the official `ComfyUI_windows_portable` archive to a fast NVMe drive.
   - Launch `ComfyUI\update\update_comfyui.bat` once so the baseline runtime is current.
   - Confirm `git` and `python` resolve in PowerShell (`git --version`, `python --version`).
2. **Lay down the base application per workflow**
   - WAN Animate → `installers/WAN-ANIMATE-COMFYUI-MANAGER_AUTO_INSTALL.bat`
   - Qwen Image Edit+ → `installers/QWEN-IMAGE-EDIT-PLUS-COMFYUI-MANAGER_AUTO_INSTALL.bat`
   - VibeVoice / RVC → `installers/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat` then `installers/VIBEVOICE-WEBUI_INSTALLER.bat`
3. **Fetch custom nodes & models**
   - Run the matching `*-MODELS-NODES_INSTALL.*` script from inside `ComfyUI\` so the relative paths resolve.
   - WAN Animate (models + LoRAs) → `installers/WAN-ANIMATE-MODELS-NODES_INSTALL.bat`
   - Qwen Image Edit+ (quantization prompt) → `installers/QWEN-IMAGE-EDIT-PLUS-MODELS-NODES_INSTALL.bat`
   - VibeVoice (RVC models, Triton/SageAttention) → `installers/VIBEVOICE-RVC-NODES_INSTALL.bat`, optional `installers/install_triton_and_sageattention_auto.bat`
   - RunPod mirrors are available via the `*_AUTO_INSTALL-RUNPOD.sh` variants; execute with `bash` in the RunPod session.
4. **Run sanity checks**
   - Launch `ComfyUI\run_nvidia_gpu.bat` and confirm the Manager UI shows required nodes (KJNodes, WanVideoWrapper, ComfyUI-GGUF, etc.).
   - Validate Torch/CUDA visibility: `python_embeded\python.exe -c "import torch; print(torch.cuda.is_available())"`.
   - For audio flows, ensure `ffmpeg -hide_banner` works after `installers/FFMPEG-INSTALL AS ADMIN.bat` (requires elevated shell).
5. **Sync workflows & tutorials**
   - Import the JSON graphs from `workflows/` via ComfyUI Manager (or copy into `ComfyUI\input\graphs\`).
   - Walk through the matching guide in `tutorials/` to align prompts, MinIO bucket names, and expected webhook payloads.

> **PowerShell batch runner (optional)**  
> ```
> Set-Location 'C:\Creators\ComfyUI_windows_portable\ComfyUI'
> & '.\pmoves\creator\installers\WAN-ANIMATE-COMFYUI-MANAGER_AUTO_INSTALL.bat'
> & '.\pmoves\creator\installers\WAN-ANIMATE-MODELS-NODES_INSTALL.bat'
> ```
> Adjust the paths per workflow. Keep each script in the ComfyUI root so the relative downloads land in the correct folders.

### Mapping to n8n Creative Flows

| n8n Flow (`pmoves/n8n/flows/...`) | Required Installers | Key Outputs | Validation |
| --- | --- | --- | --- |
| `wan_to_cgp.webhook.json` | `WAN-ANIMATE-COMFYUI-MANAGER_AUTO_INSTALL.bat`, `WAN-ANIMATE-MODELS-NODES_INSTALL.bat` (or `*_RUNPOD.sh`) | `ComfyUI/output/wan/*.mp4`, uploaded via `PMOVES • Upload File Path (MinIO)` | Trigger the WAN tutorial test prompt and POST the resulting payload to the `wan_to_cgp` webhook (use `curl` or `make n8n-webhook-demo URL=http://localhost:5678/webhook/<workflowId>/webhook/wan-to-cgp`). |
| `qwen_to_cgp.webhook.json` | `QWEN-IMAGE-EDIT-PLUS-COMFYUI-MANAGER_AUTO_INSTALL.bat`, `QWEN-IMAGE-EDIT-PLUS-MODELS-NODES_INSTALL.bat` | `ComfyUI/output/qwen/*.png` with GGUF + lightning LoRAs | Run the “spot recolor” example, confirm Supabase row creation and Geometry Bus packet in hi-rag v2. |
| `vibevoice_to_cgp.webhook.json` | `VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat`, `VIBEVOICE-RVC-NODES_INSTALL.bat`, `VIBEVOICE-WEBUI_INSTALLER.bat`, `FFMPEG-INSTALL AS ADMIN.bat` | WAV renders under `outputs/audio/vibevoice/…` + Supabase metadata | Kick off the VibeVoice tutorial prompt and watch `vibevoice_to_cgp` publish geometry/audio events; Discord preview should arrive if the webhook is configured. |

Set the n8n environment variables (`SUPABASE_REST_URL`, `SUPABASE_SERVICE_ROLE_KEY`, MinIO bucket names, RVC storage keys) before activating the flows. See `pmoves/docs/PMOVES.AI PLANS/N8N_SETUP.md` for the full list.

### Offline Mirrors & Model Audits

Use `huggingface-cli` when you need to mirror the large model files ahead of time:

```
pip install --upgrade huggingface_hub
huggingface-cli download Aitrepreneur/FLX Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors --local-dir D:\Models\wan
```

The tables below summarize the URLs each installer hits so you can pre-stage downloads or verify hashes (`certutil -hashfile <file> SHA256` on Windows):

- **WAN Animate 2.2:** `clip_vision_h.safetensors`, `Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors`, `SeC-4B-fp16.safetensors`, `vitpose*.onnx`, `umt5-xxl-enc-bf16.safetensors`, etc.
- **Qwen Image Edit+:** `Qwen2.5-VL-7B-Instruct-UD-<quant>.gguf`, `Qwen-Image-Edit-2509-<quant>.gguf`, `Qwen-Image-Edit-Lightning-*.safetensors`, `qwen_image_vae.safetensors`, upscalers (`4x-ClearRealityV1.pth`, `RealESRGAN_x4plus_anime_6B.pth`).
- **VibeVoice / RVC:** RVC model archives (`RVC1006*.7z`), Triton/SageAttention wheels, FlashAttention/Torch 2.7.0 CUDA 12.8 wheels.

Document the mirror location in `pmoves/creator/resources/README.md` when you cache the bundles so future operators know where to pull from.

## Installing the Toolchains

Run the installers from `installers/` on the creative host. The table below mirrors the previous VibeVoice notes with updated paths.

| Installer | Purpose | n8n / Pipeline Signals |
| --- | --- | --- |
| `installers/VIBEVOICE-WEBUI_INSTALLER.bat` | Clones & launches the VibeVoice TTS WebUI; exposes webhook endpoints for audio renders. | Emits `voice_job_id` + storage paths used by the audio ingest flows. |
| `installers/VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat` | Installs ComfyUI portable with the VibeVoice node pack. Pair with `workflows/VIBEVOICE-RVC_VOICE_CLONING.json`. | Sends completion payloads (speaker metadata, storage URIs) to Supabase via the VibeVoice webhook. |
| `installers/VIBEVOICE-RVC-NODES_INSTALL.bat`, `installers/RVC_INSTALLER.bat` | Adds core RVC models/scripts consumed by the ComfyUI manager bundle. | Produces intermediate WAVs that n8n normalizes and publishes. |
| `installers/FFMPEG-INSTALL AS ADMIN.bat` | Installs FFmpeg system-wide on Windows render nodes. | Required when n8n invokes FFmpeg via `N8N_FFMPEG_PATH` to normalize audio. |
| `installers/QWEN-IMAGE-EDIT-*.{bat,sh}` | One-click installers for Qwen Image Edit+ (Windows + RunPod). | Prepares the ComfyUI environment expected by the Qwen webhook (`qwen_to_cgp`). |
| `installers/WAN-ANIMATE-*.{bat,sh}` | WAN Animate installers (portable ComfyUI, RunPod automation, models/nodes). | Aligns with `wan_to_cgp` payload structure; keep LoRAs in `resources/ADV_Patreon/wan2-1-loras`. |
| `installers/install_triton_and_sageattention_auto.bat` | Optional Triton/SageAttention acceleration helper used by multiple workflows. | Run after the base installer if you need faster inference on NVIDIA GPUs. |

### Environment Expectations (VibeVoice example)

- `SUPABASE_STORAGE_AUDIO_BUCKET` — Bucket where VibeVoice uploads audio renders.
- `VIBEVOICE_STORAGE_SERVICE_ROLE_KEY` — Supabase service-role key used by n8n to fetch protected files.
- `DISCORD_VOICE_WEBHOOK_URL` / `DISCORD_VOICE_WEBHOOK_USERNAME` — Webhook for preview clips.
- `N8N_FFMPEG_PATH` — Only needed if FFmpeg is not on `$PATH` inside the n8n container.

Configure these via `docker-compose.n8n.yml` or the n8n UI → Settings → Variables before activating the creative flows.

## Tutorials

Key walkthroughs live under `tutorials/`:

- `wan_animate_2.2_tutorial.md` — full WAN Animate install + workflow walkthrough.
- `qwen_image_edit_plus_tutorial.md` — ComfyUI + Qwen Image Edit+ setup and prompts.
- `vibevoice_tts_tutorial.md` — VibeVoice + RVC voice cloning pipeline.
- `waninstall guide.md`, `imageedit.md`, `mumpitz*.md` — supplemental notes, persona examples, installer tips.
- `vibevoice_operator_notes.md` — original operator-focused checklist for VibeVoice/RVC (migrated from the legacy README).

## Workflows

Import the `.json` workflows from `workflows/` using ComfyUI Manager or by dropping them into your `ComfyUI/input/graphs/` folder. The filenames track release dates and variants (e.g., `251007_MICKMUMPITZ_WAN-2-2-VID_ADV.json`). Keep them in sync with the tutorials and update MinIO bucket mappings in the nodes before running.

## Keeping Tutorials in Sync

When you update or add installers/tutorials:

1. Drop new assets into the appropriate subfolder.
2. Update this README with a short description and expected signals.
3. Review downstream documentation (Creator pipeline runbooks, smoke tests, service guides) so they reference `pmoves/creator/...`.

This keeps the creative toolchain discoverable for operators rolling out the n8n automations and Geometry Bus demos.
