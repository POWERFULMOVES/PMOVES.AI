#!/usr/bin/env bash
# ComfyUI + WAN Animate 2.2 — Full installer (cu128 by default)
# Tested on a fresh RunPod ComfyUI template (Python 3.11, RTX 40xx).

set -euo pipefail

# ───────────────────── Config (override via env) ─────────────────────
HF_BASE="${HF_BASE:-https://huggingface.co/Aitrepreneur/FLX/resolve/main}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"

# Torch stack choice: auto | cu128 | keep
# - auto: use cu128 when NVIDIA GPU is present, else keep
WANT_TORCH_STACK="${WANT_TORCH_STACK:-auto}"
CUDA_TAG="${CUDA_TAG:-cu128}"              # cu121|cu124|cu126|cu128|cu130|cpu
TORCH_VERSION="${TORCH_VERSION:-2.8.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.23.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.8.0}"
TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"

# Known-good pins for WAN wrapper
PIN_XFORMERS="${PIN_XFORMERS:-0.0.32.post2}"
PIN_TRITON="${PIN_TRITON:-3.4.0}"
PIN_NUMPY="${PIN_NUMPY:-2.2.6}"
PIN_OPENCV="${PIN_OPENCV:-4.12.0.88}"
PIN_DIFFUSERS="${PIN_DIFFUSERS:-0.35.2}"
PIN_TRANSFORMERS="${PIN_TRANSFORMERS:-4.57.1}"
PIN_PEFT="${PIN_PEFT:-0.17.1}"
PIN_ACCELERATE="${PIN_ACCELERATE:-1.10.1}"
PIN_SAFETENSORS="${PIN_SAFETENSORS:-0.6.2}"
PIN_EINOPS="${PIN_EINOPS:-0.8.1}"
PIN_SENTENCEPIECE="${PIN_SENTENCEPIECE:-0.2.1}"
PIN_PILLOW_MIN="${PIN_PILLOW_MIN:-10.3.0}"

# Optional ONNX runtime (needed by some video/seg nodes)
INSTALL_ONNXRUNTIME="${INSTALL_ONNXRUNTIME:-true}"
PIN_ONNXRUNTIME_GPU="${PIN_ONNXRUNTIME_GPU:-1.23.0}"

# Node selection — only what you asked for
REQUIRED_NODES=(
  "ComfyUI-Manager"
  "ComfyUI-WanVideoWrapper"
  "rgthree-comfy"
  "ComfyUI-KJNodes"
  "ComfyUI-VideoHelperSuite"
  "ComfyUI-segment-anything-2"
  "Comfyui-SecNodes"
  "ComfyUI-WanAnimatePreprocess"
)

# Env hygiene
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore
export PYTHONUNBUFFERED=1
export HF_HUB_ENABLE_HF_TRANSFER=1
export PYTHONNOUSERSITE=1

# ───────────────────── Helpers ─────────────────────
need_pkg() { command -v "$1" &>/dev/null || { apt-get update -y && apt-get install -y "$@"; }; }
die() { echo "[ERROR] $*"; exit 1; }
grab () {  # grab <target> <url>
  [[ -f "$1" ]] && { echo " • $(basename "$1") exists — skip"; return; }
  echo " • downloading $(basename "$1")"
  mkdir -p "$(dirname "$1")"
  curl -L --fail --progress-bar --show-error -o "$1" "$2"
}
get_node () {  # get_node <folder> <git url> [--recursive]
  local dir=$1 url=$2 flag=${3:-}
  if [[ -d "custom_nodes/$dir" ]]; then
    echo " [SKIP] $dir"
  else
    echo " • cloning $dir"
    git clone $flag "$url" "custom_nodes/$dir"
  fi
}

# ───────────────────── Verify ComfyUI root ─────────────────────
[[ -d "models" && -d "custom_nodes" ]] || die "Run inside ComfyUI root (needs models/ and custom_nodes/)."

# ───────────────────── Base tools ─────────────────────
need_pkg curl git git-lfs
git lfs install

# ───────────────────── Venv ─────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv → $VENV_DIR"
  $PYTHON_BIN -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PYTHON="$(command -v python)"
