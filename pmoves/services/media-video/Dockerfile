# Media Video Analyzer - GPU-enabled for PyTorch/YOLOv8
# Base image: cu128 required for ARM64 (GB10/Jetson) — cu124 has no ARM64 wheels
ARG CUDA_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu22.04
FROM ${CUDA_IMAGE}

# Install Python 3.11 and required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip python3.11-dev \
    ffmpeg ca-certificates curl && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
# Security: Force weights_only=True for torch.load() (prevents arbitrary code execution)
ENV TORCH_FORCE_WEIGHTS_ONLY_LOAD=1
# timm 0.9.16 runs @torch.jit.script at IMPORT time (timm/layers/activations_me.py),
# and torch.jit compilation SEGFAULTS on aarch64 + torch 2.9 (exit 139, reproduced
# via faulthandler: torch/jit/_script.py:_script_impl). transformers imports timm
# eagerly when building the DETR pipeline (modeling_detr.py), so without this the
# model-loader thread kills the container in a restart loop. PYTORCH_JIT=0 is the
# documented torch knob that makes torch.jit.script an identity function; the DETR
# and YOLO inference paths do not depend on jit scripting.
ENV PYTORCH_JIT=0

RUN pip install --no-cache-dir --upgrade pip

# Build context is ./services/media-video (service directory)
# Security: Reproducible builds from lockfile
COPY requirements.txt requirements.lock requirements.arm64.lock ./
# Install torch from cu128 index FIRST (matching Hi-RAG GPU pattern).
ARG TORCH_CUDA=cu128
ARG TORCH_VERSION=2.9.0
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/${TORCH_CUDA} \
      torch==${TORCH_VERSION}

# Then install remaining deps
RUN --mount=type=cache,target=/root/.cache/pip \
    # amd64 uses the x86-resolved lock; arm64/Jetson uses the aarch64-compiled
    # lock (requirements.arm64.lock, pins from arm64-overrides.txt). The
    # unpinned requirements.txt path is retired on arm64: it floated
    # torch 2.13.0 + transformers 5.15.1 (torch._dynamo died at import and the
    # DETR pipeline never loaded). The preinstall pins the wheel SOURCE
    # (single index) for the torchvision pair member; the lock then sees its
    # torch/torchvision pins already satisfied (torch came from the step above).
    if [ "$(uname -m)" = "x86_64" ]; then \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/${TORCH_CUDA} -r requirements.lock; \
    else \
      pip install --no-cache-dir --index-url https://download.pytorch.org/whl/${TORCH_CUDA} torchvision==0.24.0 && \
      pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/${TORCH_CUDA} -r requirements.arm64.lock; \
    fi
COPY . ./

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8079

# Health check — real HTTP probe now that server.py exposes /healthz.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8079/healthz || exit 1
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","8079"]
