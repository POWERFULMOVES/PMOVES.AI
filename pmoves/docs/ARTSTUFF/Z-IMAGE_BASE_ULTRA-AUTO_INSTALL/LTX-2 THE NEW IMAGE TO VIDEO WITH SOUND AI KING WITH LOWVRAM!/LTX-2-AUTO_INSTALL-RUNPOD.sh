#!/usr/bin/env bash
# RunPod ComfyUI LTX-2 by Aitrepreneur

set -euo pipefail

# ───────────────────── Config (override via env) ─────────────────────
HF_BASE="${HF_BASE:-https://huggingface.co/Aitrepreneur/FLX/resolve/main}"
MODEL_VERSION="${MODEL_VERSION:-Q8_0}"

# Py env
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"

# Torch/CUDA (RunPod cu121 is common; adjust if your image differs)
TORCH_VERSION="${TORCH_VERSION:-2.4.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.19.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.4.0}"
CUDA_TAG="${CUDA_TAG:-cu121}"
TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"

# Node selection
INSTALL_ALL_NODES="${INSTALL_ALL_NODES:-false}"
REQUIRED_NODES="${REQUIRED_NODES:-"ComfyUI-GGUF ComfyUI-WanVideoWrapper ComfyUI-VideoHelperSuite ComfyUI-KJNodes ComfyUI-Impact-Pack ComfyUI_essentials ComfyUI-Manager"}"

# Patches for fragile nodes
ALLOW_SAM2="${ALLOW_SAM2:-false}"
MANAGER_ENABLE_MATRIX="${MANAGER_ENABLE_MATRIX:-false}"

# Extra base libs known to reduce cross-node friction
PIN_PILLOW_MIN="${PIN_PILLOW_MIN:-11.0.0}"
PIN_OPENCV_HEADLESS="${PIN_OPENCV_HEADLESS:-4.12.0.88}"
PIN_URLLIB3_1X="${PIN_URLLIB3_1X:-1.26.18}"

# Extra audio lib for comfyui-vrgamedevgirl
PIN_LIBROSA_VERSION="${PIN_LIBROSA_VERSION:-}"

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore

# ───────────────────── Helpers ─────────────────────
[[ $(id -u) -eq 0 ]] && SUDO="" || SUDO="sudo"
need_pkg() { command -v "$1" &>/dev/null || { echo "[INFO] installing $1 ..."; $SUDO apt-get update -y; $SUDO apt-get install -y "$1"; }; }
need_pkg curl; need_pkg git; need_pkg git-lfs; git lfs install

die() { echo "[ERROR] $*"; exit 1; }

grab () {
  [[ -f "$1" ]] && { echo " • $(basename "$1") exists – skip"; return; }
  echo " • downloading $(basename "$1")"
  mkdir -p "$(dirname "$1")"
  curl -L --fail --progress-bar --show-error -o "$1" "$2"
}

get_node () {
  local dir=$1 url=$2 flag=${3:-}
  if [[ -d "custom_nodes/$dir" ]]; then
    echo " [SKIP] $dir already present."
  else
    echo " • cloning $dir"
    git clone $flag "$url" "custom_nodes/$dir"
  fi
}

# ───────────────────── Verify paths ─────────────────────
[[ -d "models" && -d "custom_nodes" ]] || die "Run this in your ComfyUI root (need models/ and custom_nodes/)."
COMFY_ROOT="$(pwd)"

# ───────────────────── Venv (always) ─────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  echo "──────── Creating venv at $VENV_DIR ────────"
  $PYTHON_BIN -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
PYTHON="$(command -v python)"
PIP="$(command -v pip)"
echo "Using venv python: $PYTHON"

$PYTHON -m pip install --no-input --upgrade pip setuptools wheel

# ───────────────────── Models ─────────────────────
echo
echo "──────── Downloading LTX-2 Model Files ────────"

# Text encoders
grab "models/text_encoders/ltx-2-19b-embeddings_connector_dev_bf16.safetensors" \
     "$HF_BASE/ltx-2-19b-embeddings_connector_dev_bf16.safetensors?download=true"

grab "models/text_encoders/gemma-3-12b-it-IQ4_XS.gguf" \
     "$HF_BASE/gemma-3-12b-it-IQ4_XS.gguf?download=true"

# VAE
grab "models/vae/LTX2_audio_vae_bf16.safetensors" \
     "$HF_BASE/LTX2_audio_vae_bf16.safetensors?download=true"

grab "models/vae/LTX2_video_vae_bf16.safetensors" \
     "$HF_BASE/LTX2_video_vae_bf16.safetensors?download=true"

# UNet
grab "models/unet/ltx-2-19b-dev-${MODEL_VERSION}.gguf" \
     "$HF_BASE/ltx-2-19b-dev-${MODEL_VERSION}.gguf?download=true"

# Latent upscale
grab "models/latent_upscale_models/ltx-2-spatial-upscaler-x2-1.0.safetensors" \
     "$HF_BASE/ltx-2-spatial-upscaler-x2-1.0.safetensors?download=true"

