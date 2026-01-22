# comfyui — Integration Guide

ComfyUI powers the Creator pipeline renders (WAN Animate, Qwen Image Edit+, VibeVoice/RVC). The runtime is provisioned **outside** docker-compose; operators launch it on their render workstations and connect to PMOVES via MinIO + n8n webhooks.

## Bring-Up Checklist

1. **Clone / extract ComfyUI portable** to a fast local drive.
2. **Follow the one-click installer sequence** documented in [`pmoves/creator/README.md`](../../creator/README.md#one-click-bring-up-flow).
   - Run the `*_COMFYUI-MANAGER_AUTO_INSTALL` scripts to lay down the base bundles.
   - Execute the matching `*-MODELS-NODES_INSTALL` scripts (from within the ComfyUI root) to fetch Hugging Face models and node repos.
   - Install FFmpeg (`FFMPEG-INSTALL AS ADMIN.bat`) if you plan to emit audio through the VibeVoice flow.
3. **Import the workflow graphs** from `pmoves/creator/workflows/` and review the matching tutorials under `pmoves/creator/tutorials/`.
4. **Seed environment variables** (MinIO buckets, Supabase keys, Discord webhooks) in n8n before activating the creative flows.

### Model Mirrors

When operating offline or on air-gapped render nodes, pre-download the models with `huggingface-cli` and document the mirror path in [`pmoves/creator/resources/README.md`](../../creator/resources/README.md). The installers expect the same directory structure described in the creator README.

### n8n Integration

The following flows rely on the ComfyUI outputs to publish geometry + metadata into Supabase:

| Flow | Payload | Notes |
| --- | --- | --- |
| `wan_to_cgp.webhook.json` | WAN Animate mp4 + metadata | Requires WAN 2.2 models + LoRAs. |
| `qwen_to_cgp.webhook.json` | Qwen Image Edit+ png + prompt tags | Choose quantization in the installer based on GPU RAM. |
| `vibevoice_to_cgp.webhook.json` | VibeVoice WAV + speaker metadata | Needs RVC + FFmpeg on the render node. |

Use the webhook URL format `http://localhost:5678/webhook/<workflowId>/webhook/<slug>` when testing manually. The IDs appear in n8n → Workflows → Open Flow → Trigger panel.

### Verification

- Launch `ComfyUI\run_nvidia_gpu.bat`; ensure CUDA is detected (`python_embeded\python.exe -c "import torch; print(torch.cuda.is_available())"`).
- Run a sample prompt from each tutorial and confirm the corresponding Supabase row appears (bucket/key, geometry payload).
- For audio, inspect the Discord preview to ensure FFmpeg normalization succeeded.

## Reference Docs

- [CREATOR_PIPELINE](../../PMOVES.AI%20PLANS/CREATOR_PIPELINE.md)
- [CREATOR_PIPELINE_TO_CHIT](../../PMOVES.AI%20PLANS/CREATOR_PIPELINE_TO_CHIT.md)
- [COMFYUI_MINIO_PRESIGN](../../PMOVES.AI%20PLANS/COMFYUI_MINIO_PRESIGN.md)
- [N8N_SETUP](../../PMOVES.AI%20PLANS/N8N_SETUP.md)
