# VibeVoice / RVC Operator Notes

_Updated for n8n audio capture flows_

The installers in this bundle bootstrap the tools that emit VibeVoice/RVC render events. When you set up the n8n audio capture workflows, make sure these utilities are in place and expose the expected environment variables/webhooks.

## Tooling Map

| Installer | Purpose | n8n Signals |
| --- | --- | --- |
| `VIBEVOICE-WEBUI_INSTALLER.bat` | Clones and launches the VibeVoiceTTS WebUI. Use its webhook integration to emit `voice_job_id` + storage paths into Supabase. | Emits `voice_job_id`, `voice_storage_path` metadata consumed by `vibevoice_audio_ingest`. |
| `VIBEVOICE-RVC-COMFYUI-MANAGER_AUTO_INSTALL.bat` | Installs ComfyUI with the VibeVoice node pack. Configure the ComfyUI workflow (`VIBEVOICE-RVC_VOICE_CLONING.json`) to POST completion payloads to Supabase. | Supplies render payload + speaker metadata. |
| `VIBEVOICE-RVC-NODES_INSTALL.bat` / `RVC_INSTALLER.bat` | Adds the core RVC models and helper scripts used by the ComfyUI manager install. Ensure they output converted `.wav` files to the bucket referenced below. | Provides raw audio assets for FFmpeg conversion. |
| `FFMPEG-INSTALL AS ADMIN.bat` | Installs FFmpeg on Windows render hosts. The CLI is invoked by n8n during the ingest flow to normalize audio. | Must align with `N8N_FFMPEG_PATH` if you override the binary location. |

## Environment Expectations

Expose these variables to the n8n container (Settings → Variables or Compose env block):

- `SUPABASE_STORAGE_AUDIO_BUCKET` — Matches the bucket the installers upload to. Configure VibeVoice exports to target the same bucket.
- `VIBEVOICE_STORAGE_SERVICE_ROLE_KEY` — Service-role key used by n8n to read the protected audio assets.
- `DISCORD_VOICE_WEBHOOK_URL` — Voice-enabled webhook that receives the preview clip.
- `DISCORD_VOICE_WEBHOOK_USERNAME` — Optional; sets the sender name for preview posts.
- `N8N_FFMPEG_PATH` — Only required if FFmpeg lives outside `$PATH` inside the n8n container.

## Webhook Targets

- **Supabase REST** — Point the VibeVoice completion webhook at `http://host.docker.internal:54321/rest/v1/studio_board` with the service role key in both `apikey` and `Authorization` headers.
- **Discord Voice Preview** — Share `DISCORD_VOICE_WEBHOOK_URL` with the n8n `vibevoice_discord_preview` flow. This webhook must be separate from the text embed webhook used by `echo_publisher`.

Keeping these scripts aligned with the n8n configuration ensures each VibeVoice render produces a Supabase row the ingest flow can transcode and publish.