# Diffusion
grab "models/diffusion_models/MelBandRoformer_fp32.safetensors" \
     "$HF_BASE/MelBandRoformer_fp32.safetensors?download=true"

# LoRAs
grab "models/loras/ltx-2-19b-distilled-lora-384.safetensors" \
     "$HF_BASE/ltx-2-19b-distilled-lora-384.safetensors?download=true"

grab "models/loras/ltx-2-19b-ic-lora-detailer.safetensors" \
     "$HF_BASE/ltx-2-19b-ic-lora-detailer.safetensors?download=true"

grab "models/loras/ltx-2-19b-ic-lora-depth-control.safetensors" \
     "$HF_BASE/ltx-2-19b-ic-lora-depth-control.safetensors?download=true"

grab "models/loras/ltx-2-19b-ic-lora-pose-control.safetensors" \
     "$HF_BASE/ltx-2-19b-ic-lora-pose-control.safetensors?download=true"

# ───────────────────── Nodes ─────────────────────
echo
echo "──────── Cloning Custom Nodes ────────"

get_node "ComfyUI-Manager"             "https://github.com/ltdrdata/ComfyUI-Manager.git"
get_node "ComfyUI-GGUF"                "https://github.com/city96/ComfyUI-GGUF.git"
get_node "rgthree-comfy"               "https://github.com/rgthree/rgthree-comfy.git"
get_node "ComfyUI-Easy-Use"            "https://github.com/yolain/ComfyUI-Easy-Use"
get_node "ComfyUI-KJNodes"             "https://github.com/kijai/ComfyUI-KJNodes.git"
get_node "ComfyUI_UltimateSDUpscale"   "https://github.com/ssitu/ComfyUI_UltimateSDUpscale"
get_node "ComfyUI_essentials"          "https://github.com/cubiq/ComfyUI_essentials.git"
get_node "wlsh_nodes"                  "https://github.com/wallish77/wlsh_nodes.git"
get_node "comfyui-vrgamedevgirl"       "https://github.com/vrgamegirl19/comfyui-vrgamedevgirl"
get_node "RES4LYF"                     "https://github.com/ClownsharkBatwing/RES4LYF"
get_node "ComfyUI-Logic"               "https://github.com/theUpsider/ComfyUI-Logic"
get_node "comfyui_controlnet_aux"      "https://github.com/Fannovel16/comfyui_controlnet_aux"
get_node "ComfyUI-LTXVideo"            "https://github.com/Lightricks/ComfyUI-LTXVideo"
get_node "ComfyUI-Custom-Scripts"      "https://github.com/pythongosssss/ComfyUI-Custom-Scripts"
get_node "ComfyUI-Crystools"           "https://github.com/crystian/ComfyUI-Crystools"
get_node "ComfyUI-VideoHelperSuite"    "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
get_node "Derfuu_ComfyUI_ModdedNodes"  "https://github.com/Derfuu/Derfuu_ComfyUI_ModdedNodes"
get_node "ComfyUI-MelBandRoFormer"     "https://github.com/kijai/ComfyUI-MelBandRoFormer"
get_node "ComfyLiterals"               "https://github.com/M1kep/ComfyLiterals"
get_node "comfyui-yaser-nodes"         "https://github.com/YaserJaradeh/comfyui-yaser-nodes"
get_node "ComfyUI-S3-IO"               "https://github.com/olduvai-jp/ComfyUI-S3-IO"

# ───────────────────── Baseline: Torch + common pins ─────────────────────
echo
echo "──────── Installing baseline (Torch, Pillow, OpenCV headless) ────────"
# Torch stack first (locked to cu121 unless overridden)
$PYTHON -m pip install --no-input --upgrade-strategy only-if-needed \
  --index-url "$TORCH_INDEX" --extra-index-url https://pypi.org/simple \
  "torch==${TORCH_VERSION}+${CUDA_TAG}" \
  "torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}" \
  "torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}"

# Unify on headless OpenCV and pre-bump Pillow to satisfy KJNodes
$PYTHON -m pip uninstall -y opencv-python || true
$PYTHON -m pip install --no-input "opencv-python-headless==${PIN_OPENCV_HEADLESS}"
$PYTHON -m pip install --no-input "pillow>=${PIN_PILLOW_MIN}"

# If Matrix is enabled, pre-pin urllib3<2 to satisfy matrix-client 0.4.0
if [[ "$MANAGER_ENABLE_MATRIX" == "true" ]]; then
  $PYTHON -m pip install --no-input "urllib3==${PIN_URLLIB3_1X}"
fi

# ───────────────────── Known missing node dependencies ─────────────────────
echo
echo "──────── Installing known missing node dependencies ────────"

$PYTHON -m pip install --no-input \
  boto3 \
  rotary-embedding-torch \
  deepdiff \
  py-cpuinfo \
  diffusers


