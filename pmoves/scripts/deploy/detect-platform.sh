#!/bin/bash
# PMOVES.AI Platform Detection Script
# Detects the current platform, architecture, and GPU capabilities
# Supports: Linux, WSL2, Windows, macOS, Jetson devices
#
# Usage:
#   source scripts/deploy/detect-platform.sh
#   echo "Platform: $PLATFORM, Arch: $ARCH, GPU: $GPU"

set -e

# Color output
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Detect OS/Platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)
            # Check if WSL2
            if [ -f /proc/version ] && grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
                echo "wsl2"
            # Check if Jetson
            elif [ -f /etc/nv_tegra_release ] 2>/dev/null || [ -d /sys/devices/platform/host1x ]; then
                echo "jetson"
            else
                echo "linux"
            fi
            ;;
        Darwin*)
            echo "darwin"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Detect Architecture
detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        armv7l)
            echo "armv7"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Detect GPU capabilities
detect_gpu() {
    local gpu_type="none"
    local gpu_info=""

    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null 2>&1; then
            # Get GPU name
            gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs)

            # Check for Jetson Orin
            if echo "$gpu_name" | grep -qi "orin"; then
                gpu_type="jetson-orin"
                gpu_info="NVIDIA $gpu_name"

            # Check for other Jetson devices
            elif [ -f /etc/nv_tegra_release ]; then
                gpu_type="jetson"
                gpu_info="NVIDIA $gpu_name (Jetson)"

            # Check compute capability for CUDA 12 support
            elif nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | grep -qE "^8\.|9\."; then
                gpu_type="cuda-12"
                gpu_info="NVIDIA $gpu_name (CUDA 12+)"

            # General CUDA support
            else
                gpu_type="cuda"
                gpu_info="NVIDIA $gpu_name (CUDA)"
            fi
        fi
    fi

    # Check for AMD GPU (ROCm)
    if [ "$gpu_type" = "none" ] && command -v rocm-smi &> /dev/null; then
        gpu_type="rocm"
        gpu_info="AMD GPU (ROCm)"
    fi

    # Check for Intel GPU
    if [ "$gpu_type" = "none" ] && command -v intel_gpu_top &> /dev/null; then
        gpu_type="intel"
        gpu_info="Intel Integrated GPU"
    fi

    # Check for Apple Silicon GPU
    if [ "$gpu_type" = "none" ] && [ "$(detect_platform)" = "darwin" ] && [ "$(detect_arch)" = "arm64" ]; then
        gpu_type="apple-silicon"
        gpu_info="Apple Silicon GPU"
    fi

    if [ -n "$gpu_info" ]; then
        echo "$gpu_type:$gpu_info"
    else
        echo "$gpu_type"
    fi
}

# Detect Docker availability
detect_docker() {
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null 2>&1; then
            echo "available"
        else
            echo "installed-not-running"
        fi
    else
        echo "not-found"
    fi
}

# Detect Docker Compose version
detect_docker_compose() {
    if docker compose version &> /dev/null 2>&1; then
        echo "standalone"
    elif command -v docker-compose &> /dev/null; then
        echo "legacy"
    else
        echo "not-found"
    fi
}

# Get Jetson-specific info
get_jetson_info() {
    if [ -f /etc/nv_tegra_release ]; then
        source /etc/nv_tegra_release
        echo "Jetson Model: $JETSON_MODEL"
        echo "Jetson SDK: $JETSON_SDK"
        echo "Jetson OS: $JETSON_OS"
    fi

    if [ -f /sys/class/tegra/fuse/sku ]; then
        sku=$(cat /sys/class/tegra/fuse/sku)
        echo "SKU: $sku"
    fi
}

# Get CUDA version
get_cuda_version() {
    if command -v nvcc &> /dev/null; then
        nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//'
    elif [ -f /usr/local/cuda/version.txt ]; then
        cat /usr/local/cuda/version.txt
    elif command -v nvidia-smi &> /dev/null; then
        nvidia-smi | grep "CUDA Version" | sed 's/.*CUDA Version: //' | sed 's/ .*//'
    fi
}

# Get system resources
get_resources() {
    # Total memory in GB
    if [ "$(detect_platform)" = "linux" ] || [ "$(detect_platform)" = "jetson" ]; then
        mem_gb=$(free -g | awk '/^Mem:/{print $2}')
        cpu_cores=$(nproc)
    elif [ "$(detect_platform)" = "darwin" ]; then
        mem_gb=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
        cpu_cores=$(sysctl -n hw.ncpu)
    else
        mem_gb="unknown"
        cpu_cores="unknown"
    fi

    echo "CPU Cores: $cpu_cores"
    echo "Total Memory: ${mem_gb}GB"
}

