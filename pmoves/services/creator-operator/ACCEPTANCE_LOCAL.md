# Creator Operator Lattice — Local UI Acceptance (slice 1, image)

The `requires_ui` tests in `tests/test_integration_ui.py` are the **one piece that
must run on real hardware**. This is the LOCAL, **no-API-key** runbook for the
4090 (or any ≥16 GB-VRAM NVIDIA node). It drives the *real* ComfyUI UI with the
`comfy-operate-image` skill via the chrome-devtools MCP and harvests the
`POST /prompt` graph.

## What it runs (all local weights — verified against the installers)
Source: `PMOVES-Creator/installs/IDEOGRAM_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat`.
- **ComfyUI portable** `v0.24.0` (comfyanonymous/ComfyUI windows portable nvidia 7z).
- **Custom nodes:** ComfyUI-Manager, rgthree-comfy, ComfyUI-KJNodes, ComfyUI_essentials.
- **Models** (`Comfy-Org/Ideogram-4` + Aitrepreneur/FLX rehost — HF `license:other`):
  - `models/diffusion_models/ideogram4_fp8_scaled.safetensors`
  - `models/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors`
  - `models/text_encoders/gemma4_e4b_it_fp8_scaled.safetensors`
  - `models/text_encoders/qwen3vl_8b_fp8_scaled.safetensors`
  - `models/vae/flux2-vae.safetensors`
- **Workflow:** `installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json`.
- **Launch:** `run_nvidia_gpu.bat` → ComfyUI at `http://127.0.0.1:8188`.

> License gate: these are LOCAL weights, but the HF license is `other` (not
> confirmed commercial-OK) — so this is **try-locally / BYO at the user's edge**.
> The L3 `requires_ack` gate stays on; never bake into the hosted/commercial path
> (swap to `Qwen/Qwen-Image`, Apache-2.0). See `pmoves/config/creator_models.yaml`.

## Step 1 — bring ComfyUI up (heavy, one-time; ~tens of GB)
Run the existing 1-click installer (it downloads ComfyUI portable + the nodes +
the model set, then launches):
```
PMOVES-Creator\installs\IDEOGRAM_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat
```
If ComfyUI is already installed, instead drop
`IDEOGRAM_ULTRA-MODELS-NODES_INSTALL.bat` into `ComfyUI_windows_portable\ComfyUI`
and run it (models-only path). OOM on a 16 GB card → add launch args
`--reserve-vram 2 --cache-none` (per the LTX note in `installs/LTX-2.3.md`).
Confirm `curl http://127.0.0.1:8188/system_stats` returns JSON.

## Step 2 — drive the operator (the agent's job; no key needed)
With ComfyUI up at `:8188`, a chrome-devtools operator run (guided by
`.claude/skills/comfy-operate-image/SKILL.md`):
1. `navigate_page` → `http://127.0.0.1:8188`.
2. Load `installs/IDEOGRAM_ULTRA_WORKFLOW-V2.json` (Workflow → Open, or drag).
3. Set the exposed knobs (`prompt`, `seed`) — narrate each from `knobs.json`.
4. **Queue Prompt.**
5. `list_network_requests` → the `POST /prompt`; `get_network_request` → save the
   request body as `api_prompt`. **This harvest fires at queue-time, before
   execution — so it succeeds even on a cold/partial model cache.**
6. Poll `GET /history/{prompt_id}`; fetch the output image.
7. `assemble_result(workorder_id, artifact=…, api_prompt=…, transcript=…)`.

## Step 3 — assert (the acceptance)
On the 4090 with ComfyUI up:
```
set CREATOR_UI_TEST=1
PYTHONPATH=pmoves/services/creator-operator python -m pytest ^
  pmoves/services/creator-operator/tests/test_integration_ui.py -v
```
Acceptance = the live run returns `status=ok` + a **non-null** harvested
`api_prompt`, and that `api_prompt` **replays headless** via `POST /prompt`
(yields an equivalent image). The harvested `api_prompt` is the recipe that later
feeds the server-side headless path — teach-via-UI now, replay-via-API later.

## Partial acceptance (no model download)
The **harvest half** can be proven without the multi-GB model set: bring up bare
ComfyUI, load the workflow, Queue Prompt, and capture the `POST /prompt` payload.
Execution then errors on the missing weights, but `api_prompt` is real — proving
L1 (operator drives the UI) + the harvest mechanic. The **artifact half** needs
the local weights from Step 1.

## RunPod (not used here; settings = local-config reference)
`installs/LTX-2-3-AUTO_INSTALL-RUNPOD.sh` / `CITRON_ANIMA_LORA_TRAINER-RUNPOD-V2.sh`
encode the same setup for a cloud 24 GB pod (port 3000 manager / 8888 files /
7860 webui, `--reserve-vram` / `--cache-none` OOM args). We run local, but those
scripts are the reference for env vars, model dirs, and OOM flags.
