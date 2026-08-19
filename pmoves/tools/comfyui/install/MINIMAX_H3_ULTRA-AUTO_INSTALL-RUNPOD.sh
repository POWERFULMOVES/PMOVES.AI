#!/usr/bin/env bash
# RunPod ComfyUI MiniMax H3 Ultra V1 by Aitrepreneur
# Faster model downloads, safer resume/recovery, and reduced setup overhead.

set -euo pipefail

# ───────────────────── Config ─────────────────────

HF_REPO="${HF_REPO:-Aitrepreneur/FLX}"
MODEL_DOWNLOAD_WORKERS="${MODEL_DOWNLOAD_WORKERS:-2}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-venv}"

# RunPod CUDA 12.8 safe stack
TORCH_VERSION="${TORCH_VERSION:-2.8.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.23.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.8.0}"
CUDA_TAG="${CUDA_TAG:-cu128}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/${CUDA_TAG}}"

# Node install behavior
INSTALL_ALL_NODES="${INSTALL_ALL_NODES:-false}"

# This list must match the nodes actually cloned below.
REQUIRED_NODES="${REQUIRED_NODES:-"ComfyUI-Manager rgthree-comfy ComfyUI-KJNodes ComfyUI-VideoHelperSuite ComfyUI-Spectrum-MiniMax-H3"}"

# Fragile dependency behavior
MANAGER_ENABLE_MATRIX="${MANAGER_ENABLE_MATRIX:-false}"

# Pins
PIN_PILLOW_MIN="${PIN_PILLOW_MIN:-11.0.0}"
PIN_NUMPY="${PIN_NUMPY:-1.26.4}"

# Keep Transformers 4.x for compatibility with ComfyUI and custom nodes.
PIN_TRANSFORMERS="${PIN_TRANSFORMERS:-4.50.3}"
PIN_TOKENIZERS_RANGE="${PIN_TOKENIZERS_RANGE:->=0.21,<0.22}"
# huggingface_hub 0.34+ includes the modern `hf` stack and native hf_xet support.
# Keep it below 1.0 because Transformers 4.50.3 is deliberately pinned here.
PIN_HF_HUB_RANGE="${PIN_HF_HUB_RANGE:->=0.34,<1.0}"
PIN_HF_XET_RANGE="${PIN_HF_XET_RANGE:->=1.1,<2.0}"

PIN_URLLIB3_1X="${PIN_URLLIB3_1X:-1.26.18}"
PIN_LIBROSA_VERSION="${PIN_LIBROSA_VERSION:-}"

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore
export PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
export PIP_RETRIES="${PIP_RETRIES:-10}"
export PYTHONNOUSERSITE=1
export GIT_TERMINAL_PROMPT=0
unset PYTHONPATH || true

# ───────────────────── Helpers ─────────────────────

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
elif command -v sudo >/dev/null 2>&1; then
  SUDO=(sudo)
else
  echo "[ERROR] This installer needs root access or sudo to install system packages."
  exit 1
fi

die() {
  echo "[ERROR] $*"
  exit 1
}