# Main detection
PLATFORM=$(detect_platform)
ARCH=$(detect_arch)
GPU_FULL=$(detect_gpu)
GPU_TYPE=$(echo "$GPU_FULL" | cut -d: -f1)
GPU_INFO=$(echo "$GPU_FULL" | cut -d: -f2- -s)
DOCKER_STATUS=$(detect_docker)
COMPOSE_VERSION=$(detect_docker_compose)

# Export variables for use in other scripts
export PMOVES_PLATFORM="$PLATFORM"
export PMOVES_ARCH="$ARCH"
export PMOVES_GPU_TYPE="$GPU_TYPE"
export PMOVES_GPU_INFO="$GPU_INFO"
export PMOVES_DOCKER="$DOCKER_STATUS"
export PMOVES_COMPOSE="$COMPOSE_VERSION"

# Determine Docker platform specifier
case "$ARCH" in
    amd64)
        DOCKER_PLATFORM="linux/amd64"
        ;;
    arm64)
        DOCKER_PLATFORM="linux/arm64"
        ;;
    armv7)
        DOCKER_PLATFORM="linux/arm/v7"
        ;;
    *)
        DOCKER_PLATFORM="linux/amd64"
        ;;
esac

export PMOVES_DOCKER_PLATFORM="$DOCKER_PLATFORM"

# Print detection results if run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo -e "${BLUE}=== PMOVES.AI Platform Detection ===${NC}"
    echo ""
    echo -e "${GREEN}Platform:${NC}     $PLATFORM"
    echo -e "${GREEN}Architecture:${NC} $ARCH"
    echo -e "${GREEN}Docker Platform:${NC} $DOCKER_PLATFORM"
    echo ""
    if [ "$GPU_TYPE" != "none" ]; then
        echo -e "${GREEN}GPU:${NC}          $GPU_INFO"
        if [ "$GPU_TYPE" = "cuda" ] || [ "$GPU_TYPE" = "jetson" ] || [ "$GPU_TYPE" = "jetson-orin" ]; then
            cuda_ver=$(get_cuda_version)
            if [ -n "$cuda_ver" ]; then
                echo -e "${GREEN}CUDA Version:${NC} $cuda_ver"
            fi
        fi
    else
        echo -e "${YELLOW}GPU:${NC}          No GPU detected"
    fi
    echo ""
    echo -e "${GREEN}Docker:${NC}       $DOCKER_STATUS"
    echo -e "${GREEN}Docker Compose:${NC} $COMPOSE_VERSION"
    echo ""

    # Platform-specific info
    if [ "$PLATFORM" = "jetson" ]; then
        echo -e "${BLUE}=== Jetson Information ===${NC}"
        get_jetson_info
        echo ""
    fi

    echo -e "${BLUE}=== System Resources ===${NC}"
    get_resources
    echo ""

    # Deployment recommendations
    echo -e "${BLUE}=== Deployment Recommendations ===${NC}"
    case "$PLATFORM" in
        jetson)
            echo "✅ Deploy GPU-accelerated services (TensorZero, Whisper, YOLO)"
            echo "✅ Use standalone Supabase mode"
            echo "✅ Enable NATS edge routing"
            ;;
        wsl2)
            echo "✅ Full stack deployment possible"
            echo "✅ GPU services via WSL2 backend"
            echo "⚠️  Use Windows paths for data persistence"
            ;;
        linux)
            if [ "$GPU_TYPE" != "none" ]; then
                echo "✅ Full GPU-accelerated stack"
            else
                echo "⚠️  CPU-only services (no GPU detected)"
            fi
            ;;
    esac
    echo ""

    # Export script for other scripts to source
    cat <<EOF
# Source this file in other scripts:
export PMOVES_PLATFORM="$PLATFORM"
export PMOVES_ARCH="$ARCH"
export PMOVES_GPU_TYPE="$GPU_TYPE"
export PMOVES_GPU_INFO="$GPU_INFO"
export PMOVES_DOCKER_PLATFORM="$DOCKER_PLATFORM"
export PMOVES_DOCKER="$DOCKER_STATUS"
export PMOVES_COMPOSE="$COMPOSE_VERSION"
EOF
fi
