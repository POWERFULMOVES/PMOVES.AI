# MiniMax-H3 (NVFP4) ComfyUI Installer — 5090 / Blackwell

Installs the **MiniMax-H3** audio+video generation models (NVFP4 quant) plus the
3 workflow-support node packs, against **either** runtime:

- the in-tree **PMOVES-Creator** fork (native H3 nodes), or
- the operator's **Pinokio** ComfyUI fork.

Both scripts are **parametric on `COMFY_ROOT`** (set it, or run from the ComfyUI root):

| Script | Host | Options (env) |
|--------|------|---------------|
| `MINIMAX-H3-MODELS-NODES_INSTALL.bat` | Windows (5090) | `H3_PROFILE`, `INSTALL_TAIL`, `COMFY_ROOT` |
| `MINIMAX-H3-AUTO_INSTALL-RUNPOD.sh` | Linux / RunPod | same + torch-stack pins |

> Sources below were **byte-exact verified** against the HF file index on
> 2026-08-09 (`hf_fs` listings + each repo's `SHA256SUMS`). Where a claim could
> not be confirmed it is marked UNVERIFIED — nothing is guessed.

## Why NVFP4 (Blackwell)

The RTX 5090 (Blackwell, sm_120) has native FP4. The **NVFP4** UNET builds are
**10.86 GiB** each vs **20.94 GiB** for INT8-ConvRot — a verified **48% cut**,
consistent with the halving claim (block-scaled NVFP4, not AWQ; covers all 208
main + token-refiner matrices). Peak VRAM is **sequential residency** — the
~24.6 GiB encoder is unloaded before the UNET samples, so it is **not** a sum and
fits 32 GB.

## H3 nodes are NATIVE — only 3 packs are cloned

The H3 nodes ship in the PMOVES-Creator fork at `comfy_extras/nodes_minimax_h3.py`
(`EmptyMiniMaxH3LatentAV`, `MiniMaxH3ImageToVideo` = t2va/fl2va,
`MiniMaxH3ReferenceToVideo` = ref2va, `MiniMaxH3SigmaShift`); INT8/ConvRot layouts
live in `comfy/quant_ops.py`. They load in **stock ComfyUI** (commit `14b05228`)
with no core patch. **There is no H3 custom node to install.** The installer clones
only the workflow-support packs:

- `rgthree-comfy` · `ComfyUI-KJNodes` · `ComfyUI-VideoHelperSuite`

## Filenames are FREE — no renaming

ComfyUI's H3 loaders select from **dropdowns**, so the on-disk filename does not
matter. The installer keeps each file's **real repo name** and only flattens the
`hf download` repo-subpath into the target `models/` subdir.

> **Do not** chase the `minimax_h3_fl2va_pruned_int8_convrot.safetensors` name from
> the original brief — that string is **UNVERIFIED / likely nonexistent**. The
> `*_pruned_*` naming family traces to a *different, structurally different* repo
> (`Winnougan/MiniMax-H3-INT4_Convrot_ComfyUI`, pruned **W4A8**). Do not mix
> families. DmitryDB's NVFP4 files retain all 50 transformer blocks (not pruned).

## Verified model sources

### UNETs + VAEs — `DmitryDB/MiniMax-H3-ComfyUI-Quants`

| File (repo path) | Size | → dir |
|---|---:|---|
| `FL2VA/MiniMax-H3_FL2VA-NVFP4.safetensors` | 10.862 GiB | `models/diffusion_models` |
| `Ref2VA/MiniMax-H3_Ref2VA-NVFP4.safetensors` | 10.862 GiB | `models/diffusion_models` |
| `vae/MiniMax-H3_VideoVAE-FP16.safetensors` | 4.850 GiB | `models/vae` |
| `vae/MiniMax-H3_AudioVAE-FP32.safetensors` | 0.564 GiB | `models/vae` |

Profiles present: `NVFP4` (10.86 GiB, 8–12 GB class), `NVFP4-HQ` (13.60 GiB, 16–24 GB
class), and three `INT8-ConvRot` profiles (20–22 GiB, RTX 30/40). Set `H3_PROFILE`
to switch (default `NVFP4`). License on these files is the **MiniMax-H3 community
license** (not Apache).

### Encoder — `OTMFLY/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot`

| File | Size | → dir | Status |
|---|---:|---|---|
| `qwen3vl_32b_minimax_h3_ultra_uncensored_heretic_int8_convrot.safetensors` | 24.553 GiB | `models/text_encoders/MiniMax-H3` | **REQUIRED** |
| `qwen3vl_32b_minimax_h3_generation_tail_50_63_int8_convrot.safetensors` | 7.086 GiB | `models/text_encoders/MiniMax-H3` | OPTIONAL (`INSTALL_TAIL=1`) |

Selected in **CLIPLoader** with type `minimax`. No NVFP4 build of the encoder
exists — it is INT8 at 24.55 GiB regardless.

> ### CORRECTION — the layers-50–63 "tail" is NOT the conditioning encoder
> The brief assumed the ~7.6 GB tail "may be all H3 needs" (saving ~19 GB). **That
> is wrong.** The repo README states H3 "consumes the unnormalized hidden state
> after language layer 49" — so the **layers 0–49 file (24.55 GiB) is REQUIRED**.
> The tail (layers 50–63 + final norm + LM head) is used **only** for optional
> prompt enhancement (loaded temporarily by the `ComfyUI-MiniMax-H3-Guide` node,
> then unloaded). Shipping only the tail produces a workflow that cannot encode a
> prompt. **Budget the 24.55 GiB file.**

## ⚠️ Operator decision — abliterated / uncensored encoder

Both candidate encoder repos derive from `llmfan46/Qwen3-VL-32B-Instruct-ultra-
uncensored-heretic` (an **abliterated / uncensored** fine-tune). **No stock
Qwen3-VL H3 encoder exists.** For PMOVES / UNFCU / client-facing work this is an
**explicit operator decision** — confirm it is acceptable before deploying.

**Alternative source (recommended upstream):** `ethanfel/Qwen3-VL-32B-Ultra-Heretic-
H3-ComfyUI-INT8-ConvRot` — same content, authored by the `ComfyUI-MiniMax-H3-Guide`
node author (416 likes vs OTMFLY's 4; OTMFLY is a 2-file mirror). Byte sizes and the
pinned upstream revision match, but SHA-256 was **not** cross-compared between the
two (UNVERIFIED equivalence). The installer defaults to OTMFLY because its exact
filenames are byte-confirmed; switch `REPO_ENCODER` to ethanfel if you prefer
upstream (confirm ethanfel's exact filename first).

## Exact `hf download` lines

```bash
export HF_HUB_ENABLE_HF_TRANSFER=1

# --- diffusion_models (NVFP4, Blackwell) ---
hf download DmitryDB/MiniMax-H3-ComfyUI-Quants FL2VA/MiniMax-H3_FL2VA-NVFP4.safetensors  --local-dir models/diffusion_models
hf download DmitryDB/MiniMax-H3-ComfyUI-Quants Ref2VA/MiniMax-H3_Ref2VA-NVFP4.safetensors --local-dir models/diffusion_models

# --- vae ---
hf download DmitryDB/MiniMax-H3-ComfyUI-Quants vae/MiniMax-H3_VideoVAE-FP16.safetensors --local-dir models/vae
hf download DmitryDB/MiniMax-H3-ComfyUI-Quants vae/MiniMax-H3_AudioVAE-FP32.safetensors --local-dir models/vae

# --- text_encoders (REQUIRED: layers 0-49 conditioning encoder, 24.55 GiB) ---
hf download OTMFLY/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot \
  qwen3vl_32b_minimax_h3_ultra_uncensored_heretic_int8_convrot.safetensors \
  --local-dir models/text_encoders/MiniMax-H3

# --- text_encoders (OPTIONAL: prompt-enhancement tail, layers 50-63, 7.09 GiB) ---
hf download OTMFLY/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot \
  qwen3vl_32b_minimax_h3_generation_tail_50_63_int8_convrot.safetensors \
  --local-dir models/text_encoders/MiniMax-H3
```

> **hf-download path note:** `hf download` preserves repo-relative paths, so the
> first four land under `FL2VA/`, `Ref2VA/`, `vae/` subfolders of `--local-dir`
> (ComfyUI scans recursively, so they still resolve). The `.bat`/`.sh` installers
> **flatten** the leaf up into the target dir and drop the empty subfolder; the raw
> lines above do not. `NVFP4-HQ` swap: substitute `-NVFP4-HQ` in the two UNET names.

## Download totals

| Set | GB |
|---|---:|
| 2× NVFP4 UNET | 23.33 |
| 2× VAE | 5.81 |
| Encoder (0–49, required) | 26.36 |
| Tail (50–63, optional) | 7.61 |
| **Working set (no tail)** | **55.50** |
| Full set (with tail) | 63.11 |

## Run

```bat
:: Windows (5090)
set "COMFY_ROOT=D:\path\to\ComfyUI"
MINIMAX-H3-MODELS-NODES_INSTALL.bat
```

```bash
# Linux / RunPod
COMFY_ROOT=/workspace/ComfyUI bash MINIMAX-H3-AUTO_INSTALL-RUNPOD.sh
```

## Verify (T4 pass criteria)

- The 3 node packs are present under `custom_nodes/`.
- The NVFP4 UNETs + VAEs + the 24.55 GiB encoder are downloaded to the dirs above.
- Both runtimes load the H3 nodes (native — appear in node search).
- The workflow's loaders resolve (no red "missing file" nodes).
- A test generation runs within 32 GB VRAM (watch `nvidia-smi`; sequential-residency
  peak ≈ 26.4 GiB — encoder and UNET are **not** co-resident).

## UNVERIFIED / caveats (from recon)

1. **NVFP4 never run end-to-end on a 5090** — DmitryDB's RTX-50 ratings are
   architecture-based; all PASS results in their table are INT8 on a 4090. NVFP4
   passed numerical/structural validation only. Treat first-run success as unproven.
2. **Uncensored encoder** — operator decision (above); no stock alternative exists.
3. **OTMFLY vs ethanfel** equivalence is size-based only (SHA not cross-checked).
4. Optional-tail path needs `github.com/ethanfel/ComfyUI-MiniMax-H3-Guide`
   (verified stack: comfy-kitchen 0.2.26, comfy-aimdo 0.4.11, PyTorch 2.8.0+cu128;
   comfy-kitchen recommends CUDA 13.0+ — 12.8 completes with unoptimized kernels).

## Operator inputs still required to reconcile

1. **SEAP `.bat` contents + folder listing** (operator-local on the 5090).
2. **The H3 workflow JSON** — to confirm which loaders/encoder path it wires.
3. **Aitrepreneur's model-mirror link** — cross-check against the verified sources
   above (which stand on their own; the mirror is a confirmation, not a dependency).