# ───────────────────── Patch fragile requirements (optional) ─────────────────────
# Impact-Pack SAM2 -> forces torch>=2.5.1 (skip by default)
if [[ "$ALLOW_SAM2" != "true" ]]; then
  if [[ -f custom_nodes/ComfyUI-Impact-Pack/requirements.txt ]]; then
    sed -i 's@^git+https://github.com/facebookresearch/sam2.*@# sam2 disabled for CUDA/Torch stability (set ALLOW_SAM2=true to re-enable)@' \
      custom_nodes/ComfyUI-Impact-Pack/requirements.txt || true
  fi
fi

# ComfyUI-Manager Matrix (urllib3<2). Disable unless explicitly requested.
if [[ "$MANAGER_ENABLE_MATRIX" != "true" ]]; then
  if [[ -f custom_nodes/ComfyUI-Manager/requirements.txt ]]; then
    sed -i 's/^matrix-client==0\.4\.0/# matrix-client disabled by installer; set MANAGER_ENABLE_MATRIX=true to enable/' \
      custom_nodes/ComfyUI-Manager/requirements.txt || true
  fi
fi

# ───────────────────── Lock constraints after sane baseline ─────────────────────
echo "   • Writing constraints to /tmp/constraints.txt"
$PYTHON -m pip freeze | sed '/^-e /d' > /tmp/constraints.txt

# ───────────────────── Install node requirements safely ─────────────────────
collect_reqs_all()      { find custom_nodes -maxdepth 2 -name requirements.txt -print; }
collect_reqs_required() {
  for dir in $REQUIRED_NODES; do
    local req="custom_nodes/$dir/requirements.txt"
    [[ -f "$req" ]] && echo "$req" || echo "   • (no requirements.txt) $dir" >&2
  done
}

echo
echo "──────── Installing node requirements (Manager-like per node) ────────"
declare -a REQ_FILES=()
if [[ "$INSTALL_ALL_NODES" == "true" ]]; then
  while IFS= read -r path; do REQ_FILES+=("$path"); done < <(collect_reqs_all)
else
  while IFS= read -r path; do [[ -f "$path" ]] && REQ_FILES+=("$path") || true; done < <(collect_reqs_required)
fi

# Re-ensure venv is active before node installs
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PYTHON="$(command -v python)"
PIP="$(command -v pip)"
echo "Re-confirmed venv python for node installs: $PYTHON"

# Install each node from inside its folder (mirrors Manager behavior)
for req in "${REQ_FILES[@]}"; do
  echo "   • $req"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  PYTHON="$(command -v python)"; PIP="$(command -v pip)"
  req_dir="$(dirname "$req")"
  pushd "$req_dir" >/dev/null

  # Attempt 1: prefer wheels, avoid build isolation (faster, fewer surprises)
  if ! $PYTHON -m pip install --no-input --prefer-binary --no-build-isolation \
       --upgrade-strategy only-if-needed -r requirements.txt; then
    echo "     ↳ [WARN] First attempt failed; retrying with build isolation…"
    # Attempt 2: allow build isolation as a fallback
    $PYTHON -m pip install --no-input --prefer-binary \
       --upgrade-strategy only-if-needed -r requirements.txt || {
      echo "     ↳ [ERROR] Failed: $req — continuing"
    }
  fi
  popd >/dev/null
done

# ───────────────────── Final pass: mimic manual install for RES4LYF ─────────────────────
if [[ -d "$COMFY_ROOT/custom_nodes/RES4LYF" && -f "$COMFY_ROOT/custom_nodes/RES4LYF/requirements.txt" ]]; then
  echo
  echo "──────── Finalizing RES4LYF exactly like manual steps ────────"
  # Activate venv from the ComfyUI root (absolute path, like your manual flow)
  # shellcheck disable=SC1091
  source "$COMFY_ROOT/$VENV_DIR/bin/activate"
  COMFY_VENV_PIP="$COMFY_ROOT/$VENV_DIR/bin/pip"

  # Avoid hidden/global constraints or user-site pollution
  unset PIP_CONSTRAINT PIP_REQUIRE_VIRTUALENV
  export PYTHONNOUSERSITE=1

  pushd "$COMFY_ROOT/custom_nodes/RES4LYF" >/dev/null
  # Match your manual command, but ensure this node can override conflicting versions
  "$COMFY_VENV_PIP" install --upgrade --force-reinstall -r requirements.txt || {
    echo "     ↳ [ERROR] RES4LYF install step failed — continuing"
  }
  popd >/dev/null
fi

# ───────────────────── Optional extras ─────────────────────
# Base extras
$PYTHON -m pip install --no-input gguf piexif || true

# Audio stack for comfyui-vrgamedevgirl (librosa)
if [[ -n "$PIN_LIBROSA_VERSION" ]]; then
  echo "──────── Installing librosa==${PIN_LIBROSA_VERSION} for comfyui-vrgamedevgirl ────────"
  $PYTHON -m pip install --no-input "librosa==${PIN_LIBROSA_VERSION}" || true
else
  echo "──────── Installing latest librosa for comfyui-vrgamedevgirl ────────"
  $PYTHON -m pip install --no-input librosa || true
fi

echo
echo "✅ models and nodes are ready"