PIP="$(command -v pip)"
$PYTHON -m pip install --no-input -U pip setuptools wheel hf_transfer

# ───────────────────── Decide stack ─────────────────────
GPU_VENDOR="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || true)"
if [[ "${WANT_TORCH_STACK}" == "auto" ]]; then
  if [[ -n "$GPU_VENDOR" ]]; then
    WANT_TORCH_STACK="cu128"
  else
    WANT_TORCH_STACK="keep"
  fi
fi
echo "[INFO] WANT_TORCH_STACK=${WANT_TORCH_STACK}"

# ───────────────────── Models (WAN Animate 2.2) ─────────────────────
echo "Downloading WAN Animate 2.2 model files…"
# clip_vision
grab "models/clip_vision/clip_vision_h.safetensors" \
     "$HF_BASE/clip_vision_h.safetensors?download=true"
# detection
grab "models/detection/vitpose_h_wholebody_data.bin" \
     "$HF_BASE/vitpose_h_wholebody_data.bin?download=true"
grab "models/detection/vitpose_h_wholebody_model.onnx" \
     "$HF_BASE/vitpose_h_wholebody_model.onnx?download=true"
grab "models/detection/vitpose-l-wholebody.onnx" \
     "$HF_BASE/vitpose-l-wholebody.onnx?download=true"
grab "models/detection/yolov10m.onnx" \
     "$HF_BASE/yolov10m.onnx?download=true"
# diffusion
grab "models/diffusion_models/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors" \
     "$HF_BASE/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors?download=true"
# loras
grab "models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" \
     "$HF_BASE/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors?download=true"
grab "models/loras/WanAnimate_relight_lora_fp16.safetensors" \
     "$HF_BASE/WanAnimate_relight_lora_fp16.safetensors?download=true"
# sams
grab "models/sams/SeC-4B-fp16.safetensors" \
     "$HF_BASE/SeC-4B-fp16.safetensors?download=true"
# text_encoders
grab "models/text_encoders/umt5-xxl-enc-bf16.safetensors" \
     "$HF_BASE/umt5-xxl-enc-bf16.safetensors?download=true"
# vae
grab "models/vae/Wan2_1_VAE_bf16.safetensors" \
     "$HF_BASE/Wan2_1_VAE_bf16.safetensors?download=true"

# ───────────────────── Nodes ─────────────────────
echo "Cloning required custom nodes…"
get_node "ComfyUI-Manager"              "https://github.com/ltdrdata/ComfyUI-Manager.git"
get_node "ComfyUI-WanVideoWrapper"      "https://github.com/kijai/ComfyUI-WanVideoWrapper"
get_node "rgthree-comfy"                "https://github.com/rgthree/rgthree-comfy"
get_node "ComfyUI-KJNodes"              "https://github.com/kijai/ComfyUI-KJNodes"
get_node "ComfyUI-VideoHelperSuite"     "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
get_node "ComfyUI-segment-anything-2"   "https://github.com/kijai/ComfyUI-segment-anything-2"
get_node "Comfyui-SecNodes"             "https://github.com/9nate-drake/Comfyui-SecNodes"
get_node "ComfyUI-WanAnimatePreprocess" "https://github.com/kijai/ComfyUI-WanAnimatePreprocess"

# ───────────────────── Torch + core deps ─────────────────────
echo "Installing Torch stack…"
if [[ "${WANT_TORCH_STACK}" == "keep" ]]; then
  echo " • Keeping existing Torch. Ensuring other pins…"
