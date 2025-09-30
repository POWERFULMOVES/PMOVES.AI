#!/usr/bin/env bash
# RunPod ComfyUI QWEN IMAGE by Aitrepreneur

set -euo pipefail

# ───────────────────── Config (override via env) ─────────────────────
HF_BASE="${HF_BASE:-https://huggingface.co/Aitrepreneur/FLX/resolve/main}"
MODEL_VERSION="${MODEL_VERSION:-Q8_0}"

# Py env
PYTHON_BIN="${PYTHON_BIN:-python3}"            # system python to create venv
VENV_DIR="${VENV_DIR:-venv}"

# Torch/CUDA (RunPod cu121 is common; adjust if your image differs)
TORCH_VERSION="${TORCH_VERSION:-2.4.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.19.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.4.0}"
CUDA_TAG="${CUDA_TAG:-cu121}"                  # cu118 | cu121 | cpu
TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_TAG}"

# Node selection
INSTALL_ALL_NODES="${INSTALL_ALL_NODES:-false}"   # true = install every cloned node requirements
REQUIRED_NODES="${REQUIRED_NODES:-"ComfyUI-GGUF ComfyUI-WanVideoWrapper ComfyUI-VideoHelperSuite ComfyUI-KJNodes ComfyUI-Impact-Pack ComfyUI_essentials ComfyUI-Manager"}"

# Patches for fragile nodes
ALLOW_SAM2="${ALLOW_SAM2:-false}"                 # Impact-Pack pulls SAM2 -> forces torch >= 2.5.1
MANAGER_ENABLE_MATRIX="${MANAGER_ENABLE_MATRIX:-false}"  # Matrix needs urllib3<2 and is optional for most

# Extra base libs known to reduce cross-node friction
PIN_PILLOW_MIN="${PIN_PILLOW_MIN:-11.0.0}"        # >=10.3 satisfies KJNodes; 11.x is fine
PIN_OPENCV_HEADLESS="${PIN_OPENCV_HEADLESS:-4.12.0.88}"  # unify on headless; avoid dual opencv

# Hard pins that keep env stable across all installs
PIN_NUMPY_CEILING="${PIN_NUMPY_CEILING:-<2.3}"    # avoid numpy 2.3+ which breaks opencv/scipy in this stack

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore

# ───────────────────── Helpers ─────────────────────
[[ $(id -u) -eq 0 ]] && SUDO="" || SUDO="sudo"
need_pkg() { command -v "$1" &>/dev/null || { echo "[INFO] installing $1 ..."; $SUDO apt-get update -y; $SUDO apt-get install -y "$1"; }; }
need_pkg curl; need_pkg git; need_pkg git-lfs; git lfs install

die() { echo "[ERROR] $*"; exit 1; }

grab () {  # grab <target path> <url>
  [[ -f "$1" ]] && { echo " • $(basename "$1") exists – skip"; return; }
  echo " • downloading $(basename "$1")"
  mkdir -p "$(dirname "$1")"
  curl -L --fail --progress-bar --show-error -o "$1" "$2"
}

get_node () {  # get_node <folder> <git url> [--recursive]
  local dir=$1 url=$2 flag=${3:-}
  if [[ -d "custom_nodes/$dir" ]]; then
    echo " [SKIP] $dir already present."
  else
    echo " • cloning $dir"
    git clone $flag "$url" "custom_nodes/$dir"
  fi
}

# Strip packages that must NOT be upgraded by node requirements
sanitize_requirements() {
  # usage: sanitize_requirements "<path/to/requirements.txt>"
  local req="$1"
  [[ -f "$req" ]] || return 0
  sed -i -E \
    -e 's/^(torch([^#]*))/# \1  # pinned by installer/gI' \
    -e 's/^(torchvision([^#]*))/# \1  # pinned by installer/gI' \
    -e 's/^(torchaudio([^#]*))/# \1  # pinned by installer/gI' \
    -e 's/^(opencv-python([^#]*))/# \1  # pinned by installer/gI' \
    -e 's/^(opencv-python-headless([^#]*))/# \1  # pinned by installer/gI' \
    "$req" || true
}

