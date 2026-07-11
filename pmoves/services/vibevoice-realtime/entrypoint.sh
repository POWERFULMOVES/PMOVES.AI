#!/usr/bin/env bash
set -euo pipefail

: "${VIBEVOICE_MODEL_ID:=microsoft/VibeVoice-Realtime-0.5B}"
: "${VIBEVOICE_MODEL_DIR:=/models}"
: "${VIBEVOICE_PORT:=3000}"
: "${VIBEVOICE_DEVICE:=auto}"

MODEL_PATH="${VIBEVOICE_MODEL_DIR}/VibeVoice-Realtime-0.5B"

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
    echo "↷ CUDA not usable; falling back to --device cpu (RTX 5090 often needs a newer PyTorch build)."
    resolved_device="cpu"
  fi
fi

if [ "${VIBEVOICE_DEVICE}" != "auto" ]; then
  resolved_device="${VIBEVOICE_DEVICE}"
fi

python - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download

model_id = os.environ.get("VIBEVOICE_MODEL_ID", "microsoft/VibeVoice-Realtime-0.5B")
base = Path(os.environ.get("VIBEVOICE_MODEL_DIR", "/models"))
target = base / "VibeVoice-Realtime-0.5B"

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