else
  # Clean venv conflicts only
  $PIP uninstall -y torch torchvision torchaudio xformers triton numpy opencv-python opencv-python-headless \
    diffusers accelerate transformers peft || true

  $PIP install --no-input --upgrade-strategy only-if-needed \
    --index-url "$TORCH_INDEX" --extra-index-url https://pypi.org/simple \
    "torch==${TORCH_VERSION}+${CUDA_TAG}" \
    "torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}" \
    "torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}"

  $PIP install --no-input \
    "xformers==${PIN_XFORMERS}" \
    "triton==${PIN_TRITON}" \
    "numpy==${PIN_NUMPY}" \
    "opencv-python==${PIN_OPENCV}" \
    "diffusers==${PIN_DIFFUSERS}" \
    "transformers==${PIN_TRANSFORMERS}" \
    "peft==${PIN_PEFT}" \
    "accelerate==${PIN_ACCELERATE}" \
    "safetensors==${PIN_SAFETENSORS}" \
    "einops==${PIN_EINOPS}" \
    "sentencepiece==${PIN_SENTENCEPIECE}"
fi

# Prefer headless OpenCV + Pillow min
$PIP uninstall -y opencv-python || true
$PIP install --no-input "opencv-python-headless==${PIN_OPENCV}"
$PIP install --no-input "pillow>=${PIN_PILLOW_MIN}" gguf piexif || true

# Optional ONNX runtime (GPU build)
if [[ "${INSTALL_ONNXRUNTIME}" == "true" ]]; then
  echo "Installing onnxruntime-gpu ${PIN_ONNXRUNTIME_GPU} (and helpers)…"
  $PIP install --no-input --prefer-binary \
    "onnxruntime-gpu==${PIN_ONNXRUNTIME_GPU}" onnx coloredlogs humanfriendly flatbuffers || true
fi

# ───────────────────── SageAttention (wheel → source fallback) ─────────────────────
echo "Installing SageAttention…"
set +e
if ! $PYTHON - <<'PY'
try:
    import sageattention as sa
    print("ok", getattr(sa,"__version__","installed"))
except Exception:
    raise SystemExit(1)
PY
then
  if ! $PIP install --no-build-isolation --prefer-binary "sageattention==1.0.6"; then
    echo " • Wheel not available; trying GitHub source (main)…"
    need_pkg build-essential python3-dev
    $PIP install --no-build-isolation "git+https://github.com/woct0rdho/SageAttention.git" || true
  fi
fi
set -e

# Report SageAttention status
$PYTHON - <<'PY'
try:
    import sageattention as sa
    print("SageAttention:", getattr(sa,"__version__","installed"))
except Exception as e:
    print("SageAttention: NOT installed ->", e)
PY

# ───────────────────── Node requirements (per-node, tolerant) ─────────────────────
echo "Installing node requirements…"
for dir in "${REQUIRED_NODES[@]}"; do
  req="custom_nodes/$dir/requirements.txt"
  [[ -f "$req" ]] || { echo " • $dir (no requirements.txt)"; continue; }
  echo " • $req"
  pushd "$(dirname "$req")" >/dev/null
  $PIP install --no-input --prefer-binary --no-build-isolation \
    --upgrade-strategy only-if-needed -r requirements.txt \
  || $PIP install --no-input --prefer-binary -r requirements.txt || true
  popd >/dev/null
done

# ───────────────────── Final sanity print ─────────────────────
$PYTHON - <<'PY'
import sys, platform
print("Python:", sys.version.replace("\n",""))
print("Platform:", platform.platform())
try:
    import torch
    print("Torch:", torch.__version__, "| CUDA:", getattr(torch.version,"cuda",None))
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
except Exception as e:
    print("Torch import failed:", e)
def softimp(name):
    try:
        mod=__import__(name); return getattr(mod,"__version__","installed")
    except Exception as e:
        return f"not installed ({e})"
print("xformers:", softimp("xformers"))
print("triton:", softimp("triton"))
print("diffusers:", softimp("diffusers"))
print("transformers:", softimp("transformers"))
print("peft:", softimp("peft"))
print("accelerate:", softimp("accelerate"))
print("numpy:", softimp("numpy"))
try:
    import cv2; print("opencv:", cv2.__version__)
except Exception as e:
    print("opencv: not installed", e)
print("sageattention:", softimp("sageattention"))
try:
    import onnxruntime as ort; print("onnxruntime:", getattr(ort,"__version__","installed"))
except Exception as e:
    print("onnxruntime: skip", e)
PY

echo
echo "✅ Install complete. You can start ComfyUI normally."