# Manual finalize helper for fragile nodes (respects constraints)
manual_finalize_node() {
  # usage: manual_finalize_node "<folder name under custom_nodes>"
  local node_dir="$1"
  local node_path="$COMFY_ROOT/custom_nodes/$node_dir"
  local req_file="$node_path/requirements.txt"

  if [[ -d "$node_path" && -f "$req_file" ]]; then
    echo
    echo "──────── Finalizing $node_dir like manual steps ────────"
    # Activate venv from the ComfyUI root
    # shellcheck disable=SC1091
    source "$COMFY_ROOT/$VENV_DIR/bin/activate"
    local COMFY_VENV_PIP="$COMFY_ROOT/$VENV_DIR/bin/pip"

    # Avoid hidden or global constraints and user-site pollution
    unset PIP_REQUIRE_VIRTUALENV
    export PYTHONNOUSERSITE=1

    # Make sure node reqs cannot override torch/opencv pins
    sanitize_requirements "$req_file"

    pushd "$node_path" >/dev/null
    "$COMFY_VENV_PIP" install --no-input --upgrade --force-reinstall \
      --constraint /tmp/constraints.txt \
      -r requirements.txt || {
        echo "     ↳ [ERROR] $node_dir manual install failed. continuing"
      }
    "$COMFY_VENV_PIP" check || true
    popd >/dev/null
  else
    echo "   • Skipping manual finalize for $node_dir. Folder or requirements.txt missing"
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
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PYTHON="$(command -v python)"
PIP="$(command -v pip)"
echo "Using venv python: $PYTHON"

# Keep pip tooling fresh inside venv
$PYTHON -m pip install --no-input --upgrade pip setuptools wheel

# ───────────────────── Models ─────────────────────
echo
echo "──────── Downloading Qwen image edit Model Files ────────"
grab "models/text_encoders/Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf" "$HF_BASE/Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf?download=true"
grab "models/text_encoders/Qwen2.5-VL-7B-Instruct-UD-${MODEL_VERSION}.gguf"  "$HF_BASE/Qwen2.5-VL-7B-Instruct-UD-${MODEL_VERSION}.gguf?download=true"
grab "models/vae/qwen_image_vae.safetensors" "$HF_BASE/qwen_image_vae.safetensors?download=true"
grab "models/unet/Qwen_Image_Edit-${MODEL_VERSION}.gguf" "$HF_BASE/Qwen_Image_Edit-${MODEL_VERSION}.gguf?download=true"
grab "models/loras/Qwen-Image-Lightning-8steps-V1.1.safetensors" "$HF_BASE/Qwen-Image-Lightning-8steps-V1.1.safetensors?download=true"
grab "models/loras/Qwen-Image-Lightning-4steps-V1.0.safetensors" "$HF_BASE/Qwen-Image-Lightning-4steps-V1.0.safetensors?download=true"
grab "models/upscale_models/4x-ClearRealityV1.pth" "$HF_BASE/4x-ClearRealityV1.pth?download=true"
grab "models/upscale_models/RealESRGAN_x4plus_anime_6B.pth" "$HF_BASE/RealESRGAN_x4plus_anime_6B.pth?download=true"

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
get_node "ComfyUI-Crystools"           "https://github.com/crystian/ComfyUI-Crystools"

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

# ───────────────────── Global constraints file ─────────────────────
echo "   • Writing constraints to /tmp/constraints.txt"
cat > /tmp/constraints.txt <<EOF
torch==${TORCH_VERSION}+${CUDA_TAG}
torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}
torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}
numpy${PIN_NUMPY_CEILING}
opencv-python-headless==${PIN_OPENCV_HEADLESS}
pillow>=${PIN_PILLOW_MIN}
EOF
# Include all currently installed versions too
$PYTHON -m pip freeze | sed '/^-e /d' >> /tmp/constraints.txt

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

# Install each node from inside its folder (mirrors Manager behavior), with constraints
for req in "${REQ_FILES[@]}"; do
  echo "   • $req"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  PYTHON="$(command -v python)"; PIP="$(command -v pip)"
  req_dir="$(dirname "$req")"

  # Prevent torch/opencv from being upgraded by node reqs
  sanitize_requirements "$req"

  pushd "$req_dir" >/dev/null
  # Attempt 1: prefer wheels, avoid build isolation
  if ! $PYTHON -m pip install --no-input --prefer-binary --no-build-isolation \
       --upgrade-strategy only-if-needed \
       --constraint /tmp/constraints.txt \
       -r requirements.txt; then
    echo "     ↳ [WARN] First attempt failed; retrying with build isolation…"
    # Attempt 2: allow build isolation as a fallback
    $PYTHON -m pip install --no-input --prefer-binary \
       --upgrade-strategy only-if-needed \
       --constraint /tmp/constraints.txt \
       -r requirements.txt || {
      echo "     ↳ [ERROR] Failed: $req — continuing"
    }
  fi
  popd >/dev/null
done

# ───────────────────── Manual finalize installs for fragile nodes ─────────────────────
manual_finalize_node "RES4LYF"
manual_finalize_node "ComfyUI-Crystools"

# ───────────────────── Optional extras ─────────────────────
$PYTHON -m pip install --no-input gguf piexif || true

echo
echo "✅ Qwen Image edit models and nodes are ready"
