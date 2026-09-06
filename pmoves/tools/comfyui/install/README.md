# MiniMax H3 ULTRA ComfyUI Installers

Three install paths for the **MiniMax H3 ULTRA** model stack, all from
Aitrepreneur. Pick the one that matches your host. **V3 set added 2026-09-06**
(see "V3 delta" below).

## Which installer do I use?

| Host | Script | What it does |
|------|--------|--------------|
| **RunPod pod** (CUDA 12.8 image) | `MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh` | One-shot: installs PyTorch 2.8.0+cu128, clones the 5 custom nodes, downloads all 6 model files (~30GB) with HF Xet acceleration + resume/recovery, final dependency check, launches ComfyUI |
| **RunPod pod** (V3, 2026-09) | `MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD-NEW-V3.sh` | V3 stack (int8 convrot engines, upscaler, SAM 3.1) |
| **Windows desktop / laptop** (NVIDIA GPU) | `MINIMAX_H3_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat` | One-click: downloads ComfyUI_windows_portable.7z, extracts, clones 5 custom nodes, downloads all 6 model files, launches `run_nvidia_gpu.bat` |
| **Windows already-installed ComfyUI** (operator wants to add H3 to existing setup) | `MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat` | Idempotent: locks the current pip env, adds 5 custom nodes with safe dep sanitization, downloads only the missing H3 model files. Flags: `/update` (pull latest), `/force` (reinstall), `/dryrun` (preview), `/restore` (rollback to last freeze) |
| **Windows V3 variants** | `*-V3.bat` | Same paths for the V3 stack |
| **Windows, optional speed-up** (RTX 30/40/50) | `OPTIONAL_SAGEATTENTION-INSTALLER.bat` | Companion to the H3 installers: pulls DazzleML's pinned comfyui-triton-and-sageattention v0.8.10, installs the best Triton/SageAttention wheel for the detected GPU, backs up the normal launcher and creates `run_nvidia_gpu_SAGEATTENTION.bat`. Run AFTER an H3 main installer. The V3 workflow patches SageAttention at 11 sites (`PathchSageAttentionKJ`) — this is how a Windows host earns that speedup. |

## V3 delta (2026-09-06)

The V3 workflow set (`../workflows/*-V3.json`) is a production pipeline, not an
incremental update: **356 nodes**, 11-stage sampling, 12 resolution selectors,
11 video-combine outputs, SageAttention patched at 11 sites, and three new
models over V1 — `minimax_h3_latent_upscaler_3d_fp16` (3D latent upscaling),
`sam3.1_multiplex_fp16` (subject segmentation), and the audio VAE — with the
FL2VA/REF2VA/Qwen3VL engines moved to **int8 convrot** pruned builds.
Full manifest in `../workflows/README.md`.

**SPARK (GB10, arm64 sm_121) bring-up** is staged separately: the `.bat` path
is Windows/RTX-only; the Linux equivalent is DazzleML's pinned Python
installer plus arm64-Blackwell Triton wheels — same class of fight as the
torch-cu128 preinstall (#2871). Jetson combiner feeding (JONS Whisper INT8 /
YOLO / phi3 preprocess → SPARK H3) rides the pmoves.agent.task.v1 wire.

**Read `ATTRIBUTION.md` first** for the model file list, the pinned dependency
versions, and the `HF_TOKEN` requirement (the Aitrepreneur/FLX repo is gated).

## Quick start (RunPod)

```bash
# SSH into a RunPod CUDA 12.8 pod
git clone https://github.com/POWERFULMOVES/PMOVES.AI.git
cd PMOVES.AI
bash pmoves/tools/comfyui/install/MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh
# ~30 min later: ComfyUI launches, models downloaded, H3 ready
```

## Quick start (Windows desktop)

```cmd
REM From an empty folder (NOT inside an existing ComfyUI install):
pmoves\tools\comfyui\install\MINIMAX_H3_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat
REM ~30 min later: ComfyUI launches via run_nvidia_gpu.bat
```

## Quick start (Windows, add to existing ComfyUI)

```cmd
cd C:\path\to\ComfyUI_windows_portable\ComfyUI
..\..\..\pmoves\tools\comfyui\install\MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat
```

## After install: pointing Mavis at the host

Once ComfyUI is running (default `http://localhost:8188`), the Mavis client
(`pmoves/tools/comfyui_client.py`) connects automatically using these env vars
(overrides available):

- `PMOVES_COMFYUI_URL` (default `http://localhost:8188`)
- `PMOVES_COMFYUI_TIMEOUT_S` (default 600)
- `PMOVES_COMFYUI_WORKFLOW` (default `pmoves/tools/comfyui/workflows/MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json`)

## Custom node required

The H3 ULTRA workflows depend on `ComfyUI-Spectrum-MiniMax-H3` (cloned from
`xmarre/ComfyUI-Spectrum-MiniMax-H3` by all three installers). If you're
installing on an existing ComfyUI and the custom node didn't get added, clone
it into `custom_nodes/` and `pip install -r custom_nodes/ComfyUI-Spectrum-MiniMax-H3/requirements.txt`.

## Why these specific scripts

The Aitrepreneur installers are the most-tested H3 install path in the
community (the YouTube tutorial has 170K subscribers). The RunPod script
specifically handles the model download with HF Xet + safe resume (critical
for the ~30GB model bundle), and the Windows safe installer is the only path
that protects your existing pip env via a `pip_blacklist.list` + constraint
lock. Pinokio has its own H3 launcher, but it doesn't pin the deps as
strictly, which is why we ship the Aitrepreneur scripts as the canonical
install path and use Pinokio only for the launch surface.
