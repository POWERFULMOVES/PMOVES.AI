#!/usr/bin/env bash
# MiniMax H3 Ultra V3 - RunPod V3.3 / CUDA 13 Safe Installer
# by Aitrepreneur
#
# Designed for the Aitrepreneur ComfyUI CUDA 13 RunPod template.
#
# This installer:
# - uses the EXISTING ComfyUI Python environment
# - updates ComfyUI to the latest stable release before installing the workflow
# - restarts ComfyUI after the core update, then restarts it again after node installation
# - NEVER replaces Torch, CUDA, Triton, SageAttention, or the ComfyUI GPU stack
# - downloads the required MiniMax H3 models with HF/Xet + automatic HTTP fallbacks
# - clones the required custom nodes
# - installs only safe custom-node Python requirements
# - automatically restarts ComfyUI and verifies required nodes loaded
#
# Debug options:
#   SKIP_MODELS=true  -> skip model downloads
#   SKIP_NODES=true   -> skip node clone/update + requirements

set -euo pipefail

HF_REPO="${HF_REPO:-Aitrepreneur/FLX}"
SKIP_MODELS="${SKIP_MODELS:-false}"
SKIP_NODES="${SKIP_NODES:-false}"
HF_PARALLEL_JOBS="${HF_PARALLEL_JOBS:-2}"
HTTP_PARALLEL_JOBS="${HTTP_PARALLEL_JOBS:-3}"
ARIA_CONNECTIONS="${ARIA_CONNECTIONS:-16}"
HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-1}"
export HF_XET_HIGH_PERFORMANCE
export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-120}"
export HF_HUB_ETAG_TIMEOUT="${HF_HUB_ETAG_TIMEOUT:-30}"

# Keep Hugging Face/Xet cache on persistent RunPod storage when possible.
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"
export HF_XET_CACHE="${HF_XET_CACHE:-$HF_HOME/xet}"


die() {
    echo "[ERROR] $*" >&2
    exit 1
}

# ───────────────────── Locate ComfyUI ─────────────────────

find_comfy_root() {
    if [[ -n "${COMFY_ROOT:-}" ]]; then
        [[ -d "$COMFY_ROOT/models" && -d "$COMFY_ROOT/custom_nodes" ]] || \
            die "COMFY_ROOT is set to '$COMFY_ROOT', but models/ and custom_nodes/ were not found there."
        cd "$COMFY_ROOT"
        pwd
        return
    fi

    if [[ -d "./models" && -d "./custom_nodes" ]]; then
        pwd
        return
    fi

    local candidate
    for candidate in \
        "/workspace/runpod-slim/ComfyUI" \
        "/workspace/ComfyUI" \
        "/workspace/comfyui" \
        "/ComfyUI" \
        "/comfyui" \
        "/root/ComfyUI" \
        "/root/comfyui"; do
        if [[ -d "$candidate/models" && -d "$candidate/custom_nodes" ]]; then
            cd "$candidate"
            pwd
            return
        fi
    done

    die "Could not find ComfyUI. Run this script inside the ComfyUI folder, or set COMFY_ROOT=/path/to/ComfyUI"
}

COMFY_ROOT="$(find_comfy_root)"
cd "$COMFY_ROOT"

# ───────────────────── Use existing ComfyUI environment ─────────────────────

