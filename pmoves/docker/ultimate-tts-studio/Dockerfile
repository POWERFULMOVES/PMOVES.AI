# PMOVES.AI Hardened Ultimate-TTS-Studio
# Multi-engine TTS with all 7 engines (KittenTTS, Kokoro, F5-TTS, IndexTTS2, Fish, Chatterbox, VoxCPM)
# Clones from PMOVES fork: github.com/POWERFULMOVES/PMOVES-Ultimate-TTS-Studio
# Following PMOVES.AI security standards: non-root, health checks, minimal surface

ARG CUDA_VERSION=12.4.1

# Stage 1: Builder - Install all dependencies
# =============================================================================
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # WSL2/CUDA compatibility settings
    CUDA_FORCE_PTX_JIT=1 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    TORCH_CUDA_ARCH_LIST="5.0;5.2;6.0;6.1;7.0;7.5;8.0;8.6;9.0" \
    TORCH_CUDNN_V8_API_ENABLED=1

WORKDIR /build

# System deps for audio + build utilities (cmake/protobuf for onnx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    libespeak-ng-dev \
    libsndfile1 \
    libportaudio2 \
    portaudio19-dev \
    libaio-dev \
    libsox-dev \
    sox \
    git \
    curl \
    build-essential \
    cmake \
    protobuf-compiler \
    libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# PINOKIO-MATCHED INSTALLATION ORDER
# Following install.js exactly to prevent huggingface-hub version conflicts
# =============================================================================

# Step 1: Conda packages first (pynini + portaudio + scipy/numpy from conda-forge)
# CRITICAL: Install scipy/numpy from conda for proper ABI compatibility
# scipy 1.11.x works with numpy 1.26.x; scipy 1.14+ requires numpy 2.x
RUN conda install -c conda-forge pynini==2.1.6 portaudio scipy=1.11.4 numpy=1.26.4 -y && \
    conda clean -afy

# Step 2: Clone from PMOVES fork (same requirements.txt as SUP3RMASS1VE)
RUN git clone --depth 1 https://github.com/POWERFULMOVES/PMOVES-Ultimate-TTS-Studio.git app

WORKDIR /build/app

# Step 3: Install gradio and devicetorch FIRST (matches Pinokio pre-install step)
# This establishes correct dependency versions before requirements.txt
RUN pip install --upgrade pip && \
    pip install gradio devicetorch

# Step 4: Pin huggingface-hub to <1.0 BEFORE requirements.txt
# CRITICAL: Many TTS engines require huggingface-hub>=0.25.0,<1.0
# If we don't pin this, pip will install 1.2.3+ which breaks everything
RUN pip install "huggingface-hub>=0.25.0,<1.0"

# Step 5a: Pre-install packages that fail to build from source
# - onnx wheel build fails in Docker, use pre-built wheel
# - s3tokenizer depends on onnx
# NOTE: scipy/numpy already installed from conda in Step 1
RUN pip install \
    onnx==1.16.0 \
    s3tokenizer>=0.1.6

# Step 5b: Create constraint file to STRICTLY prevent pip from upgrading scipy/numpy
# Use exact versions to prevent ANY upgrades
RUN echo "onnx==1.16.0" > /tmp/constraints.txt && \
    echo "scipy==1.11.4" >> /tmp/constraints.txt && \
    echo "numpy==1.26.4" >> /tmp/constraints.txt && \
    echo "pydantic<2.12" >> /tmp/constraints.txt

# Step 5c: Install requirements.txt with strict constraints
RUN pip install -c /tmp/constraints.txt -r requirements.txt || \
    pip install --use-deprecated=legacy-resolver -c /tmp/constraints.txt -r requirements.txt

# Step 5d: Skipped deepspeed compilation (removing it later to avoid runtime crashes)


# Step 6: WeTextProcessing without deps (matches Pinokio WeTextProcessing step)
RUN pip install WeTextProcessing --no-deps || true

