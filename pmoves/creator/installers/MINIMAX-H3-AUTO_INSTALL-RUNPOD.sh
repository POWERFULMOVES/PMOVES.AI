#!/usr/bin/env bash
# MiniMax-H3 (NVFP4) — models + aux nodes installer (RunPod / Linux, cu128).
# Companion to MINIMAX-H3-MODELS-NODES_INSTALL.bat (Windows/5090).
#
# H3 nodes are NATIVE in the PMOVES-Creator fork (comfy_extras/nodes_minimax_h3.py)
# and load in stock ComfyUI — nothing to clone for H3 itself. Only 3 workflow-
# support node packs are cloned. Loaders are dropdowns → files keep real repo
# names (no renaming). NVFP4 UNETs halve the diffusion-model size on Blackwell
# (10.86 vs 20.94 GiB per UNET); peak VRAM is SEQUENTIAL residency, fits 32 GB.
# Total ≈ 55.5 GB (63 GB with the optional tail).
#
# !! ENCODER IS AN ABLITERATED / UNCENSORED FINE-TUNE — no stock alternative
# !! exists. For UNFCU / client-facing work this is an operator decision (README).
#
# RUNTIME-AGNOSTIC: set COMFY_ROOT to target a specific ComfyUI install, else run
# from inside the ComfyUI root (needs models/ and custom_nodes/).
#   Options: H3_PROFILE=NVFP4|NVFP4-HQ   INSTALL_TAIL=0|1
set -euo pipefail

# ───────────────────── Config (override via env) ─────────────────────
COMFY_ROOT="${COMFY_ROOT:-$PWD}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"
WANT_TORCH_STACK="${WANT_TORCH_STACK:-auto}"   # auto | cu128 | keep
CUDA_TAG="${CUDA_TAG:-cu128}"
TORCH_VERSION="${TORCH_VERSION:-2.8.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.23.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.8.0}"
TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"
H3_PROFILE="${H3_PROFILE:-NVFP4}"              # NVFP4 (8-12GB) | NVFP4-HQ (16-24GB)
INSTALL_TAIL="${INSTALL_TAIL:-0}"

export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
export PYTHONUNBUFFERED=1 HF_HUB_ENABLE_HF_TRANSFER=1

# ── VERIFIED SOURCES (hf_fs byte-exact, 2026-08-09 recon) ──
REPO_QUANTS="DmitryDB/MiniMax-H3-ComfyUI-Quants"
REPO_ENCODER="OTMFLY/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot"
ENC_MAIN="qwen3vl_32b_minimax_h3_ultra_uncensored_heretic_int8_convrot.safetensors"
ENC_TAIL="qwen3vl_32b_minimax_h3_generation_tail_50_63_int8_convrot.safetensors"

# ───────────────────── Helpers ─────────────────────
die() { echo "[ERROR] $*"; exit 1; }
need_pkg() { command -v "$1" &>/dev/null || { apt-get update -y && apt-get install -y "$@"; }; }
get_node() {  # get_node <folder> <git url>
  local dir=$1 url=$2
  if [[ -d "custom_nodes/$dir" ]]; then echo " [SKIP] $dir"; else
    echo " • cloning $dir"; git clone "$url" "custom_nodes/$dir"; fi
  [[ -f "custom_nodes/$dir/requirements.txt" ]] && \
    "$PIP" install --no-input --prefer-binary -r "custom_nodes/$dir/requirements.txt" || true
}
hf_get() {  # hf_get <repo> <repo-relative-file> <dest-subdir>
  local repo=$1 file=$2 sub=$3 dir="$COMFY_ROOT/$sub" base
  base="$(basename "$file")"
  [[ -f "$dir/$base" ]] && { echo " • $base present — skip"; return 0; }
  mkdir -p "$dir"
  echo " • downloading $file"
  hf download "$repo" "$file" --local-dir "$dir"
  # hf preserves the repo path — flatten the leaf up, drop the empty subdir
  if [[ "$file" != "$base" && -f "$dir/$file" ]]; then
    mv -f "$dir/$file" "$dir/$base"
    rmdir "$dir/$(dirname "$file")" 2>/dev/null || true
  fi
  return 0
}

# ───────────────────── Verify root + base tools ─────────────────────
cd "$COMFY_ROOT"
[[ -d "models" && -d "custom_nodes" ]] || die "COMFY_ROOT=$COMFY_ROOT is not a ComfyUI root."
echo "[INFO] ComfyUI root: $COMFY_ROOT | profile=$H3_PROFILE tail=$INSTALL_TAIL"
need_pkg curl git git-lfs
git lfs install || true

# ───────────────────── Venv + torch ─────────────────────
[[ -d "$VENV_DIR" ]] || { echo "Creating venv → $VENV_DIR"; $PYTHON_BIN -m venv "$VENV_DIR"; }
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PIP="$(command -v pip)"
"$PIP" install --no-input -U pip setuptools wheel "huggingface_hub[cli]" hf_transfer

GPU="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || true)"
[[ "$WANT_TORCH_STACK" == "auto" ]] && { [[ -n "$GPU" ]] && WANT_TORCH_STACK="cu128" || WANT_TORCH_STACK="keep"; }
echo "[INFO] GPU=${GPU:-none}  WANT_TORCH_STACK=$WANT_TORCH_STACK"
if [[ "$WANT_TORCH_STACK" != "keep" ]]; then
  "$PIP" install --no-input --upgrade-strategy only-if-needed \
    --index-url "$TORCH_INDEX" --extra-index-url https://pypi.org/simple \
    "torch==${TORCH_VERSION}+${CUDA_TAG}" \
    "torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}" \
    "torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}"
fi

# ───────────────────── Nodes (3 support packs; H3 is native) ─────────────────────
echo "Cloning workflow-support custom nodes…"
get_node "rgthree-comfy"            "https://github.com/rgthree/rgthree-comfy"
get_node "ComfyUI-KJNodes"          "https://github.com/kijai/ComfyUI-KJNodes"
get_node "ComfyUI-VideoHelperSuite" "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"

# ───────────────────── Models ─────────────────────
echo "Downloading MiniMax-H3 models (profile=$H3_PROFILE)…"
hf_get "$REPO_QUANTS"  "FL2VA/MiniMax-H3_FL2VA-${H3_PROFILE}.safetensors"  "models/diffusion_models"
hf_get "$REPO_QUANTS"  "Ref2VA/MiniMax-H3_Ref2VA-${H3_PROFILE}.safetensors" "models/diffusion_models"
hf_get "$REPO_QUANTS"  "vae/MiniMax-H3_VideoVAE-FP16.safetensors"          "models/vae"
hf_get "$REPO_QUANTS"  "vae/MiniMax-H3_AudioVAE-FP32.safetensors"          "models/vae"
echo " [REQUIRED] conditioning encoder (layers 0-49, ~24.6 GiB)"
hf_get "$REPO_ENCODER" "$ENC_MAIN" "models/text_encoders/MiniMax-H3"
if [[ "$INSTALL_TAIL" == "1" ]]; then
  echo " [OPTIONAL] prompt-enhancement tail (layers 50-63, ~7.1 GiB)"
  hf_get "$REPO_ENCODER" "$ENC_TAIL" "models/text_encoders/MiniMax-H3"
else
  echo " [SKIP] optional tail (set INSTALL_TAIL=1 to fetch)"
fi

echo
echo "✅ MiniMax-H3 install complete."
echo "   Encoder dir: models/text_encoders/MiniMax-H3  (CLIPLoader type: minimax)"