find_comfy_python() {
    local candidate

    if [[ -n "${COMFY_PYTHON:-}" && -x "${COMFY_PYTHON}" ]]; then
        printf '%s\n' "${COMFY_PYTHON}"
        return 0
    fi

    for candidate in \
        "$COMFY_ROOT/venv/bin/python" \
        "$COMFY_ROOT/.venv-cu130/bin/python" \
        "$COMFY_ROOT/.venv-cu128/bin/python" \
        "$COMFY_ROOT/.venv/bin/python"; do
        if [[ -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

PYTHON="$(find_comfy_python)" || \
    die "Could not find ComfyUI's Python environment. Expected venv/, .venv-cu130/, .venv-cu128/, or .venv/."

PIP_CONSTRAINT_ARGS=()
if [[ -f "/opt/comfyui-runtime-constraints.txt" ]]; then
    PIP_CONSTRAINT_ARGS=(-c "/opt/comfyui-runtime-constraints.txt")
fi

echo
echo "ComfyUI Python: $PYTHON"

"$PYTHON" - <<'PY'
import sys
import torch

print("Python:", sys.version.split()[0])
print("Torch:", torch.__version__)
print("Torch CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())

if not torch.cuda.is_available():
    raise SystemExit("ERROR: CUDA is not available in the existing ComfyUI environment.")

print("GPU:", torch.cuda.get_device_name(0))
PY

STAGING_ROOT="$COMFY_ROOT/models/.aitrepreneur_downloads"
mkdir -p "$STAGING_ROOT"

# If /workspace does not exist on this template, keep the HF cache beside ComfyUI instead.
if [[ ! -d "/workspace" ]]; then
    export HF_HOME="${COMFY_ROOT}/.cache/huggingface"
    export HF_XET_CACHE="$HF_HOME/xet"
fi
mkdir -p "$HF_HOME" "$HF_XET_CACHE"

echo
echo "ComfyUI root: $COMFY_ROOT"
echo "Hugging Face repo: $HF_REPO"

# ───────────────────── Existing tools only ─────────────────────

command -v git >/dev/null 2>&1 || \
    die "git is not available in this template. This installer will not install it automatically."


# ───────────────────── Update ComfyUI before workflow install ─────────────────────

build_comfyui_args() {
    local args_file="/workspace/runpod-slim/comfyui_args.txt"
    local extra=""

    COMFY_START_ARGS=(
        --listen 0.0.0.0
        --port 8188
        --enable-cors-header
    )

    if [[ -f "$args_file" ]]; then
        extra="$(grep -vE '^[[:space:]]*(#|$)' "$args_file" | tr '\n' ' ' || true)"

        if [[ -n "$extra" ]]; then
            # Intentional word splitting for CLI flags.
            # shellcheck disable=SC2206
            local parsed=( $extra )
            COMFY_START_ARGS+=("${parsed[@]}")
        fi
    fi

    if [[ -n "${EXTRA_ARGS:-}" ]]; then
        # Backward compatibility with the old Aitrepreneur template.
        # shellcheck disable=SC2206
        local legacy=( ${EXTRA_ARGS} )
        COMFY_START_ARGS+=("${legacy[@]}")
    fi
}


stop_comfyui_for_update() {
    local process_pattern='[p]ython.*main\.py.*--port(=|[[:space:]])8188'
    local current_pids=""

    current_pids="$(pgrep -f "$process_pattern" 2>/dev/null || true)"

    if [[ -z "$current_pids" ]]; then
        echo "No running ComfyUI process found."
        return 0
    fi

    echo "Stopping ComfyUI before updating..."

    while IFS= read -r pid; do
        if [[ -n "$pid" ]]; then
            echo " • stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done <<< "$current_pids"

    for _ in {1..30}; do
        if ! pgrep -f "$process_pattern" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done

    echo "[ERROR] The old ComfyUI process did not stop cleanly."
    pgrep -af "$process_pattern" || true
    return 1
}


update_comfyui_to_latest_stable() {
    local latest=""
    local current=""
    local tmp_req=""

    echo
    echo "──────── Updating ComfyUI to Latest Stable ────────"

    if [[ ! -d "$COMFY_ROOT/.git" ]]; then
        echo "[WARN] $COMFY_ROOT is not a Git repository."
        echo "[WARN] ComfyUI cannot be updated automatically; keeping the current version."
        return 0
    fi

    git -C "$COMFY_ROOT" remote set-url \
        origin \
        https://github.com/Comfy-Org/ComfyUI.git \
        >/dev/null 2>&1 || true

    latest="$(
        git ls-remote \
            --tags \
            --refs \
            https://github.com/Comfy-Org/ComfyUI.git \
            'refs/tags/v*' \
            2>/dev/null \
        | awk '{
            sub("refs/tags/", "", $2)
            print $2
        }' \
        | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' \
        | sort -V \
        | tail -n 1 \
        || true
    )"

    if [[ -z "$latest" ]]; then
        echo "[WARN] Could not check the latest stable ComfyUI release."
        echo "[WARN] Keeping the currently installed version."
        return 0
    fi

    current="$(
        git -C "$COMFY_ROOT" \
            describe \
            --tags \
            --exact-match \
            2>/dev/null \
            || true
    )"

    if [[ "$current" == "$latest" ]]; then
        echo "ComfyUI is already latest stable: $latest"
        return 0
    fi

    echo "Updating ComfyUI: ${current:-current build} -> $latest"

    if ! git -C "$COMFY_ROOT" fetch \
        --depth 1 \
        origin \
        "refs/tags/${latest}:refs/tags/${latest}"; then

        echo "[WARN] Could not download ComfyUI $latest."
        echo "[WARN] Keeping the currently installed version."
        return 0
    fi

    tmp_req="$(mktemp)"

    if ! git -C "$COMFY_ROOT" \
        show "${latest}:requirements.txt" \
        > "$tmp_req"; then

        echo "[WARN] Could not read the requirements for $latest."
        rm -f "$tmp_req"
        return 0
    fi

    echo "Installing requirements for $latest without replacing the CUDA 13 runtime..."

    if ! "$PYTHON" -m pip install \
        --no-input \
        --prefer-binary \
        --upgrade-strategy only-if-needed \
        "${PIP_CONSTRAINT_ARGS[@]}" \
        -r "$tmp_req"; then

        echo "[WARN] ComfyUI dependency update failed."
        echo "[WARN] Keeping the currently installed ComfyUI core."
        rm -f "$tmp_req"
        return 0
    fi

    rm -f "$tmp_req"

    git -C "$COMFY_ROOT" reset --hard "$latest"

    echo "✅ ComfyUI updated to $latest."
}


start_comfyui_after_update() {
    local log_file="/workspace/logs/comfyui.log"
    local new_pid=""
    local log_start=1
    local new_log=""

    echo
    echo "──────── Starting Updated ComfyUI ────────"

    build_comfyui_args

    mkdir -p "$(dirname "$log_file")"

    if [[ -f "$log_file" ]]; then
        log_start=$(( $(wc -l < "$log_file") + 1 ))
    fi

    {
        echo
        echo "================================================"
        echo " ComfyUI restart after core update"
        echo "================================================"
    } >> "$log_file"

    cd "$COMFY_ROOT"

    nohup "$PYTHON" main.py "${COMFY_START_ARGS[@]}" \
        >> "$log_file" 2>&1 </dev/null &

    new_pid=$!

    echo "Starting updated ComfyUI as PID $new_pid..."

    for _ in {1..120}; do
        if ! kill -0 "$new_pid" 2>/dev/null; then
            echo "[ERROR] Updated ComfyUI exited during startup."
            tail -n 100 "$log_file" 2>/dev/null || true
            return 1
        fi

        new_log="$(tail -n +"$log_start" "$log_file" 2>/dev/null || true)"

        if grep -Fq "Starting server" <<< "$new_log"; then
            echo "✅ Updated ComfyUI is running."
            return 0
        fi

        sleep 1
    done

    echo "[ERROR] Updated ComfyUI did not become ready within 120 seconds."
    tail -n 100 "$log_file" 2>/dev/null || true
    return 1
}


echo
echo "──────── Preparing Latest ComfyUI ────────"

stop_comfyui_for_update || \
    die "Could not stop ComfyUI before the update."

update_comfyui_to_latest_stable

start_comfyui_after_update || \
    die "ComfyUI failed to restart after the update."

echo
echo "✅ Latest stable ComfyUI is running."
echo "Continuing with MiniMax H3 models and custom nodes."


# ───────────────────── Existing downloader tools ─────────────────────

HAS_HF=false
HAS_ARIA=false
HAS_CURL=false
HAS_WGET=false

command -v hf >/dev/null 2>&1 && HAS_HF=true
command -v aria2c >/dev/null 2>&1 && HAS_ARIA=true
command -v curl >/dev/null 2>&1 && HAS_CURL=true
command -v wget >/dev/null 2>&1 && HAS_WGET=true

if [[ "$HAS_HF" != true && "$HAS_ARIA" != true && "$HAS_CURL" != true && "$HAS_WGET" != true ]]; then
    die "No supported model downloader exists in this template. Need an existing hf, aria2c, curl, or wget command."
fi

if [[ "$HAS_HF" == true ]]; then
    PRIMARY_DOWNLOADER="hf"
    MODEL_PARALLEL_JOBS="$HF_PARALLEL_JOBS"
    echo "Fast downloader: Hugging Face hf CLI (Xet/high-performance enabled when supported)"
    echo "Parallel model jobs: $MODEL_PARALLEL_JOBS"
elif [[ "$HAS_ARIA" == true ]]; then
    PRIMARY_DOWNLOADER="aria2c"
    MODEL_PARALLEL_JOBS="$HTTP_PARALLEL_JOBS"
    echo "Fast downloader: aria2c (${ARIA_CONNECTIONS} connections/file)"
    echo "Parallel model jobs: $MODEL_PARALLEL_JOBS"
elif [[ "$HAS_CURL" == true ]]; then
    PRIMARY_DOWNLOADER="curl"
    MODEL_PARALLEL_JOBS="$HTTP_PARALLEL_JOBS"
    echo "Downloader: curl"
    echo "Parallel model jobs: $MODEL_PARALLEL_JOBS"
else
    PRIMARY_DOWNLOADER="wget"
    MODEL_PARALLEL_JOBS="$HTTP_PARALLEL_JOBS"
    echo "Downloader: wget"
    echo "Parallel model jobs: $MODEL_PARALLEL_JOBS"
fi

# ───────────────────── Lightweight safetensors validation ─────────────────────

VALIDATOR_PY="$PYTHON"

safetensors_is_complete() {
    local file="$1"

    [[ -s "$file" ]] || return 1

    # ComfyUI templates already have Python in practice, but we do not install or modify it.
    # If Python is unavailable, use a conservative minimum-size check instead.
    if [[ -z "$VALIDATOR_PY" ]]; then
        [[ "$(stat -c%s "$file" 2>/dev/null || echo 0)" -gt 1048576 ]]
        return
    fi

    "$VALIDATOR_PY" - "$file" <<'PY' >/dev/null 2>&1
import json
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
size = path.stat().st_size
if size < 16:
    raise SystemExit(1)

with path.open("rb") as f:
    raw = f.read(8)
    if len(raw) != 8:
        raise SystemExit(1)
    header_size = struct.unpack("<Q", raw)[0]
    if header_size <= 2 or header_size > 100 * 1024 * 1024:
        raise SystemExit(1)
    if 8 + header_size > size:
        raise SystemExit(1)
    header = json.loads(f.read(header_size))

max_end = 0
count = 0
for name, value in header.items():
    if name == "__metadata__":
        continue
    if not isinstance(value, dict):
        raise SystemExit(1)
    offsets = value.get("data_offsets")
    if not isinstance(offsets, list) or len(offsets) != 2:
        raise SystemExit(1)
    start, end = offsets
    if not isinstance(start, int) or not isinstance(end, int):
        raise SystemExit(1)
    if start < 0 or end < start:
        raise SystemExit(1)
    max_end = max(max_end, end)
    count += 1

if count <= 0 or (8 + header_size + max_end) != size:
    raise SystemExit(1)
PY
}

# ───────────────────── Individual download methods ─────────────────────

try_hf_download() {
    local repo_file="$1"
    local stage_dir="$2"
    local stage_file="$stage_dir/$repo_file"

    [[ "$HAS_HF" == true ]] || return 1

    mkdir -p "$stage_dir"

    HF_XET_HIGH_PERFORMANCE="$HF_XET_HIGH_PERFORMANCE" \
    HF_HOME="$HF_HOME" \
    HF_XET_CACHE="$HF_XET_CACHE" \
        hf download "$HF_REPO" "$repo_file" --local-dir "$stage_dir" >/dev/null

    safetensors_is_complete "$stage_file"
}

try_aria_download() {
    local repo_file="$1"
    local stage_file="$2"
    local url="https://huggingface.co/${HF_REPO}/resolve/main/${repo_file}?download=true"

    [[ "$HAS_ARIA" == true ]] || return 1

    mkdir -p "$(dirname "$stage_file")"

    aria2c \
        --continue=true \
        --max-connection-per-server="$ARIA_CONNECTIONS" \
        --split="$ARIA_CONNECTIONS" \
        --min-split-size=8M \
        --file-allocation=none \
        --auto-file-renaming=false \
        --allow-overwrite=true \
        --max-tries=10 \
        --retry-wait=2 \
        --connect-timeout=30 \
        --timeout=120 \
        --console-log-level=warn \
        --summary-interval=10 \
        --dir="$(dirname "$stage_file")" \
        --out="$(basename "$stage_file")" \
        "$url"

    safetensors_is_complete "$stage_file"
}

try_curl_download() {
    local repo_file="$1"
    local stage_file="$2"
    local url="https://huggingface.co/${HF_REPO}/resolve/main/${repo_file}?download=true"

    [[ "$HAS_CURL" == true ]] || return 1

    mkdir -p "$(dirname "$stage_file")"

    curl \
        --location \
        --fail \
        --retry 10 \
        --retry-delay 2 \
        --retry-all-errors \
        --connect-timeout 30 \
        --continue-at - \
        --output "$stage_file" \
        "$url"

    safetensors_is_complete "$stage_file"
}

try_wget_download() {
    local repo_file="$1"
    local stage_file="$2"
    local url="https://huggingface.co/${HF_REPO}/resolve/main/${repo_file}?download=true"

    [[ "$HAS_WGET" == true ]] || return 1

    mkdir -p "$(dirname "$stage_file")"

    wget \
        --continue \
        --tries=10 \
        --timeout=120 \
        --output-document="$stage_file" \
        "$url"

    safetensors_is_complete "$stage_file"
}

# ───────────────────── Model downloader with automatic fallback ─────────────────────

download_model() {
    local repo_file="$1"
    local destination="$2"
    local destination_name
    local hf_stage_dir
    local http_stage_file

    destination_name="$(basename "$destination")"
    hf_stage_dir="$STAGING_ROOT/hf/$destination_name"
    http_stage_file="$STAGING_ROOT/http/${destination_name}.part"

    mkdir -p "$(dirname "$destination")"

    if safetensors_is_complete "$destination"; then
        echo " [SKIP] $destination_name already exists and passed validation."
        return 0
    fi

    if [[ -e "$destination" ]]; then
        echo " [WARN] Removing incomplete model: $destination_name"
        rm -f "$destination"
    fi

    echo " • downloading $destination_name"

    # 1) Prefer HF CLI. Modern huggingface_hub uses hf_xet automatically when available.
    if try_hf_download "$repo_file" "$hf_stage_dir"; then
        mv -f "$hf_stage_dir/$repo_file" "$destination"
        echo "   ✓ $destination_name [HF/Xet]"
        return 0
    fi

    if [[ "$HAS_HF" == true ]]; then
        echo "   ↳ HF/Xet path failed; trying direct HTTP fallback..."
    fi

    # 2) Fast direct HTTP fallback: aria2c first, then curl, then wget.
    if try_aria_download "$repo_file" "$http_stage_file"; then
        mv -f "$http_stage_file" "$destination"
        rm -f "${http_stage_file}.aria2" 2>/dev/null || true
        echo "   ✓ $destination_name [aria2c]"
        return 0
    fi

    if [[ "$HAS_ARIA" == true ]]; then
        echo "   ↳ aria2c failed; trying curl/wget fallback..."
    fi

    if try_curl_download "$repo_file" "$http_stage_file"; then
        mv -f "$http_stage_file" "$destination"
        echo "   ✓ $destination_name [curl]"
        return 0
    fi

    if try_wget_download "$repo_file" "$http_stage_file"; then
        mv -f "$http_stage_file" "$destination"
        echo "   ✓ $destination_name [wget]"
        return 0
    fi

    echo "   ✗ FAILED: $destination_name" >&2
    return 1
}

# ───────────────────── Parallel model queue ─────────────────────

MODEL_JOBS=(
    "qwen3vl_32b_minimax_h3_int8_convrot.safetensors|models/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    "minimax_h3_audio_vae_fp32.safetensors|models/vae/minimax_h3_audio_vae_fp32.safetensors"
    "minimax_h3_video_vae_fp16.safetensors|models/vae/minimax_h3_video_vae_fp16.safetensors"
    "minimax_h3_fl2va_pruned_int8_convrot.safetensors|models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
    "minimax_h3_ref2va_pruned_int8_convrot.safetensors|models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
    "minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors|models/loras/minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors"
    "minimax_h3_t1_image_vae_step1597.safetensors|models/vae/minimax_h3_t1_image_vae_step1597.safetensors"
    "taeh3.safetensors|models/vae_approx/taeh3.safetensors"
    "minimax_h3_latent_upscaler_3d_fp16.safetensors|models/latent_upscale_models/minimax_h3_latent_upscaler_3d_fp16.safetensors"
    "sam3.1_multiplex_fp16.safetensors|models/checkpoints/sam3.1_multiplex_fp16.safetensors"
)

run_model_queue() {
    local fifo
    local failed=0
    local entry repo_file relative_path pid
    local -a pids=()

    fifo="$(mktemp -u)"
    mkfifo "$fifo"
    exec 9<>"$fifo"
    rm -f "$fifo"

    # Semaphore tokens.
    for ((i=0; i<MODEL_PARALLEL_JOBS; i++)); do
        printf '.' >&9
    done

    for entry in "${MODEL_JOBS[@]}"; do
        repo_file="${entry%%|*}"
        relative_path="${entry#*|}"

        (
            read -r -n 1 <&9
            status=0
            download_model "$repo_file" "$COMFY_ROOT/$relative_path" || status=$?
            printf '.' >&9
            exit "$status"
        ) &
        pids+=("$!")
    done

    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            failed=1
        fi
    done

    exec 9>&-
    exec 9<&-

    [[ "$failed" -eq 0 ]]
}

echo
echo "──────── FAST MiniMax H3 Model Downloads ────────"
echo "HF_XET_HIGH_PERFORMANCE=$HF_XET_HIGH_PERFORMANCE"
echo

if [[ "$SKIP_MODELS" == "true" ]]; then
    echo "[SKIP] Model downloads disabled with SKIP_MODELS=true."
else
    if ! run_model_queue; then
        die "One or more model downloads failed. Re-run the installer to resume/retry."
    fi
fi

# ───────────────────── Custom nodes ─────────────────────

get_node() {
    local dir="$1"
    local url="$2"
    local target="$COMFY_ROOT/custom_nodes/$dir"

    if [[ -d "$target" ]]; then
        echo " [SKIP] $dir already exists."
        return 0
    fi

    echo " • cloning $dir"

    if ! git clone --depth 1 --filter=blob:none "$url" "$target"; then
        rm -rf "$target"

        if ! git clone --depth 1 "$url" "$target"; then
            rm -rf "$target"
            git clone "$url" "$target"
        fi
    fi
}

echo
echo "──────── Cloning MiniMax H3 Custom Nodes ────────"

REQUIRED_NODES=(
    "ComfyUI-Manager"
    "rgthree-comfy"
    "ComfyUI-KJNodes"
    "ComfyUI-VideoHelperSuite"
    "ComfyUI-Spectrum-MiniMax-H3"
    "ComfyUI-MiniMaxH3-Director"
    "ComfyUI-Fantastic-MiniMaxH3-PromptBuilder"
    "ComfyUi-Scale-Image-to-Total-Pixels-Advanced"
    "ComfyUI-MiniMaxH3-T1-Latent"
    "ComfyUI-H3-Motion-Context-MultiRef"
    "MaskVidExperiments"
    "ComfyUI-NKD-Basic-Tools"
    "Comfyui_Minimax_h3_latent_Upscaler"
)

if [[ "$SKIP_NODES" == "true" ]]; then
    echo "[SKIP] Node setup disabled with SKIP_NODES=true."
else
    get_node "ComfyUI-Manager" \
        "https://github.com/ltdrdata/ComfyUI-Manager.git"

    get_node "rgthree-comfy" \
        "https://github.com/rgthree/rgthree-comfy.git"

    get_node "ComfyUI-KJNodes" \
        "https://github.com/kijai/ComfyUI-KJNodes.git"

    get_node "ComfyUI-VideoHelperSuite" \
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"

    get_node "ComfyUI-Spectrum-MiniMax-H3" \
        "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3.git"

    get_node "ComfyUI-MiniMaxH3-Director" \
        "https://github.com/seesee75-commits/ComfyUI-MiniMaxH3-Director.git"

    get_node "ComfyUI-Fantastic-MiniMaxH3-PromptBuilder" \
        "https://github.com/Adudeguyman/ComfyUI-Fantastic-MiniMaxH3-PromptBuilder.git"

    get_node "ComfyUi-Scale-Image-to-Total-Pixels-Advanced" \
        "https://github.com/BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced.git"

    get_node "ComfyUI-MiniMaxH3-T1-Latent" \
        "https://github.com/aitrepreneur/ComfyUI-MiniMaxH3-T1-Latent.git"

    get_node "ComfyUI-H3-Motion-Context-MultiRef" \
        "https://github.com/Aitrepreneur/ComfyUI-H3-Motion-Context-MultiRef-V3.git"

    get_node "MaskVidExperiments" \
        "https://github.com/drozbay/MaskVidExperiments.git"

    get_node "ComfyUI-NKD-Basic-Tools" \
        "https://github.com/Nekodificador/ComfyUI-NKD-Basic-Tools.git"

    get_node "Comfyui_Minimax_h3_latent_Upscaler" \
        "https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler.git"

    # ───────────────────── Safe node requirements ─────────────────────

    sanitize_requirements() {
        local input="$1"
        local output="$2"

        # These packages belong to the template/runtime. Custom nodes are never
        # allowed to replace them.
        grep -Eiv \
            '^[[:space:]]*(torch|torchvision|torchaudio|xformers|triton|sageattention|numpy|transformers|tokenizers|huggingface[-_]hub|hf[-_]xet|pillow|nvidia-|cuda-|comfy[-_]kitchen|comfy[-_]aimdo|comfyui[-_]frontend[-_]package|comfyui[-_]workflow[-_]templates|comfyui[-_]embedded[-_]docs)(\[[^]]*\])?([<>=!~ ;].*)?$' \
            "$input" > "$output" || true
    }

    install_node_requirements() {
        local node="$1"
        local req="$COMFY_ROOT/custom_nodes/$node/requirements.txt"
        local tmp_req

        [[ -f "$req" ]] || {
            echo " [SKIP] $node has no requirements.txt"
            return 0
        }

        tmp_req="$(mktemp)"
        sanitize_requirements "$req" "$tmp_req"

        if [[ ! -s "$tmp_req" ]]; then
            echo " [SKIP] $node has no additional safe Python requirements."
            rm -f "$tmp_req"
            return 0
        fi

        echo " • installing safe requirements for $node"

        if ! "$PYTHON" -m pip install \
            --no-input \
            --prefer-binary \
            --upgrade-strategy only-if-needed \
            "${PIP_CONSTRAINT_ARGS[@]}" \
            -r "$tmp_req"; then

            echo " [WARN] Some optional requirements for $node failed to install."
        fi

        rm -f "$tmp_req"
    }

    echo
    echo "──────── Installing Safe Node Requirements ────────"

    for node in "${REQUIRED_NODES[@]}"; do
        # The CUDA 13 template already manages these two core nodes itself.
        # Their requirements are still harmless to skip here.
        if [[ "$node" == "ComfyUI-Manager" || "$node" == "ComfyUI-KJNodes" ]]; then
            echo " [SKIP] $node is managed by the RunPod template."
            continue
        fi

        install_node_requirements "$node"
    done

    # Verified dependency needed by VideoHelperSuite. This is intentionally
    # installed without changing any GPU/runtime packages.
    "$PYTHON" -m pip install \
        --no-input \
        --prefer-binary \
        --upgrade-strategy only-if-needed \
        "${PIP_CONSTRAINT_ARGS[@]}" \
        imageio-ffmpeg >/dev/null
fi


# ───────────────────── Automatic ComfyUI restart ─────────────────────

restart_comfyui() {
    local log_file="/workspace/logs/comfyui.log"
    local args_file="/workspace/runpod-slim/comfyui_args.txt"
    local process_pattern='[p]ython.*main\.py.*--port(=|[[:space:]])8188'
    local -a args=(
        --listen 0.0.0.0
        --port 8188
        --enable-cors-header
    )
    local extra=""
    local current_pids=""
    local new_pid=""
    local log_start=1
    local new_log=""
    local missing=0
    local node=""

    echo
    echo "──────── Restarting ComfyUI ────────"

    # Reuse any arguments configured in the Aitrepreneur RunPod template.
    if [[ -f "$args_file" ]]; then
        extra="$(grep -vE '^[[:space:]]*(#|$)' "$args_file" | tr '
' ' ' || true)"

        if [[ -n "$extra" ]]; then
            # Intentional word splitting for CLI flags.
            # shellcheck disable=SC2206
            local parsed=( $extra )
            args+=("${parsed[@]}")
        fi
    fi

    # Backward compatibility with the old template.
    if [[ -n "${EXTRA_ARGS:-}" ]]; then
        # Intentional word splitting for CLI flags.
        # shellcheck disable=SC2206
        local legacy=( ${EXTRA_ARGS} )
        args+=("${legacy[@]}")
    fi

    # IMPORTANT:
    # The template exposes ComfyUI/venv as a compatibility symlink, but the
    # running process can appear as .venv-cu128/bin/python in `ps`.
    # Therefore detect ComfyUI by its main.py + port instead of the exact
    # Python path.
    current_pids="$(pgrep -f "$process_pattern" 2>/dev/null || true)"

    if [[ -n "$current_pids" ]]; then
        echo "Stopping current ComfyUI process..."

        while IFS= read -r pid; do
            if [[ -n "$pid" ]]; then
                echo " • stopping PID $pid"
                kill "$pid" 2>/dev/null || true
            fi
        done <<< "$current_pids"

        # Wait up to 15 seconds for all old ComfyUI processes to exit.
        for _ in {1..30}; do
            if ! pgrep -f "$process_pattern" >/dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done

        # Do not start a second ComfyUI if the old process refused to exit.
        if pgrep -f "$process_pattern" >/dev/null 2>&1; then
            echo "[ERROR] The old ComfyUI process did not stop cleanly."
            pgrep -af "$process_pattern" || true
            return 1
        fi
    else
        echo "No running ComfyUI process found; starting a fresh one."
    fi

    mkdir -p "$(dirname "$log_file")"

    if [[ -f "$log_file" ]]; then
        log_start=$(( $(wc -l < "$log_file") + 1 ))
    fi

    {
        echo
        echo "================================================"
        echo " ComfyUI restarted by Aitrepreneur installer"
        echo "================================================"
    } >> "$log_file"

    cd "$COMFY_ROOT"

    nohup "$PYTHON" main.py "${args[@]}" \
        >> "$log_file" 2>&1 </dev/null &

    new_pid=$!

    echo "Starting ComfyUI as PID $new_pid..."

    # Wait for THIS new process to finish custom-node imports and reach
    # "Starting server". Do not use "port 8188 is open" as the readiness test,
    # because an old/stale process could make that look successful.
    for _ in {1..120}; do
        if ! kill -0 "$new_pid" 2>/dev/null; then
            echo "[ERROR] ComfyUI exited while restarting."
            echo "Last log lines:"
            tail -n 100 "$log_file" 2>/dev/null || true
            return 1
        fi

        new_log="$(tail -n +"$log_start" "$log_file" 2>/dev/null || true)"

        if grep -Fq "Starting server" <<< "$new_log"; then
            break
        fi

        sleep 1
    done

    new_log="$(tail -n +"$log_start" "$log_file" 2>/dev/null || true)"

    if ! grep -Fq "Starting server" <<< "$new_log"; then
        echo "[ERROR] ComfyUI did not finish starting within 120 seconds."
        tail -n 100 "$log_file" 2>/dev/null || true
        return 1
    fi

    echo "✅ ComfyUI restarted and reached server startup."

    # Verify every custom-node package required by this workflow appeared in
    # the fresh startup log.
    for node in \
        "rgthree-comfy" \
        "ComfyUI-VideoHelperSuite" \
        "ComfyUI-Spectrum-MiniMax-H3" \
        "ComfyUI-MiniMaxH3-Director" \
        "ComfyUI-Fantastic-MiniMaxH3-PromptBuilder" \
        "ComfyUi-Scale-Image-to-Total-Pixels-Advanced" \
        "ComfyUI-MiniMaxH3-T1-Latent" \
        "ComfyUI-H3-Motion-Context-MultiRef" \
        "MaskVidExperiments" \
        "ComfyUI-NKD-Basic-Tools" \
        "Comfyui_Minimax_h3_latent_Upscaler"
    do
        if grep -Fq "/custom_nodes/${node}" <<< "$new_log"; then
            echo "   ✓ Loaded: $node"
        else
            echo "   ✗ NOT LOADED: $node"
            missing=1
        fi
    done

    if [[ "$missing" -ne 0 ]]; then
        echo
        echo "[ERROR] ComfyUI restarted, but one or more required nodes did not load."
        echo "Check: tail -n 200 $log_file"
        return 1
    fi

    # Final sanity check: the new process must still be alive.
    if ! kill -0 "$new_pid" 2>/dev/null; then
        echo "[ERROR] ComfyUI stopped after startup."
        tail -n 100 "$log_file" 2>/dev/null || true
        return 1
    fi

    echo
    echo "✅ All required MiniMax H3 nodes loaded."
    echo "✅ You can now drag and drop the workflow into ComfyUI."
}


echo
echo "──────── Final Runtime Check ────────"

"$PYTHON" - <<'PY'
import torch

print("Torch:", torch.__version__)
print("Torch CUDA:", torch.version.cuda)
print("GPU:", torch.cuda.get_device_name(0))

try:
    import sageattention
    print("SageAttention: OK")
except Exception as exc:
    print("SageAttention: not available in this environment:", exc)

try:
    import imageio_ffmpeg
    print("imageio-ffmpeg:", imageio_ffmpeg.__version__)
except Exception as exc:
    print("imageio-ffmpeg check failed:", exc)
PY

echo
echo "✅ MiniMax H3 RunPod setup is ready."
echo "✅ Existing Torch / CUDA / SageAttention stack was left untouched."

restart_comfyui

echo
echo "================================================"
echo " ✅ INSTALLATION COMPLETE"
echo " ComfyUI is ready - drag and drop the workflow."
echo "================================================"