# Step 7: Fix phonemizer-fork (matches Pinokio phonemizer replacement)
RUN pip uninstall -y phonemizer 2>/dev/null || true && \
    pip install phonemizer-fork

# Step 8: Upgrade onnxruntime-gpu (matches Pinokio onnxruntime step)
RUN pip install -c /tmp/constraints.txt --upgrade --force-reinstall --no-deps --no-cache-dir onnxruntime-gpu==1.22.0

# Step 9: voxcpm and openai-whisper without deps (matches Pinokio voxcpm step)
RUN pip install -c /tmp/constraints.txt voxcpm openai-whisper --no-deps || true

# Step 10: Triton for GPU (from Pinokio torch.js) - with constraints
RUN pip install -c /tmp/constraints.txt triton

# Step 11: MCP for Gradio MCP server support - with constraints
# MCP pulls in pydantic 2.12+ which can cascade to scipy/numpy upgrades
RUN pip install -c /tmp/constraints.txt mcp

# Step 12: Download spacy model
RUN python -m spacy download en_core_web_sm || true

# Step 12b: FINAL FIX - Ensure scipy/numpy ABI compatibility
# - Force reinstall numpy/scipy to fix mixed conda/pip state
# - Remove deepspeed to prevent transformers runtime crashes
# - Upgrade numba/llvmlite to fix deprecation errors
# - Nuke numpy/_core artifact if it survives reinstall
RUN pip uninstall -y numpy deepspeed || true && \
    rm -rf /opt/conda/lib/python3.11/site-packages/numpy* && \
    pip install --force-reinstall "numpy==1.26.4" "scipy==1.11.4" && \
    pip install --upgrade numba llvmlite && \
    rm -rf /opt/conda/lib/python3.11/site-packages/numpy/_core

# Step 13: Pre-download model checkpoints (matches Pinokio model download)
RUN huggingface-cli download cocktailpeanut/oa --local-dir ./checkpoints/openaudio-s1-mini --quiet || \
    echo "Model download will happen at runtime"

# =============================================================================
# Stage 2: Runtime - NVIDIA CUDA base for full GPU support
# =============================================================================
# Using nvidia/cuda base image for complete CUDA toolkit (includes nvrtc)
# This follows the hi-rag-gateway-v2-gpu pattern
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7861 \
    GRADIO_MCP_SERVER=true \
    HF_HOME=/data/hf \
    HUGGINGFACE_HUB_CACHE=/data/hf \
    XDG_CACHE_HOME=/data/cache \
    # CUDA library paths for ONNX and PyTorch
    LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/local/cuda/lib:/usr/lib/x86_64-linux-gnu:/opt/conda/lib:${LD_LIBRARY_PATH}" \
    PATH="/opt/conda/bin:${PATH}" \
    # WSL2/CUDA compatibility settings
    CUDA_FORCE_PTX_JIT=1 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    TORCH_CUDA_ARCH_LIST="5.0;5.2;6.0;6.1;7.0;7.5;8.0;8.6;9.0" \
    TORCH_CUDNN_V8_API_ENABLED=1

# Runtime system dependencies + CUDA runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    libsndfile1 \
    libportaudio2 \
    libaio1 \
    libsox3 \
    sox \
    curl \
    # CUDA runtime libraries for ONNX GPU provider
    cuda-nvrtc-12-4 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user following PMOVES.AI standards (UID 65532)
RUN groupadd -g 65532 pmoves && \
    useradd -u 65532 -g pmoves -d /app -s /bin/bash pmoves

# Copy Python environment from builder (includes all installed packages)
COPY --from=builder /opt/conda /opt/conda

# Copy application code (includes pre-downloaded checkpoints from builder)
COPY --from=builder /build/app /app

# Create directories for models and cache
RUN mkdir -p /app/outputs /app/models /data/hf /data/cache && \
    chown -R pmoves:pmoves /app /data

WORKDIR /app

# Switch to non-root user
USER pmoves

EXPOSE 7861

# Health check (start-period allows time for model loading)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:7861/gradio_api/info || exit 1

CMD ["python", "launch.py"]
