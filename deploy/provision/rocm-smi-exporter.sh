#!/usr/bin/env bash
# Minimal Prometheus exporter for rocm-smi metrics.
# Writes the exposition text to $METRICS_FILE; rocm-smi-http-responder.sh serves it.
set -euo pipefail

METRICS_FILE=/run/rocm-smi-metrics.prom
INTERVAL=10

while true; do
  {
    echo "# HELP rocm_gpu_temperature_celsius GPU temperature"
    echo "# TYPE rocm_gpu_temperature_celsius gauge"
    rocm-smi --showtemp --json 2>/dev/null \
      | jq -r 'to_entries[] | select(.value["Temperature (Sensor edge) (C)"]) | "rocm_gpu_temperature_celsius{gpu=\"\(.key)\"} \(.value["Temperature (Sensor edge) (C)"])"' 2>/dev/null || true

    # FIXED 2026-08-14: was `rocm-smi --showmemuse`, which returns
    #   "GPU Memory Allocated (VRAM%)" / "GPU Memory Read/Write Activity (%)"
    # and has NO "VRAM Total Used Memory (B)" key — so the select() never matched and
    # this metric emitted HELP/TYPE with zero samples, silently, since it was written.
    # The byte counters live under `--showmeminfo vram`. Verified on ROCm 7.1.0.
    echo "# HELP rocm_gpu_memory_used_bytes GPU memory used"
    echo "# TYPE rocm_gpu_memory_used_bytes gauge"
    rocm-smi --showmeminfo vram --json 2>/dev/null \
      | jq -r 'to_entries[] | select(.value["VRAM Total Used Memory (B)"]) | "rocm_gpu_memory_used_bytes{gpu=\"\(.key)\"} \(.value["VRAM Total Used Memory (B)"])"' 2>/dev/null || true

    # Added: without a total, a used-bytes gauge can't be rendered as a percentage.
    echo "# HELP rocm_gpu_memory_total_bytes GPU memory total"
    echo "# TYPE rocm_gpu_memory_total_bytes gauge"
    rocm-smi --showmeminfo vram --json 2>/dev/null \
      | jq -r 'to_entries[] | select(.value["VRAM Total Memory (B)"]) | "rocm_gpu_memory_total_bytes{gpu=\"\(.key)\"} \(.value["VRAM Total Memory (B)"])"' 2>/dev/null || true

    echo "# HELP rocm_gpu_utilization_ratio GPU utilization 0-1"
    echo "# TYPE rocm_gpu_utilization_ratio gauge"
    rocm-smi --showuse --json 2>/dev/null \
      | jq -r 'to_entries[] | select(.value["GPU use (%)"]) | "rocm_gpu_utilization_ratio{gpu=\"\(.key)\"} \((.value["GPU use (%)"] | tonumber) / 100)"' 2>/dev/null || true
  } > "${METRICS_FILE}.$$"
  mv "${METRICS_FILE}.$$" "$METRICS_FILE"
  sleep "$INTERVAL"
done
