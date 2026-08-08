# MiniMax H3 ULTRA ComfyUI Installers

Three install paths for the **MiniMax H3 ULTRA** model stack, all from
Aitrepreneur. Pick the one that matches your host.

## Which installer do I use?

| Host | Script | What it does |
|------|--------|--------------|
| **RunPod pod** (CUDA 12.8 image) | `MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh` | One-shot: installs PyTorch 2.8.0+cu128, clones the 5 custom nodes, downloads all 6 model files (~30GB) with HF Xet acceleration + resume/recovery, final dependency check, launches ComfyUI |
| **Windows desktop / laptop** (NVIDIA GPU) | `MINIMAX_H3_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat` | One-click: downloads ComfyUI_windows_portable.7z, extracts, clones 5 custom nodes, downloads all 6 model files, launches `run_nvidia_gpu.bat` |
| **Windows already-installed ComfyUI** (operator wants to add H3 to existing setup) | `MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat` | Idempotent: locks the current pip env, adds 5 custom nodes with safe dep sanitization, downloads only the missing H3 model files. Flags: `/update` (pull latest), `/force` (reinstall), `/dryrun` (preview), `/restore` (rollback to last freeze) |

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