install_system_packages() {
  local -a packages=()

  command -v git >/dev/null 2>&1 || packages+=(git)
  command -v ffmpeg >/dev/null 2>&1 || packages+=(ffmpeg)
  command -v gcc >/dev/null 2>&1 || packages+=(build-essential)
  command -v make >/dev/null 2>&1 || packages+=(build-essential)
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || packages+=(python3)

  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip --version >/dev/null 2>&1 || packages+=(python3-pip)
    "$PYTHON_BIN" -m venv --help >/dev/null 2>&1 || packages+=(python3-venv)
  else
    packages+=(python3-pip python3-venv)
  fi

  if (( ${#packages[@]} == 0 )); then
    echo "[INFO] System prerequisites are already installed."
    return 0
  fi

  # Remove duplicate package names while preserving order.
  local -a unique=()
  local package seen
  for package in "${packages[@]}"; do
    seen=false
    local existing
    for existing in "${unique[@]}"; do
      if [[ "$existing" == "$package" ]]; then
        seen=true
        break
      fi
    done
    [[ "$seen" == false ]] && unique+=("$package")
  done

  command -v apt-get >/dev/null 2>&1 || die "apt-get is required on this RunPod image."

  echo "[INFO] Installing missing system packages: ${unique[*]}"
  "${SUDO[@]}" apt-get update -qq
  DEBIAN_FRONTEND=noninteractive "${SUDO[@]}" apt-get install -y -qq --no-install-recommends "${unique[@]}"
}

get_node() {
  local dir="$1"
  local url="$2"

  if [[ -d "custom_nodes/$dir" ]]; then
    echo " [SKIP] $dir already present."
    return 0
  fi

  echo " • cloning $dir"

  # Shallow, blob-filtered clones are considerably faster. Fall back gracefully
  # for older Git servers or Git builds that do not support partial clone.
  if ! git clone --depth 1 --filter=blob:none "$url" "custom_nodes/$dir"; then
    rm -rf "custom_nodes/$dir"
    if ! git clone --depth 1 "$url" "custom_nodes/$dir"; then
      rm -rf "custom_nodes/$dir"
      git clone "$url" "custom_nodes/$dir"
    fi
  fi
}

write_hf_downloader() {
  HF_DOWNLOADER_SCRIPT="/tmp/aitrepreneur_hf_downloader.py"

  cat > "$HF_DOWNLOADER_SCRIPT" <<'PYDOWNLOADER'
import json
import os
import shutil
import struct
import sys
import time
from collections import defaultdict
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


COMFY_ROOT = Path(os.environ["AITREPRENEUR_COMFY_ROOT"]).resolve()
HF_REPO = os.environ["AITREPRENEUR_HF_REPO"]
WORKERS = max(1, int(os.environ.get("AITREPRENEUR_DOWNLOAD_WORKERS", "2")))
STAGING_ROOT = COMFY_ROOT / "models" / ".aitrepreneur_hf_downloads"

JOBS = [
    (HF_REPO, "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", COMFY_ROOT / "models/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"),
    (HF_REPO, "minimax_h3_audio_vae_fp32.safetensors", COMFY_ROOT / "models/vae/minimax_h3_audio_vae_fp32.safetensors"),
    (HF_REPO, "minimax_h3_video_vae_fp16.safetensors", COMFY_ROOT / "models/vae/minimax_h3_video_vae_fp16.safetensors"),
    (HF_REPO, "minimax_h3_fl2va_pruned_int8_convrot.safetensors", COMFY_ROOT / "models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
    (HF_REPO, "minimax_h3_ref2va_pruned_int8_convrot.safetensors", COMFY_ROOT / "models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
    (HF_REPO, "minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors", COMFY_ROOT / "models/loras/minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors"),
]


def human_size(value):
    if value is None:
        return "unknown size"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def safetensors_is_complete(path: Path) -> bool:
    """Validate a safetensors file from its header and tensor data offsets."""
    try:
        file_size = path.stat().st_size
        if file_size < 16:
            return False

        with path.open("rb") as handle:
            raw = handle.read(8)
            if len(raw) != 8:
                return False
            header_size = struct.unpack("<Q", raw)[0]
            if header_size <= 2 or header_size > 100 * 1024 * 1024:
                return False
            if 8 + header_size > file_size:
                return False
            header = json.loads(handle.read(header_size))

        max_end = 0
        tensor_count = 0
        for name, value in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(value, dict):
                return False
            offsets = value.get("data_offsets")
            if not isinstance(offsets, list) or len(offsets) != 2:
                return False
            start, end = offsets
            if not isinstance(start, int) or not isinstance(end, int):
                return False
            if start < 0 or end < start:
                return False
            max_end = max(max_end, end)
            tensor_count += 1

        return tensor_count > 0 and (8 + header_size + max_end) == file_size
    except (OSError, ValueError, json.JSONDecodeError, struct.error):
        return False


def local_file_is_usable(path, expected_size):
    if not path.is_file():
        return False

    actual_size = path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        return False

    if path.suffix.lower() == ".safetensors":
        return safetensors_is_complete(path)

    # The only non-safetensors file in this installer is a small upscaler.
    # Exact remote-size matching is used whenever Hub metadata is available.
    return actual_size > 1024 * 1024


def repo_sizes(repo_id):
    sizes = {}
    info = HfApi().model_info(repo_id=repo_id, files_metadata=True)

    for sibling in info.siblings or []:
        name = getattr(sibling, "rfilename", None)
        size = getattr(sibling, "size", None)
        lfs = getattr(sibling, "lfs", None)

        if size is None and lfs is not None:
            if isinstance(lfs, dict):
                size = lfs.get("size")
            else:
                size = getattr(lfs, "size", None)

        if name and isinstance(size, int):
            sizes[name] = size

    return sizes


def download_repo_group(repo_id, jobs, sizes):
    missing = []

    for filename, target in jobs:
        expected = sizes.get(filename)
        if local_file_is_usable(target, expected):
            print(f" • {target.name} exists and passed validation - skip", flush=True)
            continue

        if target.exists():
            print(
                f"   [WARN] Removing incomplete or invalid file: {target} "
                f"({human_size(target.stat().st_size)})",
                flush=True,
            )
            target.unlink()

        missing.append((filename, target))

    if not missing:
        return

    stage_dir = STAGING_ROOT / repo_id.replace("/", "--")
    stage_dir.mkdir(parents=True, exist_ok=True)
    filenames = [filename for filename, _ in missing]

    print(
        f"\n • Downloading {len(filenames)} file(s) from {repo_id} "
        f"with up to {WORKERS} parallel workers...",
        flush=True,
    )

    last_error = None
    for attempt in range(1, 4):
        try:
            snapshot_download(
                repo_id=repo_id,
                allow_patterns=filenames,
                local_dir=stage_dir,
                max_workers=WORKERS,
                local_dir_use_symlinks=False,
            )
            last_error = None
            break
        except Exception as exc:  # Hub/Xet exceptions vary across compatible versions.
            last_error = exc
            print(f"   [WARN] Download attempt {attempt}/3 failed: {exc}", flush=True)
            if attempt < 3:
                time.sleep(5 * attempt)

    if last_error is not None:
        raise RuntimeError(f"Failed downloading from {repo_id}") from last_error

    for filename, target in missing:
        source = stage_dir / filename
        expected = sizes.get(filename)

        if not local_file_is_usable(source, expected):
            source.unlink(missing_ok=True)
            raise RuntimeError(
                f"Downloaded file failed validation: {source} "
                f"(expected {human_size(expected)})"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_target = target.with_name(target.name + ".installing")
        temporary_target.unlink(missing_ok=True)
        shutil.move(str(source), str(temporary_target))
        os.replace(temporary_target, target)

        if not local_file_is_usable(target, expected):
            target.unlink(missing_ok=True)
            raise RuntimeError(f"Final model validation failed: {target}")

        print(f"   ✓ {target.name} ({human_size(target.stat().st_size)})", flush=True)


def main():
    print("Fast downloader: Hugging Face Hub + hf_xet", flush=True)
    print(f"Resume metadata: {STAGING_ROOT}", flush=True)

    grouped = defaultdict(list)
    for repo_id, filename, target in JOBS:
        grouped[repo_id].append((filename, target))

    all_sizes = {}
    for repo_id in grouped:
        try:
            all_sizes[repo_id] = repo_sizes(repo_id)
        except Exception as exc:
            # Existing safetensors can still be strongly validated offline. New or
            # missing files will naturally fail later with a useful download error.
            print(f"   [WARN] Could not fetch file sizes for {repo_id}: {exc}", flush=True)
            all_sizes[repo_id] = {}

    for repo_id, jobs in grouped.items():
        download_repo_group(repo_id, jobs, all_sizes[repo_id])

    print("\nAll model files passed validation.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[ERROR] Download interrupted. Partial data was kept for resume.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
PYDOWNLOADER
}

download_models() {
  write_hf_downloader

  export AITREPRENEUR_COMFY_ROOT="$COMFY_ROOT"
  export AITREPRENEUR_HF_REPO="$HF_REPO"
  export AITREPRENEUR_DOWNLOAD_WORKERS="$MODEL_DOWNLOAD_WORKERS"

  export HF_HOME="${HF_HOME:-$COMFY_ROOT/.cache/huggingface}"
  export HF_XET_CACHE="${HF_XET_CACHE:-$HF_HOME/xet}"
  export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-120}"
  export HF_HUB_ETAG_TIMEOUT="${HF_HUB_ETAG_TIMEOUT:-30}"
  export HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-1}"

  mkdir -p "$HF_HOME" "$HF_XET_CACHE"

  if "$PYTHON" "$HF_DOWNLOADER_SCRIPT"; then
    return 0
  fi

  echo
  echo "[WARN] The accelerated Xet download failed. Retrying with standard Hugging Face HTTP..."
  HF_HUB_DISABLE_XET=1 HF_XET_HIGH_PERFORMANCE=0 "$PYTHON" "$HF_DOWNLOADER_SCRIPT"
}

write_constraints() {
  CONSTRAINT_FILE="/tmp/aitrepreneur_constraints.txt"

  cat > "$CONSTRAINT_FILE" <<EOF
torch==${TORCH_VERSION}+${CUDA_TAG}
torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}
torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}
numpy==${PIN_NUMPY}
transformers==${PIN_TRANSFORMERS}
tokenizers${PIN_TOKENIZERS_RANGE}
huggingface-hub${PIN_HF_HUB_RANGE}
hf-xet${PIN_HF_XET_RANGE}
Pillow>=${PIN_PILLOW_MIN}
EOF

  echo "──────── Using pip constraints ────────"
  cat "$CONSTRAINT_FILE"
}

install_torch_stack() {
  echo
  echo "──────── Installing locked Torch stack ────────"

  $PYTHON -m pip install --no-input --upgrade-strategy only-if-needed \
    --index-url "$TORCH_INDEX" \
    --extra-index-url https://pypi.org/simple \
    "torch==${TORCH_VERSION}+${CUDA_TAG}" \
    "torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}" \
    "torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}"
}

install_core_pins() {
  echo
  echo "──────── Installing core pinned packages ────────"

  $PYTHON -m pip install --no-input --upgrade-strategy only-if-needed \
    "numpy==${PIN_NUMPY}" \
    "pillow>=${PIN_PILLOW_MIN}" \
    "transformers==${PIN_TRANSFORMERS}" \
    "tokenizers${PIN_TOKENIZERS_RANGE}" \
    "huggingface-hub${PIN_HF_HUB_RANGE}" \
    "hf-xet${PIN_HF_XET_RANGE}" \
    "requests>=2.32.3,<3" \
    "charset-normalizer>=2,<4" \
    "chardet<6" \
    "fsspec<=2025.3.0,>=2023.1.0"
}

install_comfyui_requirements() {
  echo
  echo "──────── Installing ComfyUI requirements ────────"

  if [[ ! -f "$COMFY_ROOT/requirements.txt" ]]; then
    die "Could not find $COMFY_ROOT/requirements.txt"
  fi

  $PYTHON -m pip install --no-input --prefer-binary \
    --upgrade-strategy only-if-needed \
    -c "$CONSTRAINT_FILE" \
    -r "$COMFY_ROOT/requirements.txt"
}

sanitize_requirements_file() {
  local input="$1"
  local output="$2"

  # Never allow custom-node requirements to replace the locked GPU stack.
  grep -Eiv '^[[:space:]]*(torch|torchvision|torchaudio|xformers|transformers|tokenizers|huggingface[-_]hub|hf[-_]xet|numpy|nvidia-|cuda-toolkit|cuda-bindings|triton)(\[[^]]*\])?([<>=!~ ;].*)?$' "$input" > "$output" || true
}

install_node_requirements_safe() {
  local req="$1"
  local req_dir
  local tmp_req

  req_dir="$(dirname "$req")"
  tmp_req="$(mktemp)"

  sanitize_requirements_file "$req" "$tmp_req"

  echo "   • $req"

  if [[ ! -s "$tmp_req" ]]; then
    echo "     ↳ [SKIP] no safe packages left after filtering"
    rm -f "$tmp_req"
    return 0
  fi

  pushd "$req_dir" >/dev/null

  if ! $PYTHON -m pip install --no-input --prefer-binary --no-build-isolation \
    --upgrade-strategy only-if-needed \
    -c "$CONSTRAINT_FILE" \
    -r "$tmp_req"; then

    echo "     ↳ [WARN] First attempt failed; retrying with build isolation..."

    $PYTHON -m pip install --no-input --prefer-binary \
      --upgrade-strategy only-if-needed \
      -c "$CONSTRAINT_FILE" \
      -r "$tmp_req" || {
        echo "     ↳ [ERROR] Failed: $req - continuing"
      }
  fi

  popd >/dev/null
  rm -f "$tmp_req"
}

protect_comfyui_manager_pins() {
  echo
  echo "──────── Protecting pinned packages from ComfyUI-Manager ────────"

  local manager_dir="$COMFY_ROOT/user/__manager"
  mkdir -p "$manager_dir"

  cat > "$manager_dir/pip_blacklist.list" <<EOF
torch
torchvision
torchaudio
xformers
transformers
tokenizers
huggingface-hub
hf-xet
numpy
nvidia-
cuda-toolkit
cuda-bindings
triton
torchcodec
EOF

  cat > "$manager_dir/pip_auto_fix.list" <<EOF
torch==${TORCH_VERSION}+${CUDA_TAG}
torchvision==${TORCHVISION_VERSION}+${CUDA_TAG}
torchaudio==${TORCHAUDIO_VERSION}+${CUDA_TAG}
transformers==${PIN_TRANSFORMERS}
tokenizers${PIN_TOKENIZERS_RANGE}
huggingface-hub${PIN_HF_HUB_RANGE}
hf-xet${PIN_HF_XET_RANGE}
numpy==${PIN_NUMPY}
EOF

  if [[ -f "$manager_dir/config.ini" ]]; then
    sed -i 's/^always_lazy_install *= *.*/always_lazy_install = False/' "$manager_dir/config.ini" || true
    sed -i 's/^use_uv *= *.*/use_uv = False/' "$manager_dir/config.ini" || true
    sed -i 's/^network_mode *= *.*/network_mode = public/' "$manager_dir/config.ini" || true
  else
    cat > "$manager_dir/config.ini" <<EOF
[default]
always_lazy_install = False
use_uv = False
network_mode = public
security_level = normal
EOF
  fi
}

final_check() {
  echo
  echo "──────── Final dependency check ────────"

  $PYTHON - <<PY
import torch
print("Torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())

if not torch.__version__.startswith("${TORCH_VERSION}"):
    raise RuntimeError(
        f"Wrong Torch version: {torch.__version__}. Expected ${TORCH_VERSION}."
    )

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is not available. Torch/CUDA install is broken.")

import torchvision
print("TorchVision:", torchvision.__version__)

import torchaudio
print("TorchAudio:", torchaudio.__version__)

import numpy
print("NumPy:", numpy.__version__)

import transformers
import tokenizers
import huggingface_hub
from importlib.metadata import version
print("Transformers:", transformers.__version__)
print("Tokenizers:", tokenizers.__version__)
print("HuggingFace Hub:", huggingface_hub.__version__)
print("hf-xet:", version("hf-xet"))

from transformers import AutoProcessor, AutoTokenizer, AutoModel, WhisperProcessor
print("Transformers import check: OK")
PY

  if [[ ! -f "$COMFY_ROOT/comfy/ldm/minimax/model.py" ]]; then
    die "This ComfyUI installation is too old and does not contain native MiniMax H3 support."
  fi

  echo "Native MiniMax H3 support check: OK"
}

# ───────────────────── System packages ─────────────────────

echo
echo "──────── Checking prerequisites ────────"
install_system_packages


# ───────────────────── Verify paths ─────────────────────

[[ -d "models" && -d "custom_nodes" ]] || die "Run this inside your ComfyUI root folder. Need models/ and custom_nodes/."

COMFY_ROOT="$(pwd)"
echo "ComfyUI root: $COMFY_ROOT"

# ───────────────────── Update ComfyUI ─────────────────────

if [[ -d "$COMFY_ROOT/.git" ]]; then
  echo
  echo "──────── Updating ComfyUI ────────"

  if ! git -C "$COMFY_ROOT" pull --ff-only; then
    echo "[WARN] ComfyUI update failed. Continuing with the current installation."
  fi
else
  echo
  echo "[WARN] This ComfyUI folder is not a Git repository, so it cannot be updated automatically."
fi

# ───────────────────── Venv ─────────────────────

if [[ ! -d "$VENV_DIR" ]]; then
  echo "──────── Creating venv at $VENV_DIR ────────"
  $PYTHON_BIN -m venv "$VENV_DIR"
fi

if [[ -f "$VENV_DIR/pyvenv.cfg" ]]; then
  sed -i 's/^include-system-site-packages = .*/include-system-site-packages = false/' "$VENV_DIR/pyvenv.cfg" || true
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

PYTHON="$(command -v python)"
PIP="$(command -v pip)"

echo "Using venv python: $PYTHON"

$PYTHON -m pip install --no-input --upgrade pip setuptools wheel

write_constraints

# ───────────────────── Baseline ─────────────────────

install_torch_stack
install_core_pins
install_comfyui_requirements

# ───────────────────── Models ─────────────────────

echo
echo "──────── Downloading MiniMax H3 Model Files ────────"
echo "Using accelerated, parallel, resumable Hugging Face downloads."
download_models

# ───────────────────── Nodes ─────────────────────

echo
echo "──────── Cloning Custom Nodes ────────"

get_node "ComfyUI-Manager"                "https://github.com/ltdrdata/ComfyUI-Manager.git"
get_node "rgthree-comfy"                  "https://github.com/rgthree/rgthree-comfy.git"
get_node "ComfyUI-KJNodes"                "https://github.com/kijai/ComfyUI-KJNodes.git"
get_node "ComfyUI-VideoHelperSuite"       "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
get_node "ComfyUI-Spectrum-MiniMax-H3"    "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git"

# ───────────────────── Patch fragile requirements ─────────────────────

if [[ "$MANAGER_ENABLE_MATRIX" != "true" ]]; then
  if [[ -f custom_nodes/ComfyUI-Manager/requirements.txt ]]; then
    sed -i 's/^matrix-client==0\.4\.0/# matrix-client disabled by installer/' \
      custom_nodes/ComfyUI-Manager/requirements.txt || true
  fi
fi

if [[ "$MANAGER_ENABLE_MATRIX" == "true" ]]; then
  $PYTHON -m pip install --no-input "urllib3==${PIN_URLLIB3_1X}"
fi

# ───────────────────── Install node requirements safely ─────────────────────

collect_reqs_all() {
  find custom_nodes -maxdepth 2 -name requirements.txt -print
}

collect_reqs_required() {
  for dir in $REQUIRED_NODES; do
    local req="custom_nodes/$dir/requirements.txt"
    [[ -f "$req" ]] && echo "$req" || echo "   • (no requirements.txt) $dir" >&2
  done
}

echo
echo "──────── Installing node requirements safely ────────"

declare -a REQ_FILES=()

if [[ "$INSTALL_ALL_NODES" == "true" ]]; then
  while IFS= read -r path; do
    REQ_FILES+=("$path")
  done < <(collect_reqs_all)
else
  while IFS= read -r path; do
    [[ -f "$path" ]] && REQ_FILES+=("$path") || true
  done < <(collect_reqs_required)
fi

for req in "${REQ_FILES[@]}"; do
  install_node_requirements_safe "$req"
done

# ───────────────────── Base extras ─────────────────────

echo
echo "──────── Installing base extras ────────"
$PYTHON -m pip install --no-input -c "$CONSTRAINT_FILE" piexif lark || true

if [[ -n "$PIN_LIBROSA_VERSION" ]]; then
  echo "──────── Installing librosa==${PIN_LIBROSA_VERSION} ────────"
  $PYTHON -m pip install --no-input -c "$CONSTRAINT_FILE" "librosa==${PIN_LIBROSA_VERSION}" || true
else
  echo "──────── Installing latest librosa ────────"
  $PYTHON -m pip install --no-input -c "$CONSTRAINT_FILE" librosa || true
fi

# ───────────────────── Protect Manager and verify ─────────────────────

install_core_pins
protect_comfyui_manager_pins
final_check

echo
echo "✅ All MiniMax H3 models and custom nodes are ready"
echo