#!/usr/bin/env bash
# PMOVES Sidecar Host Prep Script
# Run this on ANY Linux HOST with Docker (not inside the container)
# Usage: bash scripts/sidecar-host-prep.sh [CONTAINER_NAME]

set -euo pipefail

CONTAINER_NAME="${1:-PMOVES-Sidecar}"
BASE_DIR="$HOME/agent-zero/PMOVES-Sidecar"

HAS_GPU=false
HAS_OLLAMA=false

echo "=== PMOVES Sidecar Host Prep ==="
echo "Container: $CONTAINER_NAME"
echo "Base dir: $BASE_DIR"
echo ""

# --- Auto-detect capabilities ---
echo "=== Phase 0: Detect capabilities ==="

# GPU detection
if docker info 2>/dev/null | grep -q 'nvidia'; then
    HAS_GPU=true
    DEFAULT_RT=$(docker info 2>/dev/null | grep 'Default Runtime' | awk '{print $3}')
    if [ "$DEFAULT_RT" = "nvidia" ]; then
        echo "OK: nvidia runtime available (default)"
    else
        echo "WARN: nvidia runtime available but not default (current: '$DEFAULT_RT')"
        echo "  GPU passthrough will use --runtime=nvidia flag"
    fi
else
    echo "INFO: nvidia runtime not found — CPU-only mode"
fi

# Ollama detection
if command -v ollama &>/dev/null && ollama list &>/dev/null; then
    HAS_OLLAMA=true
    echo "OK: Ollama running locally ($(ollama list | wc -l) models)"
elif curl -sf http://localhost:11434/api/tags &>/dev/null; then
    HAS_OLLAMA=true
    echo "OK: Ollama reachable at localhost:11434"
else
    echo "WARN: Ollama not detected — sidecar will run without local inference"
fi

# Port check
for PORT in 5080 5081; do
    if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        echo "WARN: port $PORT is already in use"
    else
        echo "OK: port $PORT available"
    fi
done

echo ""
echo "=== Phase 1: Create data directories ==="
mkdir -p "$BASE_DIR/data/{memory,knowledge,instruments,logs,runtime}"
echo "OK: $(ls -d $BASE_DIR/data/*)"

echo ""
echo "=== Phase 2: Write sidecar.env ==="
cat > "$BASE_DIR/sidecar.env" << 'ENVEOF'
# === PMOVES Sidecar Configuration ===
# Portable — works on any device with Docker

# Topology
DOCKED_MODE=false
TOPOLOGY_MODE=standalone
PARENT_SYSTEM=PMOVES.AI
PARENT_VERSION=v1.0.0-hardened

# CHIT (dev mode -- non-enforcing)
CHIT_PASSPHRASE=dev-local-sidecar-override
CHIT_REQUIRE_SIGNATURE=false
CHIT_DECRYPT_ANCHORS=false

# JetStream (disabled -- NATS not reachable in standalone)
AGENTZERO_JETSTREAM=false
AGENTZERO_JS_UNAVAILABLE_THRESHOLD=999

# Ollama -- Local inference via host gateway
OLLAMA_URL=http://host.docker.internal:11434

# TensorZero -- Prepared (activate when compose stack available)
TENSORZERO_BASE_URL=http://host.docker.internal:3000

# Supabase -- Prepared (activate when compose stack available)
# SUPABASE_URL=
# SUPABASE_ANON_KEY=
# SUPABASE_SERVICE_KEY=

# NATS -- Disabled in standalone
# NATS_URL=nats://nats:pmoves@nats:4222

# Agent Zero ports
AGENTZERO_PORT=8080
AGENTZERO_UI_PORT=8081

# Host env leak guard
SSL_CERT_FILE=
SSL_CERT_DIR=
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=
NODE_EXTRA_CA_CERTS=
HTTP_PROXY=
HTTPS_PROXY=
NO_PROXY=
ENVEOF
echo "OK: $(wc -l < $BASE_DIR/sidecar.env) lines written"

echo ""
echo "=== Phase 3: Stop and remove existing container ==="
if docker ps -a --format '{{.Names}}' | grep -qxF "$CONTAINER_NAME"; then
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "OK: old container removed"
else
    echo "OK: no existing container to remove"
fi

echo ""
echo "=== Phase 4: Generate docker run command ==="
GPU_FLAGS=""
if [ "$HAS_GPU" = true ]; then
    if [ "${DEFAULT_RT:-}" = "nvidia" ]; then
        GPU_FLAGS="  --gpus all \\\n"
    else
        GPU_FLAGS="  --runtime=nvidia --gpus all \\\n"
    fi
fi

echo ""
echo "=== READY: Run the following to start the sidecar ==="
echo ""
echo "docker run -d \\\n  --name $CONTAINER_NAME \\\n${GPU_FLAGS}--restart unless-stopped \\\n  --cap-drop ALL \\\n  --cap-add NET_BIND_SERVICE --cap-add CHOWN --cap-add SETGID --cap-add SETUID \\\n  --security-opt no-new-privileges:true \\\n  -p 5080:8080 -p 5081:80 \\\n  -v $BASE_DIR/usr:/a0/usr \\\n  -v $BASE_DIR/data/memory:/a0/memory \\\n  -v $BASE_DIR/data/knowledge:/a0/knowledge \\\n  -v $BASE_DIR/data/instruments:/a0/instruments \\\n  -v $BASE_DIR/data/logs:/a0/logs \\\n  -v $BASE_DIR/data/runtime:/a0/runtime \\\n  --env-file $BASE_DIR/sidecar.env \\\n  --add-host host.docker.internal:host-gateway \\\n  agent0ai/agent-zero:latest"
echo ""
echo "=== After start, verify ==="
if [ "$HAS_GPU" = true ]; then
    echo "docker exec $CONTAINER_NAME nvidia-smi"
fi
if [ "$HAS_OLLAMA" = true ]; then
    echo "docker exec $CONTAINER_NAME curl -s http://host.docker.internal:11434/api/tags"
fi
echo "docker exec $CONTAINER_NAME env | grep PARENT_SYSTEM"
echo ""
echo "=== Summary ==="
echo "GPU: $HAS_GPU | Ollama: $HAS_OLLAMA | Container: $CONTAINER_NAME"
