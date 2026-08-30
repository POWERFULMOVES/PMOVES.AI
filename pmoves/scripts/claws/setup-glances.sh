#!/usr/bin/env bash
# setup-glances.sh — Install and start Glances system monitor (BoTZ expanded sense)
# Usage: ./setup-glances.sh [--port PORT] [--docker]
#
# Installs Glances with GPU + web plugins, starts web server on Tailscale.
# Part of the BoTZ 12 Expanded Senses observability layer.

set -euo pipefail

PORT="${PORT:-61208}"
USE_DOCKER=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="$2"; shift 2 ;;
        --docker)  USE_DOCKER=true; shift ;;
        *)         echo "Unknown: $1"; exit 1 ;;
    esac
done

echo "=== PMOVES Glances Setup (BoTZ Sense: System Monitor) ==="

if $USE_DOCKER; then
    echo "[Docker mode] Starting Glances container..."
    docker run -d --name pmoves-glances --restart=always \
        -p "$PORT:61208" \
        --gpus all \
        --pid host \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        nicolargo/glances:latest-full -w
    echo "Glances running at http://$(tailscale ip -4 2>/dev/null || echo localhost):$PORT"
    exit 0
fi

# Native install
echo "[1/3] Installing Glances..."
if which glances > /dev/null 2>&1; then
    echo "  Already installed: $(glances --version 2>/dev/null | head -1)"
else
    uv pip install "glances[gpu,web,docker]" 2>/dev/null || \
    pip install --quiet "glances[gpu,web,docker]" 2>/dev/null || \
    echo "  ERROR: Could not install glances (try: uv pip install glances)"
fi

echo "[2/3] Verifying GPU plugin..."
if which nvidia-smi > /dev/null 2>&1; then
    uv pip install py3nvml 2>/dev/null || pip install --quiet py3nvml 2>/dev/null || true
    echo "  GPU monitoring: enabled"
else
    echo "  GPU monitoring: no nvidia-smi found"
fi

echo "[3/3] Starting Glances web server on port $PORT..."
TS_IP=$(tailscale ip -4 2>/dev/null || echo "127.0.0.1")

# Start in background
nohup glances -w --port "$PORT" --disable-plugin cloud > /tmp/glances.log 2>&1 &
GLANCES_PID=$!
sleep 2

if kill -0 $GLANCES_PID 2>/dev/null; then
    echo ""
    echo "=== Glances Running ==="
    echo "  Web UI: http://$TS_IP:$PORT"
    echo "  API:    http://$TS_IP:$PORT/api/3/system"
    echo "  PID:    $GLANCES_PID"
    echo "  Log:    /tmp/glances.log"
else
    echo "  ERROR: Glances failed to start. Check /tmp/glances.log"
    exit 1
fi
