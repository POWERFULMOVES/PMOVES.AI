#!/usr/bin/env bash
set -euo pipefail

: "${VIBEVOICE_MODEL_ID:=microsoft/VibeVoice-Realtime-0.5B}"
: "${VIBEVOICE_MODEL_DIR:=/models}"
: "${VIBEVOICE_PORT:=3000}"
: "${VIBEVOICE_DEVICE:=auto}"

# Cache dir tracks the model ID basename so changing VIBEVOICE_MODEL_ID uses a
# fresh dir instead of silently reusing the previous model's cache (Codex P2).
MODEL_PATH="${VIBEVOICE_MODEL_DIR}/${VIBEVOICE_MODEL_ID##*/}"

resolved_device="cpu"
if [ "${VIBEVOICE_DEVICE}" = "cuda" ] || [ "${VIBEVOICE_DEVICE}" = "auto" ]; then
  if python - <<'PY'
from __future__ import annotations

import torch

if not torch.cuda.is_available():
    raise SystemExit(2)

try:
    # Cheap sanity check that will fail on unsupported SMs with
    # "no kernel image is available for execution on the device".
    x = torch.ones(1, device="cuda") * 2
    _ = x.cpu()
except Exception as exc:  # noqa: BLE001
    print(f"CUDA probe failed: {exc}")
    raise SystemExit(3)

name = torch.cuda.get_device_name(0)
cap = torch.cuda.get_device_capability(0)
print(f"CUDA OK: {name} capability={cap}")
PY
  then
    resolved_device="cuda"
  else
    echo "↷ CUDA not usable on this GPU; falling back to --device cpu (the installed PyTorch build may lack kernels for this GPU's compute capability)."
    resolved_device="cpu"
  fi
fi

# Honor an explicit non-cuda device (cpu, mps, ...) verbatim. cuda and auto are
# resolved by the probe above (with a cpu fallback) -- do NOT override cuda back
# on top of that fallback, or an explicit `--device cuda` crashes when CUDA is
# unusable instead of degrading to cpu (CodeRabbit Major).
if [ "${VIBEVOICE_DEVICE}" != "auto" ] && [ "${VIBEVOICE_DEVICE}" != "cuda" ]; then
  resolved_device="${VIBEVOICE_DEVICE}"
fi

python - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download

model_id = os.environ.get("VIBEVOICE_MODEL_ID", "microsoft/VibeVoice-Realtime-0.5B")
base = Path(os.environ.get("VIBEVOICE_MODEL_DIR", "/models"))
# Match MODEL_PATH in the shell wrapper: cache dir = model-id basename, so
# switching VIBEVOICE_MODEL_ID re-downloads instead of reusing a stale cache.
target = base / model_id.split("/")[-1]

target.mkdir(parents=True, exist_ok=True)
has_files = any(target.iterdir())

if not has_files:
    print(f"→ Downloading {model_id} to {target} ...")
    snapshot_download(repo_id=model_id, local_dir=str(target), local_dir_use_symlinks=False)
else:
    print(f"→ Model already present at {target}")
PY

exec python demo/vibevoice_realtime_demo.py \
  --model_path "$MODEL_PATH" \
  --port "$VIBEVOICE_PORT" \
  --device "$resolved_device"
